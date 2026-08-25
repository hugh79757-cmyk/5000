"""test_editorial_quality.py - Phase 72 Wave 3 synthesis 품질 게이트 테스트

T3.1: editorial_synthesis_quality_gate (길이 ≥80자 / 숫자∈unique_data 값집합 /
      source_table 인용) 단위 테스트.
T3.2: editorial_cosine_check 계약 테스트 + synthesis 단락 추출 헬퍼 테스트.
T3.3: adapter → synthesis → gate no-LLM end-to-end 체인 (대표 경로 3종 +
      passthrough 1종).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from pipelines.etap.editorial_synthesis import (
    editorial_synthesis_step,
    extract_trailing_synthesis,
)
from pipelines.etap.data_adapters import get_unique_data_points
from pipelines.etap.quality_guard import editorial_synthesis_quality_gate


def _sample_data():
    """flight 스타일 unique_data 3개 (수치 2개 + 날짜 1개)."""
    return [
        {"label": "min_price", "value": 412, "unit": "USD", "source_table": "flight_prices"},
        {"label": "min_stops", "value": 0, "unit": "stops", "source_table": "flight_prices"},
        {"label": "departure_date", "value": "2026-09-14", "unit": "date", "source_table": "flight_prices"},
    ]


class TestSynthesisQualityGate:
    """T3.1: editorial_synthesis_quality_gate 단위 테스트."""

    def test_valid_synthesis_passes(self):
        """정상 synthesis(unique_data 3개, 수치 일치) → (True, dict)."""
        para = editorial_synthesis_step("", _sample_data(), {})
        assert para, "synthesis must be non-empty for non-empty unique_data"
        ok, details = editorial_synthesis_quality_gate(para, _sample_data())
        assert ok is True, details
        assert isinstance(details, dict)
        assert details.get("length", 0) >= 80
        assert details.get("missing_numbers") == []
        assert details.get("source_found") == "flight_prices"

    def test_short_paragraph_fails(self):
        """길이 50자 → False."""
        short = "From flight_prices, min price 412 USD and 0 stops only."  # ~55 chars
        ok, details = editorial_synthesis_quality_gate(short, _sample_data())
        assert ok is False
        assert "short" in details.get("reason", "")

    def test_hallucinated_number_fails(self):
        """미존재 수치 '9999999' 삽입 → False."""
        para = editorial_synthesis_step("", _sample_data(), {})
        assert para
        tainted = para + " Premium cabin fares start at 9999999 USD according to rumors."
        ok, details = editorial_synthesis_quality_gate(tainted, _sample_data())
        assert ok is False
        assert "9999999" in details.get("missing_numbers", [])

    def test_empty_inputs_fail(self):
        """unique_data=[] + 빈 paragraph → False."""
        ok, details = editorial_synthesis_quality_gate("", [])
        assert ok is False
        assert isinstance(details, dict)

    def test_missing_source_table_fails(self):
        """숫자는 전부 일치해도 source_table 미인용 시 False (검증 항목 c)."""
        para = editorial_synthesis_step("", _sample_data(), {})
        assert para
        stripped = para.replace("flight_prices", "the dataset")
        # source_table 문자열을 제거해도 길이·숫자 조건은 유지되어야 함
        if len(stripped.strip()) < 80:
            stripped = stripped + " Additional context padding sentence for length."
        ok, details = editorial_synthesis_quality_gate(stripped, _sample_data())
        assert ok is False
        assert details.get("source_found") is None


class TestTrailingSynthesisExtraction:
    """T3.2 보조: 본문 말미 synthesis 단락 추출 헬퍼."""

    def test_extracts_appended_synthesis(self):
        body = "## Intro\n\nSome intro text here.\n\n## Details\n\nMore body content."
        para = editorial_synthesis_step("", _sample_data(), {})
        full = body.rstrip() + "\n\n" + para + "\n"
        assert extract_trailing_synthesis(full) == para

    def test_returns_empty_without_marker(self):
        body = "# Title\n\nRegular closing paragraph without any synthesis marker."
        assert extract_trailing_synthesis(body) == ""
        assert extract_trailing_synthesis("") == ""


class TestEditorialCosineCheck:
    """T3.2: editorial_cosine_check 계약 (타입 + 임계값 방향)."""

    def test_contract_types(self):
        from pipelines.etap.uniqueness_check import editorial_cosine_check
        ok, cos = editorial_cosine_check(
            "완전 새로운 고유 데이터 기반 문장입니다 15000원 2026년", "travel-hugo"
        )
        assert isinstance(ok, bool)
        assert isinstance(cos, float)

    def test_empty_paragraph_passes(self):
        from pipelines.etap.uniqueness_check import editorial_cosine_check
        ok, cos = editorial_cosine_check("", "travel-hugo")
        assert ok is True
        assert cos == 0.0

    def test_identical_text_fails_threshold(self):
        """코퍼스와 동일 텍스트 → cosine 1.0 근접 → False (임계값 방향 검증)."""
        from pipelines.etap import uniqueness_check as _uc
        if not _uc.HAS_SKLEARN:
            pytest.skip("sklearn unavailable — cosine machinery fail-open (by design)")
        import sqlite3
        import os
        db = os.path.join(os.path.dirname(__file__), "..", "data", "content.db")
        if not os.path.exists(db):
            pytest.skip("content.db not present")
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                "SELECT blog_id, body_md FROM articles "
                "WHERE status='published' AND length(body_md) > 200 "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        if not row:
            pytest.skip("no published articles in content.db")
        blog_id, body_md = row
        para = extract_trailing_synthesis(body_md) or body_md[:600]
        ok, cos = _uc.editorial_cosine_check(para, blog_id)
        # 자기 자신(또는 그 사본)과의 유사도는 높아야 하고, 게이트는 실패해야 함
        assert cos > 0.5
        assert ok is False


class TestEndToEndNoLLM:
    """T3.3: get_unique_data_points → editorial_synthesis_step → gate 체인.

    LLM 호출 경로 없음 (adapter=DB/로컬 조회, synthesis=결정론 템플릿).
    대표 경로 3종(flight/car/curation 실DB read-only) + passthrough 1종.
    """

    def _chain(self, topic_type, topic_id=None):
        pts = get_unique_data_points(topic_type, topic_id)
        if len(pts) < 3:
            pytest.skip(f"{topic_type}: insufficient data ({len(pts)} points)")
        para = editorial_synthesis_step("", pts, {"topic_type": topic_type})
        ok, details = editorial_synthesis_quality_gate(para, pts)
        return pts, para, ok, details

    def test_flight_chain_produces_valid_synthesis(self):
        pts, para, ok, details = self._chain("flight")
        assert len(pts) >= 3
        assert len(para) >= 80
        assert ok is True, details

    def test_car_chain_produces_valid_synthesis(self):
        import sqlite3
        import os
        db = os.path.join(os.path.dirname(__file__), "..", "data", "car.db")
        if not os.path.exists(db):
            pytest.skip("car.db not present")
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                "SELECT id FROM topics WHERE car_id IS NOT NULL LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        if not row:
            pytest.skip("no car topics")
        pts, para, ok, details = self._chain("car", topic_id=row[0])
        assert any(d["source_table"] in ("cars", "trims") for d in pts)
        assert len(para) >= 80
        assert ok is True, details

    def test_curation_chain_produces_valid_synthesis(self):
        import sqlite3
        import os
        db = os.path.join(os.path.dirname(__file__), "..", "data", "curation.db")
        if not os.path.exists(db):
            pytest.skip("curation.db not present")
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                "SELECT keyword FROM products WHERE keyword IS NOT NULL LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        if not row:
            pytest.skip("no curation products")
        pts, para, ok, details = self._chain("curation", topic_id=row[0])
        assert any(d["source_table"] == "products" for d in pts)
        assert len(para) >= 80
        assert ok is True, details

    def test_unknown_topic_passthrough_is_noop(self):
        """passthrough: 미등록 topic_type → [] → 빈 synthesis → gate False."""
        pts = get_unique_data_points("nonexistent_type", None)
        assert pts == []
        para = editorial_synthesis_step("", pts, {})
        assert para == ""
        ok, details = editorial_synthesis_quality_gate(para, pts)
        assert ok is False


class TestUniqueDataPointsStorage:
    """W4 T4.1: mark_published_by_id optional unique_data_points 저장 (tmp DB — prod 미접촉).
    W4 T4.2: dispatcher._stored_points_to_gate_data 저장 JSON → S03 gate 입력 변환.
    """

    @staticmethod
    def _tmp_travelen(tmp_path):
        import sqlite3
        db_path = str(tmp_path / "travel-en.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE flight_topics (id INTEGER PRIMARY KEY, exhausted INTEGER DEFAULT 0,"
            " unique_data_points TEXT)"
        )
        conn.execute(
            "CREATE TABLE publish_log (log_id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " topic_id INTEGER, blog_id TEXT, title TEXT, slug TEXT,"
            " published_at TEXT, url TEXT)"
        )
        conn.execute("INSERT INTO flight_topics (id) VALUES (42)")
        conn.execute("INSERT INTO flight_topics (id) VALUES (7)")
        conn.commit()
        conn.close()
        return db_path

    def test_mark_published_stores_points_json(self, tmp_path, monkeypatch):
        import json as _json
        import sqlite3
        from pipelines.etap import topic_manager as tm
        db_path = self._tmp_travelen(tmp_path)
        monkeypatch.setattr(tm, "DB_PATH", db_path)
        pts = [{"label": "min_price", "value": 320, "unit": "USD",
                "source_table": "flight_prices"},
               {"label": "departure_date", "value": "2026-09-01", "unit": "date",
                "source_table": "flight_prices"}]
        ok = tm.mark_published_by_id(42, "flight_topics", "flights-hugo", "t", "s-42",
                                     unique_data_points=pts)
        assert ok is True
        conn = sqlite3.connect(db_path)
        try:
            exhausted, stored = conn.execute(
                "SELECT exhausted, unique_data_points FROM flight_topics WHERE id = 42"
            ).fetchone()
            # publish_log INSERT는 무변경 — 컬럼 추가 없음 (T4.1 체커 사양)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(publish_log)").fetchall()}
        finally:
            conn.close()
        assert exhausted == 1
        assert _json.loads(stored) == pts
        assert "unique_data_points" not in cols

    def test_mark_published_without_points_backward_compat(self, tmp_path, monkeypatch):
        """unique_data_points 미전달(None) → 기존 경로 그대로, 컬럼 NULL."""
        import sqlite3
        from pipelines.etap import topic_manager as tm
        db_path = self._tmp_travelen(tmp_path)
        monkeypatch.setattr(tm, "DB_PATH", db_path)
        ok = tm.mark_published_by_id(7, "flight_topics", "flights-hugo", "t2", "s-07")
        assert ok is True
        conn = sqlite3.connect(db_path)
        try:
            exhausted, stored = conn.execute(
                "SELECT exhausted, unique_data_points FROM flight_topics WHERE id = 7"
            ).fetchone()
        finally:
            conn.close()
        assert exhausted == 1
        assert stored is None

    def test_stored_points_to_gate_data_conversion(self):
        import json as _json
        from dispatcher import _stored_points_to_gate_data
        raw = _json.dumps([
            {"label": "min_price", "value": "320", "unit": "USD",
             "source_table": "flight_prices"},
            {"label": "airline", "value": "Korean Air", "unit": "",
             "source_table": "flight_prices"},
            {"label": "empty_val", "value": None},
            "garbage-row",
        ])
        out = _stored_points_to_gate_data(raw)
        assert out == {"stored_unique_data_points": [
            {"min_price": "320"}, {"airline": "Korean Air"}]}
        # 폴백 보존: 깨진 입력은 {} (gate 입력 없음 → 기존 재구성값만 사용)
        assert _stored_points_to_gate_data(None) == {}
        assert _stored_points_to_gate_data("") == {}
        assert _stored_points_to_gate_data("not-json") == {}
        assert _stored_points_to_gate_data(_json.dumps([])) == {}


class TestS03S04Blocking:
    """W4 T4.2: S03/S04 blocking 전환 + kill-switch (tmp site 픽스처, LLM 0회).

    S04는 완전 기능 검증(tmp site + 미치환 마커). S03은 prod travel-en.db를
    read-only로만 건드리는 구조라 slug 미일치로 gate skip 경로만 검증하고,
    저장값 병합 로직은 TestUniqueDataPointsStorage의 변환 단위테스트로 커버.
    """

    @staticmethod
    def _make_site(tmp_path):
        import os
        site = tmp_path / "site"
        post = site / "content" / "posts" / "w4test-post-a7x9"
        post.mkdir(parents=True)
        body = "Paragraph text about travel deals and prices. " * 40
        (post / "index.md").write_text(
            "---\ntitle: W4 Test\ndate: 2026-08-25\n"
            "categories: [travel]\ntags: [test]\n---\n\n"
            + body + "\n\n{{unreplaced_marker}}\n",
            encoding="utf-8",
        )
        # mtime이 cutoff(7일) 안쪽임을 보장
        os.utime(post / "index.md")
        return str(site)

    def _run(self, tmp_path, monkeypatch):
        import dispatcher
        site = self._make_site(tmp_path)
        monkeypatch.setattr(dispatcher, "_load_all_blogs",
                            lambda: {"blogs": [{"id": "deals-hugo", "site_path": site}]})
        return dispatcher.preflight_check("deals-hugo")

    def test_s04_blocks_by_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUALITY_ENFORCE_S03_S04", raising=False)
        res = self._run(tmp_path, monkeypatch)
        rules = {v["rule_id"] for v in res["violations"]}
        assert "S04" in rules
        assert res["blocked"] is True

    def test_kill_switch_restores_warn_only(self, tmp_path, monkeypatch):
        """QUALITY_ENFORCE_S03_S04=0 → 위반 기록 유지, blocked 미설정(warn-only)."""
        monkeypatch.setenv("QUALITY_ENFORCE_S03_S04", "0")
        res = self._run(tmp_path, monkeypatch)
        rules = {v["rule_id"] for v in res["violations"]}
        assert "S04" in rules
        assert res["blocked"] is False

    def test_s03_gate_skipped_without_verifiable_values(self, tmp_path, monkeypatch):
        """저장값·재구성값 없는 slug → gate skip → S03 오탐(전량 차단) 없음."""
        monkeypatch.setenv("QUALITY_ENFORCE_S03_S04", "1")
        res = self._run(tmp_path, monkeypatch)
        assert "S03" not in {v["rule_id"] for v in res["violations"]}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
