"""bus_pipeline.py - Bus route blog pipeline"""
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
    insert_comparison_table,
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

from pipelines.etap.bus_writer import generate_bus_guide
from shared.publishers.hugo_writer import _write_hugo_post_etap as _write_hugo_post
from pipelines.etap._contract import _normalize_result

BLOG_ID = "bus-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/bus-hugo"
TOPIC_TABLE = "bus_topics"
CATEGORY = "Bus Travel"

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn



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

def pick_topic():
    """topic_manager 통합 — PK 기준 중복 방지 + 고갈 체크"""
    return pick_topic_by_id(TOPIC_TABLE, BLOG_ID)

def _add_product_cards(article):
    routes = article.get("routes", [])
    if not routes:
        return article
    r = routes[0]
    currency = r.get("currency", "USD")
    comp = []
    if r.get("bus_min_price"):
        comp.append({"name": "Bus", "price": str(r["bus_min_price"]), "currency": currency, "discount": "", "link": r.get("link_url", "#")})
    if r.get("train_min_price"):
        comp.append({"name": "Train", "price": str(r["train_min_price"]), "currency": currency, "discount": "", "link": r.get("link_url", "#")})
    if r.get("flight_min_price"):
        comp.append({"name": "Flight", "price": str(r["flight_min_price"]), "currency": currency, "discount": "", "link": r.get("link_url", "#")})
    if r.get("ferry_min_price"):
        comp.append({"name": "Ferry", "price": str(r["ferry_min_price"]), "currency": currency, "discount": "", "link": r.get("link_url", "#")})
    if comp:
        article["content"] = insert_comparison_table(article["content"], comp, max_rows=5)
    link_url = r.get("link_url", "")
    if link_url:
        origin = article.get("origin", "")
        dest = article.get("destination", "")
        cards = [{
            "name": "Compare and book " + origin + " to " + dest + " by bus",
            "price": "", "currency": "", "discount": "",
            "image_url": r.get("image_url", ""),
            "link": link_url, "category": "Bus / Train / Flight",
        }]
        article["content"] = insert_product_cards(article["content"], cards, max_cards=1)
    return article

def _run_impl() -> bool:
    topic = pick_topic()
    if not topic:
        logger.info(f"[{BLOG_ID}] No topics")
        return False
    origin = topic.get("origin", "")
    dest = topic.get("destination", "")
    logger.info(f"[{BLOG_ID}] {origin} to {dest} generating")
    article = generate_bus_guide(topic)
    if not article:
        from pipelines.etap.topic_manager import mark_published_by_id
        mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID,
                             topic.get("title",""), topic.get("slug",""))
        logger.warning(f"[{BLOG_ID}] 데이터 부족 토픽 exhausted 처리: {topic.get('airline_name','')}")
        return False
    data_prices = [float(str(r.get(k,0))) for r in article.get("routes",[]) for k in ["bus_min_price","train_min_price","flight_min_price","ferry_min_price"] if r.get(k)]
    article["content"], post_issues, is_draft = postprocess_content(article["content"], data_prices=data_prices, blog_id=BLOG_ID, slug=article["slug"])
    if is_draft:
        logger.warning(f"[{BLOG_ID}] DRAFT 감지 → 발행 중단: {article['slug']} - {post_issues}")
        send_alert(BLOG_ID, article["slug"], post_issues)
        return False
    if post_issues:
        logger.info(f"[{BLOG_ID}] Quality warnings: {post_issues}")
    article = _add_product_cards(article)
    search_term = origin or dest
    cover = fetch_city_image(search_term + " bus station", "", article["slug"]) if search_term else None
    body = fetch_body_images(search_term + " bus travel", "", article["slug"], count=8) if search_term else []
    write_result = _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    if write_result is None or (isinstance(write_result, dict) and not write_result.get("success")):
        logger.error(f"[{BLOG_ID}] _write_hugo_post failed for {article['slug']} — 발행 차단")
        return False
    _mark_published(article, BLOG_ID, TOPIC_TABLE, topic["id"])
    if origin:
        register_entity("city", origin, BLOG_ID, article["slug"], "bus from " + origin, 50, 1)
    if dest:
        register_entity("city", dest, BLOG_ID, article["slug"], "bus to " + dest, 50, 1)
    return True


def run():
    """표준 계약 정규화 adapter (Phase 61, D-08). 기존 _run_impl 로직 위임. 반환만 표준 dict로."""
    return _normalize_result(_run_impl())



def run_batch(count=3):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota("bus-hugo", max_per_day=5)
    if not can_pub:
        import logging
        logging.getLogger(__name__).info(f"[bus-hugo] daily quota reached ({today_count}/5)")
        return 0
    count = min(count, 5 - today_count)
    ok = 0
    for _ in range(count):
        if _run_impl():
            ok += 1
        time.sleep(5)
    logger.info(f"[{BLOG_ID}] Batch {ok}/{count}")
    return ok
