"""발행 전 검증 (Pre-publish Validation)

validate_post() → 문제 리스트 반환 (비어있으면 통과)
검증 실패가 발행을 중단시키지 않도록 호출부에서 try/except 필수.
"""
import re
import os
import sqlite3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── 상수 ──
_AI_RESIDUES = ["다듬은 제목", "추천 제목", "```", "##", "title:", "제목 후보"]
_MIN_TITLE_LEN = 10
_MAX_TITLE_LEN = 80
_MIN_BODY_CHARS = 500
_DUP_HOURS = 72
_DUP_JACCARD_THRESHOLD = 0.7
_STALE_DAYS = 7
_DAILY_QUOTA_DEFAULT = 5

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "content.db")

# ── 네이버지도 비지역 키워드 (지도 버튼이 있으면 안 되는 키워드) ──
_NO_MAP_KEYWORDS = [
    "세금", "양도", "취득세", "종부세", "공시지가", "보증보험", "계약서",
    "임대차", "3법", "청약", "당첨", "확률", "일정", "신청", "공고",
    "청년", "LH", "임대주택", "공공임대", "행복주택", "안심주택",
    "가이드", "총정리", "핵심", "방법", "높이는", "실거래가", "전세사기",
    "단기임대", "체크리스트", "아파트실거래가", "아파트매매",
    "2주택", "1가구", "종합부동산세", "보증금", "확정일자",
]

# ── 쿠팡 검증 ──
_MAX_COUPANG_DISCLAIMERS = 1
_COUPANG_DISCLAIMER_PATTERN = "쿠팡 파트너스 활동의 일환"

# ── 내부링크 검증 ──
_INTERNAL_LINK_HEADERS = ["## 함께 읽", "## 관련 글", "## 추천 글", "## 더 읽", "## 함께 읽어보기"]


def _strip_html(html: str) -> str:
    """HTML 태그 제거 후 순수 텍스트 반환."""
    text = re.sub(r"<[^>]+>", "", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _jaccard(a: str, b: str) -> float:
    """단어 기반 Jaccard 유사도."""
    sa = set(a.split())
    sb = set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _get_recent_titles(blog_id: str, hours: int = _DUP_HOURS) -> list:
    """최근 N시간 내 발행된 (title, keyword) 쌍 조회."""
    if not os.path.exists(_DB_PATH):
        return []
    try:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.execute(
            "SELECT title, keyword FROM publish_ledger "
            "WHERE blog_id = ? AND created_at >= ? ORDER BY created_at DESC",
            (blog_id, since),
        )
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.debug(f"발행 이력 조회 실패: {e}")
        return []


def _get_today_count(blog_id: str) -> int:
    """오늘 발행 건수 조회."""
    if not os.path.exists(_DB_PATH):
        return 0
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.execute(
            "SELECT COUNT(*) FROM publish_ledger "
            "WHERE blog_id = ? AND date(created_at) = date('now')",
            (blog_id,),
        )
        count = cur.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def _check_naver_map(body: str, keyword: str) -> list:
    """네이버 지도 버튼 검증.
    
    비지역 키워드에 지도 버튼이 삽입되었으면 CRITICAL 문제.
    반복적으로 재발하는 버그이므로 엄격하게 검사.
    """
    issues = []
    has_map = "map.naver.com" in body
    
    if not has_map:
        return issues
    
    # 비지역 키워드인데 지도 버튼이 있으면 → 심각한 오류
    is_non_location = any(nk in (keyword or "") for nk in _NO_MAP_KEYWORDS)
    if is_non_location:
        issues.append(
            f"[CRITICAL] 비지역 키워드에 네이버지도 삽입됨: \"{keyword}\"")
    
    # 지도 검색어 추출하여 비정상 검색어 확인
    map_queries = re.findall(r'map\.naver\.com/v5/search/([^"]+)"', body)
    if map_queries:
        from urllib.parse import unquote
        for mq in map_queries:
            decoded = unquote(mq)
            # 비지역 키워드가 검색어에 포함되어 있으면
            for nk in _NO_MAP_KEYWORDS:
                if nk in decoded:
                    issues.append(
                        f"[CRITICAL] 지도 검색어에 비지역 키워드: \"{decoded}\"")
                    break
    
    return issues


def _check_coupang(body: str) -> list:
    """쿠팡 링크/면책 중복 검증."""
    issues = []
    
    # 면책 문구 중복 검사
    discl_count = body.count(_COUPANG_DISCLAIMER_PATTERN)
    if discl_count > _MAX_COUPANG_DISCLAIMERS:
        issues.append(
            f"[ERROR] 쿠팡 면책 {discl_count}회 중복 (허용: {_MAX_COUPANG_DISCLAIMERS}회)")
    
    # GPT가 자체 생성한 쿠팡 상품 섹션 잔존 확인
    gpt_coupang_headers = [
        "## 자취", "## 신혼", "## 프리미엄 입주", "## 추천 가전", "## 필수 아이템"
    ]
    for hdr in gpt_coupang_headers:
        if hdr in body:
            issues.append(
                f"[ERROR] GPT 자체 쿠팡 상품 섹션 잔존: \"{hdr}\"")
            break
    
    return issues


def _check_internal_links(body: str) -> list:
    """내부링크 섹션 중복 검증."""
    issues = []
    
    link_section_count = 0
    for hdr in _INTERNAL_LINK_HEADERS:
        link_section_count += body.count(hdr)
    
    if link_section_count > 1:
        issues.append(
            f"[ERROR] 내부링크 섹션 {link_section_count}개 중복 (허용: 1개)")
    
    return issues


def _check_disclaimer(body: str) -> list:
    """면책조항(국토교통부 등) 중복 검증."""
    issues = []
    
    patterns = [
        "이 글은 국토교통부",
        "이 글은 한국부동산원",
        "계약 전 반드시 등기부등본",
        "투자 판단의 책임은 본인",
    ]
    for pat in patterns:
        cnt = body.count(pat)
        if cnt > 1:
            issues.append(
                f"[ERROR] 시스템 면책 중복 ({cnt}회): \"{pat[:20]}…\"")
            break
    
    return issues


def validate_post(
    blog_id: str,
    title: str,
    html_content: str,
    context: dict | None = None,
) -> list:
    """발행 전 검증. 반환값: 문제 리스트 (비어있으면 정상).

    context 키:
        keyword     — 고유 식별자 (topic_key 역할)
        event_date  — 이벤트 날짜 (YYYY-MM-DD)
        daily_quota — 일일 한도
    """
    ctx = context or {}
    keyword = ctx.get("keyword", "")
    issues = []

    # ── 1. 제목 품질 ──
    t = (title or "").strip()
    if len(t) < _MIN_TITLE_LEN:
        issues.append(f"제목 너무 짧음 ({len(t)}자): {t[:30]}")
    if len(t) > _MAX_TITLE_LEN:
        issues.append(f"제목 너무 김 ({len(t)}자): {t[:50]}…")
    for res in _AI_RESIDUES:
        if res in t:
            issues.append(f"AI 잔여물 감지: \"{res}\" in \"{t[:40]}\"")
            break

    # ── 2. 본문 길이 ──
    plain = _strip_html(html_content)
    if len(plain) < _MIN_BODY_CHARS:
        issues.append(f"본문 부족 ({len(plain)}자 < {_MIN_BODY_CHARS}자)")

    # ── 3. 유사 제목 중복 (72h) ──
    recent = _get_recent_titles(blog_id, _DUP_HOURS)
    for prev_title, prev_keyword in recent:
        if keyword and prev_keyword and keyword == prev_keyword:
            continue
        sim = _jaccard(t, prev_title or "")
        if sim >= _DUP_JACCARD_THRESHOLD:
            issues.append(
                f"유사 제목 중복 (Jaccard {sim:.2f}): \"{prev_title[:40]}\"")
            break

    # ── 4. 오래된 데이터 감지 ──
    event_str = ctx.get("event_date", "")
    if event_str:
        try:
            event_dt = datetime.strptime(event_str[:10], "%Y-%m-%d")
            age = (datetime.now() - event_dt).days
            if age > _STALE_DAYS:
                issues.append(f"오래된 데이터 ({age}일 전): {event_str[:10]}")
        except ValueError:
            pass

    # ── 5. 일일 발행 폭주 ──
    quota = ctx.get("daily_quota", _DAILY_QUOTA_DEFAULT)
    today_count = _get_today_count(blog_id)
    if today_count >= quota:
        issues.append(f"일일 한도 초과 ({today_count}/{quota}건)")

    # ══════════════════════════════════════════════
    # 6. 네이버 지도 버튼 검증 [CRITICAL]
    #    반복 재발 버그 — 비지역 키워드에 지도 삽입 방지
    # ══════════════════════════════════════════════
    issues.extend(_check_naver_map(html_content, keyword))

    # ── 7. 쿠팡 링크/면책 중복 검증 ──
    issues.extend(_check_coupang(html_content))

    # ── 8. 내부링크 섹션 중복 검증 ──
    issues.extend(_check_internal_links(html_content))

    # ── 9. 시스템 면책 중복 검증 ──
    issues.extend(_check_disclaimer(html_content))

    # ── 알림 (문제 있을 때만) ──
    if issues:
        # CRITICAL 있으면 무조건 알림
        has_critical = any("[CRITICAL]" in i for i in issues)
        try:
            from shared.notify import alert
            severity = "🚨 CRITICAL" if has_critical else "⚠️ WARNING"
            detail = f"blog: {blog_id}\nkeyword: {keyword}\ntitle: {t[:50]}\n"
            detail += "\n".join(f"• {i}" for i in issues)
            alert(f"[Validate] {severity} — {len(issues)}건", detail)
        except Exception:
            pass

        logger.warning(f"[Validate] {blog_id} | {len(issues)} issues: {issues}")

    return issues
