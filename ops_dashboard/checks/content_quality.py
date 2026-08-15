"""ops_dashboard.checks.content_quality — 발행 글 구조 품질 검사

라이브 최신 글 HTML을 가져와, 후처리(_normalize_product_blocks)가 놓친
구조 결함이 남아있는지 검사한다.
  - 값 없는 빈 불릿 (- 배송:, - 이미지:, - 단독)
  - 쪼개진 CTA 버튼 (<div ...>\n 뒤 <a> 분리)
  - 제휴문구 개수 이상 (정상: 1~2회)
  - 상품 이미지 누락 (본문 <img> 0개)
"""
from __future__ import annotations

import logging
import re
import urllib.parse
import urllib.request

from ops_dashboard.checks import register_check
from ops_dashboard.db import get_blog_config_status, get_blog_domain

logger = logging.getLogger(__name__)

DISCLOSURE = "쿠팡 파트너스 활동의 일환"
_UA = "Mozilla/5.0 (ops-dashboard content_quality check)"


def _fetch(url: str, timeout: int = 12) -> str | None:
    try:
        # 한글 등 비ASCII 경로 퍼센트 인코딩 (스킴/호스트는 보존)
        sp = urllib.parse.urlsplit(url)
        path = urllib.parse.quote(sp.path, safe="/%")
        url = urllib.parse.urlunsplit((sp.scheme, sp.netloc, path, sp.query, sp.fragment))
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"content_quality fetch 실패 {url}: {e}")
        return None


def _latest_post_url(domain: str) -> str | None:
    """sitemap 또는 /posts/ 목록에서 최신 글 URL 1건 추출."""
    base = f"https://{domain}"
    # sitemap 우선 (lastmod 최신)
    sm = _fetch(f"{base}/sitemap.xml")
    if sm:
        locs = re.findall(r"<loc>([^<]*/posts/[^<]+)</loc>", sm)
        if locs:
            return locs[-1]
    # fallback: 목록 페이지 첫 글 링크
    lst = _fetch(f"{base}/posts/")
    if lst:
        m = re.search(r'href=["\']?([^"\'>\s]*/posts/[^"\'>\s]+/)["\']?', lst)
        if m:
            link = m.group(1)
            return link if link.startswith("http") else base + link
    return None


def _analyze(html: str) -> list[str]:
    """렌더된 라이브 HTML 기준 구조 결함 목록 (빈 리스트면 정상)."""
    issues = []

    # 1) 빈 리스트 항목 (라벨만 / 완전 빈 <li>)
    if re.search(r"<li>\s*(배송|이미지|쿠팡순위)\s*:\s*</li>", html):
        issues.append("빈 불릿(라벨만)")
    if re.search(r"<li>\s*</li>", html):
        issues.append("빈 리스트 항목")

    # 2) CTA 버튼이 <li> 안에 갇힘 (독립 블록화 실패)
    if re.search(r"<li>[^<]*<[^>]*btn-price-check", html):
        issues.append("CTA가 리스트 항목에 갇힘")

    # 3) 제휴문구 개수 (정상 1~2회)
    n = html.count(DISCLOSURE)
    if n == 0:
        issues.append("제휴문구 누락")
    elif n > 2:
        issues.append(f"제휴문구 과다({n}회)")

    # 4) 상품/썸네일 이미지 누락 (r2 썸네일 또는 쿠팡 상품 이미지)
    if not re.search(r"curation-images|r2\.dev|ads-partners\.coupang\.com|coupangcdn\.com", html):
        issues.append("상품/썸네일 이미지 없음")

    return issues



@register_check("content_quality")
def check_content_quality(conn, blog_id: str) -> dict:
    config_status = get_blog_config_status(conn, blog_id)
    if not config_status:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found", "evidence_url": ""}
    if config_status in ("inactive", "disabled"):
        return {"status": "pass", "detail": f"Blog is {config_status} — skip", "evidence_url": ""}

    domain = get_blog_domain(conn, blog_id)
    if not domain:
        return {"status": "unknown", "detail": "domain not found", "evidence_url": ""}

    post_url = _latest_post_url(domain)
    if not post_url:
        return {"status": "unknown", "detail": "최신 글 URL을 찾지 못함", "evidence_url": f"https://{domain}/posts/"}

    html = _fetch(post_url)
    if html is None:
        return {"status": "unknown", "detail": "글 HTML fetch 실패", "evidence_url": post_url}

    issues = _analyze(html)
    if issues:
        return {"status": "fail", "detail": "구조 결함: " + ", ".join(issues), "evidence_url": post_url}
    return {"status": "pass", "detail": "발행 글 구조 정상(빈불릿/CTA/제휴문구/이미지)", "evidence_url": post_url}
