"""ETAP topic manager — destinations DB에서 미발행 토픽 선택."""
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent.parent.parent / "data" / "travel-en.db"


def pick_topic(blog_id: str, window_days: int = 30) -> dict | None:
    """우선순위 높고, window_days 내 발행되지 않은 토픽 1개 반환."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=window_days)).isoformat()

    row = c.execute("""
        SELECT t.topic_id, t.dest_id, t.template_key, t.title, t.slug,
               d.city, d.country, d.region
        FROM topics t
        JOIN destinations d ON t.dest_id = d.dest_id
        WHERE t.exhausted = 0
          AND t.topic_id NOT IN (
              SELECT COALESCE(topic_id, 0) FROM publish_log
              WHERE blog_id = ? AND published_at > ?
          )
        ORDER BY t.priority DESC, t.topic_id ASC
        LIMIT 1
    """, (blog_id, cutoff)).fetchone()

    conn.close()

    if not row:
        return None

    return dict(row)


def mark_published(topic_id: int, blog_id: str, title: str, slug: str, url: str = ""):
    """발행 완료 기록."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO publish_log (topic_id, blog_id, title, slug, published_at, url) VALUES (?, ?, ?, ?, ?, ?)",
        (topic_id, blog_id, title, slug, datetime.now().isoformat(), url)
    )
    conn.commit()
    conn.close()
