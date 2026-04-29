"""deals_pipeline.py - Flight deals by origin city pipeline"""
import os, sys, sqlite3, logging, time, subprocess, re
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from pipelines.etap.image_fetcher import fetch_city_image, fetch_body_images
from pipelines.etap.post_processor import insert_product_cards, insert_comparison_table, insert_cross_sell_block, insert_adsense
from pipelines.etap.quality_guard import postprocess_content, send_alert
from shared.entity_linker import inject_internal_links, register_entity, mark_entity_published, build_cross_sell_html
from pipelines.etap.topic_manager import pick_topic_by_id, mark_published_by_id, check_exhaustion

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")

from pipelines.etap.deals_writer import generate_deals_guide

BLOG_ID = "deals-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/deals-hugo"
TOPIC_TABLE = "deals_topics"
CATEGORY = "Flight Deals"


# === ETAP v2 Postprocessing ===
try:
    from pipelines.etap.post_processor import fix_encoding, clean_tags, calculate_quality_metrics
    HAS_PP = True
except ImportError:
    HAS_PP = False
# === END ===

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
        for idx in range(min(len(body_images), len(h2_positions))):
            img = body_images[idx]
            img_block = "\n\n![Photo](" + img["url"] + ")\n*" + img.get("credit", "") + "*\n"
            h2_line_end = content.index("\n", h2_positions[idx]) + 1
            next_pp = content.find("\n\n", h2_line_end)
            if next_pp == -1:
                next_pp = len(content)
            content = content[:next_pp] + img_block + content[next_pp:]
            h2_positions = [m.start() for m in re.finditer(r"^## ", content, re.MULTILINE)]
    cross_html = build_cross_sell_html(country="", city=article.get("origin",""), exclude_blog=blog_id, max_items=3)
    if cross_html:
        content = insert_cross_sell_block(content, cross_html, position="bottom")
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
    from shared.entity_linker import mark_entity_published
    mark_published_by_id(topic_id=topic_id, topic_table=topic_table, blog_id=blog_id,
                         title=article["title"], slug=article["slug"], url="")
    mark_entity_published(blog_id, article["slug"])

def pick_topic():
    return pick_topic_by_id(TOPIC_TABLE, BLOG_ID)

def run():
    topic = pick_topic()
    if not topic:
        logger.info(f"[{BLOG_ID}] No topics")
        return False
    logger.info(f"[{BLOG_ID}] {topic.get('origin_city', topic.get('origin',''))} generating")
    article = generate_deals_guide(topic)
    if not article:
        from pipelines.etap.topic_manager import mark_published_by_id
        mark_published_by_id(topic["id"], TOPIC_TABLE, BLOG_ID,
                             topic.get("title",""), topic.get("slug",""))
        logger.warning(f"[{BLOG_ID}] 데이터 부족 토픽 exhausted 처리: {topic.get('city','')}")
        return False
    article["content"], post_issues, is_draft = postprocess_content(article["content"], data_prices=None, blog_id=BLOG_ID, slug=article["slug"])
    if is_draft:
        logger.warning(f"[{BLOG_ID}] DRAFT 감지 → 발행 중단: {article['slug']} - {post_issues}")
        send_alert(BLOG_ID, article["slug"], post_issues)
        return False
    origin = article.get("origin", "")
    # country 자리에 origin 도시명을 넣어 관련성 필터 통과율 향상
    cover = fetch_city_image(origin + " airport travel", origin, article["slug"]) if origin else None
    body = fetch_body_images(origin + " city travel", origin, article["slug"], count=8) if origin else []
    _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    _mark_published(article, BLOG_ID, TOPIC_TABLE, topic["id"])
    if origin:
        register_entity("city", origin, BLOG_ID, article["slug"], "flight deals from " + origin, 50, 1)
    return True

def run_batch(count=1):
    from pipelines.etap.topic_manager import check_daily_quota
    can_pub, today_count = check_daily_quota("deals-hugo", max_per_day=5)
    if not can_pub:
        import logging
        logging.getLogger(__name__).info(f"[deals-hugo] daily quota reached ({today_count}/5)")
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
