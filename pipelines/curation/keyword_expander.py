#!/usr/bin/env python3
"""키워드 대량 확장기
1. 네이버 자동완성 API → 연관 키워드 수집
2. 쿠팡 상품명 역추출 → 기존 products DB 활용
3. 네이버 쇼핑 검색 API → 카테고리 상품명에서 키워드 추출
4. 키워드 상호 변환 → 블로그 간 연관 키워드 공유

실행: python3 pipelines/curation/keyword_expander.py baby-hugo
"""

import os
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
load_dotenv(os.path.expanduser("~/.env.common"))

DB_PATH       = BASE_DIR / "data" / "curation.db"
KEYWORDS_PATH = BASE_DIR / "pipelines" / "curation" / "keywords.py"

NAVER_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# 동적 시드 생성: 기존 products DB에서 카테고리별 대표 키워드 추출
def _get_dynamic_seeds(blog_id: str, limit: int = 20) -> list[str]:
    """기존 products DB에서 빈도 높은 키워드를 동적 시드로 사용"""
    try:
        conn = sqlite3.connect(DB_PATH)
        # 블로그 카테고리별 키워드 매핑
        category_map = {
            "baby-hugo": ["아기", "신생아", "유아", "육아", "기저귀", "유모차", "카시트", "이유식"],
            "fitness-hugo": ["운동", "헬스", "요가", "덤벨", "러닝", "홈트", "필라테스"],
            "laptop-hugo": ["노트북", "맥북", "게이밍", "삼성", "LG", "레노버"],
            "appliance-hugo": ["청소기", "에어프라이어", "공기청정기", "세탁기", "냉장고", "밥솥"],
            "interior-hugo": ["소파", "침대", "책상", "의자", "조명", "커튼", "매트리스"],
            "pet-hugo": ["강아지", "고양이", "사료", "간식", "장난감", "캣타워"],
            "health-hugo": ["비타민", "영양제", "오메가3", "유산균", "루테인", "홍삼"],
            "kitchen-hugo": ["냄비", "프라이팬", "도마", "칼", "식기", "밥솥"],
            "beauty-hugo": ["화장품", "스킨케어", "세럼", "토너", "크림", "샴푸"],
            "camping-hugo": ["텐트", "캠핑", "침낭", "의자", "테이블", "랜턴"],
        }
        keywords = category_map.get(blog_id, [])

        # 관련 키워드로 검색된 상품의 키워드를 빈도순으로 가져오기
        ",".join(["?" for _ in keywords])
        rows = conn.execute("""
            SELECT keyword, COUNT(*) as cnt
            FROM products
            WHERE keyword LIKE ? OR keyword LIKE ? OR keyword LIKE ?
            GROUP BY keyword
            ORDER BY cnt DESC
            LIMIT ?
        """, (f"%{keywords[0]}%", f"%{keywords[1] if len(keywords) > 1 else keywords[0]}%",
              f"%{keywords[2] if len(keywords) > 2 else keywords[0]}%", limit)).fetchall()
        conn.close()
        return [row[0] for row in rows if row[0]]
    except Exception:
        return []

# 블로그별 기본 시드 (동적 시드가 부족할 때 사용)
DEFAULT_SEEDS = {
    "baby-hugo": ["아기", "신생아", "유아", "육아", "출산"],
    "fitness-hugo": ["운동", "헬스", "요가", "홈트", "다이어트"],
    "car-hugo": ["블랙박스", "차량용", "자동차 용품", "카시트", "차량 관리"],
    "laptop-hugo": ["노트북", "맥북", "게이밍", "사무용", "학생"],
    "appliance-hugo": ["에어프라이어", "청소기", "공기청정기", "세탁기", "냉장고"],
    "interior-hugo": ["소파", "침대", "책상", "의자", "조명"],
    "pet-hugo": ["강아지", "고양이", "반려동물", "사료", "간식"],
    "health-hugo": ["비타민", "영양제", "건강", "오메가3", "유산균"],
    "kitchen-hugo": ["냄비", "프라이팬", "도마", "칼", "식기"],
    "beauty-hugo": ["화장품", "스킨케어", "메이크업", "샴푸", "선크림"],
    "camping-hugo": ["텐트", "캠핑", "등산", "배낭", "침낭"],
    "golf-hugo": ["골프", "골프용품", "골프연습", "퍼팅", "드라이버"],
}

def get_root_seeds(blog_id: str) -> list[str]:
    """동적 시드 + 기본 시드 결합"""
    dynamic = _get_dynamic_seeds(blog_id)
    default = DEFAULT_SEEDS.get(blog_id, [])
    # 동적 시드 우선, 부족하면 기본 시드로 보충
    seeds = list(dict.fromkeys(dynamic + default))  # 중복 제거 유지
    return seeds[:30]  # 최대 30개


# ════════════════════════════════════════════════════════
# 1. 네이버 자동완성 API (무료, 무제한)
# ════════════════════════════════════════════════════════

def get_autocomplete(keyword: str) -> list[str]:
    """네이버 쇼핑 자동완성에서 연관 키워드 수집"""
    try:
        resp = requests.get(
            "https://ac.shopping.naver.com/ac",
            params={"q": keyword, "st": 1, "r_format": "json", "r_enc": "UTF-8"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            # 응답 구조: {"items": [["키워드1"], ["키워드2"], ...]}
            items = data.get("items", [])
            if items and isinstance(items[0], list):
                return [item[0] for item in items[0] if item]
            return [item[0] for item in items if isinstance(item, list) and item]
    except Exception:
        pass
    return []


def expand_via_autocomplete(seeds: list[str], depth: int = 2) -> set[str]:
    """자동완성 재귀 확장
    depth=1: 시드 → 자동완성 (약 10배 확장)
    depth=2: 시드 → 자동완성 → 자동완성 결과도 한 번 더 (약 100배)
    """
    collected = set(seeds)
    current_layer = set(seeds)

    for d in range(depth):
        next_layer = set()
        print(f"  [자동완성 depth={d+1}] {len(current_layer)}개 키워드 확장 중...")
        for i, kw in enumerate(sorted(current_layer)):
            results = get_autocomplete(kw)
            next_layer.update(results)
            if i % 20 == 0 and i > 0:
                print(f"    진행: {i}/{len(current_layer)} ({len(next_layer)}개 수집)")
            time.sleep(0.1)
        new_kws = next_layer - collected
        collected.update(next_layer)
        current_layer = new_kws
        print(f"  → depth={d+1} 완료: 누적 {len(collected)}개")
        if not new_kws:
            break

    return collected


# ════════════════════════════════════════════════════════
# 2. 쿠팡 상품명 역추출 (기존 DB 활용)
# ════════════════════════════════════════════════════════

def extract_from_products_db(blog_id: str, top_n: int = 200) -> list[str]:
    """Products 테이블의 product_name에서 명사 추출
    → 2~5글자 한국어 단어 중 빈도 높은 것 추출
    """
    conn   = sqlite3.connect(DB_PATH)
    # 현재 blog_id와 관련된 키워드로 수집된 상품명 가져오기
    rows   = conn.execute(
        "SELECT DISTINCT product_name FROM products WHERE keyword IN "
        "(SELECT DISTINCT keyword FROM products) LIMIT 2000"
    ).fetchall()
    conn.close()

    # 한국어 2~6글자 단어 추출
    word_counter = Counter()
    for (name,) in rows:
        if not name:
            continue
        tokens = re.findall(r"[가-힣]{2,6}", name)
        word_counter.update(tokens)

    # 불용어 제거
    STOPWORDS = {
        "추천", "브랜드", "정품", "특가", "무료", "배송", "할인",
        "신상", "최신", "인기", "베스트", "고급", "프리미엄",
        "국내", "해외", "직구", "공식", "세트",
    }
    result = [
        w for w, cnt in word_counter.most_common(top_n * 2)
        if w not in STOPWORDS and cnt >= 2
    ]
    return result[:top_n]


# ════════════════════════════════════════════════════════
# 3. 네이버 쇼핑 검색 API (상품명 기반 키워드)
# ════════════════════════════════════════════════════════

def get_naver_shopping_keywords(query: str, display: int = 100) -> list[str]:
    """네이버 쇼핑 검색 API로 상품명 수집 → 키워드 추출"""
    if not NAVER_CLIENT_ID:
        return []
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/shop.json",
            params={"query": query, "display": display, "sort": "sim"},
            headers={
                "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            timeout=8,
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            words = []
            for item in items:
                title = re.sub(r"<[^>]+>", "", item.get("title", ""))
                tokens = re.findall(r"[가-힣]{2,6}", title)
                words.extend(tokens)
            counter = Counter(words)
            STOPWORDS = {"추천", "정품", "배송", "할인", "특가", "무료", "세트"}
            return [w for w, c in counter.most_common(50) if w not in STOPWORDS and c >= 2]
    except Exception:
        pass
    return []


# ════════════════════════════════════════════════════════
# 4. DB 저장 및 keywords.py 업데이트
# ════════════════════════════════════════════════════════

def save_expanded_keywords(blog_id: str, keywords: set[str]) -> None:
    """확장된 키워드를 naver_trending_keywords에 저장"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS naver_trending_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            ratio REAL DEFAULT 0,
            collected_at TEXT DEFAULT (datetime('now')),
            UNIQUE(blog_id, keyword)
        )
    """)
    inserted = 0
    for kw in keywords:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO naver_trending_keywords (blog_id, keyword, ratio) VALUES (?,?,0)",
                (blog_id, kw)
            )
            inserted += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    print(f"[DB] {blog_id}: {inserted}개 신규 저장 (전체 {len(keywords)}개)")


def update_keywords_py(blog_id: str, new_keywords: list[str], max_add: int = 100) -> int:
    """keywords.py KEYWORD_MAP 업데이트 - 기존 키워드를 유지하면서 새 키워드 추가"""
    content = Path(KEYWORDS_PATH).read_text(encoding="utf-8")
    target  = f'"{blog_id}": ['
    idx     = content.find(target)
    if idx == -1:
        print(f"[WARN] keywords.py에서 {blog_id} 미발견")
        return 0

    # 해당 블로그 키워드 블록 찾기
    start = idx + len(target)
    depth, pos = 1, start
    while pos < len(content) and depth > 0:
        if content[pos] == "[":
            depth += 1
        elif content[pos] == "]":
            depth -= 1
        pos += 1
    end = pos - 1  # 닫는 ] 위치

    # 기존 키워드 추출
    existing = set(re.findall(r'["\'](.[^"\']*)["\']', content[start:end]))

    # 새 키워드 필터링
    added = [kw for kw in new_keywords if kw not in existing][:max_add]

    # CATEGORY_FILTERS 기반 검증
    try:
        from pipelines.curation.keywords import validate_keyword
        valid_added = []
        for kw in added:
            ok, reason = validate_keyword(kw, blog_id)
            if ok:
                valid_added.append(kw)
            else:
                print(f"[keywords.py] {blog_id}: 제외됨 '{kw}' — {reason}")
        added = valid_added
    except ImportError:
        pass

    if not added:
        print(f"[keywords.py] {blog_id}: 추가할 신규 키워드 없음")
        return 0

    # 기존 블록 내용에서 마지막 항목 뒤에 새 항목 추가
    block_content = content[start:end]
    # 마지막 항목 찾기 (쉼표 뒤에 있는 항목)
    last_item_match = re.search(r'"([^"]+)"\s*$', block_content.strip())
    if last_item_match:
        # 마지막 항목 뒤에 새 항목 추가
        insert_pos = start + block_content.strip().rfind('"') + 1
        new_entries = ",\n        ".join([f'"{k}"' for k in added])
        new_content = content[:insert_pos] + f",\n        {new_entries}" + content[insert_pos:]
    else:
        # 블록이 비어있으면 첫 번째 항목으로 추가
        new_entries = ",\n        ".join([f'"{k}"' for k in added])
        new_content = content[:start] + f"\n        {new_entries}" + content[start:]

    Path(KEYWORDS_PATH).write_text(new_content, encoding="utf-8")
    print(f"[keywords.py] {blog_id}: {len(added)}개 추가")
    return len(added)


# ════════════════════════════════════════════════════════
# 5. 메인
# ════════════════════════════════════════════════════════

def run(blog_id: str) -> None:
    seeds = get_root_seeds(blog_id)
    if not seeds:
        print(f"[ERROR] 시드 키워드 없음: {blog_id}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f" 키워드 확장: {blog_id} (동적 시드 {len(seeds)}개)")
    print(f"{'='*60}")

    all_keywords = set()

    # Step 1: 자동완성 확장 (depth=2 → 수백~수천 개)
    print("\n[Step 1] 네이버 자동완성 확장 (depth=2)...")
    autocomplete_kws = expand_via_autocomplete(seeds, depth=2)
    all_keywords.update(autocomplete_kws)
    print(f"  → 자동완성 결과: {len(autocomplete_kws)}개")

    # Step 2: 쇼핑 API로 상품명 기반 키워드 추출
    print("\n[Step 2] 네이버 쇼핑 API 키워드 추출...")
    for seed in seeds[:5]:  # API 한도 절약, 대표 시드만
        shopping_kws = get_naver_shopping_keywords(seed, display=100)
        all_keywords.update(shopping_kws)
        time.sleep(0.3)
    print(f"  → 쇼핑 API 결과 누적: {len(all_keywords)}개")

    # Step 3: 기존 DB 상품명 역추출
    print("\n[Step 3] 쿠팡 products DB 역추출...")
    db_kws = extract_from_products_db(blog_id, top_n=200)
    all_keywords.update(db_kws)
    print(f"  → DB 역추출 결과 누적: {len(all_keywords)}개")

    # 필터링: 1글자 이하, 특수문자 포함 제거
    filtered = {
        kw for kw in all_keywords
        if len(kw) >= 2 and re.match(r"^[가-힣a-zA-Z0-9\s]+$", kw)
    }
    print(f"\n[필터링 후] {len(filtered)}개 (원본 {len(all_keywords)}개)")

    # Step 4: DB 저장
    print("\n[Step 4] DB 저장...")
    save_expanded_keywords(blog_id, filtered)

    # Step 5: keywords.py 업데이트 (상위 100개)
    print("\n[Step 5] keywords.py 업데이트...")
    # ratio 있는 것 우선, 없으면 알파벳순
    conn    = sqlite3.connect(DB_PATH)
    top_kws = [
        row[0] for row in conn.execute(
            "SELECT keyword FROM naver_trending_keywords "
            "WHERE blog_id=? ORDER BY ratio DESC, keyword ASC LIMIT 100",
            (blog_id,)
        ).fetchall()
    ]
    conn.close()
    added = update_keywords_py(blog_id, top_kws, max_add=100)

    print(f"\n✅ {blog_id} 완료 — 총 {len(filtered)}개 수집, {added}개 keywords.py 추가")


def run_all() -> None:
    for blog_id in DEFAULT_SEEDS:
        run(blog_id)
        time.sleep(3)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "baby-hugo"
    if target == "all":
        run_all()
    else:
        run(target)
