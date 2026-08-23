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
from shared.publishers.hugo_writer import _write_hugo_post_etap as _write_hugo_post
from pipelines.etap._contract import _normalize_result

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")

from pipelines.etap.airlines_writer import generate_airline_review

BLOG_ID = "airlines-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/airlines-hugo"
TOPIC_TABLE = "airlines_topics"
CATEGORY = "Airline Review"

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

def _safe_price(val):
    try:
        return float(str(val).replace("$","").replace(",","").strip())
    except:
        return 0

def pick_topic():
    """topic_manager 통합 — PK 기준 중복 방지 + 고갈 체크"""
    return pick_topic_by_id(TOPIC_TABLE, BLOG_ID)

def _add_product_cards(article):
    iata = article.get("iata", "")
    if not iata:
        return article
    conn = _get_db()
    cross = []
    dest_cities = conn.execute(
        "SELECT DISTINCT destination FROM airline_routes WHERE airline = ? LIMIT 3",
        (iata,)
    ).fetchall()
    for dc in dest_cities:
        code = dc[0]
        tour = conn.execute(
            "SELECT product_name, price, currency, deep_link, image_url, category FROM viator_tours "
            "WHERE deep_link != '' AND (city LIKE ? OR country LIKE ?) "
            "ORDER BY CAST(price AS REAL) ASC LIMIT 1",
            ("%" + code + "%", "%" + code + "%")
        ).fetchone()
        if tour:
            tour = dict(tour)
            cross.append({
                "name": tour["product_name"], "price": tour["price"],
                "currency": tour.get("currency","USD"), "discount": "",
                "image_url": tour.get("image_url",""), "link": tour["deep_link"],
                "category": tour.get("category",""),
            })
    conn.close()
    if cross:
        article["content"] = insert_product_cards(article["content"], cross, max_cards=3)
    return article

def _run_impl() -> bool:
    topic = pick_topic()
    if not topic:
        logger.info("[airlines-hugo] No topics")
        return False
    logger.info(f"[airlines-hugo] {topic.get('airline_name','')} generating")
    article = generate_airline_review(topic)
    if not article:
        # 데이터 부족 토픽 exhausted 처리 (무한 반복 방지)
        from pipelines.etap.topic_manager import mark_published_by_id
        mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID,
                             topic.get("title",""), topic.get("slug",""))
        logger.warning(f"[airlines-hugo] 데이터 부족 토픽 exhausted 처리: {topic.get('airline_name','')}")
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
    # cross-sell + 내부링크 (base pipeline.py:333-339 클론 — 항공사 리뷰는 도시 컨텍스트 없음, 링크 주입만)
    _cross_html = build_cross_sell_html(country="", city="", exclude_blog=BLOG_ID, max_items=3)
    if _cross_html:
        article["content"] = insert_cross_sell_block(article["content"], _cross_html, position="bottom")
    article["content"] = inject_internal_links(article["content"], current_blog=BLOG_ID, max_links=5)
    airline_name = article.get("airline_name", "")
    cover = fetch_city_image(airline_name + " airline", "", article["slug"]) if airline_name else None
    body = fetch_body_images(airline_name + " airplane", "", article["slug"], count=8) if airline_name else []
    _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    _mark_published(article, BLOG_ID, TOPIC_TABLE, topic["id"])
    if airline_name:
        register_entity("airline", airline_name, BLOG_ID, article["slug"],
                        airline_name + " airline review", 50, 1)
    return True


def run():
    """표준 계약 정규화 adapter (Phase 61, D-08). 기존 _run_impl 로직 위임. 반환만 표준 dict로."""
    return _normalize_result(_run_impl())



def run_batch(count=3):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota("airlines-hugo", max_per_day=5)
    if not can_pub:
        import logging
        logging.getLogger(__name__).info(f"[airlines-hugo] daily quota reached ({today_count}/5)")
        return 0
    count = min(count, 5 - today_count)
    ok = 0
    for _ in range(count):
        if _run_impl():
            ok += 1
        time.sleep(5)
    logger.info(f"[airlines-hugo] Batch {ok}/{count}")
    return ok
