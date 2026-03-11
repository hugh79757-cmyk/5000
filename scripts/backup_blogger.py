import os
import sys
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from markdownify import markdownify as html_to_md
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build as google_build
from shared.content_store import init_db, insert_article, article_exists

BLOG_ID = "835513737064071192"
HUB_BLOG_ID = "travel-blogger"
SCOPES = ["https://www.googleapis.com/auth/blogger"]
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def get_blogger_service():
    token_path = os.path.join(CONFIG_DIR, "blogger_token.json")
    client_secret_path = os.path.join(CONFIG_DIR, "client_secret_hugh7973.json")

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

    return google_build("blogger", "v3", credentials=creds)


def slugify(text):
    text = re.sub(r"[^\w\s가-힣-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text.lower()[:80]


def extract_thumbnail(html):
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html or "")
    if match:
        return match.group(1)
    return ""


def fetch_all_posts(service):
    all_posts = []
    page_token = None
    while True:
        kwargs = {
            "blogId": BLOG_ID,
            "maxResults": 500,
            "fetchBodies": True,
            "status": "LIVE",
            "view": "ADMIN",
        }
        if page_token:
            kwargs["pageToken"] = page_token

        resp = service.posts().list(**kwargs).execute()
        items = resp.get("items", [])
        all_posts.extend(items)
        print("fetched " + str(len(all_posts)) + " posts so far...")

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return all_posts


def backup():
    init_db()
    service = get_blogger_service()

    print("Fetching all posts from travel.rotcha.kr ...")
    posts = fetch_all_posts(service)
    print("Total posts fetched: " + str(len(posts)))

    inserted = 0
    skipped = 0

    for post in posts:
        url = post.get("url", "")
        if article_exists(url):
            skipped += 1
            continue

        title = post.get("title", "")
        html = post.get("content", "")
        body_md = html_to_md(html, heading_style="ATX", strip=["script", "style"])
        labels = post.get("labels", [])
        published = post.get("published", "")
        thumbnail = extract_thumbnail(html)

        article = {
            "blog_id": HUB_BLOG_ID,
            "title": title,
            "slug": slugify(title),
            "body_md": body_md,
            "body_html": html,
            "thumbnail_url": thumbnail,
            "category": labels[0] if labels else "",
            "tags": ",".join(labels),
            "data_source": "blogger_backup",
            "source_id": post.get("id", ""),
            "prompt_id": "",
            "model": "",
            "published_url": url,
            "published_at": published,
            "platform": "blogger",
            "status": "published",
            "created_at": published if published else datetime.utcnow().isoformat(),
        }

        insert_article(article)
        inserted += 1

    print("Done. inserted=" + str(inserted) + " skipped=" + str(skipped))


if __name__ == "__main__":
    backup()
