"""Wave 2 (SC-1) — 발행 성공 후 자동 재검사 훅 단위 테스트.

발행 성공 직후 `_trigger_post_publish_checks(blog_id)` 가 해당 blog 의
`check_results` 를 갱신하는지 증명한다 (수동 호출 없이 check_results 증가).
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops_dashboard.db import get_conn, init_db  # noqa: E402
from dispatcher import _trigger_post_publish_checks  # noqa: E402

TEST_BLOG = "test-post-publish-hugo"


@pytest.fixture
def ops_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = get_conn(path)
    init_db(conn)  # blog_lifecycle + check_results + publish_error_events 생성
    conn.execute(
        "INSERT INTO blog_lifecycle (blog_id, brand, config_status) "
        "VALUES (?, ?, ?)",
        (TEST_BLOG, "cap", "active"),
    )
    conn.commit()
    conn.close()
    yield path
    if os.path.exists(path):
        os.remove(path)


def _count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT count(*) FROM check_results WHERE blog_id = ?",
        (TEST_BLOG,),
    ).fetchone()[0]


def test_hook_increases_check_results(ops_db):
    conn = get_conn(ops_db)
    before = _count(conn)
    conn.close()
    assert before == 0, "사전 상태: check_results 는 비어 있어야 함"

    # 발행 성공 직후 훅 호출 (ops_db_path 주입 → 실제 ops.db 오염 방지)
    _trigger_post_publish_checks(TEST_BLOG, ops_db_path=ops_db)

    conn = get_conn(ops_db)
    after = _count(conn)
    conn.close()
    assert after > before, (
        f"훅 호출 후 check_results 가 증가해야 함 (before={before}, after={after})"
    )


def test_hook_is_exception_isolated(ops_db):
    """존재하지 않는 blog_id 라도 발행 경로를 죽이지 않고 로깅만 한다."""
    # 존재하지 않는 blog 에 대해 예외가 전파되지 않아야 함
    _trigger_post_publish_checks("nonexistent-blog-xyz", ops_db_path=ops_db)
    # 도달 가능 (예외 미전파) 하면 통과
    assert True
