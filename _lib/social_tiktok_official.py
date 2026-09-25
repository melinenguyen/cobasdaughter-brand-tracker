#!/usr/bin/env python3
"""
The brand's OWN TikTok channel (@cobasdaughter.official) via the official
Display API — free, exact (Meta/TikTok's own counts, not a scraped estimate).

This is a NEW capability, not a replacement: it covers owned-channel
performance (your own 241+ videos, follower count, per-video views/likes/
comments/shares), which nothing in this tool tracked before. It does NOT
cover third-party/earned mentions (other creators' videos) — TikTok's
Display API only ever grants access to the token-holder's own content, by
design. Earned mentions still rely on social_apify.py (see its docstring for
why: TikTok's only search-capable official API, Research API, explicitly
excludes commercial brands — verified against developers.tiktok.com,
2026-09-23).

Auth: _system/tiktok_oauth.py handles the one-time OAuth login + token
refresh. This module just calls tiktok_oauth.refresh() to get a live access
token (access tokens die in 24h; the refresh token lasts a year and, verified
2026-09-23, is NOT rotated on use, so one stored refresh token is durable).
"""
import os, sys, json, urllib.request, urllib.error
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "_system"))
import tiktok_oauth  # noqa: E402

API = "https://open.tiktokapis.com/v2"
USER_FIELDS = "open_id,display_name,avatar_url,follower_count,following_count,likes_count,video_count"
VIDEO_FIELDS = "id,title,video_description,create_time,cover_image_url,share_url,view_count,like_count,comment_count,share_count"


def _token():
    return tiktok_oauth.refresh() or (
        os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip() or tiktok_oauth._envfile("TIKTOK_ACCESS_TOKEN")
    )


def _get(url, tok):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _post(url, tok, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_user_stats():
    tok = _token()
    if not tok:
        print("  ! no TikTok token — run _system/tiktok_oauth.py first")
        return None
    try:
        d = _get(f"{API}/user/info/?fields={USER_FIELDS}", tok)
        return d.get("data", {}).get("user")
    except urllib.error.HTTPError as e:
        # user.info.stats wasn't granted on this authorization (happened once,
        # 2026-09-25) — fall back to basic fields rather than losing the whole run
        print(f"  ! full user/info fields failed ({e.code}), retrying with basic fields only")
        d = _get(f"{API}/user/info/?fields=open_id,display_name,avatar_url", tok)
        return d.get("data", {}).get("user")


def fetch_own_videos(max_pages=10):
    """Paginates the full video list (241+ videos as of 2026-09-23)."""
    tok = _token()
    if not tok:
        return []
    out, cursor, has_more, page = [], 0, True, 0
    while has_more and page < max_pages:
        body = {"max_count": 20}
        if cursor:
            body["cursor"] = cursor
        d = _post(f"{API}/video/list/?fields={VIDEO_FIELDS}", tok, body)
        data = d.get("data", {})
        for v in data.get("videos", []):
            out.append({
                "platform": "tiktok",
                "id": "tt-own:" + str(v["id"]),
                "url": v.get("share_url"),
                "author": "cobasdaughter.official",
                "caption": v.get("video_description") or v.get("title") or "",
                "ts": datetime.fromtimestamp(v["create_time"], tz=timezone.utc).isoformat() if v.get("create_time") else None,
                "source": "tiktok-official/own-video",
                "engagement": {
                    "views": v.get("view_count"), "likes": v.get("like_count"),
                    "comments": v.get("comment_count"), "shares": v.get("share_count"),
                },
            })
        cursor = data.get("cursor")
        has_more = data.get("has_more", False)
        page += 1
    return out


if __name__ == "__main__":
    stats = fetch_user_stats()
    print("=== Account stats ===")
    print(json.dumps(stats, indent=2))
    vids = fetch_own_videos(max_pages=1)
    print(f"\n=== First page of own videos: {len(vids)} ===")
    for v in vids[:5]:
        print(f"   {(v['ts'] or '?')[:10]}  views={v['engagement']['views']}  {v['caption'][:50]!r}")
