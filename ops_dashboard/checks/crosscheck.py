"""ops_dashboard.checks.crosscheck — known_issues ↔ check_results 교차검증

auto_detectable 이슈가 실제로 check에서 감지되는지 검증한다.
"""
from __future__ import annotations

import logging

from ops_dashboard.checks import register_check
from ops_dashboard.db import (
    get_blog_by_id,
    get_auto_detectable_issues_for_blog,
    get_fail_checks_for_blog,
)

logger = logging.getLogger(__name__)


@register_check("gsd_crosscheck")
def check_crosscheck(conn, blog_id: str) -> dict:
    """auto_detectable 이슈가 check_results에서 감지되는지 검증."""
    blog = get_blog_by_id(conn, blog_id)
    if not blog:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found in lifecycle"}

    # 이 블로그에 영향을 미치는 auto_detectable 이슈 조회
    issues = get_auto_detectable_issues_for_blog(conn, blog_id)

    if not issues:
        return {
            "status": "pass",
            "detail": "No auto-detectable open issues affecting this blog",
            "evidence_url": "",
        }

    undetected = []
    for issue in issues:
        issue_id = issue["issue_id"]
        # 해당 블로그의 최근 fail check가 있는지 확인
        fails = get_fail_checks_for_blog(conn, blog_id)

        # auto-detectable 이슈가 있지만 fail check가 없으면 미감지
        if not fails:
            undetected.append(f"{issue_id}: {issue['symptom'][:60]}")

    if undetected:
        return {
            "status": "fail",
            "detail": f"{len(undetected)}/{len(issues)} auto-detectable issues not detected by checks: " +
                      "; ".join(undetected[:3]),
            "evidence_url": "",
        }

    return {
        "status": "pass",
        "detail": f"All {len(issues)} auto-detectable issues have corresponding check failures",
        "evidence_url": "",
    }
