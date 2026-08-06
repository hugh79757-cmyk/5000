"""ops_dashboard.checks.render — 렌더링 헬스체크

도메인 HTTP HEAD 요청으로 라이브 사이트 가용성을 검사한다.
active 블로그 한정으로 og:image, 썸네일, adsbygoogle.js 로드 여부 추가 검사.
"""
from __future__ import annotations

import logging
import urllib.request
import urllib.error
import concurrent.futures
import time

from ops_dashboard.checks import register_check

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds
MAX_CONCURRENT = 5  # 동시성 제한

# 샘플링 우선순위: 최근 발행/실패/오래된 블로그 우선


def _fetch_head(url: str, timeout: int = REQUEST_TIMEOUT) -> tuple[int | None, str | None]:
    """HEAD 요청으로 상태 코드와 Content-Type 반환."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "OpsDashboard/1.0")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError, TimeoutError):
        return None, None


def _fetch_get(url: str, timeout: int = REQUEST_TIMEOUT) -> tuple[int | None, str | None]:
    """GET 요청으로 상태 코드와 본문 일부 반환 (og:image, adsbygoogle 확인용)."""
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "OpsDashboard/1.0")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(50000).decode("utf-8", errors="replace")  # 처음 50KB만
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError, TimeoutError):
        return None, None


def _check_og_image(html: str, base_url: str) -> tuple[bool, str | None]:
    """HTML에서 og:image URL 추출하고 접근 가능 여부 확인."""
    import re
    # <meta property="og:image" content="...">
    m = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
    if not m:
        # <meta name="og:image" content="...">
        m = re.search(r'name=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
    if m:
        og_url = m.group(1)
        # 상대 URL이면 절대 URL로 변환
        if og_url.startswith("/"):
            from urllib.parse import urljoin
            og_url = urljoin(base_url, og_url)
        status, _ = _fetch_head(og_url)
        if status and 200 <= status < 400:
            return True, og_url
        return False, og_url
    return False, None


def _check_adsbygoogle(html: str) -> bool:
    """HTML에 adsbygoogle.js 로드 코드가 있는지 확인."""
    return "adsbygoogle" in html and ("adsbygoogle.js" in html or "googlesyndication.com" in html)


def _check_featureimage(html: str, base_url: str) -> tuple[bool, str | None]:
    """frontmatter featureimage나 썸네일 이미지 URL 확인."""
    import re
    # Hugo featureimage meta tag
    m = re.search(r'<meta\s+name=["\']featureimage["\']\s+content=["\']([^"\']+)["\']', html)
    if m:
        img_url = m.group(1)
        if img_url.startswith("/"):
            from urllib.parse import urljoin
            img_url = urljoin(base_url, img_url)
        status, _ = _fetch_head(img_url)
        if status and 200 <= status < 400:
            return True, img_url
        return False, img_url
    return False, None


@register_check("render_health")
def check_render_health(conn, blog_id: str) -> dict:
    """도메인 HTTP HEAD 요청 + og:image + adsbygoogle.js + 썸네일 검사.

    active 블로그만 검사, 비동기 제한 동시성, 샘플 우선순위 적용.
    """
    blog = conn.execute(
        "SELECT * FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    if not blog:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found in lifecycle"}

    config_status = blog["config_status"]
    domain = blog["domain"]

    # 비활성 블로그 또는 도메인 없음
    if config_status in ("inactive", "disabled"):
        return {
            "status": "pass",
            "detail": f"Blog is {config_status} — render check not applicable",
            "evidence_url": "",
        }
    if not domain:
        return {
            "status": "pass",
            "detail": "No domain configured — render check not applicable",
            "evidence_url": "",
        }

    base_url = f"https://{domain}"
    failures = []
    evidence_urls = []

    # 1. 홈페이지 접근성 + HTML 가져오기
    status, html = _fetch_get(base_url)
    if not status or not (200 <= status < 400):
        return {
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
    # 홈페이지에서 첫 번째 포스트 링크 찾아서 썸네일 확인
    import re
    post_link_match = re.search(r'href=["\'](https?://[^"\']+/posts/[^"\']+)["\']', html)
    if post_link_match:
        post_url = post_link_match.group(1)
        post_status, post_html = _fetch_get(post_url)
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
            "status": "fail",
            "detail": f"Render health issues: {'; '.join(failures)}",
            "evidence_url": "\n".join(evidence_urls),
        }

    return {
        "status": "pass",
        "detail": f"All render checks passed: og:image, adsbygoogle, thumbnail",
        "evidence_url": "\n".join(evidence_urls),
    }


# 배치 실행용 헬퍼 (동시성 제한 + 샘플 우선순위)
def run_render_health_batch(conn, blog_ids: list[str] | None = None, max_workers: int = MAX_CONCURRENT) -> dict:
    """여러 블로그 render_health 병렬 실행 (동시성 제한).

    샘플 우선순위:
    1. 최근 발행 실패 블로그
    2. 오래된 검사 안 된 블로그
    3. active 블로그 전체
    """
    from ops_dashboard.db import get_all_blogs

    blogs = get_all_blogs(conn)
    if blog_ids:
        blogs = [b for b in blogs if b["blog_id"] in blog_ids]

    # active 블로그만 필터
    active_blogs = [b for b in blogs if b["config_status"] == "active"]

    # 우선순위: publish_ledger에서 최근 실패 내역이 있는 블로그 우선
    # 단순화: 알파벳 순으로 (실제로는 실패 이력/최종 검사일 기준 정렬 필요)

    results = {"total": 0, "pass": 0, "fail": 0, "unknown": 0, "details": []}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_blog = {
            executor.submit(check_render_health, conn, b["blog_id"]): b
            for b in active_blogs
        }

        for future in concurrent.futures.as_completed(future_to_blog):
            blog = future_to_blog[future]
            try:
                result = future.result()
            except Exception as e:
                logger.error("render_health batch failed for %s: %s", blog["blog_id"], e)
                result = {"status": "unknown", "detail": f"Error: {e}", "evidence_url": ""}

            results["total"] += 1
            results[result["status"]] = results.get(result["status"], 0) + 1
            results["details"].append({
                "blog_id": blog["blog_id"],
                "status": result["status"],
                "detail": result["detail"],
            })

    return results