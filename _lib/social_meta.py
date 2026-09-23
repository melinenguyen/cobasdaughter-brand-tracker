#!/usr/bin/env python3
"""
Instagram mentions via the OFFICIAL Meta Graph API — free, precise (exact
timestamps + like/comment counts from Meta itself, not a scraped estimate).
Replaces Apify for Instagram entirely.

Endpoints reused as proven in marketing/performance/_system/mention_alert.py:
  /{ig-user-id}/tags        — posts that @-tagged the brand account
  ig_hashtag_search + /recent_media — the #cobasdaughter hashtag feed

Needs a Meta access token + the IG Business account's numeric user id, with
scopes instagram_basic + instagram_manage_comments + pages_show_list +
pages_read_engagement (instagram_manage_comments is required specifically for
/tags — a token without it gets HTTP 400 "Application does not have
permission for this action"). See marketing/performance/_system/META_SETUP.md
for how the token is generated (Graph API Explorer).

Known limits (Meta platform behavior, verified against the real API, not bugs
in this code):
  - The hashtag /recent_media edge does not return the poster's username —
    only /tags (posts that tagged us directly) does. Both still give exact
    timestamps and engagement counts.
  - /tags with the full field set (caption + like_count + comments_count etc.)
    returns HTTP 500 "Please reduce the amount of data you're asking for"
    above limit=15, even though the identical request at limit=15 succeeds.
    Reproduced consistently (not transient) on 2026-09-23. Kept at TAGS_LIMIT
    below rather than trimming fields, since fields are cheap and frequency
    (daily) means 15 is plenty to catch everything since the last run.
"""
import os, re, json, urllib.request, urllib.parse
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

GRAPH = "https://graph.facebook.com/v21.0"
HASHTAGS_TO_POLL = ["cobasdaughter"]
IG_RESULTS = int(os.environ.get("BST_IG_RESULTS", "25"))
TAGS_LIMIT = int(os.environ.get("BST_IG_TAGS_LIMIT", "15"))  # see docstring — /tags 500s above ~15-20

# Known account id (not secret — just an id). Overridable via env/.meta_env.
DEFAULT_IG_USER_ID = "17841465909445061"


def _envfile(key):
    p = os.path.join(ROOT, "_system", ".meta_env")
    if os.path.exists(p):
        for ln in open(p):
            if ln.strip().startswith(key):
                return ln.split("=", 1)[1].strip()
    return ""


def meta_creds():
    tok = os.environ.get("META_TOKEN", "").strip() or _envfile("META_TOKEN")
    uid = os.environ.get("IG_USER_ID", "").strip() or _envfile("IG_USER_ID") or DEFAULT_IG_USER_ID
    return tok, uid


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _iso(ts):
    if not ts:
        return None
    s = str(ts).replace("Z", "+00:00")
    # Meta returns offsets as "+0000" (no colon) — datetime.fromisoformat only
    # accepts that form on Python 3.11+; insert the colon so 3.9/3.10 parse it too.
    if re.search(r"[+-]\d{4}$", s):
        s = s[:-2] + ":" + s[-2:]
    try:
        d = datetime.fromisoformat(s)
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).isoformat()
    except Exception:
        return None


def fetch_instagram():
    tok, uid = meta_creds()
    if not tok or not uid:
        print("  ! no META_TOKEN/IG_USER_ID — Instagram skipped (see README: connect your Meta app)")
        return []
    out = []
    fields = "id,permalink,caption,media_type,timestamp,username,like_count,comments_count"

    try:
        url = f"{GRAPH}/{uid}/tags?fields={fields}&limit={TAGS_LIMIT}&access_token={tok}"
        for it in _get(url).get("data", []):
            permalink = it.get("permalink")
            if not permalink:
                continue
            out.append({
                "platform": "instagram",
                "id": "ig:" + permalink,  # same key scheme as the old Apify path, so the same
                                          # real post never double-counts across a source switch
                "url": permalink,
                "author": it.get("username"),
                "caption": it.get("caption") or "",
                "ts": _iso(it.get("timestamp")),
                "source": "ig-graph/tags",
                "engagement": {"likes": it.get("like_count"), "comments": it.get("comments_count")},
            })
    except Exception as e:
        print(f"  ! IG Graph /tags failed: {e}")

    for tag in HASHTAGS_TO_POLL:
        try:
            hs = _get(f"{GRAPH}/ig_hashtag_search?user_id={uid}&q={urllib.parse.quote(tag)}&access_token={tok}")
            hid = (hs.get("data") or [{}])[0].get("id")
            if not hid:
                continue
            hf = "id,permalink,caption,media_type,timestamp,like_count,comments_count"
            url = f"{GRAPH}/{hid}/recent_media?user_id={uid}&fields={hf}&limit={IG_RESULTS}&access_token={tok}"
            for it in _get(url).get("data", []):
                permalink = it.get("permalink")
                if not permalink:
                    continue
                out.append({
                    "platform": "instagram",
                    "id": "ig:" + permalink,
                    "url": permalink,
                    "author": None,  # hashtag feed doesn't expose the poster's username (Meta limit)
                    "caption": it.get("caption") or "",
                    "ts": _iso(it.get("timestamp")),
                    "source": f"ig-graph/#{tag}",
                    "engagement": {"likes": it.get("like_count"), "comments": it.get("comments_count")},
                })
        except Exception as e:
            print(f"  ! IG Graph hashtag #{tag} failed: {e}")

    return out


if __name__ == "__main__":
    r = fetch_instagram()
    print(f"=== Instagram (official Graph API): {len(r)} items ===")
    for x in r[:10]:
        print(f"   {(x.get('ts') or '?')[:10]}  @{x.get('author')}  {(x.get('caption') or '')[:60]!r}  [{x.get('source')}]")
        print(f"      {x.get('url')}")
