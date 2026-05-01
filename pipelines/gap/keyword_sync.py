# keyword_sync.py 수정 — is_high_value 완화 + 네이버 자동완성 추가

"""blogdex D1 → gap.db 키워드 자동 연동

D1의 Bing 키워드에서 GAP 적합 키워드를 추출하여 gap.db에 저장.
+ 네이버 자동완성/연관검색어에서 추가 수집.
스케줄러에서 주 1회 또는 daily로 호출 가능.
"""

import os
import sys
import sqlite3
import logging
import requests
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

D1_API_URL = "https://blogdex-api.hugh79757.workers.dev"
D1_API_KEY = "blogdex-secret-key"
GAP_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "gap.db")

# GAP에 부적합한 키워드 (제외 대상)
EXCLUDE_PATTERNS = [
    "번역기", "구글번역", "파파고", "번역",
    "게임", "포키", "끄투", "타자연습",
    "lol", "메렌", "커스포지",
    "갤러리", "메갤",
    "아이스크림몰", "비바샘",
    "길찾기", "지도",
    "다시보기", "다시 보기", "누누티비",
    "르노필랑트", "5090",
    "ev2", "ev 2",
    "날씨", "운세", "로또",
    "야동", "성인", "토렌트", "웹툰무료",
]

# 카테고리 자동 분류 (확장)
CATEGORY_MAP = {
    "세금/재테크": ["세금", "연말정산", "종합소득세", "자동차세", "소득세", "공제", "환급", "적금", "예금", "금리", "연금", "IRP", "CMA", "펀드"],
    "금융/부동산": ["대출", "투자", "청약", "전세", "보험", "아파트", "분양", "임대", "매매", "부동산", "주택", "빌라", "오피스텔"],
    "행정/민원": ["발급", "신고", "등록", "증명서", "주민등록", "여권", "전입신고", "경력조회"],
    "고용/취업": ["실업급여", "근로장려금", "퇴직금", "육아휴직", "채용", "알바", "구직", "일자리"],
    "건강/복지": ["건강보험", "건강검진", "복지", "장려금", "기초연금", "병원", "증상", "치료", "수술", "약국"],
    "자동차/교통": ["자동차", "하이패스", "교통", "범칙금", "차량", "전기차", "보험료"],
    "여행/축제": ["축제", "여행", "항공", "예매", "티켓", "벚꽃", "관광", "숙소", "호텔", "항공권", "캠핑"],
    "생활/보조금": ["보조금", "지원금", "직불금", "바우처"],
    "생활정보": [],  # 기본값
}

# 우선순위 부스트 키워드 (광고 단가 높은 주제)
HIGH_VALUE_BOOST = [
    "신청", "방법", "절차", "가입", "등록", "발급",
    "할인", "쿠폰", "혜택",
    "보험", "대출", "적금", "예금", "투자", "연금",
    "보조금", "지원금", "환급", "세금", "공제",
    "추천", "비교", "가격", "후기", "순위",
    "구매", "구입", "조회", "확인", "예약",
]


def classify_category(query):
    q = query.lower()
    for cat, patterns in CATEGORY_MAP.items():
        for p in patterns:
            if p in q:
                return cat
    return "생활정보"


def is_gap_suitable(query):
    q = query.lower()
    for p in EXCLUDE_PATTERNS:
        if p.lower() in q:
            return False
    if len(query) < 4:
        return False
    has_korean = any('\uac00' <= c <= '\ud7a3' for c in query)
    if not has_korean:
        return False
    return True


def calc_priority(query, impressions, position):
    """우선순위 계산 — 고가치 패턴은 부스트만, 차단 안 함"""
    base = 3
    if impressions >= 100:
        base = 1
    elif impressions >= 20 or (5 <= position <= 20):
        base = 2

    # 고가치 패턴이면 1단계 부스트
    q = query.lower()
    for p in HIGH_VALUE_BOOST:
        if p in q:
            base = max(1, base - 1)
            break

    return base


def fetch_d1_keywords(limit=10000):
    """D1에서 키워드 조회 — limit 확대"""
    headers = {"X-API-Key": D1_API_KEY, "Content-Type": "application/json"}
    try:
        r = requests.get(f"{D1_API_URL}/bing/keywords?limit={limit}", headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"D1 키워드 조회 실패: {e}")
        return []


# ── B. 네이버 자동완성 / 연관검색어 수집 ──

def fetch_naver_suggestions(seed_keywords):
    """네이버 자동완성에서 키워드 확장"""
    suggestions = []
    for seed in seed_keywords:
        try:
            url = f"https://ac.search.naver.com/nx/ac?q={seed}&con=1&frm=nv&ans=2&r_format=json&r_enc=UTF-8&r_unicode=0&t_koreng=1&run=2&rev=4&q_enc=UTF-8"
            r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                items = data.get("items", [])
                for item_group in items:
                    for pair in item_group:
                        if isinstance(pair, list) and len(pair) > 0:
                            suggestions.append(pair[0])
                        elif isinstance(pair, str):
                            suggestions.append(pair)
        except Exception as e:
            logger.warning(f"네이버 자동완성 실패 [{seed}]: {e}")
    return list(set(suggestions))


def fetch_naver_related(seed_keywords):
    """네이버 연관검색어 수집"""
    related = []
    for seed in seed_keywords:
        try:
            url = f"https://ac.search.naver.com/nx/ac?q={seed}&con=1&frm=nv&ans=2&r_format=json&r_enc=UTF-8&r_unicode=0&t_koreng=1&run=2&rev=4&q_enc=UTF-8"
            r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                items = data.get("items", [])
                for item_group in items:
                    for pair in item_group:
                        if isinstance(pair, list) and len(pair) > 0:
                            related.append(pair[0])
                        elif isinstance(pair, str):
                            related.append(pair)
        except Exception as e:
            logger.warning(f"네이버 연관검색어 실패 [{seed}]: {e}")
    return list(set(related))


# 시드 키워드 (카테고리별 대표 검색어)
SEED_KEYWORDS = [
    # 세금/재테크
    "연말정산", "종합소득세", "자동차세 연납", "근로장려금", "세금 환급",
    "청년도약계좌", "적금 추천", "연금저축",
    # 금융/부동산
    "청약 일정", "아파트 분양", "전세자금대출", "주택담보대출", "부동산 전망",
    "임대차계약", "전세보증보험",
    # 건강
    "건강검진 대상", "독감 예방접종", "건강보험료", "기초연금 자격",
    # 행정
    "주민등록등본 발급", "여권 갱신", "전입신고", "예방접종증명서",
    # 여행
    "벚꽃 축제 2026", "항공권 특가", "제주도 여행", "캠핑장 추천",
    # 자동차
    "자동차 보험 비교", "전기차 보조금", "자동차 검사",
    # 생활
    "관리비 절약", "이사 체크리스트", "보조금 신청",
    # 고용
    "실업급여 신청", "퇴직금 계산", "육아휴직 급여",
]


def sync_keywords():
    """D1 + 네이버 자동완성에서 키워드 수집하여 gap.db에 저장"""
    logger.info("=== GAP 키워드 동기화 시작 (완화 버전) ===")

    # ── 소스 1: D1 Bing ──
    all_kw = fetch_d1_keywords(limit=10000)
    logger.info(f"D1에서 {len(all_kw)}건 조회")

    candidates = []
    for kw in all_kw:
        query = kw.get("query", "").strip()
        impressions = kw.get("impressions", 0)
        position = kw.get("position", 99)

        if not is_gap_suitable(query):
            continue
        # 노출 1회 이상이면 통과 (기존 3회 → 1회로 완화)
        if impressions < 1:
            continue

        priority = calc_priority(query, impressions, position)
        candidates.append({
            "keyword": query,
            "category": classify_category(query),
            "priority": priority,
            "source": "d1_bing",
        })

    logger.info(f"D1 필터링 후: {len(candidates)}건")

    # ── 소스 2: 네이버 자동완성 ──
    logger.info(f"네이버 자동완성 수집 시작 (시드 {len(SEED_KEYWORDS)}개)")
    naver_kws = fetch_naver_suggestions(SEED_KEYWORDS)
    logger.info(f"네이버 자동완성: {len(naver_kws)}건 수집")

    for query in naver_kws:
        query = query.strip()
        if not is_gap_suitable(query):
            continue
        candidates.append({
            "keyword": query,
            "category": classify_category(query),
            "priority": 3,
            "source": "naver_suggest",
        })

    logger.info(f"총 후보: {len(candidates)}건")

    # ── gap.db에 저장 ──
    conn = sqlite3.connect(GAP_DB_PATH)
    added = 0
    skipped = 0

    for c in candidates:
        try:
            conn.execute(
                "INSERT INTO keywords (keyword, category, priority) VALUES (?, ?, ?)",
                (c["keyword"], c["category"], c["priority"])
            )
            added += 1
        except sqlite3.IntegrityError:
            existing = conn.execute(
                "SELECT priority FROM keywords WHERE keyword = ?", (c["keyword"],)
            ).fetchone()
            if existing and c["priority"] < existing[0]:
                conn.execute(
                    "UPDATE keywords SET priority = ?, category = ? WHERE keyword = ?",
                    (c["priority"], c["category"], c["keyword"])
                )
            skipped += 1

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM keywords WHERE status='active'").fetchone()[0]
    conn.close()

    logger.info(f"동기화 완료: 추가 {added}건, 스킵 {skipped}건, 총 {total}건")
    return {"added": added, "skipped": skipped, "total": total}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result = sync_keywords()
    print(f"\n결과: {result}")