"""모든 커스텀 체크 실행 + check_results_custom 저장"""
import sqlite3, os, sys
from datetime import datetime

DB_PATH = os.path.expanduser("~/Projects/5000/ops_dashboard/ops.db")

# 스크립트 디렉터리를 sys.path에 넣어 동료 체크 모듈 import 보장
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS check_results_custom (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        check_name TEXT, blog_id TEXT, result TEXT, detail TEXT,
        checked_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    conn.commit()


def clear_managed(conn):
    """이 스크립트가 관리하는 체크만 매 실행 전 삭제 → 스냅샷 누적 방지"""
    conn.execute(
        "DELETE FROM check_results_custom WHERE check_name IN ('TOPIC_POOL_HEALTH','PIPELINE_FAILURE_HEALTH','TABLE_QUALITY')"
    )
    conn.commit()


def save_results(conn, results):
    for r in results:
        conn.execute(
            "INSERT INTO check_results_custom (check_name, blog_id, result, detail) VALUES (?,?,?,?)",
            (r["check_name"], r["blog_id"], r["result"], r["detail"])
        )
    conn.commit()


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)
    clear_managed(conn)

    from topic_pool_health import run_check as pool_check
    from pipeline_failure_health import run_check as pipeline_check
    from table_quality import run_check as table_check

    all_results = pool_check() + pipeline_check() + table_check()
    save_results(conn, all_results)

    critical = [r for r in all_results if r["result"] == "critical"]
    warning = [r for r in all_results if r["result"] == "warning"]
    passed = [r for r in all_results if r["result"] == "pass"]

    print(f"Total: {len(all_results)} | CRITICAL: {len(critical)} | WARNING: {len(warning)} | PASS: {len(passed)}")
    for r in critical + warning:
        print(f"  {r['result'].upper():8s} [{r['check_name']}] {r['blog_id']}: {r['detail']}")
    conn.close()
