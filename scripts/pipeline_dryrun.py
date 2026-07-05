"""Pipeline dry-run: check curation health for all 10 CUAP blogs."""
import json
import sqlite3
import sys
sys.path.insert(0, '/Users/twinssn/Projects/5000')

from pipelines.curation.keywords import get_keywords
from pipelines.curation.pipeline import _select_keyword, CATEGORY_FILTERS
from pipelines.curation.collector import get_products

DB_PATH = '/Users/twinssn/Projects/5000/data/curation.db'

BLOGS = [
    "appliance-hugo", "baby-hugo", "beauty-hugo", "camping-hugo",
    "fitness-hugo", "health-hugo", "interior-hugo", "kitchen-hugo",
    "laptop-hugo", "pet-hugo",
]

results = {}

for blog_id in BLOGS:
    print(f"\n{'='*60}")
    print(f"📋 {blog_id}")
    print(f"{'='*60}")

    keywords = get_keywords(blog_id)
    kw_count = len(keywords)

    conn = sqlite3.connect(DB_PATH)
    cached_rows = conn.execute(
        "SELECT keyword, COUNT(*) as cnt FROM products GROUP BY keyword"
    ).fetchall()
    conn.close()

    cached_for_blog = [r for r in cached_rows if r[0] in (keywords or [])]
    cached_count = len(cached_for_blog)

    keywords_with_3plus = [r[0] for r in cached_for_blog if r[1] >= 3]
    can_publish = len(keywords_with_3plus) > 0

    selected = _select_keyword(blog_id)

    has_filter = blog_id in CATEGORY_FILTERS

    print(f"  Keywords available: {kw_count}")
    print(f"  Keywords with cached products: {cached_count}")
    print(f"  Keywords with >=3 products: {len(keywords_with_3plus)}")
    if keywords_with_3plus:
        print(f"    Examples: {keywords_with_3plus[:5]}")
    print(f"  Can publish: {'YES' if can_publish else 'NO'}")
    print(f"  _select_keyword returns: {selected or 'None'}")
    print(f"  CATEGORY_FILTERS entry: {'YES' if has_filter else 'NO'}")

    results[blog_id] = {
        "keywords": kw_count,
        "cached_keywords": cached_count,
        "keywords_3plus": len(keywords_with_3plus),
        "can_publish": can_publish,
        "select_keyword": selected is not None,
        "has_filter": has_filter,
    }

print(f"\n\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")

can_publish_list = []
issues_list = []
select_none_list = []

for blog_id, r in results.items():
    flags = []
    if r["keywords"] == 0:
        flags.append("0_KEYWORDS")
    if r["cached_keywords"] == 0:
        flags.append("0_CACHED")
    if r["keywords_3plus"] == 0:
        flags.append("NO_3PLUS")
    if not r["select_keyword"]:
        flags.append("SELECT_NONE")
        select_none_list.append(blog_id)
    if r["can_publish"]:
        can_publish_list.append(blog_id)
    if flags:
        issues_list.append(f"  {blog_id}: {', '.join(flags)}")

print(f"\nBlogs that CAN publish right now: {len(can_publish_list)}")
for b in can_publish_list:
    print(f"  ✅ {b}")

if issues_list:
    print(f"\nBlogs with issues ({len(issues_list)}):")
    for issue in issues_list:
        print(f"  ⚠️  {issue}")

if select_none_list:
    print(f"\nBlogs where _select_keyword returns None ({len(select_none_list)}):")
    for b in select_none_list:
        print(f"  ❌ {b}")

total = len(BLOGS)
healthy = len(can_publish_list)
if healthy == total:
    verdict = "GREEN"
elif healthy >= total / 2:
    verdict = "YELLOW"
else:
    verdict = "RED"

print(f"\n{'='*60}")
print(f"OVERALL HEALTH VERDICT: {verdict}")
print(f"{'='*60}")
print(f"Healthy: {healthy}/{total} blogs can publish")
print(f"Issues:  {total - healthy}/{total} blogs have problems")

# Determine exit code: fail if any blog cannot publish or missing filter
has_critical_issue = False
for blog_id, r in results.items():
    if not r["can_publish"] or not r["has_filter"]:
        has_critical_issue = True
        break

if has_critical_issue:
    print("\n❌ Dry-run FAILED: One or more blogs cannot publish or missing filters.")
    sys.exit(1)
else:
    print("\n✅ Dry-run PASSED: All blogs healthy.")
    sys.exit(0)
