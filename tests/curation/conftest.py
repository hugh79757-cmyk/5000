import pytest
import sqlite3
import tempfile
import os
from unittest.mock import patch

@pytest.fixture
def sample_products():
    return [
        {"product_name": "삼성 노트북 갤럭시북4 프로 16인치", "product_id": "1001", "product_price": 1590000, "product_image": "", "product_url": "", "category_name": "노트북", "rank": 1, "is_rocket": True, "is_free_shipping": False, "collected_at": "2026-07-05T00:00:00"},
        {"product_name": "LG 그램 15인치轻薄笔记本", "product_id": "1002", "product_price": 1490000, "product_image": "", "product_url": "", "category_name": "노트북", "rank": 2, "is_rocket": True, "is_free_shipping": False, "collected_at": "2026-07-05T00:00:00"},
        {"product_name": "델 XPS 13 플러스", "product_id": "1003", "product_price": 1890000, "product_image": "", "product_url": "", "category_name": "노트북/태블릿", "rank": 3, "is_rocket": True, "is_free_shipping": False, "collected_at": "2026-07-05T00:00:00"},
        {"product_name": "여성 골지 나시 티셔츠", "product_id": "2001", "product_price": 15000, "product_image": "", "product_url": "", "category_name": "여성의류", "rank": 1, "is_rocket": False, "is_free_shipping": True, "collected_at": "2026-07-05T00:00:00"},
        {"product_name": "강아지 사료 10kg", "product_id": "3001", "product_price": 45000, "product_image": "", "product_url": "", "category_name": "반려동물", "rank": 1, "is_rocket": True, "is_free_shipping": False, "collected_at": "2026-07-05T00:00:00"},
        {"product_name": "나이키 런닝화 에어맥스", "product_id": "4001", "product_price": 89000, "product_image": "", "product_url": "", "category_name": "스포츠/레저", "rank": 1, "is_rocket": True, "is_free_shipping": False, "collected_at": "2026-07-05T00:00:00"},
        {"product_name": "아기 기저귀 팬티형 4팩", "product_id": "5001", "product_price": 35000, "product_image": "", "product_url": "", "category_name": "출산/유아", "rank": 1, "is_rocket": True, "is_free_shipping": False, "collected_at": "2026-07-05T00:00:00"},
        {"product_name": "에어프라이어 오븐형 20L", "product_id": "6001", "product_price": 79000, "product_image": "", "product_url": "", "category_name": "가전", "rank": 1, "is_rocket": True, "is_free_shipping": False, "collected_at": "2026-07-05T00:00:00"},
    ]

@pytest.fixture
def temp_db():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
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
        CREATE TABLE IF NOT EXISTS publish_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            title TEXT,
            slug TEXT,
            published_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS published_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            published_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_publog_blog_keyword
        ON publish_log(blog_id, keyword, published_at)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pub_products_blog
        ON published_products(blog_id, product_id)
    """)
    conn.commit()
    yield db_path
    conn.close()
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def temp_db_with_data(temp_db):
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO published_products (blog_id, product_id, keyword, published_at) VALUES (?,?,?,?)",
        ("fitness-hugo", "2001", "가방", "2026-07-01T00:00:00")
    )
    conn.execute(
        "INSERT INTO published_products (blog_id, product_id, keyword, published_at) VALUES (?,?,?,?)",
        ("fitness-hugo", "3001", "가방", "2026-07-01T00:00:00")
    )
    conn.execute(
        "INSERT INTO publish_log (blog_id, keyword, title, slug, published_at) VALUES (?,?,?,?,?)",
        ("fitness-hugo", "덤벨 추천", "덤벨 추천 TOP5", "dumbbell-top5", "2026-07-04T00:00:00")
    )
    conn.commit()
    conn.close()
    return temp_db


@pytest.fixture(autouse=True)
def _isolated_keyword_pool(tmp_path, monkeypatch):
    """keyword_pool 조회가 운영 curation.db를 건드리지 않게 격리 (HARVESTER_FULL_INTEGRATION).

    존재하지 않는 tmp db를 가리킴 → _get_from_pool이 OperationalError → None 반환
    → get_keywords는 기존 KEYWORD_MAP fallback 그대로 동작.
    """
    from pipelines.curation import keywords as kw_mod
    monkeypatch.setattr(kw_mod, "_POOL_DB_PATH", str(tmp_path / "curation.db"))
