"""daytrips_pipeline.py - Day Trips blog pipeline"""
import os, sys, sqlite3, logging, time, subprocess, re
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from pipelines.etap.image_fetcher import fetch_city_image, fetch_body_images
from pipelines.etap.post_processor import insert_product_cards, insert_comparison_table, insert_cross_sell_block, insert_adsense
from pipelines.etap.quality_guard import postprocess_content, send_alert, make_draft
from shared.entity_linker import inject_internal_links, register_entity, mark_entity_published, build_cross_sell_html
from pipelines.etap.topic_manager import pick_topic_by_id, mark_published_by_id, check_exhaustion

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")

from pipelines.etap.daytrips_writer import generate_daytrips_guide

BLOG_ID = "daytrips-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/daytrips-hugo"
TOPIC_TABLE = "daytrips_topics"
CATEGORY = "Day Trips"

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _write_hugo_post(article, cover_image=None, body_images=None, blog_id=None, site_path=None, category=None):
    slug = article["slug"]
    post_dir = os.path.join(site_path, "content", "posts", slug)
    os.makedirs(post_dir, exist_ok=True)
    now = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    tags_str = chr(10).join(f'  - "{t}"' for t in article.get("tags", []) if t)
    cover_line = ""
    credit_line = ""
    if cover_image and cover_image.get("url"):
        cover_line = 'featureimage: "' + cover_image["url"] + '"'
    if cover_image and cover_image.get("credit"):
        credit_line = 'featureimagecredit: "' + cover_image.get("credit", "") + '"'
    title_safe = article["title"].replace('"', "'")
    desc_safe = article.get("description", "").replace('"', "'")
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
        for idx in range(min(len(body_images), max(0, len(h2_positions) - 1))):
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
        content = insert_cross_sell_block(content, cross_html, position="top")
    if cover_image and cover_image.get("credit"):
        content = cover_image["credit"] + "\n\n" + content
    with open(os.path.join(post_dir, "index.md"), "w") as f:
        f.write(fm + "\n" + content)
    logger.info(f"Post written: {post_dir}")
    return post_dir

def _build_and_deploy(site_path, blog_id):
    hugo = "/opt/homebrew/bin/hugo"
    wrangler = "/opt/homebrew/bin/wrangler"
    try:
        subprocess.run([hugo, "--gc", "--minify"], cwd=site_path, check=True, capture_output=True)
        subprocess.run([wrangler, "pages", "deploy", "public", "--project-name", blog_id],
                      cwd=site_path, check=True, capture_output=True)
        logger.info(f"Deploy OK: {blog_id}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Deploy failed: {e}")
        return False

def _mark_published(article, blog_id, topic_table, topic_id):
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
    pool = with_img if with_img else tours
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
        selected.append(dict(
            name=nm, price=t.get("price",""), currency=t.get("currency","USD"),
            discount=str(t.get("discount","")).replace("%",""),
            image_url=t.get("image_url",""), link=t.get("deep_link",""),
            category=t.get("category",""),
        ))
    if selected:
        article["content"] = insert_product_cards(article["content"], selected, max_cards=5)
    # 카드에 이미 포함된 투어는 비교 테이블에서 제외
    card_names = seen.copy()
    comp_tours = [t for t in sorted(tours, key=lambda x: _safe_price(x.get("price",0))) if t.get("product_name","") not in card_names][:5]
    comp = [dict(name=__import__("re").sub(r"^Save [\d.]+%!\s*", "", t["product_name"]), price=t.get("price",""), currency=t.get("currency","USD"),
                 discount=str(t.get("discount","")).replace("%",""), link=t.get("deep_link",""))
            for t in comp_tours if t.get("deep_link")]
    if comp:
        article["content"] = insert_comparison_table(article["content"], comp, max_rows=5)
    return article

def run():
    topic = pick_topic()
    if not topic:
        logger.info(f"[{BLOG_ID}] No topics")
        return False
    logger.info(f"[{BLOG_ID}] {topic.get('city','')} generating")
    article = generate_daytrips_guide(topic)
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
        logger.warning(f"[{BLOG_ID}] DRAFT: {article['slug']} - {post_issues}")
        send_alert(BLOG_ID, article["slug"], post_issues)
        article["_draft"] = True
    elif post_issues:
        logger.info(f"[{BLOG_ID}] Quality warnings: {post_issues}")
    article = _add_product_cards(article)
    city = article.get("city", "")
    country = article.get("country", "")
    cover = fetch_city_image(city + " day trip", country, article["slug"]) if city else None
    body = fetch_body_images(city + " day trip", country, article["slug"], count=3) if city else []
    _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    _mark_published(article, BLOG_ID, TOPIC_TABLE, topic["id"])
    if city:
        register_entity("city", city, BLOG_ID, article["slug"],
                        "day trips from " + city, 60, 1)
    if country:
        register_entity("country", country, BLOG_ID, article["slug"],
                        "daytrips in " + country, 40, 1)
    return True

def run_batch(count=1):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota("daytrips-hugo", max_per_day=5)
    if not can_pub:
        import logging
        logging.getLogger(__name__).info(f"[daytrips-hugo] daily quota reached ({today_count}/5)")
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
