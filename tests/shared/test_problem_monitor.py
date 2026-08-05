from unittest.mock import patch

from shared.alert_thresholds import ThresholdChecker
from shared.problem_monitor import PublishMonitor
from shared.problem_registry import Detection

SEND_PATH = "shared.problem_monitor.telegram_notifier.send"


def _p15_detection():
    return {"detection": Detection("P15", "thumbnail", "og:image 없음", "post_validate")}


class TestDefaultChecker:
    def test_default_checker_is_real_threshold_checker(self):
        monitor = PublishMonitor(dry_run=False)
        assert isinstance(monitor.checker, ThresholdChecker)


class TestDryRun:
    def test_dry_run_via_env_no_real_send(self, monkeypatch):
        monkeypatch.setenv("PROBLEM_ALERT_DRY_RUN", "1")
        with patch(SEND_PATH) as mock_send:
            monitor = PublishMonitor()
            critical = monitor.report(
                "blog-dr-crit",
                {"detection": Detection("P08", "thinking_leak", "이제 글을 작성", "post_generate")},
                phase="post_generate",
            )
            assert critical == ["P08"]
            major = monitor.report(
                "blog-dr-major",
                {"reason": "no_result"},
                phase="result_parse",
                extra={"consecutive_failures": 3},
            )
            assert major == ["P01"]
            minor = monitor.report("blog-dr-minor", {"reason": "quota_met"}, phase="result_parse")
            assert minor == []
            assert mock_send.call_count == 0


class TestCriticalAlways:
    def test_first_report_sends_immediately_then_cooldown_skips(self):
        with patch(SEND_PATH, return_value=True) as mock_send:
            monitor = PublishMonitor(dry_run=False)
            first = monitor.report("blog-crit-1", {"reason": "llm_cot_leak"}, phase="post_generate")
            assert first == ["P08"]
            second = monitor.report("blog-crit-1", {"reason": "llm_cot_leak"}, phase="post_generate")
            assert second == []
            assert mock_send.call_count == 1


class TestMajorConsecutive:
    def test_sends_only_at_three_then_cooldown_skips(self):
        with patch(SEND_PATH, return_value=True) as mock_send:
            monitor = PublishMonitor(dry_run=False)
            assert monitor.report(
                "blog-maj-1", {"reason": "no_result"}, phase="result_parse",
                extra={"consecutive_failures": 1},
            ) == []
            assert monitor.report(
                "blog-maj-1", {"reason": "no_result"}, phase="result_parse",
                extra={"consecutive_failures": 2},
            ) == []
            assert mock_send.call_count == 0
            third = monitor.report(
                "blog-maj-1", {"reason": "no_result"}, phase="result_parse",
                extra={"consecutive_failures": 3},
            )
            assert third == ["P01"]
            assert mock_send.call_count == 1
            fourth = monitor.report(
                "blog-maj-1", {"reason": "no_result"}, phase="result_parse",
                extra={"consecutive_failures": 4},
            )
            assert fourth == []
            assert mock_send.call_count == 1


class TestMinorQuiet:
    def test_quiet_never_sends(self):
        with patch(SEND_PATH) as mock_send:
            monitor = PublishMonitor(dry_run=False)
            result = monitor.report("blog-min-1", {"reason": "quota_met"}, phase="result_parse")
            assert result == []
            assert mock_send.call_count == 0


class TestHookMismatch:
    def test_wrong_phase_blocks_send(self):
        with patch(SEND_PATH) as mock_send:
            monitor = PublishMonitor(dry_run=False)
            result = monitor.report("blog-hook-1", {"reason": "llm_cot_leak"}, phase="result_parse")
            assert result == []
            assert mock_send.call_count == 0


class TestUnknownReason:
    def test_unregistered_reason_blocks_send(self):
        with patch(SEND_PATH) as mock_send:
            monitor = PublishMonitor(dry_run=False)
            result = monitor.report("blog-unk-1", {"reason": "no_such_reason"}, phase="result_parse")
            assert result == []
            assert mock_send.call_count == 0


class TestTruncation:
    def test_long_template_message_truncated_to_500(self):
        with patch(SEND_PATH, return_value=True) as mock_send:
            monitor = PublishMonitor(dry_run=False)
            rendered = monitor.send_problem_alert(
                "P07",
                "blog-trunc-1",
                {"pattern": "x" * 600, "matched": "y" * 600},
            )
            assert rendered is not None
            assert len(rendered) <= 500
            assert mock_send.call_count == 1
            sent = mock_send.call_args[0][0]
            assert len(sent) <= 500
            assert sent == rendered


class TestInMemoryCounter:
    def test_counter_sends_on_third_and_reset_problem_id(self):
        with patch(SEND_PATH, return_value=True) as mock_send:
            monitor = PublishMonitor(dry_run=False)
            assert monitor.report("blog-ctr-1", _p15_detection(), phase="post_validate") == []
            assert monitor.report("blog-ctr-1", _p15_detection(), phase="post_validate") == []
            assert mock_send.call_count == 0
            third = monitor.report("blog-ctr-1", _p15_detection(), phase="post_validate")
            assert third == ["P15"]
            assert mock_send.call_count == 1
            monitor.reset("blog-ctr-1", "P15")
            assert monitor.report("blog-ctr-1", _p15_detection(), phase="post_validate") == []
            assert mock_send.call_count == 1

    def test_reset_blog_clears_all_keys(self):
        with patch(SEND_PATH, return_value=True) as mock_send:
            monitor = PublishMonitor(dry_run=False)
            monitor.report("blog-ctr-2", _p15_detection(), phase="post_validate")
            monitor.report("blog-ctr-2", _p15_detection(), phase="post_validate")
            monitor.report(
                "blog-ctr-2",
                {"detection": Detection("P23", "url length", "600", "post_generate")},
                phase="post_generate",
            )
            assert ("blog-ctr-2", "P15") in monitor._consecutive
            assert ("blog-ctr-2", "P23") in monitor._consecutive
            monitor.reset("blog-ctr-2")
            assert all(k[0] != "blog-ctr-2" for k in monitor._consecutive)
            assert monitor.report("blog-ctr-2", _p15_detection(), phase="post_validate") == []
            assert mock_send.call_count == 0
