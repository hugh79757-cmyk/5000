import os
import sys
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, "/Users/twinssn/Projects/tour-auto-publisher")
os.chdir("/Users/twinssn/Projects/tour-auto-publisher")

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/tour-auto-publisher/.env")
load_dotenv("/Users/twinssn/Projects/5000/.env")

from shared.content_store import init_db, get_today_count, register_images, source_exists, title_similar_exists
from shared.publisher import publish, get_blog_config
from pipelines.travel.fetcher import fetch_camping, fetch_korservice, fetch_korservice_heritage, fetch_wellness, fetch_heritage, fetch_festival, fetch_food, fetch_course, fetch_random
from pipelines.travel.writer import generate_content

logger = logging.getLogger(__name__)

import random

BLOG_FETCH_MAP = {
    "travel-hugo": [
        (fetch_camping, 0.45),
        (fetch_korservice, 0.25),
        (fetch_wellness, 0.15),
        (fetch_heritage, 0.15),
    ],
    "travel1-hugo": [
        (fetch_festival, 1.0),
    ],
    "travel2-hugo": [
        (fetch_heritage, 0.6),
        (fetch_korservice_heritage, 0.4),
    ],
    "travel3-hugo": [
        (fetch_food, 1.0),
    ],
    "travel4-hugo": [
        (fetch_course, 1.0),
    ],
}


def _fetch_for_blog(blog_id):
    fetch_list = BLOG_FETCH_MAP.get(blog_id, [(fetch_random, 1.0)])
    funcs = [f for f, w in fetch_list]
    weights = [w for f, w in fetch_list]

    selected = random.choices(funcs, weights=weights, k=1)[0]
    logger.info(blog_id + " fetcher: " + selected.__name__)

    data = selected()
    if data:
        return data

    for func, _ in fetch_list:
        if func != selected:
            data = func()
            if data:
                return data

    return fetch_random()


def _git_push(blog_id):
    import subprocess
    site_dir = "/Users/twinssn/Projects/" + blog_id
    if not os.path.isdir(site_dir):
        return
    try:
        subprocess.run(["git", "add", "-A"], cwd=site_dir, capture_output=True, timeout=30)
        result = subprocess.run(
            ["git", "commit", "-m", "auto: " + datetime.now().strftime("%Y-%m-%d %H:%M")],
            cwd=site_dir, capture_output=True, text=True, timeout=30
        )
        if "nothing to commit" not in result.stdout:
            subprocess.run(["git", "push", "origin", "main"], cwd=site_dir, capture_output=True, timeout=60)
            logger.info(blog_id + " git pushed")
    except Exception as e:
        logger.error(blog_id + " git push failed: " + str(e))


def _run_single(target_blog_id):
    init_db()
    blog_cfg = get_blog_config(target_blog_id)
    quota = blog_cfg.get("daily_quota", 50)
    current = get_today_count(target_blog_id)

    if current >= quota:
        logger.info(target_blog_id + " quota reached: " + str(current) + "/" + str(quota))
        return None

    data = _fetch_for_blog(target_blog_id)
    if not data:
        logger.error("No data fetched for " + target_blog_id)
        return None

    result = generate_content(data, blog_id=target_blog_id)
    if not result:
        logger.error("Content generation failed for " + target_blog_id)
        return None

    if title_similar_exists(target_blog_id, result["title"]):
        logger.warning(target_blog_id + " similar title exists: " + result["title"][:30])
        return None

    body_md = result.get("body_md", "")
    body_html = result.get("body_html", "")

    pub_result = publish(
        blog_id=target_blog_id,
        title=result["title"],
        body_md=body_md,
        body_html=body_html,
        category=result.get("category", ""),
        tags=",".join(result.get("labels", [])),
        thumbnail_url="",
        data_source=result.get("source_type", ""),
        source_id="",
        prompt_id=result.get("prompt_id", ""),
        model=result.get("model", ""),
    )

    if pub_result and pub_result.get("success"):
        article_id = pub_result.get("article_id")
        if article_id and body_html:
            register_images(article_id, target_blog_id, body_html)
        if article_id and body_md:
            register_images(article_id, target_blog_id, body_md)
        _git_push(target_blog_id)

    logger.info(target_blog_id + " result: " + str(pub_result.get("success", False)) + " " + str(pub_result.get("url", "")))
    return pub_result


def run_once(target_blog_id="travel-blogger"):
    return _run_single(target_blog_id)


def run_hugo(target_blog_id="travel-hugo"):
    return _run_single(target_blog_id)


def run_batch(blogger_count=1, hugo_count=3):
    results = {"blogger": [], "hugo": []}

    for i in range(blogger_count):
        logger.info("blogger " + str(i + 1) + "/" + str(blogger_count))
        r = _run_single("travel-blogger")
        if r:
            results["blogger"].append(r)

    hugo_blogs = ["travel-hugo", "travel1-hugo", "travel2-hugo", "travel3-hugo", "travel4-hugo"]
    per_blog = max(1, hugo_count // len(hugo_blogs))

    for blog_id in hugo_blogs:
        for i in range(per_blog):
            logger.info(blog_id + " " + str(i + 1) + "/" + str(per_blog))
            r = _run_single(blog_id)
            if r:
                results["hugo"].append(r)

    return results


def run_all_hugo(count_per_blog=1):
    results = []
    hugo_blogs = ["travel-hugo", "travel1-hugo", "travel2-hugo", "travel3-hugo", "travel4-hugo"]

    for blog_id in hugo_blogs:
        for i in range(count_per_blog):
            logger.info(blog_id + " " + str(i + 1) + "/" + str(count_per_blog))
            r = _run_single(blog_id)
            if r:
                results.append(r)

    return results
