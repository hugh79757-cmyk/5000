"""Wave-0 tests for shared/config_validator.py unified schema (Phase 61, D-04).

These tests verify the standard-schema validation (PIPELINE-STANDARD §4) is additive
and non-blocking: required fields are flagged, standard fields accepted, branch-specific
extension fields preserved (not rejected), and managed_by: pipeline accepted.
"""

import pytest

from shared.config_validator import (
    EXTENSION_BLOG_FIELDS,
    STANDARD_BLOG_FIELDS,
    validate_blog_entry_standard,
    validate_managed_mode,
)

_REQUIRED = {"id": "rap-hugo", "pipeline": "rap", "platform": "hugo"}


class TestRequiredFields:
    def test_required_fields_flagged(self):
        issues = validate_blog_entry_standard({"name": "부동산", "platform": "hugo"})
        errs = " ".join(issues["errors"])
        assert "id" in errs
        assert "pipeline" in errs

    def test_complete_entry_has_no_errors(self):
        issues = validate_blog_entry_standard({**_REQUIRED, "name": "부동산"})
        assert issues["errors"] == []


class TestStandardFieldsAccepted:
    def test_standard_fields_validate_cleanly(self):
        blog = {
            **_REQUIRED,
            "name": "부동산 시세",
            "domain": "apt.informationhot.kr",
            "daily_quota": 10,
            "schedule": {"times": ["07:50"]},
            "status": "active",
            "managed_by": "pipeline",
        }
        issues = validate_blog_entry_standard(blog)
        assert issues["errors"] == []
        for field in STANDARD_BLOG_FIELDS:
            assert field in blog


class TestOptionalExtensionFieldsPreserved:
    def test_extension_fields_accepted(self):
        blog = {
            **_REQUIRED,
            "cf_project": "rap-hugo",
            "ga4_property": "G-XXXX",
            "blogger_blog_id": "123",
            "funnel_stage": "landing",
            "language": "ko",
        }
        issues = validate_blog_entry_standard(blog)
        assert issues["errors"] == []
        unknown = " ".join(issues["warnings"])
        for key in ("cf_project", "ga4_property", "blogger_blog_id", "funnel_stage", "language"):
            assert key in EXTENSION_BLOG_FIELDS, f"{key} not in extension set"
            assert key not in unknown, f"{key} flagged unknown"

    def test_unknown_key_is_warning_not_error(self):
        """Unknown keys are warnings (non-blocking, backward compat per D-08)."""
        blog = {**_REQUIRED, "some_future_key": 1}
        issues = validate_blog_entry_standard(blog)
        assert issues["errors"] == []
        assert "some_future_key" in " ".join(issues["warnings"])


class TestManagedByPipeline:
    def test_managed_by_pipeline_accepted(self):
        assert validate_managed_mode({**_REQUIRED, "managed_by": "pipeline"}) == []

    def test_managed_by_future_value_is_warning(self):
        warnings = validate_managed_mode({**_REQUIRED, "managed_by": "manual"})
        assert len(warnings) == 1

    def test_no_managed_by_no_warning(self):
        assert validate_managed_mode(_REQUIRED) == []
