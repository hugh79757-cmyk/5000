"""Blogger 발행기 (5000용)"""

import logging
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/blogger"]
BASE_DIR = Path(__file__).parent.parent
TOKEN_PATH = BASE_DIR / "blogger_token.pickle"
CREDENTIALS_PATH = BASE_DIR / "credentials.json"


def _get_credentials():
    creds = None
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif CREDENTIALS_PATH.exists():
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        else:
            logger.error("credentials.json not found")
            return None
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return creds


def publish_to_blogger(blog_id, title, body_html, labels=None):
    creds = _get_credentials()
    if not creds:
        return {"success": False, "error": "credentials failed"}

    try:
        service = build("blogger", "v3", credentials=creds)
        post_body = {
            "kind": "blogger#post",
            "title": title,
            "content": body_html,
        }
        if labels:
            post_body["labels"] = labels if isinstance(labels, list) else [labels]

        result = service.posts().insert(blogId=blog_id, body=post_body, isDraft=False).execute()
        url = result.get("url", "")
        post_id = result.get("id", "")
        logger.info(f"Blogger published: {title} -> {url}")
        return {"success": True, "url": url, "post_id": post_id}
    except Exception as e:
        logger.exception(f"Blogger publish failed: {e}")
        return {"success": False, "error": str(e)}
