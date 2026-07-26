"""fix_baked_crosslink_cards.py — Fix wrong hrefs in baked cross-link cards

Phase 49 (Wave 2). Scans all content/posts/*/index.md files across all 10 CUAP
blogs and fixes wrong cross-link hrefs.

Two-phase approach:
1. For each wrong href, try to look up correct URL from cuap_entities
2. If not found, search on-disk by reading frontmatter titles of all posts
   on the target blog for a matching keyword, re-register the entity,
   then use the correct URL

IMPORTANT: Run fix_cuap_entity_slugs.py FIRST to remove wrong entities.

Usage:
    # Dry-run (print changes without modifying files)
    python3 scripts/fix_baked_crosslink_cards.py --dry-run

    # Apply fixes (backs up to /tmp/fix_baked_crosslink_cards_before/)
    python3 scripts/fix_baked_crosslink_cards.py
"""

import glob
import os
import re
import shutil
import sys
from datetime import datetime

try:
    import frontmatter as fm_lib
except ImportError:
    fm_lib = None

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.cuap_entity_linker import BLOG_DOMAINS, _get_db, register_cuap_entity

CUAP_ROOT = "/Users/twinssn/Projects/cuap"
BACKUP_ROOT = "/tmp/fix_baked_crosslink_cards_before"

# Cross-link card markers
CARD_MARKER = "이런 상품도 좋아하실 거예요"
# Regex to extract hrefs from card section
# Handle both: href="URL" (ASCII quotes) and href=\"URL\" (escaped quotes in Hugo content)
HREF_RE = re.compile(r'href="(https://[^"]+)"|href=\\"(https://[^"\\\\]+)\\"')

# Build reverse map: subdomain → blog_id
SUBDOMAIN_TO_BLOG = {}
for blog_id, domain in BLOG_DOMAINS.items():
    # domain is like "https://baby.informationhot.kr"
    subdomain = domain.replace("https://", "").split(".")[0]
    SUBDOMAIN_TO_BLOG[subdomain] = blog_id


def extract_link_label(card_section: str, href: str) -> str | None:
    """Extract the link label text from the <a> tag containing the given href.

    The card section may have backslash-escaped quotes (\" \") or regular quotes (" ").
    Try both patterns when searching for the link label.
    """
    escaped_href = re.escape(href)
    for quote in ('"', '\\"'):
        pattern = rf'href={re.escape(quote)}{escaped_href}{re.escape(quote)}[^>]*>([^<]+)'
        m = re.search(pattern, card_section)
        if m:
            text = m.group(1).strip()
            # Remove emoji/icon prefix (e.g., "💪 손목 보호대 추천" → "손목 보호대 추천")
            text = re.sub(r"^[^\w\s]+", "", text).strip()
            return text
    return None


def find_matching_slug_on_disk(blog_id: str, keyword: str) -> str | None:
    """Search on-disk posts for one whose frontmatter title or slug matches the keyword.

    Tries multiple matching strategies:
    1. Frontmatter title contains keyword
    2. Slug contains keyword (direct substring)
    3. Slug contains keyword tokens (Korean word matching)
    """
    posts_dir = os.path.join(CUAP_ROOT, blog_id, "content", "posts")
    if not os.path.isdir(posts_dir):
        return None

    # For matching, strip "추천" from the keyword
    stem = keyword.replace("추천", "").strip()
    tokens = stem.split()

    # Get all slugs sorted by mtime (newest first)
    slugs_with_mtime = []
    for slug in os.listdir(posts_dir):
        d = os.path.join(posts_dir, slug)
        if not os.path.isdir(d):
            continue
        slugs_with_mtime.append((slug, os.path.getmtime(d)))
    slugs_with_mtime.sort(key=lambda x: x[1], reverse=True)

    # Strategy 1: Read frontmatter title (expensive but most accurate)
    if fm_lib:
        for slug, _ in slugs_with_mtime:
            index_path = os.path.join(posts_dir, slug, "index.md")
            if not os.path.isfile(index_path):
                continue
            try:
                post = fm_lib.load(index_path)
                title = post.get("title", "")
                if keyword in title or stem in title:
                    return slug
            except Exception:
                continue

    # Strategy 2: Direct keyword match in slug
    for slug, _ in slugs_with_mtime:
        if keyword in slug or stem in slug:
            return slug

    # Strategy 3: Token match in slug (each token checked separately)
    for slug, _ in slugs_with_mtime:
        for token in tokens:
            if len(token) >= 2 and token in slug:
                return slug

    return None


def ensure_entity_exists(conn, blog_id: str, link_label: str, domain: str, *, dry_run: bool = False) -> str | None:
    """Ensure a correct entity exists for (blog_id, link_label) and return its post_url."""
    # Step 1: Query cuap_entities for a matching entity
    entity_name = link_label if link_label.endswith("추천") else f"{link_label} 추천"
    for name in [link_label, entity_name]:
        row = conn.execute(
            """SELECT post_url FROM cuap_entities
               WHERE blog_id=? AND (link_label=? OR entity_name=?) AND published=1
               ORDER BY priority DESC, rowid DESC LIMIT 1""",
            (blog_id, name, name),
        ).fetchone()
        if row:
            return row["post_url"]

    # Step 2: Not found in DB — search on-disk for matching post
    correct_slug = find_matching_slug_on_disk(blog_id, link_label)
    if correct_slug:
        correct_url = f"{domain}/posts/{correct_slug}/"
        if not dry_run:
            # Re-register with correct slug (only in non-dry-run mode)
            register_cuap_entity(
                entity_type="category",
                entity_name=entity_name,
                blog_id=blog_id,
                post_slug=correct_slug,
                link_label=link_label,
                priority=50,
                published=1,
            )
        return correct_url

    # Step 3: No match found — use newest published entity from this blog
    row = conn.execute(
        "SELECT post_url FROM cuap_entities "
        "WHERE blog_id=? AND published=1 "
        "ORDER BY priority DESC, rowid DESC LIMIT 1",
        (blog_id,),
    ).fetchone()
    if row:
        return row["post_url"]

    return None


def main():
    dry_run = "--dry-run" in sys.argv
    conn = _get_db()

    total_files = 0
    total_cards = 0
    total_hrefs_checked = 0
    total_hrefs_fixed = 0
    total_hrefs_skipped = 0
    total_modified_files = 0
    summary = {}

    if not dry_run:
        os.makedirs(BACKUP_ROOT, exist_ok=True)

    for blog_id in sorted(BLOG_DOMAINS.keys()):
        blog_files = 0
        blog_cards = 0
        blog_fixed = 0
        blog_modified = 0

        pattern = os.path.join(CUAP_ROOT, blog_id, "content", "posts", "*", "index.md")
        md_files = glob.glob(pattern)

        for md_path in md_files:
            blog_files += 1

            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if CARD_MARKER not in content:
                    continue

                blog_cards += 1

                # Backup if not dry-run
                if not dry_run:
                    rel_path = os.path.relpath(md_path, os.path.join(CUAP_ROOT, blog_id))
                    backup_path = os.path.join(BACKUP_ROOT, blog_id, rel_path)
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    shutil.copy2(md_path, backup_path)

                # Find card section
                card_idx = content.index(CARD_MARKER)
                card_end = content.find("</div>", card_idx)
                if card_end == -1:
                    card_end = len(content)
                card_section = content[card_idx:card_end]

                hrefs = [h for tup in HREF_RE.findall(card_section) for h in tup if h]
                replacements = 0

                for href in hrefs:
                    total_hrefs_checked += 1

                    # Parse target blog from href
                    # href = "https://{sub}.informationhot.kr/posts/{slug}/"
                    m = re.match(r"https://([\w-]+)\.informationhot\.kr/posts/([^/]+)/", href)
                    if not m:
                        continue

                    target_sub = m.group(1)
                    target_blog = SUBDOMAIN_TO_BLOG.get(target_sub)
                    if not target_blog:
                        continue

                    slug_in_href = m.group(2)

                    # Check if the slug in href is wrong
                    # Wrong format: YYYYMMDD-{keyword} (8 digits + hyphen, e.g., "20260726-손목-보호대-추천")
                    # Correct format: "2026년-7월-뼈-건강-..." (year in title, NOT date-prefixed)
                    slug_is_date_prefix = bool(re.match(r"^20\d{6}-", slug_in_href))
                    if not slug_is_date_prefix:
                        # Check if slug exists on disk
                        target_posts_dir = os.path.join(
                            CUAP_ROOT, target_blog, "content", "posts", slug_in_href
                        )
                        if os.path.isdir(target_posts_dir):
                            continue  # Already correct

                    # Extract link label from the card
                    link_label = extract_link_label(card_section, href)
                    if not link_label:
                        continue

                    # Find correct URL
                    target_domain = BLOG_DOMAINS[target_blog]
                    correct_url = ensure_entity_exists(conn, target_blog, link_label, target_domain, dry_run=dry_run)

                    if not correct_url:
                        total_hrefs_skipped += 1
                        continue

                    if correct_url == href:
                        continue  # Already correct

                    # Replace href in content
                    print(f"  FIX {os.path.relpath(md_path, CUAP_ROOT)}")
                    print(f"    {href[:60]:60s}")
                    print(f"    → {correct_url[:60]:60s}")
                    content = content.replace(href, correct_url)
                    replacements += 1
                    total_hrefs_fixed += 1

                if replacements > 0:
                    blog_fixed += replacements
                    blog_modified += 1
                    if not dry_run:
                        with open(md_path, "w", encoding="utf-8") as f:
                            f.write(content)

            except Exception as e:
                print(f"  ERROR {md_path}: {e}")
                continue

        summary[blog_id] = (blog_files, blog_cards, blog_fixed, blog_modified)
        total_files += blog_files
        total_cards += blog_cards
        total_modified_files += blog_modified

    conn.close()

    mode = "DRY-RUN" if dry_run else "APPLIED"
    print(f"\n=== {mode} Summary ===")
    print(f"  {'Blog':20s} {'files':>5s} {'cards':>5s} {'fixed':>5s} {'modified':>8s}")
    print(f"  {'-'*47}")
    for blog_id, (files, cards, fixed, modified) in sorted(summary.items()):
        print(f"  {blog_id:20s} {files:5d} {cards:5d} {fixed:5d} {modified:8d}")
    print(f"  {'-'*47}")
    print(f"  {'TOTAL':20s} {total_files:5d} {total_cards:5d} {total_hrefs_fixed:5d} {total_modified_files:8d}")
    print(f"  {'':20s} {'hrefs_checked':>14s}: {total_hrefs_checked}")
    if total_hrefs_skipped > 0:
        print(f"  {'':20s} {'hrefs_skipped':>14s}: {total_hrefs_skipped}")
    if not dry_run:
        print(f"  Backup: {BACKUP_ROOT}/")
    print(f"Mode: {mode}")


if __name__ == "__main__":
    main()
