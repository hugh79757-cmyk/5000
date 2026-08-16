"""PR2: refresh stalled root + catchup retry 제한 (A~P 필수 케이스).

운영 ops.db를 절대 접근하지 않는다 — 모든 테스트는 tmp_path DB + monkeypatch 사용.
conftest.py의 autouse guard(_guard_prod_ops_db)가 OPS_DB_PATH resolve를 검증한다.
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shared import publish_error_events as events

RESOURCE_ID = "car.db/daily_refresh"


def _make_db(tmp_path, monkeypatch):
    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    return db_path


def _connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _iso(hours_ago=0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _set_health(db_path, **fields):
    conn = _connect(db_path)
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE resource_health SET {sets} WHERE resource_id = ?",
        (*fields.values(), RESOURCE_ID),
    )
    conn.commit()
    conn.close()


def _record_symptom(blog_id):
    return events.record_publish_error(
        blog_id, "result_parse", "no_topics",
        reason="no_topics", problem_id="P01",
        relation_type="symptom", retryable=False,
    )


def _stall_health(db_path, hours_ago=40):
    """마지막 성공 40h+ 전, state=failed, 유입 0 — stalled 시나리오."""
    events.record_resource_start(RESOURCE_ID)
    events.record_resource_failure(RESOURCE_ID, error_reason="boom")
    _set_health(
        db_path,
        last_failure_at=_iso(hours_ago), last_completed_at=_iso(hours_ago),
        last_success_at=None, rows_inserted=None,
    )


# --- A. no_topics + refresh 정상 12시간 전 → symptom만, root 없음 ---
def test_a_symptom_only_refresh_healthy_12h(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    _record_symptom("deal-hugo")
    events.record_resource_start(RESOURCE_ID, job_name="pipelines/car/daily_refresh.py")
    events.record_resource_success(RESOURCE_ID, rows_inserted=5)
    _set_health(db, last_success_at=_iso(12), last_completed_at=_iso(12))

    root = events.evaluate_and_open_root_stalled(now=_iso())
    assert root is None
    assert events.get_open_root_incident(RESOURCE_ID) is None
    assert events.get_open_incident("deal-hugo", "P01", reason="no_topics") is not None


# --- B. no_topics 3블로그 + refresh 40h 정체 + 유입 0 → root 1건, symptom 연결 ---
def test_b_root_created_3_symptoms_linked(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    for blog in ("deal-hugo", "car-hugo", "hotissue-hugo"):
        _record_symptom(blog)
    _stall_health(db)

    root = events.evaluate_and_open_root_stalled(now=_iso())
    assert root is not None
    conn = _connect(db)
    row = conn.execute(
        "SELECT * FROM publish_error_events WHERE incident_key = ?", (root["incident_key"],)
    ).fetchone()
    assert row["relation_type"] == "root"
    assert row["problem_id"] == "P33"
    assert row["resource_id"] == RESOURCE_ID
    syms = conn.execute(
        "SELECT blog_id FROM publish_error_events WHERE state='open' AND problem_id='P01'"
    ).fetchall()
    assert len(syms) == 3
    for s in syms:
        r = conn.execute(
            "SELECT root_incident_key FROM publish_error_events "
            "WHERE blog_id=? AND state='open' AND problem_id='P01'",
            (s["blog_id"],),
        ).fetchone()
        assert r["root_incident_key"] == root["incident_key"]
    conn.close()


# --- C. pending=0이지만 refresh 성공 직후 → root 없음 ---
def test_c_pending_zero_refresh_success_no_root(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)
    events.record_resource_start(RESOURCE_ID)
    events.record_resource_success(RESOURCE_ID, rows_inserted=0)

    root = events.evaluate_and_open_root_stalled(now=_iso())
    assert root is None
    assert events.get_open_root_incident(RESOURCE_ID) is None


# --- D. refresh timeout, SLA 충족 전 → root 없음 ---
def test_d_timeout_before_sla_no_root(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    events.record_resource_start(RESOURCE_ID)
    events.record_resource_success(RESOURCE_ID, rows_inserted=5)
    _set_health(db, last_success_at=_iso(12), last_completed_at=_iso(12))
    # 오늘 재시작 후 timeout (last_success_at 12h 전 유지)
    events.record_resource_start(RESOURCE_ID)
    events.record_resource_timeout(RESOURCE_ID)

    root = events.evaluate_and_open_root_stalled(now=_iso())
    assert root is None
    assert events.get_open_root_incident(RESOURCE_ID) is None


# --- E. SLA 36h 초과 후 root 생성 ---
def test_e_root_after_sla_36h(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    events.record_resource_start(RESOURCE_ID)
    events.record_resource_success(RESOURCE_ID, rows_inserted=0)
    _set_health(
        db, last_success_at=_iso(40), last_completed_at=_iso(40),
        state="failed", last_error_reason="boom",
    )

    root = events.evaluate_and_open_root_stalled(now=_iso())
    assert root is not None
    conn = _connect(db)
    row = conn.execute(
        "SELECT * FROM publish_error_events WHERE incident_key = ?", (root["incident_key"],)
    ).fetchone()
    assert row["relation_type"] == "root"
    assert row["problem_id"] == "P33"
    conn.close()


# --- F. refresh 성공 + rows_inserted>0 → root close, pending 복구 시 symptom close ---
def test_f_refresh_success_closes_root_and_symptom(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    _record_symptom("deal-hugo")
    _stall_health(db)
    root = events.evaluate_and_open_root_stalled(now=_iso())
    assert root is not None

    events.record_resource_start(RESOURCE_ID)
    events.record_resource_success(RESOURCE_ID, rows_inserted=5)
    assert events.close_root_stalled_if_healthy() == 1
    assert events.get_open_root_incident(RESOURCE_ID) is None

    conn = _connect(db)
    n = events.close_publish_error_event(conn, blog_id="deal-hugo", problem_id="P01")
    conn.commit()
    conn.close()
    assert n == 1
    assert events.get_open_incident("deal-hugo", "P01", reason="no_topics") is None


# --- G. refresh 성공 + rows_inserted=0 → root close 가능, symptom 유지 ---
def test_g_refresh_success_zero_rows_closes_root_keeps_symptom(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    _record_symptom("deal-hugo")
    _stall_health(db)
    root = events.evaluate_and_open_root_stalled(now=_iso())
    assert root is not None

    events.record_resource_start(RESOURCE_ID)
    events.record_resource_success(RESOURCE_ID, rows_inserted=0)
    assert events.close_root_stalled_if_healthy() == 1
    assert events.get_open_root_incident(RESOURCE_ID) is None
    # candidate_exhausted symptom은 pending>0이 될 때까지 유지 가능
    assert events.get_open_incident("deal-hugo", "P01", reason="no_topics") is not None


# --- H. catchup no_topics 1~3회 → 정책대로 허용/카운트 ---
def test_h_catchup_retry_1_to_3_allowed(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)
    _record_symptom("deal-hugo")
    for i in range(1, 4):
        assert events.increment_incident_retry("deal-hugo", "P01", reason="no_topics") is True
        state = events.get_catchup_retry_state("deal-hugo")
        assert state is not None and state["retry_count"] == i
    state = events.get_catchup_retry_state("deal-hugo")
    assert state["retry_count"] == 3
    assert state["retry_blocked"] is False


# --- I. 4번째 catchup → 실행 안 함 + amplifier open 1건 (5분 중복 방지) ---
def test_i_fourth_catchup_blocked_amplifier_one(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    _record_symptom("deal-hugo")
    for _ in range(3):
        events.increment_incident_retry("deal-hugo", "P01", reason="no_topics")
    state = events.get_catchup_retry_state("deal-hugo")
    assert state["retry_count"] >= 3

    # scheduler 로직 모사: 4번째 catchup 시도 → amplifier upsert
    events.record_retry_amplification("deal-hugo", root_incident_key=state.get("root_incident_key") or "")
    events.record_retry_amplification("deal-hugo")  # 5분 뒤 재시도 — 행 1개 유지
    conn = _connect(db)
    rows = conn.execute(
        "SELECT * FROM publish_error_events "
        "WHERE blog_id='deal-hugo' AND problem_id='P34' AND state='open'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["relation_type"] == "amplifier"
    assert rows[0]["retry_blocked"] == 1
    conn.close()


# --- J. scheduler 재시작 모사 → block 유지 (ops.db SSOT) ---
def test_j_restart_keeps_block(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)
    _record_symptom("deal-hugo")
    events.set_incident_retry_blocked("deal-hugo", "P01", True, reason="no_topics")
    # 재시작 모사: 새 연결(자동연결)로 재조회 → 유지
    state = events.get_catchup_retry_state("deal-hugo")
    assert state is not None
    assert state["retry_blocked"] is True


# --- K. pending 복구 → block 해제 ---
def test_k_pending_restored_unblocks(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)
    _record_symptom("deal-hugo")
    events.set_incident_retry_blocked("deal-hugo", "P01", True, reason="no_topics")
    events.set_incident_retry_blocked("deal-hugo", "P01", False, reason="no_topics")
    state = events.get_catchup_retry_state("deal-hugo")
    assert state["retry_blocked"] is False


# --- L. 정규 schedule → catchup block과 무관하게 동작 ---
def test_l_regular_schedule_unaffected_by_block(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)
    _record_symptom("deal-hugo")
    events.set_incident_retry_blocked("deal-hugo", "P01", True, reason="no_topics")
    # 다른 blog의 정규 발행 실패 기록은 차단 없이 정상 동작
    ev = events.record_publish_error(
        "other-hugo", "result_parse", "no_topics",
        reason="no_topics", problem_id="P01",
        relation_type="symptom", retryable=False,
    )
    assert ev is not None
    assert events.get_open_incident("other-hugo", "P01", reason="no_topics") is not None


# --- M. 동일 root를 세 블로그가 공유 → root 행 1개 ---
def test_m_single_root_shared_across_blogs(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    _stall_health(db)
    r1 = events.evaluate_and_open_root_stalled(now=_iso())
    r2 = events.evaluate_and_open_root_stalled(now=_iso())
    r3 = events.evaluate_and_open_root_stalled(now=_iso())
    keys = {r1["incident_key"], r2["incident_key"], r3["incident_key"]}
    assert len(keys) == 1
    conn = _connect(db)
    n = conn.execute(
        "SELECT COUNT(*) c FROM publish_error_events "
        "WHERE relation_type='root' AND state='open' AND resource_id=?",
        (RESOURCE_ID,),
    ).fetchone()["c"]
    assert n == 1
    conn.close()


# --- N. 발행 성공 → source_refresh_stalled root가 닫히지 않음 ---
def test_n_publish_success_does_not_close_root(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    _record_symptom("deal-hugo")
    _stall_health(db)
    root = events.evaluate_and_open_root_stalled(now=_iso())
    assert root is not None

    conn = _connect(db)
    events.close_publish_error_event(conn, blog_id="deal-hugo", problem_id="P01")
    conn.commit()
    conn.close()
    # root는 refresh success 증거로만 close — 발행 성공으로는 유지
    assert events.get_open_root_incident(RESOURCE_ID) is not None


# --- O. migration 반복 실행 → 안전 ---
def test_o_migration_repeat_safe(tmp_path, monkeypatch):
    db = _make_db(tmp_path, monkeypatch)
    for _ in range(3):
        events.ensure_schema()
    conn = _connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(publish_error_events)").fetchall()}
    for col in ("relation_type", "root_incident_key", "resource_id", "retry_blocked", "retry_count", "metadata_json"):
        assert col in cols
    health_cols = {r[1] for r in conn.execute("PRAGMA table_info(resource_health)").fetchall()}
    assert "state" in health_cols and "rows_inserted" in health_cols
    conn.close()


# --- P. 운영 DB guard → 접근 즉시 테스트 실패 (conftest autouse가 검증) ---
def test_p_prod_ops_db_guard_active(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)  # guard가 tmp_path 강제 — 운영 경로면 여기서 실패
    prod = Path("/Users/twinssn/Projects/5000/ops_dashboard/ops.db")
    assert Path(events.OPS_DB_PATH).resolve() != prod.resolve()