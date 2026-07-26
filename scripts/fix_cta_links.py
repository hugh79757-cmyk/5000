#!/usr/bin/env python3
"""fix_cta_links.py — 기존 CUAP 포스트의 markdown CTA 링크를 HTML 버튼으로 일괄 변환.

Replaces:
  [텍스트](https://link.coupang.com/...) → <div ...><a class="btn-price-check" href="URL">🛒 텍스트</a></div>
Also strips inline styles from existing <div class="cta-box"> (CSS now handles styling).

Usage:
    python3 scripts/fix_cta_links.py                          # 실제 변환
    python3 scripts/fix_cta_links.py --dry-run                  # 변경 preview
    python3 scripts/fix_cta_links.py --blog kitchen-hugo       # 특정 블로그만
"""

import argparse
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

# ── Configuration ──
CUAP_BASE = "/Users/twinssn/Projects/cuap"
BLOGS = [
    "health-hugo", "beauty-hugo", "fitness-hugo", "kitchen-hugo",
    "baby-hugo", "pet-hugo", "camping-hugo", "laptop-hugo",
    "appliance-hugo", "interior-hugo",
]

# Regex patterns
CTA_PATTERN = re.compile(
    r'\[([^\]]+)\]\((https?://(?:link\.coupang\.com|www\.coupang\.com)[^)]+)\)'
)
CTA_REPLACEMENT = (
    r'<div style="text-align:center;margin:1.5rem 0">'
    r'<a class="btn-price-check" href="\2">🛒 \1</a></div>'
)

# CTA-box inline style patterns
CTA_BOX_STYLE_PATTERN = re.compile(r'<div class="cta-box" style="[^"]*">')
CTA_BOX_P_STYLE_1 = re.compile(
    r'<p style="font-size:16px;font-weight:700;margin:0 0 8px">'
)
CTA_BOX_P_STYLE_2 = re.compile(
    r'<p style="font-size:14px;margin:0 0 12px;color:#555">'
)


def sha256_file(filepath: str) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def process_file(filepath: str, dry_run: bool = False) -> dict:
    """Process a single index.md file, return stats dict.

    Returns:
        dict with keys: modified (bool), cta_converted (int), cta_box_stripped (int), sha256_before (str)
    """
    result = {
        "modified": False,
        "cta_converted": 0,
        "cta_box_stripped": 0,
        "sha256_before": sha256_file(filepath),
    }

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content

    # 1. Convert markdown CTA links to HTML buttons
    new_content, cta_count = CTA_PATTERN.subn(CTA_REPLACEMENT, content)
    if cta_count > 0:
        result["cta_converted"] = cta_count
        content = new_content

    # 2. Strip inline styles from existing cta-box divs
    new_content, box_count = CTA_BOX_STYLE_PATTERN.subn(
        '<div class="cta-box">', content
    )
    if box_count > 0:
        result["cta_box_stripped"] += box_count
        content = new_content

    new_content, p_count = CTA_BOX_P_STYLE_1.subn("<p>", content)
    if p_count > 0:
        result["cta_box_stripped"] += p_count
        content = new_content

    new_content, p_count = CTA_BOX_P_STYLE_2.subn("<p>", content)
    if p_count > 0:
        result["cta_box_stripped"] += p_count
        content = new_content

    if content != original:
        result["modified"] = True
        if not dry_run:
            # Create .bak backup
            bak_path = filepath + ".bak"
            shutil.copy2(filepath, bak_path)
            # Write modified content
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            # Verify SHA256 changed
            sha_after = sha256_file(filepath)
            if sha_after == result["sha256_before"]:
                print(f"  ⚠️  WARNING: {filepath} — SHA256 unchanged after write!")
            result["sha256_after"] = sha_after
        else:
            # Dry-run: show diff preview
            _show_diff(Path(filepath).name, original, content)

    return result


def _show_diff(label: str, original: str, modified: str) -> None:
    """Show a compact diff for dry-run mode."""
    orig_lines = original.split("\n")
    mod_lines = modified.split("\n")
    changed = False
    for i, (o, m) in enumerate(zip(orig_lines, mod_lines)):
        if o != m:
            if not changed:
                print(f"  --- {label}")
                print(f"  +++ {label}")
                changed = True
            # Show context: 1 line before
            if i > 0 and (i == 0 or orig_lines[i - 1] == mod_lines[i - 1]):
                pass  # context already shown
            print(f"  -{o}")
            print(f"  +{m}")
    if len(orig_lines) != len(mod_lines):
        for i in range(min(len(orig_lines), len(mod_lines)), max(len(orig_lines), len(mod_lines))):
            if i < len(orig_lines):
                print(f"  -{orig_lines[i]}")
            if i < len(mod_lines):
                print(f"  +{mod_lines[i]}")


def scan_blog(blog_id: str, dry_run: bool = False) -> dict:
    """Scan all posts in a single CUAP blog, return aggregate stats.

    Returns:
        dict with keys: files_scanned (int), files_modified (int),
                        cta_converted (int), cta_box_stripped (int), errors (list)
    """
    blog_path = os.path.join(CUAP_BASE, blog_id, "content", "posts")
    stats = {
        "files_scanned": 0,
        "files_modified": 0,
        "cta_converted": 0,
        "cta_box_stripped": 0,
        "errors": [],
    }

    if not os.path.isdir(blog_path):
        stats["errors"].append(f"Blog path not found: {blog_path}")
        return stats

    posts_dir = Path(blog_path)
    for index_file in sorted(posts_dir.glob("*/index.md")):
        stats["files_scanned"] += 1
        try:
            result = process_file(str(index_file), dry_run=dry_run)
            if result["modified"]:
                stats["files_modified"] += 1
                stats["cta_converted"] += result["cta_converted"]
                stats["cta_box_stripped"] += result["cta_box_stripped"]
        except Exception as e:
            stats["errors"].append(f"{index_file}: {e}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="CUAP 포스트 markdown CTA 링크를 HTML 버튼으로 일괄 변환"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="변경 preview만 표시 (실제 수정 안함)",
    )
    parser.add_argument(
        "--blog",
        type=str,
        default=None,
        help="특정 블로그만 처리 (예: kitchen-hugo)",
    )
    args = parser.parse_args()

    blogs_to_process = [args.blog] if args.blog else BLOGS
    mode = "DRY-RUN" if args.dry_run else "LIVE"

    print(f"CUAP CTA 링크 변환 — Mode: {mode}")
    print(f"스캔 대상 블로그: {', '.join(blogs_to_process)}")
    print()

    totals = {
        "files_scanned": 0,
        "files_modified": 0,
        "cta_converted": 0,
        "cta_box_stripped": 0,
        "errors": 0,
    }

    for blog_id in blogs_to_process:
        print(f"  ── {blog_id} ──")
        stats = scan_blog(blog_id, dry_run=args.dry_run)
        print(
            f"  → {stats['files_scanned']} files, "
            f"{stats['files_modified']} modified, "
            f"{stats['cta_converted']} CTA links, "
            f"{stats['cta_box_stripped']} inline styles stripped"
        )
        if stats["errors"]:
            for err in stats["errors"][:5]:
                print(f"  ⚠️  {err}")
            if len(stats["errors"]) > 5:
                print(f"  ⚠️  ... and {len(stats['errors']) - 5} more errors")
            totals["errors"] += len(stats["errors"])
        print()
        totals["files_scanned"] += stats["files_scanned"]
        totals["files_modified"] += stats["files_modified"]
        totals["cta_converted"] += stats["cta_converted"]
        totals["cta_box_stripped"] += stats["cta_box_stripped"]

    print("═" * 50)
    print("Summary:")
    print(f"  Files scanned:     {totals['files_scanned']:,}")
    print(f"  Files modified:    {totals['files_modified']:,}")
    print(f"  CTA links converted: {totals['cta_converted']:,}")
    print(f"  CTA-box inline stripped: {totals['cta_box_stripped']:,}")
    print(f"  Errors:            {totals['errors']}")
    if args.dry_run:
        print("\n⚠️  DRY-RUN: No files were modified. Run without --dry-run to apply.")
    else:
        print("\n✅ 변환 완료. .bak 백업 파일이 생성되었습니다.")


if __name__ == "__main__":
    main()
