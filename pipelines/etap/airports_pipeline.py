import os, sys, sqlite3, logging, time, subprocess, re
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from pipelines.etap.image_fetcher import fetch_city_image, fetch_body_images
from pipelines.etap.post_processor import insert_product_cards, insert_comparison_table, insert_cross_sell_block
from shared.entity_linker import inject_internal_links, register_entity, mark_entity_published, build_cross_sell_html

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")

from pipelines.etap.airports_writer import generate_airport_guide

BLOG_ID = "airports-hugo"
SITE_PATH = "/Users/twinssn/Projects/ETAP/airports-hugo"
TOPIC_TABLE = "airports_topics"
CATEGORY = "Airport Guide"

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
        "SELECT * FROM airports_topics WHERE exhausted = 0 "
        "AND slug NOT IN (SELECT slug FROM publish_log WHERE blog_id = 'airports-hugo') "
        "ORDER BY priority DESC, id ASC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def _add_product_cards(article):
    city = article.get("city", "")
    country = article.get("country", "")
    if not city and not country:
        return article
    conn = _get_db()
    cross = []
    esim = conn.execute(
        "SELECT title, link, price, sale_price, image_link FROM airalo_esim "
        "WHERE title LIKE ? ORDER BY CAST(REPLACE(COALESCE(sale_price,price),'$','') AS REAL) ASC LIMIT 1",
        ("%" + country + "%",)
    ).fetchone()
    if esim:
        p = esim["sale_price"] or esim["price"]
        cross.append(dict(
            name=country + " eSIM", price=str(p).replace("$",""),
            currency="$", discount="", image_url=esim.get("image_link","") or "",
            link=esim["link"], category="eSIM",
        ))
    tour = conn.execute(
        "SELECT product_name, price, currency, deep_link, image_url, category FROM viator_tours "
        "WHERE city = ? AND deep_link != '' ORDER BY CAST(price AS REAL) ASC LIMIT 1",
        (city,)
    ).fetchone()
    if tour:
        cross.append(dict(
            name=tour["product_name"], price=tour["price"],
            currency=tour.get("currency","USD"), discount="",
            image_url=tour.get("image_url",""), link=tour["deep_link"],
            category=tour.get("category",""),
        ))
    conn.close()
    if cross:
        article["content"] = insert_product_cards(article["content"], cross, max_cards=3, position="bottom")
    return article

def run():
    topic = pick_topic()
    if not topic:
        logger.info("[airports-hugo] No topics")
        return False
    logger.info(f"[airports-hugo] {topic.get('iata_code','')} generating")
    article = generate_airport_guide(topic)
    if not article:
        return False
    article = _add_product_cards(article)
    city = article.get("city", "")
    country = article.get("country", "")
    iata = article.get("iata", "")
    cover = fetch_city_image(city or iata, country, article["slug"]) if city else None
    body = fetch_body_images(city or iata, country, article["slug"], count=2) if city else []
    _write_hugo_post(article, cover, body, BLOG_ID, SITE_PATH, CATEGORY)
    _mark_published(article, BLOG_ID, TOPIC_TABLE)
    if city:
        register_entity("city", city, BLOG_ID, article["slug"], "airport in " + city, 60, 1)
    if country:
        register_entity("country", country, BLOG_ID, article["slug"], "airports in " + country, 35, 1)
    return True

def run_batch(count=3):
    ok = 0
    for _ in range(count):
        if run():
            ok += 1
        time.sleep(5)
    if ok > 0:
        _build_and_deploy(SITE_PATH, BLOG_ID)
    logger.info(f"[airports-hugo] Batch {ok}/{count}")
    return ok
