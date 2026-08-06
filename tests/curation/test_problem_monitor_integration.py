"""Phase 58 Task 8 — PublishMonitor 통합 시나리오 테스트 (TEST CODE).

모든 시나리오는 mock 기반 — 실제 텔레그램 발송/외부 API 호출 금지.
`shared.problem_monitor.telegram_notifier.send`를 항상 patch하고, 모니터는
`PublishMonitor(dry_run=False)`를 명시해 env(PROBLEM_ALERT_DRY_RUN)와 무관하게
동작시키되 발송 함수는 patch라 실전 트래픽은 0이다.

커버 시나리오:
  1. curation run() 실패 블록 — reason="no_result" → P01(phase=result_parse) 보고
     + 기존 _tg_error 경로 유지 확인.
  2. writer raw 훅 — CoT 본문('이제 글을 작성하겠습니다...') → P08(phase=post_generate),
     정상 한국어 본문 → 보고 0건.
  3. publisher _run_validation — check_result issues 존재 → P15(phase=post_validate) 보고.
  4. dispatcher — 배포 실패 캡처(_build_and_deploy_central=False) → P04(deploy_error,
     phase=post_deploy) + reason 매핑(hugo_build_failed) → P05(phase=post_deploy).
  5. P22 — ai_generate RuntimeError → llm_fallback_exhausted(phase=result_parse) 보고
     + RuntimeError 재전파(no_content 흡수 경로 보존).
  6. curation deploy_error stage → phase="post_deploy"(P04 hook 일치 — 가드 차단 없음).
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.problem_monitor import PublishMonitor


def _fresh_monitor(dry_run=False):
    """실 ThresholdChecker를 쓰는 fresh PublishMonitor (쿨다운/카운터 격리)."""
    return PublishMonitor(dry_run=dry_run)


# THINKING_PATTERNS r'이제 .* 작성'에 매치되는 CoT 본문 (P08 thinking_leak 트리거)
COT_LEAK_BODY = "이제 글을 작성하겠습니다.\n본문 시작\n"

# 정상 한국어 본문 — P07/P08/P09/P23 전부 미감지, _validate_title 통과 제목.
# 주의: 500자 초과 본문은 detect_post_generate가 본문 전체를 P23(detect_image_url_length)
# 에 넘겨 P23(quiet, 로그만) 보고가 발생하므로(운영 코드 동작 — 이 태스크는 TEST CODE만
# 수정) "0 reports" 검증은 500자 미만 clean 본문으로 수행한다.
_NORMAL_LINE = (
    "이 노트북은 무게가 가볍고 배터리가 오래가서 대학생과 직장인에게 모두 적합합니다. "
    "빠른 부팅 속도와 선명한 디스플레이 덕분에 문서 작업과 영상 시청이 모두 쾌적합니다."
)
SHORT_CLEAN_BODY = "# 갤럭시북4 프로 학생용 추천\n\n" + _NORMAL_LINE


def _ai_sequence(*bodies):
    """ai_generate 가짜 시퀀스 — 요청 순서대로 본문 반환, 초과 시 마지막 값 유지."""
    state = {"i": 0}

    def _fake(*args, **kwargs):
        body = bodies[min(state["i"], len(bodies) - 1)]
        state["i"] += 1
        return body

    return _fake


# ─────────────────────────────────────────────────────────────
# 1. curation run() 실패 블록 — no_result → P01 (phase=result_parse)
# ─────────────────────────────────────────────────────────────

def test_curation_run_no_result_reports_p01():
    from pipelines.curation import pipeline as cur_pipeline

    monitor = _fresh_monitor()
    with patch("shared.problem_monitor.get_monitor", return_value=monitor), \
            patch.object(monitor, "report", wraps=monitor.report) as mr, \
            patch("shared.problem_monitor.telegram_notifier.send", return_value=True), \
            patch.object(cur_pipeline, "_tg_error") as fake_tg, \
            patch.object(cur_pipeline, "_acquire_lock", return_value=object()), \
            patch.object(cur_pipeline, "_release_lock"), \
            patch.object(cur_pipeline, "_run_inner",
                         return_value={"success": False, "reason": "no_result"}):
        result = cur_pipeline.run({"id": "int-noresult-hugo", "daily_quota": 5})

    assert result == {"success": False, "reason": "no_result"}
    assert mr.call_count == 1
    args, kwargs = mr.call_args
    assert args[0] == "int-noresult-hugo"
    assert args[1] == {"reason": "no_result"}
    # P01 hook = result_parse — phase 불일치 가드 통과 확인
    assert kwargs["phase"] == "result_parse"
    assert kwargs["extra"] == {"consecutive_failures": 1}
    # 기존 _tg_error 경로는 그대로 호출됨 (additive 게이트)
    fake_tg.assert_called_once()


# ─────────────────────────────────────────────────────────────
# 2. writer raw 훅 — CoT 본문 → P08 (phase=post_generate) / 정상 본문 → 0건
# ─────────────────────────────────────────────────────────────

def test_writer_raw_hook_reports_p08_on_cot_body(sample_products):
    from pipelines.curation import writer

    monitor = _fresh_monitor()
    with patch("shared.problem_monitor.get_monitor", return_value=monitor), \
            patch.object(monitor, "report", wraps=monitor.report) as mr, \
            patch("shared.problem_monitor.telegram_notifier.send", return_value=True) as fake_send, \
            patch.object(writer, "ai_generate",
                         side_effect=_ai_sequence(COT_LEAK_BODY, SHORT_CLEAN_BODY)):
        writer.generate_curation_article("노트북", sample_products, blog_id="int-cot-hugo")

    assert mr.call_count == 1
    args, kwargs = mr.call_args
    det = args[1]["detection"]
    assert det.problem_id == "P08"
    assert kwargs["phase"] == "post_generate"
    # P08 CRITICAL always — dry_run=0에서 1건 발송 (patch — 실전 0건)
    assert fake_send.call_count == 1
    assert "P08" in fake_send.call_args[0][0]


def test_writer_raw_hook_no_report_on_normal_body(sample_products):
    from pipelines.curation import writer

    monitor = _fresh_monitor()
    with patch("shared.problem_monitor.get_monitor", return_value=monitor), \
            patch.object(monitor, "report", wraps=monitor.report) as mr, \
            patch("shared.problem_monitor.telegram_notifier.send", return_value=True) as fake_send, \
            patch.object(writer, "ai_generate", return_value=SHORT_CLEAN_BODY):
        writer.generate_curation_article("노트북", sample_products, blog_id="int-normal-hugo")

    # 500자 미만 clean 본문 → P07/P08/P09/P23 전부 미감지 → 보고 0건
    assert mr.call_count == 0
    assert fake_send.call_count == 0


# ─────────────────────────────────────────────────────────────
# 3. publisher _run_validation — check_result issues → P15 (phase=post_validate)
# ─────────────────────────────────────────────────────────────

def test_publisher_run_validation_reports_p15(tmp_path):
    from shared.publisher import _run_validation

    site = tmp_path / "site"
    (site / "public" / "posts" / "slug").mkdir(parents=True)
    (site / "content" / "posts" / "slug").mkdir(parents=True)
    (site / "public" / "posts" / "slug" / "index.html").write_text(
        "<html><head></head><body>본문</body></html>", encoding="utf-8")
    (site / "content" / "posts" / "slug" / "index.md").write_text(
        "---\ntitle: 테스트\n---\n", encoding="utf-8")

    check_result = {
        "passed": False,
        "issues": [{"check": "thumbnail", "msg": "썸네일 누락", "severity": "error"}],
        "warnings": [],
    }

    monitor = _fresh_monitor()
    with patch("shared.problem_monitor.get_monitor", return_value=monitor), \
            patch.object(monitor, "report", wraps=monitor.report) as mr, \
            patch("shared.problem_monitor.telegram_notifier.send", return_value=True), \
            patch("shared.publisher._validate_post_html", return_value=check_result), \
            patch("shared.telegram_notifier.send_error") as fake_tg_err:
        _run_validation(str(site), "slug", "int-p15-hugo", "테스트 제목", {})

    assert mr.call_count == 1
    args, kwargs = mr.call_args
    det = args[1]["detection"]
    assert det.problem_id == "P15"
    assert kwargs["phase"] == "post_validate"
    # 기존 _tg_err(validation) 발행 경로 유지
    fake_tg_err.assert_called_once()


# ─────────────────────────────────────────────────────────────
# 4. dispatcher — 배포 실패 캡처 → P04 / reason 매핑 → P05 (phase=post_deploy)
# ─────────────────────────────────────────────────────────────

def test_dispatcher_deploy_fail_capture_p04():
    import dispatcher

    monitor = _fresh_monitor()
    cfg = {"id": "health-hugo", "status": "active", "pipeline": "test", "daily_quota": 5}
    with patch("dispatcher.get_monitor", return_value=monitor), \
            patch.object(monitor, "report", wraps=monitor.report) as mr, \
            patch("shared.problem_monitor.telegram_notifier.send", return_value=True) as fake_send, \
            patch("dispatcher.get_blog_config", return_value=cfg), \
            patch("dispatcher._is_duplicate", return_value=False), \
            patch("dispatcher._is_on_cooldown", return_value=False), \
            patch("dispatcher._is_on_daily_cooldown", return_value=False), \
            patch("dispatcher._run_pipeline", return_value={"success": True}), \
            patch("dispatcher._record_ledger"), \
            patch("dispatcher._reset_failure_count"), \
            patch("dispatcher._reset_extended_failure_keys"), \
            patch("dispatcher._build_and_deploy_central", return_value=False):
        dispatcher.dispatch("health-hugo")

    assert mr.call_count == 1
    args, kwargs = mr.call_args
    assert args[0] == "health-hugo"
    assert args[1] == {"reason": "deploy_error"}
    assert kwargs["phase"] == "post_deploy"  # P04 hook
    assert fake_send.call_count == 1
    assert "P04" in fake_send.call_args[0][0]


def test_dispatcher_reason_mapping_p05():
    import dispatcher

    monitor = _fresh_monitor()
    cfg = {"id": "health-hugo", "status": "active", "pipeline": "test"}
    with patch("dispatcher.get_monitor", return_value=monitor), \
            patch.object(monitor, "report", wraps=monitor.report) as mr, \
            patch("shared.problem_monitor.telegram_notifier.send", return_value=True) as fake_send, \
            patch("dispatcher.get_blog_config", return_value=cfg), \
            patch("dispatcher._is_duplicate", return_value=False), \
            patch("dispatcher._is_on_cooldown", return_value=False), \
            patch("dispatcher._is_on_daily_cooldown", return_value=False), \
            patch("dispatcher._run_pipeline",
                  return_value={"success": False, "reason": "hugo_build_failed"}), \
            patch("dispatcher._record_failure"), \
            patch("dispatcher._tg_error"), \
            patch("dispatcher._increment_failure_count", return_value=1):
        dispatcher.dispatch("health-hugo")

    assert mr.call_count == 1
    args, kwargs = mr.call_args
    assert args[1] == {"reason": "hugo_build_failed"}
    assert kwargs["phase"] == "post_deploy"  # P05 hook
    assert kwargs["extra"] == {"consecutive_failures": 1}
    assert fake_send.call_count == 1
    assert "P05" in fake_send.call_args[0][0]


# ─────────────────────────────────────────────────────────────
# 5. P22 — ai_generate RuntimeError → llm_fallback_exhausted + re-raise
# ─────────────────────────────────────────────────────────────

def test_writer_p22_llm_fallback_exhausted(sample_products):
    from pipelines.curation import writer

    monitor = _fresh_monitor()
    with patch("shared.problem_monitor.get_monitor", return_value=monitor), \
            patch.object(monitor, "report", wraps=monitor.report) as mr, \
            patch("shared.problem_monitor.telegram_notifier.send", return_value=True) as fake_send, \
            patch.object(writer, "ai_generate",
                         side_effect=RuntimeError("모든 LLM tier 실패")) as fake_ai:
        with pytest.raises(RuntimeError):
            writer.generate_curation_article("노트북", sample_products, blog_id="int-p22-hugo")

    assert mr.call_count == 1
    args, kwargs = mr.call_args
    assert args[1] == {"reason": "llm_fallback_exhausted"}
    assert kwargs["phase"] == "result_parse"  # P22 hook
    # P22 MAJOR consecutive:3 — 1회차는 발송 없음 (기존 no_content 흡수 경로 보존)
    assert fake_send.call_count == 0
    fake_ai.assert_called_once()


# ─────────────────────────────────────────────────────────────
# 6. curation deploy_error stage → phase="post_deploy" (P04 hook 일치)
# ─────────────────────────────────────────────────────────────

def test_curation_run_deploy_error_phase_post_deploy():
    from pipelines.curation import pipeline as cur_pipeline

    monitor = _fresh_monitor()
    with patch("shared.problem_monitor.get_monitor", return_value=monitor), \
            patch.object(monitor, "report", wraps=monitor.report) as mr, \
            patch("shared.problem_monitor.telegram_notifier.send", return_value=True) as fake_send, \
            patch.object(cur_pipeline, "_tg_error") as fake_tg, \
            patch.object(cur_pipeline, "_acquire_lock", return_value=object()), \
            patch.object(cur_pipeline, "_release_lock"), \
            patch.object(cur_pipeline, "_run_inner",
                         return_value={"success": False, "reason": "deploy_error"}):
        cur_pipeline.run({"id": "int-deployerr-hugo", "daily_quota": 5})

    assert mr.call_count == 1
    args, kwargs = mr.call_args
    assert args[1] == {"reason": "deploy_error"}
    # P04 hook = post_deploy — phase 하드코딩 없이 spec.hook 전달, 가드 차단 없음
    assert kwargs["phase"] == "post_deploy"
    assert fake_send.call_count == 1
    assert "P04" in fake_send.call_args[0][0]
    fake_tg.assert_called_once()
