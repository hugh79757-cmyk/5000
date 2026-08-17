"""Morning Audit hotfix: taxonomy reason 전달 + 이중 incident dedup 검증.

- send_error(reason=stage) → no_data=P01, low_relevance=P14 (lookup_reason 경로 복구)
- _tg_error 경로(send_error)와 monitor 경로(send_problem_alert)가 동일 incident_key로 병합
임시 SQLite DB만 사용 (라이브 ops.db 미접촉).
"""

import sqlite3
from unittest.mock import patch

from shared import publish_error_events as events
from shared import telegram_notifier as notifier
from shared.problem_monitor import PublishMonitor

SEND_PATH = "shared.problem_monitor.telegram_notifier.send"


def _make_db(tmp_path, monkeypatch):
    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    return db_path


def _rows(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT blog_id, stage, problem_id, reason, incident_key, occurrence_count"
        " FROM publish_error_events ORDER BY rowid"
    ).fetchall()
    conn.close()
    return rows


def test_send_error_no_data_maps_p01(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, monkeypatch)
    with patch.object(notifier, "send", return_value=True):
        notifier.send_error("x-hugo", "no_data", "no data for blog")
    rows = _rows(db_path)
    assert len(rows) == 1
    assert rows[0]["problem_id"] == "P01"
    assert rows[0]["reason"] == "no_data"
    assert rows[0]["stage"] == "no_data"


def test_send_error_low_relevance_maps_p14(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, monkeypatch)
    with patch.object(notifier, "send", return_value=True):
        notifier.send_error("x-hugo", "low_relevance", "low relevance")
    rows = _rows(db_path)
    assert len(rows) == 1
    assert rows[0]["problem_id"] == "P14"
    assert rows[0]["reason"] == "low_relevance"


def test_tg_error_and_monitor_paths_share_incident_key(tmp_path, monkeypatch):
    db_path = _make_db(tmp_path, monkeypatch)
    # _tg_error 경로: dispatcher._tg_error(blog_id, reason, msg) → send_error(stage=reason)
    with patch.object(notifier, "send", return_value=True):
        notifier.send_error("car-hugo", "no_data", "no data")
    # monitor 경로: dispatcher.report({"reason": "no_data", "stage": "no_data"}) → send_problem_alert
    monitor = PublishMonitor(dry_run=False)
    with patch(SEND_PATH) as mock_send:
        mock_send.return_value = True
        rendered = monitor.send_problem_alert(
            "P01", "car-hugo",
            {"stage": "no_data", "reason": "no_data", "matched": "no data", "phase": "result_parse"},
        )
    assert rendered is not None
    rows = _rows(db_path)
    # 동일 incident_key → upsert 병합 → 1행 (occurrence 2는 동일 attempt 중복 집계, 허용 오차)
    assert len(rows) == 1
    assert rows[0]["problem_id"] == "P01"
    assert rows[0]["occurrence_count"] == 2