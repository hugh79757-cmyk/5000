"""ops_dashboard.checks.freshness — 블로그 신선도 검사

계열별 예상 발행 주기를 기준으로 마지막 성공 발행 후 경과일을 검사한다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

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


# 발행 로그의 created_at이 기록되는 기준 시간대 (KST, UTC+9).
# dispatcher.py:388이 publish_ledger.created_at에 naive 서버 로컬 시각을 기록하나,
# 관측상 sitemap lastmod(+09:00)와 정렬되어 KST로 취급한다.
_KST = timezone(timedelta(hours=9))


def _parse_last_published(conn, blog_id: str) -> datetime | None:
    """publish_ledger에서 status='published' 최신 created_at을 KST 기준 datetime으로 변환.

    캐시 컬럼(days_since_last_publish)이 아니라 실데이터를 직접 조회해
    freshness 호출 시점 기준으로 재계산한다. (기존 캐시는 YAML 동기화
    시점에만 갱신되어 시간 경과를 반영하지 못하는 결함이 있었음)
    """
    from ops_dashboard.db import get_publish_log_conn

    ledger = get_publish_log_conn()
    try:
        row = ledger.execute(
            "SELECT MAX(created_at) AS last FROM publish_ledger"
            " WHERE blog_id = ? AND status = 'published'",
            (blog_id,),
        ).fetchone()
    finally:
        ledger.close()

    if row is None or not row["last"]:
        return None

    last = row["last"]
    try:
        dt = datetime.fromisoformat(last)
    except (ValueError, TypeError):
        return None

    # naive면 KST로 간주, tz-aware면 그대로 사용
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_KST)
    return dt


def _days_since(last_published: datetime | None) -> int | None:
    """KST 기준 '현재'와 마지막 발행 시각의 경과일 수 계산."""
    if last_published is None:
        return None
    now = datetime.now(_KST)
    return (now - last_published).days


@register_check("freshness")
def check_freshness(conn, blog_id: str) -> dict:
    """마지막 성공 발행 후 경과일 vs 계열 기준 검사.

    days는 캐시 컬럼이 아니라 publish_ledger 실데이터를 현재 시각 기준으로
    재계산한다. (fix: 기존 days_since_last_publish 캐시는 YAML sync 시점 값이라
    시간이 지나도 갱신되지 않아 stale을 과소/과대 판정함)
    """
    config_status = get_blog_config_status(conn, blog_id)
    if not config_status:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found in lifecycle"}

    brand = get_blog_brand(conn, blog_id)
    if not brand:
        return {"status": "unknown", "detail": f"Blog {blog_id} brand not found"}

    last_published = _parse_last_published(conn, blog_id)
    days = _days_since(last_published)
    _cached_days = get_blog_days_since_last_publish(conn, blog_id)

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
            "detail": "No publish data available (no published record in publish_ledger)",
            "evidence_url": "",
        }

    threshold = BRAND_THRESHOLDS.get(brand, 7)

    if days > threshold:
        return {
            "status": "fail",
            "detail": f"Stale: {days} days since last publish (threshold: {threshold}d for {brand}) [live, cached={_cached_days}]",
            "evidence_url": "",
        }

    return {
        "status": "pass",
        "detail": f"Last publish {days}d ago (threshold: {threshold}d for {brand}) [live, cached={_cached_days}]",
        "evidence_url": "",
    }
