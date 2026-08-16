"""FM-FEATUREIMAGE: featureimage URL 정화 (안전등급 자동수정).

shared/publishers/hugo_writer.sanitize_featureimage_url (IMAGE-GUARD) 를
프론트매터 featureimage 필드에 적용. 본문 미변경.
정화 불가능(빈 문자열 반환) 시 사람 게이트(False) 로 분류.
"""

from __future__ import annotations

import re
from pathlib import Path

from shared.autofix.core import logger
from shared.publishers.hugo_writer import sanitize_featureimage_url

# 토큰 반복(LLM 아티팩트: gLozv0gLozv0...) 탐지 (frontmatter check 와 동일 기준)
_TOKEN_REPEAT = re.compile(r"(.{4,})\1{2,}")

# featureimage + stock-hugo Blowfish variant(thumbnail) 동시 정화 대상 키
_FM_URL_KEYS = ("featureimage", "thumbnail")


def _iter_posts(site: Path):
    posts = site / "content" / "posts"
    if not posts.is_dir():
        return []
    return sorted(posts.glob("*/index.md"))


def _clean_fm_url(url: str) -> str:
    """IMAGE-GUARD 정화: 토큰 반복 / 비정상 문자 / 비-http 제거 후 길이 축소.

    정화 불가(빈 문자열) → 호출부에서 사람 게이트로 분류.
    """
    if not url:
        return ""
    url = url.strip()
    # 비정상 문자(공백·백슬래시) 또는 비-http → 정화 불가
    if re.search(r"[\s\\]", url):
        return ""
    if not url.startswith(("http://", "https://")):
        return ""
    # 토큰 반복(LLM 아티팩트) 축소 — 첫 발생만 유지
    collapsed = _TOKEN_REPEAT.sub(r"\1", url)
    if collapsed != url:
        url = collapsed
    # 길이 초과는 hugo_writer IMAGE-GUARD 가 빈 문자열로 축소(기본 썸네일)
    return sanitize_featureimage_url(url)


def fix_featureimage_url_sanitize(site: Path, blog_id: str) -> tuple[bool, str]:
    """site 포스트의 featureimage/thumbnail URL을 IMAGE-GUARD 규칙으로 정화.

    stock-hugo Blowfish variant(`thumbnail:`) 도 featureimage 와 동일하게 정화.
    본문 미변경. 정화 불가능(빈 문자열 반환) 시 사람 게이트(False) 로 분류.

    returns: (ok, message)
    """
    import frontmatter

    fixed = 0
    unsafe = 0
    try:
        for path in _iter_posts(site):
            try:
                post = frontmatter.load(path)
                keys = [k for k in _FM_URL_KEYS if k in post.metadata]
                if not keys:
                    continue
                changed = False
                unsafe_post = False
                for k in keys:
                    url = post.metadata.get(k, "")
                    if not url:
                        continue
                    cleaned = _clean_fm_url(url)
                    if cleaned == url:
                        continue
                    if not cleaned:
                        unsafe_post = True
                        continue
                    post.metadata[k] = cleaned
                    changed = True
                if unsafe_post:
                    unsafe += 1
                    continue
                if not changed:
                    continue
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
        return True, f"FM-FEATUREIMAGE: {blog_id} featureimage/thumbnail 정화 {fixed}건"
    return True, f"FM-FEATUREIMAGE: {blog_id} 정화 대상 없음 (no-op)"
