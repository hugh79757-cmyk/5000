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


def test_registry_view_aggregates_any_fail(tmp_path):
    """data_stock 노드: 마지막 행이 아닌 '브랜드 전체 any-fail→fail' + affected_blogs.

    (게이트3/위험1 보정) 2블로그 중 1개가 fail이면 노드 status=fail,
    affected_blogs=[해당 블로그]로 정확히 노출된다.
    """
    import ops_dashboard.checks as C
    conn = sqlite3.connect(str(tmp_path / "ops.db"))
    conn.row_factory = sqlite3.Row
    # 필요한 스키마 최소화 (get_registry_view가 의존하는 컬럼만)
    conn.execute(
        "CREATE TABLE check_results (blog_id TEXT, check_name TEXT, status TEXT, "
        "detail TEXT, evidence_url TEXT, rule_id TEXT, problem_id TEXT, "
        "severity TEXT, action TEXT, checked_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE blog_lifecycle (blog_id TEXT, config_status TEXT, "
        "maintenance_status TEXT, brand TEXT)"
    )
    # 2블로그 기록: 하나 pass, 하나 fail (재고 낮은 것으로 강제 주입)
    for blog, st in [("finance-hugo", "fail"), ("dining-hugo", "pass")]:
        conn.execute(
            "INSERT INTO check_results VALUES (?, 'data_stock', ?, 'd', NULL, NULL, "
            "NULL, NULL, NULL, '2026-08-15T12:00:00')",
            (blog, st),
        )
    conn.commit()
    # monkeypatch: blog_lifecycle 조회 + sc_row 등 최소 의존 충족용으로
    # get_registry_view 를 복제 대신 직접 _rule_entry 경로 검증한다.
    from ops_dashboard.db import get_registry_view

    # get_registry_view 는 blog_lifecycle 의 세션 존재를 요구하므로 2블로그 등록
    for blog, brand in [("finance-hugo", "stap"), ("dining-hugo", "etap")]:
        conn.execute(
            "INSERT INTO blog_lifecycle (blog_id, config_status, maintenance_status, "
            "brand) VALUES (?, 'active', 'none', ?)",
            (blog, brand),
        )
    conn.commit()

    import ops_dashboard.registry as _reg
    import ops_dashboard.db as _db
    orig_by_kind = _reg.by_kind
    # data_stock 규칙만으로 범위 한정 → triage_classifications 등 비관련 테이블 제거
    _reg.by_kind = lambda kind: (
        [next(e for e in _reg.RULES if e.id == "data_stock")] if kind == "rule" else []
    )
    try:
        rv = get_registry_view(conn)
    finally:
        _reg.by_kind = orig_by_kind
    ds = next((e for e in rv["rules"] if e["id"] == "data_stock"), None)
    assert ds is not None
    assert ds["status"] == "fail"
    assert ds["affected_blogs"] == ["finance-hugo"]