"""
SAP publish_log → dashboard 캐시 동기화

SAP publish_log.db의 발행 이력을 읽어서 대시보드 전용 캐시 DB에 저장.
매시간 cron/launchd로 실행.

사용법:
    python sync_sap.py
"""

import sqlite3
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ── Paths ──
_SAP_DB = Path.home() / "Projects" / "SAP" / "data" / "publish_log.db"
_DASHBOARD_DATA = Path(__file__).resolve().parent.parent / "data"
_CACHE_DB = _DASHBOARD_DATA / "sap_posts.db"

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ── SAP domain → dashboard blog_id 매핑 ──
DOMAIN_TO_BLOG_ID = {
    "https://kboplayer.informationhot.kr": "kboplayer",
    "https://kboteam.informationhot.kr": "kboteam",
    "https://kboschedule.informationhot.kr": "kboschedule",
    "https://proto.informationhot.kr": "proto",
    "https://protostats.informationhot.kr": "protostats",
    "https://fstats.informationhot.kr": "fstats",
    "https://fsched.informationhot.kr": "fsched",
    "https://betguide.informationhot.kr": "betguide",
    "https://protoking.informationhot.kr": "protoking",
    "https://sports.rotcha.kr": "sports-rotcha",
    "https://kbo.rotcha.kr": "kbo-rotcha",
    # Blogger 대체 도메인
    "sports-rotcha.blogspot.com": "sports-rotcha",
    "kbo-rotcha.blogspot.com": "kbo-rotcha",
}


def sync_sap_posts():
    """SAP publish_log.db → sap_posts.db 캐시"""
    if not _SAP_DB.exists():
        logger.error(f"SAP DB 없음: {_SAP_DB}")
        return {"status": "error", "message": f"SAP DB not found: {_SAP_DB}"}

    _DASHBOARD_DATA.mkdir(parents=True, exist_ok=True)

    # 캐시 DB 스키마
    cache_conn = sqlite3.connect(str(_CACHE_DB))
    cache_conn.execute(
        """CREATE TABLE IF NOT EXISTS sap_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            domain TEXT,
            title TEXT,
            topic_key TEXT,
            post_id TEXT,
            url TEXT,
            created_at TEXT NOT NULL,
            synced_at TEXT DEFAULT (datetime('now','localtime'))
        )"""
    )
    cache_conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_sap_blog_date
           ON sap_posts(blog_id, created_at)"""
    )
    cache_conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_sap_topic
           ON sap_posts(blog_id, topic_key)"""
    )

    # SAP publish_log 읽기 (최근 90일)
    cutoff = (datetime.now() - timedelta(days=90)).isoformat()
    sap_conn = sqlite3.connect(str(_SAP_DB))
    rows = sap_conn.execute(
        """SELECT date, domain, topic_key, title, post_id, url, created_at
           FROM publish_log
           WHERE created_at > ?
           ORDER BY created_at DESC""",
        (cutoff,),
    ).fetchall()
    sap_conn.close()
    logger.info(f"SAP publish_log: {len(rows)}건 (최근 90일)")

    # 캐시에 INSERT
    inserted = 0
    skipped = 0
    for row in rows:
        date_str, domain, topic_key, title, post_id, url, created_at = row
        blog_id = DOMAIN_TO_BLOG_ID.get(domain, domain)
        try:
            cur = cache_conn.execute(
                """INSERT OR IGNORE INTO sap_posts
                   (blog_id, domain, title, topic_key, post_id, url, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (blog_id, domain, title, topic_key, post_id, url, created_at),
            )
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            logger.warning(f"  INSERT 실패: {e}")
            skipped += 1

    cache_conn.commit()
    cache_conn.close()
    logger.info(f"SAP 동기화 완료: {inserted}건 추가, {skipped}건 중복")
    return {
        "status": "ok",
        "total": len(rows),
        "inserted": inserted,
        "skipped": skipped,
    }


if __name__ == "__main__":
    result = sync_sap_posts()
    print(f"Result: {result}")
