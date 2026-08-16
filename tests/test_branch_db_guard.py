"""Unit tests for shared.db.connect_branch_db guard (Phase 74 Wave 4, SC-7).

Verifies the guard added in Wave 1:
- import surface intact (connect_branch_db, BranchDbMissingError, get_db_path, get_connection)
- allow_create=False raises BranchDbMissingError on missing DB file
- unregistered branch raises BranchDbMissingError
- allow_create=True connects; stock vs stock_metrics map to DIFFERENT files (F1 collision resolved)

Uses a temp _DATA dir via monkeypatch so no real data/*.db file is touched/created.
"""

import os
import sqlite3

import pytest

import shared.db as db


def test_import_surface_intact():
    assert hasattr(db, "connect_branch_db")
    assert hasattr(db, "BranchDbMissingError")
    assert hasattr(db, "get_db_path")
    assert hasattr(db, "get_connection")


def test_missing_db_raises_without_allow_create(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "_DATA", str(tmp_path))
    with pytest.raises(db.BranchDbMissingError):
        db.connect_branch_db("__nonexistent__", allow_create=False)


def test_unregistered_branch_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "_DATA", str(tmp_path))
    with pytest.raises(db.BranchDbMissingError):
        db.connect_branch_db("not_a_real_branch", allow_create=False)


def test_allow_create_connects_different_files(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "_DATA", str(tmp_path))
    conn_stock = db.connect_branch_db("stock", allow_create=True)
    conn_metrics = db.connect_branch_db("stock_metrics", allow_create=True)
    assert isinstance(conn_stock, sqlite3.Connection)
    assert isinstance(conn_metrics, sqlite3.Connection)
    # F1 collision resolved: stock -> stap_content.db, stock_metrics -> stock.db
    stock_path = os.path.join(str(tmp_path), "stap_content.db")
    metrics_path = os.path.join(str(tmp_path), "stock.db")
    assert os.path.exists(stock_path)
    assert os.path.exists(metrics_path)
    assert stock_path != metrics_path
    conn_stock.close()
    conn_metrics.close()


def test_legacy_helpers_callable(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "_DATA", str(tmp_path))
    # get_db_path resolves for known branches; get_connection returns a Connection
    p = db.get_db_path("rap")
    assert p.endswith("rap.db")
    conn = db.get_connection(":memory:")
    assert isinstance(conn, sqlite3.Connection)
    conn.close()
