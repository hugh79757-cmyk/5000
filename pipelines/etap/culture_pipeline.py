"""culture_pipeline.py - Art and culture blog pipeline"""
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

from pipelines.etap.culture_writer import generate_culture_guide
from shared.publishers.hugo_writer import _write_hugo_post_etap as _write_hugo_post
from pipelines.etap._contract import _normalize_result

BLOG_ID = "culture-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/culture-hugo"
TOPIC_TABLE = "culture_topics"
CATEGORY = "Culture Tours"

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
    tours = article.get("tours", [])
    if not tours:
        return article
    selected = []
    seen = set()
    budget = [t for t in tours if 0 < _safe_price(t.get("price")) < 30][:3]
    mid = [t for t in tours if 30 <= _safe_price(t.get("price")) <= 100][:3]
    deals = sorted(
        [t for t in tours if t.get("discount") and str(t["discount"]) not in ("0","","0.0")],
        key=lambda x: _safe_price(str(x.get("discount","0")).replace("%","")),
        reverse=True
    )[:4]
    for t in budget + mid + deals:
        nm = re.sub(r"^Save [\d.]+%!\s*", "", t.get("product_name", ""))
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
    card_names = seen.copy()
    comp_tours = [t for t in sorted(tours, key=lambda x: _safe_price(x.get("price",0))) if t.get("product_name","") not in card_names][:5]
    comp = [{"name": re.sub(r"^Save [\d.]+%!\s*", "", t["product_name"]), "price": t.get("price",""), "currency": t.get("currency","USD"),
                 "discount": str(t.get("discount","")).replace("%",""), "link": t.get("deep_link","")}
            for t in comp_tours if t.get("deep_link")]
    if comp:
        article["content"] = insert_comparison_table(article["content"], comp, max_rows=5)
    return article


def _add_heritage_card(article):
    """Add heritage.aikorea24.kr card for Seoul/Korea culture posts."""
    city = article.get("city", "").lower()
    country = article.get("country", "").lower()
    korea_match = city in ("seoul", "busan", "gyeongju", "jeonju", "suwon") or "korea" in country
    if not korea_match:
        return article
    heritage_html = """

<div style="margin:24px 0;padding:20px;background:linear-gradient(135deg,#fdf6e3,#fff8dc);border-radius:14px;border:1px solid #d4a574;box-shadow:0 2px 8px rgba(0,0,0,0.06)">
<p style="margin:0 0 8px;font-size:13px;color:#8b6914;font-weight:600;letter-spacing:0.5px">🏛️ KOREAN HERITAGE GUIDE</p>
<p style="margin:0 0 12px;font-size:17px;font-weight:700;color:#2d1b00">Explore 600 Years of Royal Palace History</p>
<p style="margin:0 0 14px;font-size:14px;color:#5a3e1b;line-height:1.5">From Gyeongbokgung to Jongmyo Shrine — discover Korean royal palaces with audio guides in 4 languages, interactive maps, photos, and videos.</p>
<a href="https://heritage.aikorea24.kr/?lang=en" target="_blank" rel="noopener" style="display:inline-block;padding:10px 22px;background:#8b6914;color:#fff;border-radius:8px;text-decoration:none;font-size:14px;font-weight:600">Explore Korean Palaces →</a>
</div>

"""
    # Insert before the last H2 section
    import re
    h2_matches = list(re.finditer(r"^## ", article["content"], re.MULTILINE))
    if len(h2_matches) >= 2:
        insert_pos = h2_matches[-1].start()
        article["content"] = article["content"][:insert_pos] + heritage_html + article["content"][insert_pos:]
    else:
        article["content"] += heritage_html
    return article

def _run_impl() -> bool:
    topic = pick_topic()
    if not topic:
        logger.info(f"[{BLOG_ID}] No topics")
        return False
    city = topic.get("city", "")
    country = topic.get("country", "")
    logger.info(f"[{BLOG_ID}] {city} generating")
    article = generate_culture_guide(topic)
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
    article = _add_heritage_card(article)
    cover = fetch_city_image(city, country, article["slug"]) if city else None
    body = fetch_body_images(city, country, article["slug"], count=8) if city else []
    _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    _mark_published(article, BLOG_ID, TOPIC_TABLE, topic["id"])
    if city:
        register_entity("city", city, BLOG_ID, article["slug"], "culture tours in " + city, 55, 1)
    if country:
        register_entity("country", country, BLOG_ID, article["slug"], "art tours in " + country, 40, 1)
    return True


def run():
    """표준 계약 정규화 adapter (Phase 61, D-08). 기존 _run_impl 로직 위임. 반환만 표준 dict로."""
    return _normalize_result(_run_impl())



def run_batch(count=3):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota("culture-hugo", max_per_day=5)
    if not can_pub:
        import logging
        logging.getLogger(__name__).info(f"[culture-hugo] daily quota reached ({today_count}/5)")
        return 0
    count = min(count, 5 - today_count)
    ok = 0
    for _ in range(count):
        if _run_impl():
            ok += 1
        time.sleep(5)
    logger.info(f"[{BLOG_ID}] Batch {ok}/{count}")
    return ok
