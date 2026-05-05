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

from pipelines.etap.eurail_writer import generate_eurail_guide

BLOG_ID = "eurail-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/eurail-hugo"
TOPIC_TABLE = "eurail_topics"
CATEGORY = "European Rail"


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
        logger.error(f"Deploy failed: {e}")
        return False

def _mark_published(article, blog_id, topic_table, topic_id):
    """topic_manager 통합 — PK 기준 발행 기록"""
    from shared.entity_linker import mark_entity_published
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
        comp.append(dict(name="Train", price=str(r["train_min_price"]), currency=currency, discount="", link=r.get("link_url", "#")))
    if r.get("bus_min_price"):
        comp.append(dict(name="Bus", price=str(r["bus_min_price"]), currency=currency, discount="", link=r.get("link_url", "#")))
    if r.get("flight_min_price"):
        comp.append(dict(name="Flight", price=str(r["flight_min_price"]), currency=currency, discount="", link=r.get("link_url", "#")))
    if r.get("ferry_min_price"):
        comp.append(dict(name="Ferry", price=str(r["ferry_min_price"]), currency=currency, discount="", link=r.get("link_url", "#")))
    if comp:
        article["content"] = insert_comparison_table(article["content"], comp, max_rows=5)
    link_url = r.get("link_url", "")
    if link_url:
        origin = article.get("origin", "")
        dest = article.get("destination", "")
        cards = [dict(
            name="Compare and book " + origin + " to " + dest,
            price="", currency="", discount="",
            image_url=r.get("image_url",""),
            link=link_url, category="Train / Bus / Flight",
        )]
        article["content"] = insert_product_cards(article["content"], cards, max_cards=1)
    return article

def run():
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
        article["content"], data_prices=_data_prices if _data_prices else None,
        blog_id=BLOG_ID, slug=article["slug"])
    if _qg_draft:
        logger.warning("[%s] DRAFT: %s - %s", BLOG_ID, article["slug"], _qg_issues)
        send_alert(BLOG_ID, article["slug"], _qg_issues)
        article["_draft"] = True
    elif _qg_issues:
        logger.info("[%s] Quality warnings: %s", BLOG_ID, _qg_issues)
    article = _add_product_cards(article)
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
        if run():
            ok += 1
        time.sleep(5)
    if ok > 0:
        _build_and_deploy(SITE_PATH, BLOG_ID)
    logger.info(f"[eurail-hugo] Batch {ok}/{count}")
    return ok
