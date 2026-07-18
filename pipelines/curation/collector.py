"""쿠팡 Search API → curation.db 캐싱

- 키워드별 상품 10개 수집
- 캐시 유효기간 3일, 만료 시 재수집

⚠️ 쿠팡 파트너스 API RATE LIMIT (2026-07-16 제재 확인)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 검색 API:      분당 50회 (search)
- 리포트 API:    시간당 500회 (report)
- 전체 API:      분당 100회 (total)
- 링크생성:      분당 50회 (deeplink POST)
- 경고 3회 누적 → 이용제한 (해제 후 재발생 시 추가 제재)

이 파일 수정 시 반드시 위 제한을 준수할 것.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import hashlib
import hmac
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv

load_dotenv("/Users/twinssn/Projects/5000/.env")

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "curation.db")
BASE_URL = "https://api-gateway.coupang.com"
CACHE_DAYS = 3

def _init_db() -> None:
    """DB 테이블이 없으면 자동 생성 (DB 초기화 복구용)"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            keyword TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT,
            product_price INTEGER,
            product_image TEXT,
            product_url TEXT,
            category_name TEXT,
            rank INTEGER,
            is_rocket BOOLEAN,
            is_free_shipping BOOLEAN,
            collected_at TEXT,
            PRIMARY KEY (keyword, product_id)
        )
    """)
    conn.commit()
    conn.close()

_init_db()



# -- 키워드 변형으로 상품 풀 확대 --
KEYWORD_VARIANTS = {
    "노트북": ["노트북", "랩탑", "laptop"],
    "추천": [],
    "가성비": ["가성비", "저렴한"],
    "무선청소기": ["무선청소기", "무선 청소기", "스틱청소기"],
    "에어프라이어": ["에어프라이어", "에어 프라이어"],
    "러닝머신": ["러닝머신", "런닝머신", "트레드밀"],
    "워킹머신": ["워킹머신", "워킹패드"],
    "카시트": ["카시트", "카 시트", "carseat"],
    "유모차": ["유모차", "스트롤러"],
    "덤벨": ["덤벨", "아령", "덤벨세트"],
    "실내자전거": ["실내자전거", "스핀바이크", "실내 자전거"],
    "스핀바이크": ["스핀바이크", "실내자전거"],
    "의자": ["의자", "체어"],
    "매트리스": ["매트리스", "메트리스"],
    "책상": ["책상", "데스크"],
}


def _generate_keyword_variants(keyword):
    """원본 키워드 + 변형 키워드 생성 (최대 3개)"""
    variants = [keyword]
    kw_lower = keyword.lower()

    for base_word, alts in KEYWORD_VARIANTS.items():
        if base_word in kw_lower:
            for alt in alts:
                if alt != base_word and alt not in kw_lower:
                    variant = keyword.replace(base_word, alt)
                    if variant != keyword and variant not in variants:
                        variants.append(variant)
                    if len(variants) >= 3:
                        return variants

    # 접미사 변형: "XX 추천" → "XX" (추천 제거하고 검색)
    if keyword.endswith(" 추천"):
        bare = keyword.replace(" 추천", "")
        if bare not in variants:
            variants.append(bare)

    return variants[:3]




def _get_api_keys():
    access_key = os.getenv("COUPANG_ACCESS_KEY", "")
    secret_key = os.getenv("COUPANG_SECRET_KEY", "")
    return access_key, secret_key


def _generate_signature(method, url_path, query_string=""):
    access_key, secret_key = _get_api_keys()
    if not access_key or not secret_key:
        return None
    datetime_str = datetime.utcnow().strftime("%y%m%dT%H%M%SZ")
    message = datetime_str + method + url_path + query_string
    signature = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    authorization = f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={datetime_str}, signature={signature}"
    return {"Authorization": authorization, "Content-Type": "application/json"}


def _check_rate_limit():
    """분당/시간당 이중 레이트 리미트 — 쿠팡 API 제한(분50/시500) 준수

    ⚠️ 2026-07-16 쿠팡 파트너스 제재 이슈로 강화:
      - 검색 API: 분당 50회 (여유분 20% → 분당 40회에서 컷)
      - 전체 API: 분당 100회
      - 시간당: 300회 제한 (안전마진)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS api_call_log (id INTEGER PRIMARY KEY AUTOINCREMENT, called_at TEXT DEFAULT (datetime('now')))")
        conn.execute("CREATE TABLE IF NOT EXISTS api_block_log (id INTEGER PRIMARY KEY, blocked_until TEXT)")
        blocked = conn.execute("SELECT blocked_until FROM api_block_log WHERE id=1").fetchone()
        if blocked:
            from datetime import datetime as _dt
            try:
                block_time = _dt.fromisoformat(blocked[0].replace("Z",""))
                if _dt.now() < block_time:
                    logger.warning(f"쿠팡 API 서버 차단 중 — {blocked[0]} 까지 대기")
                    conn.close()
                    return False
            except Exception:
                pass
        # 분당 체크 (검색 API 분당 50회 → 안전마진 40회)
        per_minute = conn.execute(
            "SELECT COUNT(*) FROM api_call_log WHERE called_at > datetime('now', '-1 minute')"
        ).fetchone()[0]
        if per_minute >= 40:
            logger.warning(f"[API_RATE] 분당 한도 도달: {per_minute}/40 — 일시 중단")
            conn.close()
            return False
        # 시간당 체크 (안전마진 300회)
        per_hour = conn.execute(
            "SELECT COUNT(*) FROM api_call_log WHERE called_at > datetime('now', '-1 hour')"
        ).fetchone()[0]
        if per_hour >= 300:
            logger.warning(f"[API_RATE] 시간당 한도 도달: {per_hour}/300 — 일시 중단")
            conn.close()
            return False
        logger.info(f"[API_RATE] 분:{per_minute}/40  시:{per_hour}/300  ✅")
        conn.close()
        return True
    except Exception:
        return True

def _log_api_call() -> None:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS api_call_log (id INTEGER PRIMARY KEY AUTOINCREMENT, called_at TEXT DEFAULT (datetime('now')))")
        conn.execute("INSERT INTO api_call_log (called_at) VALUES (datetime('now'))")
        conn.execute("DELETE FROM api_call_log WHERE called_at < datetime('now', '-2 hours')")
        conn.commit()
        conn.close()
    except Exception:
        pass

def _search_api(keyword, limit=10):
    if not _check_rate_limit():
        logger.warning(f"쿠팡 API 시간당 한도 초과 — 스킵: {keyword}")
        return []
    url_path = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
    params = {"keyword": keyword, "limit": limit}
    query_string = urlencode(params)
    headers = _generate_signature("GET", url_path, query_string)
    if not headers:
        logger.error("쿠팡 API 키 미설정")
        return []
    try:
        resp = requests.get(f"{BASE_URL}{url_path}?{query_string}", headers=headers, timeout=10)
        _log_api_call()
        logger.info(f"[API_CALL] keyword={keyword} status={resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("rCode") == "403":
                msg = data.get("rMessage", "")
                logger.warning(f"[API_BLOCKED] 쿠팡 API 한도 초과 — 최근1시간 호출수 확인 필요: {msg[:120]}")
                _log_api_call()  # 서버 카운트 소진됐으므로 로컬도 기록
                import re as _re
                m = _re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", msg)
                if m:
                    try:
                        _bc = sqlite3.connect(DB_PATH)
                        _bc.execute("CREATE TABLE IF NOT EXISTS api_block_log (id INTEGER PRIMARY KEY, blocked_until TEXT)")
                        _bc.execute("INSERT OR REPLACE INTO api_block_log (id, blocked_until) VALUES (1, ?)", (m.group(1),))
                        _bc.commit()
                        _bc.close()
                        logger.warning(f"쿠팡 API 차단 시간 저장: {m.group(1)}")
                    except Exception:
                        pass
                return []
            return data.get("data", {}).get("productData", [])
        logger.error(f"Search API {resp.status_code}: {keyword}")
        return []
    except Exception as e:
        logger.exception(f"Search API 오류 [{keyword}]: {e}")
        return []


def is_cache_valid(keyword):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT MAX(collected_at) FROM products WHERE keyword=?", (keyword,)
    ).fetchone()
    # 상품 수 체크 — 3개 미만이면 캐시 무효
    cnt = conn.execute(
        "SELECT COUNT(*) FROM products WHERE keyword=?", (keyword,)
    ).fetchone()[0]
    conn.close()
    if not row or not row[0]:
        return False
    if cnt < 3:
        return False
    last = datetime.fromisoformat(row[0])
    return datetime.now() - last < timedelta(days=CACHE_DAYS)


def collect_keyword(keyword) -> bool:
    if is_cache_valid(keyword):
        logger.info(f"캐시 유효: {keyword}")
        return True

    logger.info(f"Search API 호출: {keyword}")
    products = _search_api(keyword, limit=20)
    if not products:
        products = _search_api(keyword, limit=10)

    # 변형 키워드로 추가 수집 (상품 풀 확대)
    variants = _generate_keyword_variants(keyword)
    seen_ids = {p["productId"] for p in products} if products else set()
    for vk in variants[1:]:  # 첫 번째는 원본이므로 스킵
        extra = _search_api(vk, limit=5)
        if extra:
            for ep in extra:
                if ep["productId"] not in seen_ids:
                    products.append(ep)
                    seen_ids.add(ep["productId"])
            logger.info(f"변형 키워드 '{vk}' → {len(extra)}개 추가 후보")

    if not products:
        return False

    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat()
    for p in products:
        conn.execute(
            """INSERT OR REPLACE INTO products
               (keyword, product_id, product_name, product_price, product_image,
                product_url, category_name, rank, is_rocket, is_free_shipping, collected_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (keyword, p["productId"], p["productName"], p.get("productPrice", 0),
             p.get("productImage", ""), p.get("productUrl", ""),
             p.get("categoryName", ""), p.get("rank", 0),
             1 if p.get("isRocket") else 0,
             1 if p.get("isFreeShipping") else 0, now)
        )
    conn.commit()
    conn.close()
    logger.info(f"수집 완료: {keyword} → {len(products)}개")
    return True


def get_products(keyword, limit=5):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM products WHERE keyword=?
           ORDER BY collected_at DESC, rank ASC LIMIT ?""",
        (keyword, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
