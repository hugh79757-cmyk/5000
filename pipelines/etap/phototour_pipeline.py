"""phototour_pipeline.py - Photography Tours blog pipeline"""
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

from pipelines.etap.phototour_writer import generate_phototour_guide
from shared.publishers.hugo_writer import _write_hugo_post_etap as _write_hugo_post
from pipelines.etap._contract import _normalize_result

BLOG_ID = "phototour-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/phototour-hugo"
TOPIC_TABLE = "phototour_topics"
CATEGORY = "Photography Tours"


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
    tours = article.get("tours", [])
    if not tours:
        return article
    with_img = [t for t in tours if t.get("image_url")]
    pool = with_img or tours
    budget = [t for t in pool if 0 < _safe_price(t.get("price")) < 50][:3]
    mid = [t for t in pool if 50 <= _safe_price(t.get("price")) <= 200][:3]
    deals = sorted(
        [t for t in pool if t.get("discount") and str(t["discount"]) not in ("0","","0.0")],
        key=lambda x: _safe_price(str(x.get("discount","0")).replace("%","")),
        reverse=True
    )[:4]
    selected = []
    seen = set()
    for t in budget + mid + deals:
        nm = t.get("product_name", "")
        import re as _re
        nm = _re.sub(r"^Save [\d.]+%!\s*", "", nm)
        if nm in seen:
            continue
        seen.add(nm)
        selected.append({
            "name": nm, "price": t.get("price",""), "currency": t.get("currency","USD"),
            "discount": str(t.get("discount","")).replace("%",""),
            "image_url": t.get("image_url",""), "link": t.get("deep_link",""),
            "category": t.get("category",""),
        })
    if selected:
        article["content"] = insert_product_cards(article["content"], selected, max_cards=5)
    # 카드에 이미 포함된 투어는 비교 테이블에서 제외
    card_names = seen.copy()
    comp_tours = [t for t in sorted(tours, key=lambda x: _safe_price(x.get("price",0))) if t.get("product_name","") not in card_names][:5]
    comp = [{"name": __import__("re").sub(r"^Save [\d.]+%!\s*", "", t["product_name"]), "price": t.get("price",""), "currency": t.get("currency","USD"),
                 "discount": str(t.get("discount","")).replace("%",""), "link": t.get("deep_link","")}
            for t in comp_tours if t.get("deep_link")]
    if comp:
        article["content"] = insert_comparison_table(article["content"], comp, max_rows=5)
    return article

def _run_impl() -> bool:
    topic = pick_topic()
    if not topic:
        logger.info(f"[{BLOG_ID}] No topics")
        return False
    logger.info(f"[{BLOG_ID}] {topic.get('city','')} generating")
    article = generate_phototour_guide(topic)
    if not article:
        from pipelines.etap.topic_manager import mark_published_by_id
        mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID,
                             topic.get("title",""), topic.get("slug",""))
        logger.warning(f"[{BLOG_ID}] 데이터 부족 토픽 exhausted 처리: {topic.get('city','')}")
        return False
    # Post-process quality check
    data_prices = [float(str(t.get("price",0)).replace("$","").replace(",","")) for t in article.get("tours", article.get("routes", article.get("restaurants", []))) if t.get("price")]
    article["content"], post_issues, is_draft = postprocess_content(article["content"], data_prices=data_prices, blog_id=BLOG_ID, slug=article["slug"])
    if is_draft:
        logger.warning(f"[{BLOG_ID}] DRAFT 감지 → 발행 중단: {article['slug']} - {post_issues}")
        send_alert(BLOG_ID, article["slug"], post_issues)
        return False
    if post_issues:
        logger.info(f"[{BLOG_ID}] Quality warnings: {post_issues}")
    article = _add_product_cards(article)
    city = article.get("city", "")
    country = article.get("country", "")
    cover = fetch_city_image(city + " photo tour", country, article["slug"]) if city else None
    body = fetch_body_images(city + " photo tour", country, article["slug"], count=8) if city else []
    _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    _mark_published(article, BLOG_ID, TOPIC_TABLE, topic["id"])
    if city:
        register_entity("city", city, BLOG_ID, article["slug"],
                        "photo tours from " + city, 60, 1)
    if country:
        register_entity("country", country, BLOG_ID, article["slug"],
                        "photo tours in " + country, 40, 1)
    return True


def run():
    """표준 계약 정규화 adapter (Phase 61, D-08). 기존 _run_impl 로직 위임. 반환만 표준 dict로."""
    return _normalize_result(_run_impl())



def run_batch(count=1):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota("phototour-hugo", max_per_day=5)
    if not can_pub:
        import logging
        logging.getLogger(__name__).info(f"[phototour-hugo] daily quota reached ({today_count}/5)")
        return 0
    count = min(count, 5 - today_count)
    ok = 0
    for _ in range(count):
        if _run_impl():
            ok += 1
        time.sleep(5)
    logger.info(f"[{BLOG_ID}] Batch {ok}/{count}")
    return ok
