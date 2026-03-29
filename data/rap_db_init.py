"""RAP 전용 DB 초기화 + 일일 갱신"""
import os
import sqlite3
import logging
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

RAP_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rap.db")


def init_rap_db():
    """RAP 전용 DB 생성"""
    conn = sqlite3.connect(RAP_DB_PATH)
    conn.executescript("""
        -- 실거래가 데이터 (매일 갱신)
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lawd_cd TEXT NOT NULL,
            city TEXT NOT NULL,
            district TEXT NOT NULL,
            deal_ymd TEXT NOT NULL,
            apt_name TEXT NOT NULL,
            dong_name TEXT,
            exclu_use_ar REAL,
            floor INTEGER,
            build_year INTEGER,
            deal_amount INTEGER,
            deal_year INTEGER,
            deal_month INTEGER,
            deal_day INTEGER,
            fetched_at TEXT DEFAULT (datetime('now')),
            UNIQUE(lawd_cd, deal_ymd, apt_name, exclu_use_ar, floor, deal_day)
        );

        -- 청약 공고 데이터 (매일 갱신)
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pan_id TEXT UNIQUE,
            pan_nm TEXT NOT NULL,
            region_cd TEXT,
            region_nm TEXT,
            pan_type TEXT,
            pan_start TEXT,
            pan_end TEXT,
            pan_status TEXT,
            detail_url TEXT,
            fetched_at TEXT DEFAULT (datetime('now'))
        );

        -- 발행 기록 (중복 방지)
        CREATE TABLE IF NOT EXISTS publish_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            data_type TEXT NOT NULL,
            data_key TEXT NOT NULL,
            title TEXT,
            published_at TEXT DEFAULT (datetime('now')),
            UNIQUE(blog_id, data_key)
        );

        -- 키워드 (gap.db에서 분리)
        CREATE TABLE IF NOT EXISTS keywords (
            keyword TEXT PRIMARY KEY,
            category TEXT DEFAULT '금융/부동산',
            blog_target TEXT,
            priority INTEGER DEFAULT 3,
            use_count INTEGER DEFAULT 0,
            last_used_at TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- 갱신 기록 (하루 1회 체크용)
        CREATE TABLE IF NOT EXISTS refresh_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            refresh_date TEXT NOT NULL,
            trades_added INTEGER DEFAULT 0,
            subs_added INTEGER DEFAULT 0,
            duration_sec REAL,
            refreshed_at TEXT DEFAULT (datetime('now')),
            UNIQUE(refresh_date)
        );

        CREATE INDEX IF NOT EXISTS idx_trades_lawd ON trades(lawd_cd, deal_ymd);
        CREATE INDEX IF NOT EXISTS idx_trades_apt ON trades(apt_name);
        CREATE INDEX IF NOT EXISTS idx_subs_region ON subscriptions(region_cd);
        CREATE INDEX IF NOT EXISTS idx_publish_blog ON publish_log(blog_id, data_type);
        CREATE INDEX IF NOT EXISTS idx_kw_target ON keywords(blog_target, status);
    """)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.commit()
    conn.close()
    logger.info(f"RAP DB 초기화 완료: {RAP_DB_PATH}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_rap_db()
    print(f"DB 생성: {RAP_DB_PATH}")
