---
phase: 59
plan: 05
subsystem: ops_dashboard
tags: [telegram, alerts, standard-compliance, dashboard-integration]
requires: [59-01, 59-02]
provides: [dashboard-alerts, standard-check, violation-notifications]
affects: [shared/telegram_notifier.py, ops_dashboard/checks/standard.py]
tech-stack:
  added: []
  patterns: [env-config, plugin-check, critical-only-alerting]
key-files:
  created:
    - ops_dashboard/checks/standard.py
    - tests/ops_dashboard/__init__.py
    - tests/ops_dashboard/test_standard_check.py
  modified:
    - shared/telegram_notifier.py
    - tests/shared/test_telegram_notifier.py
decisions:
  - "Dashboard URL configurable via OPS_DASHBOARD_URL env var (default localhost:5060)"
  - "send_standard_violation only fires on CRITICAL severity (MAJOR silently recorded)"
  - "Standard check uses lazy import for telegram_notifier to avoid circular deps"
  - "R01-R12 rules defined as STANDARD_RULES list with per-rule check functions"
metrics:
  duration: ~10min
  completed: 2026-08-06
  tasks: 1
  files: 5
---

# Phase 59 Plan 05: Dashboard Alerts + Standard Violation Notifications Summary

Telegram alerts with dashboard links and R01-R12 standard compliance check that triggers CRITICAL violation notifications.

## What Was Built

**shared/telegram_notifier.py additions:**
- `DASHBOARD_URL` — configurable via `OPS_DASHBOARD_URL` env var, defaults to `http://localhost:5060`
- `send_dashboard_alert(blog_id, check_name, status, detail)` — sends Ops Alert with clickable dashboard link
- `send_standard_violation(blog_id, rule_id, severity, detail)` — sends Standard Violation alert for CRITICAL only; MAJOR violations return `None` (no alert)

**ops_dashboard/checks/standard.py (new):**
- `check_standard_compliance(conn, blog_id)` — registered via `@register_check("standard_compliance")`
- 12 rule check functions (R01-R12) covering:
  - R01: `showTableOfContents = false` in hugo.toml
  - R02: `[params.advertisement]` with adsense slots
  - R03: adsbygoogle.js uses site.Params (no hardcoding)
  - R04: GA4 + mobile correction CSS
  - R05: adsense/top.html overflow:hidden + min-height
  - R06: adsense/in-article.html fluid+in-article (no auto)
  - R07: single.html H2 split injection + prose wrapper
  - R08: single.html .Lead/.Description removed
  - R09: baseof.html no custom override
  - R10: custom.css unfilled + dark mode rules
  - R11: mobile-sticky.html not used
  - R12: No unauthorized layout overrides
- On CRITICAL failure: calls `send_standard_violation()` via lazy import with try/except guard

**Tests (18 total, all passing):**
- 7 new tests in `test_telegram_notifier.py`: DASHBOARD_URL config, send_dashboard_alert, send_standard_violation
- 4 new tests in `test_standard_check.py`: registration, return format, CRITICAL→Telegram, MAJOR→no Telegram

## Deviations from Plan

None — plan executed exactly as written.

## Verification

**[검증됨]** Plan verification script passed:
```
Dashboard URL: http://localhost:5060
PASS: Telegram alert functions with dashboard link
```

**[검증됨]** All 18 tests pass (14 existing + 4 new):
- `TestDashboardUrlConfig` — 2/2 pass (default + env override)
- `TestSendDashboardAlert` — 2/2 pass (URL in message + signature)
- `TestSendStandardViolation` — 3/3 pass (CRITICAL sends, MAJOR no send, signature)
- `TestRegisterCheck` — 2/2 pass (registered + returns valid status)
- `TestViolationTelegramNotification` — 1/1 pass (CRITICAL→Telegram)
- `TestNonCriticalNoTelegram` — 1/1 pass (MAJOR→no Telegram)
- Existing 14 tests — 14/14 pass (backward compatibility confirmed)

**근거:** `pytest` output 18 passed, `python -c` verification script all assertions passed.

## Known Stubs

None — all functions fully implemented with working tests.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-59-13 (accepted) | shared/telegram_notifier.py | Dashboard URL embedded in Telegram messages — points to localhost or tunnel hostname, not sensitive |

## Self-Check: PASSED

- [✅] `shared/telegram_notifier.py` modified — DASHBOARD_URL, send_dashboard_alert, send_standard_violation added
- [✅] `ops_dashboard/checks/standard.py` created — 12 rule checks with registration
- [✅] `tests/shared/test_telegram_notifier.py` modified — 7 new tests
- [✅] `tests/ops_dashboard/test_standard_check.py` created — 4 new tests
- [✅] Commit 8412eac2b (test) exists — verified via `git log`
- [✅] Commit a80a4b69f (feat) exists — verified via `git log`
- [✅] All 18 tests pass — verified via `pytest`
- [✅] Backward compatibility — existing send_error/send_daily_report signatures unchanged

## Self-Check: PASSED (verification)

All files found on disk. Both commits (8412eac2b, a80a4b69f) exist in git log. 18/18 tests pass.
