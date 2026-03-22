"""시니어 복지 파이프라인 — fetch → write → publish (Hugo / Blogger)"""

import os
import re
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

logger = logging.getLogger(__name__)

_topic_index = {}


def _get_published_services(blog_id):
    """이미 발행된 서비스명 목록 조회"""
    try:
        import glob as _glob
        site_path = "/Users/twinssn/Projects/senior-hugo/content/posts"
        published = set()
        for md in _glob.glob(os.path.join(site_path, "*/index.md")):
            with open(md, encoding="utf-8") as f:
                content = f.read()
            m = re.search(r'^title:\s*["\'](.*?)["\']', content, re.MULTILINE)
            if m:
                published.add(m.group(1).strip())
        return published
    except Exception:
        return set()


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

    # 3.5 Enrich: 선택될 서비스 후보의 상세 데이터 보강
    try:
        from pipelines.senior.fetcher import enrich_service_detail
        from pipelines.senior.writer import _select_service
        published = _get_published_services(blog_id)
        candidate = _select_service(data["services"], topic_type, published=published)
        if candidate and not candidate.get("support_content"):
            candidate = enrich_service_detail(candidate)
            logger.info(f"Enriched: {candidate.get('service_name')}")
    except Exception as e:
        logger.warning(f"Enrich skipped: {e}")

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
        # 썸네일 로컬 생성 → post 디렉터리에 저장
        thumb_url = ""
        try:
            from pipelines.senior.thumbnail import generate_senior_thumbnail
            import tempfile
            site_path = cfg.get("site_path", "/Users/twinssn/Projects/senior-hugo")
            slug = re.sub(r'[^가-힣a-zA-Z0-9\s-]', '', article["title"]).replace(" ", "-")[:80]
            post_dir = os.path.join(site_path, "content", "posts", slug)
            os.makedirs(post_dir, exist_ok=True)
            thumb_path = os.path.join(post_dir, "feature.webp")
            generate_senior_thumbnail(
                title=article["title"],
                category=article.get("category", topic_type),
                department=article.get("department", ""),
                output_path=thumb_path,
            )
            thumb_url = "feature.webp"
            logger.info(f"Hugo thumbnail: {thumb_path}")
        except Exception as te:
            logger.warning(f"Hugo thumbnail failed: {te}")

        from shared.publisher import publish
        result = publish(
            blog_id=blog_id,
            title=article["title"],
            body_md=article["body_md"],
            category=article.get("category", topic_type),
            tags=", ".join(article["tags"]) if isinstance(article.get("tags"), list) else article.get("tags", ""),
            thumbnail_url=thumb_url,
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
        import os
        import markdown
        from shared.blogger_publisher import publish_to_blogger

        # --- blog ID ---
        blog_id_env = cfg.get("blog_id_env", "")
        target_blog_id = cfg.get("blogger_blog_id", "")
        if not target_blog_id and blog_id_env:
            target_blog_id = os.environ.get(blog_id_env, "")
        if not target_blog_id:
            logger.error(f"blogger_blog_id not set for {blog_id}")
            return "config_error"

        # --- MD → HTML 변환 ---
        body_md = article["body_md"]

        # Hugo shortcode → HTML 변환
        import re
        # {{< btn url="..." text="..." >}} → HTML 버튼
        body_md = re.sub(
            r'\{\{<\s*btn\s+url="([^"]*)"\s+text="([^"]*)"\s*>\}\}',
            r'<div style="text-align:center;margin:20px 0"><a href="\1" target="_blank" rel="noopener" style="display:inline-block;padding:14px 28px;background:#2563eb;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px">\2</a></div>',
            body_md
        )

        # 쿠팡 마크다운 링크 → HTML 스타일 링크
        body_md = re.sub(
            r'- \[([^\]]*)\]\((https://link\.coupang\.com[^)]+)\)',
            r'<div style="margin:8px 0"><a href="\2" target="_blank" rel="noopener" style="color:#e74c3c;font-weight:bold">\1</a></div>',
            body_md
        )

        body_html = markdown.markdown(body_md, extensions=["tables", "fenced_code"])

        # --- 썸네일 생성 ---
        thumb_url = ""
        try:
            from pipelines.senior.thumbnail import generate_senior_thumbnail
            from shared.r2_uploader import upload_file
            import tempfile, hashlib
            thumb_path = os.path.join(tempfile.gettempdir(), f"senior_thumb_{blog_id}.webp")
            generate_senior_thumbnail(
                title=article["title"],
                category=article.get("category", topic_type),
                department=article.get("department", ""),
                output_path=thumb_path,
            )
            if os.path.exists(thumb_path):
                from datetime import datetime
                title_hash = hashlib.md5(article["title"].encode()).hexdigest()[:10]
                r2_key = f"senior-thumbnails/{datetime.now().strftime('%Y%m%d')}-{title_hash}.webp"
                thumb_url = upload_file(thumb_path, r2_key, content_type="image/webp")
                os.remove(thumb_path)
                logger.info(f"Thumbnail uploaded: {thumb_url}")
        except Exception as te:
            logger.warning(f"Thumbnail failed: {te}")

        # --- labels ---
        raw_tags = article.get("tags", [])
        if isinstance(raw_tags, str):
            labels = [t.strip() for t in raw_tags.split(",") if t.strip()]
        else:
            labels = [str(t).strip() for t in raw_tags if str(t).strip()]
        labels.append("시니어복지")

        # --- 썸네일을 본문 상단에 삽입 ---
        if thumb_url:
            thumb_html = f'<div style="text-align:center;margin-bottom:20px"><img src="{thumb_url}" alt="{article["title"]}" style="max-width:100%;border-radius:12px" /></div>'
            body_html = thumb_html + body_html

        # --- 발행 ---
        result = publish_to_blogger(
            blog_id=target_blog_id,
            title=article["title"],
            body_html=body_html,
            labels=labels,
        )

        if result and result.get("success"):
            pub_url = result.get("url", "")
            logger.info(f"Blogger published: {article['title']} -> {pub_url}")
            try:
                from shared.content_store import insert_article
                tags_val = article.get("tags", [])
                if isinstance(tags_val, list):
                    tags_val = ", ".join(tags_val)
                insert_article({
                    "blog_id": blog_id,
                    "title": article["title"],
                    "slug": article["title"].replace(" ", "-")[:80],
                    "body_md": article["body_md"],
                    "body_html": body_html,
                    "thumbnail_url": thumb_url,
                    "category": article.get("category", topic_type),
                    "tags": tags_val,
                    "data_source": "gov24_api",
                    "source_id": article.get("service_id", ""),
                    "prompt_id": "",
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "published_url": pub_url,
                    "published_at": "",
                    "platform": "blogger",
                    "status": "published",
                })
            except Exception as e:
                logger.warning(f"Save article record failed: {e}")
            return True
        else:
            err = result.get("error", "unknown") if result else "no result"
            logger.error(f"Blogger publish failed: {err}")
            return "publish_error"
    except Exception as e:
        logger.error(f"Blogger publish error: {e}")
        return "publish_error"

