"""Wave-0 tests for shared/db.py (Phase 61, D-06 central DB path+connection helper).

These tests assert:
- get_db_path() resolves existing per-branch DB files via db_paths.py (no new files created).
- get_connection() returns a working read-only sqlite3.Connection.
- existing shared/db_paths.py symbols stay importable and unchanged.
- data/*.db files are NOT moved (D-06): git status shows no data/*.db changes.
- travel is NOT mapped to a dedicated DB (PIPELINE-STANDARD §6.4 / Review #3,#4).
"""

import os
import sqlite3
import subprocess

import pytest

import shared.db as db
import shared.db_paths as db_paths


class TestDbPathResolvesExisting:
    def test_get_db_path_returns_existing_car_db(self):
        path = db.get_db_path("car")
        assert path.endswith(os.path.join("data", "car.db"))
        assert os.path.isfile(path)

    def test_get_db_path_stock_maps_to_stap_content_db(self):
        assert db.get_db_path("stock") == db_paths.ARTICLES_DB

    def test_get_db_path_rap_and_senior_exist(self):
        assert os.path.isfile(db.get_db_path("rap"))
        assert os.path.isfile(db.get_db_path("senior"))

    def test_get_db_path_curation_exist(self):
        assert os.path.isfile(db.get_db_path("curation"))

    def test_content_ledger_resolves_via_db_paths(self):
        assert os.path.isfile(db_paths.PUBLISH_LEDGER_DB)
        assert db_paths.PUBLISH_LEDGER_DB.endswith(os.path.join("data", "content.db"))


class TestTravelNotMapped:
    def test_get_db_path_travel_raises_not_travel_en_db(self):
        """Review #3/#4: travel owns no dedicated DB — uses content.db + stap_content.db.
        get_db_path('travel') must NOT resolve to travel-en.db (stale/incorrect)."""
        with pytest.raises(ValueError):
            db.get_db_path("travel")


class TestGetConnection:
    def test_get_connection_readonly(self):
        conn = db.get_connection(db.get_db_path("car"))
        try:
            assert isinstance(conn, sqlite3.Connection)
            cur = conn.execute("SELECT 1")
            assert cur.fetchone() == (1,)
        finally:
            conn.close()


class TestDbPathsPreserved:
    def test_db_paths_symbols_unchanged(self):
        assert db_paths.PUBLISH_LEDGER_DB.endswith(os.path.join("data", "content.db"))
        assert db_paths.ARTICLES_DB.endswith(os.path.join("data", "stap_content.db"))


class TestNoDataFilesMoved:
    def test_git_status_shows_no_data_db_changes(self):
        """D-06: shared/db.py is path/connection only — no data/*.db move/mutation."""
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        changed = [line for line in proc.stdout.splitlines() if "data/" in line and line.strip().endswith(".db")]
        assert changed == [], f"data/*.db files changed/moved: {changed}"
