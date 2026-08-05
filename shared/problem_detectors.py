"""problem_detectors.py — 발행 문제 순수 탐지 함수

post_generate / post_validate 훅에서 호출되는 순수 함수 모음.
state 없음, 외부 I/O 없음(HTTP/파일 금지), 기존 시그니처만 재사용.
"""

import shared.validators
from shared.ai_response_parser import THINKING_PATTERNS, _check_multilingual_leak
from shared.problem_registry import Detection

_P15_ISSUE_KEYS = frozenset({
    "cta_html",
    "curation_cta",
    "empty_template",
    "thumbnail",
    "map_text",
    "min_length",
    "readability",
    "keyword_coverage",
})

_P19_ISSUE_KEYS = frozenset({
    "stale",
    "event_expired",
})


def detect_cjk_leak(text: str) -> Detection | None:
    """P07 CJK 누수 — 2단 분기 (CJK 오탐 방지 계약 4 준수)."""
    if not text:
        return None
    has_cjk = shared.validators.has_cjk(text)
    is_korean = shared.validators.is_korean_content(text, min_hangul_ratio=0.5)
    if has_cjk and not is_korean:
        _, _, matched = _check_multilingual_leak(text)
        if not matched:
            chars = shared.validators.cjk_chars(text)
            matched = "".join(chars[:20]) or text[:80]
        return Detection(problem_id="P07", pattern="ratio<0.5",
                         matched=matched, hook="post_generate")
    _, pattern_name, matched = _check_multilingual_leak(text)
    if pattern_name == "cjk_instruction_leak":
        return Detection(problem_id="P07", pattern="cjk_instruction_leak",
                         matched=matched or "", hook="post_generate")
    return None


def detect_cot_leak(text: str) -> Detection | None:
    """P08 LLM/CoT 누수 — thinking_leak만 (cjk_instruction_leak은 P07로 분기)."""
    if not text:
        return None
    _, pattern_name, matched = _check_multilingual_leak(text)
    if pattern_name == "thinking_leak":
        return Detection(problem_id="P08", pattern="thinking_leak",
                         matched=matched or "", hook="post_generate")
    return None


def detect_repeated_image_url(url: str) -> Detection | None:
    """P09 이미지 URL 토큰 반복 — 세그먼트 중복 비율 탐지."""
    if not url:
        return None
    segments = url.split("/")
    total = len(segments)
    unique = len(set(segments))
    if unique < total / 2:
        dup = total - unique
        return Detection(problem_id="P09",
                         pattern=f"repeated segments ({dup} of {total})",
                         matched=url, hook="post_generate")
    return None


def detect_image_url_length(url: str) -> Detection | None:
    """P23 이미지 URL 길이 초과 — sanitize_featureimage_url 500자 제한과 동일 기준."""
    if not url:
        return None
    if len(url) > 500:
        return Detection(problem_id="P23", pattern="url length",
                         matched=str(len(url)), hook="post_generate")
    return None


def detect_validation_issue(check_result, blog_id: str) -> Detection | None:
    """P15 발행 후 검증 실패 (+P19 오래된 데이터 — quiet 로그용).

    check_result: shared.post_validator.validate_post_html 반환 dict.
    dict가 아니면 예외가 자연 발생 (caller가 P24 처리).
    """
    issues = check_result.get("issues", [])
    for issue in issues:
        if isinstance(issue, dict):
            key = issue.get("check")
            value = issue.get("msg", "")
        else:
            key = issue
            value = str(issue)
        if key in _P15_ISSUE_KEYS:
            return Detection(problem_id="P15", pattern=key,
                             matched=str(value), hook="post_validate")
        if key in _P19_ISSUE_KEYS:
            return Detection(problem_id="P19", pattern="stale",
                             matched=str(value), hook="post_validate")
    return None


def detect_post_generate(content, blog_id: str) -> list:
    """post_generate raw 디스패처 — P07→P08→P09→P23 전건 반환 (감지 0건이면 [])."""
    detections = []
    for detector in (detect_cjk_leak, detect_cot_leak,
                     detect_repeated_image_url, detect_image_url_length):
        detection = detector(content)
        if detection is not None:
            detections.append(detection)
    return detections
