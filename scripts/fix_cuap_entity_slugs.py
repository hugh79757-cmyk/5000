"""fix_cuap_entity_slugs.py — Fix wrong slugs in cuap_entities DB

Phase 49 (Wave 2). Wrong-slug entities (e.g., `20260726-{keyword}`) were
created by the pre-fix pipeline and always point to 404 URLs. Since they can't
be reliably mapped to correct on-disk slugs (the slug derives from the AI
generated title, not the keyword), the safest fix is to DELETE them.

The correct entities (with `slugify(title)` format slugs) already exist in the
DB for most keywords. After deletion, run `scripts/backfill_cuap_entities.py`
if additional entities are needed.

Usage:
    # Dry-run (print changes without modifying DB)
    python3 scripts/fix_cuap_entity_slugs.py --dry-run

    # Apply fixes (DELETE all wrong-slug entities)
    python3 scripts/fix_cuap_entity_slugs.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.cuap_entity_linker import BLOG_DOMAINS, _get_db

CUAP_ROOT = "/Users/twinssn/Projects/cuap"


def get_on_disk_slugs(blog_id: str) -> set:
    """Scan content/posts/ directories to get actual on-disk slug names."""
    posts_dir = os.path.join(CUAP_ROOT, blog_id, "content", "posts")
    if not os.path.isdir(posts_dir):
        return set()
    return {name for name in os.listdir(posts_dir)
            if os.path.isdir(os.path.join(posts_dir, name))}


# Pattern for wrong date-prefixed slugs: YYYYMMDD-{keyword} (8 digits + hyphen + keyword)
# CORRECT slugs might start with "2026" as part of the title (e.g., "2026-jungnyeon-...")
RE_DATE_PREFIXED = re.compile(r"^20\d{6}-")


def slug_is_wrong(post_slug: str, on_disk: set) -> bool:
    """Check if a slug is wrong — date-prefixed (YYYYMMDD-{keyword}) or not matching any on-disk directory.

    Distinguishes between:
    - WRONG: 20260726-{keyword} (YYYYMMDD- format, keyword-based, not on disk)
    - CORRECT: 2026-jungnyeon-... (year in title, romanized, exists on disk)"

    Note: A slug that doesn't match any on-disk directory is always wrong (it's a phantom entry).
    """
    if RE_DATE_PREFIXED.match(post_slug):
        return True
    if post_slug not in on_disk:
        return True
    return False


def main():
    dry_run = "--dry-run" in sys.argv
    total_checked = 0
    total_deleted = 0
    summary = {}

    conn = _get_db()

    for blog_id in sorted(BLOG_DOMAINS.keys()):
        on_disk = get_on_disk_slugs(blog_id)

        # Get ALL published entities for this blog
        rows = conn.execute(
            "SELECT rowid, entity_name, post_slug "
            "FROM cuap_entities WHERE published=1 AND blog_id=?",
            (blog_id,),
        ).fetchall()

        blog_checked = 0
        blog_deleted = 0

        for row in rows:
            current_slug = row["post_slug"]

            if not slug_is_wrong(current_slug, on_disk):
                continue  # Already correct

            blog_checked += 1

            # Check for a correct duplicate (same blog_id, entity_name, correct slug exists)
            correct_dup = conn.execute(
                "SELECT 1 FROM cuap_entities "
                "WHERE rowid != ? AND blog_id=? AND entity_name=? AND published=1 "
                "AND post_slug NOT LIKE '2026%' AND post_slug != ?",
                (row["rowid"], blog_id, row["entity_name"], current_slug),
            ).fetchone()

            dup_label = " (dup)" if correct_dup else " (singleton)"
            print(f"  DEL {blog_id}: {current_slug[:50]:50s} entity={row['entity_name']}{dup_label}")
            if not dry_run:
                conn.execute("DELETE FROM cuap_entities WHERE rowid=?", (row["rowid"],))
            blog_deleted += 1

        summary[blog_id] = (blog_checked, blog_deleted)
        total_checked += blog_checked
        total_deleted += blog_deleted

    if not dry_run:
        conn.commit()
    conn.close()

    # Print summary
    mode = "DRY-RUN" if dry_run else "APPLIED"
    print(f"\n=== {mode} Summary ===")
    print(f"  {'Blog':20s} {'checked':>7s} {'deleted':>7s}")
    print(f"  {'-'*36}")
    for blog_id, (checked, deleted) in sorted(summary.items()):
        print(f"  {blog_id:20s} {checked:7d} {deleted:7d}")
    print(f"  {'-'*36}")
    print(f"  {'TOTAL':20s} {total_checked:7d} {total_deleted:7d}")
    print(f"Mode: {mode}")


if __name__ == "__main__":
    main()
