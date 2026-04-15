"""ETAP pipeline — 영문 travel 블로그 자동 발행."""
import logging
import os
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from pipelines.etap.topic_manager import pick_topic, mark_published, check_exhaustion, send_telegram
from pipelines.etap.writer import generate_city_guide
from pipelines.etap.quality_guard import postprocess_content, send_alert, make_draft
from pipelines.etap.image_fetcher import fetch_city_image, fetch_body_images



def _insert_body_images(content, images):
    """H2 헤딩 뒤에 본문 이미지 삽입 (최대 3장)"""
    if not images:
        return content
    lines = content.split("\n")
    h2_indices = [i for i, line in enumerate(lines) if line.startswith("## ")]
    # 2번째, 3번째, 4번째 H2 뒤에 삽입
    insert_after = h2_indices[1:4] if len(h2_indices) > 1 else h2_indices
    inserted = 0
    offset = 0
    for idx in insert_after:
        if inserted >= len(images):
            break
        img = images[inserted]
        img_md = f"\n![Photo]({img['url']})\n*{img['credit']}*\n"
        pos = idx + offset + 2  # H2 다음 줄 + 한 줄 여유
        if pos > len(lines):
            pos = len(lines)
        lines.insert(pos, img_md)
        offset += 1
        inserted += 1
    return "\n".join(lines)

def _write_hugo_post(cfg: dict, article: dict) -> str:
    """Hugo 마크다운 파일 생성. 발행된 파일 경로 반환."""
    site_path = Path(cfg["site_path"])
    slug = article["slug"]
    post_dir = site_path / "content" / "posts" / slug
    post_dir.mkdir(parents=True, exist_ok=True)

    tags_str = "\n".join(f'  - "{t}"' for t in article["tags"])

    image_block = ""
    credit_line = ""
    if article.get("image"):
        img_url = article["image"]["url"]
        image_block = f'\nfeatureimage: "{img_url}"\n'
        if article["image"].get("credit"):
            credit_line = article["image"]["credit"] + "\n\n"

    draft_line = "draft: true\n" if article.get("_draft") else ""
    frontmatter = f"""---
title: "{article['title']}"
date: {datetime.now().astimezone().isoformat(timespec='seconds')}
description: "{article['description']}"
{image_block}tags:
{tags_str}
categories:
  - "Travel Guide"
showTableOfContents: true
{draft_line}---

{credit_line}"""
    filepath = post_dir / "index.md"
    final_content = article["content"]
    if article.get("body_images"):
        final_content = _insert_body_images(final_content, article["body_images"])
    filepath.write_text(frontmatter + final_content, encoding="utf-8")
    return str(filepath)


def _build_and_deploy(cfg: dict) -> bool:
    """Hugo 빌드 + Wrangler 배포."""
    import subprocess
    site_path = cfg["site_path"]
    cf_project = cfg["cf_project"]

    build = subprocess.run(
        ["/opt/homebrew/bin/hugo", "--gc", "--minify"],
        cwd=site_path, capture_output=True, text=True, timeout=120
    )
    if build.returncode != 0:
        print(f"[ETAP] Hugo build failed: {build.stderr}")
        return False

    deploy = subprocess.run(
        ["/opt/homebrew/bin/wrangler", "pages", "deploy", "public", "--project-name", cf_project],
        cwd=site_path, capture_output=True, text=True, timeout=120
    )
    if deploy.returncode != 0:
        print(f"[ETAP] Wrangler deploy failed: {deploy.stderr}")
        return False

    print(f"[ETAP] Deployed to {cfg['domain']}")
    return True


def run(cfg: dict) -> dict:
    """dispatcher에서 호출하는 메인 함수."""
    blog_id = cfg["id"]


    # 고갈 체크
    can_pub, remaining = check_exhaustion("topics", blog_id)
    if not can_pub:
        return {"status": "exhausted", "remaining": 0}

    topic = pick_topic(blog_id)
    if not topic:
        print(f"[ETAP] {blog_id}: 발행 가능한 토픽 없음")
        return {"status": "skip", "reason": "no_topic"}

    print(f"[ETAP] {blog_id}: {topic['city']}, {topic['country']} 글 생성 시작")

    article = generate_city_guide(topic)

    # Quality guard
    article["content"], post_issues, is_draft = postprocess_content(
        article["content"], data_prices=None, blog_id=blog_id, slug=article["slug"])
    if is_draft:
        logger.warning(f"[ETAP] {blog_id} DRAFT: {article['slug']} - {post_issues}")
        send_alert(blog_id, article["slug"], post_issues)
        article["_draft"] = True
    elif post_issues:
        logger.info(f"[ETAP] {blog_id} quality: {post_issues}")

    image = fetch_city_image(topic["city"], topic["country"], article["slug"])
    if image:
        article["image"] = image
    body_imgs = fetch_body_images(topic.get("city", ""), topic.get("country", ""), article["slug"], count=3)
    if body_imgs:
        article["body_images"] = body_imgs
    filepath = _write_hugo_post(cfg, article)
    print(f"[ETAP] 파일 생성: {filepath}")

    deployed = _build_and_deploy(cfg)

    mark_published(
        topic_id=topic["topic_id"],
        blog_id=blog_id,
        title=article["title"],
        slug=article["slug"],
        url=f"https://{cfg['domain']}/posts/{article['slug']}/" if deployed else ""
    )

    return {
        "status": "ok" if deployed else "build_fail",
        "title": article["title"],
        "slug": article["slug"],
        "city": article["city"],
    }



def run_batch(cfg: dict, count: int = 3) -> list:
    """count건 연속 발행 후 마지막에 1회 빌드+배포."""
    import time
    blog_id = cfg["id"]
    results = []

    for i in range(count):
        topic = pick_topic(blog_id)
        if not topic:
            print(f"[ETAP] {blog_id}: 토픽 소진 (발행 {i}건 후 중단)")
            break

        print(f"[ETAP] {blog_id}: [{i+1}/{count}] {topic['city']}, {topic['country']}")

        article = generate_city_guide(topic)

        # Quality guard
        article["content"], post_issues, is_draft = postprocess_content(
            article["content"], data_prices=None, blog_id=blog_id, slug=article["slug"])
        if is_draft:
            logger.warning(f"[ETAP] {blog_id} DRAFT: {article['slug']} - {post_issues}")
            send_alert(blog_id, article["slug"], post_issues)
            article["_draft"] = True
        elif post_issues:
            logger.info(f"[ETAP] {blog_id} quality: {post_issues}")

        image = fetch_city_image(topic["city"], topic["country"], article["slug"])
        if image:
            article["image"] = image
        # 본문 이미지 삽입
        body_imgs = fetch_body_images(topic.get("city", ""), topic.get("country", ""), article["slug"], count=3)
        if body_imgs:
            article["body_images"] = body_imgs
        _write_hugo_post(cfg, article)

        mark_published(
            topic_id=topic["topic_id"],
            blog_id=blog_id,
            title=article["title"],
            slug=article["slug"],
            url=""
        )
        results.append({"title": article["title"], "city": article["city"]})

        if i < count - 1:
            time.sleep(5)

    if results:
        deployed = _build_and_deploy(cfg)
        if deployed:
            print(f"[ETAP] {blog_id}: {len(results)}건 발행 + 배포 완료")
        else:
            print(f"[ETAP] {blog_id}: {len(results)}건 발행, 배포 실패")

    return results

if __name__ == "__main__":
    test_cfg = {
        "id": "tour-hugo",
        "domain": "tour.techpawz.com",
        "site_path": "/Users/twinssn/Projects/ETAP/tour-hugo",
        "cf_project": "tour-hugo",
    }
    result = run(test_cfg)
    print(result)


# ─── dispatcher 경유 진입점 ───────────────────────────────────────────────────
_BLOG_PIPELINE_MAP = {
    "tour-hugo":        ("pipelines.etap.pipeline",            "run_batch"),
    "airlines-hugo":    ("pipelines.etap.airlines_pipeline",   "run_batch"),
    "airports-hugo":    ("pipelines.etap.airports_pipeline",   "run_batch"),
    "esim-hugo":        ("pipelines.etap.esim_pipeline",       "run_batch"),
    "flights-hugo":     ("pipelines.etap.flight_pipeline",     "run_batch"),
    "michelin-hugo":    ("pipelines.etap.michelin_pipeline",   "run_batch"),
    "tours-hugo":       ("pipelines.etap.tours_pipeline",      "run_batch"),
    "trains-hugo":      ("pipelines.etap.trains_pipeline",     "run_batch"),
    "visa-hugo":        ("pipelines.etap.visa_pipeline",       "run_batch"),
    "bus-hugo":         ("pipelines.etap.bus_pipeline",        "run_batch"),
    "ferry-hugo":       ("pipelines.etap.ferry_pipeline",      "run_batch"),
    "dining-hugo":      ("pipelines.etap.dining_pipeline",     "run_batch"),
    "culture-hugo":     ("pipelines.etap.culture_pipeline",    "run_batch"),
    "transfers-hugo":   ("pipelines.etap.transfers_pipeline",  "run_batch"),
    "multiday-hugo":    ("pipelines.etap.multiday_pipeline",   "run_batch"),
    "nature-hugo":      ("pipelines.etap.nature_pipeline",     "run_batch"),
    "visafree-hugo":    ("pipelines.etap.visafree_pipeline",   "run_batch"),
    "deals-hugo":       ("pipelines.etap.deals_pipeline",      "run_batch"),
    "eurail-hugo":      ("pipelines.etap.eurail_pipeline",     "run_batch"),
    "cruise-hugo":      ("pipelines.etap.cruise_pipeline",     "run_batch"),
    "phototour-hugo":   ("pipelines.etap.phototour_pipeline",  "run_batch"),
    "daytrips-hugo":    ("pipelines.etap.daytrips_pipeline",   "run_batch"),
    "walking-hugo":     ("pipelines.etap.walking_pipeline",    "run_batch"),
    "foodtour-hugo":    ("pipelines.etap.foodtour_pipeline",   "run_batch"),
    "adventure-hugo":   ("pipelines.etap.adventure_pipeline",  "run_batch"),
    "watersports-hugo": ("pipelines.etap.watersports_pipeline","run_batch"),
}

def run(cfg: dict) -> dict:
    import importlib
    blog_id = cfg.get("id", "")
    count   = cfg.get("count", 1)

    entry = _BLOG_PIPELINE_MAP.get(blog_id)
    if not entry:
        logger.error(f"[ETAP] 알 수 없는 blog_id: {blog_id}")
        return {"success": False, "reason": "unknown_blog_id"}

    module_path, func_name = entry
    try:
        mod = importlib.import_module(module_path)
        fn  = getattr(mod, func_name)
        if blog_id == "tour-hugo":
            result = fn(cfg, count=count)
        else:
            result = fn(count=count)
        ok = result if isinstance(result, int) else (1 if result else 0)
        return {"success": ok > 0, "published": ok}
    except Exception as e:
        logger.error(f"[ETAP] {blog_id} 실패: {e}")
        return {"success": False, "reason": str(e)}
