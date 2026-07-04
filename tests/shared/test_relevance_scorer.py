import os
import sqlite3
import tempfile

from shared.relevance_scorer import (
    RELEVANCE_CONFIG,
    score_product,
    score_products,
    get_threshold,
    passes_gate,
    migrate_publish_log,
    log_publish_audit,
    weekly_offtopic_report,
    run_all_weekly_reports,
    get_last_week_range,
)


class TestScoreProduct:
    def test_basic_match(self):
        result = score_product("맥북 프로", "전자제품", ["맥북"])
        assert result == 0.5

    def test_multiple_matches(self):
        result = score_product("맥북 프로", "노트북", ["맥북", "노트북", "laptop"])
        assert result == 1.0

    def test_no_match(self):
        result = score_product("의자", "가구", ["노트북", "laptop"])
        assert result == 0.0

    def test_empty_name(self):
        result = score_product("", "가구", ["가구"])
        assert result == 0.5


class TestScoreProducts:
    def test_aggregate(self):
        products = [
            {"product_name": "맥북 프로", "category_name": "노트북"},
            {"product_name": "의자", "category_name": "가구"},
        ]
        result = score_products(products, "laptop-hugo")
        assert len(result["scores"]) == 2
        assert abs(result["avg"] - 0.5) < 0.001
        assert result["min"] == 0.0
        assert result["blog_id"] == "laptop-hugo"
        assert result["threshold"] == 0.85


class TestGetThreshold:
    def test_default(self):
        assert get_threshold("unknown-blog") == 0.75

    def test_blog_override(self):
        assert get_threshold("health-hugo") == 0.65


class TestPassesGate:
    def test_above_threshold(self):
        scores = {"avg": 0.85, "threshold": 0.75}
        ok, msg = passes_gate(scores)
        assert ok is True
        assert msg == ""

    def test_below_threshold(self):
        scores = {"avg": 0.50, "threshold": 0.75}
        ok, msg = passes_gate(scores)
        assert ok is False
        assert "low_relevance" in msg
        assert "0.50" in msg
        assert "0.75" in msg


class TestMigration:
    def test_migrate_publish_log_idempotent(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE publish_log (id INTEGER PRIMARY KEY AUTOINCREMENT, blog_id TEXT, keyword TEXT, title TEXT, slug TEXT, published_at TEXT)"
            )
            conn.commit()
            conn.close()
            migrate_publish_log(path)
            migrate_publish_log(path)
            conn = sqlite3.connect(path)
            cols = [r[1] for r in conn.execute("PRAGMA table_info(publish_log)").fetchall()]
            conn.close()
            assert "avg_relevance_score" in cols
            assert "min_relevance_score" in cols
            assert "product_count" in cols
            assert "filtered_count" in cols
            assert "validation_passed" in cols
        finally:
            os.unlink(path)


class TestLogPublishAudit:
    def test_insert_and_select(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE publish_log (id INTEGER PRIMARY KEY AUTOINCREMENT, blog_id TEXT, keyword TEXT, title TEXT, slug TEXT, published_at TEXT)"
            )
            conn.commit()
            conn.close()
            migrate_publish_log(path)
            scores = {"avg": 0.85, "min": 0.5, "scores": [0.85, 0.5], "blog_id": "test-blog", "threshold": 0.75}
            log_publish_audit(path, "test-blog", "test-keyword", "Test Title", "test-slug", scores, True)
            conn = sqlite3.connect(path)
            row = conn.execute("SELECT * FROM publish_log").fetchone()
            conn.close()
            assert row is not None
            assert row[1] == "test-blog"
            assert row[2] == "test-keyword"
            assert row[3] == "Test Title"
            assert abs(row[6] - 0.85) < 0.001
            assert abs(row[7] - 0.5) < 0.001
        finally:
            os.unlink(path)


class TestWeeklyReport:
    def test_triggers_warning(self):
        from datetime import datetime, timezone
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE publish_log (id INTEGER PRIMARY KEY AUTOINCREMENT, blog_id TEXT, keyword TEXT, title TEXT, slug TEXT, published_at TEXT)"
            )
            conn.commit()
            conn.close()
            migrate_publish_log(path)
            now = datetime.now(timezone.utc).isoformat()
            conn = sqlite3.connect(path)
            for i in range(8):
                conn.execute(
                    "INSERT INTO publish_log (blog_id, keyword, title, slug, published_at, avg_relevance_score) VALUES (?,?,?,?,?,?)",
                    ("report-test", f"key{i}", f"Title {i}", f"slug-{i}", now, 0.9),
                )
            for i in range(8, 11):
                conn.execute(
                    "INSERT INTO publish_log (blog_id, keyword, title, slug, published_at, avg_relevance_score) VALUES (?,?,?,?,?,?)",
                    ("report-test", f"key{i}", f"Title {i}", f"slug-{i}", now, 0.2),
                )
            conn.commit()
            conn.close()
            msg = weekly_offtopic_report(path, "report-test")
            assert msg is not None
            assert "27.3%" in msg
            assert "report-test" in msg
        finally:
            os.unlink(path)

    def test_suppresses_below_threshold(self):
        from datetime import datetime, timezone
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE publish_log (id INTEGER PRIMARY KEY AUTOINCREMENT, blog_id TEXT, keyword TEXT, title TEXT, slug TEXT, published_at TEXT)"
            )
            conn.commit()
            conn.close()
            migrate_publish_log(path)
            now = datetime.now(timezone.utc).isoformat()
            conn = sqlite3.connect(path)
            for i in range(9):
                conn.execute(
                    "INSERT INTO publish_log (blog_id, keyword, title, slug, published_at, avg_relevance_score) VALUES (?,?,?,?,?,?)",
                    ("quiet-test", f"key{i}", f"Title {i}", f"slug-{i}", now, 0.9),
                )
            conn.execute(
                "INSERT INTO publish_log (blog_id, keyword, title, slug, published_at, avg_relevance_score) VALUES (?,?,?,?,?,?)",
                ("quiet-test", "key9", "Title 9", "slug-9", now, 0.2),
            )
            conn.commit()
            conn.close()
            msg = weekly_offtopic_report(path, "quiet-test")
            assert msg is None
        finally:
            os.unlink(path)
