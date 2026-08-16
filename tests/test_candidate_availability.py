"""PR3: candidate availability contract + scheduler gate + 대시보드 (필수 24종).

운영 ops.db / car.db를 절대 접근하지 않는다 — 모든 테스트는 tmp_path DB + monkeypatch.
conftest.py의 autouse guard(_guard_prod_ops_db)가 OPS_DB_PATH resolve를 검증한다.
"""
import json
import sqlite3
from types import SimpleNamespace
from pathlib import Path

import pytest

from shared import candidate_availability as ca
from shared import publish_error_events as events
from shared import problem_registry

CAR_DB_RESOURCE = "car.db"


# ─── 헬퍼 ───

def _make_ops_db(tmp_path, monkeypatch) -> Path:
    db_path = tmp_path / "ops.db"
    monkeypatch.setattr(events, "OPS_DB_PATH", db_path)
    events.ensure_schema()
    return db_path


def _make_car_db(tmp_path, rows) -> Path:
    """rows: list[(site_id, post_type, status)]"""
    db_path = tmp_path / "car.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE topics (id INTEGER PRIMARY KEY, site_id TEXT, post_type TEXT, status TEXT)"
    )
    for i, (site_id, post_type, status) in enumerate(rows):
        conn.execute(
            "INSERT INTO topics (id, site_id, post_type, status) VALUES (?,?,?,?)",
            (i + 1, site_id, post_type, status),
        )
    conn.commit()
    conn.close()
    return db_path


CAR_BLOG = {
    "id": "guide-hugo",
    "pipeline": "car",
    "post_type": "beginner_guide",
    "daily_quota": 5,
    "schedule": {"times": ["07:18", "10:18", "13:18", "16:18", "20:18"]},
}

HOTISSUE_BLOG = {
    "id": "hotissue-hugo",
    "pipeline": "car",
    "post_type": ["compare", "resale_compare", "search", "resale_search", "news", "resale_news"],
    "daily_quota": 5,
    "schedule": {"times": ["07:18", "10:18", "13:18", "16:18", "20:18"]},
}


def _record_root_stalled(blog_id="guide-hugo"):
    """P33 root incident 생성 (resource_id='car.db')."""
    events.record_publish_error(
        blog_id, "resource_refresh", "source_refresh_stalled",
        reason="source_refresh_stalled", problem_id="P33",
        relation_type="root", retryable=False, resource_id=CAR_DB_RESOURCE,
    )


# ─── 1. car pending=0 → dispatcher 호출 0 ───

def test_pending_zero_dispatcher_not_called(tmp_path, monkeypatch):
    ops_db = _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [])  # pending 0
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    calls = []
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: calls.append(a) or SimpleNamespace(
            returncode=0, stdout='{"success": true}\n', stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)

    result = sched.run_publish("guide-hugo")

    assert result is None  # 실행 생략
    assert calls == []  # dispatcher subprocess 호출 0


# ─── 2. pending=0 → failure_count 증가 0 (track_publish_result 미호출) ───

def test_pending_zero_no_failure_tracking(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    tracked = []
    monkeypatch.setattr(sched, "_track_publish_result", lambda bid, ok: tracked.append((bid, ok)))
    calls = []
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="{}", stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)

    result = sched.run_publish("guide-hugo")

    assert result is None
    assert tracked == []  # _track_publish_result(실패 카운트 경로) 미호출


# ─── 3. pending=0 → 신규 MAJOR Telegram 0 ───

def test_pending_zero_no_major_telegram(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    sent = []
    monkeypatch.setattr(
        "shared.telegram_notifier.send",
        lambda msg, **k: sent.append(msg),
    )
    calls = []
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="{}", stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)

    sched.run_publish("guide-hugo")

    assert calls == []
    # dispatcher 미실행 → P01 MAJOR 알림 경로 진입 자체가 없음
    assert sent == []


# ─── 4. pending=0 → WAITING upsert ───

def test_pending_zero_waiting_upsert(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    calls = []
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="{}", stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)

    sched.run_publish("guide-hugo")

    row = events.get_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide",
    )
    assert row is not None
    assert row["state"] == "waiting_for_candidates"
    assert row["available_count"] == 0
    assert row["reason"] == "no_topics"


# ─── 5. WAITING 반복 검사 → 상태 행 1개 ───

def test_repeated_check_single_row(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    for _ in range(3):
        events.upsert_availability(
            "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
            candidate_type="beginner_guide", state="waiting_for_candidates",
            available_count=0, reason="no_topics",
        )

    rows = events.get_availability_all()
    matching = [r for r in rows if r["blog_id"] == "guide-hugo"]
    assert len(matching) == 1  # upsert 중복 행 없음


# ─── 6. pending>0 → 실행 허용 ───

def test_pending_positive_allows_publish(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [("guide", "beginner_guide", "pending")])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    calls = []
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: calls.append(a) or SimpleNamespace(
            returncode=0, stdout='{"success": true}\n', stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)

    result = sched.run_publish("guide-hugo")

    assert result is True
    assert len(calls) == 1  # dispatcher 1회 실행
    # 발행 성공 → healthy upsert
    row = events.get_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide",
    )
    assert row["state"] == "healthy"


# ─── 7. 특정 post_type만 복구 → 해당 blog만 release ───

def test_refresh_releases_only_recovered_blog(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    # guide는 복구(pending>0), hotissue는 여전히 pending=0
    car_db = _make_car_db(tmp_path, [("guide", "beginner_guide", "pending")])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    import scheduler as sched
    monkeypatch.setattr(
        sched, "load_config",
        lambda: {"blogs": [CAR_BLOG, HOTISSUE_BLOG]},
    )

    sched._evaluate_car_availability_after_refresh(events)

    guide = events.get_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide",
    )
    hotissue = events.get_availability(
        "hotissue-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="compare,resale_compare,search,resale_search,news,resale_news",
    )
    assert guide["state"] == "healthy"  # prev 없음 → healthy
    assert hotissue["state"] == "waiting_for_candidates"


# ─── 8. refresh rows=0 → WAITING 유지 ───

def test_refresh_zero_rows_keeps_waiting(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    events.upsert_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide", state="waiting_for_candidates",
        available_count=0, reason="no_topics",
    )

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    sched._evaluate_car_availability_after_refresh(events)

    row = events.get_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide",
    )
    assert row["state"] == "waiting_for_candidates"


# ─── 9. refresh rows>0 + pending>0 → RECOVERING ───

def test_refresh_positive_transitions_to_recovering(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [("guide", "beginner_guide", "pending")])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    # refresh 전: WAITING 상태
    events.upsert_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide", state="waiting_for_candidates",
        available_count=0, reason="no_topics",
    )

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    sched._evaluate_car_availability_after_refresh(events)

    row = events.get_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide",
    )
    assert row["state"] == "recovering"
    assert row["available_count"] >= 1


# ─── 10. 발행 성공 → HEALTHY ───

def test_publish_success_healthy(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [("guide", "beginner_guide", "pending")])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    events.upsert_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide", state="recovering",
        available_count=1, reason="",
    )

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout='{"success": true}\n', stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)

    result = sched.run_publish("guide-hugo")

    assert result is True
    row = events.get_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide",
    )
    assert row["state"] == "healthy"


# ─── 11. P33 open → BLOCKED ───

def test_root_open_blocks_publish(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [])  # pending 0
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)
    _record_root_stalled()  # P33 root open (resource_id='car.db')

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    calls = []
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="{}", stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)

    result = sched.run_publish("guide-hugo")

    assert result is None
    assert calls == []
    row = events.get_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide",
    )
    assert row["state"] == "blocked_by_source"
    assert row["linked_incident_key"]


# ─── 12. P33 close + pending=0 → WAITING ───

def test_root_closed_returns_waiting(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)
    _record_root_stalled()
    root = events.get_open_root_incident(CAR_DB_RESOURCE)
    assert root is not None
    conn = sqlite3.connect(str(tmp_path / "ops.db"))
    events.close_publish_error_event(
        conn, blog_id="guide-hugo", problem_id="P33",
        incident_key=root["incident_key"],
    )
    conn.close()

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    calls = []
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="{}", stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)

    result = sched.run_publish("guide-hugo")

    assert result is None  # pending=0 이므로 여전히 실행 생략
    row = events.get_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide",
    )
    assert row["state"] == "waiting_for_candidates"


# ─── 13. checker 미지원 pipeline → UNKNOWN, 기존 실행 유지 ───

def test_unsupported_pipeline_unknown_keeps_running(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)

    etap_blog = {
        "id": "rome-hugo", "pipeline": "etap", "post_type": "attractions",
        "daily_quota": 5,
    }
    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [etap_blog]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    calls = []
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: calls.append(a) or SimpleNamespace(
            returncode=0, stdout='{"success": true}\n', stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)

    result = sched.run_publish("rome-hugo")

    assert result is True  # 기존 실행 유지
    assert len(calls) == 1
    row = events.get_availability("rome-hugo", pipeline="etap", resource_id="", candidate_type="")
    assert row is None or row["state"] == "unknown"  # upsert는 unknown으로 기록


# ─── 14. checker exception → 해당 schedule 1회 안전 skip ───

def test_checker_exception_safe_skip(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    monkeypatch.setattr(ca, "check_availability", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    calls = []
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="{}", stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)

    result = sched.run_publish("guide-hugo")

    assert result is None  # 1회 skip (전체 중단 아님)
    assert calls == []
    row = events.get_availability(
        "guide-hugo", pipeline="car", resource_id=CAR_DB_RESOURCE,
        candidate_type="beginner_guide",
    )
    assert row is not None and row["state"] == "checker_error"


# ─── 15. catchup blocked → pipeline 호출 0 ───

def test_catchup_blocked_skips_pipeline(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    import scheduler as sched

    class _FakeDT:
        @classmethod
        def now(cls):
            return _FakeNow()

    class _FakeNow:
        hour = 10
        day = 17
        month = 8
        year = 2026
        strftime = staticmethod(lambda fmt: "2026-08-17")

    monkeypatch.setattr(sched, "datetime", _FakeDT)
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    # retry_blocked=1 open P01 생성 (get_catchup_retry_state가 차단)
    events.record_publish_error(
        "guide-hugo", "result_parse", "no_topics",
        reason="no_topics", problem_id="P01", relation_type="symptom",
        retryable=False,
    )
    events.set_incident_retry_blocked("guide-hugo", "P01", True, reason="no_topics")
    calls = []
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="{}", stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)

    sched._catchup_missed_inner()

    assert calls == []  # retry_blocked → dispatcher 미호출


# ─── 16. 정규 schedule도 waiting이면 pipeline 호출 0 (drain 경로) ───

def test_drain_queue_waiting_no_pipeline(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    car_db = _make_car_db(tmp_path, [])
    monkeypatch.setattr(ca, "_car_db_path", lambda *a, **k: car_db)

    import scheduler as sched
    monkeypatch.setattr(sched, "load_config", lambda: {"blogs": [CAR_BLOG]})
    monkeypatch.setattr(sched, "_get_ledger_count", lambda bid, d: 0)
    calls = []
    monkeypatch.setattr(
        sched.subprocess, "run",
        lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="{}", stderr=""),
    )
    monkeypatch.setattr(sched, "acquire_publish_slot", lambda bid: "slot1")
    monkeypatch.setattr(sched, "release_publish_slot", lambda slot, bid: None)
    tracked = []
    monkeypatch.setattr(sched, "_track_publish_result", lambda bid, ok: tracked.append((bid, ok)))

    # queue_publish → drain (run_publish가 None 반환)
    sched._publish_queue.clear()
    sched.queue_publish("guide-hugo")
    sched._drain_queue()

    assert calls == []  # 정규 schedule 경로에서도 dispatcher 미호출
    assert tracked == []  # 실패 카운트 없음
    assert sched._publish_queue == []


# ─── 17. no_topics presentation → INFO/NOTICE (quiet) ───

def test_no_topics_presentation_info(tmp_path, monkeypatch):
    spec = problem_registry.PROBLEM_REGISTRY["P01"]
    override = spec.reason_overrides.get("no_topics")
    assert override is not None
    assert override["severity"] == "INFO"
    assert override["threshold"] == "quiet"
    assert override["name_ko"] == "발행 후보 대기"
    # retryable false — action은 refresh 감시
    assert "재발행" not in override.get("action", "")


# ─── 18. unknown no_result → MAJOR 유지 ───

def test_no_result_keeps_major(tmp_path, monkeypatch):
    spec = problem_registry.PROBLEM_REGISTRY["P01"]
    assert spec.severity == "MAJOR"
    assert spec.threshold == "consecutive:3"
    # no_result는 override 대상이 아님
    assert spec.reason_overrides.get("no_result") is None


# ─── 19. dashboard root 1 + symptom 3 표시 ───

def test_dashboard_root_and_symptoms(tmp_path, monkeypatch):
    ops_db = _make_ops_db(tmp_path, monkeypatch)
    # root 1
    events.record_publish_error(
        "guide-hugo", "resource_refresh", "source_refresh_stalled",
        reason="source_refresh_stalled", problem_id="P33",
        relation_type="root", retryable=False, resource_id=CAR_DB_RESOURCE,
    )
    roots = events.get_open_root_incidents()
    assert len(roots) == 1
    root_key = roots[0]["incident_key"]
    # 운영 흐름과 동일: symptom record 시 root_incident_key 연결.
    # stage 를 달리해 incident_key 를 분리 — 3건 모두 동일 stage 면
    # upsert 로 1행으로 합쳐진다.
    for i, stage in enumerate(["result_parse", "generate", "publish"]):
        events.record_publish_error(
            "guide-hugo", stage, f"no_topics {i}",
            reason="no_topics", problem_id="P01", relation_type="symptom",
            retryable=False, root_incident_key=root_key,
        )
    linked = events.get_linked_open_events(root_key)
    # P33 root 자체는 linked에서 제외되므로 symptom 3건
    assert len([e for e in linked if e.get("relation_type") != "root"]) >= 3


# ─── 20. dashboard WAITING 빨간 오류 제외 ───

def test_dashboard_waiting_css_not_red(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    repo_root = Path(__file__).resolve().parent.parent
    css = (repo_root / "ops_dashboard/static/style.css").read_text()
    assert ".state-waiting" in css
    assert "#ffc107" in css  # 노랑 — 빨간 오류 아님
    # candidate_state.html에 state-waiting 클래스 사용
    html = (repo_root / "ops_dashboard/templates/candidate_state.html").read_text()
    assert "state-waiting" in html
    assert "후보 0 · 다음 refresh 대기" in html


# ─── 21. legacy event 렌더링 (relation_type NULL) ───

def test_legacy_event_query(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    # legacy: relation_type 없음(reason='', incident_key 없음)
    conn = sqlite3.connect(str(tmp_path / "ops.db"))
    conn.execute(
        "INSERT INTO publish_error_events "
        "(blog_id, pipeline, stage, problem_id, reason, severity, state, occurred_at, fingerprint) "
        "VALUES ('guide-hugo', 'car', 'result_parse', 'P01', '', 'MAJOR', 'open', "
        "'2026-08-01T00:00:00+00:00', 'legacy-fingerprint')"
    )
    conn.commit()
    conn.close()

    rows_conn = sqlite3.connect(str(tmp_path / "ops.db"))
    rows_conn.row_factory = sqlite3.Row
    rows = events.get_publish_error_events(rows_conn, blog_id="guide-hugo")
    rows_conn.close()
    assert any(r["reason"] == "" for r in rows)  # legacy 정상 조회


# ─── 22. API backward compatibility ───

def test_api_backward_compat(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    events.record_publish_error(
        "guide-hugo", "result_parse", "no_topics",
        reason="no_topics", problem_id="P01", relation_type="symptom",
        retryable=False,
    )
    conn = sqlite3.connect(str(tmp_path / "ops.db"))
    conn.row_factory = sqlite3.Row
    summary = events.get_publish_error_summary(conn)
    assert {"total", "open", "by_problem"} <= set(summary)
    rows = events.get_publish_error_events(conn)
    assert isinstance(rows, list)
    conn.close()


# ─── 23. migration 반복 실행 ───

def test_migration_idempotent(tmp_path, monkeypatch):
    _make_ops_db(tmp_path, monkeypatch)
    events.ensure_schema()
    events.ensure_schema()  # 2회 — 에러 없어야 함
    conn = sqlite3.connect(str(tmp_path / "ops.db"))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    conn.close()
    assert "pipeline_availability" in tables
    assert "resource_health" in tables
    assert "publish_error_events" in tables


# ─── 24. 운영 DB guard ───

def test_prod_db_guard_active():
    """conftest autouse guard가 운영 ops.db 접근을 차단하는지 — OPS_DB_PATH가
    운영 경로로 resolve되면 실패해야 한다."""
    from pathlib import Path
    prod = Path("/Users/twinssn/Projects/5000/ops_dashboard/ops.db")
    from shared import publish_error_events as _events
    resolved = Path(_events.OPS_DB_PATH).resolve()
    # conftest guard와 동일 검증 — 테스트 러너에서 OPS_DB_PATH가 tmp로 교체되어야 함
    assert resolved != prod.resolve(), "테스트가 운영 ops.db를 가리킴"