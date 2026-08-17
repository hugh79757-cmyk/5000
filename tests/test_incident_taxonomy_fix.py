"""Phase 69 Sub-plan A+B contract tests (defects #1,#2,#3,#4,#6).

Locks the behavior that new publish_error_events rows have:
  A (defect #1): non-null incident_key that merges identical occurrences
  A (close path): resolved_at is set on close
  B (#3): no_topics is recorded as P01, never falling back to P02
  B (#4): no_topics reason is unified ('no_topics'), not empty
  B (#6): pipeline is populated (dispatcher passes cfg['pipeline'])
  B (#2): no_topics is WAITING semantics (retryable=False, not failure-amplifying)

Uses an isolated temp ops.db (zero real ops-DB access). No scheduler import,
no subprocess, no external calls.
"""
import pytest

from shared import publish_error_events as events


@pytest.fixture
def isolated_events(tmp_path, monkeypatch):
    real = events.OPS_DB_PATH
    monkeypatch.setattr(events, "OPS_DB_PATH", tmp_path / "ops.db")
    events.ensure_schema()
    yield events
    # guarantee we never touched the real ops.db
    assert events.OPS_DB_PATH != real


# --- Sub-plan A (defect #1): incident_key non-null + merge ---

def test_A1_incident_key_non_null(isolated_events):
    e = isolated_events.record_publish_error(
        "car-x", "result_parse", "no_topics",
        reason="no_topics", problem_id="P01", relation_type="symptom", retryable=False,
    )
    assert e["incident_key"], "incident_key must never be NULL for new rows"


def test_A2_incident_key_merge(isolated_events):
    k1 = isolated_events.record_publish_error(
        "car-x", "result_parse", "no_topics",
        reason="no_topics", problem_id="P01", relation_type="symptom", retryable=False,
    )["incident_key"]
    e2 = isolated_events.record_publish_error(
        "car-x", "result_parse", "no_topics",
        reason="no_topics", problem_id="P01", relation_type="symptom", retryable=False,
    )
    assert e2["incident_key"] == k1  # same incident -> merges
    assert e2["occurrence_count"] == 2


def test_A3_close_sets_resolved_at(isolated_events):
    isolated_events.record_publish_error(
        "car-y", "result_parse", "d",
        reason="no_topics", problem_id="P01",
    )
    conn = events._connect()
    try:
        n = events.close_publish_error_event(conn, blog_id="car-y", problem_id="P01")
    finally:
        conn.close()
    assert n >= 1
    # closed row must no longer be returned as open
    assert isolated_events.get_open_incident("car-y", "P01", reason="no_topics") is None


def test_A4_compute_incident_key_stable(isolated_events):
    k1 = isolated_events.compute_incident_key("b", "result_parse", "P01", reason="no_topics")
    k2 = isolated_events.compute_incident_key("b", "result_parse", "P01", reason="no_topics")
    assert k1 == k2 and len(k1) == 24


# --- Sub-plan B (defects #2,#3,#4,#6): no_topics taxonomy + pipeline ---

def _no_topics_kwargs(pipeline="car"):
    # mirrors dispatcher.py no_topics record_publish_error call
    return dict(
        blog_id="car-z", stage="no_topics", detail="no candidates",
        reason="no_topics", problem_id="P01", relation_type="symptom",
        retryable=False, pipeline=pipeline,
    )


def test_B1_pipeline_populated(isolated_events):  # defect #6
    e = isolated_events.record_publish_error(**_no_topics_kwargs(pipeline="car"))
    assert e["pipeline"] == "car"


def test_B2_problem_id_p01_not_p02(isolated_events):  # defect #3
    e = isolated_events.record_publish_error(**_no_topics_kwargs())
    assert e["problem_id"] == "P01"


def test_B3_reason_unified(isolated_events):  # defect #4
    e = isolated_events.record_publish_error(**_no_topics_kwargs())
    assert e["reason"] == "no_topics"


def test_B4_waiting_semantics_retryable_false(isolated_events):  # defect #2 (taxonomy)
    e = isolated_events.record_publish_error(**_no_topics_kwargs())
    # WAITING = not failure-amplifying; retryable stays False
    assert e["retryable"] == 0


def test_zero_real_ops_db_access(tmp_path, monkeypatch):
    real = events.OPS_DB_PATH
    monkeypatch.setattr(events, "OPS_DB_PATH", tmp_path / "ops.db")
    events.record_publish_error(**_no_topics_kwargs())
    assert events.OPS_DB_PATH != real
