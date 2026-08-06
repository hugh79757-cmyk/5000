"""Notification debounce module.

Implements a debounce mechanism so the same (blog_id, problem_id) combination
only triggers a Telegram push once per day. Subsequent pushes on the same day
are suppressed and counted for diagnostics.
"""

import sqlite3
from datetime import datetime


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS notification_debounce (
    blog_id TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    push_date TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    suppressed_count INTEGER DEFAULT 0,
    PRIMARY KEY (blog_id, problem_id, push_date)
)
"""


def init_debounce_tables(conn: sqlite3.Connection) -> None:
    """Create the notification_debounce table if it does not exist."""
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


def _today_str() -> str:
    """Return today's date as ISO date string (YYYY-MM-DD)."""
    return datetime.now().strftime("%Y-%m-%d")


def should_push(conn: sqlite3.Connection, blog_id: str, problem_id: str) -> bool:
    """Check whether a notification should be sent for (blog_id, problem_id) today.

    Returns True if no row exists for today (first push of the day) — caller
    should send the notification and then commit the row.
    Returns False if a row already exists for today — push is suppressed and
    the suppressed_count is incremented.
    """
    today = _today_str()
    try:
        row = conn.execute(
            "SELECT suppressed_count FROM notification_debounce "
            "WHERE blog_id = ? AND problem_id = ? AND push_date = ?",
            (blog_id, problem_id, today),
        ).fetchone()

        if row is None:
            conn.execute(
                "INSERT INTO notification_debounce "
                "(blog_id, problem_id, push_date, first_seen_at, suppressed_count) "
                "VALUES (?, ?, ?, ?, 0)",
                (blog_id, problem_id, today, datetime.now().isoformat()),
            )
            conn.commit()
            return True
        else:
            conn.execute(
                "UPDATE notification_debounce "
                "SET suppressed_count = suppressed_count + 1 "
                "WHERE blog_id = ? AND problem_id = ? AND push_date = ?",
                (blog_id, problem_id, today),
            )
            conn.commit()
            return False
    except sqlite3.Error:
        return True


def get_suppressed_count(conn: sqlite3.Connection, blog_id: str, problem_id: str) -> int:
    """Return the suppressed_count for (blog_id, problem_id) today.

    Returns 0 if no row exists or on error.
    """
    today = _today_str()
    try:
        row = conn.execute(
            "SELECT suppressed_count FROM notification_debounce "
            "WHERE blog_id = ? AND problem_id = ? AND push_date = ?",
            (blog_id, problem_id, today),
        ).fetchone()
        return row[0] if row else 0
    except sqlite3.Error:
        return 0


def get_today_stats(conn: sqlite3.Connection) -> dict:
    """Return today's debounce statistics for dashboard display.

    Returns a dict with keys:
        total_suppressed: total number of suppressed pushes today
        events: list of dicts with blog_id, problem_id, suppressed_count
    """
    today = _today_str()
    stats = {"total_suppressed": 0, "events": []}
    try:
        rows = conn.execute(
            "SELECT blog_id, problem_id, suppressed_count "
            "FROM notification_debounce "
            "WHERE push_date = ? ORDER BY suppressed_count DESC",
            (today,),
        ).fetchall()
        for row in rows:
            stats["events"].append({
                "blog_id": row[0],
                "problem_id": row[1],
                "suppressed_count": row[2],
            })
            stats["total_suppressed"] += row[2]
    except sqlite3.Error:
        pass
    return stats
