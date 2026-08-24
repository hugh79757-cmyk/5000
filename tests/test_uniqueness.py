"""test_uniqueness.py - S01 Uniqueness Ratio Gate 단위 테스트"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from pipelines.etap.quality_guard import uniqueness_ratio_gate


class TestUniquenessRatioGate:
    """S01: Uniqueness Ratio ≥ 0.85 테스트"""

    def test_unique_content_passes(self):
        """완전히 고유한 콘텐츠는 통과해야 함"""
        corpus = [
            "This is a comprehensive article about Paris travel guide with detailed tips for visitors including attractions, restaurants, and transportation options.",
            "Another detailed article about London attractions and restaurants covering museums, historic sites, and local cuisine recommendations.",
            "Tokyo travel guide for first time visitors with extensive coverage of neighborhoods, cultural sites, and practical travel advice.",
        ]
        content = "This is a completely new article about Sydney beaches and surfing with detailed information about coastal walks, beach culture, and surfing spots."
        
        passed, ratio, details = uniqueness_ratio_gate(content, corpus, threshold=0.85)
        
        assert passed is True
        assert ratio >= 0.85
        assert details["n_compared"] == 3

    def test_duplicate_content_fails(self):
        """기존 콘텐츠와 거의 동일한 콘텐츠는 실패해야 함"""
        corpus = [
            "This is a comprehensive article about Paris travel guide with detailed tips for visitors including attractions, restaurants, and transportation options.",
            "Another detailed article about London attractions and restaurants covering museums, historic sites, and local cuisine recommendations.",
        ]
        # corpus[0]과 매우 유사한 콘텐츠
        content = "This is a comprehensive article about Paris travel guide with detailed tips for visitors including attractions, restaurants, and transportation options."
        
        passed, ratio, details = uniqueness_ratio_gate(content, corpus, threshold=0.85)
        
        assert passed is False
        assert ratio < 0.85
        assert details["max_similarity"] > 0.9

    def test_partial_overlap(self):
        """일부 겹치는 콘텐츠 테스트"""
        corpus = [
            "Paris is a beautiful city with many attractions like Eiffel Tower and Louvre museum, offering visitors a rich cultural experience with many historical sites.",
            "London has great museums and historic sites that attract millions of tourists every year, including the British Museum and Tower of London.",
        ]
        content = "Paris is a beautiful city with many attractions including Eiffel Tower and other landmarks worth visiting for tourists."
        
        passed, ratio, details = uniqueness_ratio_gate(content, corpus, threshold=0.85)
        
        # 부분 겹침이어도 threshold 0.85보다는 높을 수 있음
        assert details["n_compared"] == 2
        assert 0 <= ratio <= 1.0

    def test_empty_corpus(self):
        """빈 corpus는 통과해야 함 (비교 대상 없음)"""
        content = "Any content here."
        
        passed, ratio, details = uniqueness_ratio_gate(content, [], threshold=0.85)
        
        assert passed is True
        assert ratio == 1.0
        assert details["n_compared"] == 0

    def test_short_content(self):
        """너무 짧은 콘텐츠 처리"""
        corpus = ["This is a longer article with enough content."]
        content = "Short."
        
        passed, ratio, details = uniqueness_ratio_gate(content, corpus, threshold=0.85)
        
        # 짧은 콘텐츠도 처리되어야 함 (에러 없이)
        assert "n_compared" in details

    def test_custom_threshold(self):
        """커스텀 threshold 테스트"""
        corpus = ["Article about Paris travel with detailed information about attractions and tips for visitors and more content to make it long enough."]
        content = "Article about Paris travel guide with more details and additional information."
        
        passed, ratio, details = uniqueness_ratio_gate(content, corpus, threshold=0.50)
        
        assert details["threshold"] == 0.50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])