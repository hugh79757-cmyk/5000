#!/usr/bin/env python3
"""
fix_repeated_image_urls.py — Batch fix for image URL token repetition bugs.

Scans Hugo blog content directories for image URLs with repeated substrings
(LLM stutter artifacts) and strips the repeating pattern.

Usage:
    # Dry-run: scan only, no changes
    python3 scripts/fix_repeated_image_urls.py --dry-run

    # Fix all infected files
    python3 scripts/fix_repeated_image_urls.py

    # Fix specific blogs only
    python3 scripts/fix_repeated_image_urls.py --blogs health-hugo pet-hugo

    # Backup to custom dir instead of /tmp
    python3 scripts/fix_repeated_image_urls.py --backup-dir /var/backups
"""

import argparse
import logging
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fix_repeated_urls")

# Blog scan directories
SCAN_DIRS = [
    # CUAP (10)
    "/Users/twinssn/Projects/cuap/appliance-hugo",
    "/Users/twinssn/Projects/cuap/baby-hugo",
    "/Users/twinssn/Projects/cuap/beauty-hugo",
    "/Users/twinssn/Projects/cuap/camping-hugo",
    "/Users/twinssn/Projects/cuap/fitness-hugo",
    "/Users/twinssn/Projects/cuap/health-hugo",
    "/Users/twinssn/Projects/cuap/interior-hugo",
    "/Users/twinssn/Projects/cuap/kitchen-hugo",
    "/Users/twinssn/Projects/cuap/laptop-hugo",
    "/Users/twinssn/Projects/cuap/pet-hugo",
    # CAP (rotcha.kr)
    "/Users/twinssn/Projects/CAP/hotissue-hugo",
    "/Users/twinssn/Projects/CAP/compare-hugo",
    "/Users/twinssn/Projects/CAP/deal-hugo",
    "/Users/twinssn/Projects/CAP/ev-hugo",
    "/Users/twinssn/Projects/CAP/guide-hugo",
    "/Users/twinssn/Projects/CAP/tco-hugo",
]

# Also scan these for non-Hugo content
EXTRA_SCAN_DIRS = [
    "/Users/twinssn/Projects/STAP",
]


def has_repeated_pattern(url, min_repeat_len=4, min_repeats=5):
    """Check if URL has a substring repeated consecutively >= min_repeats times.
    Returns (pattern, count, position) or None."""
    url_str = url.rstrip("/")
    url_len = len(url_str)
    for sub_len in range(min_repeat_len, min(50, url_len // min_repeats + 1)):
        for start in range(url_len - sub_len * min_repeats + 1):
            sub = url_str[start:start + sub_len]
            count = 0
            pos = start
            while pos + sub_len <= url_len and url_str[pos:pos + sub_len] == sub:
                count += 1
                pos += sub_len
            if count >= min_repeats:
                return sub, count, start
    return None


def extract_clean_url(url):
    """Extract the valid base URL by removing repeated suffix."""
    result = has_repeated_pattern(url)
    if not result:
        return url
    sub, count, pos = result
    return url[:pos]


def scan_file_for_abnormal_urls(filepath):
    """Scan a single file for abnormal image URLs.
    Returns list of (lineno, url, length, issues_list, clean_url)."""
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        for lineno, line in enumerate(content.split("\n"), 1):
            # Find markdown image URLs
            img_matches = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", line)
            for alt, url in img_matches:
                issues = []
                clean_url = None

                # Check for repeated pattern
                result = has_repeated_pattern(url)
                if result:
                    sub, count, pos = result
                    clean_url = extract_clean_url(url)
                    issues.append(f"REPEAT(pattern='{sub}' x{count} at pos {pos})")
                    issues.append(f"LEN={len(url)}→{len(clean_url)}")

                if issues and clean_url != url:
                    findings.append((lineno, url, len(url), issues, clean_url))

            # Also check raw HTML <img> tags
            img_html = re.findall(r'<img[^>]+src="([^"]+)"', line)
            for url in img_html:
                result = has_repeated_pattern(url)
                if result:
                    sub, count, pos = result
                    clean_url = extract_clean_url(url)
                    issues = [f"REPEAT(pattern='{sub}' x{count} at pos {pos})",
                              f"LEN={len(url)}→{len(clean_url)}"]
                    findings.append((lineno, url, len(url), issues, clean_url))
    except Exception as e:
        logger.error(f"  Error reading {filepath}: {e}")
    return findings


def fix_file_content(filepath, findings, dry_run=False):
    """Fix all abnormal URLs in a file."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    modified = False
    for lineno, original_url, length, issues, clean_url in findings:
        if clean_url:
            # Replace the URL in content (using quoted string for safety)
            if original_url in content:
                # For markdown images: ![alt](url)
                md_pattern = f"({re.escape(original_url)})"
                new_content = content.replace(original_url, clean_url, 1)
                if new_content != content:
                    content = new_content
                    modified = True
                    logger.info(f"  ✅ Fixed: {os.path.basename(filepath)}:{lineno} "
                                f"({length}→{len(clean_url)} chars)")
                else:
                    logger.warning(f"  ⚠️  URL not found in content for replacement: "
                                   f"{os.path.basename(filepath)}:{lineno}")

    if modified and not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    return modified


def backup_file(filepath, backup_dir):
    """Create a timestamped backup of the file."""
    rel_path = filepath.lstrip("/").replace("/", "_")
    backup_path = os.path.join(backup_dir, rel_path)
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy2(filepath, backup_path)
    return backup_path


def scan_blog(blog_path, blog_name):
    """Scan a Hugo blog for infected files."""
    content_dir = os.path.join(blog_path, "content", "posts")
    if not os.path.isdir(content_dir):
        alt = os.path.join(blog_path, "content")
        if os.path.isdir(alt):
            content_dir = alt
        else:
            return [], 0

    findings = []
    post_count = 0
    for root, dirs, files in os.walk(content_dir):
        for fname in sorted(files):
            if fname.endswith(".md"):
                post_count += 1
                fpath = os.path.join(root, fname)
                file_findings = scan_file_for_abnormal_urls(fpath)
                if file_findings:
                    findings.append((fpath, file_findings))

    return findings, post_count


def main():
    parser = argparse.ArgumentParser(
        description="Fix image URL token repetition bugs across Hugo blogs"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Scan only, don't modify any files")
    parser.add_argument("--blogs", nargs="+", default=None,
                        help="Specific blog directories to scan (e.g., health-hugo pet-hugo)")
    parser.add_argument("--backup-dir", default=None,
                        help=f"Backup directory (default: /tmp/url-fix-{datetime.now().strftime('%Y%m%d')})")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine blogs to scan
    scan_targets = SCAN_DIRS + EXTRA_SCAN_DIRS
    if args.blogs:
        # Filter by blog name (partial match)
        scan_targets = [
            d for d in scan_targets
            if any(b in os.path.basename(d) for b in args.blogs)
        ]
        if not scan_targets:
            logger.error(f"No matching blogs found for: {args.blogs}")
            sys.exit(1)

    # Setup backup dir
    backup_dir = args.backup_dir or f"/tmp/url-fix-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Scan all blogs
    all_findings = {}
    total_infected_files = 0
    total_infected_urls = 0

    for scan_path in sorted(scan_targets):
        blog_name = os.path.basename(scan_path)
        if not os.path.isdir(scan_path):
            logger.info(f"[SKIP] {blog_name}: not found at {scan_path}")
            continue

        blog_findings, post_count = scan_blog(scan_path, blog_name)
        infected_files = len(blog_findings)
        infected_urls = sum(len(f[1]) for f in blog_findings)
        total_infected_files += infected_files
        total_infected_urls += infected_urls

        if blog_findings:
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 {blog_name}: {infected_files}/{post_count} infected files, "
                        f"{infected_urls} infected URLs")
            logger.info(f"{'='*60}")

            for fpath, file_findings in sorted(blog_findings):
                rel_path = fpath
                if scan_path in rel_path:
                    rel_path = rel_path[len(scan_path) + 1:]
                for lineno, url, length, issues, clean_url in file_findings:
                    issues_str = " | ".join(issues)
                    logger.info(f"  📄 {rel_path}:{lineno}")
                    logger.info(f"     Issues: {issues_str}")
                    logger.info(f"     URL: {url[:120]}...")
                    if clean_url:
                        logger.info(f"     FIX: {clean_url[:120]}...")
                    logger.info("")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SCAN SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total infected files: {total_infected_files}")
    logger.info(f"Total infected URLs: {total_infected_urls}")

    if total_infected_urls == 0:
        logger.info("✅ No infected URLs found. Nothing to fix.")
        return

    if args.dry_run:
        logger.info(f"\n🔍 Dry-run mode: {total_infected_urls} URLs would be fixed.")
        logger.info(f"   Run without --dry-run to apply fixes.")
        return

    # Apply fixes
    logger.info(f"\n{'='*60}")
    logger.info("APPLYING FIXES")
    logger.info(f"{'='*60}")

    os.makedirs(backup_dir, exist_ok=True)
    fixed_files = 0
    fixed_urls = 0

    for scan_path in sorted(scan_targets):
        blog_name = os.path.basename(scan_path)
        if not os.path.isdir(scan_path):
            continue

        blog_findings, _ = scan_blog(scan_path, blog_name)
        for fpath, file_findings in blog_findings:
            # Backup
            backup_path = backup_file(fpath, backup_dir)

            # Fix
            modified = fix_file_content(fpath, file_findings, dry_run=False)
            if modified:
                fixed_files += 1
                fixed_urls += len(file_findings)
                logger.info(f"  📦 Backup: {backup_path}")

    logger.info(f"\n{'='*60}")
    logger.info("FIX COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Files fixed: {fixed_files}")
    logger.info(f"URLs fixed: {fixed_urls}")
    logger.info(f"Backups: {backup_dir}")
    logger.info("")  # trailing newline


if __name__ == "__main__":
    main()
