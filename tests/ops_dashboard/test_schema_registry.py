"""schema_registry 모듈 테스트.

실제 ops.db 를 건드리지 않고 tmp_path DB 로 격리 검증한다.
- DDL/init
- sync_all_schemas 실제 blogs.d+schemas 기반 85건 적재 + 멱등성
- get_schema / get_branch_summary
- classify_standardization 상태 분류 (합성 데이터)
"""
import sqlite3

import pytest

from ops_dashboard import schema_registry as sr


@pytest.fixture(autouse=True)
def _guard_prod_ops_db(monkeypatch, tmp_path):
    """conftest 운영 DB 가드 오버라이드 (레포 컨벤션) — tmp 경로 가리킴."""
    from shared import publish_error_events as events
    monkeypatch.setattr(events, "OPS_DB_PATH", tmp_path / "ops_test.db")


@pytest.fixture()
def tmp_db(tmp_path):
    db = str(tmp_path / "ops_test.db")
    # classify_standardization 이 조인하는 blog_lifecycle 생성 (init_schema_registry 밖)
    from ops_dashboard import db as ops_db
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    ops_db.init_db(conn)
    conn.close()
    return db


def _insert_blog(conn, blog_id="x-hugo", status="active", ga4_id="", branch="cap"):
    conn.execute(
        "INSERT OR REPLACE INTO schema_registry "
        "(blog_id, branch, schema_version, required_frontmatter, optional_frontmatter,"
        " ga4_id, h2_guard_enabled, build_status, last_synced_at, raw_schema)"
        " VALUES (?, ?, 'v', '[]', '[]', ?, 1, 'pass', datetime('now'), '{}')",
        (blog_id, branch, ga4_id),
    )
    conn.execute(
        "INSERT INTO blog_lifecycle (blog_id, brand, config_status, maintenance_status, site_path)"
        " VALUES (?, 'cap', ?, 'none', '')",
        (blog_id, status),
    )
    conn.commit()


def test_init_creates_table(tmp_db):
    sr.init_schema_registry(tmp_db)
    conn = sqlite3.connect(tmp_db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(schema_registry)")}
    conn.close()
    assert {
        "blog_id", "branch", "schema_version", "required_frontmatter",
        "optional_frontmatter", "ga4_id", "h2_guard_enabled",
        "build_status", "last_synced_at", "raw_schema",
    } <= cols


def test_sync_all_schemas_85_and_idempotent(tmp_db):
    sr.init_schema_registry(tmp_db)
    r1 = sr.sync_all_schemas(tmp_db)
    assert r1["total"] == 85
    assert r1["inserted"] == 85
    assert r1["failed"] == []
    # 멱등성: 재실행해도 85건 유지 (INSERT OR REPLACE)
    r2 = sr.sync_all_schemas(tmp_db)
    assert r2["inserted"] == 85
    conn = sqlite3.connect(tmp_db)
    count = conn.execute("SELECT COUNT(*) FROM schema_registry").fetchone()[0]
    conn.close()
    assert count == 85


def test_get_schema_known_blog(tmp_db):
    sr.init_schema_registry(tmp_db)
    sr.sync_all_schemas(tmp_db)
    row = sr.get_schema(tmp_db, "michelin-hugo")
    assert row is not None
    assert row["branch"] == "etap"
    assert "title" in row["required_frontmatter"]
    assert sr.get_schema(tmp_db, "no-such-blog-xyz") is None


def test_branch_summary_distribution(tmp_db):
    sr.init_schema_registry(tmp_db)
    sr.sync_all_schemas(tmp_db)
    summary = {r["branch"]: r["total"] for r in sr.get_branch_summary(tmp_db)}
    assert summary == {
        "etap": 36, "cuap": 15, "cap": 13, "tap": 8,
        "stap": 6, "rap": 5, "seap": 2,
    }


def test_classify_states(tmp_db):
    sr.init_schema_registry(tmp_db)
    conn = sqlite3.connect(tmp_db)
    # active + 고유 ga4 → ok
    _insert_blog(conn, "ok-hugo", "active", "G-AAA111")
    # active + 공유 ga4 → attention (ga4:shared)
    _insert_blog(conn, "shared-a", "active", "G-SHARED1")
    _insert_blog(conn, "shared-b", "active", "G-SHARED1")
    # paused → inactive
    _insert_blog(conn, "off-hugo", "paused", "G-BBB222")
    conn.close()

    result = sr.classify_standardization(tmp_db)
    by_id = {b["blog_id"]: b for b in result["blogs"]}
    assert by_id["ok-hugo"]["state"] == "ok"
    assert by_id["shared-a"]["state"] == "attention"
    assert "ga4:shared" in by_id["shared-a"]["reasons"]
    assert by_id["shared-b"]["state"] == "attention"
    assert by_id["off-hugo"]["state"] == "inactive"
    assert result["summary"]["total"] == 4


def test_classify_kw_attention(tmp_db, monkeypatch):
    sr.init_schema_registry(tmp_db)
    conn = sqlite3.connect(tmp_db)
    _insert_blog(conn, "lowkw-hugo", "active", "G-CCC333")
    conn.close()
    monkeypatch.setattr(
        sr, "_keyword_map_len",
        lambda bid: 12 if bid == "lowkw-hugo" else None,
    )
    result = sr.classify_standardization(tmp_db)
    row = next(b for b in result["blogs"] if b["blog_id"] == "lowkw-hugo")
    assert row["state"] == "attention"
    assert any(r.startswith("kw:") for r in row["reasons"])
