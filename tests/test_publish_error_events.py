import sqlite3

from shared import publish_error_events as events


def test_classifies_publish_error_cases():
    assert events.classify_error("scheduler", "timeout 600s")[0] == "P25"
    assert events.classify_error("data_fetch", "fetcher returned no value")[0] == "P26"
    assert events.classify_error("result_parse", "pipeline no_result: no eligible source")[0] == "P27"
    assert events.classify_error("result_parse", "invalid result contract")[0] == "P28"
    assert events.classify_error("scheduler", "AttributeError: tags split")[0] == "P29"
    assert events.classify_error("content_generation", "AI body generation failed")[0] == "P30"
    assert events.classify_error("validation", "cta_html missing")[0] == "P15"


def test_persists_event_and_telegram_delivery(tmp_path, monkeypatch):
    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    event = events.record_publish_error(
        "travel-hugo", "scheduler", "timeout 600s",
        timeout_seconds=600,
    )
    events.record_telegram_delivery(
        event["event_id"], "Publish error token=abc", delivered=True,
        telegram_message_id="123", http_status=200,
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = events.get_publish_error_events(conn)
    assert len(rows) == 1
    assert rows[0]["problem_id"] == "P25"
    assert rows[0]["timeout_seconds"] == 600
    audit = conn.execute("SELECT delivered, telegram_message_id FROM telegram_delivery_audit").fetchone()
    assert audit["delivered"] == 1
    assert audit["telegram_message_id"] == "123"
    conn.close()
