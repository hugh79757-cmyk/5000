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

from pipelines.etap.visafree_writer import generate_visafree_guide
from shared.publishers.hugo_writer import _write_hugo_post_etap as _write_hugo_post
from pipelines.etap._contract import _normalize_result

BLOG_ID = "visafree-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/visafree-hugo"
TOPIC_TABLE = "visafree_topics"
CATEGORY = "Visa-Free Travel"


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
    country = article.get("country", "")
    if not country:
        return article
    conn = _get_db()
    cross = []
    esim = conn.execute(
        "SELECT title, link, price, sale_price, image_link FROM airalo_esim "
        "WHERE title LIKE ? ORDER BY CAST(REPLACE(COALESCE(sale_price,price),'$','') AS REAL) ASC LIMIT 1",
        ("%" + country + "%",)
    ).fetchone()
    if esim:
        esim = dict(esim)
        p = esim["sale_price"] or esim["price"]
        cross.append({
            "name": country + " eSIM - " + (esim["title"] or ""),
            "price": str(p).replace("$",""), "currency": "$",
            "discount": "", "image_url": esim["image_link"] or "",
            "link": esim["link"], "category": "eSIM",
        })
    tour = conn.execute(
        "SELECT product_name, price, currency, deep_link, image_url, category FROM viator_tours "
        "WHERE country = ? AND deep_link != '' ORDER BY CAST(price AS REAL) ASC LIMIT 1",
        (country,)
    ).fetchone()
    if tour:
        tour = dict(tour)
        cross.append({
            "name": tour["product_name"], "price": tour["price"],
            "currency": tour.get("currency","USD"), "discount": "",
            "image_url": tour.get("image_url",""), "link": tour["deep_link"],
            "category": tour.get("category","Tour"),
        })
    conn.close()
    if cross:
        article["content"] = insert_product_cards(article["content"], cross, max_cards=4)
    return article

def _run_impl() -> bool:
    topic = pick_topic()
    if not topic:
        logger.info("[visafree-hugo] No topics")
        return False
    logger.info(f"[visafree-hugo] {topic.get('passport','')} generating")
    article = generate_visafree_guide(topic)
    if not article:
        from pipelines.etap.topic_manager import mark_published_by_id
        mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID,
                             topic.get("title",""), topic.get("slug",""))
        logger.warning(f"[{BLOG_ID}] 데이터 부족 토픽 exhausted 처리: {topic.get('city','')}")
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
        is_dest = article.get("is_destination", False)
        label = country + " visa policy" if is_dest else country + " visa requirements"
        register_entity("country", country, BLOG_ID, article["slug"], label, 80, 1)
    return True


def run():
    """표준 계약 정규화 adapter (Phase 61, D-08). 기존 _run_impl 로직 위임. 반환만 표준 dict로."""
    return _normalize_result(_run_impl())



def run_batch(count=3):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota("visafree-hugo", max_per_day=5)
    if not can_pub:
        import logging
        logging.getLogger(__name__).info(f"[visafree-hugo] daily quota reached ({today_count}/5)")
        return 0
    count = min(count, 5 - today_count)
    ok = 0
    for _ in range(count):
        if _run_impl():
            ok += 1
        time.sleep(5)
    logger.info(f"[visafree-hugo] Batch {ok}/{count}")
    return ok
