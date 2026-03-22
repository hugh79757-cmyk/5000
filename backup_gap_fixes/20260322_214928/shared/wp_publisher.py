"""WordPress 발행기 (5000용)"""

import logging
import requests
import base64
import tempfile
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _upload_featured_image(wp_url, headers, image_url, title):
    """외부 이미지 URL을 WP 미디어로 업로드하고 media_id 반환"""
    try:
        img_resp = requests.get(image_url, timeout=15)
        if img_resp.status_code != 200:
            logger.warning(f"Featured image download failed: {img_resp.status_code}")
            return None

        content_type = img_resp.headers.get("Content-Type", "image/webp")
        ext = "webp" if "webp" in content_type else "jpg"
        import hashlib, time
        hash_id = hashlib.md5(f"{title}{time.time()}".encode()).hexdigest()[:10]
        filename = f"gap-{hash_id}.{ext}"

        media_url = wp_url.rstrip("/") + "/wp-json/wp/v2/media"
        media_headers = {
            "Authorization": headers["Authorization"],
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": content_type,
        }

        media_resp = requests.post(
            media_url, headers=media_headers,
            data=img_resp.content, timeout=30, verify=False
        )

        if media_resp.status_code in (200, 201):
            media_id = media_resp.json().get("id")
            logger.info(f"WP media uploaded: id={media_id}")
            return media_id
        else:
            logger.warning(f"WP media upload failed: {media_resp.status_code} {media_resp.text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"WP media upload error: {e}")
        return None


def publish_to_wordpress(wp_url, wp_user, wp_pass, title, body_html, categories=None, tags=None, featured_image_url=None):
    api_url = wp_url.rstrip("/") + "/wp-json/wp/v2/posts"
    token = base64.b64encode(f"{wp_user}:{wp_pass}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }

    post_data = {
        "title": title,
        "content": body_html,
        "status": "publish",
    }

    # featured image 업로드
    if featured_image_url:
        media_id = _upload_featured_image(wp_url, headers, featured_image_url, title)
        if media_id:
            post_data["featured_media"] = media_id

    if categories:
        post_data["categories"] = categories if isinstance(categories, list) else [categories]
    if tags:
        post_data["tags"] = tags if isinstance(tags, list) else [tags]

    try:
        resp = requests.post(api_url, json=post_data, headers=headers, timeout=30, verify=False)
        if resp.status_code in (200, 201):
            data = resp.json()
            url = data.get("link", "")
            post_id = data.get("id", "")
            logger.info(f"WP published: {title} -> {url}")
            return {"success": True, "url": url, "post_id": post_id}
        else:
            logger.error(f"WP publish failed: {resp.status_code} {resp.text[:200]}")
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        logger.error(f"WP publish error: {e}")
        return {"success": False, "error": str(e)}
