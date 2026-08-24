"""test_editorial.py - Wave 2a Editorial Synthesis 단위 테스트"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from pipelines.etap.post_processor import editorial_synthesis_step, count_verifiable_data_points


class TestEditorialSynthesis:
    """Wave 2a: Editorial Synthesis Step 테스트"""

    def test_template_marker_replacement(self):
        """템플릿 마커 치환 테스트"""
        content = "Flight from {{origin}} to {{destination}} costs {{price}}."
        source_data = {
            "origin": "New York",
            "destination": "Paris",
            "price": 450
        }
        
        result, count = editorial_synthesis_step(content, source_data)
        
        assert "New York" in result
        assert "Paris" in result
        assert "450" in result
        assert "{{origin}}" not in result
        assert "{{destination}}" not in result
        assert "{{price}}" not in result

    def test_missing_template_marker(self):
        """source_data에 없는 마커는 그대로 둠"""
        content = "Flight from {{origin}} to {{destination}}."
        source_data = {
            "origin": "New York"
            # destination 없음
        }
        
        result, count = editorial_synthesis_step(content, source_data)
        
        assert "New York" in result
        assert "{{destination}}" in result  # 치환되지 않음

    def test_price_data_injection(self):
        """가격 데이터 자동 주입 테스트"""
        content = "## Introduction\n\nGreat flights available."
        source_data = {
            "flight_prices": [
                {"price": 450},
                {"price": 600}
            ]
        }
        
        result, count = editorial_synthesis_step(content, source_data)
        
        assert "Price range" in result
        assert "450" in result
        assert "600" in result
        assert count > 0

    def test_date_data_injection(self):
        """날짜 데이터 자동 주입 테스트"""
        content = "## Introduction\n\nGreat flights available."
        source_data = {
            "flight_prices": [
                {"departure_date": "2024-03-15"}
            ]
        }
        
        result, count = editorial_synthesis_step(content, source_data)
        
        assert "Travel dates" in result
        assert "2024-03-15" in result
        assert count > 0

    def test_airline_data_injection(self):
        """항공사 데이터 자동 주입 테스트"""
        content = "## Introduction\n\nGreat flights available."
        source_data = {
            "flight_prices": [
                {"airline": "Air France"},
                {"airline": "Delta"}
            ]
        }
        
        result, count = editorial_synthesis_step(content, source_data)
        
        assert "Operated by" in result
        assert "Air France" in result
        assert "Delta" in result
        assert count > 0

    def test_count_verifiable_data_points(self):
        """검증 가능 데이터 포인트 카운트 테스트"""
        content = "Flight from New York to Paris for $450 on March 15, 2024 via Air France."
        source_data = {
            "flight_prices": [
                {"price": 450, "origin": "New York", "destination": "Paris", 
                 "departure_date": "2024-03-15", "airline": "Air France"}
            ]
        }
        
        count = count_verifiable_data_points(content, source_data)
        
        assert count >= 3  # price, date, airline, origin, destination 중 최소 3개

    def test_empty_source_data(self):
        """빈 source_data 처리"""
        content = "Any content."
        source_data = {}
        
        result, count = editorial_synthesis_step(content, source_data)
        
        assert result == content
        assert count == 0

    def test_nested_data_structure(self):
        """중첩 데이터 구조 처리"""
        content = "Price is {{price}}."
        source_data = {
            "flight_prices": [
                {"price": 450}
            ]
        }
        
        result, count = editorial_synthesis_step(content, source_data)
        
        assert "450" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])