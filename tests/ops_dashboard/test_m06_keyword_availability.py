"""Tests for M06 _check_keyword_availability — 30-day real publish-candidate field.

The new `real_candidates_30d` field replicates pipeline.py _select_keyword
filters (30d publish_log exclusion, quarantine, >=3 products, 14d category dup).
The existing all-time residual field and pass/fail judgment are untouched.
"""
import os
import sqlite3
from pathlib import Path

import pytest

from ops_dashboard.checks import maintenance

REAL_ROOT = str(Path(__file__).parent.parent.parent)  # 5000 root


class _FakePath:
    """Redirects project_root-relative paths (data/, pipelines/) to a tmp dir."""

    def __init__(self, p):
        self._p = str(p)

    def __truediv__(self, other):
        base = TMP_ROOT if self._p == REAL_ROOT else self._p
        return _FakePath(os.path.join(base, str(other)))

    @property
    def parent(self):
        return _FakePath(os.path.dirname(self._p))

    def exists(self):
        return os.path.exists(self._p)

    def __str__(self):
        return self._p


TMP_ROOT = None  # set per-test via monkeypatch


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    """Build tmp project tree (data/curation.db + pipelines/curation/keywords.py)."""
    global TMP_ROOT
    TMP_ROOT = str(tmp_path)
    monkeypatch.setattr(maintenance, "Path", _FakePath)

    (tmp_path / "data").mkdir()
    (tmp_path / "pipelines" / "curation").mkdir(parents=True)

    (tmp_path / "pipelines" / "curation" / "keywords.py").write_text(
        'KEYWORD_MAP = {\n'
        '    "test-blog": [\n'
        '        "가전 냉장고 추천",\n'
        '        "가전 세탁기 추천",\n'
        '        "주방 에어프라이어 추천",\n'
        '        "주방 전기밥솥 추천",\n'
        '        "스포츠 러닝화 추천",\n'
        '        "스포츠 자전거 추천",\n'
        '    ],\n'
        '}\n'
    )

    db = sqlite3.connect(str(tmp_path / "data" / "curation.db"))
    db.executescript("""
        CREATE TABLE published_products (
            blog_id TEXT, keyword TEXT, published_at TEXT
        );
        CREATE TABLE publish_log (
            blog_id TEXT, keyword TEXT, published_at TEXT
        );
        CREATE TABLE keyword_health (
            blog_id TEXT, keyword TEXT, quarantined_until TEXT
        );
        CREATE TABLE products (
            keyword TEXT, product_id TEXT
        );
    """)
    # All 6 keywords have >=3 products
    for kw in ["가전 냉장고 추천", "가전 세탁기 추천", "주방 에어프라이어 추천",
               "주방 전기밥솥 추천", "스포츠 러닝화 추천", "스포츠 자전거 추천"]:
        for i in range(3):
            db.execute("INSERT INTO products VALUES (?, ?)", (kw, f"p-{kw}-{i}"))
    # All-time used (residual path): 2 keywords
    db.execute("INSERT INTO published_products VALUES ('test-blog', '가전 냉장고 추천', '2026-01-01')")
    db.execute("INSERT INTO published_products VALUES ('test-blog', '주방 에어프라이어 추천', '2026-01-01')")
    # 30d window: 냉장고 (5d ago, also 14d cat) + 에어프라이어 (20d ago, outside 14d cat window)
    db.execute("INSERT INTO publish_log VALUES ('test-blog', '가전 냉장고 추천', datetime('now', '-5 days'))")
    db.execute("INSERT INTO publish_log VALUES ('test-blog', '주방 에어프라이어 추천', datetime('now', '-20 days'))")
    # Quarantined: 스포츠 러닝화 추천
    db.execute("INSERT INTO keyword_health VALUES ('test-blog', '스포츠 러닝화 추천', datetime('now', '+30 days'))")
    db.commit()
    db.close()
    return tmp_path


def test_m06_real_candidates_30d_matches_reasoned_fixture(fake_project):
    """6 defined → 30d used(2) → 14d cat dup(가전 세탁기) → quarantined(러닝화) → 2 candidates."""
    conn = sqlite3.connect(":memory:")
    result = maintenance._check_keyword_availability(conn, "test-blog")
    conn.close()

    assert result["real_candidates_30d"] == 2
    # Existing residual field/judgment untouched: 6 defined - 2 all-time used = 4 < 24 → fail
    assert result["status"] == "fail"
    assert "잔량 4개" in result["detail"]


def test_m06_real_candidates_30d_is_non_negative_int_for_known_blog():
    """Live check against real curation.db — field is computed as int >= 0."""
    real_db = Path(REAL_ROOT) / "data" / "curation.db"
    if not real_db.exists():
        pytest.skip("data/curation.db 없음 — live 검사 생략")
    conn = sqlite3.connect(":memory:")
    result = maintenance._check_keyword_availability(conn, "laptop-hugo")
    conn.close()
    if result["status"] == "unknown":
        pytest.skip(f"laptop-hugo M06 미계산: {result['detail']}")
    assert isinstance(result["real_candidates_30d"], int)
    assert result["real_candidates_30d"] >= 0