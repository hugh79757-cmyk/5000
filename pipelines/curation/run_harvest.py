"""Standalone harvester runner (CLI). Schedule via cron — dispatcher/scheduler untouched.

    python -m pipelines.curation.run_harvest

Window: 02:00-06:00 KST only. Outside -> skip, exit(0).
SafetyGuard HARD_STOP -> exit(1).
Log: stdout + /var/log/harvest_{YYYYMMDD}.log
"""

import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
WINDOW_START, WINDOW_END = 2, 6  # 02:00-05:59:59 KST
LOG_DIR = "/var/log"


def _pool_db():
    """keyword_pool 저장 대상 curation.db 경로 (collector와 동일 파일)."""
    from pipelines.curation.collector import DB_PATH
    return DB_PATH


def _save_to_pool(keywords, source_tag="harvest") -> int:
    """수확 키워드를 keyword_pool에 INSERT OR IGNORE. 실패해도 harvest 결과에 영향 없음."""
    saved = 0
    try:
        conn = sqlite3.connect(_pool_db())
        conn.execute(
            "CREATE TABLE IF NOT EXISTS keyword_pool ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " blog_id TEXT DEFAULT '',"
            " keyword TEXT NOT NULL UNIQUE,"
            " source TEXT NOT NULL,"
            " harvested_at TEXT NOT NULL,"
            " used INTEGER DEFAULT 0,"
            " used_at TEXT DEFAULT NULL)"
        )
        now = datetime.now(KST).isoformat()
        for kw in keywords:
            cur = conn.execute(
                "INSERT OR IGNORE INTO keyword_pool (blog_id, keyword, source, harvested_at)"
                " VALUES ('', ?, ?, ?)",
                (kw, source_tag, now),
            )
            saved += cur.rowcount
        conn.commit()
        conn.close()
    except Exception as e:
        logging.getLogger("run_harvest").warning(f"keyword_pool 저장 실패(무시): {e}")
    return saved


def in_harvest_window(now: datetime | None = None) -> bool:
    now = now or datetime.now(KST)
    return WINDOW_START <= now.hour < WINDOW_END


def main() -> int:
    if not in_harvest_window():
        print("[SKIP] Outside harvest window")
        return 0

    log_path = f"{LOG_DIR}/harvest_{datetime.now(KST):%Y%m%d}.log"
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_path)],
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("run_harvest")

    from pipelines.curation.coupang_client import get_best_categories, get_goldbox
    from pipelines.curation.keyword_harvester import KeywordHarvester

    def fetch_fn(source: str) -> dict:
        # Coupang returns {"status_code": int, "body": {...}}; map to harvester contract.
        if source == "bestcategories":
            resp = get_best_categories()
        else:
            resp = get_goldbox()
        body = resp.get("body") or {}
        keywords = [
            (p.get("keyword") or p.get("productName") or "")
            for p in (body.get("data") or [])
            if isinstance(p, dict)
        ]
        return {
            "status_code": resp.get("status_code", 0),
            "rcode": str(body.get("rCode", "")),
            "keywords": keywords,
        }

    try:
        from pipelines.curation.keywords import KEYWORD_MAP
        existing = {kw for kws in KEYWORD_MAP.values() for kw in kws}
    except Exception:
        existing = set()

    # api_call_log는 harvester._call_api 단일 지점에서 기록 (이중 카운트 방지)
    harvester = KeywordHarvester(fetch_fn=fetch_fn, existing_keywords=existing,
                                 db_path=_pool_db())
    new_keywords = harvester.harvest()

    saved = _save_to_pool(new_keywords)
    logger.info(f"harvest complete: {len(new_keywords)} new keywords, {saved} saved to keyword_pool")
    for kw in new_keywords:
        print(kw)

    if harvester.guard.is_stopped:
        logger.critical("SafetyGuard HARD_STOP — aborting")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
