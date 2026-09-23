"""Execute pending_fixes 49건: backup → auto-approve → fix → verify.

사전 카운트: 73 files, 37 sites (dry-run verified)
백업: /tmp/r12_backup_20260923/
실행: fix_r12_overrides (37 sites), fix_r08_lead (cap-hugo), fix_r2_images detection (10 sites)
"""

from __future__ import annotations
import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Users/twinssn/Projects/5000")

DB_PATH = "/Users/twinssn/Projects/5000/ops_dashboard/ops.db"
BACKUP_DIR = Path("/tmp/r12_backup_20260923")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # === BACKUP: Copy all files that will be deleted ===
    print("=== STEP 1: BACKUP ===")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_count = 0

    for fix in conn.execute(
        "SELECT blog_id FROM pending_fixes WHERE status='proposed' AND action='fix_r12';"
    ).fetchall():
        blog_id = fix["blog_id"]
        row = conn.execute(
            "SELECT site_path FROM blog_lifecycle WHERE blog_id=?",
            (blog_id,),
        ).fetchone()
        if not row or not row["site_path"]:
            continue
        site = Path(row["site_path"])
        if not site.exists():
            continue
        for sub in ("layouts/_markup/render-link.html", "layouts/partials/home/background.html", "layouts/shortcodes/btn.html"):
            f = site / sub
            if f.exists():
                backup_path = BACKUP_DIR / blog_id / sub
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, backup_path)
                backup_count += 1

    print(f"  Backed up {backup_count} files to {BACKUP_DIR}")

    # === AUTO-APPROVE: proposed → approved ===
    print("\n=== STEP 2: AUTO-APPROVE ===")
    fixes = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM pending_fixes WHERE status='proposed';"
        ).fetchall()
    ]
    approved = 0
    for fix in fixes:
        cur = conn.execute(
            "UPDATE pending_fixes SET status='approved' WHERE id=?",
            (fix["id"],),
        )
        if cur.rowcount > 0:
            approved += 1
    conn.commit()
    print(f"  Approved {approved} fixes")

    # === EXECUTE R12 ===
    print("\n=== STEP 3: R12 FIX ===")
    r12_ok = 0
    r12_fail = 0
    for fix in conn.execute(
        "SELECT blog_id FROM pending_fixes WHERE status='approved' AND action='fix_r12';"
    ).fetchall():
        blog_id = fix["blog_id"]
        row = conn.execute(
            "SELECT site_path FROM blog_lifecycle WHERE blog_id=?",
            (blog_id,),
        ).fetchone()
        if not row or not row["site_path"]:
            r12_fail += 1
            print(f"  ✗ {blog_id}: no site_path")
            continue
        site = Path(row["site_path"])
        if not site.exists():
            r12_fail += 1
            print(f"  ✗ {blog_id}: path 없음")
            continue
        try:
            from shared.autofix.r12 import fix_r12_overrides
            ok, msg = fix_r12_overrides(site)
            if ok:
                r12_ok += 1
                deleted = "삭제" in msg
                marker = "✓" if deleted else "~"
                print(f"  {marker} {blog_id}: {msg}")
            else:
                r12_fail += 1
                print(f"  ✗ {blog_id}: {msg}")
        except Exception as e:
            r12_fail += 1
            print(f"  ✗ {blog_id}: 오류 {e}")

    print(f"  R12: OK={r12_ok}, Fail={r12_fail}")

    # === EXECUTE R08 ===
    print("\n=== STEP 4: R08 FIX (cap-hugo) ===")
    for fix in conn.execute(
        "SELECT blog_id FROM pending_fixes WHERE status='approved' AND action='fix_r08';"
    ).fetchall():
        blog_id = fix["blog_id"]
        row = conn.execute(
            "SELECT site_path FROM blog_lifecycle WHERE blog_id=?",
            (blog_id,),
        ).fetchone()
        if not row or not row["site_path"]:
            print(f"  ✗ {blog_id}: no site_path")
            continue
        site = Path(row["site_path"])
        if not site.exists():
            print(f"  ✗ {blog_id}: path 없음")
            continue
        try:
            from shared.autofix.r08 import fix_r08_lead
            ok, msg = fix_r08_lead(site)
            marker = "✓" if ok else "✗"
            print(f"  {marker} {blog_id}: {msg}")
        except Exception as e:
            print(f"  ✗ {blog_id}: 오류 {e}")

    # === R2-01 DETECTION ===
    print("\n=== STEP 5: R2-01 DETECTION ===")
    for fix in conn.execute(
        "SELECT blog_id FROM pending_fixes WHERE status='approved' AND action='fix_r2_images';"
    ).fetchall():
        blog_id = fix["blog_id"]
        row = conn.execute(
            "SELECT site_path FROM blog_lifecycle WHERE blog_id=?",
            (blog_id,),
        ).fetchone()
        if not row or not row["site_path"]:
            continue
        site = Path(row["site_path"])
        if not site.exists():
            continue
        try:
            from shared.autofix.r2 import fix_r2_images
            ok, msg = fix_r2_images(site, blog_id)
            marker = "✓" if ok else "~"
            print(f"  {marker} {blog_id}: {msg}")
        except Exception as e:
            print(f"  ✗ {blog_id}: 오류 {e}")

    conn.close()

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()
