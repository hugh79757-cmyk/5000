"""ops_dashboard.readiness — 확장 준비도 지표 계산

세 지표가 모두 녹색일 때만 확장 허용:
  1. 표준 준수율 100% (standard_compliance 최신 결과 pass 비율)
  2. stale(발행 정지) active 블로그 수 = 0 (publish_ledger 실데이터 기준)
  3. 미해결 known_issue 수 = 0

모두 충족 → 확장 허용, 하나라도 불충족 → 확장 금지.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

STALE_THRESHOLD_DAYS = 3  # 발행 정지 기준 (마지막 발행 이후 경과일)


def _get_publish_log_conn() -> sqlite3.Connection:
    """publish_ledger DB 연결 (content.db)."""
    from ops_dashboard.db import get_publish_log_conn
    return get_publish_log_conn()


def compute_standard_compliance(conn: sqlite3.Connection) -> dict:
    """표준 준수율: standard_compliance 최신 결과 pass 비율."""
    rows = conn.execute("""
        SELECT cr.blog_id, cr.status
        FROM check_results cr
        INNER JOIN (
            SELECT blog_id, check_name, MAX(checked_at) as latest
            FROM check_results WHERE check_name = 'standard_compliance'
            GROUP BY blog_id, check_name
        ) latest ON cr.blog_id = latest.blog_id
            AND cr.check_name = latest.check_name
            AND cr.checked_at = latest.latest
    """).fetchall()

    total = len(rows)
    pass_count = sum(1 for r in rows if r["status"] == "pass")
    fail_count = sum(1 for r in rows if r["status"] == "fail")
    unknown_count = total - pass_count - fail_count

    ratio = (pass_count / total * 100.0) if total > 0 else 0.0
    return {
        "pass_count": pass_count,
        "fail_count": fail_count,
        "unknown_count": unknown_count,
        "total": total,
        "ratio": round(ratio, 1),
        "green": total > 0 and ratio == 100.0 and fail_count == 0,
    }


def compute_stale_active_blogs(conn: sqlite3.Connection) -> dict:
    """stale active 블로그 수.

    blog_lifecycle.days_since_last_publish가 NULL(미집계)이므로,
    실제 데이터 소스인 publish_ledger(content.db)에서 마지막 성공 발행을 조회한다.
    """
    # active 블로그 목록 (ops.db)
    active_blogs = conn.execute(
        "SELECT blog_id FROM blog_lifecycle WHERE config_status = 'active'"
    ).fetchall()
    active_ids = {r["blog_id"] for r in active_blogs}

    if not active_ids:
        return {"count": 0, "green": True, "stale_blogs": []}

    # publish_ledger에서 블로그별 마지막 성공 발행 시각
    ledger = _get_publish_log_conn()
    now = datetime.now()
    stale_blogs = []

    for bid in active_ids:
        row = ledger.execute(
            "SELECT MAX(created_at) AS last FROM publish_ledger"
            " WHERE blog_id = ? AND status = 'published'",
            (bid,),
        ).fetchone()
        last = row["last"] if row else None
        if last is None:
            # 발행 기록 자체 없음 → 발행 정지로 간주
            stale_blogs.append({"blog_id": bid, "days": None})
        else:
            try:
                last_dt = datetime.fromisoformat(last)
            except (ValueError, TypeError):
                stale_blogs.append({"blog_id": bid, "days": None})
                continue
            days = (now - last_dt).days
            if days > STALE_THRESHOLD_DAYS:
                stale_blogs.append({"blog_id": bid, "days": days})

    ledger.close()

    return {
        "count": len(stale_blogs),
        "green": len(stale_blogs) == 0,
        "stale_blogs": stale_blogs,
    }


def compute_open_known_issues(conn: sqlite3.Connection) -> dict:
    """미해결 known_issue 수."""
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM known_issues WHERE gsd_status = 'open'"
    ).fetchone()
    count = row["cnt"]
    return {"count": count, "green": count == 0}


def compute_readiness(conn: sqlite3.Connection) -> dict:
    """확장 준비도 전체 계산."""
    compliance = compute_standard_compliance(conn)
    stale = compute_stale_active_blogs(conn)
    issues = compute_open_known_issues(conn)

    metrics = {
        "standard_compliance": compliance,
        "stale_active_blogs": stale,
        "open_known_issues": issues,
    }

    all_green = all(m["green"] for m in metrics.values())
    return {
        "ready": all_green,
        "status": "ready" if all_green else "blocked",
        "metrics": metrics,
        "computed_at": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    from ops_dashboard.db import get_conn, init_db
    conn = get_conn()
    init_db(conn)
    result = compute_readiness(conn)
    m = result["metrics"]
    print("확장 준비도:", "🟢 확장 허용" if result["ready"] else "🔴 확장 금지")
    print(f"  표준 준수율: {m['standard_compliance']['ratio']}% "
          f"(pass {m['standard_compliance']['pass_count']}/{m['standard_compliance']['total']}, "
          f"fail {m['standard_compliance']['fail_count']})")
    print(f"  stale active: {m['stale_active_blogs']['count']}개 "
          f"({', '.join(s['blog_id'] for s in m['stale_active_blogs']['stale_blogs'][:3])}...)" if
          m['stale_active_blogs']['count'] else "  stale active: 0개")
    print(f"  미해결 known_issue: {m['open_known_issues']['count']}개")
