"""FM-DRAFT: 프론트매터 draft:true 제거 (안전등급 자동수정).

본문 미변경 — frontmatter 키만 편집. git 추적 파일이므로 롤백 가능.
"""

from __future__ import annotations

from pathlib import Path

from shared.autofix.core import logger


def _iter_posts(site: Path):
    posts = site / "content" / "posts"
    if not posts.is_dir():
        return []
    return sorted(posts.glob("*/index.md"))


def fix_draft_true(site: Path, blog_id: str) -> tuple[bool, str]:
    """site 내 모든 포스트에서 draft:true 프론트매터 키를 제거.

    returns: (ok, message)
    """
    import frontmatter

    fixed = 0
    try:
        for path in _iter_posts(site):
            try:
                post = frontmatter.load(path)
                if post.metadata.get("draft") is True:
                    del post.metadata["draft"]
                    path.write_text(frontmatter.dumps(post), encoding="utf-8")
                    fixed += 1
            except Exception as e:
                logger.warning("[FM-DRAFT] %s 파싱 오류(무영향 skip): %s", path, e)
                continue
    except Exception as e:
        return False, f"FM-DRAFT 오류: {e}"
    if fixed:
        return True, f"FM-DRAFT: {blog_id} draft 제거 {fixed}건"
    return True, f"FM-DRAFT: {blog_id} draft 없음 (no-op)"
