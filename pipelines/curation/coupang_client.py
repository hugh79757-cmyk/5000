"""Coupang Partners API client — HMAC auth + rate-limited request wrappers.

Every API function takes a RateLimiter and calls limiter.wait_if_needed()
as its FIRST statement. Credentials come from env only (never hardcoded):
    COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY
"""

import hashlib
import hmac
import os
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

BASE_URL = "https://api-gateway.coupang.com"
TIMEOUT = 10


def generate_hmac(method: str, url_path: str, secret_key: str, access_key: str,
                  query_string: str = "") -> dict:
    """CEA HmacSHA256 authorization headers (same scheme as collector.py)."""
    datetime_str = datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")
    message = datetime_str + method + url_path + query_string
    signature = hmac.new(
        secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {
        "Authorization": (
            f"CEA algorithm=HmacSHA256, access-key={access_key}, "
            f"signed-date={datetime_str}, signature={signature}"
        ),
        "Content-Type": "application/json",
    }


def _credentials() -> tuple[str, str]:
    return os.getenv("COUPANG_ACCESS_KEY", ""), os.getenv("COUPANG_SECRET_KEY", "")


def _request(limiter, method: str, url_path: str, params: dict | None = None) -> dict:
    limiter.wait_if_needed()  # MUST be first statement of every API call path
    access_key, secret_key = _credentials()
    if not access_key or not secret_key:
        raise RuntimeError("COUPANG_ACCESS_KEY/COUPANG_SECRET_KEY 환경변수 미설정")
    query_string = urlencode(params or {})
    headers = generate_hmac(method, url_path, secret_key, access_key, query_string)
    url = f"{BASE_URL}{url_path}" + (f"?{query_string}" if query_string else "")
    resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    try:
        body = resp.json()
    except ValueError:
        body = {}
    return {"status_code": resp.status_code, "body": body}


def search_products(keyword: str, limit: int = 10, limiter=None) -> dict:
    from pipelines.curation.rate_limiter import RateLimiter
    limiter = limiter or RateLimiter(limit=80, window_seconds=60)
    url_path = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
    return _request(limiter, "GET", url_path, {"keyword": keyword, "limit": limit})


def get_best_categories(category_id: str = "", limiter=None) -> dict:
    from pipelines.curation.rate_limiter import RateLimiter
    limiter = limiter or RateLimiter(limit=80, window_seconds=60)
    # Live probe 2026-08-30: query param ?categoryId= returns 404.
    # Correct is path-param /v1/products/bestcategories/{categoryId} (flat list data).
    # Keep both forms handled: non-empty → path-param, empty → base path (no query).
    if category_id:
        url_path = f"/v2/providers/affiliate_open_api/apis/openapi/v1/products/bestcategories/{category_id}"
        return _request(limiter, "GET", url_path, None)
    url_path = "/v2/providers/affiliate_open_api/apis/openapi/v1/products/bestcategories"
    return _request(limiter, "GET", url_path, None)


def get_goldbox(limiter=None) -> dict:
    from pipelines.curation.rate_limiter import RateLimiter
    limiter = limiter or RateLimiter(limit=80, window_seconds=60)
    url_path = "/v2/providers/affiliate_open_api/apis/openapi/products/goldbox"
    return _request(limiter, "GET", url_path)
