"""problem_monitor.py — 발행 문제 감지·분류·알림 단일 진입점 (Phase 58, Task 4).

PublishMonitor은 dispatcher 결과 dict(`reason`) 또는 Detection 객체를 ProblemSpec으로
해석하고, severity 정책(always/consecutive:N/quiet)과 실 ThresholdChecker 쿨다운에 따라
문제별 텔레그램 알림을 발송한다. `PROBLEM_ALERT_DRY_RUN=1`이면 발송 없이 로그만 남긴다.
모든 예외 경로는 logger.error로 기록하고, monitor 호출로 파이프라인이 중단되지 않는다.

연속 카운터 단일화 (W-1):
- result_parse 카운터 소유자 = dispatcher (data/failure_count.json, Task 5 확장).
  monitor는 카운트하지 않고 extra["consecutive_failures"] 값만 소비한다.
  성공 리셋도 dispatcher가 수행한다.
- 비-dispatcher 훅(post_generate/post_validate/post_publish/post_deploy)은 monitor의
  인메모리 `self._consecutive`를 사용한다 — 단일 실행 내 연속 실패 의미이며 프로세스
  재시작 시 초기화된다. CRITICAL(always)은 카운트하지 않는다.
- 쿨다운은 ThresholdChecker의 기존 `_in_cooldown`/`_mark_alerted`만 재사용한다.
  신규 쿨다운 구현 없음.
"""

import logging
import os

from shared.problem_registry import (
    ProblemSpec,
    Detection,
    lookup_reason,
    lookup_problem,
)
from shared.problem_detectors import (
    detect_post_generate,
    detect_validation_issue,
    detect_empty_content_deployed,
)
from shared.publisher import get_blog_config
from shared.alert_thresholds import ThresholdChecker
from shared import telegram_notifier

logger = logging.getLogger(__name__)


class PublishMonitor:
    """발행 문제 감지·분류·알림을 관장하는 모니터."""

    def __init__(self, checker=None, dry_run=None):
        """checker 기본값은 실 ThresholdChecker 인스턴스 (fake 주입 금지).

        dry_run 기본값은 PROBLEM_ALERT_DRY_RUN env(1이면 True). 명시 인자가 최우선.
        """
        self.checker = checker if checker is not None else ThresholdChecker()
        if dry_run is None:
            self.dry_run = int(os.environ.get("PROBLEM_ALERT_DRY_RUN", "0")) == 1
        else:
            self.dry_run = bool(dry_run)
        self._consecutive: dict[tuple[str, str], int] = {}

    def report(self, blog_id: str, result: dict, phase: str, extra: dict | None = None) -> list[str]:
        """단일 진입점 — 발송된(또는 dry-run 발송 예정) problem_id 목록 반환.

        result dict 규약: {"detection": Detection} 우선(비-dispatcher 훅), 없으면
        {"reason": str}(result_parse) → lookup_reason(). 둘 다 없으면 경고 후 [].
        phase 인자는 매핑된 spec.hook과 반드시 일치해야 하며, 불일치 시 로그 후 발송 차단.
        """
        if extra is None:
            extra = {}
        sent: list[str] = []

        spec, context = self._resolve(blog_id, result, phase)
        if spec is None:
            return sent

        if spec.hook != phase:
            logger.error(
                f"[problem_monitor] phase 불일치 — 발송 차단: blog={blog_id} "
                f"problem={spec.problem_id} phase={phase} 기대={spec.hook}"
            )
            return sent

        consecutive = self._resolve_consecutive(blog_id, spec, phase, extra)
        context["consecutive"] = consecutive

        if spec.threshold == "always":
            if self.checker._in_cooldown(blog_id):
                logger.info(f"[problem_monitor] 쿨다운 스킵: {blog_id}/{spec.problem_id}")
                return sent
            rendered = self.send_problem_alert(spec.problem_id, blog_id, context)
            if rendered is not None:
                sent.append(spec.problem_id)
            self.checker._mark_alerted(blog_id)
        elif spec.threshold.startswith("consecutive:"):
            if self.checker.check_consecutive_failures(blog_id, consecutive):
                if self.checker._in_cooldown(blog_id):
                    logger.info(f"[problem_monitor] 쿨다운 스킵: {blog_id}/{spec.problem_id}")
                else:
                    rendered = self.send_problem_alert(spec.problem_id, blog_id, context)
                    if rendered is not None:
                        sent.append(spec.problem_id)
                    self.checker._mark_alerted(blog_id)
            else:
                logger.debug(
                    f"[problem_monitor] 연속 {consecutive}회 < 임계값: {blog_id}/{spec.problem_id}"
                )
        elif spec.threshold == "quiet":
            logger.info(
                f"[problem_monitor] MINOR 로그 전용: {blog_id}/{spec.problem_id} — {spec.name_ko}"
            )
        else:
            logger.warning(f"[problem_monitor] 미지원 threshold: {spec.threshold} ({spec.problem_id})")

        return sent

    def _resolve(self, blog_id: str, result: dict, phase: str) -> tuple[ProblemSpec | None, dict]:
        """result dict → (ProblemSpec, 템플릿 렌더 context). 해석 불가 시 (None, {})."""
        detection = result.get("detection") if isinstance(result, dict) else None
        if detection is not None:
            if isinstance(detection, dict):
                problem_id = detection.get("problem_id", "")
                pattern = detection.get("pattern", "")
                matched = detection.get("matched", "") or ""
            else:
                problem_id = detection.problem_id
                pattern = getattr(detection, "pattern", "")
                matched = getattr(detection, "matched", "") or ""
            spec = lookup_problem(problem_id)
            if spec is None:
                logger.warning(
                    f"[problem_monitor] 미등록 problem_id: {problem_id} (blog={blog_id})"
                )
                return None, {}
            context = {
                "blog_id": blog_id,
                "problem_id": spec.problem_id,
                "name_ko": spec.name_ko,
                "phase": phase,
                "pattern": pattern,
                "matched": matched[:200],
                "action": spec.action,
            }
            return spec, context

        reason = result.get("reason") if isinstance(result, dict) else None
        if reason is not None:
            spec = lookup_reason(reason)
            if spec is None:
                logger.warning(f"[problem_monitor] 미등록 reason: {reason} (blog={blog_id})")
                return None, {}
            detail = str(result.get("detail", "") or result.get("error_msg", ""))
            context = {
                "blog_id": blog_id,
                "problem_id": spec.problem_id,
                "name_ko": spec.name_ko,
                "phase": phase,
                "pattern": "",
                "matched": detail[:200],
                "action": spec.action,
            }
            return spec, context

        logger.warning(f"[problem_monitor] result 형식 미지원 (blog={blog_id}): {result}")
        return None, {}

    def _resolve_consecutive(self, blog_id: str, spec: ProblemSpec, phase: str, extra: dict) -> int:
        """연속 횟수 결정 — result_parse는 extra 소비, 비-dispatcher 훅은 인메모리 카운터."""
        if phase == "result_parse":
            return self._int_consecutive(extra)
        if spec.threshold == "always":
            return self._int_consecutive(extra)
        key = (blog_id, spec.problem_id)
        self._consecutive[key] = self._consecutive.get(key, 0) + 1
        return self._consecutive[key]

    @staticmethod
    def _int_consecutive(extra: dict) -> int:
        try:
            return int(extra.get("consecutive_failures", 1) or 1)
        except (TypeError, ValueError):
            return 1

    def detect(self, hook: str, content, blog_id: str) -> list[Detection]:
        """훅별 탐지 — post_generate는 전건(P07/P08/P09/P23), post_validate는 1건."""
        if hook == "post_generate":
            return detect_post_generate(content, blog_id)
        if hook == "post_validate":
            detection = detect_validation_issue(content, blog_id)
            return [detection] if detection is not None else []
        logger.warning(f"[problem_monitor] 미지원 hook: {hook}")
        return []

    def send_problem_alert(self, problem_id: str, blog_id: str, context: dict | None = None) -> str | None:
        """문제별 alert_template 렌더 → 500자 트렁케이션 → 발송.

        dry_run이면 로그만 남기고 렌더 문자열 반환. 실발송 모드에서는 발송 성공 시에만
        렌더 문자열 반환, 억제/실패/예외 시 None. 예외는 logger.error 후 None — 중단 금지.
        """
        if context is None:
            context = {}
        spec = lookup_problem(problem_id)
        if spec is None:
            logger.error(f"[problem_monitor] send_problem_alert: 미등록 problem_id: {problem_id}")
            return None
        render_ctx = dict(context)
        render_ctx.setdefault("blog_id", blog_id)
        render_ctx.setdefault("problem_id", problem_id)
        render_ctx.setdefault("name_ko", spec.name_ko)
        render_ctx.setdefault("phase", spec.hook)
        render_ctx.setdefault("pattern", "")
        render_ctx.setdefault("matched", "")
        render_ctx.setdefault("consecutive", "")
        render_ctx.setdefault("action", spec.action)
        try:
            message = spec.alert_template.format(**render_ctx)
        except (KeyError, ValueError, AttributeError) as e:
            logger.error(f"[problem_monitor] 템플릿 렌더 실패: {problem_id} — {e}")
            return None
        message = message[:500]
        if self.dry_run:
            logger.info(f"[problem_monitor DRY-RUN] 발송 예정: {blog_id}/{problem_id}\n{message}")
            return message
        try:
            event = {}
            try:
                from shared.publish_error_events import record_publish_error
                event = record_publish_error(
                    blog_id, spec.hook, render_ctx.get("matched", ""),
                    problem_id=problem_id,
                )
            except Exception as exc:
                logger.debug("[problem_monitor] event record failed: %s", exc)
            ok = telegram_notifier.send(message, audit_event_id=event.get("event_id"))
        except Exception as e:
            logger.error(f"[problem_monitor] 텔레그램 발송 예외: {blog_id}/{problem_id} — {e}")
            return None
        if ok:
            logger.info(f"[problem_monitor] 알림 발송: {blog_id}/{problem_id}")
            return message
        logger.warning(f"[problem_monitor] 텔레그램 발송 실패: {blog_id}/{problem_id}")
        return None

    def reset(self, blog_id: str, problem_id: str | None = None) -> None:
        """비-dispatcher 훅 인메모리 연속 카운터 리셋.

        problem_id=None이면 해당 blog의 모든 키를 삭제. 발행 성공 경로에서 호출된다.
        (인메모리 특성: 프로세스 재시작 시 자동 초기화)
        """
        if problem_id is None:
            for key in [k for k in self._consecutive if k[0] == blog_id]:
                del self._consecutive[key]
            return
        self._consecutive.pop((blog_id, problem_id), None)

    def report_deployed_content(self, blog_id: str) -> list[str]:
        """P32: 배포된 글의 빈 내용 사후 검증 (주기적 스캔용).

        blog_id → get_blog_config()로 domain, site_path 추출 →
        detect_empty_content_deployed(blog_id, domain, site_path) 호출.

        실HTTP 수행하므로 dry_run 환경에서도 스캔 자체는 실행 (알림은 dry_run에서 억제됨).
        예외(네트워크 타임아웃 등)는 '정상 통과'로 간주하지 않고 경고 로그 후 [] 반환.
        """
        try:
            cfg = get_blog_config(blog_id)
        except ValueError:
            logger.warning(f"[P32] blog_id={blog_id} 설정 없음 — 건너뜀")
            return []
        domain = cfg.get("domain", "")
        site_path = cfg.get("site_path", "")
        if not domain or not site_path:
            logger.warning(f"[P32] blog_id={blog_id} domain/site_path 누락 — 건너뜀")
            return []

        try:
            detection = detect_empty_content_deployed(blog_id, domain, site_path)
        except Exception as e:
            logger.warning(f"[P32] blog_id={blog_id} HTTP/검증 예외: {e}")
            return []

        if detection is None:
            # 정상: 빈 글 아님
            logger.debug(f"[P32] blog_id={blog_id} PASS (비어있지 않음)")
            return []

        # P32 감지됨 → 알림 발송
        sent = self.report(blog_id, {"detection": detection}, "post_deploy")
        if sent:
            logger.info(f"[P32] blog_id={blog_id} 알림 발송: {sent}")
        return sent


_monitor = None


def get_monitor() -> PublishMonitor:
    """모듈 레벨 lazy 싱글턴."""
    global _monitor
    if _monitor is None:
        _monitor = PublishMonitor()
    return _monitor
