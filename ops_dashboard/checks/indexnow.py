"""ops_dashboard.checks.indexnow — IndexNow 제출 실패 탐지 (detect-only)

scripts/indexnow.py 가 매 실행마다 data/indexnow_last_status.json 에
도메인별 엔진 제출 결과(연속 실패 수, 마지막 상태 코드)를 기록한다.
이 check는 그 상태 파일을 읽어, 대상 블로그 도메인의 최근 제출이
실패했으면 fail 를 반환한다.

이 check는 **탐지만** 한다. 자동수정/재시도/배포는 절대 하지 않는다.
(경고 발송은 scripts/indexnow.py 쪽에서만 수행하며, 여기서는 기록/표시만.)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from ops_dashboard.checks import register_check
from ops_dashboard.db import get_blog_config_status, get_blog_domain

logger = logging.getLogger(__name__)

try:
    from shared.paths import DATA_DIR
except Exception:
    DATA_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
    )

STATE_PATH = os.path.join(DATA_DIR, "indexnow_last_status.json")
_STALE_HOURS = 24


@register_check("indexnow")
def check_indexnow(conn, blog_id: str) -> dict:
    """블로그 도메인의 최근 IndexNow 제출 상태를 상태 파일에서 탐지."""
    config_status = get_blog_config_status(conn, blog_id)
    if not config_status:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found in lifecycle"}
    if config_status in ("inactive", "disabled"):
        return {"status": "pass", "detail": f"Blog is {config_status} — indexnow check not applicable"}

    domain = get_blog_domain(conn, blog_id)
    if not domain:
        return {"status": "unknown", "detail": "domain not found"}

    if not os.path.exists(STATE_PATH):
        return {"status": "pass", "detail": "No IndexNow submission record yet"}

    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        logger.warning("indexnow state read failed: %s", e)
        return {"status": "unknown", "detail": f"state read error: {e}"}

    updated_at = state.get("updated_at")
    if updated_at:
        try:
            age_h = (datetime.now() - datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600
            if age_h > _STALE_HOURS:
                return {"status": "pass", "detail": f"IndexNow state stale ({age_h:.0f}h old) — no recent submission"}
        except Exception:
            pass

    dom = (state.get("domains") or {}).get(domain)
    if not dom:
        return {"status": "pass", "detail": f"No IndexNow record for {domain}"}

    engines = dom.get("engines") or {}
    failed = []
    for engine, info in engines.items():
        cf = info.get("consecutive_failures", 0)
        last = info.get("last_status")
        if cf >= 1 or (last not in (200, 202, None)):
            failed.append(f"{engine.split('//')[-1]}: consecutive={cf} last={last}")

    if failed:
        return {
            "status": "fail",
            "detail": f"IndexNow submission failing for {domain}: " + "; ".join(failed[:3]),
            "evidence_url": "",
        }
    return {"status": "pass", "detail": f"IndexNow submission OK for {domain}"}
