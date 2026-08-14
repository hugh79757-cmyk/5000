"""Phase 71 (SC-4 카나리) — 신호 정합성 버그 2건 회귀 테스트.

작업 1:
  Bug A (db.py): _RULE_ID_RE = \\bR\\d{2}\\b 가 THUMBNAIL-01/R2-01 같은 비 R\\d\\d 규칙을
    놓쳐, R-규칙 동반 실패 시 비 R\\d\\d 규칙이 거짓 pass(또는 unknown)로 표시됐다.
    수정: ① _rule_entry 가 개별 DB 행(ground truth) status를 aggregate 파싱보다
    우선 신뢰, ② _RULE_ID_RE 일반화(숫자포함 + '(' 직전 토큰).

  Bug B (standard.py): full-pass 조기 반환("if not failures: return")이
    _scrub_passed_rules 보다 앞서 실행돼, full-pass 전환 시 stale fail 행이
    남아 phantom(fail)이 됐다. 수정: scrub 를 조기 반환 앞으로 이동.

각 테스트는 카나리 외 블로그에 불침투하며, ops.db 를 건드리지 않고
인메모리 DB 로 격리 검증한다.
"""
import sqlite3

import pytest

from ops_dashboard import db


def _make_conn() -> sqlite3.Connection:
    """init_db 로 실제 스키마를 만든 인메모리 커넥션 (triage_classifications 보완)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    # triage_classifications 는 init_db 미포함 — get_registry_view 의 error loop 용으로 생성
    conn.execute("""
        CREATE TABLE IF NOT EXISTS triage_classifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT DEFAULT '',
            problem_id TEXT NOT NULL,
            severity TEXT DEFAULT '',
            target TEXT DEFAULT '',
            action TEXT DEFAULT '',
            source TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            classification TEXT DEFAULT '',
            classified_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def _insert_blog(conn, blog_id="test-hugo", status="active", site_path="/tmp/__nosuch__"):
    conn.execute("""
        INSERT INTO blog_lifecycle
        (blog_id, brand, config_status, maintenance_status, site_path)
        VALUES (?, 'cap', ?, 'none', ?)
    """, (blog_id, status, site_path))
    conn.commit()


def _insert_check(conn, check_name, status, detail="", rule_id="", blog_id="test-hugo"):
    conn.execute("""
        INSERT INTO check_results (blog_id, check_name, status, detail, rule_id, checked_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, (blog_id, check_name, status, detail, rule_id))


# ---------------------------------------------------------------------------
# Bug A — get_registry_view
# ---------------------------------------------------------------------------

def test_bugA_thumbnail_ground_truth_beats_aggregate():
    """THUMBNAIL-01 fail 개별 행이 있으면, aggregate 상세에 R-규칙만 보여도 fail.

    구정규식은 THUMBNAIL-01 을 놓쳐 aggregate 경로가 이 규칙을 pass 로 오판했지만,
    개별 DB 행(ground truth) 우선 신뢰로 fail 이 유지돼야 한다.
    """
    conn = _make_conn()
    # aggregate fail — 상세에 R08 과 THUMBNAIL-01 둘 다 명시 (구정규식은 R08 만 인식)
    _insert_check(conn, "standard_compliance", "fail",
                  detail="2/2 rules failed: R08(MAJOR): x; THUMBNAIL-01(MAJOR): thumb")
    # 두 규칙 모두 개별 fail 행 (ground truth)
    _insert_check(conn, "R08", "fail", detail="R08 fail", rule_id="R08")
    _insert_check(conn, "THUMBNAIL-01", "fail", detail="thumb fail", rule_id="THUMBNAIL-01")
    conn.commit()

    reg = db.get_registry_view(conn, blog_id="test-hugo")
    by_id = {r["rule_id"]: r for r in reg["rules"] if r["rule_id"]}

    assert by_id["R08"]["status"] == "fail"
    # Bug A 핵심: ground truth(개별 fail 행)가 aggregate 파싱 오판을 이겨야 함
    assert by_id["THUMBNAIL-01"]["status"] == "fail"


def test_bugA_regex_captures_thumbnail_in_aggregate_fallback():
    """개별 행이 없는 규칙(비활성 블로그 폴백 경로)에서도 THUMBNAIL-01 이 fail.

    get_registry_view 는 개별 행 없이 aggregate 상세만 있을 때 _determine_rule_status_
    from_aggregate 로 판정한다. 일반화된 파서는 THUMBNAIL-01 을 인식해 fail 을 반환해야
    한다 (구정규식은 놓쳐 unknown/None 폴백).
    """
    conn = _make_conn()
    # 개별 행 없음 — aggregate 상세에 THUMBNAIL-01 만 명시
    _insert_check(conn, "standard_compliance", "fail",
                  detail="1/2 rules failed: THUMBNAIL-01(MAJOR): thumb broken")
    conn.commit()

    reg = db.get_registry_view(conn, blog_id="test-hugo")
    th = next(r for r in reg["rules"] if r["rule_id"] == "THUMBNAIL-01")
    assert th["status"] == "fail"


def test_bugA_regex_parses_r2_01():
    """R2-01 도 구정규식(R+2자리)으로 놓치는 케이스 — 일반화 파서로 fail 인식."""
    conn = _make_conn()
    _insert_check(conn, "standard_compliance", "fail",
                  detail="1/2 rules failed: R2-01(MAJOR): images not on R2")
    conn.commit()
    reg = db.get_registry_view(conn, blog_id="test-hugo")
    r2 = next(r for r in reg["rules"] if r["rule_id"] == "R2-01")
    assert r2["status"] == "fail"


# ---------------------------------------------------------------------------
# Bug B — full-pass scrub
# ---------------------------------------------------------------------------

def test_bugB_full_pass_scrubs_stale_fail_rows(tmp_path, monkeypatch):
    """full-pass 전환 시 stale 개별 fail 행이 scrub 된다 (phantom 제거).

    모든 규칙이 pass 하면('if not failures') scrub 가 조기 반환보다 앞서 실행되어,
    이전에 fail 이었던 R04 의 stale 개별 행이 삭제되어야 한다.
    """
    from ops_dashboard.checks import standard

    conn = _make_conn()
    site = tmp_path / "site"
    site.mkdir(parents=True)
    _insert_blog(conn, site_path=str(site))

    # 모든 규칙을 pass 로 강제 (full-pass 경로 유도)
    monkeypatch.setattr(standard, "_resolve_check_fn",
                        lambda check_fn: (lambda s: (True, "ok")))

    # R04 stale fail 행 주입 (이전 실행에서 fail 이었으나 지금은 pass 인 상황)
    _insert_check(conn, "R04", "fail", detail="old stale", rule_id="R04")
    conn.commit()

    result = standard.check_standard_compliance(conn, "test-hugo")
    assert result["status"] == "pass"

    cnt = conn.execute(
        "SELECT COUNT(*) FROM check_results "
        "WHERE blog_id='test-hugo' AND check_name='R04' AND status='fail'"
    ).fetchone()[0]
    assert cnt == 0, "full-pass 에서도 stale fail 행이 남아 phantom 이 되어선 안 됨"


def test_bugB_fail_path_still_records_failures(tmp_path, monkeypatch):
    """fail 경로에서는 실패 규칙 개별 행이 정상 기록돼야 한다 (회귀 방지).

    scrub 를 조기 반환 앞으로 옮긴 뒤에도, 실제 fail 규칙의 개별 행은
    _record_failed_rules 로 기록되어야 한다.
    """
    from ops_dashboard.checks import standard

    conn = _make_conn()
    site = tmp_path / "site"
    site.mkdir(parents=True)
    _insert_blog(conn, site_path=str(site))

    real_rules = {}

    def fake_resolve(check_fn_name):
        # R08 만 fail, 나머지 pass
        def check_fn(site):
            return (False, "R08 violates") if check_fn_name == "_check_r08" else (True, "ok")
        return check_fn

    monkeypatch.setattr(standard, "_resolve_check_fn", fake_resolve)

    result = standard.check_standard_compliance(conn, "test-hugo")
    assert result["status"] == "fail"

    # R08 개별 fail 행이 기록됐는지
    cnt = conn.execute(
        "SELECT COUNT(*) FROM check_results "
        "WHERE blog_id='test-hugo' AND check_name='R08' AND status='fail'"
    ).fetchone()[0]
    assert cnt == 1, "fail 규칙의 개별 행이 기록되어야 함"
