"""ops_dashboard.checks.problem_checks — P14/P15/P21/P25/P31/P33/P11/P16/P28/P08 체크

각 P-code별 open 이벤트를 publish_error_events에서 조회하는 최소 체크 함수.
플레이북은 있으나 전용 @register_check가 없던 것들.
"""
from __future__ import annotations

import logging

from ops_dashboard.checks import register_check

logger = logging.getLogger(__name__)


def _make_check(problem_id: str, detail_label: str):
    """problem_id별 체크 함수 팩토리."""
    @register_check(f"p{problem_id.lower()}_{detail_label}")
    def check(conn, blog_id: str, _pid=problem_id, _label=detail_label):
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM publish_error_events "
                "WHERE blog_id = ? AND problem_id = ? AND state = 'open'",
                (blog_id, _pid),
            ).fetchone()
            count = row["cnt"] if row else 0
            if count > 0:
                return {
                    "status": "fail",
                    "open_count": count,
                    "detail": f"{_pid} {_label} {count}건 open",
                }
            return {"status": "pass", "open_count": 0, "detail": f"{_pid} open 이벤트 없음"}
        except Exception as e:
            logger.error("[%s] check error for %s: %s", _pid, blog_id, e)
            return {"status": "unknown", "detail": f"{_pid} check error: {e}"}
    return check


for _pid, _label in [
    ("P14", "collect_gate"),
    ("P15", "post_validate"),
    ("P21", "config_error"),
    ("P25", "scheduler_timeout"),
    ("P31", "telegram"),
    ("P33", "stalled"),
    ("P11", "title_regen"),
    ("P16", "dup_slug"),
    ("P28", "invalid_contract"),
    ("P08", "cot_leak"),
]:
    globals()[f"check_{_pid.lower()}_{_label}"] = _make_check(_pid, _label)
