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
    insert_product_cards,
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

from pipelines.etap.esim_writer import generate_esim_guide
from shared.publishers.hugo_writer import _write_hugo_post_etap as _write_hugo_post

BLOG_ID = "esim-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/esim-hugo"
TOPIC_TABLE = "esim_topics"
CATEGORY = "eSIM Guide"

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
    """topic_manager 통합 — PK 기준 발행 기록"""
    mark_published_by_id(
        topic_id=topic_id,
        topic_table=topic_table,
        blog_id=blog_id,
        title=article["title"],
        slug=article["slug"],
        url=""
    )
    mark_entity_published(blog_id, article["slug"])

def _safe_price(val):
    try:
        return float(str(val).replace("$","").replace(",","").strip())
    except:
        return 0

def pick_topic():
    """topic_manager 통합 — PK 기준 중복 방지 + 고갈 체크"""
    return pick_topic_by_id(TOPIC_TABLE, BLOG_ID)

def _add_product_cards(article):
    plans = article.get("plans", [])
    if not plans:
        return article
    selected = []
    for p in plans[:8]:
        price_val = str(p.get("sale_price") or p.get("price","")).replace("$","")
        original = str(p.get("price","")).replace("$","")
        discount = ""
        try:
            pf = float(price_val)
            of = float(original)
            if pf < of:
                discount = str(round((1 - pf/of) * 100))
        except:
            pass
        selected.append({
            "name": p.get("title",""), "price": price_val, "currency": "$",
            "discount": discount, "image_url": p.get("image_link",""),
            "link": p.get("link",""), "category": "eSIM Plan",
        })
    if selected:
        article["content"] = insert_product_cards(article["content"], selected, max_cards=8)
    return article

def run() -> bool:
    topic = pick_topic()
    if not topic:
        logger.info("[esim-hugo] No topics")
        return False
    logger.info(f"[esim-hugo] {topic.get('country','')} generating")
    article = generate_esim_guide(topic)
    if not article:
        from pipelines.etap.topic_manager import mark_published_by_id
        mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID,
                             topic.get("title",""), topic.get("slug",""))
        logger.warning(f"[{BLOG_ID}] 데이터 부족 토픽 exhausted 처리: {topic.get('airline_name','')}")
        return False

    # Quality guard
    article["content"], _qg_issues, _qg_draft = postprocess_content(
        article["content"], data_prices=None,
        blog_id=BLOG_ID, slug=article["slug"])
    if _qg_draft:
        logger.warning("[%s] DRAFT: %s - %s", BLOG_ID, article["slug"], _qg_issues)
        send_alert(BLOG_ID, article["slug"], _qg_issues)
        article["_draft"] = True
    elif _qg_issues:
        logger.info("[%s] Quality warnings: %s", BLOG_ID, _qg_issues)
    article = _add_product_cards(article)
    country = article.get("country", "")
    cover = fetch_city_image(country, "", article["slug"]) if country else None
    body = fetch_body_images(country, "", article["slug"], count=8) if country else []
    _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    _mark_published(article, BLOG_ID, TOPIC_TABLE, topic["id"])
    if country:
        register_entity("country", country, BLOG_ID, article["slug"], country + " eSIM plans", 70, 1)
    return True

def run_batch(count=3):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota("esim-hugo", max_per_day=5)
    if not can_pub:
        import logging
        logging.getLogger(__name__).info(f"[esim-hugo] daily quota reached ({today_count}/5)")
        return 0
    count = min(count, 5 - today_count)
    ok = 0
    for _ in range(count):
        if run():
            ok += 1
        time.sleep(5)
    logger.info(f"[esim-hugo] Batch {ok}/{count}")
    return ok
