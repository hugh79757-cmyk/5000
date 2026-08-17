"""Regression: P계열 근본원인 노출 — publish_error 이벤트의 stage가 실제 reason으로 보존된다.

작업1(phase-71e-pcode-1): dispatcher가 낸 이유(no_content/stap_subprocess_error 등)가
spec.hook(=result_parse)로 뭉개지지 않고 publish_error_events.stage에 남도록
problem_monitor가 보존하는지 검증한다.
"""

from unittest.mock import patch

from shared.problem_monitor import PublishMonitor

SEND_PATH = "shared.problem_monitor.telegram_notifier.send"
RECORD_PATH = "shared.publish_error_events.record_publish_error"


class TestStagePreservation:
    def test_no_content_reason_preserved_as_stage(self):
        """no_content가 P02(result_parse)로 매핑되되, stage는 'no_content'로 보존돼야 한다."""
        captured = {}

        def _fake_record(blog_id, stage, detail, problem_id="", reason=""):
            captured["stage"] = stage
            captured["detail"] = detail
            captured["problem_id"] = problem_id
            captured["reason"] = reason
            return {"event_id": 1}

        with patch(SEND_PATH, return_value=True), \
             patch(RECORD_PATH, side_effect=_fake_record):
            monitor = PublishMonitor(dry_run=False)
            sent = monitor.report(
                "blog-stage-1",
                {"reason": "no_content", "stage": "no_content", "detail": "no_content"},
                phase="result_parse",
                extra={"consecutive_failures": 3},
            )
        assert sent == ["P02"]
        # 핵심: DB stage가 spec.hook 'result_parse'가 아니라 실제 reason 'no_content'
        assert captured["stage"] == "no_content"
        assert captured["problem_id"] == "P02"
        # send_problem_alert가 reason을 record로 전달 (incident key 일치를 위한 커밋 B 변경)
        assert captured["reason"] == "no_content"

    def test_stap_subprocess_error_reason_preserved_as_stage(self):
        """STAP subprocess 크래시(stap_subprocess_error)도 stage로 보존 — sector 진단 캡처."""
        captured = {}

        def _fake_record(blog_id, stage, detail, problem_id="", reason=""):
            captured["stage"] = stage
            captured["detail"] = detail
            captured["problem_id"] = problem_id
            captured["reason"] = reason
            return {"event_id": 1}

        with patch(SEND_PATH, return_value=True), \
             patch(RECORD_PATH, side_effect=_fake_record):
            monitor = PublishMonitor(dry_run=False)
            # stap_subprocess_error 는 P20(MAJOR) 계열 — threshold 확인을 위해 extra 전달
            sent = monitor.report(
                "blog-stage-2",
                {"reason": "stap_subprocess_error", "stage": "stap_subprocess_error",
                 "detail": "Traceback: boom"},
                phase="result_parse",
                extra={"consecutive_failures": 3},
            )
        assert captured["stage"] == "stap_subprocess_error"
        # detail(Traceback)이 matched로 넘어가 record detail에 캡처되어야 한다
        assert "Traceback" in captured["detail"]
        assert captured["reason"] == "stap_subprocess_error"