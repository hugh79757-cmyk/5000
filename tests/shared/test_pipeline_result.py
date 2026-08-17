"""PR-CAP-1 tests — Pipeline Result Contract (T01–T16).

All tests are unit/fixture based. Operational DB, network, publisher, and
deployer are mocked/avoided. No live content is generated or published.
"""
import sqlite3
import types

import pytest

from shared.pipeline_result import (
    PipelineStatus,
    PipelineResult,
    from_legacy,
    from_exception,
)


# T01 — contract creation + both serializations
def test_T01_result_contract_create_and_serialize():
    r = PipelineResult(
        status=PipelineStatus.SUCCESS,
        pipeline="car",
        blog="ev-hugo",
        stage="publish",
        reason="",
        evidence="slug=ev6-x",
    )
    d = r.to_dict()
    assert d["status"] == "SUCCESS"
    assert d["pipeline"] == "car"
    assert d["blog"] == "ev-hugo"
    leg = r.to_legacy_dict()
    assert leg["success"] is True
    assert leg["reason"] == ""


# T02 — forbidden combinations rejected; adapter never propagates
def test_T02_forbidden_combination_rejected():
    bad = [
        dict(status=PipelineStatus.SUCCESS, publish_blocked=True),
        dict(status=PipelineStatus.WAITING_FOR_CANDIDATES, retryable=True),
        dict(status=PipelineStatus.FAILED_PERMANENT, retryable=True),
        dict(status=PipelineStatus.BLOCKED_QUALITY, publish_blocked=False),
    ]
    for kw in bad:
        with pytest.raises(ValueError):
            PipelineResult(**kw)
    # adapter must never raise into caller for any known legacy shape
    for raw in [
        {"success": True, "reason": "x"},
        {"success": False, "reason": "no_topics"},
        {"success": False, "reason": "no_data"},
        {"success": False, "reason": "duplicate_source_id"},
    ]:
        res = from_legacy(raw, {"pipeline": "car", "blog": "b", "stage": ""})
        assert isinstance(res, PipelineResult)


# T03 — legacy bool compatibility
def test_T03_legacy_bool_compat():
    t = from_legacy(True, {})
    assert t.status == PipelineStatus.SUCCESS
    assert t.to_legacy_dict()["success"] is True
    f = from_legacy(False, {})
    assert f.status == PipelineStatus.FAILED_TRANSIENT
    assert f.to_legacy_dict()["success"] is False


# T04 — legacy dict compatibility; original extras preserved
def test_T04_legacy_dict_compat():
    raw = {"success": False, "reason": "generation_failed", "url": "http://x", "article_id": 5}
    res = from_legacy(raw, {"pipeline": "car", "blog": "ev-hugo", "stage": ""})
    assert res.status == PipelineStatus.FAILED_TRANSIENT
    assert res.retryable is True
    leg = res.to_legacy_dict()
    assert leg["reason"] == "generation_failed"
    assert leg["url"] == "http://x"
    assert leg["article_id"] == 5


# T05 — legacy None compatibility
def test_T05_legacy_none_compat():
    res = from_legacy(None, {})
    assert res.status == PipelineStatus.FAILED_TRANSIENT
    assert res.reason == "no_result"
    assert res.to_legacy_dict()["success"] is False


# T06 — unknown return type -> safe fallback, never raises
def test_T06_unknown_return_safe_fallback():
    res = from_legacy(12345, {})
    assert isinstance(res, PipelineResult)
    leg = res.to_legacy_dict()
    assert leg["success"] is False
    assert leg["reason"] == "unknown_return_type"
    res2 = from_legacy({"foo": "bar"}, {})
    assert isinstance(res2, PipelineResult)


# T07 — exception boundary adapter (unit only)
def test_T07_exception_to_failed_result_boundary():
    res = from_exception(RuntimeError("boom"), {"pipeline": "car", "blog": "b"})
    assert res.status == PipelineStatus.FAILED_TRANSIENT
    assert res.reason == "exception:RuntimeError"
    assert res.retryable is True


# T08 — subprocess exit-code parity (contract level): legacy dict is JSON-serializable
#       with success/reason preserved, so dispatcher still prints valid JSON and
#       exits 0.
def test_T08_subprocess_exit_code_parity():
    import json

    res = from_legacy(
        {"success": True, "reason": "", "url": "u"},
        {"pipeline": "car", "blog": "b"},
    )
    out = json.loads(json.dumps(res.to_legacy_dict()))
    assert out["success"] is True
    assert "reason" in out


# T09 — success publish path parity: success:True reaches scheduler parse
def test_T09_success_publish_path_parity():
    raw = {"success": True, "url": "https://x/posts/s/", "file_path": "/p/i.md", "article_id": 7, "deployed": True}
    res = from_legacy(raw, {"pipeline": "car", "blog": "ev-hugo"})
    leg = res.to_legacy_dict()
    assert leg["success"] is True
    assert leg["url"] == "https://x/posts/s/"


# T10 — no_topics path parity: reason verbatim; dispatcher WAITING branch intact
def test_T10_no_topics_path_parity():
    res = from_legacy(
        {"success": False, "reason": "no_topics"},
        {"pipeline": "car", "blog": "ev-hugo"},
    )
    assert res.reason == "no_topics"
    assert res.status == PipelineStatus.WAITING_FOR_CANDIDATES
    assert res.to_legacy_dict()["reason"] == "no_topics"


# T11 — deploy-failure path parity: success:True preserved (unchanged behavior)
def test_T11_deploy_failure_path_parity():
    raw = {"success": True, "deployed": False, "deploy_error": "x"}
    res = from_legacy(raw, {"pipeline": "car", "blog": "ev-hugo"})
    assert res.to_legacy_dict()["success"] is True
    assert res.status == PipelineStatus.FAILED_TRANSIENT


# T12 — failure_count delta parity: mapping drives dispatcher increment decision
def test_T12_failure_count_delta_parity():
    no_topics = from_legacy({"success": False, "reason": "no_topics"}, {})
    no_data = from_legacy({"success": False, "reason": "no_data"}, {})
    assert no_topics.retryable is False  # dispatcher does NOT increment for no_topics
    assert no_data.retryable is True     # dispatcher increments for no_data


# T13 — cooldown delta parity: None -> no_result (dispatcher sets cooldown pre-normalization)
def test_T13_cooldown_delta_parity():
    res = from_legacy(None, {})
    assert res.reason == "no_result"


# T14 + T15 — real dispatch side-effect & operational-DB isolation parity.
# All side-effecting internals are monkeypatched; sqlite3.connect is stubbed so
# no operational DB file is ever touched. We assert the call pattern is
# identical to pre-change behavior (1 ledger insert on success, 1 failure +
# 1 increment on failure) and that pipeline_status is added without altering
# success/reason.
def test_T14_T15_dispatch_sideeffect_parity(monkeypatch):
    import dispatcher
    import shared.publish_error_events as pee

    calls = {"ledger": 0, "failure": 0, "increment": 0, "cooldown": 0, "deploy": 0}

    def fake_record_ledger(blog_id):
        calls["ledger"] += 1

    def fake_record_failure(blog_id, reason, detail=""):
        calls["failure"] += 1

    def fake_increment(blog_id, problem_id=None):
        calls["increment"] += 1
        return 1

    def fake_set_cooldown(blog_id):
        calls["cooldown"] += 1

    def fake_build_deploy(blog_id):
        calls["deploy"] += 1
        return True

    def fake_reset(blog_id):
        return None

    def fake_close(blog_id):
        return None

    def fake_trigger(blog_id):
        return None

    # Stub sqlite3 so no operational DB file is opened.
    class _FakeConn:
        def close(self):
            pass

    def _fake_connect(*a, **k):
        return _FakeConn()

    monkeypatch.setattr(sqlite3, "connect", _fake_connect)
    monkeypatch.setattr(pee, "close_publish_error_event", lambda *a, **k: 0)

    monkeypatch.setattr(dispatcher, "_record_ledger", fake_record_ledger)
    monkeypatch.setattr(dispatcher, "_record_failure", fake_record_failure)
    monkeypatch.setattr(dispatcher, "_increment_failure_count", fake_increment)
    monkeypatch.setattr(dispatcher, "_set_cooldown", fake_set_cooldown)
    monkeypatch.setattr(dispatcher, "_build_and_deploy_central", fake_build_deploy)
    monkeypatch.setattr(dispatcher, "_reset_failure_count", fake_reset)
    monkeypatch.setattr(dispatcher, "_reset_extended_failure_keys", fake_reset)
    monkeypatch.setattr(dispatcher, "_close_publish_failure_events", fake_close)
    monkeypatch.setattr(dispatcher, "_trigger_post_publish_checks", fake_trigger)
    monkeypatch.setattr(dispatcher, "_tg_error", lambda *a, **k: None)
    monkeypatch.setattr(dispatcher, "_record_summary_event", lambda *a, **k: None)
    monkeypatch.setattr(dispatcher, "_debounce_push", lambda *a, **k: False)
    monkeypatch.setattr(dispatcher, "init_debounce_tables", lambda *a, **k: None)
    monkeypatch.setattr(dispatcher, "init_daily_summary_tables", lambda *a, **k: None)
    monkeypatch.setattr(dispatcher, "_is_duplicate", lambda blog_id: False)
    monkeypatch.setattr(dispatcher, "_is_on_cooldown", lambda blog_id: False)
    monkeypatch.setattr(dispatcher, "_is_on_daily_cooldown", lambda blog_id: False)
    monkeypatch.setattr(dispatcher, "acquire_publish_slot", lambda blog_id: "slot-1")
    monkeypatch.setattr(dispatcher, "get_inherited_slot_info", lambda: None)
    monkeypatch.setattr(dispatcher, "_deploy_log_hint", lambda blog_id: "")
    monkeypatch.setattr(dispatcher, "lookup_reason", lambda reason: None)
    monkeypatch.setattr(
        dispatcher, "get_monitor",
        lambda: types.SimpleNamespace(report=lambda *a, **k: None),
    )

    # ---- success path ----
    monkeypatch.setattr(dispatcher, "_run_pipeline", lambda cfg: {
        "success": True, "reason": "", "url": "u", "file_path": "f",
        "article_id": 1, "deployed": True,
    })
    res_ok = dispatcher.dispatch("ev-hugo")
    assert isinstance(res_ok, dict)
    assert res_ok.get("success") is True
    assert res_ok.get("pipeline_status") == "SUCCESS"
    assert calls["ledger"] == 1
    assert calls["increment"] == 0  # success resets, never increments

    # ---- failure path ----
    monkeypatch.setattr(dispatcher, "_run_pipeline", lambda cfg: {
        "success": False, "reason": "no_data",
    })
    res_fail = dispatcher.dispatch("ev-hugo")
    assert res_fail.get("success") is False
    assert res_fail.get("pipeline_status") == "FAILED_TRANSIENT"
    assert calls["failure"] == 1
    assert calls["increment"] == 1  # no_data increments failure_count


# T16 — no external call: adapters never invoke publisher/deploy/r2/ai
def test_T16_no_external_call_fixture(monkeypatch):
    import shared.publisher as publisher
    import shared.publishers.deploy as deploy

    def _boom(*a, **k):
        raise AssertionError("real external call executed")

    monkeypatch.setattr(publisher, "publish", _boom)
    monkeypatch.setattr(deploy, "deploy_site", _boom)

    # Constructing adapters must not reach those call sites.
    from_legacy({"success": True, "reason": ""}, {"pipeline": "car", "blog": "b"})
    from_legacy(None, {})
    from_exception(RuntimeError("x"))
    PipelineResult(status=PipelineStatus.SUCCESS)
