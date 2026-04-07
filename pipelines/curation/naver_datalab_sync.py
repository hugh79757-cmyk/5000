#!/usr/bin/env python3
"""
네이버 데이터랩 쇼핑인사이트 → curation keywords.py 자동 동기화
실행: python3 pipelines/curation/naver_datalab_sync.py [blog_id]
스케줄: 매주 월요일 자동 실행 권장
"""

import os
import sys
import json
import sqlite3
import time
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# ── 환경 설정 ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[2]  # /Users/twinssn/Projects/5000
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

NAVER_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
DB_PATH             = BASE_DIR / "data" / "curation.db"
KEYWORDS_PATH       = BASE_DIR / "pipelines" / "curation" / "keywords.py"

# ── 카테고리 코드 매핑 (네이버쇼핑 cat_id) ────────────────────────────────
CATEGORY_MAP = {
    "baby-hugo":     {"name": "출산/육아",     "cat_id": "50005535"},
    "fitness-hugo":  {"name": "스포츠/레저",   "cat_id": "50000075"},
    "laptop-hugo":   {"name": "컴퓨터",        "cat_id": "50000006"},
    "appliance-hugo":{"name": "가전디지털",    "cat_id": "50000008"},
    "interior-hugo": {"name": "가구/인테리어", "cat_id": "50000033"},
}

# ── 트렌드 점수 계산 기간 ────────────────────────────────────────────────
TREND_DAYS = 30  # 최근 30일 평균 클릭률 기준


# ════════════════════════════════════════════════════════════════════════════
# 1. 네이버 데이터랩 API: 분야 내 인기 키워드 TOP N 조회
# ════════════════════════════════════════════════════════════════════════════

def fetch_top_keywords(cat_id: str, top_n: int = 100) -> list[dict]:
    """
    쇼핑인사이트 분야별 인기 키워드 조회
    → 반환: [{"keyword": str, "ratio": float}, ...] (ratio 높은 순)
    
    ※ 네이버 API는 키워드 트렌드 비교만 가능하고 '분야 내 TOP 키워드 목록'을
      직접 제공하지 않으므로, 사전 시드 키워드를 기반으로 ratio를 비교해
      상위 키워드를 선별하는 방식을 사용합니다.
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        logger.error("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 미설정")
        return []

    # 시드 키워드 (카테고리별 초기 풀)
    SEED_KEYWORDS = {
        "50005535": [  # 출산/육아
            "기저귀 추천", "기저귀 브랜드", "신생아 기저귀", "분유", "유모차", "카시트", "아기띠", "힙시트",
            "젖병", "유축기", "수유패드", "이유식", "아기 물티슈",
            "신생아 의류", "아기 보습제", "아기 샴푸", "아기 로션",
            "아기 욕조", "바운서", "점퍼루", "아기 매트", "안전문",
            "아기 침대", "범퍼침대", "모빌", "치발기", "딸랑이",
            "아기 식탁의자", "이유식 용기", "아기 숟가락", "아기 컵",
            "기저귀가방", "수유쿠션", "아기 선크림", "배앓이 패드",
            "신생아 카시트", "신생아 속싸개", "아기 내복", "아기 수면조끼",
            "아기 보행기", "아기 쏘서", "아기 장난감", "블록 장난감",
            "레고 듀플로", "물티슈", "베베드피노", "베베숲",
            "돌반지", "탯줄도장", "백일 선물", "돌잔치 답례품",
            "아기 사진관", "육아일기",
        ],
        "50000075": [  # 스포츠/레저
            "러닝화", "요가매트", "덤벨", "아령", "줄넘기", "폼롤러",
            "스트레칭밴드", "헬스장갑", "운동복", "레깅스",
            "사이클링복", "수영복", "등산화", "등산배낭", "트레킹폴",
            "텐트", "침낭", "캠핑의자", "캠핑테이블", "인라인스케이트",
        ],
        "50000006": [  # 컴퓨터
            "노트북", "맥북", "게이밍 노트북", "SSD", "RAM", "그래픽카드",
            "키보드", "마우스", "모니터", "웹캠", "마이크",
            "외장하드", "USB허브", "노트북 거치대", "노트북 파우치",
        ],
        "50000008": [  # 가전디지털
            "에어프라이어", "로봇청소기", "공기청정기", "가습기", "제습기",
            "전기밥솥", "전자레인지", "식기세척기", "블렌더", "커피머신",
            "청소기", "세탁기", "냉장고", "전기히터", "선풍기",
        ],
        "50000033": [  # 가구/인테리어
            "책상", "의자", "소파", "침대", "매트리스", "조명", "커튼",
            "러그", "선반", "수납함", "옷걸이", "행거", "화분", "인테리어소품",
        ],
    }

    seeds = SEED_KEYWORDS.get(cat_id, [])
    if not seeds:
        logger.warning(f"cat_id {cat_id}에 대한 시드 키워드 없음")
        return []

    end_date   = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=TREND_DAYS)).strftime("%Y-%m-%d")

    # API 한 번에 최대 5개 키워드 비교 가능 → 배치 처리
    BATCH = 5
    all_results = {}

    for i in range(0, len(seeds), BATCH):
        batch = seeds[i:i+BATCH]
        payload = {
            "startDate": start_date,
            "endDate":   end_date,
            "timeUnit":  "date",
            "category":  cat_id,
            "keyword": [
                {"name": kw, "param": [kw]}
                for kw in batch
            ],
        }
        try:
            resp = requests.post(
                "https://openapi.naver.com/v1/datalab/shopping/category/keywords",
                headers={
                    "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
                    "Content-Type":          "application/json",
                },
                data=json.dumps(payload),
                timeout=10,
            )
            if resp.status_code != 200:
                logger.error(f"API 오류 {resp.status_code}: {resp.text[:200]}")
                time.sleep(1)
                continue

            data = resp.json()
            for result in data.get("results", []):
                kw    = result["title"]
                ratios = [d["ratio"] for d in result.get("data", [])]
                avg   = sum(ratios) / len(ratios) if ratios else 0
                all_results[kw] = avg

            time.sleep(0.3)  # API rate limit 준수

        except Exception as e:
            logger.error(f"API 호출 오류 (batch {i}~{i+BATCH}): {e}")
            time.sleep(1)

    # ratio 기준 정렬
    sorted_kw = sorted(all_results.items(), key=lambda x: x[1], reverse=True)
    logger.info(f"[{cat_id}] 트렌드 분석 완료: {len(sorted_kw)}개 키워드")

    return [{"keyword": kw, "ratio": round(ratio, 2)} for kw, ratio in sorted_kw[:top_n]]


# ════════════════════════════════════════════════════════════════════════════
# 2. DB 저장: naver_trending_keywords 테이블
# ════════════════════════════════════════════════════════════════════════════

def save_to_db(blog_id: str, keywords: list[dict]):
    """트렌드 키워드를 DB에 저장 (upsert)"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS naver_trending_keywords (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id     TEXT NOT NULL,
            keyword     TEXT NOT NULL,
            ratio       REAL DEFAULT 0,
            collected_at TEXT DEFAULT (datetime('now')),
            UNIQUE(blog_id, keyword)
        )
    """)
    for item in keywords:
        conn.execute("""
            INSERT INTO naver_trending_keywords (blog_id, keyword, ratio, collected_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(blog_id, keyword) DO UPDATE SET
                ratio=excluded.ratio,
                collected_at=excluded.collected_at
        """, (blog_id, item["keyword"], item["ratio"]))
    conn.commit()
    conn.close()
    logger.info(f"[{blog_id}] DB 저장 완료: {len(keywords)}개")


# ════════════════════════════════════════════════════════════════════════════
# 3. keywords.py 자동 업데이트
# ════════════════════════════════════════════════════════════════════════════

def update_keywords_py(blog_id: str, new_keywords: list[str], top_n: int = 50):
    """
    keywords.py의 KEYWORD_MAP[blog_id] 목록을 
    네이버 트렌드 TOP 키워드로 갱신 (기존 키워드는 유지 + 신규 추가)
    """
    content = Path(KEYWORDS_PATH).read_text(encoding="utf-8")

    target = f'"{blog_id}": ['
    idx = content.find(target)
    if idx == -1:
        logger.warning(f"keywords.py에서 {blog_id} 섹션 미발견")
        return 0

    start = idx + len(target)
    end   = content.find("]", start)
    existing_block = content[start:end]
    existing = {
        k.strip().strip('"\'')
        for k in existing_block.split(",")
        if k.strip().strip('"\'')
    }

    added = [kw for kw in new_keywords if kw not in existing][:top_n]
    if not added:
        logger.info(f"[{blog_id}] 추가할 신규 키워드 없음")
        return 0

    new_entries = ",\n        ".join([f'"{k}"' for k in added])
    new_content = (
        content[:end]
        + f",\n        {new_entries}"
        + content[end:]
    )
    Path(KEYWORDS_PATH).write_text(new_content, encoding="utf-8")
    logger.info(f"[{blog_id}] keywords.py 업데이트: {len(added)}개 추가")
    return len(added)


# ════════════════════════════════════════════════════════════════════════════
# 4. 쿠팡 벌크 수집 (키워드 → products DB)
# ════════════════════════════════════════════════════════════════════════════

def bulk_collect_coupang(blog_id: str, keywords: list[str]):
    """신규 키워드에 대해 쿠팡 상품 수집"""
    sys.path.insert(0, str(BASE_DIR))
    from pipelines.curation.collector import collect_keyword, get_products

    ok = low = fail = 0
    for i, kw in enumerate(keywords, 1):
        try:
            collect_keyword(kw)
            cnt = len(get_products(kw, limit=10))
            if cnt >= 3:
                logger.info(f"  [{i:03d}] ✅ {kw}: {cnt}개")
                ok += 1
            elif cnt > 0:
                logger.warning(f"  [{i:03d}] ⚠️  {kw}: {cnt}개 (부족)")
                low += 1
            else:
                logger.warning(f"  [{i:03d}] ❌ {kw}: 0개")
                fail += 1
        except Exception as e:
            logger.error(f"  [{i:03d}] 💥 {kw}: {e}")
            fail += 1
        time.sleep(0.4)

    logger.info(f"\n[{blog_id}] 수집 결과 — 성공:{ok} / 부족:{low} / 실패:{fail}")
    return ok, low, fail


# ════════════════════════════════════════════════════════════════════════════
# 5. 메인 실행
# ════════════════════════════════════════════════════════════════════════════

def run(blog_id: str = "baby-hugo"):
    if blog_id not in CATEGORY_MAP:
        logger.error(f"지원하지 않는 blog_id: {blog_id}")
        logger.error(f"지원 목록: {list(CATEGORY_MAP.keys())}")
        sys.exit(1)

    cat    = CATEGORY_MAP[blog_id]
    cat_id = cat["cat_id"]
    logger.info(f"=== 네이버 데이터랩 동기화 시작: {blog_id} ({cat['name']}) ===")

    # Step 1: 트렌드 키워드 수집
    logger.info("Step 1. 네이버 쇼핑인사이트 트렌드 조회...")
    trending = fetch_top_keywords(cat_id, top_n=100)
    if not trending:
        logger.error("트렌드 키워드 수집 실패 — API 키 확인 필요")
        sys.exit(1)

    top_kws = [item["keyword"] for item in trending]
    logger.info(f"  → 상위 10개: {top_kws[:10]}")

    # Step 2: DB 저장
    logger.info("Step 2. 트렌드 키워드 DB 저장...")
    save_to_db(blog_id, trending)

    # Step 3: keywords.py 업데이트
    logger.info("Step 3. keywords.py 업데이트...")
    added_count = update_keywords_py(blog_id, top_kws, top_n=30)

    # Step 4: 쿠팡 상품 벌크 수집 (신규 추가된 키워드만)
    if added_count > 0:
        logger.info(f"Step 4. 쿠팡 상품 수집 ({added_count}개 신규 키워드)...")
        new_kws = top_kws[:added_count]
        bulk_collect_coupang(blog_id, new_kws)
    else:
        logger.info("Step 4. 신규 키워드 없음 — 수집 스킵")

    logger.info(f"=== 완료: {blog_id} ===\n")


def run_all():
    """모든 블로그 순차 동기화"""
    for blog_id in CATEGORY_MAP:
        run(blog_id)
        time.sleep(2)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "baby-hugo"
    if target == "all":
        run_all()
    else:
        run(target)
