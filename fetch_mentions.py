#!/usr/bin/env python3
"""
Daily fetch: pulls every mention source, merges into the persistent history
data/mentions.json (deduped by id, never overwritten once seen — a source
resurfacing an old post just confirms a date we already have).

Instagram uses the official Meta Graph API (free, precise — see social_meta.py).
The brand's OWN TikTok channel also uses an official API now (social_tiktok_
official.py, free, exact) — but third-party/EARNED TikTok mentions still rely
on Apify (social_apify.py): TikTok's only search-capable official product,
Research API, explicitly excludes commercial brands, so there is no official
alternative for that one piece specifically.

  python3 fetch_mentions.py               # everything, incl. TikTok Apify (earned)
  python3 fetch_mentions.py --no-tiktok   # skip the one remaining paid source
"""
import os, sys, json, glob
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "_lib"))

import mentions_free           # noqa: E402
import social_meta             # noqa: E402
import social_apify            # noqa: E402
import social_tiktok_official  # noqa: E402

DATA = os.path.join(HERE, "data")
STORE = os.path.join(DATA, "mentions.json")
OWN_TIKTOK_STORE = os.path.join(DATA, "tiktok_own.json")
SEED_FLAG = os.path.join(DATA, ".seeded")


def load_store():
    if os.path.exists(STORE):
        with open(STORE) as f:
            return json.load(f)
    return {"mentions": {}}


def save_store(store):
    os.makedirs(DATA, exist_ok=True)
    with open(STORE, "w") as f:
        json.dump(store, f, indent=1, ensure_ascii=False)


def seed_from_baseline(store):
    """One-time import of the real dated records already sitting in the
    performance repo's day-1 baseline (marketing/performance/data/mentions.json)."""
    if os.path.exists(SEED_FLAG):
        return 0
    candidates = glob.glob(os.path.join(HERE, "..", "performance", "data", "mentions.json"))
    added = 0
    for p in candidates:
        try:
            d = json.load(open(p))
        except Exception:
            continue
        for m in d.get("mentions", []):
            if not m.get("date") or not m.get("url"):
                continue
            mid = f"seed:{m['platform']}:{m['url']}"
            if mid not in store["mentions"]:
                store["mentions"][mid] = {
                    "platform": m["platform"], "id": mid, "url": m["url"],
                    "author": m.get("handle") or m.get("creator"),
                    "caption": m.get("title") or "",
                    "ts": m["date"] + "T00:00:00Z",
                    "source": "seed/performance-baseline",
                }
                added += 1
    open(SEED_FLAG, "w").write(datetime.utcnow().isoformat())
    return added


def merge(store, records):
    added = 0
    for r in records:
        if not r.get("id") or not r.get("ts"):
            continue
        if r["id"] not in store["mentions"]:
            store["mentions"][r["id"]] = r
            added += 1
    return added


def fetch_own_tiktok():
    """Kept separate from data/mentions.json on purpose: these are the brand's
    OWN videos, not third-party buzz — mixing them into the mentions feed
    would make 241+ owned posts drown out the handful of real earned mentions
    per platform. Rendered as its own 'owned channel' panel instead."""
    stats = social_tiktok_official.fetch_user_stats()
    if stats is None:
        print("  ! TikTok official API unavailable (no token) — owned-channel stats skipped")
        return
    videos = social_tiktok_official.fetch_own_videos(max_pages=15)
    out = {
        "generated_utc": datetime.utcnow().isoformat() + "Z",
        "account": stats,
        "videos": videos,
    }
    with open(OWN_TIKTOK_STORE, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"  · tiktok_own.json: {stats.get('follower_count')} followers, {len(videos)} videos")


def main():
    skip_tiktok = "--no-tiktok" in sys.argv or "--free-only" in sys.argv  # --free-only kept as an alias
    store = load_store()

    seeded = seed_from_baseline(store)
    if seeded:
        print(f"  · imported {seeded} dated record(s) from the performance-repo baseline")

    total_new = 0
    print("Reddit + web/news (free)...")
    total_new += merge(store, mentions_free.fetch_all_free())

    print("Instagram (official Meta Graph API)...")
    total_new += merge(store, social_meta.fetch_instagram())

    print("TikTok — own channel (official Display API)...")
    fetch_own_tiktok()

    if not skip_tiktok:
        print("TikTok (Apify — no official alternative for earned mentions)...")
        total_new += merge(store, social_apify.fetch_tiktok())
    else:
        print("  · --no-tiktok: skipping TikTok")

    save_store(store)
    print(f"\n{total_new} new mention(s) added. Store now has {len(store['mentions'])} total.")


if __name__ == "__main__":
    main()
