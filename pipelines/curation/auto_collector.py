#!/usr/bin/env python3
"""
CUAP 백그라운드 상품 수집기
- 매시간 scheduler.py에서 호출
- 캐시 없는 키워드 우선 수집 (시간당 최대 5개 키워드)
- 쿠팡 API 시간당 6회 한도 준수
- 전체 키워드 캐시 완료 시 자동 슬립
"""
import os, sys, sqlite3, logging, time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))

from pipelines.curation.collector import (
    _check_rate_limit, _search_api, _log_api_call, _generate_keyword_variants
)
from pipelines.curation.keywords import KEYWORD_MAP

DB_PATH    = BASE_DIR / "data" / "curation.db"
CACHE_DAYS = 3
MAX_PER_RUN = 5  # 시간당 최대 수집 키워드 수

logger = logging.getLogger(__name__)


def _get_cached_keywords() -> dict:
    """keyword → 최신 collected_at 매핑 반환"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT keyword, MAX(collected_at) FROM products GROUP BY keyword"
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def _is_expired(collected_at: str) -> bool:
    """캐시 만료 여부 (CACHE_DAYS 초과)"""
    try:
        dt = datetime.fromisoformat(collected_at)
        return datetime.now() - dt > timedelta(days=CACHE_DAYS)
    except Exception:
        return True


def _save_products(keyword: str, products: list):
    """수집된 상품을 DB에 저장"""
    if not products:
        return 0
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat()
    saved = 0
    for p in products:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO products
                   (keyword, product_id, product_name, product_price, product_image,
                    product_url, category_name, rank, is_rocket, is_free_shipping, collected_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (keyword, p["productId"], p["productName"],
                 p.get("productPrice", 0), p.get("productImage", ""),
                 p.get("productUrl", ""), p.get("categoryName", ""),
                 p.get("rank", 0),
                 1 if p.get("isRocket") else 0,
                 1 if p.get("isFreeShipping") else 0, now)
            )
            saved += 1
        except Exception as e:
            logger.debug(f"상품 저장 실패 ({keyword}): {e}")
    conn.commit()
    conn.close()
    return saved


def run():
    """메인 수집 실행 — scheduler에서 매시간 호출"""
    logger.info("[auto_collector] 시작")

    # 전체 키워드 풀 수집
    all_keywords = []
    for blog_id, kws in KEYWORD_MAP.items():
        for kw in kws:
            all_keywords.append((blog_id, kw))

    total_kw = len(all_keywords)

    # 현재 캐시 상태
    cached = _get_cached_keywords()

    # 수집 우선순위 분류
    no_cache    = [(b, k) for b, k in all_keywords if k not in cached]
    expired     = [(b, k) for b, k in all_keywords if k in cached and _is_expired(cached[k])]
    fresh       = [(b, k) for b, k in all_keywords if k in cached and not _is_expired(cached[k])]

    logger.info(
        f"[auto_collector] 전체 {total_kw}개 | "
        f"캐시없음 {len(no_cache)}개 | "
        f"만료 {len(expired)}개 | "
        f"신선 {len(fresh)}개"
    )

    # 모두 신선하면 슬립
    if not no_cache and not expired:
        logger.info("[auto_collector] 모든 키워드 캐시 완료 — 슬립")
        return {"status": "sleep", "reason": "all_cached", "total": total_kw}

    # 수집 대상: 캐시없음 우선, 그 다음 만료
    targets = (no_cache + expired)[:MAX_PER_RUN]

    collected = 0
    skipped   = 0

    for blog_id, keyword in targets:
        if not _check_rate_limit():
            logger.warning(f"[auto_collector] API 한도 도달 — 중단 ({collected}개 수집)")
            break

        logger.info(f"[auto_collector] 수집: {blog_id} / {keyword}")
        products = _search_api(keyword, limit=10)
        _log_api_call()

        if products:
            # 변형 키워드로 추가 수집
            variants = _generate_keyword_variants(keyword)
            seen_ids = {p["productId"] for p in products}
            for vk in variants[1:]:
                if not _check_rate_limit():
                    break
                extra = _search_api(vk, limit=5)
                _log_api_call()
                if extra:
                    for ep in extra:
                        if ep["productId"] not in seen_ids:
                            products.append(ep)
                            seen_ids.add(ep["productId"])
                time.sleep(0.5)

            saved = _save_products(keyword, products)
            logger.info(f"[auto_collector] 저장: {keyword} → {saved}개")
            collected += 1
        else:
            logger.warning(f"[auto_collector] 수집 실패 (결과 없음): {keyword}")
            skipped += 1

        time.sleep(1)

    # 수집 후 현황
    cached_after = _get_cached_keywords()
    fresh_after  = sum(1 for k, t in cached_after.items() if not _is_expired(t))

    result = {
        "status":      "ok",
        "collected":   collected,
        "skipped":     skipped,
        "total_kw":    total_kw,
        "cached_now":  len(cached_after),
        "fresh_now":   fresh_after,
        "remaining":   len(no_cache) + len(expired) - collected,
    }
    logger.info(f"[auto_collector] 완료 — {result}")
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    result = run()
    print(f"\n결과: {result}")
    cached = _get_cached_keywords()
    fresh  = sum(1 for k, t in cached.items() if not _is_expired(t))
    print(f"캐시 현황: 전체 {len(cached)}개 키워드 / 신선 {fresh}개")
