"""Phase 62-03 — report-only 배선 + incident 계약 테스트 (I01~I08).

All tests are unit/fixture based. No DB, network, publisher, deployer access.
"""

import json

from shared.pipeline_result import PipelineStatus
from shared.validation_result import (
    ValidationIssue,
    ValidationResult,
)


def _make_result(
    passed=False,
    issues=None,
    *,
    scope="global",
    family=None,
    block=False,
):
    return ValidationResult(
        passed=passed,
        issues=issues or [],
        scope=scope,
        family=family,
        block=block,
    )


# --- I01: to_incident 3요소 존재 ---
def test_I01_to_incident_three_elements():
    r = _make_result(
        passed=False,
        issues=[ValidationIssue("CRITICAL", "R01", "m1")],
    )
    inc = r.to_incident(reason_key="validation", stage="post_publish")
    assert set(inc.keys()) == {"reason", "stage", "detail", "pcode"}
    assert inc["reason"] == "validation"
    assert inc["stage"] == "post_publish"
    assert inc["detail"] == "[CRITICAL] m1"
    assert inc["pcode"] == "P15"  # lookup_reason("validation") → P15


# --- I02: detail sanitize (500자 초과/개행/비밀) ---
def test_I02_detail_sanitized():
    long_msg = "x" * 600
    newline_msg = "line1\nline2"
    secret_msg = "key=abc api_key=SECRET123 done"
    r = _make_result(
        passed=False,
        issues=[
            ValidationIssue("CRITICAL", "c1", long_msg),
            ValidationIssue("WARNING", "c2", newline_msg),
            ValidationIssue("WARNING", "c3", secret_msg),
        ],
    )
    inc = r.to_incident(reason_key="validation", stage="test")
    detail = inc["detail"]
    assert len(detail) <= 500  # 잘림
    assert "\n" not in detail  # 개행 → 공백
    assert "SECRET123" not in detail  # 비밀 마스킹
    assert "[redacted:evidence]" in detail


# --- I03: pcode 등록/미등록 ---
def test_I03_pcode_registered_and_unregistered():
    r = _make_result(passed=False, issues=[ValidationIssue("WARNING", "c1", "m")])
    # 등록된 reason_key("validation" → P15)
    assert r.to_incident("validation", "s")["pcode"] == "P15"
    # 미등록 reason_key → pcode="", 예외 없음 (standard_violation 은 registry 미등록)
    inc = r.to_incident("standard_violation", "s")
    assert inc["pcode"] == ""
    assert inc["reason"] == "standard_violation"


# --- I04: report-only 기본값 + 게이트 의미 보존 ---
def test_I04_report_only_default_and_gate_preserved():
    default_r = _make_result(passed=True)
    assert default_r.block is False  # report-only 기본값
    # 차단 게이트 의미 보존: block=True 는 발신 측이 명시해야 함
    blocked_r = _make_result(passed=False, block=True)
    legacy = blocked_r.to_legacy()
    assert legacy["blocked"] is True
    assert legacy["reason"] == "validation_failed"


# --- I05: as_pipeline_extra additive (success/reason 불변 + JSON 왕복) ---
def test_I05_as_pipeline_extra_additive():
    r = _make_result(
        passed=False,
        issues=[ValidationIssue("CRITICAL", "R01", "m1")],
        scope="family",
        family="etap",
    )
    base = {"success": True, "reason": ""}
    merged = {**base, **r.as_pipeline_extra()}
    # success/reason 최상위 키 불변
    assert merged["success"] is True
    assert merged["reason"] == ""
    # validation 키 존재
    v = merged["validation"]
    assert v["passed"] is False
    assert v["issues"] == [{"severity": "CRITICAL", "check": "R01", "msg": "m1"}]
    assert v["scope"] == "family"
    assert v["family"] == "etap"
    assert v["block"] is False
    # JSON 왕복
    assert json.loads(json.dumps(merged)) == merged


# --- I06: report-only 가 절대 BLOCKED_QUALITY 로 매핑되지 않음 ---
def test_I06_report_only_never_blocked_quality():
    r = _make_result(
        passed=False,
        issues=[ValidationIssue("WARNING", "R01", "m1")],
        block=False,  # report-only
    )
    extra = r.as_pipeline_extra()
    assert extra["validation"]["block"] is False
    # report-only 는 PipelineStatus.BLOCKED_QUALITY 나 publish_blocked=True 로 매핑 금지
    assert PipelineStatus.BLOCKED_QUALITY.value not in str(extra)
    # to_legacy 의 blocked 도 False 유지
    assert r.to_legacy()["blocked"] is False


# --- I07: incident dict JSON 직렬화 가능 ---
def test_I07_incident_dict_json_serializable():
    r = _make_result(
        passed=False,
        issues=[ValidationIssue("CRITICAL", "R01", "한글 메시지")],
    )
    inc = r.to_incident("validation", "post_publish")
    rt = json.loads(json.dumps(inc))
    assert rt == inc
    assert rt["detail"] == "[CRITICAL] 한글 메시지"


# --- I08: 외부 호출 부작용 없음 (T16 패턴) ---
def test_I08_no_external_call(monkeypatch):
    import shared.publisher
    import shared.publishers.deploy

    def _boom(*args, **kwargs):
        raise AssertionError("real external call executed")

    for mod in (shared.publisher, shared.publishers.deploy):
        for attr in dir(mod):
            if attr.startswith("_"):
                continue
            target = getattr(mod, attr)
            if callable(target):
                monkeypatch.setattr(mod, attr, _boom, raising=False)

    r = _make_result(
        passed=False,
        issues=[
            ValidationIssue("CRITICAL", "R01", "a"),
            ValidationIssue("WARNING", "R02", "b"),
        ],
    )
    inc = r.to_incident("validation", "test_stage")
    assert inc["reason"] == "validation"
    extra = r.as_pipeline_extra()
    assert extra["validation"]["passed"] is False
