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


def _build_and_deploy(site_path, blog_id) -> bool | None:
    hugo = "/opt/homebrew/bin/hugo"
    wrangler = "/opt/homebrew/bin/wrangler"
    try:
        # leaf bundle 방지: content/posts/index.md 존재 시 삭제
        from pathlib import Path as _Path
        rogue = _Path(site_path) / "content" / "posts" / "index.md"
        if rogue.exists():
            rogue.unlink()
            logger.info(f"[guard] Removed rogue index.md from {site_path}")
        subprocess.run([hugo, "--gc", "--minify"], cwd=site_path, check=True, capture_output=True)
        subprocess.run([wrangler, "pages", "deploy", "public", "--project-name", blog_id],
                      cwd=site_path, check=True, capture_output=True)
        logger.info(f"Deploy OK: {blog_id}")
        return True
    except subprocess.CalledProcessError as e:
        logger.exception(f"Deploy failed: {e}")
        return False

def _mark_published(article, blog_id, topic_table, topic_id) -> None:
    mark_published_by_id(topic_id=topic_id, topic_table=topic_table, blog_id=blog_id,
                         title=article["title"], slug=article["slug"], url="")
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
    # country 자리에 origin 도시명을 넣어 관련성 필터 통과율 향상
    cover = fetch_city_image(origin + " airport travel", origin, article["slug"]) if origin else None
    body = fetch_body_images(origin + " city travel", origin, article["slug"], count=8) if origin else []
    _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
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
