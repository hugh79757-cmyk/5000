"""ops_dashboard.checks — 플러그인 헬스체크 엔진

각 check 함수는 (conn, blog_id) → dict를 반환:
  {"status": "pass"|"fail"|"unknown", "detail": str, "evidence_url": str}

register_check()로 등록된 check만 run_all_checks()에서 실행됨.
"""
from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

# 플러그인 레지스트리: 이름 → check 함수
CHECKS: dict[str, Callable] = {}


def register_check(name: str):
    """데코레이터: check 함수를 레지스트리에 등록."""
    def decorator(fn):
        CHECKS[name] = fn
        return fn
    return decorator


def run_all_checks(
    conn,
    blog_ids: list[str] | None = None,
) -> dict:
    """등록된 모든 check를 실행하고 결과를 DB에 기록.

    반환: {"total": int, "pass": int, "fail": int, "unknown": int,
            "attention_items": list}
    """
    from ops_dashboard.db import record_check, get_all_blogs

    blogs = get_all_blogs(conn)
    if blog_ids:
        blogs = [b for b in blogs if b["blog_id"] in blog_ids]

    summary = {"total": 0, "pass": 0, "fail": 0, "unknown": 0, "attention_items": []}

    for blog in blogs:
        bid = blog["blog_id"]
        for check_name, check_fn in CHECKS.items():
            try:
                result = check_fn(conn, bid)
                status = result.get("status", "unknown")
                detail = result.get("detail", "")
                evidence_url = result.get("evidence_url", "")

                record_check(conn, bid, check_name, status, detail, evidence_url)

                summary["total"] += 1
                if status in summary:
                    summary[status] += 1
                else:
                    summary["unknown"] += 1

                if status == "fail":
                    summary["attention_items"].append({
                        "blog_id": bid,
                        "check": check_name,
                        "detail": detail,
                        "evidence_url": evidence_url,
                    })
            except Exception as e:
                logger.error("Check %s failed for %s: %s", check_name, bid, e)
                record_check(conn, bid, check_name, "unknown", f"Error: {e}")
                summary["total"] += 1
                summary["unknown"] += 1

    return summary
