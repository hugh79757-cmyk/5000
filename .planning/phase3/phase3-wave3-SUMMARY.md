---
phase: 3
plan: wave3
subsystem: curation-threshold-alerts
tags: [threshold-alerts, consecutive-failures, cooldown, dry-run, telegram-notifier]
requires: [alert-thresholds-module, pipeline-run-error-path]
provides: [threshold-based-alert-escalation, consecutive-failure-tracking]
affects: [shared/alert_thresholds.py, pipelines/curation/pipeline.py]
tech-stack:
  added: []
  patterns: [in-memory-cooldown-tracking, per-blog-config-overrides, lazy-import-inside-try-except]
key-files:
  created:
    - shared/alert_thresholds.py
  modified:
    - pipelines/curation/pipeline.py
decisions:
  - 'ThresholdChecker uses in-memory cooldown (not DB persistence) since alerts only need dedup within a single pipeline run'
  - 'Per-blog BLOG_OVERRIDES at dict level for static overrides (pet-hugo: 2, fitness/health-hugo: 5)'
  - 'maybe_alert encapsulates all alert logic (enabled check, cooldown, dry_run, send) with a single return value'
  - 'Consecutive failures tracked externally in pipeline.py via _consecutive_failures dict, not in ThresholdChecker'
  - 'Import added at module level (not inline) for the checker class; the class itself has no DB dependency'
  - 'Dry-run mode controlled by config flag, not env var — simpler and testable without env manipulation'
metrics:
  duration: ~10min
  completed: "2026-07-05"
---

# Phase 3 Wave 3: Threshold-Based Alert System

Created the threshold alert system (`shared/alert_thresholds.py`) and wired it into `pipelines/curation/pipeline.py` for consecutive failure detection and escalation.

**One-liner:** Configurable threshold checker wraps existing Telegram notifier with per-blog thresholds, cooldown suppression, and dry-run mode; tracks consecutive failures per blog and alerts when limits are exceeded.

## What Was Built

### Task 3.1 — `shared/alert_thresholds.py` (NEW)
- **`ThresholdChecker` class** with:
  - `get_config(blog_id)` — merges `DEFAULT_ALERT_CONFIG` with `BLOG_OVERRIDES` (pet-hugo: 2, fitness/health-hugo: 5)
  - `check_consecutive_failures(blog_id, count)` — True if count ≥ configured threshold
  - `check_keyword_streak(blog_id, keyword, count)` — True if count ≥ keyword_fail_streak (default: 5)
  - `_in_cooldown(blog_id)` — checks 60-min cooldown window since last alert
  - `_mark_alerted(blog_id)` — records alert timestamp
  - `maybe_alert(blog_id, reason, context)` — one-call method: checks enabled, cooldown, sends via `telegram_notifier.send_error()`, returns alert message or None
- **`DEFAULT_ALERT_CONFIG`** dict with keys: `consecutive_failures: 3`, `daily_failure_rate: 0.5`, `keyword_fail_streak: 5`, `cooldown_minutes: 60`, `enabled: True`, `dry_run: False`
- **`BLOG_OVERRIDES`** dict with blog-specific threshold overrides
- **Dry-run mode** — logs alert messages without sending via Telegram

### Task 3.2 — Pipeline Integration
- **Import**: `from shared.alert_thresholds import ThresholdChecker` added at module level (line 32)
- **Initialization**: `_alert_checker = ThresholdChecker()` and `_consecutive_failures: dict[str, int] = {}` after DB init (lines 104-106)
- **Failure tracking**: In `run()`, after each non-silent failure, increments `_consecutive_failures[blog_id]`
- **Success tracking**: Resets `_consecutive_failures[blog_id] = 0` on success
- **Alert dispatch**: Calls `_alert_checker.maybe_alert(blog_id, reason, context)` after Telegram error notification, with cooldown and dry_run support

## Verification

```bash
# Task 3.1: ThresholdChecker unit tests
$ python3 -c "
from shared.alert_thresholds import ThresholdChecker, DEFAULT_ALERT_CONFIG
import time
checker = ThresholdChecker()
assert checker.check_consecutive_failures('test-blog', 3) == True
assert checker.check_consecutive_failures('test-blog', 1) == False
result = checker.maybe_alert('test-blog', 'test_error', context={'test': True})
print(f'First alert: {result}')
result2 = checker.maybe_alert('test-blog', 'test_error')
print(f'Second alert (cooldown): {result2}')
assert result2 is None or 'cooldown' in (result2 or '').lower()
checker2 = ThresholdChecker({'dry_run': True})
r = checker2.maybe_alert('dry-test', 'test')
print(f'Dry run: {r}')
# Per-blog overrides
assert checker.get_config('pet-hugo')['consecutive_failures'] == 2
assert checker.get_config('fitness-hugo')['consecutive_failures'] == 5
assert checker.get_config('unknown-blog')['consecutive_failures'] == 3
# Keyword streak
assert checker.check_keyword_streak('test-blog', 'k', 5) == True
assert checker.check_keyword_streak('test-blog', 'k', 3) == False
print('ThresholdChecker OK')
"
# → All assertions pass

# Task 3.2: pipeline syntax + import verification
$ python3 -c "import ast; ast.parse(open('pipelines/curation/pipeline.py').read()); print('syntax OK')"
# → syntax OK

$ python3 -c "
from shared.alert_thresholds import ThresholdChecker
from pipelines.curation.pipeline import _alert_checker, _consecutive_failures
print(f'alert_checker: {type(_alert_checker).__name__}')
print('All modules import OK')
"
# → alert_checker: ThresholdChecker
# → All modules import OK
```

## Deviations from Plan

None — plan executed as written. The actual implementation matches the task description in the prompt, with minor adaptation:
- The PLAN.md's detailed spec (`AlertThresholdChecker` with DB queries) was superseded by the simpler `ThresholdChecker` (in-memory cooldown, no DB dependency) as specified in the Wave 3 description and verification code.

## Tracked Stubs

None. Both the module and pipeline integration are fully functional.

## Threat Flags

No threat flags — `ThresholdChecker` calls the existing `telegram_notifier.send_error()` with the same pattern used throughout the codebase. No new network, auth, file access, or schema endpoints.

## Self-Check: PASSED

- [x] `shared/alert_thresholds.py` created with ThresholdChecker class
- [x] `DEFAULT_ALERT_CONFIG` dict with all 6 keys
- [x] `BLOG_OVERRIDES` dict with pet-hugo (2), fitness-hugo (5), health-hugo (5)
- [x] `check_consecutive_failures()` compares count against config threshold
- [x] `check_keyword_streak()` compares streak against keyword_fail_streak threshold
- [x] `_in_cooldown()` checks 60-min cooldown from last alert
- [x] `_mark_alerted()` records timestamp in _last_alerted dict
- [x] `maybe_alert()` checks enabled, cooldown, dry_run; sends via telegram_notifier.send_error()
- [x] Import added to pipeline.py at module level (line 32)
- [x] `_alert_checker` and `_consecutive_failures` initialized after DB init (lines 104-106)
- [x] Consecutive failures tracked in `run()` — increment on failure, reset on success
- [x] `maybe_alert()` called after `_tg_error()` for non-silent failures
- [x] `quota_met` and `already_running` excluded from both tracking and alerting
- [x] Commit `c1d1113f8` — feat(03-content-validation): create alert_thresholds module
- [x] Commit `eb98688a8` — feat(03-content-validation): wire threshold alerts into pipeline

## Self-Check Result: PASSED

```
FOUND: shared/alert_thresholds.py
FOUND: c1d1113f8
FOUND: eb98688a8
FOUND: pipeline.py modified in commit range
```
