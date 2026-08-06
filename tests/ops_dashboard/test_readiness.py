"""Tests for ops_dashboard.readiness — 확장 준비도 지표 (정상화 대상 한정)."""
import sqlite3
from unittest.mock import patch


def _make_conn():
    """In-memory ops.db with the tables readiness.py depends on."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE blog_lifecycle (
            blog_id TEXT PRIMARY KEY,
            brand TEXT NOT NULL,
            config_status TEXT NOT NULL DEFAULT 'inactive',
            maintenance_status TEXT NOT NULL DEFAULT 'none',
            resume_ready INTEGER NOT NULL DEFAULT 0,
            site_path TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE check_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            check_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unknown',
            detail TEXT DEFAULT '',
            evidence_url TEXT DEFAULT '',
            checked_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE known_issues (
            issue_id TEXT PRIMARY KEY,
            blog_ids TEXT DEFAULT '',
            category TEXT NOT NULL,
            symptom TEXT NOT NULL,
            recorded_date TEXT NOT NULL,
            gsd_status TEXT NOT NULL DEFAULT 'open',
            auto_detectable TEXT NOT NULL DEFAULT 'no',
            detection_method TEXT DEFAULT '',
            resolution_status TEXT NOT NULL DEFAULT 'open',
            current_detection TEXT NOT NULL DEFAULT 'na',
            notes TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    return conn


def _seed_lifecycle(conn):
    """active 2 + 재개 예정(paused-awaiting) 1 + 비활성 2."""
    rows = [
        ("alpha-hugo", "active", "none", 0),
        ("beta-hugo", "active", "none", 0),
        ("gamma-hugo", "paused", "awaiting", 0),   # 재개 예정 → 대상
        ("delta-hugo", "inactive", "none", 0),      # 비활성 → 대상 아님
        ("eps-hugo", "disabled", "none", 0),        # 비활성 → 대상 아님
    ]
    for bid, cfg, maint, resume in rows:
        conn.execute(
            "INSERT INTO blog_lifecycle (blog_id, brand, config_status,"
            " maintenance_status, resume_ready) VALUES (?, 'test', ?, ?, ?)",
            (bid, cfg, maint, resume),
        )
    conn.commit()


def test_normalization_target_ids_active_and_resume():
    conn = _make_conn()
    _seed_lifecycle(conn)
    from ops_dashboard.readiness import _get_normalization_target_ids

    targets = _get_normalization_target_ids(conn)
    assert targets == {"alpha-hugo", "beta-hugo", "gamma-hugo"}
    conn.close()


def test_standard_compliance_limited_to_targets():
    conn = _make_conn()
    _seed_lifecycle(conn)
    # check_results: 대상 블로그 2개 pass, 비활성 블로그 1개 fail
    for bid, status in [("alpha-hugo", "pass"), ("beta-hugo", "pass"),
                        ("delta-hugo", "fail")]:
        conn.execute(
            "INSERT INTO check_results (blog_id, check_name, status, checked_at)"
            " VALUES (?, 'standard_compliance', ?, datetime('now'))",
            (bid, status),
        )
    conn.commit()

    from ops_dashboard.readiness import compute_standard_compliance
    result = compute_standard_compliance(conn)

    # 대상 3개(alpha, beta, gamma) 중 gamma는 결과 없음 → unknown
    assert result["total"] == 3
    assert result["pass_count"] == 2
    assert result["fail_count"] == 0
    assert result["unknown_count"] == 1
    # delta(비활성) fail이 분모에 포함되지 않았음을 확인
    assert result["ratio"] == round(2 / 3 * 100, 1)
    conn.close()


def test_stale_excludes_no_history_blogs():
    conn = _make_conn()
    _seed_lifecycle(conn)

    from ops_dashboard.readiness import compute_stale_active_blogs

    # publish_ledger mock: alpha만 발행 기록(오래됨), beta는 최근, gamma~eps는 기록 없음
    class FakeLedger:
        def __init__(self):
            self.rows = {
                "alpha-hugo": "2026-07-01T00:00:00",
                "beta-hugo": "2026-08-05T00:00:00",
            }

        def execute(self, sql, params):
            bid = params[0]
            last_val = self.rows.get(bid)

            class Cursor:
                def fetchone(self):
                    return {"last": last_val}
            return Cursor()

        def close(self):
            pass

    with patch("ops_dashboard.readiness._get_publish_log_conn", return_value=FakeLedger()):
        result = compute_stale_active_blogs(conn)

    # alpha만 stale(경과 > 3일), beta는 최근 발행 → 정상
    stale_ids = [s["blog_id"] for s in result["stale_blogs"]]
    assert stale_ids == ["alpha-hugo"]
    assert result["count"] == 1
    # 발행기록 없는 gamma(대상)는 stale가 아닌 관리 제외 버킷으로 분리
    no_hist = [s["blog_id"] for s in result["excluded_no_history"]]
    assert no_hist == ["gamma-hugo"]
    # delta/eps는 대상 자체가 아님 → 버킷에 없음
    assert "delta-hugo" not in no_hist and "eps-hugo" not in no_hist
    conn.close()


def test_open_issues_limited_to_targets():
    conn = _make_conn()
    _seed_lifecycle(conn)
    from ops_dashboard.readiness import compute_open_known_issues

    rows = [
        ("ISSUE-1", "", "구조 이슈 — 전역"),                    # 전역 → 항상 집계
        ("ISSUE-2", "alpha-hugo", "대상 블로그 이슈"),          # 대상 → 집계
        ("ISSUE-3", "delta-hugo", "비활성 블로그 전용 이슈"),    # 비활성 → 제외
        ("ISSUE-4", "gamma-hugo,delta-hugo", "대상+비활성 혼합"),  # 교집합 있음 → 집계
    ]
    for iid, blog_ids, cat in rows:
        conn.execute(
            "INSERT INTO known_issues (issue_id, blog_ids, category, symptom,"
            " recorded_date, gsd_status) VALUES (?, ?, ?, ?, date('now'), 'open')",
            (iid, blog_ids, cat, cat),
        )
    conn.commit()

    result = compute_open_known_issues(conn)
    assert result["count"] == 3  # ISSUE-1, ISSUE-2, ISSUE-4
    conn.close()
