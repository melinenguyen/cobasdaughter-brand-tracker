#!/usr/bin/env python3
"""
Search-volume is manually fed, not scraped — see memory: Google Trends returns
essentially no data for this brand at any useful resolution (tested live,
2026-09-22), and Amazon Branded Search only exists as a manual monthly export.
The user updates these sources themselves by dropping export files into:

  data/amazon_awareness/*.csv   — Amazon Brand Analytics "Awareness Trends" export
                                   (same format already parsed by
                                   marketing/performance/_system/build_report.py)
  data/google_trends/*.csv      — raw CSV export downloaded from trends.google.com
                                   for the brand keyword (Weekly or Daily)

This module only PARSES whatever is dropped there — it invents nothing, and
reports "no data" honestly when a folder is empty.
"""
import os, csv, glob, re, json
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AMZ_DIR = os.path.join(ROOT, "data", "amazon_awareness")
GT_DIR = os.path.join(ROOT, "data", "google_trends")


def _month_end(s):
    """'June 30, 2025' -> '2025-06-30'"""
    s = s.strip().strip('"')
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def parse_amazon_awareness_csv(path):
    """Date,Customers in Awareness,Customers in Consideration,Branded Search Customers,Branded Search Ratio"""
    out = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            r = csv.DictReader(f)
            for row in r:
                date = _month_end(row.get("Date", ""))
                if not date:
                    continue
                def num(k):
                    try:
                        return float(row.get(k, "") or 0)
                    except Exception:
                        return None
                out.append({
                    "date": date,
                    "awareness": num("Customers in Awareness"),
                    "consideration": num("Customers in Consideration"),
                    "branded_search": num("Branded Search Customers"),
                    "branded_search_ratio": num("Branded Search Ratio"),
                })
    except Exception as e:
        print(f"  ! failed to parse {path}: {e}")
    return out


def parse_google_trends_csv(path):
    """Handles the standard trends.google.com export: a few preamble lines,
    then a header row starting with Day/Week/Month, then date,value rows."""
    out = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            lines = [ln.rstrip("\n") for ln in f]
        header_idx = None
        for i, ln in enumerate(lines):
            if re.match(r"^(Day|Week|Month)\s*,", ln):
                header_idx = i
                break
        if header_idx is None:
            return out
        header = lines[header_idx].split(",")
        value_col = header[1] if len(header) > 1 else "value"
        for ln in lines[header_idx + 1:]:
            if not ln.strip():
                continue
            parts = ln.split(",")
            if len(parts) < 2:
                continue
            date_raw, val_raw = parts[0].strip(), parts[1].strip()
            try:
                date = datetime.strptime(date_raw, "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                continue
            val = None if val_raw in ("", "<1") else _safe_float(val_raw)
            out.append({"date": date, "interest": val, "label": value_col})
    except Exception as e:
        print(f"  ! failed to parse {path}: {e}")
    return out


def _safe_float(s):
    try:
        return float(s)
    except Exception:
        return None


def sync():
    """Scan both drop folders and MERGE onto whatever's already in
    data/search_volume.json — never shrinks it. This matters because the
    sibling-repo seed fallback below only exists on the local machine (the
    CI runner doesn't check out marketing/performance), so a naive
    regenerate-from-scratch would silently wipe real committed data on every
    cloud run."""
    os.makedirs(AMZ_DIR, exist_ok=True)
    os.makedirs(GT_DIR, exist_ok=True)

    existing_path = os.path.join(ROOT, "data", "search_volume.json")
    amazon, trends = {}, {}
    if os.path.exists(existing_path):
        existing = json.load(open(existing_path))
        for row in existing.get("amazon_branded_search", []):
            amazon[row["date"]] = row
        for row in existing.get("google_trends", []):
            trends[row["date"]] = row

    for p in sorted(glob.glob(os.path.join(AMZ_DIR, "*.csv"))):
        for row in parse_amazon_awareness_csv(p):
            amazon[row["date"]] = row  # dropped file wins per date over what's stored

    if not amazon:
        # Local-machine-only convenience: on first run, seed from the real export
        # that already sits in the sibling performance repo. Not available in CI
        # (only this repo is checked out there) — harmless no-op if missing.
        seed_candidates = sorted(glob.glob(
            os.path.join(ROOT, "..", "performance", "input", "brand performance", "*", "Amazon Awareness Trends.csv")
        ))
        for p in seed_candidates:
            for row in parse_amazon_awareness_csv(p):
                amazon[row["date"]] = row
        if amazon:
            print(f"  · seeded Amazon Branded Search from {len(seed_candidates)} existing export(s) "
                  f"in marketing/performance/input/ — drop your own into data/amazon_awareness/ to take over")

    for p in sorted(glob.glob(os.path.join(GT_DIR, "*.csv"))):
        for row in parse_google_trends_csv(p):
            trends[row["date"]] = row

    out = {
        "generated_utc": datetime.utcnow().isoformat() + "Z",
        "amazon_branded_search": sorted(amazon.values(), key=lambda r: r["date"]),
        "google_trends": sorted(trends.values(), key=lambda r: r["date"]),
        "note": "Manually fed — see module docstring. Empty arrays mean no export has been dropped yet, not zero volume.",
    }
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(existing_path, "w") as f:
        json.dump(out, f, indent=1)
    print(f"  · search_volume.json: {len(out['amazon_branded_search'])} Amazon month(s), "
          f"{len(out['google_trends'])} Google Trends point(s)")
    return out


if __name__ == "__main__":
    sync()
