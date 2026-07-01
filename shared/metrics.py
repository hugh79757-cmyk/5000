"""
metrics.py — Pipeline metrics collection and reporting

Tracks: articles published per day, error rate per pipeline,
API call count (TourAPI/OpenAI), content diversity score.

Metrics stored in SQLite (content.db, metrics table).
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta

from shared.db_paths import PUBLISH_LEDGER_DB

logger = logging.getLogger(__name__)

_METRICS_DB = os.path.join(
    os.path.dirname(PUBLISH_LEDGER_DB),
    "metrics.db",
)


def _get_conn():
    os.makedirs(os.path.dirname(_METRICS_DB), exist_ok=True)
    conn = sqlite3.connect(_METRICS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            blog_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            UNIQUE(date, blog_id, metric_name)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            api_name TEXT NOT NULL,
            endpoint TEXT,
            duration_ms INTEGER,
            status TEXT
        )
    """)
    conn.commit()
    return conn


def record_api_call(api_name: str, endpoint: str = "", duration_ms: int = 0, status: str = "ok"):
    """Record an external API call (TourAPI, OpenAI, etc.)"""
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO api_calls (timestamp, api_name, endpoint, duration_ms, status) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), api_name, endpoint, duration_ms, status),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Metrics: failed to record API call: {e}")


def record_publish(blog_id: str):
    """Record a successful publish for daily metrics."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = _get_conn()
        conn.execute(
            """INSERT OR IGNORE INTO metrics (date, blog_id, metric_name, metric_value)
               VALUES (?, ?, 'publish_count', 0)""",
            (today, blog_id),
        )
        conn.execute(
            """UPDATE metrics SET metric_value = metric_value + 1
               WHERE date = ? AND blog_id = ? AND metric_name = 'publish_count'""",
            (today, blog_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Metrics: failed to record publish: {e}")


def record_error(blog_id: str, pipeline: str = ""):
    """Record a publish failure for error rate calculation."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = _get_conn()
        conn.execute(
            """INSERT OR IGNORE INTO metrics (date, blog_id, metric_name, metric_value)
               VALUES (?, ?, 'error_count', 0)""",
            (today, blog_id),
        )
        conn.execute(
            """UPDATE metrics SET metric_value = metric_value + 1
               WHERE date = ? AND blog_id = ? AND metric_name = 'error_count'""",
            (today, blog_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Metrics: failed to record error: {e}")


def record_diversity(blog_id: str, unique_sigungus: int):
    """Record content diversity score (unique sigungus published today)."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = _get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO metrics (date, blog_id, metric_name, metric_value)
               VALUES (?, ?, 'diversity_score', ?)""",
            (today, blog_id, unique_sigungus),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Metrics: failed to record diversity: {e}")


def get_daily_summary(days: int = 7) -> dict:
    """Return aggregated metrics for the last N days."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        conn = _get_conn()
        rows = conn.execute(
            """SELECT date, blog_id, metric_name, metric_value
               FROM metrics
               WHERE date >= ?
               ORDER BY date DESC""",
            (cutoff,),
        ).fetchall()
        conn.close()

        summary = {
            "period_days": days,
            "total_publishes": 0,
            "total_errors": 0,
            "error_rate": 0.0,
            "by_blog": {},
            "by_date": {},
        }

        for date, blog_id, name, value in rows:
            if name == "publish_count":
                summary["total_publishes"] += value
            elif name == "error_count":
                summary["total_errors"] += value
            elif name == "diversity_score":
                pass

            if blog_id not in summary["by_blog"]:
                summary["by_blog"][blog_id] = {"publishes": 0, "errors": 0, "diversity": 0}
            summary["by_blog"][blog_id]["publishes"] += value if name == "publish_count" else 0
            summary["by_blog"][blog_id]["errors"] += value if name == "error_count" else 0
            if name == "diversity_score":
                summary["by_blog"][blog_id]["diversity"] = max(
                    summary["by_blog"][blog_id]["diversity"], value
                )

        total = summary["total_publishes"] + summary["total_errors"]
        summary["error_rate"] = round(summary["total_errors"] / total, 4) if total > 0 else 0.0

        return summary
    except Exception as e:
        logger.warning(f"Metrics: failed to get summary: {e}")
        return {"error": str(e)}


def get_api_call_summary(days: int = 7) -> dict:
    """Return API call statistics for the last N days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    try:
        conn = _get_conn()
        rows = conn.execute(
            """SELECT api_name, COUNT(*) as calls,
                      AVG(duration_ms) as avg_ms,
                      SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) as errors
               FROM api_calls
               WHERE timestamp >= ?
               GROUP BY api_name""",
            (cutoff,),
        ).fetchall()
        conn.close()
        return {
            "period_days": days,
            "by_api": {
                name: {
                    "calls": count,
                    "avg_duration_ms": round(avg, 1) if avg else 0,
                    "errors": err or 0,
                }
                for name, count, avg, err in rows
            },
        }
    except Exception as e:
        logger.warning(f"Metrics: failed to get API summary: {e}")
        return {"error": str(e)}


def print_metrics_summary(days: int = 7):
    """Print a human-readable metrics summary."""
    summary = get_daily_summary(days)
    api_summary = get_api_call_summary(days)

    print(f"=== Metrics Summary (last {days}d) ===")
    print(f"Total publishes: {summary.get('total_publishes', 0)}")
    print(f"Total errors:    {summary.get('total_errors', 0)}")
    print(f"Error rate:      {summary.get('error_rate', 0):.1%}")
    print()
    if summary.get("by_blog"):
        print("By blog:")
        for blog_id, stats in summary["by_blog"].items():
            print(f"  {blog_id}: {stats['publishes']} pubs, {stats['errors']} errs, diversity={stats['diversity']}")
    print()
    if api_summary.get("by_api"):
        print("API calls:")
        for name, stats in api_summary["by_api"].items():
            print(f"  {name}: {stats['calls']} calls, avg {stats['avg_duration_ms']}ms, {stats['errors']} errs")


if __name__ == "__main__":
    print_metrics_summary()
