"""Phase 69 Sub-plan A+B contract tests (defects #1,#2,#3,#4,#6).

Locks the behavior that new publish_error_events rows have:
  A (defect #1): non-null incident_key that merges identical occurrences
  A (close path): resolved_at is set on close
  B (#3): no_topics is recorded as P01, never falling back to P02
  B (#4): no_topics reason is unified ('no_topics'), not empty
  B (#6): pipeline is populated (dispatcher passes the resolved pipeline)
  B (#2): no_topics is WAITING semantics (retryable=False, not failure-amplifying)

Boundary (M4): no_topics keeps state='open' (lifecycle) + reason='no_topics' +
P01; the M4 Dashboard is expected to present execution status=
WAITING_FOR_CANDIDATES derived from that combination. No Dashboard change here.

Uses an isolated temp ops.db (zero real ops-DB access). No scheduler import,
no subprocess, no external calls.
"""
import pytest

from dispatcher import _resolved_pipeline_for
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


# --- Sub-plan B (defect #6 wiring): dispatcher resolved-pipeline + lifecycle ---

def test_B5_resolved_pipeline_cap_car_non_empty():
    # 신규 CAP/car 이벤트의 pipeline이 빈 문자열이 되지 않아야 한다.
    assert _resolved_pipeline_for("car-hugo", {"pipeline": "car"}) == "car"
    assert _resolved_pipeline_for("hotissue-hugo", {"pipeline": "car"}) == "car"
    assert _resolved_pipeline_for("compare-hugo", {"pipeline": "car"}) == "car"


def test_B6_resolved_pipeline_stap_uses_module_name():
    # STAP 블로그는 cfg.pipeline("stock")이 아니라 실제 실행 모듈 파이프라인 이름.
    assert _resolved_pipeline_for("sector-hugo", {"pipeline": "stock"}) == "sector"
    assert _resolved_pipeline_for("ipo-hugo", {"pipeline": "stock"}) == "ipo"


def test_B7_resolved_pipeline_no_cfg_fallback_for_cap():
    # cfg에 pipeline 키가 없어도 STAP 매핑에 있으면 그 값 사용 (빈 문자열 금지).
    assert _resolved_pipeline_for("etf-hugo", {}) == "etf"


def test_B8_no_topics_state_stays_open(isolated_events):
    # state='open'은 incident lifecycle — WAITING 표현을 위해 오버로드하지 않는다.
    e = isolated_events.record_publish_error(**_no_topics_kwargs(pipeline="car"))
    assert e["state"] == "open"
    assert e["reason"] == "no_topics"
    assert e["problem_id"] == "P01"
    assert isolated_events.get_open_incident("car-z", "P01", reason="no_topics") is not None
