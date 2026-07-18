"""
Centralized editorial thumbnail generator for 5000-managed blogs.

Uses HTML/CSS (Jinja2) → Playwright screenshot → WebP → R2 upload.

Usage:
    from shared.thumbnail_generator import generate_thumbnail, list_supported_sites

    url = generate_thumbnail(
        site_id="kuta",
        slug="2026-온더고-도시락-인기-메뉴",
        title="1200만이 선택한 온더고 도시락 인기 메뉴",
        category="생활정보",
    )
    print(url)  # R2 public URL
"""

from shared.thumbnail_generator.generator import generate_thumbnail, generate_batch, split_title
from shared.thumbnail_generator.colors import (
    BLOG_PALETTES,
    get_blog_palette,
    get_accent_for_category,
    list_supported_sites,
)

__all__ = [
    "generate_thumbnail",
    "generate_batch",
    "split_title",
    "BLOG_PALETTES",
    "get_blog_palette",
    "get_accent_for_category",
    "list_supported_sites",
]
