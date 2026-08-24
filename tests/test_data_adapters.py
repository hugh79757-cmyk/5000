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
)


class TestDataAdapters:
    """Wave 2a: Data Adapters (flight, viator, nature, deals) 테스트"""

    def test_registry_has_four_keys(self):
        """ADAPTER_REGISTRY must expose exactly the 4 planned topic types."""
        assert set(ADAPTER_REGISTRY.keys()) == {"flight", "viator", "nature", "deals"}

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
