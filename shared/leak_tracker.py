"""shared/leak_tracker.py — C01/C04 원인추적 훅

파이프라인 각 단계 경계에서 C01(곡선따옴표)과 C04(프롬프트 누수)를 검사하여
처음 탐지된 지점을 logs/leak-origin.log에 기록한다.

3개 삽입 지점:
  (a) 생성 직후: AI 작성 완료 후, humanizer 투입 전
  (b) humanizer 통과 직후: humanizer 변환 후, _write_hugo_post 전
  (c) _write_hugo_post 저장 직전: 파일 저장 직전 최종 검사
"""
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# 로그 파일 경로
LEAK_LOG_PATH = Path(__file__).parent.parent / "logs" / "leak-origin.log"
LEAK_JSONL_PATH = Path(__file__).parent.parent / "logs" / "leak-origin.jsonl"

# C01: 곡선따옴표 (U+2018, U+2019, U+201C, U+201D)
# 직선따옴표(' "...')는 정상, 곡선따옴표(' ' " ")만 위반으로 탐지
_C01_CURVED_SINGLE = ["\u2018", "\u2019"]  # ' '
_C01_CURVED_DOUBLE = ["\u201c", "\u201d"]  # " "

# C04: 프롬프트 누수 패턴 (국문 + 영문)
_C04_KO_PATTERNS = [
    r"먼저\s*생각", r"생각해보자", r"생각해\s*보자",
    r"다음\s*단계", r"단계별로\s*(생각|접근|분석|해결|수행)",
    r"우리가\s*해야\s*할", r"필요한\s*것",
    r"생각\s*과정", r"결론부터\s*말하면",
]
_C04_EN_PATTERNS = [
    r"\bNeed\s+think\b", r"\bWe\s+need\s+to\s+write\b",
    r"Let.s\s+think\s+step\s+by\s+step",
    r"think\s+step\s+by\s+step",
    r"let.s\s+break\s+this\s+down",
    r"here.?s\s+the\s+plan",
    r"in\s+order\s+to\s+achieve",
    r"as\s+an\s+AI\s+language\s+model",
    r"I\s+cannot\s+",
    # CUAP 프롬프트 릭: LLM이 instruction 텍스트를 본문에 그대로 에코
    r"editorial synthesis is constructed exclusively",
    r"contains no externally modeled or estimated values",
    r"every figure can be traced back to its named source table",
]


def _ensure_log_dir():
    """로그 디렉토리 존재 확인."""
    LEAK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _log_leak_origin(stage: str, slug: str, rule_id: str, pattern_type: str, snippet: str) -> None:
    """leak-origin.log에 최초 탐지 기록.

    같은 slug에 대해 여러 지점에서 탐지되면 첫 지점만 기록(중복 방지).
    """
    _ensure_log_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] stage={stage} slug={slug} rule={rule_id} type={pattern_type} snippet={snippet[:100]}\n"
    with open(LEAK_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(log_line)
    logger.warning(f"[LEAK-ORIGIN] {log_line.strip()}")


def _log_leak_jsonl(stage: str, slug: str, rule_id: str, pattern_type: str, snippet: str, blog_id=None) -> None:
    """leak-origin.jsonl sidecar에 JSON 한 줄 기록 (per detection).

    Fields: ts(iso), stage, slug, rule_id, pattern_type, snippet[:100], blog_id.
    blog_id는 "" 으로 폴백하여 기존 text 로그와의 호환 유지.
    """
    import json

    _ensure_log_dir()
    ts = datetime.now().isoformat()
    payload = {
        "ts": ts,
        "stage": stage,
        "slug": slug,
        "rule_id": rule_id,
        "pattern_type": pattern_type,
        "snippet": snippet[:100],
        "blog_id": blog_id or "",
    }
    with open(LEAK_JSONL_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


# 이미 기록된 slug 추적 (중복 방지 — 메모리 내)
_logged_slugs: set[str] = set()


def _is_logged(slug: str) -> bool:
    """해당 slug가 이미 기록되었는지 확인."""
    return slug in _logged_slugs


def _mark_logged(slug: str) -> None:
    """해당 slug 기록 완료 표시."""
    _logged_slugs.add(slug)


def check_c01_c04(
    content: str,
    stage: str,
    slug: str,
    locale: str = "ko",
    log_originally: bool = True,
    blog_id: str | None = None,
    log_every_stage: bool = False,
) -> dict:
    """C01(곡선따옴표) + C04(프롬프트 누수) 검사.

    Args:
        content: 검사 대상 텍스트 (frontmatter 또는 body)
        stage: 삽입 지점 식별자 ("after_generation" / "after_humanizer" / "before_write")
        slug: 포스트 slug
        locale: "ko" 또는 "en" (C04 패턴 선택)
        log_originally: True면 최초 탐지 지점만 기록, False면 기록 안 함 (재검증용)
        blog_id: blog 식별자 (JSONL sidecar에 기록, 없으면 "" )
        log_every_stage: True면 dedup과 무관하게 JSONL은 매 탐지마다 기록 (aggregate 관측용).
                         False면 JSONL도 text 로그와 동일하게 dedup.
                         Text 로그는 항상 dedup 유지.

    Returns:
        {"c01_detected": bool, "c04_detected": bool,
         "c01_patterns": list[str], "c04_patterns": list[str],
         "first_stage": str | None}  # 처음 탐지된 stage (없으면 None)
    """
    result = {
        "c01_detected": False,
        "c04_detected": False,
        "c01_patterns": [],
        "c04_patterns": [],
        "first_stage": None,
    }

    # C01 검사
    c01_found = []
    if any(c in content for c in _C01_CURVED_SINGLE):
        c01_found.append("곡선따옴표(' ')")
        result["c01_detected"] = True
    if any(c in content for c in _C01_CURVED_DOUBLE):
        c01_found.append('곡선따옴표(" ")')
        result["c01_detected"] = True
    result["c01_patterns"] = c01_found

    # C04 검사
    c04_found = []
    patterns = _C04_EN_PATTERNS if locale == "en" else _C04_KO_PATTERNS
    for pat in patterns:
        m = re.search(pat, content, re.IGNORECASE)
        if m:
            c04_found.append(m.group()[:40])
    if c04_found:
        result["c04_detected"] = True
        result["c04_patterns"] = c04_found

    # 로그 기록
    # Text 로그는 항상 dedup (기존 동작 유지, Telegram 노이즈 방지)
    # JSONL은 log_every_stage=True이면 dedup 무시하고 매 탐지마다 기록 (aggregate 관측용)
    if log_originally and (result["c01_detected"] or result["c04_detected"]):
        is_first = not _is_logged(slug)
        if is_first:
            _mark_logged(slug)
            if result["c01_detected"]:
                _log_leak_origin(stage, slug, "C01", "curve_quote", c01_found[0])
                _log_leak_jsonl(stage, slug, "C01", "curve_quote", c01_found[0], blog_id=blog_id)
                result["first_stage"] = stage if result["first_stage"] is None else result["first_stage"]
            if result["c04_detected"]:
                _log_leak_origin(stage, slug, "C04", "prompt_leak", c04_found[0])
                _log_leak_jsonl(stage, slug, "C04", "prompt_leak", c04_found[0], blog_id=blog_id)
                result["first_stage"] = stage if result["first_stage"] is None else result["first_stage"]
        else:
            if log_every_stage:
                # text는 dedup 유지, JSONL만 추가 기록
                if result["c01_detected"]:
                    _log_leak_jsonl(stage, slug, "C01", "curve_quote", c01_found[0], blog_id=blog_id)
                if result["c04_detected"]:
                    _log_leak_jsonl(stage, slug, "C04", "prompt_leak", c04_found[0], blog_id=blog_id)
            else:
                # 둘 다 dedup — 추가 기록 없음
                pass

    return result


# 후크 등록용 전역 저장소
_HOOKS: list[dict] = []


def register_hook(stage: str, check_fn: Callable[[str, str], dict]) -> None:
    """원인추적 훅 등록.

    Args:
        stage: 지점 식별자 ("after_generation", "after_humanizer", "before_write")
        check_fn: (content, slug) → {"c01_detected": bool, "c04_detected": bool, ...}
    """
    _HOOKS.append({"stage": stage, "check_fn": check_fn})
    logger.info(f"[LEAK-TRACKER] Hook registered: {stage}")


def run_hooks(content: str, slug: str, stage: str, locale: str = "ko") -> dict:
    """해당 stage의 훅을 실행하고 결과 반환."""
    results = []
    for hook in _HOOKS:
        if hook["stage"] == stage:
            result = hook["check_fn"](content, slug)
            result["stage"] = stage
            results.append(result)
    return {"stage": stage, "results": results}
