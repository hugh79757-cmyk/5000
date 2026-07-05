#!/usr/bin/env python3
"""Health dashboard: aggregates quarantine stats, recent failures, publish volume."""
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.curation.keyword_health import KeywordHealthStore
from shared.relevance_scorer import get_last_week_range


DB_PATH = PROJECT_ROOT / "data" / "curation.db"
BLOGS = [
    "laptop-hugo", "appliance-hugo", "interior-hugo", "baby-hugo",
    "fitness-hugo", "health-hugo", "pet-hugo", "kitchen-hugo",
    "beauty-hugo", "camping-hugo",
]


def get_quarantine_summary():
    """Return dict: blog_id -> quarantined_count and overall total."""
    store = KeywordHealthStore(str(DB_PATH))
    total_quarantined = 0
    per_blog = {}
    for blog_id in BLOGS:
        qk = store.get_quarantined_keywords(blog_id)
        count = len(qk)
        per_blog[blog_id] = count
        total_quarantined += count
    return total_quarantined, per_blog


def get_failures_last_24h():
    """Return dict: blog_id -> count of failed validations in last 24h.
    Assumes publish_log has validation_passed column (default 1)."""
    conn = sqlite3.connect(str(DB_PATH))
    since = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    failures_by_blog = {}
    try:
        rows = conn.execute(
            "SELECT blog_id, COUNT(*) as cnt FROM publish_log WHERE published_at > ? AND validation_passed = 0 GROUP BY blog_id",
            (since,)
        ).fetchall()
        for blog_id, cnt in rows:
            failures_by_blog[blog_id] = cnt
    except sqlite3.OperationalError:
        # Column may not exist yet in older DBs
        pass
    conn.close()
    return failures_by_blog


def get_publish_volume_last_7d():
    """Return dict: blog_id -> count of published articles (publish_log rows) in last 7 days."""
    conn = sqlite3.connect(str(DB_PATH))
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    volume = {}
    rows = conn.execute(
        "SELECT blog_id, COUNT(*) as cnt FROM publish_log WHERE published_at > ? GROUP BY blog_id",
        (since,)
    ).fetchall()
    for blog_id, cnt in rows:
        volume[blog_id] = cnt
    conn.close()
    return volume


def render_markdown_table(per_blog_data):
    """Render a Markdown table with rows ordered by blog_id."""
    headers = ["Blog", "Quarantined", "Failures (24h)", "Publishes (7d)", "Health"]
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for blog_id in BLOGS:
        q = per_blog_data[blog_id]["quarantined"]
        f = per_blog_data[blog_id]["failures"]
        p = per_blog_data[blog_id]["publishes"]
        # Health status: OK if q==0 and f==0; WARN if some but not critical; ERR if many
        if q == 0 and f == 0:
            health = "✅ OK"
        elif q > 0 and f == 0:
            health = "⚠️ Q"
        elif f > 0:
            health = "❌ ERR"
        else:
            health = "?"
        lines.append(f"| {blog_id} | {q} | {f} | {p} | {health} |")
    return "\n".join(lines)


def main():
    print(f"# CUAP Health Dashboard — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"\n*Data source: {DB_PATH}*\n")

    total_quarantined, quarantine_per_blog = get_quarantine_summary()
    failures = get_failures_last_24h()
    publishes = get_publish_volume_last_7d()

    # Combine per-blog data
    per_blog_data = {}
    for blog_id in BLOGS:
        per_blog_data[blog_id] = {
            "quarantined": quarantine_per_blog.get(blog_id, 0),
            "failures": failures.get(blog_id, 0),
            "publishes": publishes.get(blog_id, 0),
        }

    # Overall summary
    total_publishes = sum(publishes.values())
    total_failures = sum(failures.values())
    print("## Summary")
    print(f"- **Total quarantined keywords:** {total_quarantined}")
    print(f"- **Failed validations (24h):** {total_failures}")
    print(f"- **Published posts (7d):** {total_publishes}")
    print()

    # Table
    print("## Per-Blog Metrics")
    print()
    print(render_markdown_table(per_blog_data))
    print()

    # Notes
    print("## Notes")
    print("- Quarantined: Keywords under exponential backoff due to consecutive failures.")
    print("- Failures: Publish validation failures in the last 24 hours (e.g., low relevance, technical errors).")
    print("- Publishes: Number of posts successfully published in the last 7 days.")
    print()

    # Optional: send to Telegram could be added with a flag
    # from shared.telegram_notifier import send_message as tg_send
    # tg_send("Health dashboard report...")


if __name__ == "__main__":
    main()
