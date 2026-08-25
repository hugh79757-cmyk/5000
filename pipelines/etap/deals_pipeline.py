"""deals_pipeline.py - Flight deals by origin city pipeline"""
import logging
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from pipelines.etap.image_fetcher import fetch_body_images, fetch_city_image
from pipelines.etap.post_processor import (
    insert_adsense,
    insert_cross_sell_block,
)
from pipelines.etap.quality_guard import postprocess_content, send_alert
from pipelines.etap.topic_manager import mark_published_by_id, pick_topic_by_id
from shared.entity_linker import (
    build_cross_sell_html,
    inject_internal_links,
    mark_entity_published,
    register_entity,
)

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")

from pipelines.etap.deals_writer import generate_deals_guide
from shared.publishers.hugo_writer import _write_hugo_post_etap as _write_hugo_post
from pipelines.etap._contract import _normalize_result

BLOG_ID = "deals-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/deals-hugo"
TOPIC_TABLE = "deals_topics"
CATEGORY = "Flight Deals"


# === ETAP v2 Postprocessing ===
try:
    from pipelines.etap.post_processor import calculate_quality_metrics, clean_tags, fix_encoding
    HAS_PP = True
except ImportError:
    HAS_PP = False
# === END ===

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn



def _mark_published(article, blog_id, topic_table, topic_id) -> None:
    mark_published_by_id(topic_id=topic_id, topic_table=topic_table, blog_id=blog_id,
                         title=article["title"], slug=article["slug"], url="",
                         unique_data_points=article.get("unique_data_points"))
    mark_entity_published(blog_id, article["slug"])

def pick_topic():
    return pick_topic_by_id(TOPIC_TABLE, BLOG_ID)

def _run_impl() -> dict | bool:
    topic = pick_topic()
    if not topic:
        logger.info(f"[{BLOG_ID}] No topics")
        return {"success": False, "reason": "no_topic"}
    logger.info(f"[{BLOG_ID}] {topic.get('origin_city', topic.get('origin',''))} generating")
    try:
        article = generate_deals_guide(topic)
    except RuntimeError as e:
        error_msg = str(e)
        if "chain_timeout" in error_msg:
            reason = "chain_timeout"
        elif "quota" in error_msg.lower() or "429" in error_msg:
            reason = "ai_quota"
        else:
            reason = "ai_generate_error"
        from pipelines.etap.topic_manager import mark_published_by_id
        mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID,
                             topic.get("title",""), topic.get("slug",""))
        logger.warning(f"[{BLOG_ID}] AI 생성 오류({reason}): {error_msg[:120]}")
        return {"success": False, "reason": reason}
    if not article:
        from pipelines.etap.topic_manager import mark_published_by_id
        mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID,
                             topic.get("title",""), topic.get("slug",""))
        logger.warning(f"[{BLOG_ID}] 데이터 부족 토픽 exhausted 처리: {topic.get('origin_city', topic.get('origin',''))}")
        return {"success": False, "reason": "no_data"}
    article["content"], post_issues, is_draft = postprocess_content(article["content"], data_prices=None, blog_id=BLOG_ID, slug=article["slug"])
    if is_draft:
        logger.warning(f"[{BLOG_ID}] DRAFT 감지 → 발행 중단: {article['slug']} - {post_issues}")
        send_alert(BLOG_ID, article["slug"], post_issues)
        return {"success": False, "reason": "draft_detected"}
    origin = article.get("origin", "")
    # 커버: 목적지(destination) 기준으로 고유화 — 동일 origin 출발 글끼리 썸네일 중복 방지
    # body: 동일하게 목적지 기반 분산 (origin만 쓰면 LA 출발 4건 모두 동일 Pexels 결과 → 동일 R2 etag)
    _deals_for_img = article.get("deals", [])
    _dest_for_cover = _deals_for_img[0].get("dest_city") if _deals_for_img and _deals_for_img[0].get("dest_city") else origin
    cover = fetch_city_image(_dest_for_cover + " travel", _dest_for_cover, article["slug"]) if _dest_for_cover else None
    body = fetch_body_images(_dest_for_cover + " city travel", _dest_for_cover, article["slug"], count=8) if _dest_for_cover else []
    # cross-sell: base pipeline 표준 블록 (deals는 도시 기반 — origin을 city로 사용)
    cross_html = build_cross_sell_html(
        country=article.get("country", ""),
        city=origin,
        exclude_blog=BLOG_ID, max_items=3)
    if cross_html:
        article["content"] = insert_cross_sell_block(article["content"], cross_html, position="bottom")
    article["content"] = inject_internal_links(article["content"], current_blog=BLOG_ID, max_links=5)
    # write-fail 가드 (multiday 패턴): 쓰기 실패 시 mark_published 스킵 → DB/디스크 불일치(팬텀 행) 방지
    write_result = _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    if write_result is None or (isinstance(write_result, dict) and not write_result.get("success")):
        logger.error(f"[{BLOG_ID}] Hugo 쓰기 실패 → 발행 차단: {article['slug']}")
        return {"success": False, "reason": "write_failed"}
    _mark_published(article, BLOG_ID, TOPIC_TABLE, topic["id"])
    if origin:
        register_entity("city", origin, BLOG_ID, article["slug"], "flight deals from " + origin, 50, 1)
    return True


def run():
    """표준 계약 정규화 adapter (Phase 61, D-08). 기존 _run_impl 로직 위임. 반환만 표준 dict로."""
    return _normalize_result(_run_impl())



def run_batch(count=1):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota("deals-hugo", max_per_day=5)
    if not can_pub:
        import logging
        logging.getLogger(__name__).info(f"[deals-hugo] daily quota reached ({today_count}/5)")
        return 0
    count = min(count, 5 - today_count)
    ok = 0
    for _ in range(count):
        if _run_impl() is True:
            ok += 1
        time.sleep(5)
    logger.info(f"[{BLOG_ID}] Batch {ok}/{count}")
    return ok
