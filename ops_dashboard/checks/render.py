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


def _check_og_image(html: str) -> tuple[bool, Optional[str]]:
    """HTML에서 og:image URL 추출 (속성 순서 무관).

    - 표준 순서: property="og:image" content="..."
    - 역순 (Blogger): content='...' property='og:image'
    """
    patterns = [
        # 표준 순서 (property/name 먼저)
        r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
        r'name=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
        # 역순 (Blogger: content 먼저)
        r'content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
        r'content=["\']([^"\']+)["\']\s+name=["\']og:image["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return True, m.group(1)
    return False, None


def _find_post_url(html: str, base_url: str) -> Optional[str]:
    """홈페이지 HTML에서 첫 번째 포스트 URL 추출.

    minified(unquoted) href와 Blogger(/YYYY/MM/slug.html) 패턴을 모두 지원한다.
    순수 목록 페이지(/posts/, /posts)와 정적 에셋은 건너뛴다.
    """
    from urllib.parse import urljoin

    # 1) /posts/<slug>/ 패턴 (Hugo 표준) — quoted/unquoted 모두.
    #    /posts/(목록), /posts(목록), css/js 등 정적 에셋은 제외.
    for pat in (
        r'href=["\']([^"\']+/posts/[^"\']+)[\'"]',
        r'href=([^\s>]+/posts/[^\s>\'"]+)',
        r'href=(/posts/[^\s>\'"]+)',
    ):
        for m in re.finditer(pat, html):
            url = m.group(1)
            path = url.split("?", 1)[0].rstrip("/")
            # Blogger feeds/등 비포스트 경로 제외
            if "feeds/" in path or "/feeds" in path:
                continue
            # 목록/인덱스 페이지 제외
            if path.endswith("/posts") or path.endswith("/posts/") or path.endswith("/posts/index.html"):
                continue
            # 정적 에셋 제외
            if re.search(r"\.(css|js|png|jpe?g|webp|svg|ico|xml|json|txt)$", path):
                continue
            return url if url.startswith("http") else urljoin(base_url, url)

    # 2) Blogger: /YYYY/MM/slug.html (feeds 등 목록/정적 리소스 제외)
    for m in re.finditer(r'href=["\']([^"\']+/\d{4}/\d{2}/[^"\']+\.html)[\'"]', html):
        url = m.group(1)
        if "feeds/" in url or "/feeds" in url:
            continue
        return url if url.startswith("http") else urljoin(base_url, url)

    # 3) 루트 수준 포스트 슬러그 (PaperMod 계열: /<slug>-2026<...>/ 또는 /<slug>-20…/)
    for m in re.finditer(r'href=([^\s>]+)', html):
        url = m.group(1)
        if "feeds/" in url or "/feeds" in url:
            continue
        path = url.split("?", 1)[0].rstrip("/")
        if re.search(r"\.(css|js|png|jpe?g|webp|svg|ico|xml|json|txt)$", path):
            continue
        # 루트 슬러그 후보: 퍼센트인코딩/한글/영문 슬러그에 날짜 패턴(-2026 등) 포함
        slug = path.rsplit("/", 1)[-1]
        if slug and re.search(r"(20\d{2}|-s\d+|\d{6})", slug) and "/" not in path[1:]:
            return url if url.startswith("http") else urljoin(base_url, url)

    return None


def _check_adsbygoogle(html: str) -> bool:
    """HTML에 adsbygoogle.js 로드 코드가 있는지 확인."""
    return "adsbygoogle" in html and ("adsbygoogle.js" in html or "googlesyndication.com" in html)


# AdSense Publisher ID ↔ 도메인 계열 매핑 (AGENTS.md 섹션 1 규칙)
# 한 HTML 페이지 = 하나의 Publisher ID. 계열별 고정 ID.
_ADSENSE_FAMILY: dict[str, str] = {
    "rotcha.kr": "ca-pub-8772455780561463",
    "techpawz.com": "ca-pub-8772455780561463",
    "informationhot.kr": "ca-pub-6677996696534146",
    "aikorea24.kr": "ca-pub-5938862195544185",
}

_PUB_RE = re.compile(r"ca-pub-\d+")


def _expected_pub_id(domain: str) -> str | None:
    """도메인 접미사로 계열 매핑된 기대 Publisher ID 반환 (미등록 계열은 None)."""
    for suffix, pub in _ADSENSE_FAMILY.items():
        if domain == suffix or domain.endswith("." + suffix):
            return pub
    return None


def _check_adsense_publisher_id(html: str, domain: str) -> tuple[bool, str | None]:
    """라이브 HTML의 ca-pub-* 가 도메인 계열 매핑(AGENTS.md §1)과 일치하는지 교차검증.

    - loader: adsbygoogle.js?client=ca-pub-XXXX
    - slot:   data-ad-client="ca-pub-XXXX"
    기대 ID(_expected_pub_id)가 None 이면 미등록 계열 → 검사 생략(pass).
    ca-pub 가 전혀 없으면 AdSense 미사용 → pass (부재는 _check_adsbygoogle 가 다룸).
    loader 또는 slot 중 하나라도 기대 ID와 다르면 ADSENSE-ID-MISMATCH 로 fail.
    자동수정은 하지 않는다(detect-only).
    """
    expected = _expected_pub_id(domain)
    if expected is None:
        return True, None
    clients = set(_PUB_RE.findall(html))
    if not clients:
        return True, None
    # 기대 ID 부재 → 도메인 계열과 불일치 (공백/잘못된 계정)
    if expected not in clients:
        return False, f"ADSENSE-ID-MISMATCH observed={sorted(clients)} expected={expected}"
    # 페이지 내 여러 ca-pub 혼재 → 불일치
    if len(clients) > 1:
        return False, f"ADSENSE-ID-MISMATCH multiple ca-pub in page={sorted(clients)} expected={expected}"
    return True, None


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

        # 2. adsbygoogle.js 로드 확인
        if not _check_adsbygoogle(html):
            failures.append("adsbygoogle.js not loaded")
        else:
            evidence_urls.append("adsbygoogle.js: loaded")

        # 3. og:image 확인 — 테마(Hugo/Blowfish/PaperMod)는 홈페이지가 아닌
        #    포스트 페이지에서 og:image를 발행하므로, 최근 포스트 1개를 샘플로 검사.
        #    (Blogger는 content 먼저 역순 속성 발행 — _check_og_image가 처리)
        post_url = _find_post_url(html, base_url)
        og_checked_on = "homepage"
        og_ok = False
        og_url = None
        post_status = None
        post_html = ""
        if post_url:
            post_status, post_html = await _fetch_get(client, post_url)
            if post_status and 200 <= post_status < 400:
                og_checked_on = "post"
                og_ok, og_url = _check_og_image(post_html)
                if not og_ok:
                    # 포스트에서 못 찾으면 홈페이지에서 fallback 확인
                    og_ok, og_url = _check_og_image(html)
                    if og_ok:
                        og_checked_on = "homepage"
        else:
            og_ok, og_url = _check_og_image(html)

        if not og_ok:
            failures.append("og:image missing or inaccessible")
        else:
            evidence_urls.append(f"og:image: {og_url} (OK, from {og_checked_on})")

        # 3b. AdSense Publisher-ID ↔ 도메인 계열 교차검증 (detect-only)
        combined_html = html + "\n" + post_html
        ok_pub, pub_detail = _check_adsense_publisher_id(combined_html, domain)
        if not ok_pub:
            failures.append(pub_detail or "ADSENSE-ID-MISMATCH")

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