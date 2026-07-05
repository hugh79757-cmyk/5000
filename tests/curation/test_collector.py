import sys
sys.path.insert(0, "/Users/twinssn/Projects/5000")

import pytest
from unittest.mock import patch
from pipelines.curation.collector import _generate_keyword_variants, _check_rate_limit, get_products, is_cache_valid


class TestGenerateKeywordVariants:
    def test_known_word_generates_variants(self):
        variants = _generate_keyword_variants("노트북 추천")
        assert len(variants) >= 2
        assert "노트북 추천" in variants
        assert any("랩탑" in v or "laptop" in v for v in variants)

    def test_unknown_word_returns_original_only(self):
        variants = _generate_keyword_variants("abcdefgh")
        assert variants == ["abcdefgh"]

    def test_max_3_variants(self):
        variants = _generate_keyword_variants("노트북")
        assert len(variants) <= 3

    def test_suffix_removal_variant(self):
        variants = _generate_keyword_variants("가나다 추천")
        assert any(v == "가나다" for v in variants)

    def test_duplicates_not_added(self):
        variants = _generate_keyword_variants("추천")
        assert len(variants) == 1  # KEYWORD_VARIANTS["추천"] is empty

    def test_variant_is_different_from_original(self):
        variants = _generate_keyword_variants("매트리스 추천")
        assert any(v != "매트리스 추천" for v in variants)


class TestCheckRateLimit:
    def test_under_limit_returns_true(self, temp_db):
        with patch("pipelines.curation.collector.DB_PATH", temp_db):
            assert _check_rate_limit() is True

    def test_over_limit_returns_false(self, temp_db):
        with patch("pipelines.curation.collector.DB_PATH", temp_db):
            conn = __import__("sqlite3").connect(temp_db)
            conn.execute("CREATE TABLE IF NOT EXISTS api_call_log (id INTEGER PRIMARY KEY AUTOINCREMENT, called_at TEXT DEFAULT (datetime('now')))")
            for _ in range(200):
                conn.execute("INSERT INTO api_call_log (called_at) VALUES (datetime('now'))")
            conn.commit()
            conn.close()
            assert _check_rate_limit() is False


class TestGetProducts:
    def test_returns_products_for_keyword(self, temp_db):
        conn = __import__("sqlite3").connect(temp_db)
        conn.execute(
            "INSERT INTO products (keyword, product_id, product_name, collected_at) VALUES (?,?,?,?)",
            ("test-keyword", "1", "Test Product", "2026-07-05T00:00:00")
        )
        conn.execute(
            "INSERT INTO products (keyword, product_id, product_name, collected_at) VALUES (?,?,?,?)",
            ("test-keyword", "2", "Test Product 2", "2026-07-05T00:00:00")
        )
        conn.commit()
        conn.close()
        with patch("pipelines.curation.collector.DB_PATH", temp_db):
            products = get_products("test-keyword", limit=5)
            assert len(products) == 2

    def test_empty_keyword_returns_empty(self, temp_db):
        with patch("pipelines.curation.collector.DB_PATH", temp_db):
            products = get_products("nonexistent", limit=5)
            assert products == []
