"""ops_dashboard.checks.crosslink — 크로스링크 주제 일관성 자동검사 (M03 / audit Q5)

블로그 포스트 내 삽입된 내부 크로스링크를 파싱해,
링크 대상 글의 카테고리/계열이 원글과 같거나 인접한지 판정한다.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from ops_dashboard.checks import register_check

logger = logging.getLogger(__name__)

# CUAP 블로그 도메인 → 카테고리 매핑
CUAP_BLOG_CATEGORIES = {
    "appliance.informationhot.kr": "가전",
    "baby.informationhot.kr": "유아/출산",
    "beauty.informationhot.kr": "뷰티",
    "camping.informationhot.kr": "캠핑",
    "fitness.informationhot.kr": "피트니스",
    "health.informationhot.kr": "건강",
    "interior.informationhot.kr": "인테리어",
    "kitchen.informationhot.kr": "주방",
    "laptop.informationhot.kr": "노트북",
    "pet.informationhot.kr": "펫",
    "senior.informationhot.kr": "건강",  # SEAP 시니어/복지
}

# 인접 카테고리 정의 (같거나 인접하면 pass)
ADJACENT_CATEGORIES = {
    "가전": {"가전", "주방", "노트북"},
    "주방": {"주방", "가전", "인테리어"},
    "노트북": {"노트북", "가전"},
    "뷰티": {"뷰티", "건강", "유아/출산"},
    "건강": {"건강", "뷰티", "유아/출산", "피트니스"},
    "유아/출산": {"유아/출산", "뷰티", "건강"},
    "캠핑": {"캠핑", "피트니스", "인테리어"},
    "피트니스": {"피트니스", "건강", "캠핑"},
    "인테리어": {"인테리어", "주방", "캠핑"},
    "펫": {"펫"},
}


def _find_hugo_root(blog_row: dict) -> Path | None:
    """Resolve the Hugo site root from blog_lifecycle row."""
    site_path = blog_row.get("site_path", "")
    if not site_path:
        return None
    p = Path(site_path)
    if not p.is_dir():
        return None
    return p


def _read_file_safe(path: Path) -> str:
    """Read file contents, return empty string on error."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return ""


def _extract_frontmatter_category(content: str) -> str | None:
    """Extract category from frontmatter."""
    # categories: ['추천'] or categories: ["추천"] or categories: [추천]
    m = re.search(r"categories\s*:\s*\[([^\]]+)\]", content)
    if m:
        cats = m.group(1)
        # 첫 번째 카테고리만 사용
        first = re.search(r'["\']?([^"\',]+)["\']?', cats)
        if first:
            return first.group(1).strip()
    return None


def _extract_crosslink_urls(content: str) -> list[str]:
    """Extract internal CUAP cross-link URLs from post content."""
    urls = []
    # 패턴: <a href="https://blog.informationhot.kr/posts/...">
    for m in re.finditer(r'<a\s+href="(https://[^"]+\.informationhot\.kr/posts/[^"]+)"', content):
        urls.append(m.group(1))
    return urls


def _resolve_post_category_from_url(url: str) -> str | None:
    """Resolve blog domain from URL and map to category."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        return CUAP_BLOG_CATEGORIES.get(domain)
    except Exception:
        return None


def _is_category_consistent(source_category: str, target_category: str) -> bool:
    """Check if target category is same or adjacent to source."""
    if source_category == target_category:
        return True
    adjacent = ADJACENT_CATEGORIES.get(source_category, set())
    return target_category in adjacent


@register_check("crosslink_consistency")
def check_crosslink_consistency(conn, blog_id: str) -> dict:
    """크로스링크 주제 일관성 검사 (M03 / audit Q5).

    각 포스트의 크로스링크가 같은/인접 계열을 가리키는지 검사.
    무관 카테고리 링크가 있으면 fail.
    카테고리 메타데이터가 없으면 UNKNOWN(needs_manual).
    """
    blog = conn.execute(
        "SELECT * FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    if not blog:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found in lifecycle"}

    site = _find_hugo_root(dict(blog))
    if not site:
        return {"status": "unknown", "detail": f"Site path not found for {blog_id}"}

    # 블로그 자체의 카테고리 결정 (도메인/브랜드 기반)
    source_category = _resolve_blog_category(blog)
    if not source_category:
        return {"status": "unknown", "detail": f"Cannot determine category for blog {blog_id}"}

    # 포스트 디렉토리 탐색
    posts_dir = site / "content" / "posts"
    if not posts_dir.is_dir():
        return {"status": "pass", "detail": "No content/posts directory"}

    violations = []
    checked_posts = 0

    for post_dir in posts_dir.iterdir():
        if not post_dir.is_dir():
            continue

        index_md = post_dir / "index.md"
        if not index_md.exists():
            continue

        content = _read_file_safe(index_md)
        if not content.strip():
            continue

        # 크로스링크 URL 추출
        crosslink_urls = _extract_crosslink_urls(content)
        if not crosslink_urls:
            continue

        checked_posts += 1

        for url in crosslink_urls:
            target_category = _resolve_post_category_from_url(url)
            if not target_category:
                # CUAP 외부 링크거나 알 수 없는 도메인
                continue

            if not _is_category_consistent(source_category, target_category):
                violations.append({
                    "post": post_dir.name,
                    "source_category": source_category,
                    "target_category": target_category,
                    "url": url,
                })

    if violations:
        detail = f"{len(violations)} cross-links to unrelated categories found in {checked_posts} posts"
        evidence_lines = [
            f"Post: {v['post']}, Source: {v['source_category']}, Target: {v['target_category']}, URL: {v['url']}"
            for v in violations[:3]
        ]
        evidence = "\n".join(evidence_lines)
        return {"status": "fail", "detail": detail, "evidence_url": evidence}

    if checked_posts == 0:
        return {"status": "unknown", "detail": "No posts with cross-links to check"}

    return {
        "status": "pass",
        "detail": f"All {checked_posts} posts with cross-links have consistent categories",
        "evidence_url": "",
    }


def _resolve_blog_category(blog: sqlite3.Row) -> str | None:
    """Resolve blog's category from its domain or brand."""
    domain = blog["domain"] if blog["domain"] else ""
    if domain in CUAP_BLOG_CATEGORIES:
        return CUAP_BLOG_CATEGORIES[domain]

    # Fallback: try to infer from brand
    brand = blog["brand"] if blog["brand"] else ""
    if brand == "cuap":
        # Could map from blog_id if domain not in CUAP_BLOG_CATEGORIES
        pass
    return None