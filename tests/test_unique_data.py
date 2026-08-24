"""test_unique_data.py - S03 Unique Data Points Gate 단위 테스트"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from pipelines.etap.quality_guard import unique_data_points_gate


class TestUniqueDataPointsGate:
    """S03: Unique Data Points ≥ 3 테스트"""

    def test_sufficient_data_points_passes(self):
        """충분한 데이터 포인트가 있으면 통과"""
        content = """
        ## Introduction
        The cheapest flight from New York to Paris is $450 on Air France.
        Departure date is March 15, 2024. The flight duration is 7 hours.
        """
        source_data = {
            "flight_prices": [
                {"price": 450, "airline": "Air France", "departure_date": "2024-03-15", "duration": 7}
            ]
        }
        
        passed, count, details = unique_data_points_gate(content, source_data, threshold=3)
        
        assert passed is True
        assert count >= 3
        assert "price:$450" in str(details["found_points"]) or "price:450" in str(details["found_points"])

    def test_insufficient_data_points_fails(self):
        """데이터 포인트가 부족하면 실패"""
        content = """
        ## Introduction
        Paris is a great city to visit.
        """
        source_data = {
            "flight_prices": [
                {"price": 450, "airline": "Air France"}
            ]
        }
        
        passed, count, details = unique_data_points_gate(content, source_data, threshold=3)
        
        assert passed is False
        assert count < 3

    def test_price_verification(self):
        """가격 검증 테스트"""
        content = "Flight from $450 to $500."
        source_data = {
            "flight_prices": [{"price": 450}, {"price": 500}]
        }
        
        passed, count, details = unique_data_points_gate(content, source_data, threshold=2)
        
        assert count >= 2

    def test_date_verification(self):
        """날짜 검증 테스트 (ISO 포맷으로 본문·소스 일치)"""
        content = "Depart on 2024-03-15 and return 2024-03-22."
        source_data = {
            "flight_prices": [
                {"departure_date": "2024-03-15", "return_date": "2024-03-22"}
            ]
        }
        
        passed, count, details = unique_data_points_gate(content, source_data, threshold=2)
        
        assert count >= 2

    def test_entity_verification(self):
        """엔티티(항공사, 도시 등) 검증 테스트"""
        content = "Air France operates this route from New York to Paris."
        source_data = {
            "flight_prices": [
                {"airline": "Air France", "origin": "New York", "destination": "Paris"}
            ]
        }
        
        passed, count, details = unique_data_points_gate(content, source_data, threshold=3)
        
        assert count >= 3

    def test_metric_verification(self):
        """메트릭(소요시간, 경유지 등) 검증 테스트"""
        content = "Duration is 7 hours with 0 stops."
        source_data = {
            "flight_prices": [
                {"duration": 7, "stops": 0}
            ]
        }
        
        passed, count, details = unique_data_points_gate(content, source_data, threshold=2)
        
        assert count >= 2

    def test_empty_source_data(self):
        """빈 source_data 처리"""
        content = "Any content."
        source_data = {}
        
        passed, count, details = unique_data_points_gate(content, source_data, threshold=3)
        
        assert passed is False
        assert count == 0

    def test_no_source_data(self):
        """source_data가 None인 경우"""
        content = "Any content."
        source_data = None
        
        passed, count, details = unique_data_points_gate(content, source_data, threshold=3)
        
        assert passed is False
        assert count == 0

    def test_tolerance_matching(self):
        """허용 오차 내 매칭 테스트 ($2 차이 허용)"""
        content = "Price is $452."
        source_data = {
            "flight_prices": [{"price": 450}]
        }
        
        passed, count, details = unique_data_points_gate(content, source_data, threshold=1)
        
        # $452 vs $450 = $2 차이, 허용 범위 내
        assert count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])