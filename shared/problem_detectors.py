"""problem_detectors.py — 발행 문제 순수 탐지 함수

post_generate / post_validate 훅에서 호출되는 순수 함수 모음.
state 없음, 외부 I/O 없음(HTTP/파일 금지), 기존 시그니처만 재사용.
"""

import logging
import os
import re
import shared.validators
from shared.ai_response_parser import THINKING_PATTERNS, _check_multilingual_leak
from shared.problem_registry import Detection

logger = logging.getLogger(__name__)
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
        det = Detection(problem_id="P09",
                        pattern=f"repeated segments ({dup} of {total})",
                        matched=url, hook="post_generate")
        logger.warning(
            "[P09-detect_repeated_image_url] 감지됨: url=%s pattern=%s",
            url, det.pattern,
        )
        return det
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


def _extract_image_urls_from_content(content: str) -> list[str]:
    """포스트 본문(markdown/HTML 혼합)에서 이미지 URL만 추출.

    대상: markdown ![alt](url), HTML <img src="url">, frontmatter featureimage.
    중복 제거 없이 모두 반환 (호출부에서 개별 검사).
    """
    if not content:
        return []
    urls: list[str] = []
    # frontmatter featureimage
    m = re.search(r"featureimage:\s*[\"']?([^\"'\n]+)[\"']?", content)
    if m and m.group(1).strip():
        urls.append(m.group(1).strip())
    # markdown ![...](url)
    for m in re.finditer(r"!\[[^\]]*\]\(\s*(https?://[^\)]+)\)", content):
        urls.append(m.group(1).strip())
    # HTML <img ... src="url">
    for m in re.finditer(
        r'<img\s[^>]*src\s*=\s*["\'](https?://[^"\'>\s]+)["\']', content, re.IGNORECASE
    ):
        urls.append(m.group(1).strip())
    return urls


def detect_repeated_image_url_in_content(content: str) -> Detection | None:
    """P09 본문 내 이미지 URL 토큰 반복 — URL 단위로 개별 검사.

    detect_repeated_image_url(단일 URL용)을 본문에서 추출한 각 이미지 URL에
    개별 호출하여, 본문 전체가 "/"로 분할되어 오탐되던 문제(BUG-P09-001)를
    수정한다. 위반 URL이 여러 개면 첫 감지 건만 반환 (monitor.report가
    detection 1건씩 처리하므로).
    """
    if not content:
        return None
    for url in _extract_image_urls_from_content(content):
        det = detect_repeated_image_url(url)
        if det is not None:
            return det
    return None


def detect_image_url_length_in_content(content: str) -> Detection | None:
    """P23 본문 내 이미지 URL 길이 초과 — URL 단위로 개별 검사.

    detect_image_url_length(단일 URL용)을 본문에서 추출한 각 이미지 URL에
    개별 호출한다. 본문 전체가 500자를 넘어 오탐되던 문제를 수정.
    (P23도 detect_post_generate에서 본문 전체를 전달하던 동일 패턴.)
    """
    if not content:
        return None
    for url in _extract_image_urls_from_content(content):
        det = detect_image_url_length(url)
        if det is not None:
            return det
    return None


def detect_post_generate(content, blog_id: str) -> list:
    """post_generate raw 디스패처 — P07→P08→P09→P23 전건 반환 (감지 0건이면 []).

    P09/P23은 본문 전체가 아니라 본문에서 추출한 개별 이미지 URL 각각에 대해
    detect_repeated_image_url / detect_image_url_length를 호출한다
    (BUG-P09-001 / BUG-P23-001 수정).
    """
    detections = []
    for detector in (detect_cjk_leak, detect_cot_leak,
                     detect_repeated_image_url_in_content,
                     detect_image_url_length_in_content):
        detection = detector(content)
        if detection is not None:
            detections.append(detection)
    return detections


def detect_empty_content_deployed(blog_id: str, domain: str, site_path: str) -> Detection | None:
    """P32: 라이브 배포 후 본문이 의도치 않게 비었거나 소실된 글 감지.

    판별 로직:
    1. 로컬 저장본에서 canonical URL, wordCount, 섹션 수 추출
       - blog_id로 최신 발행 slug 확인 (content.db publish_ledger)
       - 마크다운 frontmatter의 wordCount / 본문 raw ## 개수
    2. 라이브 HTTP GET → 실제 렌더된 HTML에서:
       - HTTP 200 확인
       - schema.org wordCount 확인 (JSON-LD에서)
       - 본문 텍스트 단어수 확인 (태그 제거 후 공백 분리)
       - h2 + strong 섹션 헤딩 존재 확인
    3. 비교 판정:
       - HTTP 200 + wordCount ≥ 200 + 섹션 ≥ 3 → 정상 (None)
       - HTTP 200 + wordCount < 200 → P32: "빈 글"
       - HTTP 404/리다이렉트 → "배포문제" (P32 아님, 별도 추적)
       - 로컬 content 있으나 라이브에 없음 → "배포 누락" (P32 아님)

    임계: 단어수 ≥ 200, 섹션 ≥ 3
    """
    import sqlite3 as _sql
    import requests as _requests
    import re as _re

    _db = _sql.connect(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data", "content.db"))
    _db.row_factory = _sql.Row

    # 최신 발행된 해당 blog_id 글의 slug 확인
    _row = _db.execute(
        "SELECT slug FROM publish_ledger WHERE blog_id=? AND status='published' "
        "ORDER BY created_at DESC LIMIT 1",
        (blog_id,)
    ).fetchone()

    if not _row:
        _db.close()
        return None  # 발행 기록 없음 — 감지 대상 아님

    _slug = _row["slug"]
    _canonical_url = f"https://{domain}/posts/{_slug}/"

    # 로컬 저장본 로드
    _local_path = os.path.join(site_path, "content", "posts", _slug, "index.md")
    if not os.path.exists(_local_path):
        _db.close()
        return None  # 로컬 파일 없음 — 감지 대상 아님

    with open(_local_path, "r") as _f:
        _local_content = _f.read()

    # frontmatter 분리
    _fm_match = _re.match(r"^---\n(.*?)\n---\n", _local_content, _re.DOTALL)
    _body = _local_content[_fm_match.end():] if _fm_match else _local_content

    # 로컬 본문 통계
    _local_word_count = len(_body.split())
    _local_h2_count = len(_re.findall(r"^## ", _body, _re.MULTILINE))
    # strong 문단형 섹션 헤딩도 의미적 섹션으로 (H2-GUARD 적용 후 시뮬레이션)
    _local_strong_sections = len(_re.findall(
        r"<p><strong>[^<]{10,}", _body
    ))  # <p><strong>로 시작하는 문단형 헤딩
    _local_semantic_sections = _local_h2_count + _local_strong_sections

    _db.close()

    # 라이브 HTTP 요청 (P32는 발행 후 검증용 외부 I/O 예외 허용)
    try:
        _resp = _requests.get(_canonical_url, timeout=10, headers={
            "User-Agent": "P32-content-validator/1.0"
        })
    except Exception as _e:
        return None  # 네트워크 오류 — 감지 보류

    # HTTP 상태 코드 판정
    if _resp.status_code != 200:
        # 404는 "배포문제", 리다이렉트는 "경로 불일치" — P32 아님
        return None

    _html = _resp.text

    # schema.org wordCount 추출
    _schema_wc = None
    _m = _re.search(r'"wordCount"\s*:\s*"(\d+)"', _html)
    if _m:
        _schema_wc = int(_m.group(1))

    # 본문 텍스트 단어 수 (<script>, <style>, <nav> 등 제외 후)
    _body_text = _re.sub(r'<(script|style|nav|header|footer)[^>]*>.*?</\1>', '', _html, flags=_re.DOTALL|re.IGNORECASE)
    _body_text = _re.sub(r'<[^>]+>', ' ', _body_text)
    _body_text = _re.sub(r'\s+', ' ', _body_text).strip()
    _live_text_wc = len(_body_text.split())

    # 라이브 헤딩 확인 (h2 + 의미적 strong 섹션)
    _live_h2 = len(_re.findall(r'<h2[^>]*>', _html))
    _live_strong_sections = len(_re.findall(
        r'<p[^>]*><strong>[^<]{10,}', _html
    ))
    _live_semantic_sections = _live_h2 + _live_strong_sections

    # 판정: wordCount ≥ 200 && semantic_sections ≥ 3
    _min_word_count = max(_schema_wc or 0, _live_text_wc)
    _min_semantic = max(_local_semantic_sections, _live_semantic_sections)

    if _min_word_count < 200 or _min_semantic < 3:
        _reason = []
        if _min_word_count < 200:
            _reason.append(f"단어수 부족 (로컬 {len(_body.split())}, 라이브 schema { _schema_wc}, 텍스트 { _live_text_wc})")
        if _min_semantic < 3:
            _reason.append(f"섹션 수 부족 (로컬 semantic { _local_semantic_sections}, 라이브 { _live_semantic_sections})")
        return Detection(
            problem_id="P32",
            pattern="empty_deployed_content",
            matched="; ".join(_reason),
            hook="post_deploy"
        )

    return None
