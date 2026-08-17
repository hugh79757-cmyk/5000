"""Phase 62-02 — 규칙 계층 로딩/해석 테스트 (H01~H10).

All tests are unit/fixture based. No DB (explicit fake conn only), no network,
no publisher/deployer/r2/ai access.
"""

import pytest
import yaml

from shared.paths import CONFIG_DIR
from shared.rule_hierarchy import (
    DEFAULT_RULES_YAML,
    RuleSpec,
    load_blog_rules,
    load_rules,
    resolve_rules,
    resolve_rules_for_blog,
)


# --- H01: 실 config/rules.yaml 로드 ---
def test_H01_load_rules_reads_rules_yaml():
    rules = load_rules()
    loaded_codes = [r.code for r in rules]
    for expected in ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08",
                     "R09", "R10", "R11", "R12"]:
        assert expected in loaded_codes, f"{expected} 누락"
    # scope 미지정 → 기본 "global"
    assert all(r.scope == "global" for r in rules)
    # 기존 family="validation" 은 category — brand 로 해석되지 않음
    assert all(r.family is None for r in rules)


# --- H02: family scope fixture ---
def test_H02_load_rules_family_scope_fixture(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text(
        "rules:\n"
        "- code: F1\n"
        "  severity: CRITICAL\n"
        "  scope: family\n"
        "  family: etap\n"
        "  check_fn: _check_f1\n",
        encoding="utf-8",
    )
    rules = load_rules(str(p))
    assert len(rules) == 1
    assert rules[0].code == "F1"
    assert rules[0].scope == "family"
    assert rules[0].family == "etap"
    assert rules[0].check == "_check_f1"


# --- H03: family scope without family → ValueError ---
def test_H03_family_scope_without_family_raises(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text(
        "rules:\n"
        "- code: F1\n"
        "  severity: CRITICAL\n"
        "  scope: family\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_rules(str(p))


# --- H04: global 전용 해석 ---
def test_H04_resolve_global_only():
    rules = [
        RuleSpec("G1", "CRITICAL", scope="global"),
        RuleSpec("G2", "WARNING", scope="global"),
    ]
    out = resolve_rules(rules, brand="cap")
    assert [r.code for r in out] == ["G1", "G2"]


# --- H05: family 필터 ---
def test_H05_resolve_family_filter():
    rules = [
        RuleSpec("F1", "CRITICAL", scope="family", family="etap"),
        RuleSpec("G1", "WARNING", scope="global"),
    ]
    etap = resolve_rules(rules, brand="etap")
    assert "F1" in [r.code for r in etap]
    cap = resolve_rules(rules, brand="cap")
    assert "F1" not in [r.code for r in cap]
    assert "G1" in [r.code for r in cap]


# --- H06: family 가 해당 brand 에서 global 대체, 타 brand 는 global 유지 ---
def test_H06_priority_family_over_global():
    rules = [
        RuleSpec("X", "WARNING", scope="global"),
        RuleSpec("X", "CRITICAL", scope="family", family="etap"),
    ]
    etap = {r.code: r for r in resolve_rules(rules, brand="etap")}
    assert etap["X"].severity == "CRITICAL"  # family 가 대체
    cap = {r.code: r for r in resolve_rules(rules, brand="cap")}
    assert cap["X"].severity == "WARNING"  # global 유지


# --- H07: blog > family > global 우선순위 ---
def test_H07_priority_blog_over_family_global():
    rules = [
        RuleSpec("X", "WARNING", scope="global"),
        RuleSpec("X", "CRITICAL", scope="family", family="etap"),
        RuleSpec("Y", "WARNING", scope="global"),
    ]
    blog_overrides = {
        "etap-blog1": [RuleSpec("X", "INFO", scope="blog", check="b1")],
    }
    out = {r.code: r for r in resolve_rules(
        rules, brand="etap", blog_id="etap-blog1", blog_overrides=blog_overrides
    )}
    assert out["X"].severity == "INFO"  # blog 가 대체
    assert out["Y"].severity == "WARNING"  # global 유지
    # blog_id 없음 → blog 계층 무시
    out2 = {r.code: r for r in resolve_rules(rules, brand="etap")}
    assert out2["X"].severity == "CRITICAL"  # family


# --- H08: resolve_rules_for_blog 가 get_blog_brand 래핑 ---
def test_H08_resolve_for_blog_wraps_get_blog_brand(monkeypatch):
    import ops_dashboard.db as db_mod

    def fake_get_blog_brand(conn, blog_id):
        assert blog_id == "cuap-hugo"
        return "cuap"

    monkeypatch.setattr(db_mod, "get_blog_brand", fake_get_blog_brand)
    rules = [
        RuleSpec("G1", "WARNING", scope="global"),
        RuleSpec("F1", "CRITICAL", scope="family", family="cuap"),
        RuleSpec("F2", "CRITICAL", scope="family", family="etap"),
    ]
    out = resolve_rules_for_blog(rules, conn="fake-conn", blog_id="cuap-hugo")
    codes = [r.code for r in out]
    assert "G1" in codes and "F1" in codes
    assert "F2" not in codes  # cuap brand → etap family 배제


# --- H09: load_blog_rules 빈/존재 ---
def test_H09_load_blog_rules_empty_and_present():
    assert load_blog_rules({}) == []
    assert load_blog_rules({"id": "x-hugo", "pipeline": "gap"}) == []
    cfg = {
        "quality_rules": [
            {"code": "B1", "severity": "WARNING", "scope": "blog"},
            {"code": "B2", "severity": "CRITICAL", "scope": "blog", "check": "custom_fn"},
        ],
    }
    out = load_blog_rules(cfg)
    assert [r.code for r in out] == ["B1", "B2"]
    assert out[0].scope == "blog"
    assert out[1].check == "custom_fn"


# --- H10: 외부 호출 부작용 없음 (T16 패턴) ---
def test_H10_no_external_call(monkeypatch):
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
    # r2/ai
    for mod_name in ("shared.r2_uploader", "shared.ai_writer"):
        try:
            mod = __import__(mod_name, fromlist=["*"])
        except Exception:
            continue
        for attr in dir(mod):
            if attr.startswith("_"):
                continue
            target = getattr(mod, attr)
            if callable(target):
                monkeypatch.setattr(mod, attr, _boom, raising=False)

    # 로딩/해석 — DB(명시적 conn 제외)/네트워크/배포 부작용 없이 완료
    rules = load_rules()
    assert len(rules) > 0
    out = resolve_rules(rules, brand="cap")
    assert isinstance(out, list)
    blog_rules = load_blog_rules({})
    assert blog_rules == []
