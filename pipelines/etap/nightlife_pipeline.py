"""nightlife_pipeline.py - Nightlife And Entertainment pipeline"""
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

from pipelines.etap.image_fetcher import fetch_body_images, fetch_city_image
from pipelines.etap.nightlife_writer import generate_nightlife_guide
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

BLOG_ID = "nightlife-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/nightlife-hugo"
TOPIC_TABLE = "nightlife_topics"
CATEGORY = "Nightlife"

def _safe_price(val):
    try:
        return float(str(val).replace("$","").replace(",","").strip())
    except:
        return 0

def _write_hugo_post(article, cover_image=None, body_images=None, blog_id=None, site_path=None, category=None):
    slug = article["slug"]
    post_dir = os.path.join(site_path, "content", "posts", slug)
    os.makedirs(post_dir, exist_ok=True)
    now = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    tags_str = chr(10).join(f'  - "{t}"' for t in article.get("tags", []) if t)
    cover_line = ""
    credit_line = ""
    if cover_image and cover_image.get("url"):
        from shared.publisher import sanitize_featureimage_url
        img_url = sanitize_featureimage_url(cover_image["url"])
        if img_url:
            cover_line = 'featureimage: "' + img_url + '"'
    if cover_image and cover_image.get("credit"):
        credit_line = 'featureimagecredit: "' + cover_image.get("credit", "") + '"'
    title_safe = article["title"].replace('"',"'")
    desc_safe = article.get("description", "").replace('"',"'")
    fm = "---\n"
    fm += f'title: "{title_safe}"\n'
    fm += f"date: {now}\n"
    fm += f'description: "{desc_safe}"\n'
    if cover_line:
        fm += cover_line + "\n"
    if credit_line:
        fm += credit_line + "\n"
    fm += "tags:\n" + tags_str + "\n"
    fm += f'categories:\n  - "{category}"\n'
    fm += "showTableOfContents: true\n"
    if article.get("_draft"):
        fm += "draft: true\n"
    fm += "---\n"
    content = article["content"]
    content = inject_internal_links(content, current_blog=blog_id, max_links=5)
    content = insert_adsense(content)
    if body_images:
        h2_positions = [m.start() for m in re.finditer(r"^## ", content, re.MULTILINE)]
        for idx in range(min(len(body_images), len(h2_positions))):
            img = body_images[idx]
            img_block = "\n\n![Photo](" + img["url"] + ")\n*" + img.get("credit", "") + "*\n"
            h2_line_end = content.index("\n", h2_positions[idx]) + 1
            next_pp = content.find("\n\n", h2_line_end)
            if next_pp == -1:
                next_pp = len(content)
            content = content[:next_pp] + img_block + content[next_pp:]
            h2_positions = [m.start() for m in re.finditer(r"^## ", content, re.MULTILINE)]
    country = article.get("country", "")
    city = article.get("city", "")
    cross_html = build_cross_sell_html(country=country, city=city, exclude_blog=blog_id, max_items=3)
    if cross_html:
        content = insert_cross_sell_block(content, cross_html, position="bottom")
    with open(os.path.join(post_dir, "index.md"), "w") as f:
        f.write(fm + "\n" + content)
    logger.info(f"Post written: {post_dir}")
    return post_dir

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

def run(cfg=None) -> bool:
    topic = pick_topic_by_id(TOPIC_TABLE, BLOG_ID)
    if not topic:
        logger.info(f"[{BLOG_ID}] No topics")
        return False
    city = topic.get("city", "")
    country = topic.get("country", "")
    logger.info(f"[{BLOG_ID}] {city} generating")
    article = generate_nightlife_guide(topic)
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
    article = _add_product_cards(article)
    cover = fetch_city_image(city + " nightlife city lights entertainment", country, article["slug"]) if city else None
    body = fetch_body_images(city + " nightlife entertainment show", country, article["slug"], count=8) if city else []
    _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID, article["title"], article["slug"])
    mark_entity_published(BLOG_ID, article["slug"])
    if city:
        register_entity("city", city, BLOG_ID, article["slug"], "nightlife and entertainment in " + city, 50, 1)
    if country:
        register_entity("country", country, BLOG_ID, article["slug"], "nightlife and entertainment in " + country, 35, 1)
    return True

def run_batch(cfg=None, count=3):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota(BLOG_ID, max_per_day=5)
    if not can_pub:
        logger.info(f"[{BLOG_ID}] daily quota reached ({today_count}/5)")
        return 0
    count = min(count, 5 - today_count)
    ok = 0
    for _ in range(count):
        if run():
            ok += 1
        time.sleep(5)
    if ok > 0:
        _build_and_deploy(SITE_PATH, BLOG_ID)
    logger.info(f"[{BLOG_ID}] Batch {ok}/{count}")
    return ok
