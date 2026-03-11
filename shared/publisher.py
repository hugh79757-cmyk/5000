import os
import re
import yaml
import markdown
import requests
import frontmatter
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv
from shared.content_store import insert_article, update_published, get_today_count

load_dotenv()

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
SCOPES = ["https://www.googleapis.com/auth/blogger"]


def load_blogs():
    with open(os.path.join(CONFIG_DIR, "blogs.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["blogs"]


def load_api_keys():
    path = os.path.join(CONFIG_DIR, "api_keys.yaml")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def get_blog_config(blog_id):
    blogs = load_blogs()
    for b in blogs:
        if b["id"] == blog_id:
            return b
    raise ValueError("Blog not found: " + blog_id)


def get_blogger_service():
    keys = load_api_keys()
    blogger_cfg = keys.get("blogger", {})
    token_path = blogger_cfg.get("token_path", "")
    client_secret_path = blogger_cfg.get("client_secret_path", "")

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("blogger", "v3", credentials=creds)


def slugify(text):
    text = re.sub(r"[^\w\s가-힣-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text.lower()[:80]


def publish(blog_id, title, body_md, body_html=None,
            category="", tags="", thumbnail_url="",
            data_source="", source_id="", prompt_id="",
            model=""):

    blog_cfg = get_blog_config(blog_id)

    today_count = get_today_count(blog_id)
    if today_count >= blog_cfg.get("daily_quota", 15):
        return {"success": False, "reason": "daily_quota_exceeded", "count": today_count}

    if not body_html:
        body_html = markdown.markdown(body_md, extensions=["tables", "fenced_code"])

    slug = slugify(title)

    article = {
        "blog_id": blog_id,
        "title": title,
        "slug": slug,
        "body_md": body_md,
        "body_html": body_html,
        "thumbnail_url": thumbnail_url,
        "category": category,
        "tags": tags,
        "data_source": data_source,
        "source_id": source_id,
        "prompt_id": prompt_id,
        "model": model,
        "platform": blog_cfg["platform"],
        "status": "pending",
        "published_url": "",
        "published_at": "",
    }
    article_id = insert_article(article)

    platform = blog_cfg["platform"]

    if platform == "blogger":
        result = _publish_blogger(blog_cfg, title, body_html, tags)
    elif platform == "hugo":
        result = _publish_hugo(blog_cfg, title, body_md, slug, category, tags, thumbnail_url)
    elif platform == "wordpress":
        result = _publish_wordpress(blog_cfg, title, body_html, category, tags)
    else:
        result = {"success": False, "reason": "unsupported_platform: " + platform}

    if result.get("success"):
        update_published(article_id, result.get("url", ""))

    result["article_id"] = article_id
    return result


def _publish_blogger(blog_cfg, title, body_html, tags):
    service = get_blogger_service()
    labels = [t.strip() for t in tags.split(",") if t.strip()]
    post_body = {"kind": "blogger#post", "title": title, "content": body_html}
    if labels:
        post_body["labels"] = labels

    resp = service.posts().insert(blogId=blog_cfg["blog_id"], body=post_body, isDraft=False).execute()
    return {"success": True, "url": resp.get("url", ""), "post_id": resp.get("id", "")}


def _publish_hugo(blog_cfg, title, body_md, slug, category, tags, thumbnail_url):
    repo_name = blog_cfg.get("repo", "")
    repo_path = os.path.join("/Users/twinssn/Projects", repo_name)
    content_dir = os.path.join(repo_path, "content", "posts")
    os.makedirs(content_dir, exist_ok=True)

    post = frontmatter.Post(body_md)
    post["title"] = title
    post["slug"] = slug
    post["date"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    post["draft"] = False
    if category:
        post["categories"] = [category]
    if tags:
        post["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if thumbnail_url:
        post["image"] = thumbnail_url

    file_path = os.path.join(content_dir, slug + ".md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))

    expected_url = "https://" + blog_cfg.get("domain", "") + "/posts/" + slug + "/"
    return {"success": True, "url": expected_url, "file_path": file_path}


def _publish_wordpress(blog_cfg, title, body_html, category, tags):
    keys = load_api_keys()
    wp_configs = keys.get("wordpress", {})
    wp_key = blog_cfg["id"].replace("-wp", "").replace("-", "_")
    wp_cfg = None
    for k, v in wp_configs.items():
        if k == wp_key or v.get("url", "") == blog_cfg.get("url", ""):
            wp_cfg = v
            break

    if not wp_cfg:
        return {"success": False, "reason": "wp_config_not_found"}

    api_url = wp_cfg["url"] + "/wp-json/wp/v2/posts"
    data = {
        "title": title,
        "content": body_html,
        "status": "publish",
    }
    resp = requests.post(api_url, json=data,
                         auth=(wp_cfg["username"], wp_cfg["app_password"]))

    if resp.status_code in (200, 201):
        result = resp.json()
        return {"success": True, "url": result.get("link", ""), "post_id": str(result.get("id", ""))}
    return {"success": False, "reason": resp.text}
