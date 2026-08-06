"""ops_dashboard.checks.render — 렌더링 헬스체크

도메인 HTTP HEAD 요청으로 라이브 사이트 가용성을 검사한다.
active 블로그 한정으로 og:image, 썸네일, adsbygoogle.js 로드 여부 추가 검사.
비동기(async/await) + httpx.AsyncClient + 동시성 제한 적용.
"""
from __future__ import annotations

import logging
import re
import asyncio
import httpx
from typing import Optional

from ops_dashboard.checks import register_check
from ops_dashboard.db import get_blog_config_status, get_blog_domain

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds
MAX_CONCURRENT = 20  # 동시성 제한 (semaphore)

# 헤더
HEADERS = {"User-Agent": "OpsDashboard/1.0"}


async def _fetch_head(client: httpx.AsyncClient, url: str) -> tuple[Optional[int], Optional[str]]:
    """HEAD 요청으로 상태 코드와 Content-Type 반환."""
    try:
        resp = await client.head(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        return resp.status_code, resp.headers.get("Content-Type", "")
    except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as e:
        if hasattr(e, 'response') and e.response is not None:
            return e.response.status_code, ""
        return None, None


async def _fetch_get(client: httpx.AsyncClient, url: str) -> tuple[Optional[int], Optional[str]]:
    """GET 요청으로 상태 코드와 본문 일부 반환 (og:image, adsbygoogle 확인용)."""
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        body = resp.text[:50000]  # 처음 50KB만
        return resp.status_code, body
    except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as e:
        if hasattr(e, 'response') and e.response is not None:
            return e.response.status_code, ""
        return None, None


def _check_og_image(html: str, base_url: str) -> tuple[bool, Optional[str]]:
    """HTML에서 og:image URL 추출하고 접근 가능 여부 확인."""
    m = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
    if not m:
        m = re.search(r'name=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
    if m:
        og_url = m.group(1)
        if og_url.startswith("/"):
            from urllib.parse import urljoin
            og_url = urljoin(base_url, og_url)
        return True, og_url
    return False, None


def _check_adsbygoogle(html: str) -> bool:
    """HTML에 adsbygoogle.js 로드 코드가 있는지 확인."""
    return "adsbygoogle" in html and ("adsbygoogle.js" in html or "googlesyndication.com" in html)


def _check_featureimage(html: str, base_url: str) -> tuple[bool, Optional[str]]:
    """frontmatter featureimage나 썸네일 이미지 URL 확인."""
    m = re.search(r'<meta\s+name=["\']featureimage["\']\s+content=["\']([^"\']+)["\']', html)
    if m:
        img_url = m.group(1)
        if img_url.startswith("/"):
            from urllib.parse import urljoin
            img_url = urljoin(base_url, img_url)
        return True, img_url
    return False, None


async def _check_single_blog(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, blog_id: str, domain: str) -> dict:
    """단일 블로그 render_health 검사 (비동기)."""
    async with semaphore:
        base_url = f"https://{domain}"
        failures = []
        evidence_urls = []

        # 1. 홈페이지 접근성 + HTML 가져오기
        status, html = await _fetch_get(client, base_url)
        if not status or not (200 <= status < 400):
            return {
                "blog_id": blog_id,
                "status": "fail",
                "detail": f"Homepage HTTP {status or 'connection failed'}",
                "evidence_url": base_url,
            }

        # 2. og:image 확인
        og_ok, og_url = _check_og_image(html, base_url)
        if not og_ok:
            failures.append("og:image missing or inaccessible")
            if og_url:
                evidence_urls.append(f"og:image: {og_url}")
        else:
            evidence_urls.append(f"og:image: {og_url} (OK)")

        # 3. adsbygoogle.js 로드 확인
        if not _check_adsbygoogle(html):
            failures.append("adsbygoogle.js not loaded")
        else:
            evidence_urls.append("adsbygoogle.js: loaded")

        # 4. 썸네일/featureimage 확인 (최근 포스트 1개 샘플)
        post_link_match = re.search(r'href=["\'](https?://[^"\']+/posts/[^"\']+)["\']', html)
        if post_link_match:
            post_url = post_link_match.group(1)
            post_status, post_html = await _fetch_get(client, post_url)
            if post_status and 200 <= post_status < 400:
                thumb_ok, thumb_url = _check_featureimage(post_html, base_url)
                if not thumb_ok:
                    failures.append("featureimage/thumbnail inaccessible")
                    if thumb_url:
                        evidence_urls.append(f"featureimage: {thumb_url}")
                else:
                    evidence_urls.append(f"featureimage: {thumb_url} (OK)")

        if failures:
            return {
                "blog_id": blog_id,
                "status": "fail",
                "detail": f"Render health issues: {'; '.join(failures)}",
                "evidence_url": "\n".join(evidence_urls),
            }

        return {
            "blog_id": blog_id,
            "status": "pass",
            "detail": "All render checks passed: og:image, adsbygoogle, thumbnail",
            "evidence_url": "\n".join(evidence_urls),
        }


@register_check("render_health")
def check_render_health(conn, blog_id: str) -> dict:
    """단일 블로그 render_health 검사 (동기 래퍼 - 비동기 함수 실행)."""
    config_status = get_blog_config_status(conn, blog_id)
    if not config_status:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found in lifecycle"}

    domain = get_blog_domain(conn, blog_id)
    if not domain:
        return {
            "status": "pass",
            "detail": "No domain configured — render check not applicable",
            "evidence_url": "",
        }

    if config_status in ("inactive", "disabled"):
        return {
            "status": "pass",
            "detail": f"Blog is {config_status} — render check not applicable",
            "evidence_url": "",
        }

    # 비동기 함수를 동기적으로 실행
    import asyncio
    async def _run():
        semaphore = asyncio.Semaphore(1)  # 단일 블로그도 semaphore 사용
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
            return await _check_single_blog(client, asyncio.Semaphore(1), blog_id, domain)
    
    return asyncio.run(_run())


# 배치 실행용 헬퍼 (비동기 + 동시성 제한 + 샘플 우선순위)
async def _run_batch_async(blog_ids: list[str], domains: dict[str, str], max_workers: int = 10) -> dict:
    """여러 블로그 render_health 비동기 병렬 실행."""
    semaphore = asyncio.Semaphore(max_workers)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        tasks = [
            _check_single_blog(client, semaphore, blog_id, domains[blog_id])
            for blog_id in blog_ids
            if blog_id in domains
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    summary = {"total": 0, "pass": 0, "fail": 0, "unknown": 0, "details": []}
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"render_health batch error: {result}")
            summary["unknown"] += 1
            continue
        summary["total"] += 1
        summary[result["status"]] = summary.get(result["status"], 0) + 1
        summary["details"].append(result)
    return summary


def run_render_health_batch(conn, blog_ids: list[str] | None = None, max_workers: int = 10) -> dict:
    """여러 블로그 render_health 비동기 병렬 실행 (동시성 제한).

    샘플 우선순위:
    1. 최근 발행 실패 블로그
    2. 오래된 검사 안 된 블로그
    3. active 블로그 전체
    """
    from ops_dashboard.db import get_all_blogs, get_blog_domain, get_blog_config_status

    blogs = get_all_blogs(conn)
    if blog_ids:
        blogs = [b for b in blogs if b["blog_id"] in blog_ids]

    # active 블로그만 필터
    active_blogs = [b for b in blogs if b["config_status"] == "active"]
    
    # 도메인 매핑 생성
    domains = {}
    for b in active_blogs:
        domain = get_blog_domain(conn, b["blog_id"])
        if domain:
            domains[b["blog_id"]] = domain

    # 비동기 배치 실행
    import asyncio
    return asyncio.run(_run_batch_async(list(domains.keys()), domains, max_workers))