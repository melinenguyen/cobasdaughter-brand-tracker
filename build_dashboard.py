#!/usr/bin/env python3
"""
Builds output/index.html — a single self-contained interactive dashboard.
All period-picking and comparison math runs client-side in JS against the
embedded daily series, so the viewer can pick any date range without a rebuild.
"""
import os, json
from datetime import datetime, timezone
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "output")

PLATFORMS = ["tiktok", "instagram", "reddit", "web"]
PLATFORM_LABEL = {"tiktok": "TikTok", "instagram": "Instagram", "reddit": "Reddit", "web": "Web / News"}


def load_mentions():
    p = os.path.join(DATA, "mentions.json")
    if not os.path.exists(p):
        return []
    d = json.load(open(p))
    recs = list(d.get("mentions", {}).values()) if isinstance(d.get("mentions"), dict) else d.get("mentions", [])
    out = []
    for r in recs:
        ts = r.get("ts")
        if not ts:
            continue
        try:
            date = ts[:10]
            datetime.strptime(date, "%Y-%m-%d")
        except Exception:
            continue
        plat = r.get("platform") if r.get("platform") in PLATFORMS else "web"
        out.append({
            "date": date, "platform": plat, "url": r.get("url"),
            "author": r.get("author"), "caption": (r.get("caption") or "").split("\n")[0][:140],
            "source": r.get("source"),
        })
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def load_search_volume():
    p = os.path.join(DATA, "search_volume.json")
    if not os.path.exists(p):
        return {"amazon_branded_search": [], "google_trends": []}
    return json.load(open(p))


def load_own_tiktok():
    p = os.path.join(DATA, "tiktok_own.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    videos = d.get("videos", [])
    monthly = defaultdict(lambda: {"views": 0, "likes": 0, "comments": 0, "shares": 0, "posts": 0})
    for v in videos:
        ts = v.get("ts")
        if not ts:
            continue
        month = ts[:7]  # YYYY-MM
        eng = v.get("engagement") or {}
        m = monthly[month]
        m["views"] += eng.get("views") or 0
        m["likes"] += eng.get("likes") or 0
        m["comments"] += eng.get("comments") or 0
        m["shares"] += eng.get("shares") or 0
        m["posts"] += 1
    monthly_series = [{"month": k, **v} for k, v in sorted(monthly.items())]
    top_videos = sorted(videos, key=lambda v: (v.get("engagement") or {}).get("views") or 0, reverse=True)[:8]
    return {
        "account": d.get("account", {}),
        "monthly": monthly_series,
        "top_videos": top_videos,
        "total_posts": len(videos),
    }


def daily_series(mentions):
    by_date = defaultdict(lambda: defaultdict(int))
    for m in mentions:
        by_date[m["date"]][m["platform"]] += 1
    if not by_date:
        return []
    dates = sorted(by_date.keys())
    start = datetime.strptime(dates[0], "%Y-%m-%d")
    end = datetime.strptime(dates[-1], "%Y-%m-%d")
    series = []
    d = start
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        row = {"date": ds}
        total = 0
        for p in PLATFORMS:
            v = by_date[ds].get(p, 0)
            row[p] = v
            total += v
        row["total"] = total
        series.append(row)
        d = d.fromordinal(d.toordinal() + 1)
    return series


def build():
    mentions = load_mentions()
    sv = load_search_volume()
    series = daily_series(mentions)
    own_tiktok = load_own_tiktok()

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "series": series,
        "mentions": mentions[:500],
        "amazon": sv.get("amazon_branded_search", []),
        "trends": sv.get("google_trends", []),
        "platforms": PLATFORMS,
        "platform_label": PLATFORM_LABEL,
        "own_tiktok": own_tiktok,
    }

    html = TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Built output/index.html — {len(series)} day(s) of series, {len(mentions)} mention(s), "
          f"{len(payload['amazon'])} Amazon month(s), {len(payload['trends'])} Trends point(s)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CoBa's Daughter — Brand Search &amp; Mentions Tracker</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{
  --ivory:#f8f7f2; --paper:#fffefb; --stone:#efecec; --line:#e6e2d8;
  --forest:#2c332f; --olive:#716a56; --ink:#252525; --clay:#b08968; --sand:#a67c52;
  --muted:#8f897b; --good:#0ca30c; --warn:#b07f3a; --bad:#c1443c; --r:14px; --maxw:1280px;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; /* validated categorical: tiktok/instagram/reddit/web */
  color-scheme: light;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ivory:#171715; --paper:#1d1d1a; --stone:#242422; --line:#33322d;
    --forest:#e8e6df; --olive:#c3c2b7; --ink:#f2f1ec; --clay:#d9a066; --sand:#c98c5a;
    --muted:#9a988f; --good:#0ca30c; --warn:#d9a066; --bad:#e66767;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
    color-scheme: dark;
  }
}
:root[data-theme="dark"]{
  --ivory:#171715; --paper:#1d1d1a; --stone:#242422; --line:#33322d;
  --forest:#e8e6df; --olive:#c3c2b7; --ink:#f2f1ec; --clay:#d9a066; --sand:#c98c5a;
  --muted:#9a988f; --good:#0ca30c; --warn:#d9a066; --bad:#e66767;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  color-scheme: dark;
}
*{box-sizing:border-box}
body{margin:0; background:var(--ivory); color:var(--ink); font-family:"Plus Jakarta Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:15px; line-height:1.5; -webkit-font-smoothing:antialiased}
.wrap{max-width:var(--maxw); margin:0 auto; padding:28px 20px 80px}
header.top{display:flex; align-items:flex-start; justify-content:space-between; gap:20px; margin-bottom:22px; flex-wrap:wrap}
h1{font-size:22px; font-weight:800; margin:0 0 4px; letter-spacing:-0.01em}
.sub{color:var(--muted); font-size:13.5px}
.themebtn{border:1px solid var(--line); background:var(--paper); color:var(--ink); border-radius:10px; padding:7px 12px; font-size:12.5px; cursor:pointer; font-family:inherit}

.periodbar{display:flex; align-items:center; gap:8px; flex-wrap:wrap; background:var(--paper); border:1px solid var(--line); border-radius:var(--r); padding:10px 12px; margin-bottom:20px}
.pbtn{border:1px solid transparent; background:transparent; color:var(--olive); border-radius:8px; padding:7px 12px; font-size:13px; font-weight:600; cursor:pointer; font-family:inherit; white-space:nowrap}
.pbtn:hover{background:var(--stone)}
.pbtn.active{background:var(--forest); color:var(--ivory); border-color:var(--forest)}
.pbtn.active:hover{background:var(--forest)}
.periodbar input[type=date]{border:1px solid var(--line); background:var(--ivory); color:var(--ink); border-radius:8px; padding:6px 8px; font-family:inherit; font-size:12.5px}
.periodbar .sep{width:1px; height:22px; background:var(--line); margin:0 4px}
.periodlabel{margin-left:auto; font-size:12.5px; color:var(--muted); font-weight:600}

.kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin-bottom:14px}
.kpi{background:var(--paper); border:1px solid var(--line); border-radius:var(--r); padding:14px 16px}
.kpi .n{font-size:26px; font-weight:800; letter-spacing:-0.01em}
.kpi .l{font-size:11.5px; color:var(--muted); font-weight:600; text-transform:uppercase; letter-spacing:.04em; margin-bottom:3px}

.chipsrow{display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px; margin-bottom:26px}
.chip{background:var(--paper); border:1px solid var(--line); border-radius:var(--r); padding:13px 15px}
.chip .cl{font-size:11.5px; color:var(--muted); font-weight:700; text-transform:uppercase; letter-spacing:.03em; margin-bottom:6px}
.chip .cv{display:flex; align-items:baseline; gap:8px}
.chip .cn{font-size:19px; font-weight:800}
.chip .cd{font-size:12.5px; font-weight:700; padding:2px 7px; border-radius:20px}
.chip .cd.up{color:var(--good); background:color-mix(in srgb, var(--good) 14%, transparent)}
.chip .cd.down{color:var(--bad); background:color-mix(in srgb, var(--bad) 14%, transparent)}
.chip .cd.flat{color:var(--muted); background:var(--stone)}
.chip .cref{font-size:11.5px; color:var(--muted); margin-top:4px}

section{background:var(--paper); border:1px solid var(--line); border-radius:var(--r); padding:20px; margin-bottom:20px}
section h2{font-size:15px; font-weight:800; margin:0 0 2px}
section .shint{font-size:12.5px; color:var(--muted); margin-bottom:14px}
.legend{display:flex; gap:14px; flex-wrap:wrap; margin-bottom:10px}
.legend button{display:flex; align-items:center; gap:6px; border:none; background:transparent; cursor:pointer; font-family:inherit; font-size:12.5px; font-weight:600; color:var(--ink); padding:3px 0; opacity:1}
.legend button.off{opacity:.35}
.legend .sw{width:10px; height:10px; border-radius:3px; display:inline-block}
.chartwrap{position:relative}
svg.chart{width:100%; height:auto; display:block; overflow:visible}
.gridline{stroke:var(--line); stroke-width:1}
.axislabel{fill:var(--muted); font-size:10.5px; font-family:"Plus Jakarta Sans",sans-serif}
.tooltip{position:absolute; pointer-events:none; background:var(--forest); color:var(--ivory); border-radius:8px; padding:8px 10px; font-size:12px; line-height:1.5; box-shadow:0 6px 18px rgba(0,0,0,.18); opacity:0; transition:opacity .1s; white-space:nowrap; z-index:5}
.crosshair{stroke:var(--muted); stroke-width:1; stroke-dasharray:3 3; opacity:0}
.emptystate{color:var(--muted); font-size:13px; padding:30px 10px; text-align:center; border:1px dashed var(--line); border-radius:10px}

table.feed{width:100%; border-collapse:collapse; font-size:13px}
table.feed th{text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.03em; color:var(--muted); font-weight:700; padding:6px 10px; border-bottom:1px solid var(--line)}
table.feed td{padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top}
table.feed tr:last-child td{border-bottom:none}
.tag{display:inline-block; font-size:10.5px; font-weight:700; padding:2px 8px; border-radius:20px; color:var(--paper)}
.tag.tiktok{background:var(--s1)} .tag.instagram{background:var(--s2)} .tag.reddit{background:var(--s3)} .tag.web{background:var(--s4)}
.feedlink{color:var(--sand); text-decoration:none; font-weight:600}
.feedlink:hover{text-decoration:underline}
.filterrow{display:flex; gap:6px; margin-bottom:12px; flex-wrap:wrap}
.filterrow button{border:1px solid var(--line); background:var(--ivory); color:var(--olive); border-radius:20px; padding:5px 12px; font-size:12px; font-weight:600; cursor:pointer; font-family:inherit}
.filterrow button.active{background:var(--forest); color:var(--ivory); border-color:var(--forest)}
footer{color:var(--muted); font-size:11.5px; text-align:center; margin-top:10px}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <h1>Brand Search &amp; Mentions Tracker</h1>
      <div class="sub">CoBa's Daughter — TikTok, Instagram, Reddit, web/news mentions + brand search volume</div>
    </div>
    <button class="themebtn" id="themeToggle">Toggle theme</button>
  </header>

  <div class="periodbar" id="periodbar">
    <button class="pbtn" data-preset="7">Last 7 days</button>
    <button class="pbtn" data-preset="30">Last 30 days</button>
    <button class="pbtn" data-preset="90">Last 90 days</button>
    <button class="pbtn" data-preset="qtd">Quarter to date</button>
    <button class="pbtn" data-preset="ytd">Year to date</button>
    <button class="pbtn" data-preset="all">All time</button>
    <span class="sep"></span>
    <input type="date" id="startDate"> <span style="color:var(--muted)">→</span> <input type="date" id="endDate">
    <span class="periodlabel" id="periodLabel"></span>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="chipsrow" id="chips"></div>

  <section>
    <h2>Mentions over time</h2>
    <div class="shint">By platform, bucketed by the post's real date (not discovery date). Hover for daily detail.</div>
    <div class="legend" id="legend"></div>
    <div class="chartwrap"><svg class="chart" id="mentionsChart" viewBox="0 0 1100 320"></svg><div class="tooltip" id="tt1"></div></div>
  </section>

  <section>
    <h2>Brand search volume</h2>
    <div class="shint" id="svHint">Manually updated — see note below.</div>
    <div id="svAmazon"></div>
    <div id="svTrends" style="margin-top:16px"></div>
  </section>

  <section id="ownTiktokSection" style="display:none">
    <h2>Owned TikTok channel — @cobasdaughter.official</h2>
    <div class="shint">Official Display API — exact counts from TikTok itself, not a scraped estimate. Your own posts only (not third-party mentions, tracked separately below).</div>
    <div class="kpis" id="ownTtKpis" style="margin-bottom:18px"></div>
    <div id="ownTtChart"></div>
    <div style="font-size:12.5px;font-weight:700;color:var(--olive);margin:18px 0 8px">Top videos by views</div>
    <table class="feed" id="ownTtTable">
      <thead><tr><th>Date</th><th>Caption</th><th>Views</th><th>Likes</th><th>Comments</th><th>Shares</th><th></th></tr></thead>
      <tbody id="ownTtBody"></tbody>
    </table>
  </section>

  <section>
    <h2>Recent mentions</h2>
    <div class="filterrow" id="feedFilter"></div>
    <table class="feed" id="feedTable">
      <thead><tr><th>Date</th><th>Platform</th><th>Author</th><th>Snippet</th><th></th></tr></thead>
      <tbody id="feedBody"></tbody>
    </table>
  </section>

  <footer>Generated <span id="genAt"></span> · data updates on each scheduled run</footer>
</div>

<script>
const DATA = __PAYLOAD__;
const PCOLOR = {tiktok:'var(--s1)', instagram:'var(--s2)', reddit:'var(--s3)', web:'var(--s4)'};
const PLABEL = DATA.platform_label;

function parseDate(s){ const [y,m,d] = s.split('-').map(Number); return new Date(y, m-1, d); }
function fmtDate(d){ // LOCAL date components — toISOString() would shift by a day in UTC+ timezones (e.g. Vietnam)
  return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}
function addDays(d, n){ const r = new Date(d); r.setDate(r.getDate()+n); return r; }
function fmtHuman(d){ return d.toLocaleDateString('en-US',{month:'short', day:'numeric', year:'numeric'}); }

const seriesByDate = {};
DATA.series.forEach(r => seriesByDate[r.date] = r);
const allDates = DATA.series.map(r => r.date);
const dataMin = allDates.length ? parseDate(allDates[0]) : new Date();
const dataMax = allDates.length ? parseDate(allDates[allDates.length-1]) : new Date();

function sumRange(start, end){ // inclusive, Date objects
  const out = {tiktok:0, instagram:0, reddit:0, web:0, total:0};
  let d = new Date(start);
  while (d <= end){
    const row = seriesByDate[fmtDate(d)];
    if (row){ DATA.platforms.forEach(p => out[p]+=row[p]); out.total += row.total; }
    d = addDays(d,1);
  }
  return out;
}

function calWeek(ref){ const d=new Date(ref); const day=d.getDay(); const start=addDays(d,-day); const end=addDays(start,6); return [start,end]; }
function calMonth(ref){ const start=new Date(ref.getFullYear(), ref.getMonth(), 1); const end=new Date(ref.getFullYear(), ref.getMonth()+1, 0); return [start,end]; }
function calQuarter(ref){ const q=Math.floor(ref.getMonth()/3); const start=new Date(ref.getFullYear(), q*3, 1); const end=new Date(ref.getFullYear(), q*3+3, 0); return [start,end]; }
function shiftYear(start,end,n){ const s=new Date(start); s.setFullYear(s.getFullYear()+n); const e=new Date(end); e.setFullYear(e.getFullYear()+n); return [s,e]; }

function pctDelta(curr, prev){
  if (prev===0) return curr===0 ? 0 : null; // null = "new" (no baseline)
  return ((curr-prev)/prev)*100;
}

let state = { start: dataMax, end: dataMax, activePreset: '30' };

function applyPreset(p){
  state.activePreset = p;
  if (p==='7') { state.end = dataMax; state.start = addDays(dataMax,-6); }
  else if (p==='30') { state.end = dataMax; state.start = addDays(dataMax,-29); }
  else if (p==='90') { state.end = dataMax; state.start = addDays(dataMax,-89); }
  else if (p==='qtd') { const [s,] = calQuarter(dataMax); state.start = s; state.end = dataMax; }
  else if (p==='ytd') { state.start = new Date(dataMax.getFullYear(),0,1); state.end = dataMax; }
  else if (p==='all') { state.start = dataMin; state.end = dataMax; }
  render();
}

document.querySelectorAll('.pbtn').forEach(b => b.addEventListener('click', () => applyPreset(b.dataset.preset)));
document.getElementById('startDate').addEventListener('change', e => { state.start = parseDate(e.target.value); state.activePreset=null; render(); });
document.getElementById('endDate').addEventListener('change', e => { state.end = parseDate(e.target.value); state.activePreset=null; render(); });

let hiddenPlatforms = new Set();

function renderLegend(){
  const el = document.getElementById('legend'); el.innerHTML='';
  DATA.platforms.forEach(p => {
    const b = document.createElement('button');
    b.className = hiddenPlatforms.has(p) ? 'off':'';
    b.innerHTML = `<span class="sw" style="background:${PCOLOR[p]}"></span>${PLABEL[p]}`;
    b.addEventListener('click', () => { hiddenPlatforms.has(p) ? hiddenPlatforms.delete(p) : hiddenPlatforms.add(p); renderLegend(); renderChart(); });
    el.appendChild(b);
  });
}

function renderKpis(){
  const tot = sumRange(state.start, state.end);
  const days = Math.round((state.end-state.start)/86400000)+1;
  const el = document.getElementById('kpis');
  el.innerHTML = `
    <div class="kpi"><div class="l">Total mentions</div><div class="n">${tot.total}</div></div>
    <div class="kpi"><div class="l">TikTok</div><div class="n" style="color:${PCOLOR.tiktok}">${tot.tiktok}</div></div>
    <div class="kpi"><div class="l">Instagram</div><div class="n" style="color:${PCOLOR.instagram}">${tot.instagram}</div></div>
    <div class="kpi"><div class="l">Reddit</div><div class="n" style="color:${PCOLOR.reddit}">${tot.reddit}</div></div>
    <div class="kpi"><div class="l">Web / News</div><div class="n" style="color:${PCOLOR.web}">${tot.web}</div></div>
    <div class="kpi"><div class="l">Selected range</div><div class="n" style="font-size:15px; font-weight:700; padding-top:4px">${days}d</div></div>
  `;
  document.getElementById('periodLabel').textContent = `${fmtHuman(state.start)} – ${fmtHuman(state.end)}`;
}

function chipHtml(label, curr, prev, refLabel){
  let dclass='flat', dtext='—';
  const d = pctDelta(curr, prev);
  if (d===null){ dclass='up'; dtext='new'; }
  else if (Math.abs(d) < 0.5){ dclass='flat'; dtext='flat'; }
  else { dclass = d>0?'up':'down'; dtext = (d>0?'+':'') + d.toFixed(0) + '%'; }
  return `<div class="chip"><div class="cl">${label}</div><div class="cv"><span class="cn">${curr}</span><span class="cd ${dclass}">${dtext}</span></div><div class="cref">${refLabel} · was ${prev}</div></div>`;
}

function renderChips(){
  const cur = sumRange(state.start, state.end).total;
  const lenDays = Math.round((state.end-state.start)/86400000)+1;

  // 1. This calendar week vs last calendar week (anchored on data's most recent day)
  const [tw_s, tw_e] = calWeek(dataMax);
  const [lw_s, lw_e] = [addDays(tw_s,-7), addDays(tw_e,-7)];
  const wkCur = sumRange(tw_s, dataMax).total; // partial week to date
  const wkPrev = sumRange(lw_s, addDays(lw_s, dataMax-tw_s > 0 ? Math.round((dataMax-tw_s)/86400000): 6)).total;

  // 2. This calendar month vs last calendar month
  const [tm_s,] = calMonth(dataMax);
  const mCur = sumRange(tm_s, dataMax).total;
  const [lm_s, lm_e] = calMonth(addDays(tm_s,-1));
  const mPrev = sumRange(lm_s, addDays(lm_s, Math.round((dataMax-tm_s)/86400000))).total;

  // 3. This calendar quarter vs last calendar quarter
  const [tq_s,] = calQuarter(dataMax);
  const qCur = sumRange(tq_s, dataMax).total;
  const [lq_s,] = calQuarter(addDays(tq_s,-1));
  const qPrev = sumRange(lq_s, addDays(lq_s, Math.round((dataMax-tq_s)/86400000))).total;

  // 4. Selected period vs immediately preceding period of equal length
  const cp_end = addDays(state.start,-1);
  const cp_start = addDays(cp_end, -(lenDays-1));
  const cpPrev = sumRange(cp_start, cp_end).total;

  // 5. Selected period vs same dates last year
  const [yr_s, yr_e] = shiftYear(state.start, state.end, -1);
  const yrPrev = sumRange(yr_s, yr_e).total;

  const el = document.getElementById('chips');
  el.innerHTML =
    chipHtml('vs Last Week', wkCur, wkPrev, `${fmtHuman(tw_s)}–now`) +
    chipHtml('vs Last Month', mCur, mPrev, `${fmtHuman(tm_s)}–now`) +
    chipHtml('vs Last Quarter', qCur, qPrev, `${fmtHuman(tq_s)}–now`) +
    chipHtml('vs Last Comparable Period', cur, cpPrev, `prior ${lenDays}d`) +
    chipHtml('vs Last Year', cur, yrPrev, `${fmtHuman(state.start)}–${fmtHuman(state.end)}`);
}

function renderChart(){
  const svg = document.getElementById('mentionsChart');
  const W=1100,H=320,padL=34,padR=14,padT=14,padB=28;
  const start=state.start, end=state.end;
  const days=[]; let d=new Date(start); while(d<=end){ days.push(fmtDate(d)); d=addDays(d,1); }
  if (days.length===0 || DATA.series.length===0){
    svg.innerHTML = `<foreignObject x="0" y="0" width="${W}" height="${H}"><div xmlns="http://www.w3.org/1999/xhtml" class="emptystate">No mentions in this range yet.</div></foreignObject>`;
    return;
  }
  const rows = days.map(ds => seriesByDate[ds] || {date:ds, tiktok:0,instagram:0,reddit:0,web:0,total:0});
  const visible = DATA.platforms.filter(p => !hiddenPlatforms.has(p));
  let maxY = 1;
  rows.forEach(r => visible.forEach(p => { if (r[p]>maxY) maxY=r[p]; }));
  maxY = Math.ceil(maxY*1.15) || 1;
  const x = i => padL + (days.length<=1 ? 0 : i*(W-padL-padR)/(days.length-1));
  const y = v => H-padB - (v/maxY)*(H-padT-padB);

  let svgEl = `<g>`;
  for (let g=0; g<=4; g++){
    const gy = padT + g*(H-padT-padB)/4;
    const val = Math.round(maxY - g*maxY/4);
    svgEl += `<line class="gridline" x1="${padL}" x2="${W-padR}" y1="${gy}" y2="${gy}"/><text class="axislabel" x="4" y="${gy+3}">${val}</text>`;
  }
  const stepLabels = Math.max(1, Math.round(days.length/7));
  days.forEach((ds,i) => { if (i%stepLabels===0 || i===days.length-1){ const dt=parseDate(ds); svgEl += `<text class="axislabel" x="${x(i)}" y="${H-8}" text-anchor="middle">${dt.toLocaleDateString('en-US',{month:'short',day:'numeric'})}</text>`; } });

  visible.forEach(p => {
    let path='';
    rows.forEach((r,i) => { path += (i===0?'M':'L') + x(i).toFixed(1) + ' ' + y(r[p]).toFixed(1) + ' '; });
    svgEl += `<path d="${path}" fill="none" stroke="${PCOLOR[p]}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;
  });

  svgEl += `<line class="crosshair" id="cross" x1="0" x2="0" y1="${padT}" y2="${H-padB}"/>`;
  svgEl += `<rect x="${padL}" y="${padT}" width="${W-padL-padR}" height="${H-padT-padB}" fill="transparent" id="hoverzone"/>`;
  svgEl += `</g>`;
  svg.innerHTML = svgEl;

  const zone = document.getElementById('hoverzone');
  const cross = document.getElementById('cross');
  const tt = document.getElementById('tt1');
  const wrap = zone.closest('.chartwrap');
  zone.addEventListener('mousemove', ev => {
    const rect = svg.getBoundingClientRect();
    const px = (ev.clientX-rect.left) * (W/rect.width);
    let idx = Math.round((px-padL)/((W-padL-padR)/(Math.max(1,days.length-1))));
    idx = Math.max(0, Math.min(days.length-1, idx));
    const r = rows[idx];
    cross.setAttribute('x1', x(idx)); cross.setAttribute('x2', x(idx)); cross.style.opacity=1;
    const lines = visible.map(p => `<span style="color:${PCOLOR[p]}">●</span> ${PLABEL[p]}: ${r[p]}`).join('<br>');
    tt.innerHTML = `<b>${fmtHuman(parseDate(r.date))}</b><br>${lines}<br><b>Total: ${r.total}</b>`;
    const wrect = wrap.getBoundingClientRect();
    tt.style.left = Math.min(wrect.width-160, Math.max(0,(ev.clientX-wrect.left)+12)) + 'px';
    tt.style.top = Math.max(0,(ev.clientY-wrect.top)-60) + 'px';
    tt.style.opacity = 1;
  });
  zone.addEventListener('mouseleave', () => { cross.style.opacity=0; tt.style.opacity=0; });
}

function renderSearchVolume(){
  const amz = DATA.amazon, trends = DATA.trends;
  const hint = document.getElementById('svHint');
  hint.textContent = "Manually updated by the team (Google Trends returns too little volume for this brand to be a reliable automated signal; Amazon Branded Search is a monthly export). Empty means no export dropped yet, not zero.";

  const amzEl = document.getElementById('svAmazon');
  if (!amz.length){
    amzEl.innerHTML = `<div class="emptystate">No Amazon Branded Search export yet — drop one into <code>data/amazon_awareness/</code>.</div>`;
  } else {
    const W=1100,H=200,padL=44,padR=14,padT=14,padB=28;
    const maxV = Math.max(...amz.map(r=>r.branded_search||0)) * 1.15 || 1;
    const bw = (W-padL-padR)/amz.length*0.6;
    let svg = `<svg class="chart" viewBox="0 0 ${W} ${H}">`;
    for (let g=0; g<=3; g++){ const gy=padT+g*(H-padT-padB)/3; const val=Math.round(maxV-g*maxV/3);
      svg += `<line class="gridline" x1="${padL}" x2="${W-padR}" y1="${gy}" y2="${gy}"/><text class="axislabel" x="4" y="${gy+3}">${val}</text>`; }
    amz.forEach((r,i) => {
      const cx = padL + (i+0.5)*(W-padL-padR)/amz.length;
      const bh = ((r.branded_search||0)/maxV)*(H-padT-padB);
      const by = H-padB-bh;
      svg += `<rect x="${(cx-bw/2).toFixed(1)}" y="${by.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="3" fill="var(--s1)"/>`;
      const dt = parseDate(r.date);
      svg += `<text class="axislabel" x="${cx}" y="${H-8}" text-anchor="middle">${dt.toLocaleDateString('en-US',{month:'short',year:'2-digit'})}</text>`;
    });
    svg += `</svg>`;
    amzEl.innerHTML = `<div style="font-size:12.5px;font-weight:700;color:var(--olive);margin-bottom:6px">Amazon Branded Search Customers / month</div>` + svg;
  }

  const trEl = document.getElementById('svTrends');
  if (!trends.length){
    trEl.innerHTML = `<div class="emptystate">No Google Trends export yet — drop one into <code>data/google_trends/</code> (download a CSV for the brand keyword from trends.google.com).</div>`;
  } else {
    trEl.innerHTML = `<div style="font-size:12.5px;font-weight:700;color:var(--olive);margin-bottom:6px">Google Trends — relative search interest (0–100, US)</div><div class="shint">${trends.length} point(s) loaded.</div>`;
  }
}

function renderOwnTiktok(){
  const own = DATA.own_tiktok;
  const section = document.getElementById('ownTiktokSection');
  if (!own || !own.monthly || !own.monthly.length){ section.style.display='none'; return; }
  section.style.display='';

  const a = own.account || {};
  document.getElementById('ownTtKpis').innerHTML = `
    <div class="kpi"><div class="l">Followers</div><div class="n">${(a.follower_count||0).toLocaleString()}</div></div>
    <div class="kpi"><div class="l">Total likes</div><div class="n">${(a.likes_count||0).toLocaleString()}</div></div>
    <div class="kpi"><div class="l">Total videos</div><div class="n">${(own.total_posts||0).toLocaleString()}</div></div>
  `;

  const W=1100,H=220,padL=50,padR=14,padT=14,padB=32;
  const rows = own.monthly;
  const maxV = Math.max(...rows.map(r=>r.views)) * 1.15 || 1;
  const bw = (W-padL-padR)/rows.length*0.6;
  let svg = `<svg class="chart" viewBox="0 0 ${W} ${H}">`;
  for (let g=0; g<=3; g++){ const gy=padT+g*(H-padT-padB)/3; const val=Math.round(maxV-g*maxV/3);
    svg += `<line class="gridline" x1="${padL}" x2="${W-padR}" y1="${gy}" y2="${gy}"/><text class="axislabel" x="4" y="${gy+3}">${val.toLocaleString()}</text>`; }
  rows.forEach((r,i) => {
    const cx = padL + (i+0.5)*(W-padL-padR)/rows.length;
    const bh = (r.views/maxV)*(H-padT-padB);
    const by = H-padB-bh;
    svg += `<rect x="${(cx-bw/2).toFixed(1)}" y="${by.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="3" fill="var(--s1)"/>`;
    const [y,m] = r.month.split('-');
    svg += `<text class="axislabel" x="${cx}" y="${H-10}" text-anchor="middle">${new Date(y,m-1,1).toLocaleDateString('en-US',{month:'short',year:'2-digit'})}</text>`;
  });
  svg += `</svg>`;
  document.getElementById('ownTtChart').innerHTML = `<div style="font-size:12.5px;font-weight:700;color:var(--olive);margin-bottom:6px">Views per month (own posts)</div>` + svg;

  document.getElementById('ownTtBody').innerHTML = (own.top_videos||[]).map(v => {
    const e = v.engagement || {};
    return `<tr>
      <td>${v.ts ? fmtHuman(parseDate(v.ts.slice(0,10))) : '—'}</td>
      <td>${(v.caption||'').replace(/</g,'&lt;').slice(0,90)}</td>
      <td>${(e.views||0).toLocaleString()}</td>
      <td>${(e.likes||0).toLocaleString()}</td>
      <td>${(e.comments||0).toLocaleString()}</td>
      <td>${(e.shares||0).toLocaleString()}</td>
      <td>${v.url ? `<a class="feedlink" href="${v.url}" target="_blank" rel="noopener">View →</a>` : ''}</td>
    </tr>`;
  }).join('') || `<tr><td colspan="7"><div class="emptystate">No videos loaded.</div></td></tr>`;
}

let feedFilterPlatform = null;
function renderFeedFilter(){
  const el = document.getElementById('feedFilter'); el.innerHTML='';
  const all = document.createElement('button'); all.textContent='All'; all.className = feedFilterPlatform===null?'active':'';
  all.onclick = () => { feedFilterPlatform=null; renderFeedFilter(); renderFeed(); }; el.appendChild(all);
  DATA.platforms.forEach(p => {
    const b = document.createElement('button'); b.textContent = PLABEL[p]; b.className = feedFilterPlatform===p?'active':'';
    b.onclick = () => { feedFilterPlatform=p; renderFeedFilter(); renderFeed(); }; el.appendChild(b);
  });
}

function renderFeed(){
  const body = document.getElementById('feedBody');
  let items = DATA.mentions.filter(m => m.date >= fmtDate(state.start) && m.date <= fmtDate(state.end));
  if (feedFilterPlatform) items = items.filter(m => m.platform===feedFilterPlatform);
  items = items.slice(0,60);
  if (!items.length){ body.innerHTML = `<tr><td colspan="5"><div class="emptystate">No mentions in this range.</div></td></tr>`; return; }
  body.innerHTML = items.map(m => `<tr>
    <td>${fmtHuman(parseDate(m.date))}</td>
    <td><span class="tag ${m.platform}">${PLABEL[m.platform]}</span></td>
    <td>${m.author ? '@'+m.author.replace(/^@/,'') : '—'}</td>
    <td>${(m.caption||'').replace(/</g,'&lt;')}</td>
    <td>${m.url ? `<a class="feedlink" href="${m.url}" target="_blank" rel="noopener">View →</a>` : ''}</td>
  </tr>`).join('');
}

function render(){
  document.querySelectorAll('.pbtn').forEach(b => b.classList.toggle('active', b.dataset.preset===state.activePreset));
  document.getElementById('startDate').value = fmtDate(state.start);
  document.getElementById('endDate').value = fmtDate(state.end);
  renderKpis(); renderChips(); renderChart(); renderSearchVolume(); renderFeed();
}

renderLegend(); renderFeedFilter(); renderOwnTiktok();
document.getElementById('genAt').textContent = new Date(DATA.generated_utc).toLocaleString('en-US',{dateStyle:'medium', timeStyle:'short'});
applyPreset('30');

const themeBtn = document.getElementById('themeToggle');
themeBtn.addEventListener('click', () => {
  const cur = document.documentElement.getAttribute('data-theme');
  document.documentElement.setAttribute('data-theme', cur==='dark' ? 'light' : 'dark');
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
