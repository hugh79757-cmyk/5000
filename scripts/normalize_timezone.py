#!/usr/bin/env python3
"""시간대 정규화: +07/+09 문자열 -> UTC ISO8601 (1회성 마이그레이션)"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

PLUS07 = timezone(timedelta(hours=7))
PLUS09 = timezone(timedelta(hours=9))

TARGET_DBS = [
    ("data/content.db", "articles", "published_at", PLUS09),
    ("data/car.db", "articles", "published_at", PLUS09),
    ("data/stap_content.db", "articles", "published_at", None),  # 이미 UTC
    ("data/rap.db", "articles", "published_at", PLUS09),
    ("data/senior.db", "articles", "published_at", PLUS09),
    ("data/gap.db", "articles", "published_at", PLUS09),
    ("data/curation.db", "articles", "published_at", PLUS09),
    ("data/travel-en.db", "articles", "published_at", PLUS09),
    ("data/stock.db", "articles", "published_at", PLUS09),
    ("data/festival.db", "articles", "published_at", PLUS09),
    ("data/course.db", "articles", "published_at", PLUS09),
]

def normalize_db(db_path: str, table: str, col: str, src_tz):
    path = Path(db_path)
    if not path.exists():
        print(f"[SKIP] {db_path} not found")
        return
    
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f"SELECT rowid, {col} FROM {table}").fetchall()
        updated = 0
        for rowid, val in rows:
            if val and isinstance(val, str) and 'T' not in val and len(val) == 19:
                # +07/+09 문자열 (예: 2026-09-17 10:24:04)
                try:
                    if src_tz:
                        dt = datetime.strptime(val, "%Y-%m-%d %H:%M:%S").replace(tzinfo=src_tz)
                        utc_val = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        conn.execute(f"UPDATE {table} SET {col}=? WHERE rowid=?", (utc_val, rowid))
                        updated += 1
                except ValueError:
                    pass
        conn.commit()
        print(f"[OK] {db_path}.{table}.{col}: {updated} rows normalized")
    except sqlite3.OperationalError as e:
        print(f"[SKIP] {db_path}.{table}: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("=== 시간대 정규화 시작 (+07/+09 -> UTC) ===")
    for db_path, table, col, src_tz in TARGET_DBS:
        normalize_db(db_path, table, col, src_tz)
    print("=== 완료 ===")