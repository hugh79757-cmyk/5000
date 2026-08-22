"""Tests for run_harvest CLI: window gate, harvest call, HARD_STOP exit code. Mock only."""

import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from pipelines.curation import run_harvest

KST = timezone(timedelta(hours=9))


@pytest.fixture(autouse=True)
def _quiet_log(tmp_path, monkeypatch):
    monkeypatch.setattr(run_harvest, "LOG_DIR", str(tmp_path))
    # keyword_pool 저장이 운영 curation.db에 쓰지 않게 격리
    monkeypatch.setattr(run_harvest, "_pool_db", lambda: str(tmp_path / "curation.db"))


def test_outside_window_exits_0_with_skip(capsys):
    # 12:00 KST — outside 02:00-06:00
    noon = datetime(2026, 8, 23, 12, 0, tzinfo=KST)
    with patch.object(run_harvest, "in_harvest_window", return_value=False):
        rc = run_harvest.main()
    assert rc == 0
    assert "[SKIP] Outside harvest window" in capsys.readouterr().out


def test_in_window_calls_harvester_and_returns_0():
    fake = type("H", (), {})()
    fake.guard = type("G", (), {"is_stopped": False})()
    fake.harvest = lambda max_new=20: ["신규키워드"]
    with patch.object(run_harvest, "in_harvest_window", return_value=True), \
         patch("pipelines.curation.keyword_harvester.KeywordHarvester",
               return_value=fake) as mock_h:
        rc = run_harvest.main()
    assert rc == 0
    assert mock_h.called


def test_hard_stop_returns_1():
    fake = type("H", (), {})()
    fake.guard = type("G", (), {"is_stopped": True})()
    fake.harvest = lambda max_new=20: []
    with patch.object(run_harvest, "in_harvest_window", return_value=True), \
         patch("pipelines.curation.keyword_harvester.KeywordHarvester",
               return_value=fake):
        rc = run_harvest.main()
    assert rc == 1


def test_window_boundary_logic():
    inside = datetime(2026, 8, 23, 2, 30, tzinfo=KST)
    outside_early = datetime(2026, 8, 23, 1, 59, tzinfo=KST)
    outside_late = datetime(2026, 8, 23, 6, 0, tzinfo=KST)
    assert run_harvest.in_harvest_window(inside)
    assert not run_harvest.in_harvest_window(outside_early)
    assert not run_harvest.in_harvest_window(outside_late)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
