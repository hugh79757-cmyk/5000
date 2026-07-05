import sys
sys.path.insert(0, "/Users/twinssn/Projects/5000")

import pytest
from unittest.mock import patch
from pipelines.curation.pipeline import (
    _filter_irrelevant_products,
    _filter_used_products,
    _make_slug,
    _extract_category,
    _title_is_duplicate,
    CATEGORY_FILTERS,
)


class TestFilterIrrelevantProducts:
    def test_allowed_keyword_in_name_passes(self, sample_products):
        products = _filter_irrelevant_products("laptop-hugo", "노트북 추천", sample_products[:2])
        assert len(products) == 2
        assert any(p["product_id"] == "1001" for p in products)

    def test_blocked_keyword_in_name_filtered(self, sample_products):
        products = _filter_irrelevant_products("fitness-hugo", "운동복 추천", sample_products)
        assert all(p["product_id"] != "2001" for p in products)  # 여성의류 blocked

    def test_blocked_keyword_in_category_filtered(self, sample_products):
        products = _filter_irrelevant_products("baby-hugo", "아기용품", sample_products)
        assert all(p["product_id"] != "3001" for p in products)  # 반려동물 blocked

    def test_no_allowed_keyword_returns_empty(self, sample_products):
        products = _filter_irrelevant_products("kitchen-hugo", "잡화", sample_products[:4])
        assert products == []

    def test_1_to_2_products_still_returned_fallback(self, sample_products):
        products = _filter_irrelevant_products(
            "fitness-hugo", "운동화 추천",
            [{"product_name": "나이키 런닝화 에어맥스", "product_id": "4001", "category_name": "스포츠/레저"}]
        )
        assert len(products) >= 1

    def test_0_products_returns_empty(self):
        result = _filter_irrelevant_products("laptop-hugo", "test", [])
        assert result == []

    def test_unknown_blog_returns_all(self, sample_products):
        products = _filter_irrelevant_products("unknown-blog", "test", sample_products[:3])
        assert len(products) == 3

    def test_beauty_blocks_food_category(self, sample_products):
        products = _filter_irrelevant_products("beauty-hugo", "화장품", sample_products)
        assert all(p["product_id"] != "6001" for p in products)  # 가전 blocked

    def test_fitness_passes_sports_products(self, sample_products):
        products = _filter_irrelevant_products("fitness-hugo", "운동화", [
            {"product_name": "나이키 운동화 에어맥스", "product_id": "4002", "category_name": "스포츠/레저"},
            {"product_name": "요가매트 TPE 10mm", "product_id": "4003", "category_name": "스포츠/레저"},
            {"product_name": "헬스장갑 퀵그립", "product_id": "4004", "category_name": "스포츠/레저"},
        ])
        assert len(products) == 3

    def test_camping_passes_outdoor_products(self, sample_products):
        products = _filter_irrelevant_products("camping-hugo", "캠핑용품", [
            {"product_name": "콜맨 텐트 4인용", "product_id": "7001", "category_name": "캠핑"},
            {"product_name": "버너 스토브", "product_id": "7002", "category_name": "캠핑/레저"},
            {"product_name": "침낭 사계절용", "product_id": "7003", "category_name": "아웃도어"},
        ])
        assert len(products) == 3


class TestFilterUsedProducts:
    def test_recently_used_products_filtered(self, sample_products, temp_db_with_data):
        with patch("pipelines.curation.pipeline.DB_PATH", temp_db_with_data):
            products = _filter_used_products("fitness-hugo", sample_products[:4])
            assert all(p["product_id"] != "2001" for p in products)
            assert all(p["product_id"] != "3001" for p in products)

    def test_unused_products_pass(self, sample_products, temp_db_with_data):
        with patch("pipelines.curation.pipeline.DB_PATH", temp_db_with_data):
            products = _filter_used_products("fitness-hugo", sample_products[7:8])
            assert len(products) == 1

    def test_empty_products_returns_empty(self, temp_db_with_data):
        with patch("pipelines.curation.pipeline.DB_PATH", temp_db_with_data):
            products = _filter_used_products("fitness-hugo", [])
            assert products == []

    def test_different_blog_is_not_filtered(self, sample_products, temp_db_with_data):
        with patch("pipelines.curation.pipeline.DB_PATH", temp_db_with_data):
            products = _filter_used_products("laptop-hugo", sample_products[:4])
            assert len(products) == 4


class TestMakeSlug:
    def test_spaces_become_hyphens(self):
        slug = _make_slug("노트북 추천")
        assert "-" in slug

    def test_special_chars_removed(self):
        slug = _make_slug("노트북! @추천#")
        assert "!" not in slug
        assert "@" not in slug
        assert "#" not in slug

    def test_starts_with_date(self):
        import re
        from datetime import datetime
        slug = _make_slug("테스트")
        assert re.match(r"^\d{8}-", slug)

    def test_lowercase(self):
        slug = _make_slug("Laptop Review")
        assert slug == slug.lower()


class TestExtractCategory:
    def test_first_token_is_category(self):
        assert _extract_category("노트북 추천 게이밍") == "노트북"

    def test_single_word(self):
        assert _extract_category("맥북") == "맥북"


class TestCATEGORY_FILTERS:
    def test_all_10_blogs_have_filters(self):
        assert len(CATEGORY_FILTERS) == 10

    def test_each_filter_has_allowed_and_blocked(self):
        for blog, f in CATEGORY_FILTERS.items():
            assert "allowed" in f, f"{blog} missing 'allowed'"
            assert "blocked" in f, f"{blog} missing 'blocked'"
            assert len(f["allowed"]) > 0, f"{blog} has empty allowed list"
