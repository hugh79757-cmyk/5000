"""Post-publish HTML validation — 발행 품질 자동 검증"""

import logging
import re

logger = logging.getLogger(__name__)

# 검증 대상 블로그 그룹
TAP_TRAVEL_BLOGS = {"travel-hugo", "travel1-hugo", "travel2-hugo", "travel3-hugo", "travel4-hugo"}


def _readability_score(text: str) -> float:
    """Compute a simplified Korean readability score (0.0–1.0).

    Factors:
    - Average sentence length (chars): shorter = more readable
    - Ratio of common Korean particles/endings vs total chars
    - Syllable variety (unique / total)

    Returns score where 1.0 = very readable, 0.0 = very difficult.
    """
    if not text or len(text.strip()) < 20:
        return 0.5

    sentences = re.split(r'[.!?]\s+', text)
    sentences = [s for s in sentences if len(s.strip()) > 5]
    if not sentences:
        return 0.5

    avg_sentence_len = sum(len(s) for s in sentences) / len(sentences)

    # Score 1: sentence length (ideal: 30-60 chars per sentence)
    if avg_sentence_len <= 80:
        len_score = 1.0
    elif avg_sentence_len <= 120:
        len_score = 0.7
    elif avg_sentence_len <= 160:
        len_score = 0.4
    else:
        len_score = 0.2

    # Score 2: Korean particle ratio (은/는/이/가/을/를/의/에/에서)
    particles = len(re.findall(r'[은는이가을를의에에서로으로과와]', text))
    particle_ratio = particles / len(text) if text else 0
    if 0.05 <= particle_ratio <= 0.15:
        particle_score = 1.0
    elif 0.03 <= particle_ratio <= 0.20:
        particle_score = 0.7
    else:
        particle_score = 0.4

    score = (len_score * 0.6 + particle_score * 0.4)
    return round(score, 2)


def _keyword_coverage(text: str, keywords: list[str]) -> dict:
    """Check coverage of target keywords in body text.

    Returns dict with:
      - total: number of keywords checked
      - covered: number of keywords found
      - ratio: coverage ratio 0.0–1.0
      - missing: list of missing keywords
    """
    if not keywords:
        return {"total": 0, "covered": 0, "ratio": 1.0, "missing": []}

    text_lower = text.lower()
    covered = []
    missing = []
    for kw in keywords:
        if kw.lower() in text_lower:
            covered.append(kw)
        else:
            missing.append(kw)

    return {
        "total": len(keywords),
        "covered": len(covered),
        "ratio": round(len(covered) / len(keywords), 2) if keywords else 1.0,
        "missing": missing,
    }


def validate_post_html(html: str, blog_id: str) -> dict:
    """발행된 HTML을 검증하여 품질 이슈 목록 반환

    Returns:
        dict: {"passed": bool, "issues": list[dict]}
    """
    issues = []

    # 1. CTA 존재 여부 (travel 블로그만)
    if blog_id in TAP_TRAVEL_BLOGS:
        if "cta-box" not in html and "cta_box" not in html:
            count = _count_cta_plain_text(html)
            if count == 0:
                issues.append({"severity": "ERROR", "check": "cta_html",
                               "msg": "Trip.com CTA HTML 누락"})
            else:
                issues.append({"severity": "WARNING", "check": "cta_html",
                               "msg": f"CTA가 HTML이 아닌 평문으로 {count}개 존재"})

    # 2. {{}} 잔재 (Hugo 단축코드 {{< ... >}} 는 제외)
    clean = re.sub(r"\{\{<[\s\S]*?>}}", "", html)
    count = clean.count("{{")
    if count > 0:
        issues.append({"severity": "WARNING", "check": "empty_template",
                       "msg": f"{{{{}}}} 빈 템플릿 {count}개 발견"})

    # 3. og:image 썸네일
    if 'property="og:image"' not in html and 'name="twitter:image"' not in html:
        issues.append({"severity": "WARNING", "check": "thumbnail",
                       "msg": "og:image / twitter:image 메타 태그 없음"})

    # 4. 지도보기 평문
    if "지도에서 보기" in html:
        issues.append({"severity": "WARNING", "check": "map_text",
                       "msg": "'지도에서 보기' 평문 잔재"})

    # 5. 최소 본문 글자수 (HTML 태그 제외)
    body_text = re.sub(r"<[^>]+>", "", html)
    body_text = re.sub(r"\s+", " ", body_text).strip()
    if len(body_text) < 500:
        issues.append({"severity": "ERROR", "check": "min_length",
                       "msg": f"본문 {len(body_text)}자 (최소 500자 필요)"})

    # 6. Readability score
    readability_score = _readability_score(body_text)
    if readability_score < 0.3:
        issues.append({"severity": "WARNING", "check": "readability",
                       "msg": f"읽기 어려운 본문 (가독성 점수: {readability_score})"})

    # 7. Keyword coverage
    parts = re.split(r'[-_]', blog_id)
    # 기술 식별자 제외 (블로그 ID 구성요소 중 콘텐츠 키워드가 아닌 것)
    TECH_IDENTIFIERS = {
        'travel', 'travel1', 'travel2', 'travel3', 'travel4',
        'hugo', 'blogger', 'wordpress', 'tap', 'stap', 'cuap',
        'rap', 'senior', 'stock', 'etf', 'dividend', 'sector', 'ipo', 'finance',
        'car', 'appliance', 'baby', 'fitness', 'interior', 'laptop', 'health',
        'pet', 'kitchen', 'beauty', 'camping', 'ev', 'compare', 'deal', 'guide', 'tco',
        'hotissue', 'info', 'rank', 'pick', 'kuta', 'gap', 'tvshow', 'ud',
        'kboplayer', 'kboteam', 'kboschedule', 'proto', 'protostats', 'fstats', 'fsched', 'betguide', 'protoking',
        'aikorea24', 'persona', 'money', 'sports', 'kbo',
        'rotcha', 'techpawz', 'informationhot',
    }
    keywords = [p for p in parts if len(p) > 2 and p.lower() not in TECH_IDENTIFIERS]
    if 'travel' in blog_id.lower():
        keywords.extend(['여행', '맛집'])
    seen = set()
    keywords = [k for k in keywords if not (k in seen or seen.add(k))]

    kw_result = _keyword_coverage(body_text, keywords)
    if kw_result["ratio"] < 0.5:
        issues.append({"severity": "WARNING", "check": "keyword_coverage",
                       "msg": f"키워드 커버리지 낮음 ({kw_result['covered']}/{kw_result['total']}, "
                              f"{kw_result['ratio']:.0%}). 누락: {kw_result['missing']}"})

    return {
        "passed": len([i for i in issues if i["severity"] == "ERROR"]) == 0,
        "issues": issues,
    }


def _count_cta_plain_text(html: str) -> int:
    """트립닷컴 CTA가 HTML 태그 없이 평문으로만 있는지 확인"""
    return len(re.findall(r"트립닷컴에서\s*최저가\s*확인하기", html))
