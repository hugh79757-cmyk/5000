"""시니어 복지 파이프라인 — fetch → write → publish"""

import os
import re
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

logger = logging.getLogger(__name__)

_topic_index = {}


# ─── 헬퍼 함수 ───

def _get_published_titles(site_path):
    """이미 발행된 제목 목록 조회"""
    try:
        import glob as _glob
        posts_dir = os.path.join(site_path, "content", "posts")
        published = set()
        for md in _glob.glob(os.path.join(posts_dir, "*/index.md")):
            with open(md, encoding="utf-8") as f:
                content = f.read()
            m = re.search(r'^title:\s*["\'](.+?)["\']', content, re.MULTILINE)
            if m:
                published.add(m.group(1).strip())
        return published
    except Exception:
        return set()


def _pick_topic(blog_id, services):
    """카테고리 순환 선택"""
    available = list(set(s["category"] for s in services))
    if not available:
        return "생활지원"
    idx = _topic_index.get(blog_id, 0)
    topic = available[idx % len(available)]
    _topic_index[blog_id] = idx + 1
    return topic


def _make_thumbnail(cfg, article, topic_type, platform):
    """썸네일 생성 — Hugo: 로컬 feature.webp, Blogger: R2 업로드 URL"""
    try:
        from pipelines.senior.thumbnail import generate_senior_thumbnail

        if platform == "hugo":
            site_path = cfg.get("site_path", "")
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
            logger.info(f"[SeniorThumb] saved: {thumb_path}")
            return "feature.webp"
        else:
            import tempfile
            import hashlib
            from shared.r2_uploader import upload_file
            from datetime import datetime
            thumb_path = os.path.join(tempfile.gettempdir(), f"senior_thumb_{cfg.get('id','')}.webp")
            generate_senior_thumbnail(
                title=article["title"],
                category=article.get("category", topic_type),
                department=article.get("department", ""),
                output_path=thumb_path,
            )
            if os.path.exists(thumb_path):
                title_hash = hashlib.md5(article["title"].encode()).hexdigest()[:10]
                r2_key = f"senior-thumbnails/{datetime.now().strftime('%Y%m%d')}-{title_hash}.webp"
                url = upload_file(thumb_path, r2_key, content_type="image/webp")
                os.remove(thumb_path)
                logger.info(f"[SeniorThumb] R2: {url}")
                return url
    except Exception as e:
        logger.warning(f"Thumbnail failed: {e}")
    return ""


def _prepare_tags(article, topic_type):
    """tags를 문자열로 정규화"""
    raw = article.get("tags", [])
    if isinstance(raw, list):
        tags = ", ".join(str(t).strip() for t in raw if str(t).strip())
    else:
        tags = str(raw)
    if "시니어복지" not in tags:
        tags = tags + ", 시니어복지" if tags else "시니어복지"
    return tags


def _convert_md_to_blogger_html(body_md):
    """마크다운을 Blogger용 HTML로 변환 (shortcode 처리 포함)"""
    import markdown

    # Hugo shortcode → HTML 버튼
    body_md = re.sub(
        r'\{\{<\s*btn\s+url="([^"]*)"\s+text="([^"]*)"\s*>\}\}',
        r'<div style="text-align:center;margin:20px 0"><a href="\1" target="_blank" '
        r'rel="noopener" style="display:inline-block;padding:14px 28px;background:#2563eb;'
        r'color:#fff;border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px">\2</a></div>',
        body_md
    )
    # 쿠팡 마크다운 링크 → HTML
    body_md = re.sub(
        r'- \[([^\]]*)\]\((https://link\.coupang\.com[^)]+)\)',
        r'<div style="margin:8px 0"><a href="\2" target="_blank" rel="noopener" '
        r'style="color:#e74c3c;font-weight:bold">\1</a></div>',
        body_md
    )
    return markdown.markdown(body_md, extensions=["tables", "fenced_code"])


# ─── 메인 run ───

def run(cfg):
    """시니어 파이프라인 진입점 — 통일된 dict 반환"""
    blog_id = cfg.get("id", "senior-hugo")
    platform = cfg.get("platform", "hugo")
    site_path = cfg.get("site_path", "")
    logger.info(f"Senior pipeline: {blog_id} (platform: {platform})")

    # 1. Quota check
    try:
        from shared.content_store import get_today_count
        today_count = get_today_count(blog_id)
        daily_quota = cfg.get("daily_quota", 5)
        if today_count >= daily_quota:
            logger.info(f"{blog_id} quota met: {today_count}/{daily_quota}")
            return {"success": False, "reason": "quota_met"}
    except Exception as e:
        logger.warning(f"Quota check failed (continue): {e}")

    # 2. Fetch data
    try:
        from pipelines.senior.fetcher import fetch_all
        data = fetch_all()
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return {"success": False, "reason": "fetch_error"}

    if not data.get("services"):
        logger.warning("No senior services data")
        return {"success": False, "reason": "no_data"}

    # 3. Pick topic + enrich
    topic_type = _pick_topic(blog_id, data["services"])
    logger.info(f"Topic selected: {topic_type}")

    try:
        from pipelines.senior.fetcher import enrich_service_detail
        from pipelines.senior.writer import _select_service
        published = _get_published_titles(site_path) if site_path else set()
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
        return {"success": False, "reason": "write_error"}

    if not article:
        return {"success": False, "reason": "no_content"}

    # 5. Thumbnail
    thumb_url = _make_thumbnail(cfg, article, topic_type, platform)

    # 6. Tags
    tags = _prepare_tags(article, topic_type)

    # 7. Publish
    if platform == "hugo":
        return _do_publish_hugo(cfg, blog_id, article, tags, thumb_url)
    elif platform == "blogger":
        return _do_publish_blogger(cfg, blog_id, article, tags, thumb_url)
    else:
        logger.error(f"Unknown platform: {platform}")
        return {"success": False, "reason": "config_error"}


# ─── 발행 함수 (각각 하나의 작업만) ───

def _do_publish_hugo(cfg, blog_id, article, tags, thumb_url):
    """Hugo 발행 — shared.publisher에 위임"""
    try:
        from shared.publisher import publish
        result = publish(
            blog_id=blog_id,
            title=article["title"],
            body_md=article["body_md"],
            category=article.get("category", ""),
            tags=tags,
            thumbnail_url=thumb_url,
        )
        if result and result.get("success"):
            logger.info(f"Hugo published: {article['title']} -> {result.get('url')}")
            return result
        else:
            logger.error(f"Hugo publish failed: {result}")
            return {"success": False, "reason": "publish_error"}
    except Exception as e:
        logger.error(f"Hugo publish error: {e}")
        return {"success": False, "reason": "publish_error"}


def _do_publish_blogger(cfg, blog_id, article, tags, thumb_url):
    """Blogger 발행 — shared.blogger_publisher + content_store에 위임"""
    try:
        from shared.blogger_publisher import publish_to_blogger
        from shared.content_store import insert_article

        target_blog_id = cfg.get("blogger_blog_id", "")
        if not target_blog_id:
            blog_id_env = cfg.get("blog_id_env", "")
            target_blog_id = os.environ.get(blog_id_env, "") if blog_id_env else ""
        if not target_blog_id:
            logger.error(f"blogger_blog_id not set for {blog_id}")
            return {"success": False, "reason": "config_error"}

        body_html = _convert_md_to_blogger_html(article["body_md"])

        if thumb_url:
            thumb_html = (
                f'<div style="text-align:center;margin-bottom:20px">'
                f'<img src="{thumb_url}" alt="{article["title"]}" '
                f'style="max-width:100%;border-radius:12px" /></div>'
            )
            body_html = thumb_html + body_html

        labels = [t.strip() for t in tags.split(",") if t.strip()]

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
                insert_article({
                    "blog_id": blog_id,
                    "title": article["title"],
                    "slug": article["title"].replace(" ", "-")[:80],
                    "body_md": article["body_md"],
                    "body_html": body_html,
                    "thumbnail_url": thumb_url,
                    "category": article.get("category", ""),
                    "tags": tags,
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
            return {"success": True, "url": pub_url, "title": article["title"]}
        else:
            err = result.get("error", "unknown") if result else "no result"
            logger.error(f"Blogger publish failed: {err}")
            return {"success": False, "reason": "publish_error"}
    except Exception as e:
        logger.error(f"Blogger publish error: {e}")
        return {"success": False, "reason": "publish_error"}
