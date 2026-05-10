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

def sanitize_title(title: str) -> str:
    """제목에서 마크다운 잔여물 제거 + 연속 중복 단어 제거 + 부분 중복 제거"""
    if not title:
        return title
    t = title.strip()
    # 1) 마크다운 볼드/이탤릭 기호 제거
    t = t.replace("**", "").replace("__", "")
    # 2) 연속 동일 단어 제거: "청주시 청주시" → "청주시"
    words = t.split()
    deduped = []
    for w in words:
        if not deduped or w != deduped[-1]:
            deduped.append(w)
    t = " ".join(deduped)
    # 3) 연속 2어절 중복: "A B A B" → "A B"
    import re as _re
    t = _re.sub(r'(\S+\s+\S+)\s+\1', r'\1', t)
    # 4) 뒤쪽 단어가 앞쪽 복합어에 이미 포함된 경우 제거
    #    "여행코스 3곳 코스 추천" → "여행코스 3곳 추천"
    words = t.split()
    cleaned = []
    for i, w in enumerate(words):
        duplicate = False
        for j in range(max(0, i - 3), i):
            if len(w) >= 2 and w in cleaned[j] and w != cleaned[j]:
                duplicate = True
                break
        if not duplicate:
            cleaned.append(w)
        else:
            cleaned.append(w)  # placeholder
    # 실제 제거 로직
    final = []
    for i, w in enumerate(words):
        is_substr = False
        for j in range(max(0, i - 4), i):
            if len(w) >= 2 and w != words[j] and w in words[j]:
                is_substr = True
                break
        if not is_substr:
            final.append(w)
    t = " ".join(final)
    # 5) 공백 정리
    t = _re.sub(r'\s+', ' ', t).strip()
    return t


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
            "WHERE blog_id = ? AND date(created_at) = date('now', '+9 hours')",
            (blog_id,),
        )
        count = cur.fetchone()[0]
        conn.close()
        return count
    except sqlite3.Error as e:
        logger.error(f"[DB_ERROR] Failed to get today count for blog {blog_id}: {e}")
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
    map_queries = re.findall(r'map\.naver\.com/v5/search/([^"\)\s>]+)', body)
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
    # 시스템 삽입 제목은 허용 (부동산 거래, 차량 관리, 여행 준비)
    _SYSTEM_COUPANG_TITLES = [
        "## 부동산 거래 시 유용한 추천 상품",
        "## 차량 관리에 도움되는 추천 용품",
        "## 여행 준비에 도움되는 추천 용품",
    ]
    gpt_coupang_headers = [
        "## 자취", "## 신혼부부 추천", "## 신혼 추천", "## 프리미엄 입주", "## 추천 가전",
        "## 필수 아이템", "## 새집 입주", "## 이사 준비", "## 원룸 필수",
        "## 스마트한 생활",
    ]
    for hdr in gpt_coupang_headers:
        if hdr in body:
            # 시스템 제목에 포함된 경우는 스킵
            is_system = False
            for sys_title in _SYSTEM_COUPANG_TITLES:
                if sys_title in body and hdr in sys_title:
                    is_system = True
                    break
            if not is_system:
                issues.append(
                    f"[ERROR] GPT 자체 쿠팡 상품 섹션 잔존: \"{hdr}\"")
                break
    
    return issues


def _check_internal_links(body: str) -> list:
    """내부링크 섹션 중복 검증."""
    issues = []
    
    # 부분 문자열 중복 매칭 방지: 가장 긴 패턴부터 매칭하고 해당 위치 제거
    _sorted_headers = sorted(_INTERNAL_LINK_HEADERS, key=len, reverse=True)
    _temp_body = body
    link_section_count = 0
    for hdr in _sorted_headers:
        c = _temp_body.count(hdr)
        link_section_count += c
        _temp_body = _temp_body.replace(hdr, "")  # 매칭된 부분 제거하여 중복 카운트 방지
    
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

    # ── 로깅만 (알림은 validate_post_extended에서 통합 발송) ──
    if issues:
        logger.warning(f"[Validate] {blog_id} | {len(issues)} issues: {issues}")

    return issues


# ══════════════════════════════════════════════════════════
# 파이프라인별 추가 검증 함수
# ══════════════════════════════════════════════════════════

def _check_gap(title: str, body: str, ctx: dict) -> list:
    """GAP 전용 검증: 키워드-본문 관련성, 원문 복사 여부."""
    issues = []
    keyword = ctx.get("keyword", "")
    
    # 키워드가 본문에 최소 2회 이상 등장해야 함
    if keyword and body.count(keyword) < 2:
        issues.append(f"[WARNING] 키워드 '{keyword}' 본문 내 {body.count(keyword)}회만 등장 (최소 2회)")
    
    # 원문 복사 의심: 동일 문장이 3줄 연속 인용부호 없이 등장
    lines = body.split("\n")
    long_lines = [l.strip() for l in lines if len(l.strip()) > 80 and not l.strip().startswith(">")]
    if len(long_lines) > 10:
        # 80자 이상 긴 문장이 10개 넘으면 원문 복사 의심
        issues.append(f"[WARNING] 원문 복사 의심: 80자 이상 문장 {len(long_lines)}개")
    
    # 참고자료 출처 표기 확인
    has_source = any(k in body for k in ["출처", "참고", "원문", "자료:"])
    if not has_source:
        issues.append("[WARNING] 참고자료 출처 표기 없음")
    
    return issues


def _load_car_names_from_db() -> list:
    """car.db에서 brand + model을 동적으로 읽어 차량명 리스트 반환.
    DB 접근 실패 시 하드코딩 fallback 리스트 사용."""
    import sqlite3 as _sq
    import os as _os
    _DB_PATH = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "data", "car.db"
    )
    _FALLBACK = [
        "현대", "기아", "제네시스", "쉐보레", "르노", "쌍용", "KG",
        "BMW", "벤츠", "아우디", "폭스바겐", "볼보", "렉서스", "토요타", "혼다", "테슬라", "포르쉐",
        "그랜저", "쏘나타", "아반떼", "투싼", "싼타페", "팰리세이드", "캐스퍼", "코나", "아이오닉",
        "K3", "K5", "K8", "K9", "셀토스", "스포티지", "쏘렌토", "카니발", "EV6", "EV9", "레이",
        "GV60", "GV70", "GV80", "G70", "G80", "G90", "필랑트",
        "그랑 콜레오스", "콜레오스", "QM6", "XM3", "SM6", "아르카나", "캡처",
        "말리부", "트랙스", "트레일블레이저", "이쿼녹스",
        "렉스턴", "토레스", "티볼리", "코란도", "액티언",
        "모델 Y", "모델 3", "모델 S", "모델 X", "사이버트럭",
        "골프", "티구안", "ID.4", "ID.7",
        "캠리", "라브4", "프리우스", "시빅", "어코드",
        "카이엔", "마칸", "파나메라", "타이칸", "911", "718",
        "XC40", "XC60", "XC90", "EX30", "EX90",
        "BYD", "폴스타", "링컨", "레인지로버", "디펜더", "재규어",
    ]
    try:
        if not _os.path.exists(_DB_PATH):
            return _FALLBACK
        conn = _sq.connect(_DB_PATH)
        rows = conn.execute(
            "SELECT DISTINCT brand, model FROM cars WHERE brand IS NOT NULL AND model IS NOT NULL"
        ).fetchall()
        conn.close()
        names = set(_FALLBACK)  # fallback을 기본으로 포함
        for brand, model in rows:
            if brand:
                names.add(brand.strip())
            if model:
                # 모델명 공백 정규화 후 추가
                names.add(model.strip())
                # 복합 모델명(예: "그랑 콜레오스")은 첫 단어도 추가
                parts = model.strip().split()
                if len(parts) >= 2:
                    names.add(parts[0])
        return list(names)
    except Exception:
        return _FALLBACK


def _check_car(title: str, body: str, ctx: dict) -> list:
    """CAR 전용 검증: 차량 데이터 정확성, 제목 품질.
    차량명은 car.db에서 동적 로딩 (신규 모델 자동 반영).
    DB 접근 불가 시 fallback 하드코딩 리스트 사용.
    """
    issues = []
    import re

    _car_names = _load_car_names_from_db()
    # top5_rank / persona_pick 은 세그먼트형 제목 — 차량명 검증 면제
    _post_type = ctx.get("post_type", "")
    _exempt_types = ("top5_rank", "persona_pick", "price_trend")
    if _post_type not in _exempt_types:
        title_has_car = any(name in title for name in _car_names)
        if not title_has_car:
            issues.append(f"[CRITICAL] 제목에 차량명 없음: \"{title[:50]}\"")

    # 가격 데이터 존재 확인
    price_pattern = re.compile(r"\d{1,2},?\d{3}만원|\d+억")
    if not price_pattern.search(body):
        issues.append("[WARNING] 차량 가격 정보 없음")

    # 연식/모델 정보 확인
    year_pattern = re.compile(r"202[4-9]|203[0-9]")
    if not year_pattern.search(body):
        issues.append("[WARNING] 최신 연식 정보 없음 (2024~)")

    # 연비/배기량 등 핵심 스펙 확인
    spec_keywords = ["연비", "배기량", "마력", "토크", "cc", "km/L", "kWh"]
    has_spec = any(k in body for k in spec_keywords)
    if not has_spec:
        issues.append("[WARNING] 차량 핵심 스펙 정보 없음 (연비/배기량/마력)")

    return issues


def _check_travel(title: str, body: str, ctx: dict) -> list:
    """Travel 전용 검증: 축제/행사 날짜, 관광지 유효성."""
    issues = []
    
    # 행사 날짜 경과 여부
    event_date = ctx.get("event_date", "")
    if event_date:
        try:
            from datetime import datetime
            evt = datetime.strptime(event_date[:10], "%Y-%m-%d")
            days_past = (datetime.now() - evt).days
            if days_past > 3:
                issues.append(f"[WARNING] 행사/축제 종료 {days_past}일 경과: {event_date[:10]}")
        except ValueError:
            pass
    
    # 위치/주소 정보 확인
    addr_keywords = ["주소", "위치", "찾아가", "도로명", "지번"]
    has_addr = any(k in body for k in addr_keywords)
    if not has_addr:
        issues.append("[WARNING] 관광지 위치/주소 정보 없음")
    
    # 운영시간/입장료 정보 확인 (문화유산 블로그는 면제 — anti-hallucination 정책)
    _heritage_blogs = ["travel-hugo", "travel1-hugo", "travel2-hugo", "travel3-hugo", "travel4-hugo"]
    _blog_id = ctx.get("blog_id", "")
    if _blog_id not in _heritage_blogs:
        info_keywords = ["운영시간", "영업시간", "브레이크타임", "라스트오더", "입장료", "관람시간", "이용료", "무료", "요금"]
        has_info = any(k in body for k in info_keywords)
        if not has_info:
            issues.append("[WARNING] 운영시간/입장료 정보 없음")
    
    # [PATCH] 빈 데이터 글 감지 — AI가 데이터 없이 채운 글 차단
    empty_signals = [
        "구체적인 축제명이나 일정은 제공되지 않았",
        "구체적으로 제공되지 않았",
        "정보를 확인할 수 없으나",
        "정보가 제공되지 않았",
        "데이터가 부족하여",
        "확인되지 않았으나",
    ]
    empty_count = sum(1 for s in empty_signals if s in body)
    if empty_count >= 2:
        issues.append(f"[CRITICAL] 빈 데이터 글 감지 ({empty_count}개 빈 데이터 표현)")
    
    # [PATCH] 숫자 할루시네이션 감지 — 반복되는 가짜 숫자 차단
    import re as _val_re
    halluc_patterns = [
        _val_re.compile(r"(?:연간?\s*(?:약\s*)?|매년\s*(?:약\s*)?)(\d+)만\s*명"),
        _val_re.compile(r"(?:주차장은?\s*(?:딱|단|약)?\s*)(\d+)대"),
        _val_re.compile(r"(\d+)대\s*(?:수용|분)"),
    ]
    for pat in halluc_patterns:
        matches = pat.findall(body)
        if matches:
            issues.append(f"[CRITICAL] 숫자 할루시네이션 의심: {pat.pattern} → {matches}")
    
    return issues


def _check_senior(title: str, body: str, ctx: dict) -> list:
    """Senior 전용 검증: 정책 시행일, 정부24 데이터 유효성."""
    issues = []
    
    # 정책 시행일 경과 여부
    policy_date = ctx.get("event_date", "") or ctx.get("policy_date", "")
    if policy_date:
        try:
            from datetime import datetime
            pdt = datetime.strptime(policy_date[:10], "%Y-%m-%d")
            days_past = (datetime.now() - pdt).days
            if days_past > 30:
                issues.append(f"[WARNING] 정책 시행일 {days_past}일 경과: {policy_date[:10]}")
        except ValueError:
            pass
    
    # 신청 방법/자격 요건 정보 확인
    req_keywords = ["신청", "자격", "대상", "조건", "구비서류", "제출"]
    has_req = any(k in body for k in req_keywords)
    if not has_req:
        issues.append("[WARNING] 신청 자격/방법 정보 없음")
    
    # 정부24/복지로 등 공식 출처 확인
    gov_sources = ["정부24", "gov.kr", "복지로", "bokjiro", "nhis", "국민건강보험"]
    has_gov = any(k in body for k in gov_sources)
    if not has_gov:
        issues.append("[WARNING] 정부 공식 출처 링크 없음")
    
    return issues


def _check_stap(title: str, body: str, ctx: dict) -> list:
    """STAP 전용 검증: 종목코드, 주가 날짜, 빈 데이터 차단."""
    issues = []
    import re
    from datetime import datetime

    combined = title + " " + body
    data_source = ctx.get("data_source", "")
    is_dividend = "dividend" in data_source

    zero_patterns = [
        (r"\b0억\s*원?", "0억 원"),
        (r"공모가\s*0%|영업이익률\s*0%|순이익률\s*0%", "0%"),
        (r"희석률\s*0%", "희석률 0%"),
        (r"공모가\s*0원", "공모가 0원"),
        (r"\b0만\s*주", "0만 주"),
    ]
    # 배당 블로그: 0% 단독 패턴 제외 (배당률 0%는 정상 문맥)
    if is_dividend:
        zero_patterns = [(p, l) for p, l in zero_patterns if l not in ("0%",)]

    zero_hits = []
    for pat, label in zero_patterns:
        if re.search(pat, combined):
            zero_hits.append(label)
    if zero_hits:
        issues.append(f"[CRITICAL] 파싱 실패 데이터 발행 차단: {', '.join(zero_hits)}")

    missing_signals = [
        "아직 공개되지 않았습니다",
        "아직 공개되지 않은",
        "공개되지 않았습니다",
        "확정되지 않았습니다",
        "미정입니다",
        "미정으로",
        "미공개",
        "추후 공개",
        "추후 확정",
        "아직 확정되지",
        "발표되지 않았",
        "정해지지 않았",
    ]
    missing_count = sum(1 for s in missing_signals if s in body)
    if missing_count >= 3:
        issues.append(f"[CRITICAL] 핵심 데이터 부재 ({missing_count}개 미공개 표현 감지)")

    title_placeholders = re.findall(r"\*\*\d+[억만%원주]", title)
    if title_placeholders:
        issues.append(f"[CRITICAL] 제목에 빈 플레이스홀더: {title_placeholders}")

    stock_codes = re.findall(r"\b\d{6}\b", body)

    date_matches = re.findall(r"(202[4-9])년\s*(\d{1,2})월\s*(\d{1,2})일", body)
    if date_matches:
        latest = None
        for y, m, d in date_matches:
            try:
                dt = datetime(int(y), int(m), int(d))
                if latest is None or dt > latest:
                    latest = dt
            except ValueError:
                continue
        if latest:
            age = (datetime.now() - latest).days
            if age > 7:
                issues.append(f"[WARNING] 주가 데이터 {age}일 경과 ({latest.strftime('%Y-%m-%d')})")

    # 재무지표 체크: stock/dividend 블로그만 적용
    fin_required = any(x in data_source for x in ["stock_", "dividend_", "disclosure"]) and not data_source.startswith("etf_")
    if fin_required:
        fin_keywords = ["매출", "영업이익", "순이익", "PER", "PBR", "ROE", "EPS", "배당"]
        has_fin = sum(1 for k in fin_keywords if k in body)
        if has_fin < 2:
            issues.append(f"[WARNING] 재무 지표 부족 ({has_fin}개, 최소 2개)")

    return issues

_PIPELINE_VALIDATORS = {
    "gap": _check_gap,
    "car": _check_car,
    "travel": _check_travel,
    "senior": _check_senior,
    "stap": _check_stap,
}


def validate_post_extended(
    blog_id: str,
    title: str,
    html_content: str,
    context: dict | None = None,
    pipeline: str = "",
) -> list:
    """확장 검증: 기본 validate_post + 파이프라인별 추가 검증.
    
    pipeline: "gap", "car", "travel", "senior", "stap", "rap" 중 하나.
    RAP은 기존 validate_post에 이미 전용 검증이 포함되어 있으므로 추가 불필요.
    """
    # 기본 검증
    issues = validate_post(blog_id, title, html_content, context)
    
    # 파이프라인별 추가 검증
    pl = pipeline.lower().strip()
    checker = _PIPELINE_VALIDATORS.get(pl)
    if checker:
        try:
            extra = checker(title, html_content or "", context or {})
            issues.extend(extra)
        except Exception as e:
            logger.debug(f"파이프라인 검증 오류 ({pl}): {e}")
    
    # 추가 이슈가 있으면 알림 갱신
    if issues:
        has_critical = any("[CRITICAL]" in i for i in issues)
        try:
            from shared.notify import alert
            severity = "🚨 CRITICAL" if has_critical else "⚠️ WARNING"
            ctx = context or {}
            detail = f"blog: {blog_id}\npipeline: {pl}\ntitle: {title[:50]}\n"
            detail += "\n".join(f"• {i}" for i in issues)
            alert(f"[Validate] {severity} — {len(issues)}건", detail)
        except Exception:
            pass
    

    # ── 검증: 빈 섹션 (## 헤딩 뒤 내용 없음) ──
    _lines = (html_content or "").split("\n")
    for _idx, _line in enumerate(_lines):
        if _line.startswith("## "):
            _has_content = False
            for _k in range(_idx + 1, min(_idx + 5, len(_lines))):
                _s = _lines[_k].strip()
                if _s and not _s.startswith("## ") and not _s.startswith("#") and _s != "---" and _s != ">":
                    _has_content = True
                    break
            if not _has_content:
                issues.append(f"[ERROR] 빈 섹션: {_line.strip()[:40]}")

    # ── 검증: 쿠팡 상품 관련성 (시니어 파이프라인) ──
    if context and context.get("pipeline") == "senior" and "link.coupang" in (html_content or ""):
        _senior_words = ["혈압", "혈당", "영양", "보행", "안마", "난방", "간병",
                        "지팡이", "돋보기", "보청기", "건강", "운동", "미끄럼", "온열",
                        "찜질", "무릎", "관절", "칼슘", "오메가", "루테인", "홍삼",
                        "보스웰리아", "비타민", "유산균", "마그네슘", "아연", "철분",
                        "프로바이오틱스", "혈행", "눈건강", "요가", "스텝퍼", "밴드"]
        for _line in body_md.split("\n"):
            if "link.coupang" in _line and (_line.strip().startswith("- [") or _line.strip().startswith("* [")):
                import re as _re
                _m = _re.search(r'\[(.+?)\]', _line)
                if _m:
                    _product = _m.group(1)
                    _relevant = any(_sw in _product for _sw in _senior_words)
                    if not _relevant:
                        issues.append(f"[ERROR] 쿠팡 비관련 상품: {_product[:40]}")

    return issues
