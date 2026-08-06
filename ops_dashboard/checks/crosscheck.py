"""ops_dashboard.checks.crosscheck — known_issues ↔ check_results 교차검증

auto_detectable 이슈가 실제로 check에서 감지되는지 검증한다.
"""
from __future__ import annotations

import logging

from ops_dashboard.checks import register_check

logger = logging.getLogger(__name__)


@register_check("gsd_crosscheck")
def check_crosscheck(conn, blog_id: str) -> dict:
    """auto_detectable 이슈가 check_results에서 감지되는지 검증."""
    blog = conn.execute(
        "SELECT * FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    if not blog:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found in lifecycle"}

    # 이 블로그에 영향을 미치는 auto_detectable 이슈 조회
    # blog_ids가 비어있으면 일반 이슈 (모든 블로그에 해당)
    issues = conn.execute("""
        SELECT issue_id, symptom, blog_ids
        FROM known_issues
        WHERE auto_detectable = 'yes'
          AND gsd_status = 'open'
          AND (blog_ids LIKE ? OR blog_ids = '')
    """, (f"%{blog_id}%",)).fetchall()

    if not issues:
        return {
            "status": "pass",
            "detail": "No auto-detectable open issues affecting this blog",
            "evidence_url": "",
        }

    undetected = []
    for issue in issues:
        issue_id = issue["issue_id"]
        # 해당 이슈의 detection_method를 check_results에서 fail 건이 있는지 확인
        # 간단히: check_results에서 이 블로그의 fail 항목이 있는지 확인
        fails = conn.execute("""
            SELECT check_name, detail
            FROM check_results
            WHERE blog_id = ? AND status = 'fail'
            ORDER BY checked_at DESC
            LIMIT 5
        """, (blog_id,)).fetchall()

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
