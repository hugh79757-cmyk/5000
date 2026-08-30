#!/usr/bin/env python3
"""Track cannibalization risk for the LLM-crawl pilot (fire-your-seo-agency apply).

Cannibalization = allowing AI crawlers to index/cite content may reduce human
visits -> AdSense revenue drop. This script rolls up weekly metrics per pilot site
into analytics.db:cannibalization_tracking so a 4-6 week pre/post comparison is
possible. Data already exists in adsense_daily (domain), gsc_pages + ga4_daily
(blog_id). We only roll up weekly.

Run:
  python3 scripts/track_cannibalization.py --backfill 6   # fill past 6 weeks
  python3 scripts/track_cannibalization.py --week         # this week (for scheduler)
"""
import argparse
import os
import sqlite3
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "analytics.db")

# Pilot cohort (blog_id, domain). travel3-hugo domain quirk: tour2.rotcha.kr.
PILOT = [
    ("hotissue-hugo", "hotissue.rotcha.kr"),
    ("guide-hugo", "guide.rotcha.kr"),
    ("deal-hugo", "deal.rotcha.kr"),
    ("travel1-hugo", "travel1.rotcha.kr"),
    ("travel3-hugo", "tour2.rotcha.kr"),
    ("travel2-hugo", "travel2.rotcha.kr"),
    ("escape-hugo", "escape.techpawz.com"),
    ("nomad-hugo", "nomad.techpawz.com"),
    ("techpawz-hugo", "techpawz.com"),
    ("rotcha.kr", "rotcha.kr"),
]


def monday(d):
    return d - timedelta(days=d.weekday())


def ensure_table(con):
    con.execute(
        """CREATE TABLE IF NOT EXISTS cannibalization_tracking (
            week_start TEXT,
            blog_id TEXT,
            domain TEXT,
            gsc_clicks REAL,
            gsc_impressions REAL,
            ga4_sessions REAL,
            ga4_ad_revenue REAL,
            adsense_earnings REAL,
            adsense_rpm REAL,
            adsense_page_views REAL,
            PRIMARY KEY (week_start, blog_id)
        )"""
    )


def snapshot_week(con, ws):
    we = ws + timedelta(days=6)
    lo, hi = ws.isoformat(), we.isoformat()
    rows = []
    for blog_id, domain in PILOT:
        g = con.execute(
            "SELECT COALESCE(SUM(clicks),0), COALESCE(SUM(impressions),0) "
            "FROM gsc_pages WHERE blog_id=? AND date BETWEEN ? AND ?",
            (blog_id, lo, hi),
        ).fetchone()
        ga = con.execute(
            "SELECT COALESCE(SUM(sessions),0), COALESCE(SUM(ad_revenue),0) "
            "FROM ga4_daily WHERE blog_id=? AND date BETWEEN ? AND ?",
            (blog_id, lo, hi),
        ).fetchone()
        ad = con.execute(
            "SELECT COALESCE(SUM(estimated_earnings),0), COALESCE(AVG(rpm),0), "
            "COALESCE(SUM(page_views),0) FROM adsense_daily WHERE domain=? AND date BETWEEN ? AND ?",
            (domain, lo, hi),
        ).fetchone()
        rows.append(
            (ws.isoformat(), blog_id, domain, g[0], g[1], ga[0], ga[1], ad[0], ad[1], ad[2])
        )
    con.executemany(
        "INSERT OR REPLACE INTO cannibalization_tracking "
        "(week_start,blog_id,domain,gsc_clicks,gsc_impressions,ga4_sessions,"
        "ga4_ad_revenue,adsense_earnings,adsense_rpm,adsense_page_views) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    con.commit()
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=int, default=0, help="number of past weeks to fill")
    ap.add_argument("--week", action="store_true", help="snapshot current week")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    ensure_table(con)
    today = date.today()
    ws = monday(today)
    n = 0
    if args.backfill:
        for i in range(args.backfill, -1, -1):
            n += snapshot_week(con, ws - timedelta(weeks=i))
    if args.week:
        n += snapshot_week(con, ws)
    if not args.backfill and not args.week:
        # default: just this week
        n = snapshot_week(con, ws)
    con.close()
    print(f"snapshot rows written: {n} (week_start={ws.isoformat()})")


if __name__ == "__main__":
    main()
