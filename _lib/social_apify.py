#!/usr/bin/env python3
"""
TikTok + Instagram mentions via Apify (paid, per-result — kept deliberately
shallow here to stay cheap and not compete for budget with the existing
twice-daily mention alarm in marketing/performance, which shares the same
$5/mo Apify free plan).

Actor names and record shapes are reused as-is from
marketing/performance/_system/mention_alert.py (verified working there).

Known, accepted limits (see memory: social-mention-alarm):
  - Instagram has no public caption search — only @-tagged posts and the
    #cobasdaughter hashtag feed are discoverable.
  - TikTok search/hashtag results are POPULARITY-ranked, not date-filtered
    (clockworks' date-sort params have been under maintenance since Aug 2026),
    so old viral posts resurface. Each result still carries its own real
    creation date, so historical bucketing by post date is accurate even
    though "what's new today" from the search alone is not reliable.
"""
import os, re, json, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

IG_BRAND_HANDLES = ["cobasdaughter", "cobasdaughterusa"]
HASHTAGS_TO_POLL = ["cobasdaughter"]

IG_TAGGED_ACTOR  = "apify~instagram-tagged-scraper"
IG_HASHTAG_ACTOR = "apify~instagram-hashtag-scraper"
TT_ACTOR         = "clockworks~tiktok-scraper"

APIFY_SYNC = "https://api.apify.com/v2/acts/{}/run-sync-get-dataset-items?token={}&timeout=300"

# Kept shallow on purpose — see module docstring. ~$0.02-0.04/day at this depth.
TT_RESULTS = int(os.environ.get("BST_TT_RESULTS", "8"))
IG_RESULTS = int(os.environ.get("BST_IG_RESULTS", "8"))


def _envfile(name, key):
    p = os.path.join(ROOT, "_system", name)
    if os.path.exists(p):
        for ln in open(p):
            if ln.startswith(key):
                return ln.split("=", 1)[1].strip()
    return ""


def apify_token():
    return os.environ.get("APIFY_TOKEN", "").strip() or _envfile(".apify_env", "APIFY_TOKEN")


def _post(url, payload, timeout=300):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _iso(v):
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
        return v
    except Exception:
        return None


def fetch_tiktok():
    tok = apify_token()
    if not tok:
        print("  ! no APIFY_TOKEN — TikTok skipped")
        return []
    out = []
    jobs = [
        ({"hashtags": HASHTAGS_TO_POLL, "resultsPerPage": TT_RESULTS}, "tt/hashtag"),
    ]
    for payload, tag in jobs:
        try:
            for it in _post(APIFY_SYNC.format(TT_ACTOR, tok), payload):
                url = it.get("webVideoUrl")
                if not url:
                    continue
                author = (it.get("authorMeta") or {}).get("name")
                out.append({
                    "platform": "tiktok",
                    "id": "tt:" + url,
                    "url": url,
                    "author": author,
                    "caption": it.get("text") or "",
                    "ts": _iso(it.get("createTimeISO") or it.get("createTime")),
                    "source": tag,
                    "engagement": {
                        "views": it.get("playCount"),
                        "likes": it.get("diggCount"),
                        "comments": it.get("commentCount"),
                        "shares": it.get("shareCount"),
                    },
                })
        except Exception as e:
            print(f"  ! TikTok {tag} failed: {e}")
    return out


def fetch_instagram():
    tok = apify_token()
    if not tok:
        print("  ! no APIFY_TOKEN — Instagram skipped")
        return []
    out = []
    try:
        items = _post(APIFY_SYNC.format(IG_TAGGED_ACTOR, tok),
                       {"username": [IG_BRAND_HANDLES[0]], "resultsLimit": IG_RESULTS})
        out += [_ig_rec(it, "ig-apify/tagged") for it in items]
    except Exception as e:
        print(f"  ! IG tagged scrape failed: {e}")
    try:
        items = _post(APIFY_SYNC.format(IG_HASHTAG_ACTOR, tok),
                       {"hashtags": HASHTAGS_TO_POLL, "resultsLimit": IG_RESULTS})
        out += [_ig_rec(it, "ig-apify/hashtag") for it in items]
    except Exception as e:
        print(f"  ! IG hashtag scrape failed: {e}")
    return [r for r in out if r]


def _ig_rec(it, source):
    url = it.get("url") or it.get("inputUrl")
    if not url:
        return None
    owner = it.get("ownerUsername") or it.get("username")
    cap = it.get("caption") or ""
    return {
        "platform": "instagram",
        "id": "ig:" + url,
        "url": url,
        "author": owner,
        "caption": cap,
        "ts": _iso(it.get("timestamp")),
        "source": source,
        "engagement": {
            "views": it.get("videoViewCount"),
            "likes": it.get("likesCount"),
            "comments": it.get("commentsCount"),
        },
    }


def fetch_all_social():
    return fetch_tiktok() + fetch_instagram()


if __name__ == "__main__":
    for name, fn in (("TikTok", fetch_tiktok), ("Instagram", fetch_instagram)):
        r = fn()
        print(f"\n=== {name}: {len(r)} items ===")
        for x in r[:5]:
            print(f"   {(x.get('ts') or '?')[:10]}  @{x.get('author')}  {(x.get('caption') or '')[:60]!r}")
            print(f"      {x.get('url')}")
