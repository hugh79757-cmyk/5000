from pipelines.etap.post_processor import insert_adsense
from pipelines.etap.quality_guard import postprocess_content, send_alert
"""
항공권 딜 글 발행 파이프라인
"""
import os
import sys
import sqlite3
import logging
import subprocess
import time
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

from pipelines.etap.topic_manager import check_exhaustion, send_telegram
logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
sys.path.insert(0, BASE_DIR)

from pipelines.etap.flight_writer import generate_flight_deal
from pipelines.etap.image_fetcher import fetch_city_image, fetch_body_images


def _get_db():
    return sqlite3.connect(DB_PATH)


def pick_flight_topic(blog_id="flights-hugo"):
    db = _get_db()
    row = db.execute("""
        SELECT ft.id, ft.origin, ft.destination, ft.origin_city, ft.dest_city,
               ft.title, ft.slug
        FROM flight_topics ft
        WHERE ft.exhausted = 0
        AND NOT EXISTS (
            SELECT 1 FROM publish_log pl WHERE pl.topic_id = ft.id
            AND pl.blog_id = ?
        )
        AND EXISTS (
            SELECT 1 FROM flight_prices fp
            WHERE fp.origin = ft.origin AND fp.destination = ft.destination
        )
        ORDER BY ft.priority DESC, RANDOM()
        LIMIT 1
    """, (blog_id,)).fetchone()
    if not row:
        row = db.execute("""
            SELECT ft.id, ft.origin, ft.destination, ft.origin_city, ft.dest_city,
                   ft.title, ft.slug
            FROM flight_topics ft
            WHERE ft.exhausted = 0
            AND NOT EXISTS (
                SELECT 1 FROM publish_log pl WHERE pl.topic_id = ft.id
                AND pl.blog_id = ?
            )
            ORDER BY ft.priority DESC, RANDOM()
            LIMIT 1
        """, (blog_id,)).fetchone()
    db.close()
    if not row:
        return None
    return {"id": row[0], "origin": row[1], "destination": row[2],
            "origin_city": row[3], "dest_city": row[4],
            "title": row[5], "slug": row[6]}



def _insert_body_images(content, images):
    """H2 섹션 사이에 이미지 삽입"""
    if not images:
        return content
    lines = content.split("\n")
    h2_indices = [i for i, line in enumerate(lines) if line.startswith("## ")]
    inserted = 0
    for idx in h2_indices[1:4]:
        if inserted >= len(images):
            break
        img = images[inserted]
        img_md = f'\n![Photo]({img["url"]})\n*{img["credit"]}*\n'
        insert_pos = idx + inserted * 4
        lines.insert(insert_pos, img_md)
        inserted += 1
    return "\n".join(lines)

def _write_hugo_post(cfg, article):
    slug = article["slug"]
    post_dir = os.path.join(cfg["site_path"], "content", "posts", slug)
    os.makedirs(post_dir, exist_ok=True)
    now = datetime.now(KST).isoformat(timespec="seconds")
    tags_yaml = "\n".join([f'  - "{t}"' for t in article.get("tags", [])])
    img_block = ""
    credit_line = ""
    if article.get("image_url"):
        img_block = f'featureimage: "{article["image_url"]}"'
        if article.get("image_credit"):
            credit_line = article["image_credit"]
    fm = f"""---
title: "{article['title']}"
date: {now}
description: "{article['description']}"
{img_block}
tags:
{tags_yaml}
categories:
  - "Flight Deals"
params:
  priceUpdateTime: "{datetime.now(KST).strftime('%B %d, %Y %H:%M KST')}"
showTableOfContents: true
---
{credit_line}

{_insert_body_images(article['content'], article.get('body_images', []))}
"""
    filepath = os.path.join(post_dir, "index.md")
    with open(filepath, "w") as f:
        f.write(fm)
    logger.info(f"[ETAP-Flight] 파일 생성: {filepath}")
    return filepath


def _build_and_deploy(cfg):
    site = cfg["site_path"]
    subprocess.run(["/opt/homebrew/bin/hugo", "--gc", "--minify"], cwd=site, capture_output=True)
    subprocess.run(["/opt/homebrew/bin/wrangler", "pages", "deploy", "public",
                    "--project-name", cfg["cf_project"]], cwd=site, capture_output=True)
    logger.info(f"[ETAP-Flight] Deployed to {cfg['domain']}")


def mark_published(topic_id, blog_id, title, slug):
    db = _get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("""
        INSERT INTO publish_log (topic_id, blog_id, title, slug, published_at, url)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (topic_id, blog_id, title, slug, now, slug))
    db.commit()
    db.close()


def run(cfg):
    topic = pick_flight_topic(blog_id=cfg.get("id", "flights-hugo"))
    if topic:
        post_dir = os.path.join(cfg["site_path"], "content", "posts", topic["slug"])
        if os.path.exists(post_dir):
            logger.warning(f"[ETAP-Flight] 이미 존재하는 슬러그, 스킵: {topic['slug']}")
            db = _get_db()
            db.execute("UPDATE flight_topics SET exhausted = 1 WHERE id = ?", (topic["id"],))
            db.commit()
            db.close()
            topic = pick_flight_topic(blog_id=cfg.get("id", "flights-hugo"))
    if not topic:
        logger.info("[ETAP-Flight] 발행 가능한 토픽 없음")
        return {"status": "skip"}
    logger.info(f"[ETAP-Flight] {topic['origin_city']} -> {topic['dest_city']} 글 생성 시작")
    article = generate_flight_deal(topic)
    if not article:
        return {"status": "error", "reason": "generation failed"}
    img = fetch_city_image(topic["dest_city"], "", topic["slug"])
    if img:
        article["image_url"] = img.get("url", "")
        article["image_credit"] = img.get("credit", "")
    body_imgs = fetch_body_images(topic["dest_city"], "", topic["slug"], count=3)
    if body_imgs:
        article["body_images"] = body_imgs
    _write_hugo_post(cfg, article)
    mark_published(topic["id"], cfg.get("id", "flights-hugo"), article["title"], article["slug"])
    return {"status": "ok", "title": article["title"], "slug": article["slug"]}


def run_batch(cfg, count=2):
    results = []
    for i in range(count):
        result = run(cfg)
        results.append(result)
        if result["status"] == "skip":
            break
        if i < count - 1:
            time.sleep(5)
    if any(r["status"] == "ok" for r in results):
        _build_and_deploy(cfg)
    ok = sum(1 for r in results if r["status"] == "ok")
    logger.info(f"[ETAP-Flight] 배치 완료: {ok}/{count}건")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    cfg = {
        "id": "tour-hugo",
        "domain": "tour.techpawz.com",
        "site_path": "/Users/twinssn/Projects/ETAP/flights-hugo",
        "cf_project": "flights-hugo",
    }
    result = run(cfg)
    print(result)