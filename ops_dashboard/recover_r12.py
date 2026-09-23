"""Recover deleted layout files from git, then selectively re-delete only confirmed junk.

Known junk (safe to delete):
- layouts/_markup/render-link.html (duplicate of _default version)
- layouts/partials/home/background.html (custom, not needed)
- layouts/shortcodes/btn.html (custom, not needed)

All other deleted files are restored from git.
"""

from __future__ import annotations
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/Users/twinssn/Projects/5000")

DB_PATH = "/Users/twinssn/Projects/5000/ops_dashboard/ops.db"

# Files confirmed safe to delete (the actual junk from the dry run + backup)
CONFIRMED_JUNK = {
    "layouts/_markup/render-link.html",
    "layouts/partials/home/background.html",
    "layouts/shortcodes/btn.html",
}


def get_r12_sites(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    sites = []
    for fix in conn.execute(
        "SELECT blog_id FROM pending_fixes WHERE action='fix_r12';"
    ).fetchall():
        row = conn.execute(
            "SELECT site_path FROM blog_lifecycle WHERE blog_id=?",
            (fix["blog_id"],),
        ).fetchone()
        if row and row["site_path"]:
            sites.append((fix["blog_id"], row["site_path"]))
    return sites


def get_git_deleted(conn: sqlite3.Connection, site_path: str) -> list[str]:
    """Get layout files deleted from git working tree."""
    result = subprocess.run(
        ["git", "status", "--short", "layouts/"],
        cwd=site_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    deleted = []
    for line in result.stdout.strip().split("\n"):
        if line.startswith(" D "):
            deleted.append(line[3:].strip())
    return deleted


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    sites = get_r12_sites(conn)
    print(f"=== R12 sites: {len(sites)} ===\n")

    total_deleted = 0
    total_restored = 0
    total_junk = 0

    for blog_id, site_path in sites:
        site = Path(site_path)
        if not site.exists():
            print(f"  SKIP {blog_id}: path 없음")
            continue

        # Check if it's a git repo
        git_check = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=site_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if git_check.returncode != 0 or "true" not in git_check.stdout:
            print(f"  SKIP {blog_id}: git repo 아님")
            continue

        deleted = get_git_deleted(conn, site_path)
        if not deleted:
            print(f"  {blog_id}: 삭제된 파일 없음")
            continue

        for rel_path in deleted:
            total_deleted += 1
            if rel_path in CONFIRMED_JUNK:
                # Confirmed junk - leave deleted, ensure directory is clean
                f = site / rel_path
                if not f.exists():
                    total_junk += 1
                    continue
                # Should not happen (already deleted)
                print(f"  {blog_id}: WARN {rel_path} still exists")
            else:
                # Restore from git
                subprocess.run(
                    ["git", "checkout", "HEAD", "--", rel_path],
                    cwd=site_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                restored_path = site / rel_path
                if restored_path.exists():
                    total_restored += 1
                    print(f"  {blog_id}: restored {rel_path}")
                else:
                    print(f"  {blog_id}: RESTORE FAILED {rel_path}")

    print(f"\n=== RECOVERY SUMMARY ===")
    print(f"Deleted files found: {total_deleted}")
    print(f"Restored from git: {total_restored}")
    print(f"Confirmed junk (left deleted): {total_junk}")

    conn.close()


if __name__ == "__main__":
    main()
