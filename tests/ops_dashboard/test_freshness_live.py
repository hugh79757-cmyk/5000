"""Tests for ops_dashboard.checks.freshness — live publish_ledger 재계산 회귀.

온보딩/활성화 전 저장됨 (작업1). 목적:
- check_freshness가 캐시 컬럼(days_since_last_publish)이 아니라
  publish_ledger 실데이터를 호출 시점 기준으로 재계산하는지 검증.
- YAML 동기화가 일어나지 않아도 일수가 시간 경과를 반영하는지 확인.
- 시간대(naive published_at → KST) 보정 동작 확인.
"""
import sqlite3
from unittest.mock import patch

from ops_dashboard.checks.freshness import (
    _days_since,
    _parse_last_published,
    check_freshness,
)


def _make_ops_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE blog_lifecycle (
            blog_id TEXT PRIMARY KEY,
            brand TEXT NOT NULL,
            config_status TEXT NOT NULL DEFAULT 'inactive',
            maintenance_status TEXT NOT NULL DEFAULT 'none',
            days_since_last_publish INTEGER,
            resume_ready INTEGER NOT NULL DEFAULT 0,
            site_path TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    return conn


def _make_content_db_rows(rows):
    """임시 content.db를 만들고 publish_ledger에 지정한 행 삽입.

    get_publish_log_conn()은 shared.paths.FIVEK_ROOT 기반의
    data/content.db 고정 경로를 연다. 따라서 patch로 상수와 팩토리를
    대체하는 대신, real path에 접근하지 않는 독립 검증은
    _parse_last_published의 순수 로직 + _days_since로 구성한다.
    """
    return rows


def test_parse_last_published_naive_is_kst():
    conn = object()  # 사용하지 않음 — row 직접 전달
    # publish_ledger의 MAX(created_at) 값이 naive면 KST(+09:00)로 간주
    from datetime import datetime, timedelta, timezone

    patch_target = "ops_dashboard.db.get_publish_log_conn"

    class FakeRow:
        def __getitem__(self, key):
            assert key == "last"
            return "2026-08-10T10:00:52.085006"

    class FakeLedger:
        def __init__(self):
            self.row = FakeRow()

        def execute(self, q, args):
            return self

        def fetchone(self):
            return self.row

        def close(self):
            pass

    fake = FakeLedger()

    def _fake_conn():
        return fake

    with patch(patch_target, side_effect=_fake_conn):
        dt = _parse_last_published(conn, "pet-hugo")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 9 * 3600  # KST
    assert dt.year == 2026 and dt.month == 8 and dt.day == 10


def test_days_since_computes_elapsed_from_kst_now():
    from datetime import datetime, timedelta, timezone

    kst = timezone(timedelta(hours=9))
    # 5일 전 발행 → 최소 4일 이상 경과여야 함 (시간 단위 소수점 때문에)
    last = datetime.now(kst).replace(microsecond=0) - timedelta(days=5)
    days = _days_since(last)
    assert days is not None
    assert days >= 4


def test_days_since_recent_returns_zero_or_one():
    from datetime import datetime, timedelta, timezone

    kst = timezone(timedelta(hours=9))
    # 방금 발행 → 0일
    last = datetime.now(kst).replace(microsecond=0)
    days = _days_since(last)
    assert days == 0


def test_check_freshness_uses_live_not_cached():
    """캐시 컬럼이 1(오래된 sync값)이어도, publish_ledger 실데이터가
    최근 발행이면 live 재계산(0d)이 detail에 반영되어야 한다.

    cuap threshold=1: live 0일 → pass. cached=1은 통계용으로만 노출.
    """
    from datetime import datetime, timedelta, timezone

    ops = _make_ops_conn()
    ops.execute(
        "INSERT INTO blog_lifecycle (blog_id, brand, config_status, days_since_last_publish)"
        " VALUES ('pet-hugo','cuap','paused',1)"
    )
    ops.commit()

    cache_days = ops.execute(
        "SELECT days_since_last_publish FROM blog_lifecycle WHERE blog_id='pet-hugo'"
    ).fetchone()[0]
    assert cache_days == 1

    # publish_ledger live: 방금 발행(0일) 모의
    patch_target = "ops_dashboard.db.get_publish_log_conn"
    kst = timezone(timedelta(hours=9))
    last_now = datetime.now(kst).replace(tzinfo=None)

    class FakeRow:
        def __getitem__(self, key):
            assert key == "last"
            return last_now.isoformat()

    class FakeLedger:
        def __init__(self):
            self.row = FakeRow()

        def execute(self, q, args):
            return self

        def fetchone(self):
            return self.row

        def close(self):
            pass

    fake = FakeLedger()

    def _fake_conn():
        return fake

    with patch(patch_target, side_effect=_fake_conn):
        result = check_freshness(ops, "pet-hugo")

    assert result["status"] == "pass"
    # live 재계산 반영: cached=1과 다르게 0d 표기
    assert "0d ago" in result["detail"]
    assert "cached=1" in result["detail"]


def test_check_freshness_live_stale_returns_fail():
    """실제 발행이 4일 전이면(cuap threshold=1) live 재계산으로 fail."""
    from datetime import datetime, timedelta, timezone

    ops = _make_ops_conn()
    ops.execute(
        "INSERT INTO blog_lifecycle (blog_id, brand, config_status, days_since_last_publish)"
        " VALUES ('pet-hugo','cuap','paused',1)"
    )
    ops.commit()

    patch_target = "ops_dashboard.db.get_publish_log_conn"
    kst = timezone(timedelta(hours=9))
    last_4d = (datetime.now(kst) - timedelta(days=4)).replace(tzinfo=None)

    class FakeRow:
        def __getitem__(self, key):
            assert key == "last"
            return last_4d.isoformat()

    class FakeLedger:
        def __init__(self):
            self.row = FakeRow()

        def execute(self, q, args):
            return self

        def fetchone(self):
            return self.row

        def close(self):
            pass

    fake = FakeLedger()

    def _fake_conn():
        return fake

    with patch(patch_target, side_effect=_fake_conn):
        result = check_freshness(ops, "pet-hugo")

    assert result["status"] == "fail"
    assert "Stale: 4 days" in result["detail"]
    assert "cached=1" in result["detail"]