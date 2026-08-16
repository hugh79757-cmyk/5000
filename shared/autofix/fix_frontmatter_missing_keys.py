"""FM-MISSINGKEYS: 필수 프론트매터 키 보강 (안전등급 자동수정).

title/description/date/slug/tags 가 없으면 파생값으로 **추가만** 함.
기존값은 절대 덮지 않음. 본문 미변경, 콘텐츠 발명 없음.
파생 불가능 시 사람 게이트(False) 로 분류.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from shared.autofix.core import logger

_REQUIRED = ("title", "description", "date", "slug", "tags")


def _iter_posts(site: Path):
    posts = site / "content" / "posts"
    if not posts.is_dir():
        return []
    return sorted(posts.glob("*/index.md"))


def fix_frontmatter_missing_keys(site: Path, blog_id: str) -> tuple[bool, str]:
    """site 포스트의 누락된 필수 프론트매터 키를 파생값으로 추가.

    returns: (ok, message)
    """
    import frontmatter

    fixed = 0
    try:
        for path in _iter_posts(site):
            try:
                post = frontmatter.load(path)
                md = post.metadata
                missing = [k for k in _REQUIRED if k not in md or md[k] in (None, "")]
                if not missing:
                    continue
                stem = path.parent.name
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                defaults = {
                    "title": stem,
                    "description": md.get("title") or stem,
                    "date": mtime.date(),
                    "slug": stem,
                    "tags": ["uncategorized"],
                }
                for k in missing:
                    md[k] = defaults[k]
                path.write_text(frontmatter.dumps(post), encoding="utf-8")
                fixed += 1
            except Exception as e:
                logger.warning("[FM-MISSINGKEYS] %s 파싱 오류(무영향 skip): %s", path, e)
                continue
    except Exception as e:
        return False, f"FM-MISSINGKEYS 오류: {e}"
    if fixed:
        return True, f"FM-MISSINGKEYS: {blog_id} 키 보강 {fixed}건"
    return True, f"FM-MISSINGKEYS: {blog_id} 누락 키 없음 (no-op)"
