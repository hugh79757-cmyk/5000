"""data_stock 체크 검사 (DATA-01).

- 재고 산출 fn 매핑(BRAND_STOCK_FNS)이 brand 기준으로 동작하는지
- 임계 STOCK_EMPTY=0 / STOCK_LOW=10 판정
- 재고 산출 불가/브랜드 미확인 → unknown (오판 방지)
- registry RULES 엔트리 및 standard 준수 skip 경로
"""
import sqlite3

import pytest

import ops_dashboard.checks as C
from ops_dashboard.checks import data_stock as DS
from ops_dashboard.registry.rules import RULES


@pytest.fixture()
def ops_conn(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "ops.db"))
    conn.execute(
        "CREATE TABLE blog_lifecycle (blog_id TEXT, brand TEXT)"
    )
    conn.commit()
    return conn


def test_registered_and_constants():
    assert "data_stock" in C.CHECKS
    assert DS.STOCK_EMPTY == 0
    assert DS.STOCK_LOW == 10


@pytest.mark.parametrize(
    "blog_id,status",
    [
        ("dining-hugo", "pass"),   # etap 재고 충분
        ("stock-hugo", "unknown"),  # stap 소스 매핑 미확정 → unknown (오판 방지)
        ("travel-hugo", "unknown"),  # tap 브랜드 fn 없음
        ("no-such-blog", "unknown"),  # 브랜드 미확인
    ],
)
def test_sample_judgement(ops_conn, blog_id, status):
    ops_conn.execute(
        "INSERT INTO blog_lifecycle (blog_id, brand) VALUES (?, ?)",
        (blog_id, _brand_for(blog_id)),
    )
    ops_conn.commit()
    result = DS.check_data_stock(ops_conn, blog_id)
    assert result["status"] == status


def _brand_for(blog_id):
    # 실행 시점 ops.db 의 brand 값과 동기화가 어려운 테스트용 헬퍼 —
    # 체크 fn 은 brand 를 ops_conn 에서 조회하므로, 실DB 기준으로만 검증한다.
    return {
        "dining-hugo": "etap",
        "stock-hugo": "stap",
        "travel-hugo": "tap",
    }.get(blog_id)


def test_threshold_branching(tmp_path):
    """STOCK_EMPTY / STOCK_LOW 경계 판정 (patch 로 재고 주입)."""
    conn = sqlite3.connect(str(tmp_path / "ops.db"))
    conn.execute("CREATE TABLE blog_lifecycle (blog_id TEXT, brand TEXT)")
    conn.execute("INSERT INTO blog_lifecycle VALUES ('b1','etap'),('b2','cap')")
    conn.commit()

    calls = {}

    def fake_etap(b):
        calls["a"] = b
        return DS.STOCK_LOW  # == 10 → 부족(fail)
    def fake_cap(b):
        calls["b"] = b
        return DS.STOCK_EMPTY  # == 0 → 고갈(fail)

    orig = DS.BRAND_STOCK_FNS
    DS.BRAND_STOCK_FNS = {"etap": fake_etap, "cap": fake_cap}
    try:
        assert DS.check_data_stock(conn, "b1")["status"] == "fail"
        assert DS.check_data_stock(conn, "b2")["status"] == "fail"
    finally:
        DS.BRAND_STOCK_FNS = orig


def test_registry_rule_declared():
    entry = next((e for e in RULES if e.id == "data_stock"), None)
    assert entry is not None
    assert entry.kind == "rule"
    assert entry.severity == "MINOR"
    assert entry.bucket == "deferred"
    # standard.py 에 존재하지 않는 check_fn 이름 → standard 준수에서 skip
    from ops_dashboard.checks.standard import _resolve_check_fn
    assert _resolve_check_fn(entry.check_fn) is None