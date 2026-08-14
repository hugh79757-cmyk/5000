"""R12: 허용 집합 벗어난 layouts 오버라이드 정리 + junk 정리."""

from __future__ import annotations

import re
from pathlib import Path

from shared.autofix.core import logger

ALLOWED_OVERRIDES = {
    "layouts/_default/single.html",
    "layouts/archives/single.html",
    "layouts/partials/extend-head.html",
    "layouts/partials/extend_head.html",
    "layouts/partials/adsense",
    "layouts/partials/related.html",
    "layouts/partials/head/custom.html",
    "layouts/partials/head.html",
    "layouts/partials/head.xml",
    "layouts/partials/cuap-spider-links.html",
    "layouts/_default/_markup/render-link.html",
    "layouts/partials/header/components/translations.html",
    "layouts/partials/tradingview-widget.html",
    "layouts/partials/extend-article-link.html",
    "layouts/shortcodes/article.html",
    "layouts/shortcodes/lead.html",
    "layouts/shortcodes/chain-card.html",
    "layouts/shortcodes/chain-official-card.html",
    "layouts/shortcodes/dual-cta.html",
    "layouts/partials/extend-head-uncached.html",
    "layouts/partials/related-posts.html",
    "layouts/partials/adsense/top.html",
    "layouts/partials/adsense/in-article.html",
    "layouts/partials/adsense/out-of-article.html",
    "layouts/partials/breadcrumbs.html",
    "layouts/partials/series/series.html",
    "layouts/partials/author.html",
    "layouts/partials/seo/meta.html",
    "layouts/partials/seo/og.html",
    "layouts/partials/sidebar.html",
    "layouts/partials/comments.html",
    "layouts/partials/pagination.html",
    "layouts/404.html",
    "layouts/index.html",
    "layouts/search.html",
    "layouts/posts/list.html",
}

JUNK_SUFFIXES = (".DS_Store", ".bak", ".bak2", ".swp", "~", ".orig")


def fix_r12_overrides(site: Path) -> tuple[bool, str]:
    layouts = site / "layouts"
    if not layouts.is_dir():
        return True, "layouts/ 없음 — pass"

    removed = []
    junk = []
    for f in layouts.rglob("*"):
        if not f.is_file():
            continue
        rel = str(f.relative_to(site))
        if any(rel.endswith(s) for s in JUNK_SUFFIXES) or "/.DS_Store" in rel:
            junk.append(rel)
            continue

        is_allowed = False
        for allowed in ALLOWED_OVERRIDES:
            if rel == allowed or rel.startswith(allowed + "/") or rel.startswith(allowed):
                is_allowed = True
                break
        if not is_allowed:
            if f.parent.name in ("adsense", "partials", "_default"):
                pass
            removed.append(rel)

    if not removed:
        return True, f"모든 오버라이드 허용 집합 내 (정크: {len(junk)}건)"

    for rel in removed:
        f = site / rel
        if f.exists():
            f.unlink()
            logger.info(f"  R12 삭제: {rel}")

    return True, f"무단 오버라이드 {len(removed)}건 삭제 (정크: {len(junk)}건)"
