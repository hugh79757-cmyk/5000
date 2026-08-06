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


def _get_normalization_target_ids(conn: sqlite3.Connection) -> set[str]:
    """정상화 대상 블로그 ID — active + 재개 예정(maintenance 대상).

    2026-08-06 (커밋 C 3단계): 준비도 지표 산정 대상을 active + 재개 예정
    블로그로 한정. 비활성(inactive/disabled)·발행기록 없는 블로그는 분모에서
    제외된다(ETAP 35개 등 AdSense 미사용/미발행 사이트가 준비도를 막지 않음).
    """
    rows = conn.execute("""
        SELECT blog_id FROM blog_lifecycle
        WHERE config_status = 'active'
           OR maintenance_status IN ('awaiting', 'in_progress')
    """).fetchall()
    return {r["blog_id"] for r in rows}


def _get_publish_log_conn() -> sqlite3.Connection:
    """publish_ledger DB 연결 (content.db)."""
    from ops_dashboard.db import get_publish_log_conn
    return get_publish_log_conn()


def compute_standard_compliance(conn: sqlite3.Connection) -> dict:
    """표준 준수율: standard_compliance 최신 결과 pass 비율 (정상화 대상 한정)."""
    target_ids = _get_normalization_target_ids(conn)
    if not target_ids:
        return {"pass_count": 0, "fail_count": 0, "unknown_count": 0,
                "total": 0, "ratio": 0.0, "green": False}

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

    # 정상화 대상 블로그별 최신 결과 매핑
    latest_by_blog = {r["blog_id"]: r["status"] for r in rows}
    pass_count = 0
    fail_count = 0
    unknown_count = 0
    for bid in sorted(target_ids):
        status = latest_by_blog.get(bid)
        if status == "pass":
            pass_count += 1
        elif status == "fail":
            fail_count += 1
        else:
            # 검사 결과 없음(미실행) 또는 unknown → unknown으로 집계
            unknown_count += 1

    total = len(target_ids)
    ratio = (pass_count / total * 100.0) if total > 0 else 0.0
    return {
        "pass_count": pass_count,
        "fail_count": fail_count,
        "unknown_count": unknown_count,
        "total": total,
        "ratio": round(ratio, 1),
        "green": total > 0 and ratio == 100.0 and fail_count == 0 and unknown_count == 0,
    }


def compute_stale_active_blogs(conn: sqlite3.Connection) -> dict:
    """stale(발행 정지) 블로그 수 — 정상화 대상(active + 재개 예정) 한정.

    blog_lifecycle.days_since_last_publish가 NULL(미집계)이므로,
    실제 데이터 소스인 publish_ledger(content.db)에서 마지막 성공 발행을 조회한다.
    발행 기록 자체가 없는 블로그는 stale로 치지 않고 별도 "관리 제외" 버킷으로 분리
    (2026-08-06, 커밋 C 3단계: techpawz/rotcha 계열 발행기록 없음 블로그가
    준비도를 막지 않도록).
    """
    # 정상화 대상 블로그 (active + 재개 예정)
    target_ids = _get_normalization_target_ids(conn)
    if not target_ids:
        return {"count": 0, "green": True, "stale_blogs": [], "excluded_no_history": []}

    # publish_ledger에서 블로그별 마지막 성공 발행 시각
    ledger = _get_publish_log_conn()
    now = datetime.now()
    stale_blogs = []
    no_history = []

    for bid in sorted(target_ids):
        row = ledger.execute(
            "SELECT MAX(created_at) AS last FROM publish_ledger"
            " WHERE blog_id = ? AND status = 'published'",
            (bid,),
        ).fetchone()
        last = row["last"] if row else None
        if last is None:
            # 발행 기록 없음 → stale로 치지 않고 별도 버킷
            no_history.append({"blog_id": bid, "days": None})
            continue
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
        "excluded_no_history": no_history,
    }


def compute_open_known_issues(conn: sqlite3.Connection) -> dict:
    """미해결 known_issue 수 — 정상화 대상 블로그 관련 이슈 한정.

    이슈의 blog_ids가 비어 있으면(구조 이슈 STRUCT 등) 전역 이슈로 간주해 항상
    집계하고, blog_ids가 있으면 정상화 대상 블로그와 교집합이 있는 경우에만
    집계한다 (비활성 블로그 전용 이슈는 준비도를 막지 않음).
    """
    target_ids = _get_normalization_target_ids(conn)
    rows = conn.execute(
        "SELECT issue_id, blog_ids FROM known_issues WHERE gsd_status = 'open'"
    ).fetchall()
    count = 0
    for r in rows:
        blog_ids = (r["blog_ids"] or "").strip()
        if not blog_ids:
            # 전역 구조 이슈 — 항상 집계
            count += 1
        elif any(bid in target_ids for bid in (b.strip() for b in blog_ids.split(",")) if bid):
            count += 1
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
