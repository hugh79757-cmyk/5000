"""ops_dashboard.seed — CLI entry point for DB initialization.

Usage:
    python ops_dashboard/seed.py                 # init + sync + seed
    python ops_dashboard/seed.py --run-checks    # + run all health checks
    python ops_dashboard/seed.py --db-path /tmp/ops.db  # custom DB path
"""
import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path so ops_dashboard is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from ops_dashboard.db import get_conn, init_db, seed_known_issues, seed_maintenance_status, sync_blog_lifecycle


def main() -> None:
    parser = argparse.ArgumentParser(description="Ops Dashboard DB setup")
    parser.add_argument(
        "--run-checks", action="store_true",
        help="Run all checks after seeding",
    )
    parser.add_argument(
        "--db-path", default=None,
        help="Custom DB path (default: ops_dashboard/ops.db)",
    )
    args = parser.parse_args()

    conn = get_conn(args.db_path)
    init_db(conn)

    blog_count = sync_blog_lifecycle(conn)
    print(f"Synced {blog_count} blogs from YAML")

    issue_count = seed_known_issues(conn)
    print(f"Seeded {issue_count} known issues")

    maint_count = seed_maintenance_status(conn)
    print(f"Seeded {maint_count} maintenance status entries")

    if args.run_checks:
        from ops_dashboard.checks import run_all_checks

        print("Running all checks...")
        summary = run_all_checks(conn)
        print(
            f"Checks complete: total={summary['total']}, "
            f"pass={summary['pass']}, fail={summary['fail']}, "
            f"unknown={summary['unknown']}"
        )

    conn.close()


if __name__ == "__main__":
    main()
