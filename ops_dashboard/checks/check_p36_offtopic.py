"""ops_dashboard.checks.check_p36_offtopic — P36 오프토픽 차단 체크

publish_error_events에서 P36 open 이벤트가 있는지 조회.
"""
from __future__ import annotations

import logging

from ops_dashboard.checks import register_check

logger = logging.getLogger(__name__)


@register_check("p36_offtopic")
def check_p36_offtopic(conn, blog_id: str) -> dict:
    """P36 오프토픽 차단 이벤트가 열려 있는지 확인."""
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM publish_error_events "
            "WHERE blog_id = ? AND problem_id = 'P36' AND state = 'open'",
            (blog_id,),
        ).fetchone()
        count = row["cnt"] if row else 0
        if count > 0:
            return {
                "status": "fail",
                "open_count": count,
                "detail": f"P36 오프토픽 차단 {count}건 open",
            }
        return {"status": "pass", "open_count": 0, "detail": "P36 open 이벤트 없음"}
    except Exception as e:
        logger.error(f"[P36] check error for {blog_id}: {e}")
        return {"status": "unknown", "detail": f"P36 check error: {e}"}
