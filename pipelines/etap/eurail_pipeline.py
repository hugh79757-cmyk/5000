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

from pipelines.etap.eurail_writer import generate_eurail_guide
from shared.publishers.hugo_writer import _write_hugo_post_etap as _write_hugo_post
from pipelines.etap._contract import _normalize_result

BLOG_ID = "eurail-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/eurail-hugo"
TOPIC_TABLE = "eurail_topics"
CATEGORY = "European Rail"


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
    routes = article.get("routes", [])
    if not routes:
        return article
    r = routes[0]
    currency = r.get("currency", "USD")
    comp = []
    if r.get("train_min_price"):
        comp.append({"name": "Train", "price": str(r["train_min_price"]), "currency": currency, "discount": "", "link": r.get("link_url", "#")})
    if r.get("bus_min_price"):
        comp.append({"name": "Bus", "price": str(r["bus_min_price"]), "currency": currency, "discount": "", "link": r.get("link_url", "#")})
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
            "name": "Compare and book " + origin + " to " + dest,
            "price": "", "currency": "", "discount": "",
            "image_url": r.get("image_url",""),
            "link": link_url, "category": "Train / Bus / Flight",
        }]
        article["content"] = insert_product_cards(article["content"], cards, max_cards=1)
    return article

def _run_impl() -> bool:
    topic = pick_topic()
    if not topic:
        logger.info("[eurail-hugo] No topics")
        return False
    origin = topic.get("origin", "")
    dest = topic.get("destination", "")
    logger.info(f"[eurail-hugo] {origin} to {dest} generating")
    article = generate_eurail_guide(topic)
    if not article:
        from pipelines.etap.topic_manager import mark_published_by_id
        mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID,
                             topic.get("title",""), topic.get("slug",""))
        logger.warning(f"[{BLOG_ID}] 데이터 부족 토픽 exhausted 처리: {topic.get('city','')}")
        return False

    # Quality guard
    _data_prices = []
    for _t in article.get("routes", []):
        try:
            _p = float(str(_t.get("price", 0)).replace("$","").replace(",",""))
            if _p > 0:
                _data_prices.append(_p)
        except Exception:
            pass
    article["content"], _qg_issues, _qg_draft = postprocess_content(
        article["content"], data_prices=_data_prices or None,
        blog_id=BLOG_ID, slug=article["slug"])
    if _qg_draft:
        logger.warning("[%s] DRAFT: %s - %s", BLOG_ID, article["slug"], _qg_issues)
        send_alert(BLOG_ID, article["slug"], _qg_issues)
        article["_draft"] = True
    elif _qg_issues:
        logger.info("[%s] Quality warnings: %s", BLOG_ID, _qg_issues)
    article = _add_product_cards(article)
    # cross-sell + 내부링크 (base pipeline.py:333-339 복제 — 전용 파이프라인은 import만 있고 호출부가 없었음)
    cross_html = build_cross_sell_html(
        country=topic.get("dest_country", ""),
        city=dest,
        exclude_blog=BLOG_ID, max_items=3)
    if cross_html:
        article["content"] = insert_cross_sell_block(article["content"], cross_html, position="bottom")
    article["content"] = inject_internal_links(article["content"], current_blog=BLOG_ID, max_links=5)
    search_term = origin or dest
    cover = fetch_city_image(search_term, "", article["slug"]) if search_term else None
    body = fetch_body_images(search_term, "", article["slug"], count=8) if search_term else []
    _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    _mark_published(article, BLOG_ID, TOPIC_TABLE, topic["id"])
    if origin:
        register_entity("city", origin, BLOG_ID, article["slug"], "European rail from " + origin, 55, 1)
    if dest:
        register_entity("city", dest, BLOG_ID, article["slug"], "rail routes to " + dest, 55, 1)
    return True


def run():
    """표준 계약 정규화 adapter (Phase 61, D-08). 기존 _run_impl 로직 위임. 반환만 표준 dict로."""
    return _normalize_result(_run_impl())



def run_batch(count=3):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota("eurail-hugo", max_per_day=5)
    if not can_pub:
        import logging
        logging.getLogger(__name__).info(f"[eurail-hugo] daily quota reached ({today_count}/5)")
        return 0
    count = min(count, 5 - today_count)
    ok = 0
    for _ in range(count):
        if _run_impl():
            ok += 1
        time.sleep(5)
    logger.info(f"[eurail-hugo] Batch {ok}/{count}")
    return ok
