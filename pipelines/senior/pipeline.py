"""시니어 복지 파이프라인 — fetch → write → publish (Hugo / Blogger)"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

logger = logging.getLogger(__name__)

_topic_index = {}


def _pick_topic(blog_id, services):
    available = list(set(s["category"] for s in services))
    if not available:
        return "생활지원"
    idx = _topic_index.get(blog_id, 0)
    topic = available[idx % len(available)]
    _topic_index[blog_id] = idx + 1
    return topic


def run(cfg):
    blog_id = cfg.get("id", "senior-hugo")
    platform = cfg.get("platform", "hugo")
    logger.info(f"Senior pipeline: {blog_id} (platform: {platform})")

    # 1. Quota check
    try:
        from shared.content_store import get_today_count
        today_count = get_today_count(blog_id)
        daily_quota = cfg.get("daily_quota", 5)
        if today_count >= daily_quota:
            logger.info(f"{blog_id} quota met: {today_count}/{daily_quota}")
            return "quota_met"
    except Exception as e:
        logger.warning(f"Quota check failed (continue): {e}")

    # 2. Fetch data
    try:
        from pipelines.senior.fetcher import fetch_all
        data = fetch_all()
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return "fetch_error"

    if not data.get("services"):
        logger.warning("No senior services data")
        return "no_data"

    # 3. Pick topic
    topic_type = _pick_topic(blog_id, data["services"])
    logger.info(f"Topic selected: {topic_type}")

    # 4. Generate article
    try:
        from pipelines.senior.writer import generate_senior_article
        article = generate_senior_article(data, topic_type=topic_type)
    except Exception as e:
        logger.error(f"Writer failed: {e}")
        return "write_error"

    if not article:
        return "no_content"

    # 5. Publish — Hugo or Blogger
    if platform == "hugo":
        return _publish_hugo(cfg, blog_id, article, topic_type)
    elif platform == "blogger":
        return _publish_blogger(cfg, blog_id, article, topic_type)
    else:
        logger.error(f"Unknown platform: {platform}")
        return "config_error"


def _publish_hugo(cfg, blog_id, article, topic_type):
    try:
        from shared.publisher import publish
        result = publish(
            blog_id=blog_id,
            title=article["title"],
            body_md=article["body_md"],
            category=article.get("category", topic_type),
            tags=article.get("tags", ""),
            thumbnail_url=article.get("thumbnail", ""),
        )
        if result and result.get("success"):
            logger.info(f"Hugo published: {article['title']} -> {result.get('url')}")
            return result
        else:
            logger.error(f"Hugo publish failed: {result}")
            return "publish_error"
    except Exception as e:
        logger.error(f"Hugo publish error: {e}")
        return "publish_error"


def _publish_blogger(cfg, blog_id, article, topic_type):
    try:
        from shared.blogger_publisher import publish_to_blogger

        target_blog_id = cfg.get("blogger_blog_id", "")
        if not target_blog_id:
            logger.error(f"blogger_blog_id not set for {blog_id}")
            return "config_error"

        labels = [t.strip() for t in article.get("tags", "").split(",") if t.strip()]
        labels.append("시니어복지")

        result = publish_to_blogger(
            blog_id=target_blog_id,
            title=article["title"],
            body_html=article["body_md"],
            labels=labels,
        )

        if result:
            logger.info(f"Blogger published: {article['title']} -> {result}")
            try:
                from shared.content_store import save_article
                save_article(
                    blog_id=blog_id,
                    title=article["title"],
                    slug=article["title"].replace(" ", "-")[:80],
                    body=article["body_md"],
                    category=article.get("category", topic_type),
                    tags=article.get("tags", ""),
                    source="gov24_api",
                    keyword=topic_type,
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    published_url=str(result),
                    platform="blogger",
                )
            except Exception as e:
                logger.warning(f"Save article record failed: {e}")
            return True
        else:
            logger.error("Blogger publish returned None")
            return "publish_error"
    except Exception as e:
        logger.error(f"Blogger publish error: {e}")
        return "publish_error"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    cfg = {
        "id": "senior-hugo",
        "platform": "hugo",
        "daily_quota": 5,
        "site_path": "/Users/twinssn/Projects/senior-hugo",
        "theme": "blowfish",
        "cf_project": "senior-hugo",
        "domain": "senior.informationhot.kr",
    }
    result = run(cfg)
    print(f"\nResult: {result}")
