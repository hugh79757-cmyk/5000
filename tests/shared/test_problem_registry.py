import re
from pathlib import Path

import pytest

from shared.problem_registry import (
    PROBLEM_REGISTRY,
    lookup_problem,
    lookup_reason,
)

_DEPLOY_PATHS = (
    Path(__file__).resolve().parents[2]
    / ".planning"
    / "phase-58-publish-problem-telegram-alerting"
    / "DEPLOY-PATHS.md"
)

_REASON_TOKEN = re.compile(r"[a-z][a-z0-9_]+")
_TUPLE_REASON = re.compile(r'^\(("[a-z_]+",?\s*)+\)$')


def _load_inventory_reasons(doc_path):
    text = Path(doc_path).read_text(encoding="utf-8")
    start = text.index("## Section C")
    end = text.index("## Section D")
    section = text[start:end]
    reasons = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        first = cells[0].replace("`", "")
        if _TUPLE_REASON.fullmatch(first):
            reasons.extend(re.findall(r'"([a-z_]+)"', first))
            continue
        token = first.strip()
        if _REASON_TOKEN.fullmatch(token):
            reasons.append(token)
    return reasons


class TestRegistryTotals:
    def test_total_specs_is_25(self):
        assert len(PROBLEM_REGISTRY) == 25

    def test_severity_counts_among_24_problems(self):
        problems = [s for s in PROBLEM_REGISTRY.values() if s.problem_id != "unknown_failure"]
        assert len(problems) == 24
        assert sum(1 for s in problems if s.severity == "CRITICAL") == 6
        assert sum(1 for s in problems if s.severity == "MAJOR") == 12
        assert sum(1 for s in problems if s.severity == "MINOR") == 6

    def test_unknown_failure_minor_makes_total_minor_7(self):
        assert sum(1 for s in PROBLEM_REGISTRY.values() if s.severity == "MINOR") == 7

    def test_registry_contains_all_p01_to_p24(self):
        ids = {s.problem_id for s in PROBLEM_REGISTRY.values()}
        assert {f"P{i:02d}" for i in range(1, 25)} <= ids


class TestReasonCoverage:
    def test_inventory_loader_parses_expected_reasons(self):
        reasons = set(_load_inventory_reasons(_DEPLOY_PATHS))
        for expected in (
            "no_result",
            "stap_subprocess_error",
            "duplicate_title",
            "similar_title",
            "duplicate_slug",
            "dispatch_returned_none",
        ):
            assert expected in reasons, f"missing from parsed inventory: {expected}"
        assert len(reasons) == 34

    def test_every_inventory_reason_resolves_to_exactly_one_spec(self):
        reasons = set(_load_inventory_reasons(_DEPLOY_PATHS))
        assert len(reasons) > 0
        for reason in reasons:
            assert lookup_reason(reason) is not None, f"inventory reason unmapped: {reason}"
            owners = [s for s in PROBLEM_REGISTRY.values() if reason in s.reason_keys]
            assert len(owners) == 1, f"reason mapped to {len(owners)} specs: {reason}"

    def test_no_reason_key_shared_across_specs(self):
        owner_counts = {}
        for spec in PROBLEM_REGISTRY.values():
            for key in spec.reason_keys:
                owner_counts[key] = owner_counts.get(key, 0) + 1
        dup = {k: c for k, c in owner_counts.items() if c > 1}
        assert dup == {}

    def test_known_inventory_mappings(self):
        assert lookup_reason("no_result").problem_id == "P01"
        assert lookup_reason("similar_title").problem_id == "P03"
        assert lookup_reason("stap_timeout").problem_id == "P20"
        assert lookup_reason("config_error").problem_id == "P21"
        assert lookup_reason("duplicate_slug").problem_id == "P16"


class TestLookup:
    def test_lookup_reason_unknown_returns_none(self):
        assert lookup_reason("no_such_reason") is None

    def test_lookup_problem_unknown_returns_none(self):
        assert lookup_problem("P99") is None

    def test_lookup_problem_known_returns_spec(self):
        assert lookup_problem("P01") is not None


class TestAlertTemplate:
    def test_all_templates_render_with_full_context_within_500_chars(self):
        context = {
            "blog_id": "test-hugo",
            "problem_id": "PXX",
            "name_ko": "테스트 문제",
            "severity": "MAJOR",
            "phase": "result_parse",
            "pattern": "테스트 패턴",
            "matched": "테스트 매치",
            "consecutive": 3,
            "action": "테스트 조치",
        }
        for spec in PROBLEM_REGISTRY.values():
            rendered = spec.alert_template.format(**context)
            assert len(rendered) <= 500, f"{spec.problem_id}: {len(rendered)} chars"


class TestUnknownFailureSpec:
    def test_unknown_failure_spec_exists_with_quiet_threshold(self):
        spec = lookup_problem("unknown_failure")
        assert spec is not None
        assert spec.threshold == "quiet"
        assert spec.severity == "MINOR"
        assert spec.reason_keys == ()


# Phase 61 (Plan 61-02): previously unregistered reason keys must map to concrete P-codes.
# Corrected per PIPELINE-STANDARD §5.2 + Review #5: `language_error` is ALREADY registered
# as P12 — it is NOT in this set. The 10 genuinely-unregistered reasons are:
_UNREGISTERED_REASONS = [
    "daily_quota_reached",
    "expired_service",
    "generation_failed",
    "no_subscription_data",
    "no_topic",
    "no_topics",
    "no_trade_data",
    "prompt_not_found",
    "publish_failed",
    "write_failed",
]


class TestPhase61UnregisteredReasons:
    def test_language_error_already_registered(self):
        """Review #5: language_error is already P12 — must NOT be added again."""
        spec = lookup_reason("language_error")
        assert spec is not None
        assert spec.problem_id == "P12"

    def test_ten_unregistered_reasons_now_recognized(self):
        for reason in _UNREGISTERED_REASONS:
            spec = lookup_reason(reason)
            assert spec is not None, f"{reason} still unmapped"
            assert spec.problem_id != "unknown_failure", f"{reason} falls to unknown_failure"

    def test_each_new_reason_maps_to_exactly_one_spec(self):
        for reason in _UNREGISTERED_REASONS:
            owners = [s for s in PROBLEM_REGISTRY.values() if reason in s.reason_keys]
            assert len(owners) == 1, f"{reason} mapped to {len(owners)} specs"

    def test_existing_24_reason_mappings_unchanged(self):
        """No regression in the existing P01..P24 reason mappings."""
        assert lookup_reason("no_result").problem_id == "P01"
        assert lookup_reason("deploy_error").problem_id == "P04"
        assert lookup_reason("content_quality_gate").problem_id == "P12"
        assert lookup_reason("stap_timeout").problem_id == "P20"
        assert lookup_reason("quota_met").problem_id == "P17"
        assert lookup_reason("event_expired").problem_id == "P19"
