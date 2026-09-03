"""Extract demand signals from GSC keyword data (Phase 77, observation mode).

Reads analytics.db gsc_keywords (last 90 days), keeps queries with total
clicks >= 1, caps 20 queries per blog, writes data/keyword_performance.json
atomically (tmp + os.replace). This JSON is the learning state — regenerable
from raw data every collection cycle; rollback = delete file, next cycle
rebuilds it. Consumers (Wave 2) do token matching on their side.
"""

import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("performance_signals")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "analytics.db"
OUT_PATH = DATA_DIR / "keyword_performance.json"
WINDOW_DAYS = 90
MIN_CLICKS = 1
MAX_PER_BLOG = 20


def extract_signals():
    """Return {blog_id: [query, ...]} — top clicked queries, 90-day window."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
        try:
            rows = conn.execute(
                "SELECT blog_id, query, SUM(clicks) AS total_clicks "
                "FROM gsc_keywords "
                "WHERE date >= date('now', ?) "
                "GROUP BY blog_id, query "
                "HAVING total_clicks >= ? "
                "ORDER BY total_clicks DESC",
                (f"-{WINDOW_DAYS} days", MIN_CLICKS),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.error("gsc_keywords read failed: %s", exc)
        return {}
    signals = {}
    for blog_id, query, _total in rows:
        queries = signals.setdefault(blog_id, [])
        if len(queries) < MAX_PER_BLOG:
            queries.append(query)
    return signals


def write_signals(signals, path=OUT_PATH):
    """Atomic write: tmp file then os.replace. Returns True on success."""
    tmp = Path(str(path) + ".tmp")
    try:
        tmp.write_text(json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        logger.error("keyword_performance.json write failed: %s", exc)
        return False
    return True


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    signals = extract_signals()
    assert signals, "extract_signals() empty — check gsc_keywords data"
    all_queries = [q for qs in signals.values() for q in qs]
    # Known real patterns from 2026-09-03 data audit (CONTEXT.md)
    assert any("유지비" in q for q in all_queries), "expected '유지비' pattern missing"
    assert any("드라이브" in q for q in all_queries), "expected '드라이브' pattern missing"
    total = sum(len(qs) for qs in signals.values())
    print(f"[perf-signals] blogs={len(signals)} patterns={total}")
    for blog_id in sorted(signals):
        print(f"  {blog_id}: {signals[blog_id][:3]}")
    if dry_run:
        print("[perf-signals] dry-run — JSON not written")
    else:
        assert write_signals(signals), "write_signals failed"
        print(f"[perf-signals] wrote {OUT_PATH}")
