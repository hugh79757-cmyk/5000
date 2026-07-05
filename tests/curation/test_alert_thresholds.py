"""Unit tests for alert_thresholds.py — ThresholdChecker and cooldown."""
import time
from unittest.mock import patch
from shared.alert_thresholds import ThresholdChecker, DEFAULT_ALERT_CONFIG, BLOG_OVERRIDES


def test_get_config_merges_defaults_override_instance():
    checker = ThresholdChecker(blog_config={"pet-hugo": {"consecutive_failures": 2}})
    cfg = checker.get_config("pet-hugo")
    # Instance config overrides static BLOG_OVERRIDES and default
    assert cfg["consecutive_failures"] == 2
    # Default values present
    assert "dry_run" in cfg
    assert "cooldown_minutes" in cfg


def test_get_config_uses_blog_overrides():
    checker = ThresholdChecker()
    cfg = checker.get_config("pet-hugo")
    # pet-hugo has override of 2 consecutive failures
    assert cfg["consecutive_failures"] == 2
    # Also check health-hugo has 5
    cfg2 = checker.get_config("health-hugo")
    assert cfg2["consecutive_failures"] == 5


def test_check_consecutive_failures_against_threshold():
    checker = ThresholdChecker()
    # default threshold 3
    assert checker.check_consecutive_failures("unknown-blog", 2) is False
    assert checker.check_consecutive_failures("unknown-blog", 3) is True
    assert checker.check_consecutive_failures("unknown-blog", 5) is True
    # pet-hugo threshold 2
    assert checker.check_consecutive_failures("pet-hugo", 1) is False
    assert checker.check_consecutive_failures("pet-hugo", 2) is True


def test_check_keyword_streak():
    checker = ThresholdChecker()
    # default keyword_fail_streak 5
    assert checker.check_keyword_streak("unknown-blog", "anykw", 4) is False
    assert checker.check_keyword_streak("unknown-blog", "anykw", 5) is True


def test_cooldown_prevents_duplicate_alerts():
    checker = ThresholdChecker()
    checker._last_alerted["test-blog"] = time.time() - 30*60  # 30 minutes ago (cooldown default 60)
    # Not yet, still within cooldown
    assert checker._in_cooldown("test-blog") is True
    # After enough time passes, cooldown expires
    checker._last_alerted["test-blog"] = time.time() - 70*60  # 70 minutes ago
    assert checker._in_cooldown("test-blog") is False


def test_mark_alerted_sets_timestamp():
    checker = ThresholdChecker()
    before = time.time()
    checker._mark_alerted("test-blog")
    after = time.time()
    ts = checker._last_alerted.get("test-blog")
    assert ts is not None
    assert before <= ts <= after


def test_maybe_alert_returns_none_when_disabled():
    checker = ThresholdChecker(blog_config={"blog1": {"enabled": False}})
    result = checker.maybe_alert("blog1", "test_reason")
    assert result is None


def test_maybe_alert_returns_message_when_passed_and_not_in_cooldown(caplog):
    checker = ThresholdChecker(blog_config={"blog1": {"dry_run": True}})
    # No prior alert
    msg = checker.maybe_alert("blog1", "test_reason", {"cnt": 3})
    assert msg is not None
    assert "test_reason" in msg
    assert "cnt=3" in msg
    # dry_run should log but not send telegram
    # Already captured in logs
    assert any("DRY-RUN" in rec.message for rec in caplog.records)


def test_maybe_alert_suppressed_during_cooldown(caplog):
    checker = ThresholdChecker()
    # First alert
    msg1 = checker.maybe_alert("blog1", "test_reason")
    assert msg1 is not None
    # Second immediate alert should be suppressed
    msg2 = checker.maybe_alert("blog1", "test_reason")
    assert msg2 is None
    # Cooldown log should appear
    assert any("쿨다운" in rec.message for rec in caplog.records)


def test_blog_specific_cooldown_works():
    checker = ThresholdChecker()
    checker._last_alerted["blog1"] = time.time() - 30*60
    # blog1 in cooldown, but blog2 not
    assert checker._in_cooldown("blog1") is True
    assert checker._in_cooldown("blog2") is False
