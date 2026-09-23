# Brand Search & Mentions Tracker — CoBa's Daughter

Tracks brand mentions across TikTok, Instagram, Reddit and web/news, plus brand
search volume, with a period picker and 5 built-in comparisons (vs last week,
last month, last quarter, last comparable period, last year).

**Live:** https://melinenguyen.github.io/cobasdaughter-brand-tracker/

## Run it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 fetch_mentions.py             # Reddit + web/news (free) + Instagram (official Graph API) + TikTok (Apify)
python3 fetch_mentions.py --no-tiktok # skip the one remaining paid source (no cost)
python3 _lib/search_volume.py         # re-parse whatever's in data/amazon_awareness/ + data/google_trends/
python3 build_dashboard.py            # writes output/index.html
```

Open `output/index.html` directly in a browser — it's fully self-contained,
no server needed.

## Data sources

| Source | How | Cost | Precision |
|---|---|---|---|
| Reddit | `search.rss`, keyless (the `.json` endpoint is blocked to anonymous clients) | free | exact |
| Web / news | Google News + Bing News RSS, keyless | free | exact |
| **Instagram** | **Official Meta Graph API** (`/tags` + `ig_hashtag_search`) via your Meta Developer App | **free** | **exact** — Meta's own timestamps + like/comment counts, not a scraped estimate |
| TikTok | Apify `clockworks~tiktok-scraper`, hashtag `#cobasdaughter` | ~$0.02–0.04/run at current depth (`BST_TT_RESULTS=8`) | approximate — see note below |
| Amazon Branded Search | **manual** — drop an Amazon Brand Analytics "Awareness Trends" CSV into `data/amazon_awareness/` | free | exact, monthly |
| Google search interest | **manual** — drop a CSV exported from trends.google.com for the brand keyword into `data/google_trends/` | free | exact, manual |

**Why Instagram moved off Apify (2026-09-23):** the user's Meta Developer App
now has a real access token, unlocking the official Graph API — free and more
precise than a scraper for both @-tagged posts and the `#cobasdaughter`
hashtag feed. See `_lib/social_meta.py`.

**Why TikTok still uses Apify:** TikTok's official developer API (Login Kit /
Display API — what a standard "TikTok App" gets you) only ever grants access
to *the connected account's own content*. There is no standard-tier API for
"find other creators' videos that mention us" — that capability (Research
API) is gated to approved academic/qualifying institutions only. Apify
scraping is the only mechanism that can currently catch third-party TikTok
mentions at all, so it stays, deliberately kept shallow to limit cost. If your
TikTok app is ever upgraded to Research/Content API access, tell me and this
gets replaced too.

**Instagram official-API limit (Meta platform behavior, not a bug):** the
`ig_hashtag_search` → `/recent_media` edge does not return the poster's
username — only `/tags` (posts that directly tagged the brand) does. Both
still carry exact timestamps and engagement counts.

**Why search volume is manual:** tested live (2026-09-22) — Google Trends
returns essentially no data for "CoBa's Daughter" at any useful resolution;
the brand's query volume is below its indexing floor. Amazon Branded Search is
real counted data but only available as a monthly export. Rather than
automate something that would mostly show empty/misleading flat lines, both
panels render honestly ("no export yet") until real data is dropped in.

## Credentials

- `_system/.apify_env` — `APIFY_TOKEN` (TikTok only now).
- `_system/.meta_env` — `META_TOKEN` + `IG_USER_ID` (Instagram, official
  Graph API). Same account id already known from the existing mention alarm
  (`17841465909445061`), defaulted in `social_meta.py` — override in this
  file if the token is for a different IG Business account.

Both files are gitignored. In GitHub Actions these are read from repo
secrets (`APIFY_TOKEN`, `META_TOKEN`, `IG_USER_ID`) — set via **Settings →
Secrets and variables → Actions** (writing secrets isn't something this
session's automation is able to do on your behalf; it's a manual one-time
step).

## Known platform limits (verified, not assumed)

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
- `_lib/social_meta.py` — Instagram via the official Meta Graph API.
- `_lib/social_apify.py` — TikTok via Apify (the one remaining paid source).
- `_lib/search_volume.py` — parses the manual CSV drop folders into
  `data/search_volume.json`. Merges onto whatever's already there — never
  regenerates from scratch, so a CI run with no dropped CSVs can't wipe real
  committed data (this bug happened once, 2026-09-22, and was fixed).
- `build_dashboard.py` — renders `output/index.html` from the two data files.
  All period-picking and comparison math runs client-side in JS against the
  embedded daily series — no rebuild needed to change the date range.

## Automation

GitHub Actions, `.github/workflows/daily-build.yml`, cron `0 6 * * *` (06:00
UTC = 13:00 ICT) + manual dispatch + push-on-code-change. Deploys to GitHub
Pages via `actions/deploy-pages` (Actions-based Pages source, no extra
token needed). The job commits `data/*.json` back to `main` each run so
history accumulates.
