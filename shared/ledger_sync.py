import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT       = Path(__file__).parent.parent
DATA       = ROOT / "data"
LEDGER_DB  = DATA / "content.db"

SOURCES = [
    {
        "name":    "etap",
        "db":      DATA / "travel-en.db",
        "sql":     "SELECT blog_id, title, slug, published_at, url FROM publish_log",
        "mapping": ("blog_id", "title", "slug", "published_at", "url"),
    },
    {
        "name":    "stock",
        "db":      DATA / "stock.db",
        "sql":     "SELECT blog_id, title, '', published_at FROM publish_log",
        "mapping": ("blog_id", "title", "slug", "published_at"),
    },
    {
        "name":    "curation",
        "db":      DATA / "curation.db",
        "sql":     "SELECT blog_id, title, slug, published_at FROM publish_log",
        "mapping": ("blog_id", "title", "slug", "published_at"),
    },
    {
        "name":    "rap",
        "db":      DATA / "rap.db",
        "sql":     "SELECT blog_id, title, '', published_at FROM publish_log",
        "mapping": ("blog_id", "title", "slug", "published_at"),
    },
    {
        "name":    "cap",
        "db":      DATA / "car.db",
        "sql":     "SELECT site || '-hugo', title, slug, published_at, url FROM publish_log",
        "mapping": ("blog_id", "title", "slug", "published_at", "url"),
    },
    {
        "name":    "stap",
        "db":      Path(os.environ.get("STAP_ROOT", os.path.join(str(ROOT.parent), "STAP")), "data", "stap_content.db"),
        "sql":     "SELECT blog_id, title, slug, created_at, published_url FROM articles WHERE status='published'",
        "mapping": ("blog_id", "title", "slug", "published_at", "url"),
    },
    {
        "name":    "seap",
        "db":      DATA / "senior.db",
        "sql":     "SELECT blog_id, service_name, service_id, published_at, '' FROM services WHERE status='published'",
        "mapping": ("blog_id", "title", "slug", "published_at", "url"),
    },
    {
        "name":    "seap_blogger",
        "db":      DATA / "5000_content.db",
        "sql":     "SELECT blog_id, title, slug, published_at, published_url FROM articles WHERE blog_id='senior-blogger' AND status='published'",
        "mapping": ("blog_id", "title", "slug", "published_at", "url"),
    },
    {
        "name":    "tap",
        "db":      Path(os.environ.get("TAP_ROOT", os.path.join(str(ROOT.parent), "TAP")), "tap.db"),
        "sql":     "SELECT 'tap-hugo', post_title, '', published_at, post_url FROM publish_logs",
        "mapping": ("blog_id", "title", "slug", "published_at", "url"),
    },
]

def _ensure_schema(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS publish_ledger (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id       TEXT NOT NULL,
            title         TEXT NOT NULL,
            slug          TEXT DEFAULT '',
            published_url TEXT DEFAULT '',
            status        TEXT DEFAULT 'published',
            source        TEXT DEFAULT '',
            created_at    TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_dedup
        ON publish_ledger(blog_id, slug, DATE(created_at))
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ledger_blog_date
        ON publish_ledger(blog_id, created_at)
    """)
    conn.commit()

def _sync_source(ledger_conn, src):
    db_path = src["db"]
    if not db_path.exists():
        logger.warning(f"[ledger_sync] DB 없음: {db_path.name}")
        return 0
    try:
        src_conn = sqlite3.connect(db_path)
        rows = src_conn.execute(src["sql"]).fetchall()
        src_conn.close()
    except Exception as e:
        logger.exception(f"[ledger_sync] {src['name']} 조회 실패: {e}")
        return 0
    inserted = 0
    for row in rows:
        mapping = src["mapping"]
        blog_id    = row[mapping.index("blog_id")]
        title      = (row[mapping.index("title")] or "").strip()
        slug       = row[mapping.index("slug")] if "slug" in mapping else ""
        created_at = row[mapping.index("published_at")] if "published_at" in mapping else datetime.now().isoformat()
        url        = row[mapping.index("url")] if "url" in mapping else ""
        if not title or not blog_id:
            continue
        try:
            ledger_conn.execute(
                """INSERT OR IGNORE INTO publish_ledger
                   (blog_id, title, slug, published_url, status, source, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (blog_id, title, slug or "", url or "", "published", src["name"], created_at)
            )
            if ledger_conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
        except Exception as e:
            logger.debug(f"[ledger_sync] insert skip ({blog_id}): {e}")
    ledger_conn.commit()
    return inserted

def run_sync():
    try:
        conn = sqlite3.connect(str(LEDGER_DB))
        _ensure_schema(conn)
    except Exception as e:
        logger.exception(f"[ledger_sync] ledger DB 연결 실패: {e}")
        return {"success": False, "reason": str(e)}
    results = {}
    total = 0
    for src in SOURCES:
        n = _sync_source(conn, src)
        results[src["name"]] = n
        total += n
        if n > 0:
            logger.info(f"[ledger_sync] {src['name']}: {n}건 신규 등록")
    conn.close()
    logger.info(f"[ledger_sync] 완료 — 총 {total}건 신규: {results}")
    return {"success": True, "total": total, "detail": results}

def report(days=1):
    try:
        conn = sqlite3.connect(str(LEDGER_DB))
        _ensure_schema(conn)
        rows = conn.execute("""
            SELECT blog_id, COALESCE(source, 'unknown') as source, COUNT(*) as cnt
            FROM publish_ledger
            WHERE DATE(created_at) >= DATE('now', ? || ' days')
            GROUP BY blog_id, source
            ORDER BY cnt DESC
        """, (f"-{days-1}",)).fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.exception(f"[ledger_sync] report 실패: {e}")
        return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run_sync()
    print(f"\n동기화 결과: {result}")
    print("\n오늘 발행 현황:")
    for row in report(1):
        print(f"  {row[0]:25s} [{row[1]:8s}] {row[2]}건")
