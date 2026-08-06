"""ops_dashboard.checks.freshness — 블로그 신선도 검사

계열별 예상 발행 주기를 기준으로 마지막 성공 발행 후 경과일을 검사한다.
"""
from __future__ import annotations

import logging

from ops_dashboard.checks import register_check
from ops_dashboard.db import get_blog_config_status, get_blog_brand, get_blog_domain, get_blog_days_since_last_publish

logger = logging.getLogger(__name__)

# 계열별 stale 기준 (일)
BRAND_THRESHOLDS: dict[str, int] = {
    "cuap": 1,
    "etap": 3,
    "tap": 7,
    "stap": 7,
    "cap": 7,
    "rap": 7,
    "seap": 7,
    "manual": 30,
}


@register_check("freshness")
def check_freshness(conn, blog_id: str) -> dict:
    """마지막 성공 발행 후 경과일 vs 계열 기준 검사."""
    config_status = get_blog_config_status(conn, blog_id)
    if not config_status:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found in lifecycle"}

    brand = get_blog_brand(conn, blog_id)
    if not brand:
        return {"status": "unknown", "detail": f"Blog {blog_id} brand not found"}

    days = get_blog_days_since_last_publish(conn, blog_id)

    # 비활성/비활성화 블로그는 스킵
    if config_status in ("inactive", "disabled"):
        return {
            "status": "pass",
            "detail": f"Blog is {config_status} — freshness check not applicable",
            "evidence_url": "",
        }

    # 발행 데이터 없는 경우
    if days is None:
        return {
            "status": "unknown",
            "detail": "No publish data available (days_since_last_publish is NULL)",
            "evidence_url": "",
        }

    threshold = BRAND_THRESHOLDS.get(brand, 7)

    if days > threshold:
        return {
            "status": "fail",
            "detail": f"Stale: {days} days since last publish (threshold: {threshold}d for {brand})",
            "evidence_url": "",
        }

    return {
        "status": "pass",
        "detail": f"Last publish {days}d ago (threshold: {threshold}d for {brand})",
        "evidence_url": "",
    }
