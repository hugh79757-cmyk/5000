#!/usr/bin/env python3
"""
Sync SAP publish logs to dashboard cache.
Copies from /Users/twinssn/Projects/SAP/data/publish_log.db → data/dashboard/data/sap_posts.db
"""

import sqlite3
from datetime import datetime
from pathlib import Path

SAP_DB = Path("/Users/twinssn/Projects/SAP/data/publish_log.db")
DASHBOARD_CACHE = Path(__file__).resolve().parent.parent / "data" / "sap_posts.db"


def sync_sap():
    """Sync SAP publish logs to dashboard cache."""
    if not SAP_DB.exists():
        print(f"❌ SAP DB not found: {SAP_DB}")
        return False
    
    # Read SAP
    sap_conn = sqlite3.connect(str(SAP_DB))
    sap_conn.row_factory = sqlite3.Row
    rows = sap_conn.execute("""
        SELECT domain as blog_id, title, date as created_at, url, 'published' as status
        FROM publish_log
        WHERE date > datetime('now', '-90 days')
        ORDER BY date DESC
    """).fetchall()
    
    print(f"📊 Found {len(rows)} SAP publish logs (last 90 days)")
    
    # Write to dashboard cache
    DASHBOARD_CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache_conn = sqlite3.connect(str(DASHBOARD_CACHE))
    cache_conn.execute("""
        CREATE TABLE IF NOT EXISTS sap_posts (
            blog_id TEXT NOT NULL,
            title TEXT,
            created_at TEXT NOT NULL,
            url TEXT DEFAULT '',
            synced_at TEXT DEFAULT (datetime('now')),
            UNIQUE(blog_id, created_at, title)
        )
    """)
    cache_conn.execute("CREATE INDEX IF NOT EXISTS idx_sap_blog ON sap_posts(blog_id)")
    cache_conn.execute("CREATE INDEX IF NOT EXISTS idx_sap_created ON sap_posts(created_at)")
    
    count = 0
    for row in rows:
        try:
            cache_conn.execute("""
                INSERT OR REPLACE INTO sap_posts (blog_id, title, created_at, url, synced_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (row['blog_id'], row['title'], row['created_at'], row['url']))
            count += 1
        except Exception as e:
            print(f"⚠️  Failed to insert {row['blog_id']}: {e}")
    
    cache_conn.commit()
    cache_conn.close()
    sap_conn.close()
    
    print(f"✅ Synced {count} SAP posts to dashboard cache")
    print(f"📁 Cache: {DASHBOARD_CACHE}")
    return True


if __name__ == "__main__":
    success = sync_sap()
    exit(0 if success else 1)
