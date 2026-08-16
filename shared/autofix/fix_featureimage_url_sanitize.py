"""FM-FEATUREIMAGE: featureimage URL 정화 (안전등급 자동수정).

shared/publishers/hugo_writer.sanitize_featureimage_url (IMAGE-GUARD) 를
프론트매터 featureimage 필드에 적용. 본문 미변경.
정화 불가능(빈 문자열 반환) 시 사람 게이트(False) 로 분류.
"""

from __future__ import annotations

from pathlib import Path

from shared.autofix.core import logger
from shared.publishers.hugo_writer import sanitize_featureimage_url


def _iter_posts(site: Path):
    posts = site / "content" / "posts"
    if not posts.is_dir():
        return []
    return sorted(posts.glob("*/index.md"))


def fix_featureimage_url_sanitize(site: Path, blog_id: str) -> tuple[bool, str]:
    """site 포스트의 featureimage URL을 IMAGE-GUARD 규칙으로 정화.

    returns: (ok, message)
    """
    import frontmatter

    fixed = 0
    unsafe = 0
    try:
        for path in _iter_posts(site):
            try:
                post = frontmatter.load(path)
                url = post.metadata.get("featureimage", "")
                if not url:
                    continue
                cleaned = sanitize_featureimage_url(url)
                if cleaned == url:
                    continue
                if not cleaned:
                    unsafe += 1
                    continue
                post.metadata["featureimage"] = cleaned
                path.write_text(frontmatter.dumps(post), encoding="utf-8")
                fixed += 1
            except Exception as e:
                logger.warning("[FM-FEATUREIMAGE] %s 파싱 오류(무영향 skip): %s", path, e)
                continue
    except Exception as e:
        return False, f"FM-FEATUREIMAGE 오류: {e}"
    if unsafe:
        return False, f"FM-FEATUREIMAGE: {blog_id} 정화불가 {unsafe}건 (사람 게이트)"
    if fixed:
        return True, f"FM-FEATUREIMAGE: {blog_id} featureimage 정화 {fixed}건"
    return True, f"FM-FEATUREIMAGE: {blog_id} 정화 대상 없음 (no-op)"
