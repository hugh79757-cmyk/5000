"""DRY RUN: Check what fix_r12 would delete across all R12 sites.

No files are modified. This is for 사전 카운트 only.
"""

from __future__ import annotations
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, "/Users/twinssn/Projects/5000")

DB_PATH = "/Users/twinssn/Projects/5000/ops_dashboard/ops.db"

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


def dry_run_r12(site: Path) -> tuple[int, int, list[str], list[str]]:
    """Returns: (junk_count, unauthorized_count, junk_paths, unauthorized_paths)"""
    layouts = site / "layouts"
    if not layouts.is_dir():
        return 0, 0, [], []

    junk = []
    unauthorized = []
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
            # Same logic as fix_r12: skip if parent is adsense/partials/_default
            if f.parent.name in ("adsense", "partials", "_default"):
                pass  # these are allowed (same as fix_r12)
            else:
                unauthorized.append(rel)
    return len(junk), len(unauthorized), junk, unauthorized


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get R12 site paths
    r12_sites = []
    for fix in conn.execute(
        "SELECT blog_id FROM pending_fixes WHERE status='proposed' AND action='fix_r12';"
    ).fetchall():
        row = conn.execute(
            "SELECT site_path FROM blog_lifecycle WHERE blog_id=?",
            (fix["blog_id"],),
        ).fetchone()
        if row and row["site_path"]:
            r12_sites.append((fix["blog_id"], row["site_path"]))

    print(f"=== R12 DRY RUN: {len(r12_sites)} sites ===\n")

    total_junk = 0
    total_unauthorized = 0
    sites_with_junk = 0
    sites_with_unauth = 0
    all_unauthorized = []

    for blog_id, site_path in sorted(r12_sites):
        site = Path(site_path)
        if not site.exists():
            print(f"  NO PATH: {blog_id} → {site_path}")
            continue
        junk_count, unauth_count, junk, unauthorized = dry_run_r12(site)
        total_junk += junk_count
        total_unauthorized += unauth_count
        if junk_count > 0:
            sites_with_junk += 1
        if unauth_count > 0:
            sites_with_unauth += 1
            for p in unauthorized:
                all_unauthorized.append((blog_id, p))
        status = ""
        if junk_count > 0 and unauth_count > 0:
            status = f" (junk: {junk_count}, unauth: {unauth_count})"
        elif junk_count > 0:
            status = f" (junk only: {junk_count})"
        elif unauth_count > 0:
            status = f" (unauthorized: {unauth_count})"
        else:
            status = " (clean)"
        print(f"  {blog_id}: {status}")

    print(f"\n=== DRY RUN SUMMARY ===")
    print(f"Total sites checked: {len(r12_sites)}")
    print(f"Total junk files (will delete): {total_junk}")
    print(f"Total unauthorized overrides (will delete): {total_unauthorized}")
    print(f"Sites with junk: {sites_with_junk}")
    print(f"Sites with unauthorized: {sites_with_unauth}")
    print(f"\n=== ALL UNAUTHORIZED FILES (by blog) ===")
    for blog_id, path in sorted(all_unauthorized):
        print(f"  {blog_id}: {path}")

    conn.close()


if __name__ == "__main__":
    main()
