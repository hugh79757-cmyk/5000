"""curation 파이프라인 — 상품 큐레이션 글 자동 발행

흐름: 키워드 선택 → 상품 수집(캐시) → AI 글 생성 → Hugo 발행
"""
import os
import sys
import re
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/5000/.env")

from shared.content_store import get_today_count, title_similar_exists
from shared.publisher import publish
from shared.validators import sanitize_title
from shared.image_handler import process_and_upload
import requests as _requests
from shared.telegram_notifier import send_error as _tg_error
from pipelines.curation.keywords import get_keywords
from pipelines.curation.collector import collect_keyword, get_products
from pipelines.curation.writer import generate_curation_article
from pipelines.curation.enricher import enrich_products

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_DIR / "data" / "curation.db"


def _select_keyword(blog_id):
    """7일 내 미사용 키워드 중 하나 선택"""
    keywords = get_keywords(blog_id)
    if not keywords:
        return None

    conn = sqlite3.connect(str(DB_PATH))
    used = conn.execute(
        """SELECT keyword FROM publish_log
           WHERE blog_id=? AND published_at > datetime('now', '-7 days')""",
        (blog_id,)
    ).fetchall()
    conn.close()

    used_set = {r[0] for r in used}
    available = [k for k in keywords if k not in used_set]

    if not available:
        conn = sqlite3.connect(str(DB_PATH))
        oldest = conn.execute(
            """SELECT keyword FROM publish_log
               WHERE blog_id=? ORDER BY published_at ASC LIMIT 1""",
            (blog_id,)
        ).fetchone()
        conn.close()
        return oldest[0] if oldest else keywords[0]

    return available[0]


def _upload_thumbnail(image_url):
    """쿠팡 상품 이미지를 R2에 업로드하여 썸네일로 사용"""
    try:
        resp = _requests.get(image_url, timeout=10)
        if resp.status_code == 200 and len(resp.content) > 1000:
            r2_url = process_and_upload(resp.content, key_prefix="curation-images")
            return r2_url
    except Exception as e:
        logger.warning(f"썸네일 업로드 실패: {e}")
    return ""


def _filter_used_products(blog_id, products):
    """30일 내 동일 blog_id에서 발행된 상품 제외"""
    if not products:
        return products
    conn = sqlite3.connect(str(DB_PATH))
    used = conn.execute(
        """SELECT product_id FROM published_products
           WHERE blog_id=? AND published_at > datetime('now', '-30 days')""",
        (blog_id,)
    ).fetchall()
    conn.close()
    used_ids = {r[0] for r in used}
    filtered = [p for p in products if p["product_id"] not in used_ids]
    if len(filtered) < 3:
        return products[:5]
    return filtered[:5]


def _record_products(blog_id, keyword, products):
    """발행에 사용된 상품 ID 기록"""
    conn = sqlite3.connect(str(DB_PATH))
    now = datetime.now().isoformat()
    for p in products:
        conn.execute(
            "INSERT INTO published_products (blog_id, product_id, keyword, published_at) VALUES (?,?,?,?)",
            (blog_id, p["product_id"], keyword, now)
        )
    conn.commit()
    conn.close()


def _make_slug(keyword):
    slug = keyword.replace(" ", "-").lower()
    slug = re.sub(r'[^a-z0-9가-힣\-]', '', slug)
    date_prefix = datetime.now().strftime("%Y%m%d")
    return f"{date_prefix}-{slug}"


def _record_publish(blog_id, keyword, title, slug):
    """publish_log에 발행 기록"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO publish_log (blog_id, keyword, title, slug, published_at) VALUES (?,?,?,?,?)",
        (blog_id, keyword, title, slug, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def run(cfg):
    """curation 파이프라인 메인 — dispatcher에서 호출"""
    blog_id = cfg.get("id", "")
    daily_quota = cfg.get("daily_quota", 5)

    # 할당량 체크
    today_count = get_today_count(blog_id)
    if today_count >= daily_quota:
        logger.info(f"[{blog_id}] 할당량 도달 ({today_count}/{daily_quota})")
        return {"success": False, "reason": "quota_met"}

    # 키워드 선택
    keyword = _select_keyword(blog_id)
    if not keyword:
        logger.error(f"[{blog_id}] 사용 가능한 키워드 없음")
        _tg_error(blog_id, "keyword", "키워드 풀 비어있음")
        return {"success": False, "reason": "no_keyword"}

    # 상품 수집 (캐시 또는 API)
    collected = collect_keyword(keyword)
    if not collected:
        logger.error(f"[{blog_id}] 상품 수집 실패: {keyword}")
        return {"success": False, "reason": "collect_error"}

    products = get_products(keyword, limit=10)
    products = _filter_used_products(blog_id, products)
    if len(products) < 3:
        logger.error(f"[{blog_id}] 상품 부족: {keyword} ({len(products)}개)")
        return {"success": False, "reason": "insufficient_products"}

    # 상품 데이터 인리치 (스펙 파싱 + 네이버 brand)
    products = enrich_products(products, blog_id)

    # AI 글 생성
    article = generate_curation_article(keyword, products)
    if not article:
        return {"success": False, "reason": "write_error"}

    title = sanitize_title(article["title"])
    body_md = article["body_md"]
    description = article.get("description", "")
    if description:
        body_md = f"<!-- DESC: {description} -->\n\n{body_md}"
    slug = _make_slug(keyword)

    # 썸네일: 첫 번째 상품 이미지를 R2에 업로드
    thumbnail_url = ""
    if products and products[0].get("product_image"):
        thumbnail_url = _upload_thumbnail(products[0]["product_image"])

    # 유사 제목 체크
    if title_similar_exists(blog_id, title):
        logger.warning(f"[{blog_id}] 유사 제목 존재: {title}")
        return {"success": False, "reason": "similar_title"}

    # 발행
    result = publish(blog_id, title, body_md, category="추천", tags=keyword, thumbnail_url=thumbnail_url)
    if not result or not result.get("success"):
        logger.error(f"[{blog_id}] 발행 실패: {title}")
        return {"success": False, "reason": "publish_error"}

    # 발행 기록
    _record_publish(blog_id, keyword, title, slug)
    _record_products(blog_id, keyword, products[:5])
    logger.info(f"[{blog_id}] 발행 완료: {title}")

    return {
        "success": True,
        "title": title,
        "keyword": keyword,
        "product_count": article["product_count"],
    }
