"""발행 문제 인벤토리 — ProblemSpec + PROBLEM_REGISTRY (Phase 58, Task 2).

dispatcher가 내보내는 reason 문자열을 problem_id로 매핑하는 단일 소스 레지스트리.
24개 문제(P01~P24) + 미등록 reason용 `unknown_failure` = 총 25개 spec.

완전성 기준: DEPLOY-PATHS.md Section C 인벤토리의 모든 reason 문자열은
`lookup_reason()`으로 정확히 1개 spec에 해석되어야 한다. 인벤토리에만 있고
PLAN.md 기본표에 없는 reason은 가장 유사한 spec의 reason_keys에 병합했다.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SEVERITIES = ("CRITICAL", "MAJOR", "MINOR")
HOOKS = ("result_parse", "post_generate", "post_validate", "post_publish", "post_deploy")
THRESHOLDS = ("always", "consecutive:N", "quiet")


@dataclass(frozen=True)
class ProblemSpec:
    """문제 1건의 메타데이터. reason 문자열 → problem_id 역방향 탐색의 대상."""

    problem_id: str
    name_ko: str
    severity: str
    reason_keys: tuple
    hook: str
    alert_template: str
    threshold: str
    cooldown_minutes: int = 60
    action: str = ""
    detect_fn: str = ""


@dataclass(frozen=True)
class Detection:
    """탐지 결과 타입 (problem_detectors / monitor 공용)."""

    problem_id: str
    pattern: str
    matched: str = ""
    hook: str = ""


PROBLEM_REGISTRY: dict[str, ProblemSpec] = {}


def _register(spec: ProblemSpec) -> None:
    PROBLEM_REGISTRY[spec.problem_id] = spec


# --- CRITICAL (6) — 1회 발생 시 즉시 알림 (threshold="always") ---

_register(ProblemSpec(
    problem_id="P04",
    name_ko="배포 실패 (deploy_error)",
    severity="CRITICAL",
    reason_keys=("deploy_error", "deploy"),
    hook="post_deploy",
    threshold="always",
    alert_template=(
        "🚨 [CRITICAL] 배포 실패\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "조치: {action}"
    ),
    action="wrangler 배포 로그 확인 후 재배포",
))

_register(ProblemSpec(
    problem_id="P05",
    name_ko="Hugo 빌드 실패",
    severity="CRITICAL",
    reason_keys=("hugo_build_failed", "build_failed"),
    hook="post_deploy",
    threshold="always",
    alert_template=(
        "🚨 [CRITICAL] Hugo 빌드 실패\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "조치: {action}"
    ),
    action="Hugo 테마/themesDir 점검 후 재빌드",
))

_register(ProblemSpec(
    problem_id="P06",
    name_ko="썸네일 404 (broken_featureimage)",
    severity="CRITICAL",
    reason_keys=("broken_featureimage",),
    hook="post_publish",
    threshold="always",
    alert_template=(
        "🚨 [CRITICAL] 썸네일 404\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "조치: {action}"
    ),
    action="batch_thumbnails.py로 썸네일 생성 후 R2 업로드",
))

_register(ProblemSpec(
    problem_id="P07",
    name_ko="CJK 누수",
    severity="CRITICAL",
    reason_keys=("cjk_leak",),
    hook="post_generate",
    threshold="always",
    alert_template=(
        "🚨 [CRITICAL] 콘텐츠 오염 — CJK 누수 감지\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "감지 패턴: {pattern}\n"
        "조치: {action}"
    ),
    action="scan_multilingual_leak.py로 확인 후 재생성",
))

_register(ProblemSpec(
    problem_id="P08",
    name_ko="LLM/CoT 누수",
    severity="CRITICAL",
    reason_keys=("llm_cot_leak", "cot_leak"),
    hook="post_generate",
    threshold="always",
    alert_template=(
        "🚨 [CRITICAL] 콘텐츠 오염 — LLM/CoT 누수 감지\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "감지 패턴: {pattern}\n"
        "조치: {action}"
    ),
    action="scan_multilingual_leak.py로 확인 후 재생성",
))

_register(ProblemSpec(
    problem_id="P09",
    name_ko="이미지 URL 토큰 반복",
    severity="CRITICAL",
    reason_keys=("image_url_repeat",),
    hook="post_generate",
    threshold="always",
    alert_template=(
        "🚨 [CRITICAL] 콘텐츠 오염 — 이미지 URL 토큰 반복\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "감지 패턴: {pattern}\n"
        "조치: {action}"
    ),
    action="이미지 URL 토큰 반복 제거 후 재생성",
))

# --- MAJOR (12) — 연속 3회 시 알림 (threshold="consecutive:3") ---

_register(ProblemSpec(
    problem_id="P01",
    name_ko="발행 데이터 없음 (no_result)",
    severity="MAJOR",
    reason_keys=(
        "no_result",
        "no_data",
        "fetch_error",
        # DEPLOY-PATHS.md C-6: dispatcher.py:718 escalation stage — 연속 실패 에스컬레이션
        "escalation",
    ),
    hook="result_parse",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] 발행 데이터 없음\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="데이터 수집 소스/API 상태 확인 후 재발행",
))

_register(ProblemSpec(
    problem_id="P02",
    name_ko="콘텐츠 생성 실패 (no_content)",
    severity="MAJOR",
    reason_keys=(
        "no_content",
        "write_error",
        "publish_error",
        # DEPLOY-PATHS.md C-6: rap:1240 publish stage — 발행 실패 알림 stage
        "publish",
    ),
    hook="result_parse",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] 콘텐츠 생성 실패\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="프롬프트/모델 설정 점검 후 콘텐츠 재생성",
))

_register(ProblemSpec(
    problem_id="P03",
    name_ko="유사 제목 중복 (similar_title)",
    severity="MAJOR",
    reason_keys=("similar_title",),
    hook="result_parse",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] 발행 불가 — 유사 제목 중복\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="키워드별 제목 변형 다양화 검토",
))

_register(ProblemSpec(
    problem_id="P10",
    name_ko="제목 템플릿 패턴 (title_blocked)",
    severity="MAJOR",
    reason_keys=("title_blocked",),
    hook="result_parse",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] 발행 불가 — 제목 템플릿/차단 키워드\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="제목 템플릿/블랙키워드 점검",
))

_register(ProblemSpec(
    problem_id="P11",
    name_ko="제목 재생성 실패",
    severity="MAJOR",
    reason_keys=("title_regenerate_failed",),
    hook="result_parse",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] 발행 불가 — 제목 재생성 실패\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="제목 생성 프롬프트/모델 확인 후 재생성",
))

_register(ProblemSpec(
    problem_id="P12",
    name_ko="콘텐츠 품질 게이트 차단",
    severity="MAJOR",
    reason_keys=(
        "content_quality_gate",
        # DEPLOY-PATHS.md C-4/C-5: curation:1073 언어 검증(중국어 생성 차단) — 품질 게이트 성격
        "language_error",
    ),
    hook="result_parse",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] 발행 불가 — 콘텐츠 품질 게이트\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="콘텐츠 품질 게이트 통과 기준 확인",
))

_register(ProblemSpec(
    problem_id="P13",
    name_ko="API 차단 (rate_limited)",
    severity="MAJOR",
    reason_keys=("rate_limited",),
    hook="result_parse",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] API 차단\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="API 할당량 초기화 후 재시도",
))

_register(ProblemSpec(
    problem_id="P14",
    name_ko="수집/품질 게이트 실패",
    severity="MAJOR",
    reason_keys=(
        "no_keyword",
        "collect_error",
        "insufficient_products",
        "irrelevant_products",
        "low_relevance",
    ),
    hook="result_parse",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] 발행 불가 — 수집/품질 게이트\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="수집 소스/필터 기준 점검",
))

_register(ProblemSpec(
    problem_id="P15",
    name_ko="발행 후 검증 실패",
    severity="MAJOR",
    reason_keys=("validation", "validation_failed"),
    hook="post_validate",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] 발행 후 검증 실패\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="검증 항목별 문제 수정 후 재발행",
))

_register(ProblemSpec(
    problem_id="P20",
    name_ko="subprocess 에러",
    severity="MAJOR",
    reason_keys=(
        "stap_timeout",
        "tap_timeout",
        "stap_subprocess_error",
        "stap_no_output",
        # DEPLOY-PATHS.md C-1 병합: STAP/TAP subprocess 계열 dispatcher-exportable reason
        "stap_error",
        "tap_error",
        "stap_not_found",
        "tap_not_found",
        "tap_subprocess_error",
        # DEPLOY-PATHS.md C-1: dispatcher.py:840 dispatch() None 반환 — 디스패치 실패 계열
        "dispatch_returned_none",
    ),
    hook="result_parse",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] subprocess 실행 에러\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="STAP/TAP subprocess 로그 확인 후 재실행",
))

_register(ProblemSpec(
    problem_id="P21",
    name_ko="설정 오류 (config_error)",
    severity="MAJOR",
    reason_keys=(
        "config_error",
        "unknown_pipeline",
        "unknown_blog_id",
        "inactive",
        # DEPLOY-PATHS.md C-1: STAP_PIPELINE_MAP 매핑 없음 — 설정/매핑 문제
        "unknown_stap_blog",
        # DEPLOY-PATHS.md C-6: config(649)/pipeline(444) stage — 설정·파이프라인 로드 실패
        "config",
        "pipeline",
    ),
    hook="result_parse",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] 설정 오류\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="블로그 설정(blogs.d) 확인 후 수정",
))

_register(ProblemSpec(
    problem_id="P22",
    name_ko="LLM 폴백 체인 전체 실패",
    severity="MAJOR",
    reason_keys=("llm_fallback_exhausted",),
    hook="result_parse",
    threshold="consecutive:3",
    alert_template=(
        "⚠️ [MAJOR] LLM 폴백 체인 전체 실패\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    action="모델 폴백 체인/provider 키 점검",
))

# --- MINOR (6) — 로그만 (threshold="quiet") ---

_register(ProblemSpec(
    problem_id="P16",
    name_ko="중복 slug/source_id",
    severity="MINOR",
    reason_keys=("duplicate_slug", "duplicate_source_id"),
    hook="result_parse",
    threshold="quiet",
    alert_template=(
        "ℹ️ [MINOR] 중복 slug/source_id\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}"
    ),
    action="slug/source_id 중복 제거 후 재발행",
))

_register(ProblemSpec(
    problem_id="P17",
    name_ko="일일 할당량 도달",
    severity="MINOR",
    reason_keys=(
        "quota_met",
        "quota_exceeded",
        "daily_quota_exceeded",
        "daily_quota",
        "duplicate_title",
    ),
    hook="result_parse",
    threshold="quiet",
    alert_template=(
        "ℹ️ [MINOR] 일일 할당량 도달\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}"
    ),
    action="일일 할당량 초기화 대기",
))

_register(ProblemSpec(
    problem_id="P18",
    name_ko="동시 실행 방지",
    severity="MINOR",
    reason_keys=("already_running",),
    hook="result_parse",
    threshold="quiet",
    alert_template=(
        "ℹ️ [MINOR] 동시 실행 방지\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}"
    ),
    action="이전 실행 종료 확인 후 재실행",
))

_register(ProblemSpec(
    problem_id="P19",
    name_ko="오래된/만료 데이터",
    severity="MINOR",
    reason_keys=("stale", "stale_data", "event_expired"),
    hook="post_validate",
    threshold="quiet",
    alert_template=(
        "ℹ️ [MINOR] 오래된/만료 데이터\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}"
    ),
    action="오래된 데이터 갱신/제거",
))

_register(ProblemSpec(
    problem_id="P23",
    name_ko="이미지 URL 길이 초과",
    severity="MINOR",
    reason_keys=("image_url_length",),
    hook="post_generate",
    threshold="quiet",
    alert_template=(
        "ℹ️ [MINOR] 이미지 URL 길이 초과\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}"
    ),
    action="이미지 URL 길이 축소",
))

_register(ProblemSpec(
    problem_id="P24",
    name_ko="검증 함수 자체 결함",
    severity="MINOR",
    reason_keys=("validation_defect",),
    hook="post_validate",
    threshold="quiet",
    alert_template=(
        "ℹ️ [MINOR] 검증 함수 자체 결함\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}"
    ),
    action="검증 함수 자체 점검/수정",
))

# --- 미등록 reason용 (25번째) — 로그만 ---

_register(ProblemSpec(
    problem_id="unknown_failure",
    name_ko="미등록 실패 사유",
    severity="MINOR",
    reason_keys=(),
    hook="result_parse",
    threshold="quiet",
    alert_template=(
        "ℹ️ [MINOR] 미등록 실패 사유\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}"
    ),
    action="dispatcher 로그에서 실패 원인 확인",
))


def lookup_reason(reason: str) -> ProblemSpec | None:
    """reason 문자열 → 소유 ProblemSpec 역방향 탐색. 미등록이면 None."""
    for spec in PROBLEM_REGISTRY.values():
        if reason in spec.reason_keys:
            return spec
    return None


def lookup_problem(problem_id: str) -> ProblemSpec | None:
    """problem_id → ProblemSpec. 미등록이면 None."""
    return PROBLEM_REGISTRY.get(problem_id)


def lookup_hook(problem_id: str) -> str | None:
    """problem_id의 감지 hook 반환. 미등록이면 None."""
    spec = PROBLEM_REGISTRY.get(problem_id)
    return spec.hook if spec else None
