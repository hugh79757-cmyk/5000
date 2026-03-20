"""blogdex D1 → gap.db 키워드 자동 연동

D1의 Bing 키워드에서 고가치 + GAP 적합 키워드를 추출하여 gap.db에 저장.
스케줄러에서 주 1회 또는 daily로 호출 가능.
"""

import os
import sys
import sqlite3
import logging
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

D1_API_URL = "https://blogdex-api.hugh79757.workers.dev"
D1_API_KEY = "blogdex-secret-key"
GAP_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "gap.db")

# GAP에 적합한 고가치 패턴
HIGH_VALUE_PATTERNS = [
    "신청", "방법", "절차", "가입", "등록", "발급",
    "할인", "쿠폰", "혜택",
    "보험", "대출", "적금", "예금", "투자", "연금",
    "보조금", "지원금", "환급", "세금", "공제",
    "추천", "비교", "가격", "후기", "순위",
    "구매", "구입",
    "조회", "확인", "예약",
    "다시보기",
]

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
]

# 카테고리 자동 분류
CATEGORY_MAP = {
    "세금": ["세금", "연말정산", "종합소득세", "자동차세", "소득세", "공제", "환급"],
    "금융/부동산": ["대출", "적금", "예금", "투자", "연금", "청약", "전세", "보험", "금리"],
    "행정/민원": ["발급", "신고", "등록", "조회", "증명서", "주민등록"],
    "고용/취업": ["실업급여", "근로장려금", "퇴직금", "육아휴직", "채용"],
    "건강/복지": ["건강보험", "건강검진", "복지", "장려금", "기초연금"],
    "자동차/교통": ["자동차", "하이패스", "교통", "범칙금", "차량"],
    "여가/축제": ["축제", "여행", "항공", "예매", "티켓", "다시보기"],
    "생활정보": [],  # 기본값
}


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
    # 최소 2글자 이상, 한글 포함
    if len(query) < 4:
        return False
    has_korean = any('\uac00' <= c <= '\ud7a3' for c in query)
    if not has_korean:
        return False
    return True


def is_high_value(query):
    q = query.lower()
    for p in HIGH_VALUE_PATTERNS:
        if p.lower() in q:
            return True
    return False


def fetch_d1_keywords(limit=1000):
    headers = {"X-API-Key": D1_API_KEY, "Content-Type": "application/json"}
    try:
        r = requests.get(f"{D1_API_URL}/bing/keywords?limit={limit}", headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"D1 키워드 조회 실패: {e}")
        return []


def sync_keywords():
    """D1에서 고가치 키워드를 추출하여 gap.db에 저장"""
    logger.info("=== GAP 키워드 동기화 시작 ===")

    all_kw = fetch_d1_keywords(limit=1000)
    if not all_kw:
        logger.warning("D1에서 키워드 0건")
        return {"added": 0, "skipped": 0, "total": 0}

    logger.info(f"D1에서 {len(all_kw)}건 조회")

    # 필터링: GAP 적합 + 고가치 + 노출 3 이상
    candidates = []
    for kw in all_kw:
        query = kw.get("query", "").strip()
        impressions = kw.get("impressions", 0)
        position = kw.get("position", 99)

        if not is_gap_suitable(query):
            continue
        if not is_high_value(query):
            continue
        if impressions < 3:
            continue

        # 우선순위 계산: 노출 높고 순위 5~20이면 1페이지 진입 가능 = 최고 우선
        if impressions >= 100:
            priority = 1
        elif impressions >= 20 or (5 <= position <= 20):
            priority = 2
        else:
            priority = 3

        candidates.append({
            "keyword": query,
            "category": classify_category(query),
            "priority": priority,
            "impressions": impressions,
            "position": position,
            "site": kw.get("site", ""),
        })

    logger.info(f"필터링 후 후보: {len(candidates)}건")

    # gap.db에 저장
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
            logger.info(f"  추가: [{c['priority']}] {c['keyword']} ({c['category']}) 노출={c['impressions']}")
        except sqlite3.IntegrityError:
            # 이미 존재하면 우선순위만 업데이트 (더 높은 우선순위로)
            existing = conn.execute(
                "SELECT priority FROM keywords WHERE keyword = ?", (c["keyword"],)
            ).fetchone()
            if existing and c["priority"] < existing[0]:
                conn.execute(
                    "UPDATE keywords SET priority = ?, category = ? WHERE keyword = ?",
                    (c["priority"], c["category"], c["keyword"])
                )
                logger.info(f"  업데이트: {c['keyword']} priority {existing[0]} -> {c['priority']}")
            skipped += 1

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM keywords").fetchone()[0]
    conn.close()

    logger.info(f"동기화 완료: 추가 {added}건, 스킵 {skipped}건, 총 {total}건")
    return {"added": added, "skipped": skipped, "total": total}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result = sync_keywords()
    print(f"\n결과: {result}")
