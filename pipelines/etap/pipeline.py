"""ETAP pipeline — 영문 travel 블로그 자동 발행."""
import os
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from pipelines.etap.topic_manager import pick_topic, mark_published
from pipelines.etap.writer import generate_city_guide
from pipelines.etap.image_fetcher import fetch_city_image


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

    frontmatter = f"""---
title: "{article['title']}"
date: {datetime.now().astimezone().isoformat(timespec='seconds')}
description: "{article['description']}"
{image_block}tags:
{tags_str}
categories:
  - "Travel Guide"
showTableOfContents: true
---

{credit_line}"""
    filepath = post_dir / "index.md"
    filepath.write_text(frontmatter + article["content"], encoding="utf-8")
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

    topic = pick_topic(blog_id)
    if not topic:
        print(f"[ETAP] {blog_id}: 발행 가능한 토픽 없음")
        return {"status": "skip", "reason": "no_topic"}

    print(f"[ETAP] {blog_id}: {topic['city']}, {topic['country']} 글 생성 시작")

    article = generate_city_guide(topic)
    image = fetch_city_image(topic["city"], topic["country"], article["slug"])
    if image:
        article["image"] = image
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
        image = fetch_city_image(topic["city"], topic["country"], article["slug"])
        if image:
            article["image"] = image
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
