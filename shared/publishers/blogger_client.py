"""
Blogger API v3 클라이언트

OAuth2 인증 필요:
  1. Google Cloud Console → 프로젝트 생성
  2. Blogger API 활성화
  3. OAuth2 클라이언트 ID 발급 (Desktop app type)
  4. credentials.json 다운로드 → config/blogger_credentials.json 저장
  5. 최초 실행 시 브라우저 인증 → token.pickle 자동 생성

사용법:
  client = BloggerClient()
  url = client.publish_post(blog_id, "title", "<html>", labels=["tag1"])
"""

import os
import pickle
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/blogger"]

# Token 캐싱 경로
DEFAULT_CREDENTIALS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "blogger_credentials.json"
)
DEFAULT_TOKEN_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "blogger_token.pickle"
)


class BloggerClient:
    def __init__(
        self,
        credentials_path: str = None,
        token_path: str = None,
    ):
        self.credentials_path = credentials_path or str(
            Path(DEFAULT_CREDENTIALS_PATH).resolve()
        )
        self.token_path = token_path or str(Path(DEFAULT_TOKEN_PATH).resolve())
        self.service = self._get_service()

    def _get_service(self):
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        if os.path.exists(self.token_path):
            with open(self.token_path, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Blogger credentials not found at {self.credentials_path}. "
                        "Create a Google Cloud OAuth2 Desktop client ID, "
                        "download credentials.json, and save it there."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "wb") as f:
                pickle.dump(creds, f)

        return build("blogger", "v3", credentials=creds)

    def publish_post(
        self,
        blog_id: str,
        title: str,
        html_content: str,
        labels: list = None,
        is_draft: bool = False,
    ) -> str:
        """Blogger에 포스트 발행. 발행된 public URL 반환."""
        body = {
            "kind": "blogger#post",
            "title": title,
            "content": html_content,
            "labels": labels or [],
        }
        request = self.service.posts().insert(
            blogId=blog_id, body=body, isDraft=is_draft
        )
        result = request.execute()
        return result.get("url", "")

    def update_post(self, blog_id: str, post_id: str, html_content: str):
        """기존 포스트 본문 업데이트 (카드 주입용)."""
        body = {
            "kind": "blogger#post",
            "content": html_content,
        }
        request = self.service.posts().patch(
            blogId=blog_id, postId=post_id, body=body
        )
        request.execute()

    def get_post_by_url(self, blog_id: str, url: str) -> dict | None:
        """URL로 post_id 조회. posts.list 검색 후 URL 매칭."""
        request = self.service.posts().list(blogId=blog_id, maxResults=50)
        while request:
            result = request.execute()
            for post in result.get("items", []):
                if post.get("url") == url:
                    return post
            request = self.service.posts().list_next(request, result)
        return None


if __name__ == "__main__":
    import sys

    blog_id = sys.argv[1] if len(sys.argv) > 1 else input("Blogger blog ID: ")
    title = sys.argv[2] if len(sys.argv) > 2 else "Test Post"
    html = "<p>Hello from mc BloggerClient</p>"
    client = BloggerClient()
    url = client.publish_post(blog_id, title, html, is_draft=True)
    print(f"Draft saved: {url}")
