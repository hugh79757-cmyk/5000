"""WordPress 발행기 (5000용)"""

import logging
import requests
import base64
from typing import Optional

logger = logging.getLogger(__name__)


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

    if categories:
        post_data["categories"] = categories if isinstance(categories, list) else [categories]
    if tags:
        post_data["tags"] = tags if isinstance(tags, list) else [tags]

    try:
        resp = requests.post(api_url, json=post_data, headers=headers, timeout=30)
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
