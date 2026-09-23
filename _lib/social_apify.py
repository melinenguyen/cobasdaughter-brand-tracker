#!/usr/bin/env python3
"""
TikTok mentions via Apify — the ONLY source for third-party/earned TikTok
mentions. TikTok's official developer API (Login Kit / Display API) only ever
grants access to the connected account's OWN content; there is no standard-tier
API for "find other creators' videos that mention us" — that capability
(Research API) is gated to approved academic/qualifying institutions only.
So unlike Instagram (see social_meta.py, official Graph API, no Apify needed),
TikTok earned-mention discovery has no official replacement.

Actor name and record shape reused as-is from
marketing/performance/_system/mention_alert.py (verified working there).

Known, accepted limit (see memory: social-mention-alarm): TikTok search/hashtag
results are POPULARITY-ranked, not date-filtered (clockworks' date-sort params
have been under maintenance since Aug 2026), so old viral posts resurface.
Each result still carries its own real creation date, so historical bucketing
by post date is accurate even though "what's new today" from the search alone
is not reliable.
"""
import os, re, json, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

HASHTAGS_TO_POLL = ["cobasdaughter"]
TT_ACTOR = "clockworks~tiktok-scraper"

APIFY_SYNC = "https://api.apify.com/v2/acts/{}/run-sync-get-dataset-items?token={}&timeout=300"

# Kept shallow on purpose — see module docstring. ~$0.02-0.04/day at this depth.
TT_RESULTS = int(os.environ.get("BST_TT_RESULTS", "8"))


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


if __name__ == "__main__":
    r = fetch_tiktok()
    print(f"=== TikTok: {len(r)} items ===")
    for x in r[:5]:
        print(f"   {(x.get('ts') or '?')[:10]}  @{x.get('author')}  {(x.get('caption') or '')[:60]!r}")
        print(f"      {x.get('url')}")
