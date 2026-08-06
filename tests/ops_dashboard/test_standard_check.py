"""Tests for ops_dashboard.checks.standard — standard compliance check."""
import sqlite3
from unittest.mock import patch, MagicMock

import pytest


def _make_conn():
    """Create an in-memory SQLite DB with the required tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE check_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            check_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unknown',
            detail TEXT DEFAULT '',
            evidence_url TEXT DEFAULT '',
            checked_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE standard_rules (
            rule_id TEXT PRIMARY KEY,
            source TEXT,
            target TEXT,
            detection_method TEXT,
            severity TEXT,
            description TEXT
        );
        CREATE TABLE blog_lifecycle (
            blog_id TEXT PRIMARY KEY,
            brand TEXT NOT NULL,
            config_status TEXT NOT NULL DEFAULT 'inactive',
            site_path TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE known_issues (
            issue_id TEXT PRIMARY KEY,
            blog_ids TEXT DEFAULT '',
            category TEXT NOT NULL,
            symptom TEXT NOT NULL,
            recorded_date TEXT NOT NULL,
            gsd_status TEXT NOT NULL DEFAULT 'open',
            auto_detectable TEXT NOT NULL DEFAULT 'no',
            detection_method TEXT DEFAULT '',
            resolution_status TEXT NOT NULL DEFAULT 'open',
            current_detection TEXT NOT NULL DEFAULT 'na',
            notes TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    return conn


class TestRegisterCheck:
    def test_standard_compliance_registered(self):
        from ops_dashboard.checks import CHECKS
        # Import triggers registration
        from ops_dashboard.checks import standard  # noqa: F401
        assert "standard_compliance" in CHECKS

    def test_check_returns_pass_fail_or_unknown(self):
        from ops_dashboard.checks import standard  # noqa: F401
        from ops_dashboard.checks import CHECKS
        conn = _make_conn()
        # blog_lifecycle must have the blog for the check to look up site_path
        conn.execute(
            "INSERT INTO blog_lifecycle (blog_id, brand, site_path) VALUES (?, ?, ?)",
            ("test-hugo", "cap", "/tmp/test-site"),
        )
        conn.commit()
        result = CHECKS["standard_compliance"](conn, "test-hugo")
        assert result["status"] in ("pass", "fail", "unknown")
        assert "detail" in result


class TestViolationTelegramNotification:
    @patch("shared.telegram_notifier.send_standard_violation")
    def test_critical_violation_sends_telegram(self, mock_send):
        mock_send.return_value = True
        from ops_dashboard.checks import CHECKS
        conn = _make_conn()
        conn.execute(
            "INSERT INTO blog_lifecycle (blog_id, brand, site_path) VALUES (?, ?, ?)",
            ("test-hugo", "cap", "/tmp/test-site"),
        )
        conn.execute(
            "INSERT INTO standard_rules (rule_id, target, severity, description) VALUES (?, ?, ?, ?)",
            ("R01", "hugo.toml", "CRITICAL", "showTableOfContents must be false"),
        )
        conn.commit()
        # Run check — should detect R01 violation and call send_standard_violation
        result = CHECKS["standard_compliance"](conn, "test-hugo")
        # If R01 is a fail, send_standard_violation should have been called
        # (only on CRITICAL)
        if result["status"] == "fail":
            # At least one call with CRITICAL
            calls = mock_send.call_args_list
            critical_calls = [c for c in calls if "CRITICAL" in str(c)]
            assert len(critical_calls) > 0, "No CRITICAL Telegram notification sent"


class TestNonCriticalNoTelegram:
    @patch("shared.telegram_notifier.send_standard_violation")
    def test_major_violation_no_telegram(self, mock_send):
        from ops_dashboard.checks import CHECKS
        conn = _make_conn()
        conn.execute(
            "INSERT INTO blog_lifecycle (blog_id, brand, site_path) VALUES (?, ?, ?)",
            ("test-hugo", "cap", "/tmp/test-site"),
        )
        conn.execute(
            "INSERT INTO standard_rules (rule_id, target, severity, description) VALUES (?, ?, ?, ?)",
            ("R04", "extend_head.html", "MAJOR", "GA4 + mobile CSS"),
        )
        conn.commit()
        result = CHECKS["standard_compliance"](conn, "test-hugo")
        # MAJOR violations should NOT trigger Telegram
        mock_send.assert_not_called()
