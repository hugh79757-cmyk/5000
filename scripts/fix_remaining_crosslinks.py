#!/usr/bin/env python3
"""fix_remaining_crosslinks.py — 잔여 404 크로스링크 일괄 수정

Phase 49-B Step 2. Scans all 10 CUAP blogs, finds broken crosslinks (404),
matches them to actual posts on the target blog using keyword matching,
and replaces the href with the correct URL.

Strategy:
  1. Extract keyword from link text (e.g., "제습기 추천" → "제습기")
  2. Search target blog's content/posts/ for directory names containing the keyword
  3. If exactly one match → use it
  4. If multiple matches → pick the most recently created post
  5. If no match → fuzzy match with difflib SequenceMatcher
  6. If best similarity < threshold → skip (log for manual review)

Usage:
    # Dry-run only (no changes)
    python3 scripts/fix_remaining_crosslinks.py --dry-run

    # Apply fixes (backs up originals to /tmp/crosslink_fix_backup/)
    python3 scripts/fix_remaining_crosslinks.py

    # Fix a single blog
    python3 scripts/fix_remaining_crosslinks.py --blog baby-hugo
"""

import glob
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher

# ── Configuration ──────────────────────────────────────────────────────────
CUAP_ROOT = "/Users/twinssn/Projects/CUAP"
BACKUP_ROOT = "/tmp/crosslink_fix_backup"

CUAP_BLOGS = [
    "appliance-hugo",
    "baby-hugo",
    "beauty-hugo",
    "camping-hugo",
    "fitness-hugo",
    "health-hugo",
    "interior-hugo",
    "kitchen-hugo",
    "laptop-hugo",
    "pet-hugo",
]

SUBDOMAIN_TO_BLOG = {
    "appliance": "appliance-hugo",
    "baby": "baby-hugo",
    "beauty": "beauty-hugo",
    "camping": "camping-hugo",
    "fitness": "fitness-hugo",
    "health": "health-hugo",
    "interior": "interior-hugo",
    "kitchen": "kitchen-hugo",
    "laptop": "laptop-hugo",
    "pet": "pet-hugo",
}

DOMAIN_TO_SUBDOMAIN = {v: k for k, v in SUBDOMAIN_TO_BLOG.items()}

# Regex patterns (same as scan script)
HREF_PATTERN = re.compile(
    r'href="https://([\w-]+)\.informationhot\.kr/posts/([^"/]+)/"'
    r'|href=\\"https://([\w-]+)\.informationhot\.kr/posts/([^"\\]+)\\"'
)
SIMILARITY_THRESHOLD = 0.3  # minimum SequenceMatcher ratio to auto-fix


def get_link_text(content: str, href: str) -> str:
    """Extract visible link text from the <a> tag."""
    escaped_href = re.escape(href)
    for quote in ('"', '\\"'):
        pattern = rf'href={re.escape(quote)}{escaped_href}{re.escape(quote)}[^>]*>([^<]+)<'
        m = re.search(pattern, content)
        if m:
            text = m.group(1).strip()
            text = re.sub(r'^[^\w\s]+', '', text).strip()
            return text
    return ""


def extract_keywords(link_text: str, url_slug: str) -> list:
    """Extract search keywords from link text and URL slug.
    
    Returns a prioritized list of keyword variants.
    """
    keywords = []

    # 1. From link text (most reliable)
    if link_text:
        # Remove duplicate "추천" like "핸드블렌더 추천 추천" → "핸드블렌더 추천"
        clean = re.sub(r'추천\s*추천', '추천', link_text)
        # Remove "추천" suffix for matching (directory names include many keywords)
        stem = clean.replace("추천", "").strip()
        if stem:
            keywords.append(stem)
        keywords.append(clean)
        # Tokens for individual matching
        tokens = [t.strip() for t in re.split(r'[\s,]+', clean) if len(t.strip()) >= 2]
        keywords.extend(tokens)

    # 2. From URL slug (strip date prefix like "20260722-")
    if url_slug:
        # Remove date prefix
        clean_slug = re.sub(r'^20\d{6}-', '', url_slug)
        # Remove trailing slashes
        clean_slug = clean_slug.rstrip('/')
        if clean_slug and clean_slug != url_slug:
            keywords.append(clean_slug)
        # Also try with Korean normalization (replace hyphens with spaces)
        korean_normalized = clean_slug.replace('-', ' ')
        if korean_normalized != clean_slug:
            keywords.append(korean_normalized)

    return keywords


def find_best_slug(target_blog: str, keywords: list) -> tuple:
    """Find the best matching slug on the target blog.

    Returns (slug, similarity) or (None, 0).
    """
    posts_dir = os.path.join(CUAP_ROOT, target_blog, "content", "posts")
    if not os.path.isdir(posts_dir):
        return None, 0

    all_slugs = []
    for entry in os.listdir(posts_dir):
        d = os.path.join(posts_dir, entry)
        if os.path.isdir(d):
            all_slugs.append((entry, os.path.getmtime(d)))

    # Sort by mtime (newest first for tie-breaking)
    all_slugs.sort(key=lambda x: x[1], reverse=True)

    best_slug = None
    best_score = 0
    best_match_type = None  # "substring" or "fuzzy"

    for keyword in keywords:
        if not keyword or len(keyword) < 2:
            continue
        for slug, _ in all_slugs:
            if keyword in slug:
                # Direct substring match: base score of 0.6 + bonus for longer keyword
                score = 0.6 + min(len(keyword) / 20.0, 0.3)
                if score > best_score:
                    best_score = score
                    best_slug = slug
                    best_match_type = "substring"

    if best_slug and best_score >= SIMILARITY_THRESHOLD:
        return best_slug, best_score

    # Fuzzy match fallback — only for keywords >= 4 chars
    for keyword in keywords:
        if not keyword or len(keyword) < 4:
            continue
        for slug, _ in all_slugs:
            ratio = SequenceMatcher(None, keyword.lower(), slug.lower()).ratio()
            if ratio > best_score:
                best_score = ratio
                best_slug = slug
                best_match_type = "fuzzy"

    if best_slug and best_score >= SIMILARITY_THRESHOLD:
        return best_slug, best_score

    return None, best_score


def fix_file(md_path: str, content: str, dry_run: bool) -> dict:
    """Fix all broken crosslinks in a single file.
    
    Returns dict with stats: fixed, skipped, errors.
    """
    blog_id = md_path.replace(CUAP_ROOT + "/", "").split("/")[0]
    result = {"fixed": 0, "skipped": 0, "errors": 0, "changes": []}

    # Find all crosslink hrefs
    for m in HREF_PATTERN.finditer(content):
        sub = m.group(1) or m.group(3)
        slug = m.group(2) or m.group(4)
        slug = slug.rstrip('/')  # Strip trailing slashes from captured slug
        target_blog = SUBDOMAIN_TO_BLOG.get(sub)
        if not target_blog:
            continue

        href = f"https://{sub}.informationhot.kr/posts/{slug}/"

        # Skip if target slug exists on disk
        target_dir = os.path.join(CUAP_ROOT, target_blog, "content", "posts", slug)
        if os.path.isdir(target_dir):
            continue

        # Extract link text and keywords
        link_text = get_link_text(content, href)
        keywords = extract_keywords(link_text, slug)

        # Find best matching slug
        best_slug, score = find_best_slug(target_blog, keywords)

        if best_slug and score >= SIMILARITY_THRESHOLD:
            correct_href = f"https://{sub}.informationhot.kr/posts/{best_slug}/"
            old_href_short = slug[:40]
            new_href_short = best_slug[:40]
            result["changes"].append({
                "old_href": href,
                "new_href": correct_href,
                "old_slug": slug,
                "new_slug": best_slug,
                "link_text": link_text,
                "score": round(score, 3),
                "target_blog": target_blog,
            })
            content = content.replace(href, correct_href)
            result["fixed"] += 1
        else:
            result["skipped"] += 1
            result["changes"].append({
                "old_href": href,
                "new_href": None,
                "old_slug": slug,
                "new_slug": None,
                "link_text": link_text,
                "score": round(score, 3),
                "target_blog": target_blog,
                "reason": f"No match found (best score={score:.3f})",
            })

    # Write back if changes made
    if result["fixed"] > 0 and not dry_run:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)

    return result


def main():
    dry_run = "--dry-run" in sys.argv
    blogs_to_fix = CUAP_BLOGS

    for arg in sys.argv[1:]:
        if arg.startswith("--blog="):
            blog_filter = arg.split("=", 1)[1]
            if blog_filter in CUAP_BLOGS:
                blogs_to_fix = [blog_filter]
            else:
                print(f"Unknown blog: {blog_filter}")
                sys.exit(1)

    # ── Phase 1: Re-scan all crosslinks ──
    print("=" * 72)
    print("  Step 1: 크로스링크 전수 스캔 중...")
    print("=" * 72)

    # Import scan as a module
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from scripts.scan_all_crosslinks import scan_blog as scan_func

    all_broken = []
    all_scanned_files = 0
    all_crosslinks = 0

    for blog_id in blogs_to_fix:
        links, total_files, _ = scan_func(blog_id)
        all_scanned_files += total_files
        all_crosslinks += len(links)
        for link in links:
            target_blog = SUBDOMAIN_TO_BLOG.get(link["subdomain"])
            if target_blog:
                target_dir = os.path.join(CUAP_ROOT, target_blog, "content", "posts", link["slug"])
                if not os.path.isdir(target_dir):
                    link["target_blog"] = target_blog
                    all_broken.append(link)

    print(f"  스캔 완료: {all_scanned_files}개 파일, {all_crosslinks}개 링크")
    print(f"  발견된 404 링크: {len(all_broken)}건")
    print()

    if not all_broken:
        print("  ✅ 수정할 404 링크가 없습니다!")
        return

    # ── Phase 2: Back up original files ──
    if not dry_run:
        print("=" * 72)
        print("  Step 2: 백업 생성 중...")
        print("=" * 72)

        source_files = set(b["source_file"] for b in all_broken)
        for src_path in source_files:
            blog_id = src_path.replace(CUAP_ROOT + "/", "").split("/")[0]
            rel_path = os.path.relpath(src_path, CUAP_ROOT)
            backup_path = os.path.join(BACKUP_ROOT, blog_id, rel_path)
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(src_path, backup_path)

        print(f"  백업 완료: {len(source_files)}개 파일 → {BACKUP_ROOT}/")
        print()

    # ── Phase 3: Fix files ──
    print("=" * 72)
    print(f"  Step 3: {'[DRY-RUN] ' if dry_run else ''}404 링크 수정 중...")
    print("=" * 72)

    # Group broken links by source file
    by_source = defaultdict(list)
    for bl in all_broken:
        by_source[bl["source_file"]].append(bl)

    total_fixed = 0
    total_skipped = 0
    total_modified_files = 0
    changes_by_blog = defaultdict(lambda: {"fixed": 0, "skipped": 0, "modified_files": 0})

    for src_path in sorted(by_source.keys()):
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"  ERROR reading {src_path}: {e}")
            continue

        blog_id = src_path.replace(CUAP_ROOT + "/", "").split("/")[0]
        result = fix_file(src_path, content, dry_run)

        if result["fixed"] > 0:
            total_modified_files += 1
            changes_by_blog[blog_id]["modified_files"] += 1

        total_fixed += result["fixed"]
        total_skipped += result["skipped"]
        changes_by_blog[blog_id]["fixed"] += result["fixed"]
        changes_by_blog[blog_id]["skipped"] += result["skipped"]

        # Print changes
        for ch in result["changes"]:
            if ch["new_href"]:
                src_short = os.path.relpath(src_path, CUAP_ROOT)
                print(f"  ✅ {src_short}")
                print(f"     {ch['old_slug'][:50]:50s}")
                print(f"     → {ch['new_slug'][:50]:50s}")
                print(f"     (text: {ch['link_text']}, score: {ch['score']})")
                print()
            else:
                src_short = os.path.relpath(src_path, CUAP_ROOT)
                print(f"  ⚠️  SKIP {src_short}")
                print(f"     {ch['old_slug'][:50]:50s}")
                print(f"     reason: {ch['reason']}")
                print()

    # ── Summary ──
    print("=" * 72)
    mode = "DRY-RUN" if dry_run else "APPLIED"
    print(f"  === {mode} Summary ===")
    print(f"  {'Blog':20s} {'fixed':>6s} {'skipped':>8s} {'files':>6s}")
    print(f"  {'-'*44}")
    for blog_id in sorted(changes_by_blog.keys()):
        cb = changes_by_blog[blog_id]
        print(f"  {blog_id:20s} {cb['fixed']:6d} {cb['skipped']:8d} {cb['modified_files']:6d}")
    print(f"  {'-'*44}")
    print(f"  {'TOTAL':20s} {total_fixed:6d} {total_skipped:8d} {total_modified_files:6d}")
    print(f"  Mode: {mode}")
    if not dry_run:
        print(f"  Backup: {BACKUP_ROOT}/")
    print()


if __name__ == "__main__":
    main()
