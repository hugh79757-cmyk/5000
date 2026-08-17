"""Phase 62-01 — ValidationResult 계약 테스트 (V01~V07).

All tests are unit/fixture based. No DB, network, publisher, deployer access.
"""

import json

from shared.validation_result import (
    ValidationIssue,
    ValidationResult,
    from_legacy_issues,
    from_preflight,
)


# --- V01: 계약 기본값 (report-only) ---
def test_V01_contract_create_default_report_only():
    r = ValidationResult(passed=True)
    assert r.block is False  # report-only 기본값
    assert r.scope == "global"
    assert r.family is None
    assert r.blog_id is None
    assert r.issues == []


# --- V02: to_legacy preflight 구조 + JSON 직렬화 ---
def test_V02_to_legacy_preflight_shape():
    r = ValidationResult(
        passed=False,
        issues=[
            ValidationIssue("CRITICAL", "R01", "msg1"),
            ValidationIssue("WARNING", "validate_post", "msg2"),
        ],
        block=False,
    )
    legacy = r.to_legacy()
    assert set(legacy.keys()) == {"blocked", "violations", "reason"}
    assert legacy["blocked"] is False
    assert legacy["reason"] == "validation_failed"
    assert legacy["violations"] == [
        {"check": "R01", "severity": "CRITICAL", "detail": "msg1"},
        {"check": "validate_post", "severity": "WARNING", "detail": "msg2"},
    ]
    # JSON 왕복 (dispatcher JSON 계약 불변)
    roundtripped = json.loads(json.dumps(legacy))
    assert roundtripped == legacy


# --- V03: [] → passed=True ---
def test_V03_from_legacy_issues_empty_list_passed():
    r = from_legacy_issues([], blog_id="test-hugo")
    assert r.passed is True
    assert r.issues == []
    assert r.blog_id == "test-hugo"


# --- V04: severity 접두사 매핑 ---
def test_V04_severity_prefix():
    r = from_legacy_issues(["[ERROR] x", "[WARNING] y", "z"])
    assert r.passed is False
    assert [i.severity for i in r.issues] == ["CRITICAL", "WARNING", "WARNING"]
    assert [i.msg for i in r.issues] == ["[ERROR] x", "[WARNING] y", "z"]
    assert all(i.check == "validate_post" for i in r.issues)


# --- V05: (ok, errors) 튜플 ---
def test_V05_tuple_ok_errors():
    r = from_legacy_issues((True, []))
    assert r.passed is True
    r2 = from_legacy_issues((False, ["a", "b"]))
    assert r2.passed is False
    assert len(r2.issues) == 2
    assert all(i.severity == "WARNING" for i in r2.issues)
    assert [i.msg for i in r2.issues] == ["a", "b"]


# --- V06: dict {passed, issues} 형태 ---
def test_V06_passed_dict():
    r = from_legacy_issues(
        {
            "passed": False,
            "issues": [
                {"severity": "CRITICAL", "check": "c1", "msg": "m1"},
                {"severity": "INFO", "check": "c2", "msg": "m2"},
            ],
        },
        blog_id="b-hugo",
    )
    assert r.passed is False
    assert [(i.severity, i.check, i.msg) for i in r.issues] == [
        ("CRITICAL", "c1", "m1"),
        ("INFO", "c2", "m2"),
    ]
    assert r.blog_id == "b-hugo"


# --- V07: from_preflight blocked 보존 ---
def test_V07_from_preflight_preserves_block():
    preflight = {
        "blocked": True,
        "violations": [
            {"slug": "s1", "rule_id": "R01", "severity": "CRITICAL", "detail": "d1"},
        ],
    }
    r = from_preflight(preflight, blog_id="b-hugo")
    assert r.passed is False
    assert r.block is True  # 기존 차단 게이트 의미 보존
    assert len(r.issues) == 1
    assert r.issues[0].check == "R01"
    assert r.issues[0].msg == "s1: d1"

    # 미차단 preflight
    r2 = from_preflight({"blocked": False, "violations": []}, blog_id="b-hugo")
    assert r2.passed is True
    assert r2.block is False
