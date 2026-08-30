"""best_collector.py — Coupang Bestcategories → curation.db:best_products 캐싱 (Phase 75)

Additive parallel to collector.py [RESEARCH Architecture Patterns L428-431, Pattern 1 L451-480]
- 기존 collector.py 수정 없음 — 별도 파일/테이블로 rank 의미 충돌 방지 [RESEARCH Standard Stack L55]
- BEST_CACHE_DAYS=1 (best는 일 단위 변동) vs collector CACHE_DAYS=3 [RESEARCH Pattern 1 L460]
- rate guard는 collector._check_rate_limit / _log_api_call 재사용 (api_call_log 공유) [RESEARCH L204-242, Pitfall 5]
- variant 확장 금지 — categoryId는 숫자 트리, 키워드 변형 적용 불필요 [RESEARCH Pitfall anti-pattern L513]
- envelope 양쪽 대응: flat list data=[...] 또는 dict data.productData [RESEARCH A4, Pitfall 1]
- PK는 (category_id, product_id) [RESEARCH Curation DB schema L148-158]

Wave0 probe lock (2026-08-30):
- Correct path: /v2/providers/affiliate_open_api/apis/openapi/v1/products/bestcategories/{categoryId} (path-param)
- Envelope live: flat list data (not productData) — both branches handled
- Verified IDs: 1020 주방용품, 1010 뷰티, 1011 출산/유아
"""

import hashlib
import hmac
import logging
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv

load_dotenv("/Users/twinssn/Projects/5000/.env")
try:
    load_dotenv(os.path.expanduser("~/.env.common"))
except Exception:
    pass

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "curation.db")
BASE_URL = "https://api-gateway.coupang.com"
BEST_CACHE_DAYS = 1  # [RESEARCH Open Q 2 L684, Pattern 1 L460]

# Reuse rate guard from collector (DB api_call_log 공유) [RESEARCH L204-242, Pitfall 5 L562-564]
from pipelines.curation.collector import _check_rate_limit, _log_api_call

# For _get_api_keys / HMAC reuse — mirror collector pattern but keep local for path-param case
from pipelines.curation.collector import _get_api_keys as _collector_get_keys  # noqa: F401


def _init_best_db() -> None:
    """Create best_products table if not exists (same DB file, separate table) [RESEARCH Standard Stack L55]."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS best_products (
            category_id TEXT NOT NULL,
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
            PRIMARY KEY (category_id, product_id)
        )
    """)
    # api_call_log / api_block_log created by collector._check_rate_limit/_log_api_call on demand,
    # but ensure tables exist for standalone calls
    conn.execute("CREATE TABLE IF NOT EXISTS api_call_log (id INTEGER PRIMARY KEY AUTOINCREMENT, called_at TEXT DEFAULT (datetime('now')))")
    conn.execute("CREATE TABLE IF NOT EXISTS api_block_log (id INTEGER PRIMARY KEY, blocked_until TEXT)")
    conn.commit()
    conn.close()


_init_best_db()


def _generate_signature(method: str, url_path: str, query_string: str = "") -> dict | None:
    """CEA HmacSHA256 headers — same scheme as collector.py [RESEARCH coupang_client L20-34]."""
    ak = os.getenv("COUPANG_ACCESS_KEY", "")
    sk = os.getenv("COUPANG_SECRET_KEY", "")
    if not ak or not sk:
        return None
    datetime_str = datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")
    message = datetime_str + method + url_path + query_string
    signature = hmac.new(sk.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = f"CEA algorithm=HmacSHA256, access-key={ak}, signed-date={datetime_str}, signature={signature}"
    return {"Authorization": authorization, "Content-Type": "application/json"}


def _extract_products(body: dict) -> list[dict]:
    """Envelope branching: handle both flat list and productData dict [RESEARCH A4, L469].

    - bestcategories live: {"rCode":"0","data":[{product...}, ...]} flat list
    - search / fallback: {"rCode":"0","data":{"productData":[...]}} dict wrap
    Returns [] on unknown shape.
    """
    if not isinstance(body, dict):
        return []
    data = body.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        pd = data.get("productData")
        if isinstance(pd, list):
            return pd
        # also handle bare dict data fallback
        return []
    return []


def _best_search_api(category_id: str) -> list[dict]:
    """Call bestcategories API for category_id → product list [RESEARCH coupang_client L64-68, collector L203-242].

    Rate guard: _check_rate_limit() before call, _log_api_call() after success AND on 403 [RESEARCH collector L220-223].
    Path: /v1/products/bestcategories/{categoryId} (path-param) — live verified 2026-08-30.
    Returns [] on rate limit, missing keys, 403, or empty data.
    """
    if not _check_rate_limit():
        logger.warning(f"쿠팡 API 레이트리밋 — 스킵: categoryId={category_id}")
        return []
    # Path-param form is live-correct; do not use query ?categoryId= (404)
    url_path = f"/v2/providers/affiliate_open_api/apis/openapi/v1/products/bestcategories/{category_id}"
    headers = _generate_signature("GET", url_path, "")
    if not headers:
        logger.error("쿠팡 API 키 미설정")
        return []
    try:
        resp = requests.get(f"{BASE_URL}{url_path}", headers=headers, timeout=10)
        _log_api_call()
        logger.info(f"[BEST_API] categoryId={category_id} status={resp.status_code}")
        if resp.status_code == 200:
            try:
                body = resp.json()
            except ValueError:
                body = {}
            # rCode 403 (body-level) means quota blocked — log extra and record api_block_log
            if body.get("rCode") == "403":
                msg = body.get("rMessage", "")
                logger.warning(f"[API_BLOCKED] bestcategories 한도 초과: {msg[:120]}")
                _log_api_call()  # double log per collector L221
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
            # rCode 400 means invalid categoryId — harmless skip [RESEARCH run_harvest L99]
            if body.get("rCode") == "400":
                logger.info(f"[BEST_API] categoryId not found/active: {category_id} msg={body.get('rMessage','')[:80]}")
                return []
            products = _extract_products(body)
            return products if isinstance(products, list) else []
        logger.error(f"Bestcategories API {resp.status_code}: categoryId={category_id}")
        return []
    except Exception as e:
        logger.exception(f"Bestcategories API 오류 [{category_id}]: {e}")
        return []


def is_best_cache_valid(category_id: str) -> bool:
    """1d cache, min 3 rows [RESEARCH collector L245-261, Pattern 1 L473-474]."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT MAX(collected_at) FROM best_products WHERE category_id=?", (category_id,)
        ).fetchone()
        cnt = conn.execute(
            "SELECT COUNT(*) FROM best_products WHERE category_id=?", (category_id,)
        ).fetchone()[0]
    finally:
        conn.close()
    if not row or not row[0]:
        return False
    if cnt < 3:
        return False
    try:
        last = datetime.fromisoformat(row[0])
    except Exception:
        return False
    return datetime.now() - last < timedelta(days=BEST_CACHE_DAYS)


def collect_best(category_id: str) -> bool:
    """Fetch bestcategory and upsert to best_products. NO variant expansion [RESEARCH Pitfall L513, Pattern 1 L476].

    Returns True on cache hit or successful fetch, False on empty fetch.
    """
    if is_best_cache_valid(category_id):
        logger.info(f"베스트 캐시 유효: {category_id}")
        return True

    logger.info(f"Bestcategories API 호출: {category_id}")
    products = _best_search_api(category_id)

    if not products:
        logger.info(f"베스트 수집 결과 없음: {category_id}")
        return False

    # NO variant expansion — categoryId has no natural-language variants [RESEARCH anti-pattern L513]
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat()
    for p in products:
        try:
            pid = str(p.get("productId", ""))
            if not pid:
                continue
            conn.execute(
                """INSERT OR REPLACE INTO best_products
                   (category_id, product_id, product_name, product_price, product_image,
                    product_url, category_name, rank, is_rocket, is_free_shipping, collected_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (category_id, pid, p.get("productName", ""), p.get("productPrice", 0),
                 p.get("productImage", ""), p.get("productUrl", ""),
                 p.get("categoryName", ""), p.get("rank", 0),
                 1 if p.get("isRocket") else 0,
                 1 if p.get("isFreeShipping") else 0, now)
            )
        except Exception as e:
            logger.warning(f"best_products insert skip pid={p.get('productId')}: {e}")
            continue
    conn.commit()
    conn.close()
    logger.info(f"베스트 수집 완료: {category_id} → {len(products)}개")
    return True


def get_best_products(category_id: str, limit: int = 5) -> list[dict]:
    """Return best products ORDER BY collected_at DESC, rank ASC [RESEARCH collector L311-320].

    Separate table already isolates rank semantics (sales rank vs search exposure) [RESEARCH Pitfall L510].
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT * FROM best_products WHERE category_id=?
               ORDER BY collected_at DESC, rank ASC LIMIT ?""",
            (category_id, limit)
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
