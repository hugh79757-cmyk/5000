#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, '/Users/twinssn/Projects/5000')
from ops_dashboard.checks.content_quality_live import run_live_check

STAP_BLOGS = [
    "stock-hugo",
    "dividend-hugo",
    "etf-hugo",
    "sector-hugo",
    "ipo-hugo",
    "finance-hugo",
]

BASE = Path("/Users/twinssn/Projects/STAP")
def find_latest_post(blog_id):
    site = BASE / blog_id / "content/posts"
    if not site.exists():
        return None
    # find newest index.md by mtime
    files = list(site.rglob("index.md"))
    if not files:
        return None
    latest = max(files, key=lambda p: p.stat().st_mtime)
    return latest

results = []
for blog in STAP_BLOGS:
    md_path = find_latest_post(blog)
    if not md_path:
        results.append((blog, "no_posts"))
        continue
    res = run_live_check(blog, md_path)
    results.append((blog, res))

for blog, res in results:
    print(f"{blog}: {res}")
