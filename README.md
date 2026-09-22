# Brand Search & Mentions Tracker — CoBa's Daughter

Tracks brand mentions across TikTok, Instagram, Reddit and web/news, plus brand
search volume, with a period picker and 5 built-in comparisons (vs last week,
last month, last quarter, last comparable period, last year).

## Run it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 fetch_mentions.py          # pulls Reddit + web/news (free) + TikTok/IG (Apify)
python3 fetch_mentions.py --free-only   # skip Apify (no cost)
python3 _lib/search_volume.py      # re-parse whatever's in data/amazon_awareness/ + data/google_trends/
python3 build_dashboard.py         # writes output/index.html
```

Open `output/index.html` directly in a browser — it's fully self-contained,
no server needed.

## Data sources

| Source | How | Cost | Live? |
|---|---|---|---|
| Reddit | `search.rss`, keyless (the `.json` endpoint is blocked to anonymous clients) | free | yes, headless |
| Web / news | Google News + Bing News RSS, keyless | free | yes, headless |
| TikTok | Apify `clockworks~tiktok-scraper`, hashtag `#cobasdaughter` | ~$0.02–0.04/run at current depth (`BST_TT_RESULTS=8`) | yes, headless |
| Instagram | Apify `apify~instagram-tagged-scraper` + `apify~instagram-hashtag-scraper` | ~$0.02–0.04/run | yes, headless |
| Amazon Branded Search | **manual** — drop an Amazon Brand Analytics "Awareness Trends" CSV into `data/amazon_awareness/` | free | monthly, manual |
| Google search interest | **manual** — drop a CSV exported from trends.google.com for the brand keyword into `data/google_trends/` | free | manual |

**Why search volume is manual:** tested live (2026-09-22) — Google Trends
returns essentially no data for "CoBa's Daughter" at any useful resolution;
the brand's query volume is below its indexing floor. Amazon Branded Search is
real counted data but only available as a monthly export. Rather than
automate something that would mostly show empty/misleading flat lines, both
panels render honestly ("no export yet") until real data is dropped in.

**Cost note:** TikTok/Instagram scraping reuses the same Apify token as the
existing twice-daily mention alarm in `marketing/performance/`
(`_system/.apify_env`), which shares a $5/mo free-plan budget. This tool is
tuned to a shallow depth (8 results/platform) specifically to avoid competing
for that budget — adds roughly $1–2/mo on top of the existing ~$3.60/mo usage.
If Apify usage needs to be cut, lower `BST_TT_RESULTS` / `BST_IG_RESULTS` env
vars or drop `--free-only` runs in between.

## Known platform limits (verified, not assumed)

- **Instagram has no public caption search** — only @-tagged posts and the
  `#cobasdaughter` hashtag feed are discoverable. An untagged mention is
  invisible to this tool (same limit as the existing mention alarm).
- **TikTok search/hashtag results are popularity-ranked, not date-filtered**
  (clockworks' date-sort params have been under maintenance since Aug 2026),
  so old viral posts can resurface in any given pull. Each result still
  carries its own real post date, so the historical trend chart (bucketed by
  post date) stays accurate even though a single day's *discovery* isn't a
  reliable "what's new today" signal.

## Files

- `fetch_mentions.py` — orchestrates all mention sources, merges into
  `data/mentions.json` (deduped by id, dates never overwritten once seen).
- `_lib/mentions_free.py` — Reddit + web/news RSS fetchers.
- `_lib/social_apify.py` — TikTok + Instagram via Apify.
- `_lib/search_volume.py` — parses the manual CSV drop folders into
  `data/search_volume.json`.
- `build_dashboard.py` — renders `output/index.html` from the two data files.
  All period-picking and comparison math runs client-side in JS against the
  embedded daily series — no rebuild needed to change the date range.

## Automating it (not yet set up)

The mention fetchers (Reddit/web/TikTok/IG) can all run headless on a daily
GitHub Actions cron, same pattern as the existing `cobasdaughter-engine` repo.
The search-volume panels stay manual either way. Not deployed yet — ask to set
up a repo + Pages + cron once you're happy with the local build.
