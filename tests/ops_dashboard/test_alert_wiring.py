"""배선 단위 테스트: _run_recheck_all 신규 FAIL → 텔레그램 [OPS ALERT] (옵션 A).

검증 대상 [PRODUCTION CODE]:
- scheduler._snapshot_check_fails  — check_results fail (blog_id, check_name) 스냅샷
- scheduler._alert_new_check_fails — 직전 스냅샷 대비 신규 FAIL 만 send_dashboard_alert 1회

케이스:
  (a) 신규 FAIL 발생 → send_dashboard_alert 1회 호출 (mock)
  (b) FAIL 없음       → 알림 0회
  (c) 지속 FAIL(직전에도 있었던 것) → 알림 0회
  (d) 디바운스: 같은 날 이미 fleet 알림을 보냄 → 신규 FAIL 이어도 0회

주의: 테스트는 tempfile DB + init_db 사용 — 프로덕션 ops.db 에 기록하지 않음.
scheduler 모듈 임포트의 부수효과(_check_dependencies, logging FileHandler)는
실행 중인 launchd 서비스와 동일 환경(venv)에서 검증되어 안전.
"""
import tempfile
from unittest import mock

import pytest

from ops_dashboard.db import get_conn, init_db, record_check
from scheduler import _alert_new_check_fails, _snapshot_check_fails


@pytest.fixture
def ops_conn():
    fd, path = tempfile.mkstemp(suffix=".db")
    conn = get_conn(path)
    init_db(conn)
    yield conn
    conn.close()


def _seed_fail(conn, blog_id="b1", check_name="M01"):
    record_check(conn, blog_id, check_name, "fail", "test detail")


def test_new_fail_triggers_single_alert(ops_conn):
    """(a) 신규 FAIL 발생 → send_dashboard_alert 1회 호출."""
    _seed_fail(ops_conn)
    before = set()  # 직전 스냅샷에는 없었음 = 신규 FAIL
    with mock.patch("shared.telegram_notifier.send_dashboard_alert") as mock_alert:
        _alert_new_check_fails(ops_conn, before)
    assert mock_alert.call_count == 1
    kwargs = mock_alert.call_args
    assert kwargs.args[0] == "fleet"
    assert "b1" in kwargs.args[3] and "M01" in kwargs.args[3]


def test_no_fail_no_alert(ops_conn):
    """(b) FAIL 없음 → 알림 0회."""
    with mock.patch("shared.telegram_notifier.send_dashboard_alert") as mock_alert:
        _alert_new_check_fails(ops_conn, set())
    mock_alert.assert_not_called()


def test_ongoing_fail_no_alert(ops_conn):
    """(c) 지속 FAIL(직전에도 있었던 것) → 알림 0회."""
    _seed_fail(ops_conn)
    before = _snapshot_check_fails(ops_conn)  # 직전에도 동일 fail 존재
    assert before == {("b1", "M01")}
    with mock.patch("shared.telegram_notifier.send_dashboard_alert") as mock_alert:
        _alert_new_check_fails(ops_conn, before)
    mock_alert.assert_not_called()


def test_debounce_suppresses_same_day_alert(ops_conn):
    """(d) 디바운스: 같은 날 이미 fleet 알림을 보냄 → 신규 FAIL 이어도 0회."""
    _seed_fail(ops_conn)
    with mock.patch("shared.notification_debounce.should_push", return_value=False):
        with mock.patch("shared.telegram_notifier.send_dashboard_alert") as mock_alert:
            _alert_new_check_fails(ops_conn, set())
    mock_alert.assert_not_called()
