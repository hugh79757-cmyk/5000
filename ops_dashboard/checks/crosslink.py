"""ops_dashboard.checks.crosslink — 크로스링크 주제 일관성 자동검사 (M03 / audit Q5)

블로그 포스트 내 삽입된 내부 크로스링크를 파싱해,
링크 대상이 cuap_entity_linker.py의 CROSS_GRAPH에 정의된 의도적 연결인지 판정한다.
CROSS_GRAPH에 없으면 무관 링크로 간주해 fail.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from ops_dashboard.checks import register_check

logger = logging.getLogger(__name__)

# CUAP 블로그 도메인 → 블로그 ID 매핑 (CROSS_GRAPH 키와 일치)
CUAP_DOMAIN_TO_BLOG_ID = {
    "appliance.informationhot.kr": "appliance-hugo",
    "baby.informationhot.kr": "baby-hugo",
    "beauty.informationhot.kr": "beauty-hugo",
    "camping.informationhot.kr": "camping-hugo",
    "fitness.informationhot.kr": "fitness-hugo",
    "health.informationhot.kr": "health-hugo",
    "interior.informationhot.kr": "interior-hugo",
    "kitchen.informationhot.kr": "kitchen-hugo",
    "laptop.informationhot.kr": "laptop-hugo",
    "pet.informationhot.kr": "pet-hugo",
    "senior.informationhot.kr": "senior-hugo",
}

# CROSS_GRAPH 직접 임포트 (shared 모듈에서)
try:
    from shared.cuap_entity_linker import CROSS_GRAPH
except ImportError:
    CROSS_GRAPH = {}


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


def _extract_crosslink_urls(content: str) -> list[str]:
    """Extract internal CUAP cross-link URLs from post content."""
    urls = []
    for m in re.finditer(r'<a\s+href="(https://[^"]+\.informationhot\.kr/posts/[^"]+)"', content):
        urls.append(m.group(1))
    return urls


def _resolve_blog_id_from_url(url: str) -> str | None:
    """Resolve blog_id from URL using domain mapping."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        return CUAP_DOMAIN_TO_BLOG_ID.get(domain)
    except Exception:
        return None


def _is_crosslink_allowed(source_blog_id: str, target_blog_id: str) -> bool:
    """Check if cross-link from source to target is defined in CROSS_GRAPH."""
    if source_blog_id not in CROSS_GRAPH:
        return False
    graph = CROSS_GRAPH[source_blog_id]
    allowed = set()
    for category in ("primary", "secondary", "use_cases"):
        allowed.update(graph.get(category, []))
    return target_blog_id in allowed


@register_check("crosslink_consistency")
def check_crosslink_consistency(conn, blog_id: str) -> dict:
    """크로스링크 주제 일관성 검사 (M03 / audit Q5).

    각 포스트의 크로스링크가 CROSS_GRAPH에 정의된 의도적 연결인지 검사.
    CROSS_GRAPH에 없는 링크가 있으면 fail.
    CUAP 블로그가 아니면 UNKNOWN(needs_manual).
    """
    blog = conn.execute(
        "SELECT * FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    if not blog:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found in lifecycle"}

    site = _find_hugo_root(dict(blog))
    if not site:
        return {"status": "unknown", "detail": f"Site path not found for {blog_id}"}

    # Only apply to CUAP blogs (have CROSS_GRAPH entry)
    if blog_id not in CROSS_GRAPH:
        return {
            "status": "unknown",
            "detail": f"Blog {blog_id} not in CROSS_GRAPH — not a CUAP blog",
        }

    posts_dir = site / "content" / "posts"
    if not posts_dir.is_dir():
        return {"status": "pass", "detail": "No content/posts directory"}

    violations = []
    checked_posts = 0
    total_links = 0

    for post_dir in posts_dir.iterdir():
        if not post_dir.is_dir():
            continue

        index_md = post_dir / "index.md"
        if not index_md.exists():
            continue

        content = _read_file_safe(index_md)
        if not content.strip():
            continue

        crosslink_urls = _extract_crosslink_urls(content)
        if not crosslink_urls:
            continue

        checked_posts += 1

        for url in crosslink_urls:
            total_links += 1
            target_blog_id = _resolve_blog_id_from_url(url)
            if not target_blog_id:
                # CUAP 외부 링크
                continue

            if not _is_crosslink_allowed(blog_id, target_blog_id):
                violations.append({
                    "post": post_dir.name,
                    "source_blog": blog_id,
                    "target_blog": target_blog_id,
                    "url": url,
                })

    if violations:
        detail = f"{len(violations)}/{total_links} cross-links NOT in CROSS_GRAPH found in {checked_posts} posts"
        evidence_lines = [
            f"Post: {v['post']}, Source: {v['source_blog']}, Target: {v['target_blog']}, URL: {v['url']}"
            for v in violations[:3]
        ]
        evidence = "\n".join(evidence_lines)
        return {"status": "fail", "detail": detail, "evidence_url": evidence}

    if checked_posts == 0:
        return {"status": "unknown", "detail": "No posts with cross-links to check"}

    return {
        "status": "pass",
        "detail": f"All {total_links} cross-links in {checked_posts} posts match CROSS_GRAPH",
        "evidence_url": "",
    }