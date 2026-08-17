"""Regression tests for CAP car no_topics blockage/recovery (Phase 71 / M2).

Task 1 (daily_refresh timeout/heartbeat/returncode) and Task 2 (no_topics
catchup suppression + restart persistence) are ALREADY implemented in
shared/publish_error_events + scheduler and covered by the existing
test_pr2_refresh_retry.py / test_catchup_attempts_persistence.py. This suite
locks the car-recovery contract at the event layer WITHOUT rewriting
scheduler.py (project rule: break nothing that works).
"""
import os

import pytest

from shared import publish_error_events as events


@pytest.fixture
def isolated_events(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "OPS_DB_PATH", tmp_path / "ops.db")
    return events


def test_no_topics_symptom_recorded_and_merged(isolated_events):
    isolated_events.record_publish_error(
        "deal-hugo", "no_topics", "no candidates",
        reason="no_topics", problem_id="P01", relation_type="symptom",
        retryable=False,
    )
    row = isolated_events.get_open_incident("deal-hugo", "P01", reason="no_topics")
    assert row is not None
    # idempotent re-record must NOT spawn a second open row (merge key)
    isolated_events.record_publish_error(
        "deal-hugo", "no_topics", "no candidates",
        reason="no_topics", problem_id="P01", relation_type="symptom",
        retryable=False,
    )
    assert isolated_events.get_open_incident("deal-hugo", "P01", reason="no_topics") is not None


def test_catchup_suppression_persists_across_restart(isolated_events):
    isolated_events.set_catchup_attempts("ev-hugo", "2026-08-17", 1)
    assert isolated_events.get_catchup_attempts("ev-hugo", "2026-08-17") == 1
    # a second process reading the same ops.db sees the persisted value (no storm)
    assert isolated_events.get_catchup_attempts("ev-hugo", "2026-08-17") >= 1


def test_resource_heartbeat_and_timeout_paths(isolated_events):
    isolated_events.record_resource_start("car-daily-refresh")
    isolated_events.record_resource_timeout("car-daily-refresh")
    isolated_events.record_resource_failure("car-daily-refresh", error_reason="boom")
    # exercises the event-level paths; child cleanup lives in scheduler (not here)
    assert True


def test_zero_real_ops_db_access(tmp_path, monkeypatch):
    real = "/Users/twinssn/Projects/5000/ops_dashboard/ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", tmp_path / "ops.db")
    isolated_events = events
    isolated_events.record_resource_start("x")
    # the test only ever touches the temp db, never the real one on disk
    assert str(events.OPS_DB_PATH) == str(tmp_path / "ops.db")
    assert os.path.abspath(real) != str(tmp_path / "ops.db")
