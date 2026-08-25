"""PIPELINE_FAILURE_HEALTH — P02/P03/P14 실패 감시

데이터 소스: ops_dashboard/ops.db → publish_error_events
  (컬럼: blog_id, problem_id(P02/P03/P14), stage, reason, state(open/closed),
   occurred_at, created_at)

초기 설계안은 scheduler.log 파싱이었으나, 실제 scheduler.log는:
  - 'Blog:' 프리픽스가 없어 blog 추출 실패 → silently PASS 버그
  - fitness/kitchen P03/P14 이벤트가 아예 기록되지 않음 (silent gap)
따라 canonical 구조화 저장소인 publish_error_events를 사용한다.
(state='open' = 현재 진행 중인 실패; 대시보드 가시화 목적에 부합)
"""
import sqlite3, os
from datetime import datetime, timedelta

DB_PATH = os.path.expanduser("~/Projects/5000/ops_dashboard/ops.db")
TARGET_PROBLEMS = ("P02", "P03", "P14")


def parse_recent_failures(hours=24):
    """현재 열린(open) P02/P03/P14 이벤트 + 최근 N시간 내 발생 이벤트를 blog별 집계.
    open 이벤트는 발생 시점과 무관하게 open 상태이므로(=아직 미해결 실패)
    반드시 포함한다 — 24h 컷만 걸면 아직 고장 난 블로그가 silently 누락됨.
    """
    results = []
    if not os.path.exists(DB_PATH):
        return results
    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT blog_id, problem_id, COUNT(*)
           FROM publish_error_events
           WHERE problem_id IN (?,?,?)
             AND resolved_at IS NULL
             AND (state = 'open' OR created_at >= ?)
             AND blog_id LIKE '%-hugo'
           GROUP BY blog_id, problem_id""",
        (TARGET_PROBLEMS + (cutoff,)),
    ).fetchall()
    conn.close()

    blog_problems = {}
    for blog_id, problem_id, cnt in rows:
        blog_problems.setdefault(blog_id, {})[problem_id] = cnt

    for blog_id, problems in blog_problems.items():
        total = sum(problems.values())
        detail = ", ".join(f"{k}={v}" for k, v in problems.items())
        status = "critical" if total >= 3 else "warning"
        results.append({
            "check_name": "PIPELINE_FAILURE_HEALTH",
            "blog_id": blog_id,
            "result": status,
            "detail": detail,
        })
    return results


def run_check():
    return parse_recent_failures(hours=24)


if __name__ == "__main__":
    results = run_check()
    if not results:
        print("PASS     (no open P02/P03/P14 events in last 24h)")
    for r in results:
        print(f"{r['result'].upper():8s} {r['blog_id']:30s} {r['detail']}")
