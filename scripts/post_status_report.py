#!/usr/bin/env python3
"""Post status report: classify published posts by GSC clicks performance.

Joins content.db articles (status='published') with analytics.db gsc_pages
on normalized URL. READ-ONLY on all DBs.
"""
import argparse
import sqlite3
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DB = ROOT / "data" / "content.db"
ANALYTICS_DB = ROOT / "data" / "analytics.db"


def norm_url(url: str) -> str:
    """Normalize URL for matching: strip protocol, www, trailing slash, percent-decode."""
    u = unquote((url or "").strip().lower())
    if u.startswith("https://"):
        u = u[8:]
    elif u.startswith("http://"):
        u = u[7:]
    if u.startswith("www."):
        u = u[4:]
    return u.rstrip("/")


def fetch_articles(blog: str | None) -> list[dict]:
    con = sqlite3.connect(f"file:{CONTENT_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    q = "SELECT blog_id, title, published_url, published_at FROM articles WHERE status='published'"
    args: tuple = ()
    if blog:
        q += " AND blog_id=?"
        args = (blog,)
    rows = [dict(r) for r in con.execute(q, args)]
    con.close()
    return rows


def fetch_gsc(days: int) -> dict[str, dict]:
    """Aggregate gsc_pages over lookback window → {norm_url: {clicks, impressions}}."""
    con = sqlite3.connect(f"file:{ANALYTICS_DB}?mode=ro", uri=True)
    q = (
        "SELECT page, SUM(clicks) clicks, SUM(impressions) impressions "
        "FROM gsc_pages WHERE date >= date('now', ?) GROUP BY page"
    )
    agg: dict[str, dict] = {}
    sample_pages: list[str] = []
    for page, clicks, imps in con.execute(q, (f"-{days} days",)):
        n = norm_url(page)
        cur = agg.setdefault(n, {"clicks": 0, "impressions": 0})
        cur["clicks"] += clicks or 0
        cur["impressions"] += imps or 0
        if len(sample_pages) < 10:
            sample_pages.append(page)
    con.close()
    return agg, sample_pages


def classify(articles: list[dict], gsc: dict[str, dict]) -> list[dict]:
    out = []
    for a in articles:
        n = norm_url(a["published_url"])
        rec = {**a, "clicks": None, "impressions": None, "cls": "unmatched"}
        if n in gsc:
            g = gsc[n]
            rec["clicks"] = g["clicks"]
            rec["impressions"] = g["impressions"]
            if g["clicks"] >= 5:
                rec["cls"] = "top"
            elif g["clicks"] >= 1:
                rec["cls"] = "low"
            elif g["impressions"] > 0:
                rec["cls"] = "zero"
            else:
                rec["cls"] = "no_impressions"
        out.append(rec)
    return out


def build_report(recs: list[dict], gsc: dict, sample_pages: list[str], days: int, top_n: int) -> str:
    total = len(recs)
    matched = [r for r in recs if r["cls"] != "unmatched"]
    counts = {c: sum(1 for r in recs if r["cls"] == c) for c in
              ("top", "low", "zero", "no_impressions", "unmatched")}
    lines: list[str] = []
    add = lines.append

    add(f"# Post Status Report ({days}-day GSC window)\n")
    add(f"Generated: {__import__('datetime').date.today():%Y-%m-%d} | Total published: {total}\n")

    # 1. Summary
    add("## 1. Classification Summary\n")
    add("| Classification | Count | % |")
    add("|---|---|---|")
    labels = {"top": "Top performers (clicks>=5)", "low": "Low clicks (1-4)",
              "zero": "Zero clicks (imps>0)", "no_impressions": "No impressions",
              "unmatched": "Unmatched (no GSC data)"}
    for c in ("top", "low", "zero", "no_impressions", "unmatched"):
        pct = counts[c] / total * 100 if total else 0
        add(f"| {labels[c]} | {counts[c]} | {pct:.1f}% |")
    match_rate = len(matched) / total * 100 if total else 0
    add(f"\n**Match rate: {len(matched)}/{total} ({match_rate:.1f}%)** — unmatched includes 403-skipped blogs (no GSC data collected).\n")

    # 2. Per-blog breakdown
    add("## 2. Per-Blog Breakdown\n")
    add("| Blog | Posts | Matched | Top | Zero | Unmatched |")
    add("|---|---|---|---|---|---|")
    blogs: dict[str, dict] = {}
    for r in recs:
        b = blogs.setdefault(r["blog_id"], {"posts": 0, "matched": 0, "top": 0, "zero": 0})
        if r["cls"] != "unmatched":
            b["matched"] += 1
        if r["cls"] == "top":
            b["top"] += 1
        if r["cls"] == "zero":
            b["zero"] += 1
    for bid in sorted(blogs, key=lambda k: -blogs[k]["posts"]):
        b = blogs[bid]
        unm = b["posts"] - b["matched"]
        add(f"| {bid} | {b['posts']} | {b['matched']} | {b['top']} | {b['zero']} | {unm} |")
    add("")

    # 3. Top posts by clicks
    add(f"## 3. Top {top_n} Posts by Clicks\n")
    add("| Blog | Title | Clicks | Impr | CTR | Published |")
    add("|---|---|---|---|---|---|")
    top = sorted(matched, key=lambda r: -r["clicks"])[:top_n]
    for r in top:
        ctr = r["clicks"] / r["impressions"] * 100 if r["impressions"] else 0
        add(f"| {r['blog_id']} | {r['title'][:60]} | {r['clicks']} | {r['impressions']} | {ctr:.1f}% | {r['published_at'] or ''} |")
    add("")

    # 4. Revival candidates
    rev = [r for r in recs if r["cls"] == "zero" and r["impressions"] >= 100]
    add(f"## 4. Revival Candidates (impressions>=100, clicks=0): {len(rev)}\n")
    add("| Blog | Title | Impr | Published |")
    add("|---|---|---|---|")
    for r in sorted(rev, key=lambda r: -r["impressions"]):
        add(f"| {r['blog_id']} | {r['title'][:60]} | {r['impressions']} | {r['published_at'] or ''} |")
    add("")

    # 5. Match-rate diagnostics
    add("## 5. Match-Rate Diagnostics\n")
    gsc_doms = {n.split("/")[0] for n in gsc}
    un = [r for r in recs if r["cls"] == "unmatched"][:10]
    add("Sample unmatched article URLs:")
    for r in un:
        raw = r["published_url"] or ""
        if "://" not in raw:
            why = "malformed published_url (not a URL)"
        else:
            d = norm_url(raw).split("/")[0]
            why = ("domain not in GSC (403-skip / not collected)" if d not in gsc_doms
                   else "domain in GSC, URL absent (window/backfill)")
        add(f"- `{raw}` ({r['blog_id']}) — {why}")
    add("\nSample gsc_pages entries:")
    for p in sample_pages:
        add(f"- `{p}`")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=90, help="GSC lookback window (default 90)")
    ap.add_argument("--blog", help="filter single blog_id")
    ap.add_argument("--top", type=int, default=30, help="top list size (default 30)")
    args = ap.parse_args()

    articles = fetch_articles(args.blog)
    gsc, sample_pages = fetch_gsc(args.days)
    recs = classify(articles, gsc)
    report = build_report(recs, gsc, sample_pages, args.days, args.top)
    print(report)

    out_dir = ROOT / ".planning" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{__import__('datetime').date.today():%Y-%m-%d}-post-status.md"
    out.write_text(report, encoding="utf-8")
    print(f"\n[written] {out}")


if __name__ == "__main__":
    main()
