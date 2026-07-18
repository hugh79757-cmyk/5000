#!/usr/bin/env python3
"""
Batch thumbnail generator for all 5000-managed Hugo sites.

Scans Hugo posts, generates editorial thumbnails via the shared Playwright
generator, uploads to R2, and updates frontmatter.

Usage:
    # All sites
    python scripts/batch_thumbnails.py

    # Single site
    python scripts/batch_thumbnails.py --site kuta-hugo

    # Missing-only (skip posts that already have cover image)
    python scripts/batch_thumbnails.py --missing-only

    # Dry run (preview only)
    python scripts/batch_thumbnails.py --dry-run

    # Resume from saved progress
    python scripts/batch_thumbnails.py --resume

    # Single post
    python scripts/batch_thumbnails.py --slug "2026-온더고-도시락-인기-메뉴"
"""

import argparse
import glob
import os
import re
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.thumbnail_generator import (
    generate_thumbnail,
    list_supported_sites,
)

PROGRESS_FILE = os.path.join(os.path.dirname(__file__), ".batch_thumbnails_progress.txt")

# ── Site configurations ─────────────────────────────────────────────────────

SITE_CONFIGS = {
    "informationhot-hugo": {
        "path": os.path.expanduser("~/Projects/informationhot-hugo"),
        "site_id": "informationhot",
        "cover_field": ("cover", "image"),    # cover.image in frontmatter
        "theme": "PaperMod",
    },
    "kuta-hugo": {
        "path": os.path.expanduser("~/Projects/kuta-hugo"),
        "site_id": "kuta",
        "cover_field": ("featureimage",),      # top-level featureimage
        "theme": "blowfish",
    },
    "rotcha-blog": {
        "path": os.path.expanduser("~/Projects/rotcha-blog"),
        "site_id": "rotcha",
        "cover_field": ("cover", "image"),
        "theme": "PaperMod",
    },
    "techpawz-hugo": {
        "path": os.path.expanduser("~/Projects/techpawz-hugo"),
        "site_id": "techpawz",
        "cover_field": ("featureimage",),
        "theme": "blowfish",
    },
    "issue-techpawz-hugo": {
        "path": os.path.expanduser("~/Projects/issue-techpawz-hugo"),
        "site_id": "issue-techpawz",
        "cover_field": ("thumbnail",),
        "theme": "blowfish",
    },
    "biz.techpawz-hugo": {
        "path": os.path.expanduser("~/Projects/biz.techpawz-hugo"),
        "site_id": "biz.techpawz",
        "cover_field": ("featureimage",),
        "theme": "blowfish",
    },
    "info.techpawz-hugo": {
        "path": os.path.expanduser("~/Projects/info.techpawz-hugo"),
        "site_id": "info.techpawz",
        "cover_field": ("featureimage",),
        "theme": "blowfish",
    },
}


# ── Frontmatter helpers ─────────────────────────────────────────────────────

def _read_frontmatter(filepath: str) -> dict | None:
    """Parse YAML frontmatter from a Hugo markdown file."""
    with open(filepath) as f:
        raw = f.read()
    parts = raw.split("---", 2)
    if len(parts) >= 3:
        try:
            return yaml.safe_load(parts[1])
        except Exception:
            return None
    return None


def _has_cover(meta: dict, cover_field: tuple) -> bool:
    """Check if the post already has a cover image set."""
    if not meta:
        return False
    if len(cover_field) == 1:
        return bool(meta.get(cover_field[0]))
    elif len(cover_field) == 2:
        parent = meta.get(cover_field[0], {}) or {}
        return bool(parent.get(cover_field[1]))
    return False


def _get_title(meta: dict) -> str:
    return (meta.get("title") or "").strip()


def _get_category(meta: dict) -> str:
    cats = meta.get("categories") or []
    if isinstance(cats, list) and cats:
        # Return the first category
        c = cats[0]
        if isinstance(c, str):
            return c
    return ""


def _update_frontmatter(filepath: str, cover_field: tuple, new_url: str) -> bool:
    """Inject or update the cover image field in frontmatter."""
    with open(filepath) as f:
        raw = f.read()

    parts = raw.split("---", 2)
    if len(parts) < 3:
        print(f"  ⚠ No frontmatter found, skipping")
        return False

    raw_fm = parts[1]

    if len(cover_field) == 1:
        # Single-level: featureimage:
        field = cover_field[0]
        if f"{field}:" in raw_fm:
            # Replace existing
            raw_fm = re.sub(
                rf"^{re.escape(field)}:.*$",
                f'{field}: "{new_url}"',
                raw_fm,
                flags=re.MULTILINE,
            )
        else:
            # Add
            raw_fm = raw_fm.rstrip() + f'\n{field}: "{new_url}"\n'
    elif len(cover_field) == 2:
        # Nested: cover.image:
        parent, child = cover_field
        cover_block = f"{parent}:\n  {child}: \"{new_url}\""
        if f"{parent}:" in raw_fm:
            # Match: parent:\n  child: "url" — explicit pattern, no lookahead fragility
            pattern = re.compile(
                rf"^{re.escape(parent)}:\s*\n\s+{re.escape(child)}:\s+\"[^\"]*\"",
                re.MULTILINE,
            )
            new_fm = pattern.sub(cover_block, raw_fm)
            if new_fm == raw_fm:
                # Fallback: try parent: line (some files may have other formats)
                raw_fm = re.sub(
                    rf"^\s*{re.escape(parent)}\.{re.escape(child)}:.*$",
                    f'  {child}: "{new_url}"',
                    raw_fm,
                    flags=re.MULTILINE,
                )
                new_fm = raw_fm
            raw_fm = new_fm
        else:
            lines = raw_fm.split("\n")
            insert_idx = len(lines) - 1
            for i in range(len(lines) - 1, -1, -1):
                stripped = lines[i].strip()
                if stripped and not stripped.startswith("#"):
                    insert_idx = i + 1
                    break
            lines.insert(insert_idx, cover_block)
            raw_fm = "\n".join(lines)

    raw = f"---{raw_fm}---{parts[2]}"
    with open(filepath, "w") as f:
        f.write(raw)
    return True


# ── Post discovery ──────────────────────────────────────────────────────────

def find_posts(site_path: str, content_subdir: str = "posts") -> list[tuple[str, str, dict]]:
    """
    Return list of (slug, filepath, meta) tuples for all non-draft posts.
    Supports both flat *.md files and directory-based posts (index.md).
    """
    posts_dir = os.path.join(site_path, "content", content_subdir)
    if not os.path.isdir(posts_dir):
        print(f"  ⚠ Content dir not found: {posts_dir}")
        return []

    posts = []

    # Directory-based posts (blowfish-style: content/posts/slug/index.md)
    for d in sorted(glob.glob(os.path.join(posts_dir, "*"))):
        if not os.path.isdir(d):
            continue
        idx = os.path.join(d, "index.md")
        if not os.path.exists(idx):
            continue
        slug = os.path.basename(d)
        meta = _read_frontmatter(idx)
        if meta and not meta.get("draft", False):
            posts.append((slug, idx, meta))

    # Flat posts (content/posts/slug.md)
    for f in sorted(glob.glob(os.path.join(posts_dir, "*.md"))):
        slug = os.path.splitext(os.path.basename(f))[0]
        # Skip if already found as directory-based
        if any(s == slug for s, _, _ in posts):
            continue
        meta = _read_frontmatter(f)
        if meta and not meta.get("draft", False):
            posts.append((slug, f, meta))

    return posts


# ── Progress tracking ───────────────────────────────────────────────────────

def _load_progress() -> set:
    if not os.path.exists(PROGRESS_FILE):
        return set()
    with open(PROGRESS_FILE) as f:
        return set(line.strip() for line in f if line.strip())


def _save_progress(slug: str):
    os.makedirs(os.path.dirname(PROGRESS_FILE) or ".", exist_ok=True)
    with open(PROGRESS_FILE, "a") as f:
        f.write(f"{slug}\n")


# ── Main ────────────────────────────────────────────────────────────────────

def process_site(
    site_name: str,
    config: dict,
    missing_only: bool = False,
    dry_run: bool = False,
    progress_set: set | None = None,
):
    """Process all posts in a single Hugo site."""
    site_path = config["path"]
    site_id = config["site_id"]
    cover_field = config["cover_field"]

    print(f"\n{'='*60}")
    print(f"Site: {site_name} (ID: {site_id}, Theme: {config['theme']})")
    print(f"Path: {site_path}")
    print(f"{'='*60}")

    if not os.path.isdir(site_path):
        print(f"  ✗ Site path not found, skipping")
        return {"site": site_name, "total": 0, "skipped": 0, "generated": 0, "failed": 0, "updated": 0}

    posts = find_posts(site_path)
    stats = {"site": site_name, "total": len(posts), "skipped": 0, "generated": 0, "failed": 0, "updated": 0}

    if not posts:
        print(f"  No posts found")
        return stats

    for idx, (slug, filepath, meta) in enumerate(posts):
        # Skip if already done (resume mode)
        if progress_set is not None and slug in progress_set:
            stats["skipped"] += 1
            continue

        # Skip if already has cover (--missing-only mode)
        if missing_only and _has_cover(meta, cover_field):
            stats["skipped"] += 1
            continue

        title = _get_title(meta)
        category = _get_category(meta)

        if not title:
            print(f"  ⚠ {slug}: missing title, skipping")
            stats["skipped"] += 1
            continue

        print(f"  [{stats['generated'] + stats['failed'] + 1}/{stats['total']}] {slug}")
        print(f"    title: {title[:50]}")
        print(f"    category: {category}")

        if dry_run:
            print(f"    [dry-run] Would generate + upload thumbnail")
            stats["generated"] += 1
            continue

        # Generate thumbnail + upload to R2
        try:
            url = generate_thumbnail(
                site_id=site_id,
                slug=slug,
                title=title,
                category=category,
                upload=True,
            )
        except Exception as e:
            print(f"    ✗ Generation failed: {e}")
            stats["failed"] += 1
            _save_progress(slug) if not dry_run else None
            continue

        if not url:
            print(f"    ✗ R2 upload returned no URL")
            stats["failed"] += 1
            _save_progress(slug) if not dry_run else None
            continue

        stats["generated"] += 1
        print(f"    ✓ Uploaded: {url}")

        # Update frontmatter
        if _update_frontmatter(filepath, cover_field, url):
            stats["updated"] += 1
            _save_progress(slug) if not dry_run else None
        else:
            print(f"    ⚠ Failed to update frontmatter")

        # Gentle rate limiting
        time.sleep(0.3)

    print(f"  → Done: {stats['generated']} generated, {stats['updated']} updated, {stats['failed']} failed, {stats['skipped']} skipped")
    return stats


def process_site_batch(
    site_name: str,
    config: dict,
    missing_only: bool = False,
    dry_run: bool = False,
    progress_set: set | None = None,
):
    """Process all posts in a site using a single shared Playwright browser session."""
    from shared.thumbnail_generator import generate_batch

    site_path = config["path"]
    site_id = config["site_id"]
    cover_field = config["cover_field"]

    print(f"\n{'='*60}")
    print(f"Site: {site_name} (ID: {site_id}, Theme: {config['theme']})")
    print(f"Path: {site_path}")
    print(f"{'='*60}")

    if not os.path.isdir(site_path):
        print(f"  ✗ Site path not found, skipping")
        return {"site": site_name, "total": 0, "skipped": 0, "generated": 0, "failed": 0, "updated": 0}

    all_posts = find_posts(site_path)
    stats = {"site": site_name, "total": len(all_posts), "skipped": 0, "generated": 0, "failed": 0, "updated": 0}

    if not all_posts:
        print(f"  No posts found")
        return stats

    # First pass: collect pending posts
    pending = []
    for slug, filepath, meta in all_posts:
        if progress_set is not None and slug in progress_set:
            stats["skipped"] += 1
            continue
        if missing_only and _has_cover(meta, cover_field):
            stats["skipped"] += 1
            continue
        title = _get_title(meta)
        if not title:
            print(f"  ⚠ {slug}: missing title, skipping")
            stats["skipped"] += 1
            continue
        category = _get_category(meta)
        pending.append({"slug": slug, "filepath": filepath, "title": title, "category": category})

    if not pending:
        print(f"  No pending posts to process")
        return stats

    print(f"  Pending: {len(pending)} posts")

    if dry_run:
        stats["generated"] = len(pending)
        for p in pending:
            print(f"    [dry-run] Would generate: {p['slug']}")
        return stats

    # Batch process with shared browser
    def on_progress(slug, success, result):
        if success and result:
            filepath = next(p["filepath"] for p in pending if p["slug"] == slug)
            if _update_frontmatter(filepath, cover_field, result):
                stats["updated"] += 1
            _save_progress(slug)
            stats["generated"] += 1
            print(f"    ✓ {slug}")
        else:
            stats["failed"] += 1
            print(f"    ✗ {slug}: {result}")

    try:
        generate_batch(
            site_id=site_id,
            posts=pending,
            template_name="default.html",
            progress_callback=on_progress,
        )
    except KeyboardInterrupt:
        print(f"\n  Interrupted. Run with --resume to continue.")

    print(f"  → Done: {stats['generated']} generated, {stats['updated']} updated, {stats['failed']} failed, {stats['skipped']} skipped")
    return stats


def main():
    parser = argparse.ArgumentParser(description="Batch thumbnail generator for all Hugo sites")
    parser.add_argument("--site", type=str, help="Specific site name (e.g., kuta-hugo)")
    parser.add_argument("--missing-only", action="store_true", help="Only posts without cover image")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no changes")
    parser.add_argument("--resume", action="store_true", help="Resume from saved progress")
    parser.add_argument("--slug", type=str, help="Single slug to process (across all sites)")
    args = parser.parse_args()

    if args.slug:
        # Find the slug across all sites
        for site_name, config in SITE_CONFIGS.items():
            posts = find_posts(config["path"])
            for slug, filepath, meta in posts:
                if slug == args.slug:
                    print(f"Found in {site_name}: {filepath}")
                    title = _get_title(meta)
                    category = _get_category(meta)
                    url = generate_thumbnail(
                        site_id=config["site_id"],
                        slug=slug,
                        title=title,
                        category=category,
                        upload=not args.dry_run,
                    )
                    if url and not args.dry_run:
                        _update_frontmatter(filepath, config["cover_field"], url)
                    print(f"Result: {url}")
                    return
        print(f"Post '{args.slug}' not found in any site")
        return

    progress_set = _load_progress() if args.resume else None
    total_stats = {"total_posts": 0, "total_generated": 0, "total_failed": 0, "total_updated": 0}

    sites_to_process = [args.site] if args.site else list(SITE_CONFIGS.keys())

    for site_name in sites_to_process:
        if site_name not in SITE_CONFIGS:
            print(f"Unknown site: {site_name}. Known: {list(SITE_CONFIGS.keys())}")
            continue

        stats = process_site_batch(
            site_name,
            SITE_CONFIGS[site_name],
            missing_only=args.missing_only,
            dry_run=args.dry_run,
            progress_set=progress_set,
        )
        total_stats["total_posts"] += stats["total"]
        total_stats["total_generated"] += stats["generated"]
        total_stats["total_failed"] += stats["failed"]
        total_stats["total_updated"] += stats["updated"]

    if args.dry_run:
        print(f"\n{'='*60}")
        print("DRY RUN — no changes made.")
    print(f"\nTotal: {total_stats['total_generated']} generated, {total_stats['total_updated']} updated, {total_stats['total_failed']} failed across all sites")


if __name__ == "__main__":
    main()
