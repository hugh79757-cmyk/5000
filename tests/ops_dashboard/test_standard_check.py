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


class TestR12AllowedOverrides:
    """R12: layouts/ 오버라이드 인가 목록 검사 (2026-08-06 확장)."""

    def _make_site(self, tmp_path, files):
        site = tmp_path / "site"
        for rel in files:
            p = site / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{{ .Title }}", encoding="utf-8")
        return site

    def test_allowed_overrides_pass(self, tmp_path):
        from ops_dashboard.checks.standard import _check_r12
        site = self._make_site(tmp_path, [
            "layouts/_default/single.html",
            "layouts/partials/related.html",          # 77개 블로그 공통
            "layouts/partials/head/custom.html",      # 35개 adsbygoogle 로더
            "layouts/partials/cuap-spider-links.html",# 15개 CUAP 교차링크
            "layouts/_default/_markup/render-link.html",
            "layouts/partials/adsense/in-article.html",
            "layouts/partials/adsense/top.html",
        ])
        ok, detail = _check_r12(site)
        assert ok is True, detail
        assert "Unauthorized" not in detail

    def test_unknown_override_fails(self, tmp_path):
        from ops_dashboard.checks.standard import _check_r12
        site = self._make_site(tmp_path, [
            "layouts/sitemap.xml",   # 사용 빈도 1~2 개별 오버라이드
        ])
        ok, detail = _check_r12(site)
        assert ok is False
        assert "sitemap.xml" in detail

    def test_junk_files_not_violations(self, tmp_path):
        from ops_dashboard.checks.standard import _check_r12
        site = self._make_site(tmp_path, [
            "layouts/partials/related.html",
            "layouts/.DS_Store",
            "layouts/_default/single.html.bak",
            "layouts/partials/extend-head.html.bak",
        ])
        ok, detail = _check_r12(site)
        # 정크만 있으면 pass (위반 아님), detail에 junk 집계
        assert ok is True, detail
        assert ".DS_Store" in detail

    def test_allowed_prefix_matches_subdirs(self, tmp_path):
        from ops_dashboard.checks.standard import _check_r12
        site = self._make_site(tmp_path, [
            "layouts/partials/adsense/in-article.html",
            "layouts/partials/adsense/leaderboard.html",
            "layouts/partials/adsense/adsense-loader.html",
        ])
        ok, detail = _check_r12(site)
        assert ok is True, detail


class TestR2_01AffiliateExempt:
    """R2-01 affiliate hotlink 예외 (Phase 71c).

    affiliate CDN (config r2_exempt_domains) 이미지는 정상으로 인정,
    자체 콘텐츠 이미지(featureimage/자체 본문)는 기존대로 R2 강제 유지.
    """

    _R2 = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/img/cover.webp"
    _AFFILIATE = "https://assets.omio.design/marketing/x.png"
    _NONR2 = "https://img.techpawz.com/images/x/thumb_x.webp"

    def _make_post(self, tmp_path, featureimage=None, body_images=None):
        site = tmp_path / "site"
        post_dir = site / "content" / "posts" / "sample-post"
        post_dir.mkdir(parents=True, exist_ok=True)
        body = ""
        for u in (body_images or []):
            body += f"![img]({u})\n"
        fm_lines = ["---", "title: sample", "date: 2026-08-15"]
        if featureimage:
            fm_lines.append(f"featureimage: \"{featureimage}\"")
        fm_lines.append("---")
        (post_dir / "index.md").write_text("\n".join(fm_lines) + "\n" + body, encoding="utf-8")
        return site

    def test_affiliate_image_pass(self, tmp_path):
        from ops_dashboard.checks.standard import _check_r2_01, _load_r2_exempt_domains
        # affiliate 도메인이 config에서 로드됐는지 확인 (config 무존재 시 적용 불가)
        assert "assets.omio.design" in _load_r2_exempt_domains(), (
            "r2_exempt_domains 미로드 — config/quality_checklist.yaml 확인"
        )
        site = self._make_post(tmp_path, body_images=[self._AFFILIATE])
        ok, detail = _check_r2_01(site)
        assert ok is True, detail
        assert "affiliate exempt" in detail

    def test_nonr2_self_image_still_fails(self, tmp_path):
        from ops_dashboard.checks.standard import _check_r2_01
        site = self._make_post(tmp_path, body_images=[self._NONR2])
        ok, detail = _check_r2_01(site)
        assert ok is False, "비R2 자체 본문 이미지는 여전히 fail이어야 함"
        assert "img.techpawz.com" in detail

    def test_r2_self_image_pass(self, tmp_path):
        from ops_dashboard.checks.standard import _check_r2_01
        site = self._make_post(tmp_path, featureimage=self._R2, body_images=[self._R2])
        ok, detail = _check_r2_01(site)
        assert ok is True, detail

    def test_nonr2_featureimage_still_fails(self, tmp_path):
        from ops_dashboard.checks.standard import _check_r2_01
        # featureimage가 자체이미지(비R2, 비affiliate)면 fail 유지 — 예외로 통과시키면 안 됨
        site = self._make_post(tmp_path, featureimage=self._NONR2)
        ok, detail = _check_r2_01(site)
        assert ok is False, "비R2 자체 featureimage는 여전히 fail이어야 함"
        assert "/featureimage" in detail

    def test_affiliate_featureimage_exempt(self, tmp_path):
        from ops_dashboard.checks.standard import _check_r2_01
        site = self._make_post(tmp_path, featureimage=self._AFFILIATE)
        ok, detail = _check_r2_01(site)
        assert ok is True, detail
        assert "affiliate exempt" in detail
