# Brand Search & Mentions Tracker — CoBa's Daughter

Tracks brand mentions across TikTok, Instagram, Reddit and web/news, plus brand
search volume, with a period picker and 5 built-in comparisons (vs last week,
last month, last quarter, last comparable period, last year). Every source
polls typo/spelling variants (not just the exact "cobasdaughter" spelling)
and every result is verified against `_lib/brandmatch.py` — see "Typo &
variant coverage" below.

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
| **TikTok — own channel** | **Official Display API** (`/user/info/` + `/video/list/`) via your TikTok Developer App, OAuth-connected to `@cobasdaughter.official` | **free** | **exact** — TikTok's own view/like/comment/share counts for all 241+ own videos |
| TikTok — earned (other creators) | Apify `clockworks~tiktok-scraper`, hashtag `#cobasdaughter` | ~$0.02–0.04/run at current depth (`BST_TT_RESULTS=8`) | approximate — see note below |
| Amazon Branded Search | **manual** — drop an Amazon Brand Analytics "Awareness Trends" CSV into `data/amazon_awareness/` | free | exact, monthly |
| Google search interest | **manual** — drop a CSV exported from trends.google.com for the brand keyword into `data/google_trends/` | free | exact, manual |

**Why Instagram moved off Apify (2026-09-23):** the user's Meta Developer App
now has a real access token, unlocking the official Graph API — free and more
precise than a scraper for both @-tagged posts and the `#cobasdaughter`
hashtag feed. See `_lib/social_meta.py`.

**TikTok is now split into two genuinely different capabilities (2026-09-23):**
- **Owned channel** (`_lib/social_tiktok_official.py`) — the brand's own
  `@cobasdaughter.official` posts, via the official Display API. OAuth-connected
  once (`_system/tiktok_oauth.py`); free, exact, no Apify involved. Rendered as
  its own "Owned TikTok channel" section — kept separate from the mentions feed
  on purpose, since 241+ owned videos would otherwise drown out the handful of
  real earned mentions per platform.
- **Earned mentions** (other creators' videos) — still Apify. Verified directly
  against TikTok's current official documentation (2026-09-23): the only
  API product that supports keyword/hashtag/username video search, the
  Research API, states explicitly **"Commercial users, creators, and
  advertisers are explicitly ineligible."** Login Kit / Display API (any
  standard "TikTok App," including yours) has no search parameter at all — it
  is architecturally read-only-your-own-content. So there is no official
  substitute for earned TikTok mentions, at any app tier, for a commercial
  brand — Apify (kept shallow, cost-capped) is what's left. If TikTok ever
  changes this policy, tell me and this gets replaced too.

**TikTok OAuth notes for future reference:**
- Access tokens die in **24h**; the refresh token lasts **1 year** and,
  verified live, is **not rotated on use** — one stored refresh token is
  durable, no secret-rotation workflow needed. `social_tiktok_official.py`
  calls `tiktok_oauth.refresh()` before every use rather than tracking expiry.
- TikTok's OAuth now requires **PKCE** (`code_challenge`/`code_verifier`) —
  `tiktok_oauth.py` handles this automatically.
- **`localhost` redirect URIs are rejected** by TikTok's app settings (unlike
  most OAuth providers). Used the already-registered
  `cobasdaughter-brand-pulse.onrender.com` redirect instead — that app's own
  page rejects the login session (it's a different app's callback route, by
  a different tool), but the `code` still lands in the browser's address bar
  regardless of what the destination page renders, which is all that's
  actually needed.
- The sandbox app's Client Key carries an `sbaw` prefix — TikTok's convention
  for Sandbox apps, which only complete login for accounts explicitly added
  as **Target Users** in the developer portal. `@cobasdaughter.official` is
  added there.

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

- `_system/.apify_env` — `APIFY_TOKEN` (TikTok earned-mentions only now).
- `_system/.meta_env` — `META_TOKEN` + `IG_USER_ID` (Instagram, official
  Graph API). Same account id already known from the existing mention alarm
  (`17841465909445061`), defaulted in `social_meta.py` — override in this
  file if the token is for a different IG Business account.
- `_system/.tiktok_env` — `TIKTOK_CLIENT_KEY` + `TIKTOK_CLIENT_SECRET` +
  `TIKTOK_ACCESS_TOKEN` + `TIKTOK_REFRESH_TOKEN` + `TIKTOK_OPEN_ID` (TikTok
  owned-channel, official Display API). Generated via `_system/tiktok_oauth.py`
  — see its docstring for the one-time OAuth login flow.

All three files are gitignored. In GitHub Actions these are read from repo
secrets — set via **Settings → Secrets and variables → Actions** (writing
secrets isn't something this session's automation is able to do on your
behalf; it's a manual one-time step):

| Secret | Source |
|---|---|
| `APIFY_TOKEN` | `_system/.apify_env` |
| `META_TOKEN` | `_system/.meta_env` |
| `IG_USER_ID` | `_system/.meta_env` |
| `TIKTOK_CLIENT_KEY` | `_system/.tiktok_env` |
| `TIKTOK_CLIENT_SECRET` | `_system/.tiktok_env` |
| `TIKTOK_REFRESH_TOKEN` | `_system/.tiktok_env` |

## Typo & variant coverage (2026-09-25)

Every source used to poll only the single exact spelling "cobasdaughter."
Hashtag search (Instagram, TikTok) has **no fuzzy option** — `#cobasdaugther`
is a completely different, separately-indexed hashtag from `#cobasdaughter`
to the platform, so a real post using the misspelled tag was structurally
invisible no matter how deep the search went. Fixed by:

- Polling a fixed list of ~6 real-world spellings (`cobasdaughter`,
  `cobadaughter`, `cobasdaugther`, `cobasdaughters`, `cobasdaughterusa`,
  `cobasdaughterofficial`) on every hashtag-based source.
- Broadening the Reddit/web text query with the same misspelled forms.
- Verifying **every** result (from every source) against `_lib/brandmatch.py`
  — ported from the proven, self-tested matcher already used by the
  performance repo's mention alarm (Damerau-Levenshtein distance ≤2,
  transposition-aware, `python3 _lib/brandmatch.py` runs its 38-case
  self-test). This is what keeps a wider net from also letting unrelated
  content in.

Measured effect: one fetch run went from 58 to 67 stored mentions with this
change alone, picking up real posts (e.g. under `#cobadaughter`) that the
exact-spelling-only version could never have found.

**Honest ceiling — worth saying plainly:** no method, official API or
scraper, can guarantee "every mention on social media." Platforms only
expose what their own public search/hashtag/tag surfaces choose to index —
that's true for TikTok's popularity-ranked results and for Instagram's
hashtag feed alike. This fix closes the specific, provable gap (spelling
variants), not that ceiling.

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
- `_lib/social_tiktok_official.py` — the brand's own TikTok channel via the
  official Display API (owned-channel stats, `data/tiktok_own.json` — kept
  out of the mentions feed on purpose, see above).
- `_lib/social_apify.py` — TikTok earned mentions via Apify (the one
  remaining paid source; no official alternative exists for a commercial brand).
- `_system/tiktok_oauth.py` — one-time OAuth login + token refresh for the
  TikTok Display API.
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
