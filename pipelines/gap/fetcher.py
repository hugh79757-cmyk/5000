import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search"


def _headers():
    return {
        "X-Naver-Client-Id": os.getenv("NAVER_CLIENT_ID", ""),
        "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET", ""),
    }


def search_web(keyword, display=10):
    try:
        r = requests.get(
            f"{NAVER_SEARCH_URL}/webkr.json",
            headers=_headers(),
            params={"query": keyword, "display": display, "sort": "date"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        logger.exception(f"네이버 웹 검색 실패 [{keyword}]: {e}")
        return []


def search_blog(keyword, display=10):
    try:
        r = requests.get(
            f"{NAVER_SEARCH_URL}/blog.json",
            headers=_headers(),
            params={"query": keyword, "display": display, "sort": "date"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        logger.exception(f"네이버 블로그 검색 실패 [{keyword}]: {e}")
        return []


def search_news(keyword, display=10):
    try:
        r = requests.get(
            f"{NAVER_SEARCH_URL}/news.json",
            headers=_headers(),
            params={"query": keyword, "display": display, "sort": "date"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        logger.exception(f"네이버 뉴스 검색 실패 [{keyword}]: {e}")
        return []


def search_image(keyword, display=5):
    try:
        r = requests.get(
            f"{NAVER_SEARCH_URL}/image",
            headers=_headers(),
            params={"query": keyword, "display": display, "sort": "sim", "filter": "large"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        logger.exception(f"네이버 이미지 검색 실패 [{keyword}]: {e}")
        return []


def fetch_keyword_data(keyword):
    web = search_web(keyword, display=5)
    blog = search_blog(keyword, display=5)
    news = search_news(keyword, display=5)
    return {
        "keyword": keyword,
        "fetched_at": datetime.now().isoformat(),
        "web": web,
        "blog": blog,
        "news": news,
        "total_sources": len(web) + len(blog) + len(news),
    }
