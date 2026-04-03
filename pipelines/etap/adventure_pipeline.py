"""adventure_pipeline.py - Adventure blog pipeline"""
import os, sys, sqlite3, logging, time, subprocess, re
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from pipelines.etap.image_fetcher import fetch_city_image, fetch_body_images
from pipelines.etap.post_processor import insert_product_cards, insert_comparison_table, insert_cross_sell_block, insert_adsense
from shared.entity_linker import inject_internal_links, register_entity, mark_entity_published, build_cross_sell_html

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")

from pipelines.etap.adventure_writer import generate_adventure_guide

BLOG_ID = "adventure-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/adventure-hugo"
TOPIC_TABLE = "adventure_topics"
CATEGORY = "Adventure"

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

def _mark_published(article, blog_id, topic_table):
    conn = _get_db()
    conn.execute("INSERT INTO publish_log (blog_id, slug, title, published_at) VALUES (?,?,?,?)",
                 (blog_id, article["slug"], article["title"], datetime.now(KST).isoformat()))
    conn.execute(f"UPDATE {topic_table} SET exhausted = 1 WHERE slug = ?", (article["slug"],))
    conn.commit()
    conn.close()
    mark_entity_published(blog_id, article["slug"])

def _safe_price(val):
    try:
        return float(str(val).replace("$","").replace(",","").strip())
    except:
        return 0

def pick_topic():
    conn = _get_db()
    row = conn.execute(
        f"SELECT * FROM {TOPIC_TABLE} WHERE exhausted = 0 "
        f"AND slug NOT IN (SELECT slug FROM publish_log WHERE blog_id = '{BLOG_ID}') "
        "ORDER BY priority DESC, id ASC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None

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
    article = generate_adventure_guide(topic)
    if not article:
        return False
    article = _add_product_cards(article)
    city = article.get("city", "")
    country = article.get("country", "")
    cover = fetch_city_image(city + " adventure activity", country, article["slug"]) if city else None
    body = fetch_body_images(city + " adventure activity", country, article["slug"], count=3) if city else []
    _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    _mark_published(article, BLOG_ID, TOPIC_TABLE)
    if city:
        register_entity("city", city, BLOG_ID, article["slug"],
                        "adventure activities in " + city, 60, 1)
    if country:
        register_entity("country", country, BLOG_ID, article["slug"],
                        "adventure in " + country, 40, 1)
    return True

def run_batch(count=1):
    ok = 0
    for _ in range(count):
        if run():
            ok += 1
        time.sleep(5)
    if ok > 0:
        _build_and_deploy(SITE_PATH, BLOG_ID)
    logger.info(f"[{BLOG_ID}] Batch {ok}/{count}")
    return ok
