"""Finalize pending_fixes statuses:
- R12/R08/R2: approved → resolved (execution completed)
- cap-hugo R08: → rejected (no site path)
"""

from __future__ import annotations
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, "/Users/twinssn/Projects/5000")

DB_PATH = "/Users/twinssn/Projects/5000/ops_dashboard/ops.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 1. R12: approved → resolved
    r12 = conn.execute(
        "SELECT id FROM pending_fixes WHERE action='fix_r12' AND status='approved';"
    ).fetchall()
    for row in r12:
        conn.execute(
            "UPDATE pending_fixes SET status='resolved', resolved_at=datetime('now') WHERE id=?",
            (row["id"],),
        )
    r12_count = len(r12)

    # 2. R08 for cap-hugo: approved → rejected (no site)
    cap_r08 = conn.execute(
        "SELECT id FROM pending_fixes WHERE blog_id='cap-hugo' AND action='fix_r08' AND status='approved';"
    ).fetchall()
    for row in cap_r08:
        conn.execute(
            "UPDATE pending_fixes SET status='rejected' WHERE id=?",
            (row["id"],),
        )
    cap_count = len(cap_r08)

    # 3. R2-01: approved → resolved (detection completed, remaining = manual R2 URL)
    r2 = conn.execute(
        "SELECT id FROM pending_fixes WHERE action='fix_r2_images' AND status='approved';"
    ).fetchall()
    for row in r2:
        conn.execute(
            "UPDATE pending_fixes SET status='resolved', resolved_at=datetime('now') WHERE id=?",
            (row["id"],),
        )
    r2_count = len(r2)

    conn.commit()

    print(f"R12 resolved: {r12_count}")
    print(f"cap-hugo R08 rejected: {cap_count}")
    print(f"R2-01 resolved: {r2_count}")

    # Summary
    print("\n=== PENDING_FIXES STATUS ===")
    for status in ["proposed", "approved", "resolved", "rejected", "failed"]:
        count = conn.execute(
            "SELECT COUNT(*) FROM pending_fixes WHERE status=?", (status,)
        ).fetchone()[0]
        print(f"  {status}: {count}")

    conn.close()


if __name__ == "__main__":
    main()
