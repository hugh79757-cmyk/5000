"""Unit tests for keyword_health.py — quarantine, backoff, health summary."""
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pipelines.curation.keyword_health import KeywordHealthStore, BACKOFF_HOURS, MAX_QUARANTINE_PERCENT


def test_ensure_table_creates_tables():
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    try:
        store = KeywordHealthStore(path)
        store.ensure_table()
        conn = sqlite3.connect(path)
        # Check table exists
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='keyword_health'").fetchall()
        assert len(tables) == 1
        # Check index exists
        idx = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_kh_blog_quarantined'").fetchall()
        assert len(idx) == 1
        conn.close()
    finally:
        os.unlink(path)


def test_record_failure_starts_consecutive_count():
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    try:
        store = KeywordHealthStore(path)
        store.ensure_table()
        store.record_failure("blog1", "kw1", "test_reason")
        row = store._get_row("blog1", "kw1")
        assert row["consecutive_failures"] == 1
        assert row["last_failure_reason"] == "test_reason"
        assert row["quarantined_until"] is not None
    finally:
        os.unlink(path)


def test_record_failure_exponential_backoff():
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    try:
        store = KeywordHealthStore(path)
        store.ensure_table()
        base_time = datetime.now()

        # consecutive 1 -> 1 hour backoff
        store.record_failure("blog1", "kw1", "r1")
        row = store._get_row("blog1", "kw1")
        q_until = datetime.fromisoformat(row["quarantined_until"])
        assert (q_until - base_time).total_seconds() / 3600 >= BACKOFF_HOURS[0] - 1  # allow 1h tolerance

        # consecutive 2 -> 4 hours backoff
        store.record_failure("blog1", "kw1", "r2")
        row = store._get_row("blog1", "kw1")
        assert row["consecutive_failures"] == 2
        q_until = datetime.fromisoformat(row["quarantined_until"])
        assert (q_until - base_time).total_seconds() / 3600 >= BACKOFF_HOURS[1] - 1

        # consecutive 5+ -> 720 hours backoff (max)
        for _ in range(3):
            store.record_failure("blog1", "kw1", "r_more")
        row = store._get_row("blog1", "kw1")
        assert row["consecutive_failures"] == 5
        q_until = datetime.fromisoformat(row["quarantined_until"])
        assert (q_until - base_time).total_seconds() / 3600 >= BACKOFF_HOURS[-1] - 1
    finally:
        os.unlink(path)


def test_record_success_resets_consecutive_and_clears_quarantine():
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    try:
        store = KeywordHealthStore(path)
        store.ensure_table()
        # First, cause some failures
        store.record_failure("blog1", "kw1", "r1")
        store.record_failure("blog1", "kw1", "r2")
        row_before = store._get_row("blog1", "kw1")
        assert row_before["consecutive_failures"] == 2
        assert store.is_quarantined("blog1", "kw1") is True

        # Now record success
        store.record_success("blog1", "kw1")
        row_after = store._get_row("blog1", "kw1")
        assert row_after["consecutive_failures"] == 0
        assert row_after["success_count"] >= 1
        assert store.is_quarantined("blog1", "kw1") is False
    finally:
        os.unlink(path)


def test_is_quarantined_checks_datetime():
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    try:
        store = KeywordHealthStore(path)
        store.ensure_table()
        # Quarantine to past time -> not quarantined
        past = (datetime.now() - timedelta(hours=2)).isoformat()
        conn = sqlite3.connect(path)
        conn.execute(
            "INSERT INTO keyword_health (blog_id, keyword, quarantined_until) VALUES (?,?,?)",
            ("blog1", "kw1", past)
        )
        conn.commit()
        conn.close()
        assert store.is_quarantined("blog1", "kw1") is False

        # Quarantine to future time -> quarantined
        future = (datetime.now() + timedelta(hours=2)).isoformat()
        conn = sqlite3.connect(path)
        conn.execute(
            "UPDATE keyword_health SET quarantined_until = ? WHERE blog_id=? AND keyword=?",
            (future, "blog1", "kw1")
        )
        conn.commit()
        conn.close()
        assert store.is_quarantined("blog1", "kw1") is True
    finally:
        os.unlink(path)


def test_get_quarantined_keywords_returns_only_future():
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    try:
        store = KeywordHealthStore(path)
        store.ensure_table()
        now = datetime.now()
        past = (now - timedelta(hours=1)).isoformat()
        future = (now + timedelta(hours=1)).isoformat()
        conn = sqlite3.connect(path)
        conn.execute(
            "INSERT INTO keyword_health (blog_id, keyword, quarantined_until) VALUES (?,?,?)",
            ("blog1", "kw1", future)
        )
        conn.execute(
            "INSERT INTO keyword_health (blog_id, keyword, quarantined_until) VALUES (?,?,?)",
            ("blog1", "kw2", past)
        )
        conn.execute(
            "INSERT INTO keyword_health (blog_id, keyword, quarantined_until) VALUES (?,?,?)",
            ("blog2", "kw3", future)
        )
        conn.commit()
        conn.close()
        # blog1 only
        q1 = store.get_quarantined_keywords(blog_id="blog1")
        assert len(q1) == 1
        assert q1[0]["keyword"] == "kw1"
        # all blogs
        q_all = store.get_quarantined_keywords()
        assert len(q_all) == 2
        keywords = [r["keyword"] for r in q_all]
        assert "kw1" in keywords
        assert "kw3" in keywords
    finally:
        os.unlink(path)


def test_get_health_summary_returns_counts():
    # This requires integration with keywords module. We'll stub get_keywords.
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    try:
        store = KeywordHealthStore(path)
        store.ensure_table()
        # Setup: blog has 10 total keywords (stubbed)
        # We'll monkeypatch pipelines.curation.keywords.get_keywords
        import pipelines.curation.keywords as kw_mod
        original_get = kw_mod.get_keywords
        kw_mod.get_keywords = lambda blog_id: ["k1","k2","k3","k4","k5","k6","k7","k8","k9","k10"] if blog_id=="blog1" else []

        try:
            # Record some quarantined and failing
            store.record_failure("blog1", "k1", "r1")
            store.record_failure("blog1", "k2", "r1")
            store.record_failure("blog1", "k3", "r1")  # k1,k2,k3 consecutive >0
            summary = store.get_health_summary("blog1")
            assert summary["total_keywords"] == 10
            assert summary["quarantined_count"] == 3  # all three quarantined after several consecutive failures
            assert summary["healthy_count"] == 7
            assert len(summary["most_failing_keywords"]) <= 10
        finally:
            kw_mod.get_keywords = original_get
    finally:
        os.unlink(path)


def test_reset_keyword_clears_quarantine():
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    try:
        store = KeywordHealthStore(path)
        store.ensure_table()
        store.record_failure("blog1", "kw1", "r1")
        assert store.is_quarantined("blog1", "kw1") is True
        store.reset_keyword("blog1", "kw1")
        assert store.is_quarantined("blog1", "kw1") is False
        # Row should still exist with quarantined_until NULL
        row = store._get_row("blog1", "kw1")
        assert row["quarantined_until"] is None
    finally:
        os.unlink(path)


def test_failure_history_is_capped_at_10():
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    try:
        store = KeywordHealthStore(path)
        store.ensure_table()
        # Record 12 failures
        for i in range(12):
            store.record_failure("blog1", "kw1", f"reason{i}")
        row = store._get_row("blog1", "kw1")
        history = row["failure_history"]
        # Should be JSON list with max 10 entries
        import json
        hist_list = json.loads(history)
        assert len(hist_list) == 10
        # The latest should be reason 11 (last entry)
        assert hist_list[-1]["reason"] == "reason11"
    finally:
        os.unlink(path)


def test_max_quarantine_percent_cap_prevents_new_quarantine():
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    try:
        store = KeywordHealthStore(path)
        store.ensure_table()
        # Stub get_keywords to return a small pool so cap triggers
        import pipelines.curation.keywords as kw_mod
        original_get = kw_mod.get_keywords
        # 5 total keywords
        kw_mod.get_keywords = lambda blog_id: ["k1","k2","k3","k4","k5"] if blog_id=="blog1" else []
        try:
            # Quarantine 5% of 5 = 0.2*5=1.0 -> maximum 1 allowed, second should be blocked if cap=20%? Actually 20% of 5 = 1.0 floor => 1.
            # We'll quarantine 2 to see cap
            store.record_failure("blog1", "k1", "r1")
            # First should be quarantined
            assert store.is_quarantined("blog1", "k1") is True
            # Second attempt for a different keyword should hit cap if total keywords 5 and already 1 quarantined (20% reached)
            # But _count_quarantined counts currently quarantined. After first, count=1. 
            # Adding another would be (1+1)/5 = 0.4 > 0.2, so cap prevents.
            store.record_failure("blog1", "k2", "r2")
            row2 = store._get_row("blog1", "k2")
            # k2 should have quarantined_until = None because cap hit
            assert row2["quarantined_until"] is None
        finally:
            kw_mod.get_keywords = original_get
    finally:
        os.unlink(path)
