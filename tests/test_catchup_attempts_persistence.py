"""PR5: catchup attempt 영속화 테스트 — ops.db SSOT 기반, 재시작 후에도 유지."""

from shared import publish_error_events as events


def test_get_missing_returns_zero(tmp_path, monkeypatch):
    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    assert events.get_catchup_attempts("b1", "2026-08-17") == 0


def test_set_then_get_persists(tmp_path, monkeypatch):
    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    events.set_catchup_attempts("b1", "2026-08-17", 1)
    events.set_catchup_attempts("b1", "2026-08-17", 2)
    assert events.get_catchup_attempts("b1", "2026-08-17") == 2


def test_new_date_resets_window(tmp_path, monkeypatch):
    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    events.set_catchup_attempts("b1", "2026-08-17", 3)
    assert events.get_catchup_attempts("b1", "2026-08-18") == 0


def test_reconnect_keeps_value(tmp_path, monkeypatch):
    """재시작 시뮬레이션: 새 연결(새 함수 호출)로 다시 읽어도 값 유지."""
    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    events.set_catchup_attempts("b1", "2026-08-17", 3)
    assert events.get_catchup_attempts("b1", "2026-08-17") == 3