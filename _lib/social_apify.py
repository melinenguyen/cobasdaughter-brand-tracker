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

2026-09-25 — coverage fix: was only polling the single exact hashtag
"cobasdaughter", so any real video tagged #cobadaughter, #cobasdaugther,
#cobasdaughters etc. was invisible — TikTok hashtags have no fuzzy search,
each spelling is queried separately. Expanded HASHTAGS_TO_POLL to the same
proven variant list used for Instagram (see social_meta.py), and every result
is now re-verified against brandmatch.py so a broader net doesn't let
unrelated content in.

COST NOTE: passing N hashtags to one Apify call returns up to N×TT_RESULTS
items, so this run costs roughly 6x what the single-hashtag version did —
~$0.12-0.24/run at the current depth (was ~$0.02-0.04). Combined with the
existing twice-daily mention alarm in marketing/performance (~$3.60/mo), this
tool's own daily run adds roughly $3.60-7/mo, which can approach or exceed
the shared $5/mo Apify free-plan budget those other jobs are tuned around.
Lower BST_TT_RESULTS if that budget needs protecting.
"""
import os, re, sys, json, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import brandmatch  # noqa: E402

HASHTAGS_TO_POLL = [
    "cobasdaughter", "cobadaughter", "cobasdaugther",
    "cobasdaughters", "cobasdaughterusa", "cobasdaughterofficial",
]
TT_ACTOR = "clockworks~tiktok-scraper"

APIFY_SYNC = "https://api.apify.com/v2/acts/{}/run-sync-get-dataset-items?token={}&timeout=300"

# See COST NOTE above — was shallow-on-purpose at 1 hashtag; now spread across 6.
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

    seen, deduped = set(), []
    for r in out:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        deduped.append(r)
    return [r for r in deduped if brandmatch.matches(text=r.get("caption"))]


if __name__ == "__main__":
    r = fetch_tiktok()
    print(f"=== TikTok: {len(r)} items ===")
    for x in r[:5]:
        print(f"   {(x.get('ts') or '?')[:10]}  @{x.get('author')}  {(x.get('caption') or '')[:60]!r}")
        print(f"      {x.get('url')}")
