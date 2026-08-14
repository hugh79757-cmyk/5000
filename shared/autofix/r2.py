"""R2-01: 본문 이미지 URL 을 R2 버킷으로 치환 (원본 R2 URL 아는 경우만)."""

from __future__ import annotations

import re
from pathlib import Path

from shared.autofix.core import logger

R2_PATTERN = re.compile(r"pub-[0-9a-f]+\.r2\.dev")


def fix_r2_images(site: Path, blog_id: str) -> tuple[bool, str]:
    """최근 포스트의 featureimage + 본문 이미지 URL을 R2로 치환.

    주의: 원본 R2 URL이 무엇인지 모르면 치환하지 않음.
    이 함수는 featureimage 가 이미 R2 URL이면 pass, 아니면 '잔여'로 분류.
    """
    posts_dir = site / "content" / "posts"
    if not posts_dir.is_dir():
        return True, "content/posts/ 없음 — pass"

    posts = sorted(
        [d for d in posts_dir.iterdir() if d.is_dir()],
        key=lambda p: p.stat().st_mtime, reverse=True
    )[:10]

    if not posts:
        return True, "포스트 없음 — pass"

    fixed_count = 0
    remaining = []

    for post_dir in posts:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        content = idx.read_text(encoding="utf-8", errors="replace")

        fm_match = re.search(r"featureimage:\s*[\"']?([^\"'\n]+)[\"']?", content)
        if fm_match:
            url = fm_match.group(1).strip()
            if not R2_PATTERN.search(url):
                remaining.append(f"{post_dir.name}/featureimage: {url[:80]}")

        body_start = content.find("---", 3)
        body = content[body_start + 3:] if body_start >= 0 else content
        for m in re.finditer(r"""!\[[^\]]*\]\(\s*(https?://[^\)"'\s]+)""", body):
            url = m.group(1).strip()
            if not R2_PATTERN.search(url):
                remaining.append(f"{post_dir.name}/body_img: {url[:80]}")

    if not remaining:
        return True, "최근 포스트 이미지 전부 R2 호스팅 (정상)"

    return False, f"R2 아님 이미지 {len(remaining)}건 — 원본 R2 URL 미확인 (잔여 큐)"
