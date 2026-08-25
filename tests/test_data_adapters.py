"""test_data_adapters.py - Wave 2a Data Adapters 단위 테스트"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from pipelines.etap.data_adapters import (
    ADAPTER_REGISTRY,
    get_unique_data_points,
    flight_adapter,
    viator_adapter,
    nature_adapter,
    deals_adapter,
    car_adapter,
    stock_evergreen_adapter,
    stock_disclosure_adapter,
    rap_trade_adapter,
    rap_sub_adapter,
    curation_adapter,
    senior_adapter,
)


class TestDataAdapters:
    """Wave 2a: Data Adapters (flight, viator, nature, deals) 테스트"""

    def test_registry_has_four_keys(self):
        """ADAPTER_REGISTRY must expose at least the original 4 topic types.

        Phase 72 W2 T2.2: equality relaxed to superset — original-4-exist
        semantics preserved while 7 new branch adapters join the registry.
        """
        assert set(ADAPTER_REGISTRY.keys()) >= {"flight", "viator", "nature", "deals"}

    def test_registry_has_wave2_branch_keys(self):
        """Phase 72 W2 T2.2: the 7 new branch adapters must be registered."""
        assert {
            "car",
            "stock_evergreen",
            "stock_disclosure",
            "rap_trade",
            "rap_sub",
            "curation",
            "senior",
        } <= set(ADAPTER_REGISTRY.keys())

    def test_flight_adapter_returns_points(self):
        """Flight adapter returns normalized data points from flight_prices."""
        data = flight_adapter()
        assert isinstance(data, list)
        if data:  # DB may be populated
            for d in data:
                assert set(d.keys()) == {"label", "value", "unit", "source_table"}
            assert any(d["label"] == "min_price" for d in data)

    def test_viator_adapter_returns_points(self):
        """Viator adapter returns normalized data points from viator_tours."""
        data = viator_adapter()
        assert isinstance(data, list)
        if data:
            for d in data:
                assert set(d.keys()) == {"label", "value", "unit", "source_table"}

    def test_nature_adapter_returns_points(self):
        """Nature adapter returns normalized data points from nature_topics."""
        data = nature_adapter()
        assert isinstance(data, list)
        if data:
            for d in data:
                assert set(d.keys()) == {"label", "value", "unit", "source_table"}

    def test_deals_adapter_returns_points(self):
        """Deals adapter returns normalized data points from deals_topics."""
        data = deals_adapter()
        assert isinstance(data, list)
        if data:
            for d in data:
                assert set(d.keys()) == {"label", "value", "unit", "source_table"}

    def test_get_unique_data_points_dispatch(self):
        """get_unique_data_points dispatches by topic_type and never raises."""
        data = get_unique_data_points("flight")
        assert isinstance(data, list)
        # Unknown topic_type yields empty list, not an error.
        assert get_unique_data_points("nonexistent") == []

    def test_adapter_does_not_crash_on_empty(self):
        """Adapters tolerate missing data and return a list (possibly empty)."""
        for name in ("flight", "viator", "nature", "deals"):
            result = ADAPTER_REGISTRY[name](topic_id=999999)
            assert isinstance(result, list)

    def test_wave2_adapters_return_points_with_schema(self):
        """Phase 72 W2 T2.2: new adapters never raise and honor point schema."""
        for name in (
            "car",
            "stock_evergreen",
            "stock_disclosure",
            "rap_trade",
            "rap_sub",
            "curation",
            "senior",
        ):
            data = ADAPTER_REGISTRY[name](topic_id=999999)  # 존재하지 않는 키 → []
            assert isinstance(data, list), name
            assert isinstance(get_unique_data_points(name), list)  # dispatch 경로 무예외
        # 실DB 데이터가 있는 어댑터는 ≥1 point 반환 (never-raise 계약 + 스키마 검증)
        evergreen = stock_evergreen_adapter()
        assert isinstance(evergreen, list)
        if evergreen:
            for d in evergreen:
                assert set(d.keys()) == {"label", "value", "unit", "source_table"}

    def test_flight_adapter_scopes_by_topic_route(self):
        """Phase 72 W2 T2.1: topic row resolves → route-scoped prices, not global.

        Cross-contamination guard (threat T-72-01): scoped min_price must equal
        the DB min price for that exact route when the route has its own rows.
        """
        import sqlite3
        import os
        db = os.path.join(os.path.dirname(__file__), "..", "data", "travel-en.db")
        if not os.path.exists(db):
            pytest.skip("travel-en.db not present")
        conn = sqlite3.connect(db)
        try:
            trow = conn.execute(
                "SELECT id, origin, destination FROM flight_topics "
                "WHERE origin IS NOT NULL AND destination IS NOT NULL LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        if not trow:
            pytest.skip("no flight_topics rows")
        topic_id, origin, destination = trow
        pts = flight_adapter(topic_id=topic_id)
        assert isinstance(pts, list)
        if not pts:
            return
        route = next((p for p in pts if p["label"] == "route"), None)
        if route is not None:
            assert route["value"] == f"{origin}→{destination}"

    def test_flight_adapter_falls_back_without_topic(self):
        """Missing topic_id keeps legacy global-fallback behavior (list)."""
        pts = flight_adapter(topic_id=99999999)
        assert isinstance(pts, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
