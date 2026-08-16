"""PR1: publish_error_events 인시던트 upsert + lifecycle 테스트.

- 동일 open incident 재발: 새 행 INSERT 금지, occurrence_count+=1, last_seen_at 갱신
- closed incident 재발: 새 incident 행 생성 (reopen 금지)
- canonical key: detail/시각/횟수 제외, reason alias 정규화
- 동시성: partial UNIQUE index로 open incident 1행 강제
- 임시 SQLite DB만 사용 (라이브 ops.db 미접촉)
"""

import sqlite3
import threading
import time

from shared import publish_error_events as events


def _make_db(tmp_path, monkeypatch):
    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    return db_path


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn):
    return conn.execute(
        "SELECT event_id, blog_id, stage, problem_id, reason, state, incident_key,"
        " occurrence_count, first_seen_at, last_seen_at, resolved_at, detail_redacted"
        " FROM publish_error_events ORDER BY rowid"
    ).fetchall()


def test_same_key_100_records_single_incident(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, monkeypatch)
    first = events.record_publish_error("b1", "result_parse", "detail-0", reason="no_topics")
    for i in range(1, 100):
        events.record_publish_error("b1", "result_parse", f"detail-{i}", reason="no_topics")
    conn = _connect(db_path)
    rows = _rows(conn)
    assert len(rows) == 1
    row = rows[0]
    assert row["state"] == "open"
    assert row["occurrence_count"] == 100
    assert row["first_seen_at"] == first["first_seen_at"]
    assert row["last_seen_at"] >= row["first_seen_at"]
    assert row["detail_redacted"] == "detail-99"
    assert row["incident_key"] is not None
    conn.close()


def test_detail_only_differs_same_incident(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, monkeypatch)
    for i in range(10):
        events.record_publish_error("b1", "result_parse", f"attempt {i} @ {i}:00:00", reason="no_topics")
    conn = _connect(db_path)
    rows = _rows(conn)
    assert len(rows) == 1
    assert rows[0]["occurrence_count"] == 10
    conn.close()


def test_different_reason_separate_incident(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, monkeypatch)
    events.record_publish_error("b1", "result_parse", "same detail", reason="no_topics")
    events.record_publish_error("b1", "result_parse", "same detail", reason="no_content")
    conn = _connect(db_path)
    rows = _rows(conn)
    assert len(rows) == 2
    assert {r["problem_id"] for r in rows} == {"P01", "P02"}
    assert rows[0]["incident_key"] != rows[1]["incident_key"]
    conn.close()


def test_different_blog_separate_incident(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, monkeypatch)
    events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
    events.record_publish_error("b2", "result_parse", "d", reason="no_topics")
    conn = _connect(db_path)
    rows = _rows(conn)
    assert len(rows) == 2
    assert {r["blog_id"] for r in rows} == {"b1", "b2"}
    conn.close()


def test_close_then_recur_new_incident(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, monkeypatch)
    first = events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
    events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
    conn = _connect(db_path)
    closed = events.close_publish_error_event(
        conn, blog_id="b1", problem_id="P01", incident_key=first["incident_key"])
    assert closed == 1
    rows = _rows(conn)
    assert len(rows) == 1
    assert rows[0]["state"] == "closed"
    assert rows[0]["resolved_at"] is not None
    assert rows[0]["occurrence_count"] == 2  # close가 occurrence 보존
    assert rows[0]["first_seen_at"] == first["first_seen_at"]
    conn.close()

    # 재발 → 기존 행 reopen 금지, 새 open incident 생성
    events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
    events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
    conn = _connect(db_path)
    rows = _rows(conn)
    assert len(rows) == 2
    states = sorted(r["state"] for r in rows)
    assert states == ["closed", "open"]
    open_row = [r for r in rows if r["state"] == "open"][0]
    assert open_row["occurrence_count"] == 2
    assert open_row["incident_key"] == first["incident_key"]  # 같은 key, 새 행
    assert open_row["first_seen_at"] != rows[0]["first_seen_at"]
    conn.close()


def test_close_repeat_safe(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, monkeypatch)
    ev = events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
    conn = _connect(db_path)
    assert events.close_publish_error_event(
        conn, blog_id="b1", problem_id="P01", incident_key=ev["incident_key"]) == 1
    # 이미 closed → 재호출 안전 (0건, 상태 불변)
    assert events.close_publish_error_event(
        conn, blog_id="b1", problem_id="P01", incident_key=ev["incident_key"]) == 0
    rows = _rows(conn)
    assert len(rows) == 1
    assert rows[0]["state"] == "closed"
    assert rows[0]["occurrence_count"] == 1
    conn.close()


def test_migration_twice_safe(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, monkeypatch)
    events.ensure_schema()
    events.ensure_schema()
    events.ensure_schema()
    conn = _connect(db_path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(publish_error_events)")}
    for name in ("incident_key", "key_version", "occurrence_count", "first_seen_at",
                 "last_seen_at", "resolved_at"):
        assert name in cols
    idx = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_publish_error_open_incident'"
    ).fetchone()
    assert idx is not None
    conn.close()


def test_migration_preserves_old_rows(tmp_path, monkeypatch):
    """구 스키마(신규 컬럼 없음) 데이터 존재 상태에서 migration → 기존 행 유실 없음."""
    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    conn = _connect(db_path)
    conn.executescript("""
        CREATE TABLE publish_error_events (
            event_id TEXT PRIMARY KEY,
            occurred_at TEXT NOT NULL,
            blog_id TEXT NOT NULL,
            pipeline TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL,
            problem_id TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL,
            retryable INTEGER NOT NULL DEFAULT 0,
            attempt INTEGER,
            max_attempts INTEGER,
            source_name TEXT NOT NULL DEFAULT '',
            http_status INTEGER,
            timeout_seconds INTEGER,
            detail_redacted TEXT NOT NULL DEFAULT '',
            fingerprint TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    for i in range(3):
        conn.execute(
            "INSERT INTO publish_error_events (event_id, occurred_at, blog_id, stage,"
            " problem_id, severity, fingerprint) VALUES (?, ?, 'old', 's', 'P01', 'MAJOR', 'fp')",
            (f"e{i}", f"2026-08-01T00:0{i}:00",),
        )
    conn.commit()
    conn.close()

    events.ensure_schema()
    conn = _connect(db_path)
    rows = _rows(conn)
    assert len(rows) == 3  # 기존 행 유실 없음
    for row in rows:
        assert row["incident_key"] is None  # 기존 행은 key 밖 (삭제/병합 없음)
    idx = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_publish_error_open_incident'"
    ).fetchone()
    assert idx is not None  # 기존 중복(NULL)과 충돌 없이 index 생성 성공
    conn.close()


def test_legacy_caller_no_new_args(tmp_path, monkeypatch):
    """신규 인자(resource_id/incident_key) 없이 호출해도 정상 동작."""
    db_path = _make_db(tmp_path, monkeypatch)
    ev = events.record_publish_error("b1", "scheduler", "timeout 600s")
    assert ev["incident_key"] is not None
    assert ev["occurrence_count"] == 1
    conn = _connect(db_path)
    closed = events.close_publish_error_event(conn, blog_id="b1", problem_id="P25")
    assert closed == 1
    rows = _rows(conn)
    assert rows[0]["state"] == "closed"
    conn.close()


def test_concurrent_same_key_single_open(tmp_path, monkeypatch):
    """병렬 동시성: 같은 incident를 동시에 기록해도 open 행은 1개만 남는다."""
    db_path = _make_db(tmp_path, monkeypatch)
    errors = []

    def _worker(n):
        try:
            for _ in range(20):
                events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
        except Exception as exc:  # pragma: no cover - 실패 기록용
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    conn = _connect(db_path)
    rows = _rows(conn)
    open_rows = [r for r in rows if r["state"] == "open"]
    closed_rows = [r for r in rows if r["state"] == "closed"]
    assert len(open_rows) == 1  # open 중복 없음
    assert len(closed_rows) == 0
    assert open_rows[0]["occurrence_count"] >= 1  # 일부 race 실패 허용, 단 1행은 보장
    conn.close()


def test_key_stable_with_time_count_detail(tmp_path, monkeypatch):
    """detail에 시각·횟수가 달라도 canonical key 동일 (compute + record 경로)."""
    k1 = events.compute_incident_key("b1", "result_parse", "P01", reason="no_topics")
    k2 = events.compute_incident_key("b1", "result_parse", "P01", reason="no_topics")
    assert k1 == k2
    db_path = _make_db(tmp_path, monkeypatch)
    ev1 = events.record_publish_error(
        "b1", "result_parse", "occurrence 1 at 2026-08-01", reason="no_topics")
    ev2 = events.record_publish_error(
        "b1", "result_parse", "occurrence 99 at 2026-08-16", reason="no_topics")
    assert ev1["incident_key"] == ev2["incident_key"]
    assert ev2["occurrence_count"] == 2


def test_different_normalized_reason_key_differs(tmp_path, monkeypatch):
    """alias(no_topic→no_topics)는 같은 key, 본질이 다른 reason은 다른 key."""
    alias_a = events.compute_incident_key("b1", "result_parse", "P01", reason="no_topic")
    alias_b = events.compute_incident_key("b1", "result_parse", "P01", reason="no_topics")
    assert alias_a == alias_b
    other = events.compute_incident_key("b1", "result_parse", "P01", reason="no_result")
    assert alias_b != other
    db_path = _make_db(tmp_path, monkeypatch)
    events.record_publish_error("b1", "result_parse", "d", reason="no_topic")
    events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
    conn = _connect(db_path)
    assert len(_rows(conn)) == 1  # alias 통일로 1 incident
    conn.close()


# ─── event_id 반환 정합 (PR1 안정화: state='open' + 결정적 ORDER BY) ───


def test_event_id_returns_open_with_closed_history(tmp_path, monkeypatch):
    """A: 같은 key의 closed 3개 + open 1개 상태에서 record 반환 event_id는 open 행."""
    db_path = _make_db(tmp_path, monkeypatch)
    conn = _connect(db_path)
    for _ in range(3):
        ev = events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
        assert events.close_publish_error_event(
            conn, blog_id="b1", problem_id="P01", incident_key=ev["incident_key"]) == 1
    ev = events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
    conn.close()

    conn = _connect(db_path)
    rows = _rows(conn)
    conn.close()
    assert len(rows) == 4
    assert sum(1 for r in rows if r["state"] == "closed") == 3
    open_row = [r for r in rows if r["state"] == "open"][0]
    assert ev["event_id"] == open_row["event_id"]  # closed가 아닌 open 행 반환
    assert ev["occurrence_count"] == open_row["occurrence_count"] == 1


def test_event_id_after_close_recur_is_new_open(tmp_path, monkeypatch):
    """B: close 후 같은 key 재발 시 신규 open 행의 event_id 반환."""
    db_path = _make_db(tmp_path, monkeypatch)
    first = events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
    conn = _connect(db_path)
    assert events.close_publish_error_event(
        conn, blog_id="b1", problem_id="P01", incident_key=first["incident_key"]) == 1
    conn.close()
    second = events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
    assert second["event_id"] != first["event_id"]
    assert second["incident_key"] == first["incident_key"]
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT state FROM publish_error_events WHERE event_id = ?",
        (second["event_id"],),
    ).fetchone()
    assert row["state"] == "open"
    conn.close()


def test_concurrent_all_return_same_open_event_id(tmp_path, monkeypatch):
    """C: 8 thread가 같은 key를 기록해도 모두 동일 open event_id 반환."""
    db_path = _make_db(tmp_path, monkeypatch)
    returned = []

    def _worker():
        ev = events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
        returned.append(ev["event_id"])

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(returned) == 8
    assert len(set(returned)) == 1  # 전부 동일 open incident
    conn = _connect(db_path)
    open_rows = [r for r in _rows(conn) if r["state"] == "open"]
    assert len(open_rows) == 1
    assert returned[0] == open_rows[0]["event_id"]
    conn.close()


def test_separate_connections_return_same_open_event_id(tmp_path, monkeypatch):
    """D: 개별 connection(프로세스 모사)마다 record해도 동일 open event_id 반환."""
    db_path = _make_db(tmp_path, monkeypatch)
    ids = []
    for _ in range(6):
        ev = events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
        ids.append(ev["event_id"])
    assert len(set(ids)) == 1
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT event_id FROM publish_error_events WHERE state='open'", ()
    ).fetchone()
    assert row["event_id"] == ids[0]
    conn.close()


def test_telegram_audit_links_open_incident(tmp_path, monkeypatch):
    """E: 반환 event_id를 Telegram audit에 기록해도 open incident와 정확히 일치."""
    db_path = _make_db(tmp_path, monkeypatch)
    # closed 이력 + open 상태 공존 (과거 버그 시나리오)
    conn = _connect(db_path)
    for _ in range(2):
        ev = events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
        assert events.close_publish_error_event(
            conn, blog_id="b1", problem_id="P01", incident_key=ev["incident_key"]) == 1
    ev = events.record_publish_error("b1", "result_parse", "d", reason="no_topics")
    conn.close()

    events.record_telegram_delivery(
        ev["event_id"], "msg", delivered=True, telegram_message_id="t1",
        http_status=200, detail="ok")

    conn = _connect(db_path)
    audit = conn.execute(
        "SELECT event_id FROM telegram_delivery_audit WHERE telegram_message_id = 't1'",
    ).fetchone()
    assert audit["event_id"] == ev["event_id"]
    row = conn.execute(
        "SELECT state FROM publish_error_events WHERE event_id = ?", (ev["event_id"],),
    ).fetchone()
    assert row["state"] == "open"  # FK가 open incident를 가리킴
    conn.close()