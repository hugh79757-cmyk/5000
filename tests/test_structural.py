"""test_structural.py - S02 Structural Similarity Gate 단위 테스트"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from pipelines.etap.quality_guard import structural_similarity_gate


class TestStructuralSimilarityGate:
    """S02: Structural Similarity ≤ 0.70 테스트"""

    def test_different_h2_structure_passes(self):
        """완전히 다른 H2 구조는 통과해야 함"""
        corpus = [
            "## Introduction\n\nContent.\n\n## Paris Attractions\n\nContent.\n\n## Travel Tips\n\nContent.",
            "## Overview\n\nContent.\n\n## London Museums\n\nContent.\n\n## Budget Guide\n\nContent.",
        ]
        content = "## Introduction\n\nContent.\n\n## Sydney Beaches\n\nContent.\n\n## Surfing Guide\n\nContent."

        passed, sim, details = structural_similarity_gate(content, corpus, threshold=0.70)

        assert passed is True
        assert sim <= 0.70
        assert len(details["content_h2s"]) == 3

    def test_same_h2_structure_fails(self):
        """동일한 H2 구조는 실패해야 함 (템플릿 재사용 탐지)"""
        corpus = [
            "## Introduction\n\nThis is the introduction content with enough text to pass the length filter.\n\n## Top Attractions\n\nHere are the top attractions with detailed descriptions for visitors.\n\n## Travel Tips\n\nUseful travel tips and advice for making the most of your trip.",
            "## Overview\n\nOverview content with sufficient length to pass the minimum length filter.\n\n## Best Restaurants\n\nBest restaurants in the area with detailed reviews and recommendations.\n\n## Budget Guide\n\nBudget guide with money saving tips and cost breakdowns for travelers.",
        ]
        # H2 순서와 개수가 동일한 템플릿
        content = "## Introduction\n\nThis is the introduction content with enough text to pass the length filter.\n\n## Top Attractions\n\nHere are the top attractions with detailed descriptions for visitors.\n\n## Travel Tips\n\nUseful travel tips and advice for making the most of your trip."

        passed, sim, details = structural_similarity_gate(content, corpus, threshold=0.70)

        assert passed is False
        assert sim > 0.70
        assert details["content_h2s"] == ["introduction", "top attractions", "travel tips"]

    def test_partial_h2_overlap(self):
        """부분적인 H2 겹침 테스트"""
        corpus = [
            "## Introduction\n\nThis is the introduction content with enough text to pass the length filter.\n\n## Paris Attractions\n\nDetailed information about Paris attractions for visitors.\n\n## Travel Tips\n\nUseful travel tips and advice for making the most of your trip.",
        ]
        content = "## Introduction\n\nThis is the introduction content with enough text to pass the length filter.\n\n## Paris Attractions\n\nDetailed information about Paris attractions for visitors.\n\n## Budget Guide\n\nBudget guide with money saving tips for travelers."

        passed, sim, details = structural_similarity_gate(content, corpus, threshold=0.70)

        # 2개 중 2개 겹침 (bigram 기준)
        assert details["n_compared"] == 1
        assert 0 <= sim <= 1.0

    def test_no_h2_headings(self):
        """H2 헤딩이 없는 콘텐츠"""
        corpus = ["## Introduction\n\nContent."]
        content = "Just plain text without headings."

        passed, sim, details = structural_similarity_gate(content, corpus, threshold=0.70)

        assert passed is True
        assert sim == 0.0
        assert details["content_h2s"] == []

    def test_empty_corpus(self):
        """빈 corpus"""
        content = "## Introduction\n\nContent."

        passed, sim, details = structural_similarity_gate(content, [], threshold=0.70)

        assert passed is True
        assert sim == 0.0
        assert details["n_compared"] == 0

    def test_custom_threshold(self):
        """커스텀 threshold 테스트"""
        corpus = [
            "## Introduction\n\nContent with enough text to pass the filter length requirement here.\n\n## Attractions\n\nMore content describing attractions in detail for the length check.",
        ]
        content = "## Introduction\n\nContent with enough text to pass the filter length requirement here.\n\n## Attractions\n\nMore content describing attractions in detail for the length check."

        passed, sim, details = structural_similarity_gate(content, corpus, threshold=0.90)

        # threshold를 높이면 통과할 수 있음
        assert details["threshold"] == 0.90

    def test_h2_normalization(self):
        """H2 정규화 테스트 (대소문자, 구두점 무시)"""
        corpus = [
            "## INTRODUCTION\n\nContent with enough text to pass the filter length requirement here.\n\n## TOP ATTRACTIONS!\n\nMore content describing attractions in detail for the length check.",
        ]
        content = "## Introduction\n\nContent with enough text to pass the filter length requirement here.\n\n## Top Attractions\n\nMore content describing attractions in detail for the length check."

        passed, sim, details = structural_similarity_gate(content, corpus, threshold=0.70)

        # 정규화 후 동일하게 처리되어야 함
        assert details["content_h2s"] == ["introduction", "top attractions"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
