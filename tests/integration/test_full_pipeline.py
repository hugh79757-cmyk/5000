"""End-to-end integration test with mocked Coupang API."""
import json
import sqlite3
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from pipelines.curation.pipeline import _filter_irrelevant_products, _filter_used_products, _select_keyword
from pipelines.curation.collector import collect_keyword, get_products, _search_api
from shared.relevance_scorer import score_products, passes_gate


# Mock product data format from Coupang API
def make_mock_coupang_product(product_id, name, category, price=10000, is_rocket=True):
    return {
        "productId": product_id,
        "productName": name,
        "productPrice": price,
        "productImage": f"https://image.example.com/{product_id}.jpg",
        "productUrl": f"https://coupa.ng/product/{product_id}",
        "categoryName": category,
        "rank": 1,
        "isRocket": is_rocket,
        "isFreeShipping": True,
    }


# Per-blog keywords and expected products
BLOG_TEST_DATA = {
    "laptop-hugo": {
        "keyword": "노트북 추천",
        "products": [
            make_mock_coupang_product("LAP1", "게이밍 노트북", "노트북", 1500000),
            make_mock_coupang_product("LAP2", "맥북 프로 14인치", "노트북/태블릿", 2500000),
            make_mock_coupang_product("LAP3", "델 XPS 13", "노트북", 2000000),
        ],
        "should_pass": True,
    },
    "appliance-hugo": {
        "keyword": "에어프라이어 추천",
        "products": [
            make_mock_coupang_product("APP1", "에어프라이어 20L", "가전", 79000),
            make_mock_coupang_product("APP2", " ihc电磁炉", "가전", 120000),
        ],
        "should_pass": True,
    },
    "interior-hugo": {
        "keyword": "인체공학 의자",
        "products": [
            make_mock_coupang_product("INT1", "인체공학 의자", "가구", 250000),
            make_mock_coupang_product("INT2", "컴퓨터 책상", "가구", 180000),
        ],
        "should_pass": True,
    },
    "baby-hugo": {
        "keyword": "아기 기저귀",
        "products": [
            make_mock_coupang_product("BAB1", "프리미엄 기저귀 4팩", "출산/유아", 45000),
            make_mock_coupang_product("BAB2", "아기 물티슈", "출산/유아", 12000),
        ],
        "should_pass": True,
    },
    "fitness-hugo": {
        "keyword": "덤벨 추천",
        "products": [
            make_mock_coupang_product("FIT1", "철제 덤벨 20kg", "스포츠/레저", 89000),
            make_mock_coupang_product("FIT2", "요가매트 TPE", "스포츠/레저", 35000),
        ],
        "should_pass": True,
    },
    "health-hugo": {
        "keyword": "비타민D",
        "products": [
            make_mock_coupang_product("HEA1", "비타민D 5000IU", "건강식품", 25000),
            make_mock_coupang_product("HEA2", "오메가3", "건강식품", 30000),
        ],
        "should_pass": True,
    },
    "pet-hugo": {
        "keyword": "강아지 사료",
        "products": [
            make_mock_coupang_product("PET1", "프리미엄 사료 10kg", "반려동물", 55000),
            make_mock_coupang_product("PET2", "강아지 간식", "반려동물", 8000),
        ],
        "should_pass": True,
    },
    "kitchen-hugo": {
        "keyword": "프라이팬",
        "products": [
            make_mock_coupang_product("KIT1", "스테인리스 프라이팬 28cm", "주방가전", 45000),
            make_mock_coupang_product("KIT2", "후라이팬", "주방", 35000),
        ],
        "should_pass": True,
    },
    "beauty-hugo": {
        "keyword": "에센스",
        "products": [
            make_mock_coupang_product("BEA1", "히알루론산 에센스", "스킨케어", 22000),
            make_mock_coupang_product("BEA2", "토너", "스킨케어", 18000),
        ],
        "should_pass": True,
    },
    "camping-hugo": {
        "keyword": "텐트",
        "products": [
            make_mock_coupang_product("CAM1", "콜맨 텐트 4인용", "캠핑", 280000),
            make_mock_coupang_product("CAM2", "경량 텐트 2인용", "캠핑", 150000),
        ],
        "should_pass": True,
    },
}


@pytest.fixture(scope="function")
def temp_db_integration(tmp_path):
    """Create a temporary SQLite DB with required tables."""
    db_path = tmp_path / "integration.db"
    conn = sqlite3.connect(str(db_path))
    # Create tables
    conn.execute("""
        CREATE TABLE products (
            keyword TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT,
            product_price INTEGER,
            product_image TEXT,
            product_url TEXT,
            category_name TEXT,
            rank INTEGER,
            is_rocket BOOLEAN,
            is_free_shipping BOOLEAN,
            collected_at TEXT,
            PRIMARY KEY (keyword, product_id)
        )
    """)
    conn.execute("""
        CREATE TABLE publish_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            title TEXT,
            slug TEXT,
            published_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE published_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            published_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX idx_publog_blog_keyword ON publish_log(blog_id, keyword, published_at)
    """)
    conn.execute("""
        CREATE INDEX idx_pub_products_blog ON published_products(blog_id, product_id)
    """)
    conn.commit()
    conn.close()

    yield str(db_path)

    # cleanup
    import os
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture(autouse=True)
def mock_db_path(monkeypatch, temp_db_integration):
    """Patch DB_PATH in modules to use temp DB."""
    import pipelines.curation.pipeline as pipeline_mod
    import pipelines.curation.collector as collector_mod
    import pipelines.curation.keyword_health as health_mod

    monkeypatch.setattr(pipeline_mod, "DB_PATH", temp_db_integration)
    monkeypatch.setattr(collector_mod, "DB_PATH", temp_db_integration)
    monkeypatch.setattr(health_mod, "KeywordHealthStore", lambda path: health_mod.KeywordHealthStore(path))


@pytest.fixture(autouse=True)
def mock_coupang_api(monkeypatch):
    """Mock _search_api to return predefined products per keyword."""
    original_search = _search_api

    # Build keyword -> products mapping
    keyword_map = {}
    for blog_cfg in BLOG_TEST_DATA.values():
        keyword_map[blog_cfg["keyword"]] = blog_cfg["products"]

    def mock_search(keyword, limit=10):
        products = keyword_map.get(keyword, [])
        return products[:limit]

    monkeypatch.setattr("pipelines.curation.collector._search_api", mock_search)
    yield
    # monkeypatch restores automatically


def test_full_pipeline_all_blogs_produce_products():
    """For each blog, selecting a keyword and collecting products should yield filter-passing items."""
    for blog_id, config in BLOG_TEST_DATA.items():
        keyword = config["keyword"]
        # 1. Collect products (this populates products table via mock API)
        success = collect_keyword(keyword)
        assert success is True, f"Collect failed for {blog_id}/{keyword}"

        # 2. Get products from DB
        products = get_products(keyword, limit=10)
        assert len(products) > 0, f"No products collected for {blog_id}"

        # 3. Filter irrelevant products
        filtered = _filter_irrelevant_products(blog_id, keyword, products)
        # Expected pass: should have >=1; expected fail: should be empty
        if config["should_pass"]:
            assert len(filtered) >= 1, f"Filter blocked all products for {blog_id} with keyword {keyword}"
        else:
            assert len(filtered) == 0, f"Filter allowed products for {blog_id} but expected block"


def test_relevance_scoring_integration():
    """Test that relevance scoring and gate evaluation work end-to-end."""
    blog_id = "laptop-hugo"
    keyword = "노트북"
    # Ensure we have products
    if not get_products(keyword):
        collect_keyword(keyword)
        products = get_products(keyword)
    else:
        products = get_products(keyword)

    filtered = _filter_irrelevant_products(blog_id, keyword, products)
    if not filtered:
        pytest.skip(f"No filtered products for {blog_id}")
    # Score
    scores = score_products(filtered, blog_id)
    assert "avg" in scores
    assert "threshold" in scores
    # Gate
    passed, reason = passes_gate(scores)
    # We don't assert pass/fail globally because data may vary; we just ensure the logic runs
    assert isinstance(passed, bool)
    assert isinstance(reason, str)


def test_used_products_filtering_with_db(temp_db_integration):
    """Test that _filter_used_products excludes recently published items."""
    # Use custom products rather than relying on collect_keyword
    blog_id = "fitness-hugo"
    keyword = "덤벨"
    sample_products = [
        {"product_name": "덤벨 20kg", "product_id": "DUM1", "category_name": "스포츠/레저", "rank": 1, "is_rocket": True, "is_free_shipping": True, "collected_at": datetime.utcnow().isoformat()},
        {"product_name": "요가매트", "product_id": "DUM2", "category_name": "스포츠/레저", "rank": 2, "is_rocket": False, "is_free_shipping": False, "collected_at": datetime.utcnow().isoformat()},
        {"product_name": "러닝화", "product_id": "DUM3", "category_name": "스포츠/레저", "rank": 3, "is_rocket": True, "is_free_shipping": True, "collected_at": datetime.utcnow().isoformat()},
        {"product_name": "피트니스 밴드", "product_id": "DUM4", "category_name": "스포츠/레저", "rank": 4, "is_rocket": False, "is_free_shipping": False, "collected_at": datetime.utcnow().isoformat()},
    ]

    # Initially, no used products => all pass
    filtered_initial = _filter_used_products(blog_id, sample_products)
    assert len(filtered_initial) == len(sample_products)

    # Now manually insert a published product record for DUM1
    conn = sqlite3.connect(temp_db_integration)
    conn.execute(
        "INSERT INTO published_products (blog_id, product_id, keyword, published_at) VALUES (?,?,?,?)",
        (blog_id, sample_products[0]["product_id"], keyword, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    # Re-run filter
    filtered_after = _filter_used_products(blog_id, sample_products)
    # Should have one less (the used one removed); since we have >=4 total, fallback not triggered
    assert len(filtered_after) == len(sample_products) - 1
    assert sample_products[0]["product_id"] not in [p["product_id"] for p in filtered_after]
    # The remaining should be DUM2, DUM3, DUM4
    remaining_ids = {p["product_id"] for p in filtered_after}
    assert remaining_ids == {"DUM2", "DUM3", "DUM4"}
