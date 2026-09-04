"""escape_pipeline.py - Escape Rooms And Puzzle Experiences pipeline"""
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from pipelines.etap.escape_writer import generate_escape_guide
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
from shared.publishers.hugo_writer import _write_hugo_post_etap as _write_hugo_post
from pipelines.etap._contract import _normalize_result

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BLOG_ID = "escape-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/escape-hugo"
TOPIC_TABLE = "escape_topics"
CATEGORY = "Escape Rooms"

def _safe_price(val):
    try:
        return float(str(val).replace("$","").replace(",","").strip())
    except:
        return 0



def _affiliate_link(link):
    pid = os.getenv("VIATOR_PID", "")
    mcid = os.getenv("VIATOR_MCID", "42383")
    if pid and link and "pid=" not in link:
        sep = "&" if "?" in link else "?"
        link = f"{link}{sep}pid={pid}&mcid={mcid}&medium=link&campaign={BLOG_ID}"
    return link

def _add_product_cards(article):
    tours = article.get("tours", [])
    if not tours:
        return article
    selected = []
    seen = set()
    budget = [t for t in tours if 0 < _safe_price(t.get("price")) < 30][:3]
    mid = [t for t in tours if 30 <= _safe_price(t.get("price")) <= 100][:3]
    deals = sorted(
        [t for t in tours if t.get("discount") and str(t["discount"]) not in ("0","","0.0")],
        key=lambda x: _safe_price(str(x.get("discount","0")).replace("%","")), reverse=True
    )[:4]
    for t in budget + mid + deals:
        nm = re.sub(r"^Save [\d.]+%!\s*", "", t.get("product_name", ""))
        if nm in seen:
            continue
        seen.add(nm)
        selected.append({"name": nm, "price": t.get("price",""), "currency": t.get("currency","USD"),
            "discount": str(t.get("discount","")).replace("%",""),
            "image_url": t.get("image_url",""), "link": _affiliate_link(t.get("deep_link","")), "category": t.get("category","")})
    if selected:
        article["content"] = insert_product_cards(article["content"], selected, max_cards=5)
    comp_tours = [t for t in sorted(tours, key=lambda x: _safe_price(x.get("price",0))) if t.get("product_name","") not in seen][:5]
    comp = [{"name": re.sub(r"^Save [\d.]+%!\s*","",t["product_name"]), "price": t.get("price",""),
                 "currency": t.get("currency","USD"), "discount": str(t.get("discount","")).replace("%",""),
                 "link": t.get("deep_link","")} for t in comp_tours if t.get("deep_link")]
    if comp:
        article["content"] = insert_comparison_table(article["content"], comp, max_rows=5)
    return article

def _disambiguate_slug(slug: str, city: str) -> str:
    """기존 발행 slug(corpus)와 충돌 시 접미 disambiguator 부여 (P12 lookbook)."""
    import os as _os
    from pathlib import Path as _P
    base = slug or re.sub(r"[^a-z0-9]+", "-", (city or "escape").lower()).strip("-") + "-escape-rooms"
    posts_dir = _P(SITE_PATH) / "content" / "posts"
    seen = set()
    if posts_dir.is_dir():
        seen = {p.name for p in posts_dir.iterdir() if p.is_dir()}
    if base not in seen:
        return base
    for n in range(2, 50):
        cand = f"{base}-{n}"
        if cand not in seen:
            logger.info(f"[{BLOG_ID}] slug 충돌 회전: {base} → {cand}")
            return cand
    return base


def _run_impl(cfg=None) -> bool:
    topic = pick_topic_by_id(TOPIC_TABLE, BLOG_ID)
    if not topic:
        logger.info(f"[{BLOG_ID}] No topics")
        return False
    city = topic.get("city", "")
    country = topic.get("country", "")
    logger.info(f"[{BLOG_ID}] {city} generating")
    article = generate_escape_guide(topic)
    if not article:
        mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID, topic.get("title",""), topic.get("slug",""))
        logger.warning(f"[{BLOG_ID}] 데이터 부족: {city}")
        return False
    data_prices = [float(str(t.get("price",0)).replace("$","").replace(",","")) for t in article.get("tours",[]) if t.get("price")]
    article["content"], post_issues, is_draft = postprocess_content(article["content"], data_prices=data_prices, blog_id=BLOG_ID, slug=article["slug"])
    if is_draft:
        logger.warning(f"[{BLOG_ID}] DRAFT 감지 → 발행 중단: {article['slug']} - {post_issues}")
        send_alert(BLOG_ID, article["slug"], post_issues)
        return False
    if post_issues:
        logger.info(f"[{BLOG_ID}] Quality warnings: {post_issues}")
    # B-step: 슬러그 중복 회전 (P12 lookbook) — 기존 발행 slug와 충돌 시 disambiguator 부여
    article["slug"] = _disambiguate_slug(article.get("slug", ""), article.get("city", ""))
    article = _add_product_cards(article)
    cover = fetch_city_image(city, country, article["slug"]) if city else None
    body = fetch_body_images(city, country, article["slug"], count=8) if city else []
    write_result = _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    if write_result is None or (isinstance(write_result, dict) and not write_result.get("success")):
        logger.error(f"[{BLOG_ID}] _write_hugo_post failed for {article['slug']} — 발행 차단")
        return False
    mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID, article["title"], article["slug"])
    mark_entity_published(BLOG_ID, article["slug"])
    if city:
        register_entity("city", city, BLOG_ID, article["slug"], "escape rooms and puzzle experiences in " + city, 50, 1)
    if country:
        register_entity("country", country, BLOG_ID, article["slug"], "escape rooms and puzzle experiences in " + country, 35, 1)
    return True


def run(cfg=None):
    """표준 계약 정규화 adapter (Phase 61, D-08). 기존 _run_impl 로직 위임. 반환만 표준 dict로."""
    return _normalize_result(_run_impl(cfg))



def run_batch(cfg=None, count=3):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota(BLOG_ID, max_per_day=5)
    if not can_pub:
        logger.info(f"[{BLOG_ID}] daily quota reached ({today_count}/5)")
        return 0
    count = min(count, 5 - today_count)
    ok = 0
    for _ in range(count):
        if _run_impl():
            ok += 1
        time.sleep(5)
    logger.info(f"[{BLOG_ID}] Batch {ok}/{count}")
    return ok
