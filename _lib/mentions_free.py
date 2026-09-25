#!/usr/bin/env python3
"""
Free, keyless mention sources: Reddit + Google News + Bing News.

Adapted from marketing/performance/_system/sources.py (same brand, same proven
endpoints) — Reddit's .json search is blocked to anonymous clients, search.rss
still works; Google/Bing News RSS need no key either.

2026-09-25 — coverage fix: added common misspelled forms to the query itself
(a search engine won't fuzzy-match "cobasdaugther" against a query for
"cobasdaughter" the way a human would), and every result is now re-verified
against brandmatch.py (marketing/performance's proven typo-tolerant matcher,
distance<=2, transposition-aware) before being kept — so the broader query
doesn't let unrelated results (e.g. "cobalt", "my daughter") through.
"""
import os, re, sys, time, hashlib, urllib.request, urllib.parse
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brandmatch  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) CoBaBrandTracker/1.0")

# One combined OR-query, not several separate ones — Reddit 429s on repeated hits.
OR_QUERY = ('"coba\'s daughter" OR cobasdaughter OR "cobas daughter" OR cobadaughter '
            'OR cobasdaugther OR "coba daughter"')


def _fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _iso(dt):
    try:
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _rfc822(s):
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            d = datetime.strptime(s.strip(), fmt)
            return _iso(d if d.tzinfo else d.replace(tzinfo=timezone.utc))
        except Exception:
            pass
    return None


def _uid(prefix, s):
    return f"{prefix}:" + hashlib.sha1(s.encode()).hexdigest()[:16]


def fetch_reddit(limit=25):
    out, ns = [], {"a": "http://www.w3.org/2005/Atom"}
    url = ("https://www.reddit.com/search.rss?"
           f"q={urllib.parse.quote(OR_QUERY)}&sort=new&limit={limit}&t=year")
    root = None
    for attempt in range(3):
        try:
            root = ET.fromstring(_fetch(url))
            break
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            print(f"  ! Reddit failed: {e}")
            return out
    if root is not None:
        for e in root.findall("a:entry", ns):
            link_el = e.find("a:link", ns)
            link = (link_el is not None and link_el.get("href")) or ""
            title = (e.findtext("a:title", "", ns) or "").strip()
            body = re.sub(r"<[^>]+>", " ", e.findtext("a:content", "", ns) or "")
            auth = e.find("a:author", ns)
            out.append({
                "platform": "reddit",
                "id": _uid("rd", link or title),
                "url": link,
                "author": (auth.findtext("a:name", "", ns) if auth is not None else None),
                "caption": f"{title}\n{body}"[:2000],
                "ts": e.findtext("a:updated", None, ns),
                "source": "reddit/search",
            })
    return [r for r in out if brandmatch.matches(text=r.get("caption"))]


def _rss_items(xml, source, platform="web"):
    out = []
    try:
        root = ET.fromstring(xml)
    except Exception:
        return out
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        title = (it.findtext("title") or "").strip()
        desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
        if not link:
            continue
        src_tag = it.findtext("source") or ""
        out.append({
            "platform": platform,
            "id": _uid("web", link),
            "url": link,
            "author": (src_tag or urllib.parse.urlparse(link).netloc or None),
            "caption": f"{title}\n{desc}"[:2000],
            "ts": _rfc822(it.findtext("pubDate") or ""),
            "source": source,
        })
    return out


def fetch_web():
    out = []
    qq = urllib.parse.quote(OR_QUERY)
    for url, tag in (
        (f"https://news.google.com/rss/search?q={qq}&hl=en-US&gl=US&ceid=US:en", "web/google-news"),
        (f"https://www.bing.com/news/search?q={qq}&format=RSS", "web/bing-news"),
    ):
        try:
            out += _rss_items(_fetch(url), tag)
        except Exception as e:
            print(f"  ! {tag} failed: {e}")
    return [r for r in out if brandmatch.matches(text=r.get("caption"))]


def fetch_all_free():
    return fetch_reddit() + fetch_web()


if __name__ == "__main__":
    for name, fn in (("Reddit", fetch_reddit), ("Web/news", fetch_web)):
        r = fn()
        print(f"\n=== {name}: {len(r)} items ===")
        for x in r[:5]:
            print(f"   {(x.get('ts') or '?')[:10]}  {str(x.get('author'))[:26]:26} {(x.get('caption') or '')[:58]!r}")
            print(f"      {x.get('url')}")
