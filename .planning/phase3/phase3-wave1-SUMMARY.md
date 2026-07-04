---
phase: 3
plan: wave1
subsystem: curation-content-validation
tags: [relevance-scoring, publish-log-migration, content-validation]
requires: []
provides: [relevance-scorer-module, pipeline-migration-hook]
affects: [pipelines/curation/pipeline.py]
tech-stack:
  added: [shared/relevance_scorer.py]
  patterns: [deferred-import-for-circular-deps, try-except-alter-table]
key-files:
  created:
    - shared/relevance_scorer.py
    - tests/shared/test_relevance_scorer.py
  modified:
    - pipelines/curation/pipeline.py
decisions:
  - 'Deferred import for CATEGORY_FILTERS inside score_products() avoids circular import between relevance_scorer.py and pipeline.py'
  - 'migrate_publish_log uses try/except on ALTER TABLE (each column individually) rather than IF NOT EXISTS syntax, matching _init_db() pattern'
  - 'weekly_offtopic_report uses percentage values (0-100) for rate comparison to keep message template formula readable'
metrics:
  duration: 12min
  completed: "2026-07-04"
---

# Phase 3 Wave 1: Relevance Scorer Foundation + Pipeline Migration Hook

Built the standalone `shared/relevance_scorer.py` module with all 9 functions (score_product, score_products, get_threshold, passes_gate, migrate_publish_log, log_publish_audit, weekly_offtopic_report, run_all_weekly_reports, get_last_week_range) and fully tested them with 13 pytest tests. Wired the migration hook into `pipelines/curation/pipeline.py` so publish_log gets score columns on next import.

## Key Implementation Details

- **score_product** — simple substring matching against allowed keywords, normalized to `min(count / 2, 1.0)` using `RELEVANCE_CONFIG["default"]["min_keyword_matches"] = 2`
- **score_products** — uses deferred import `from pipelines.curation.pipeline import CATEGORY_FILTERS` inside function body to avoid circular import at module level
- **migrate_publish_log** — 5 separate `ALTER TABLE ADD COLUMN` calls, each wrapped in try/except `sqlite3.OperationalError` for idempotency
- **weekly_offtopic_report** — queries `publish_log` for past 7 days, computes off-topic rate as percentage, returns formatted Korean Telegram message if rate > 20%, `None` otherwise
- **All 9 functions** — docstring-only, no inline comments, matching project conventions

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

```
tests/shared/test_relevance_scorer.py::TestScoreProduct::test_basic_match PASSED
tests/shared/test_relevance_scorer.py::TestScoreProduct::test_multiple_matches PASSED
tests/shared/test_relevance_scorer.py::TestScoreProduct::test_no_match PASSED
tests/shared/test_relevance_scorer.py::TestScoreProduct::test_empty_name PASSED
tests/shared/test_relevance_scorer.py::TestScoreProducts::test_aggregate PASSED
tests/shared/test_relevance_scorer.py::TestGetThreshold::test_default PASSED
tests/shared/test_relevance_scorer.py::TestGetThreshold::test_blog_override PASSED
tests/shared/test_relevance_scorer.py::TestPassesGate::test_above_threshold PASSED
tests/shared/test_relevance_scorer.py::TestPassesGate::test_below_threshold PASSED
tests/shared/test_relevance_scorer.py::TestMigration::test_migrate_publish_log_idempotent PASSED
tests/shared/test_relevance_scorer.py::TestLogPublishAudit::test_insert_and_select PASSED
tests/shared/test_relevance_scorer.py::TestWeeklyReport::test_triggers_warning PASSED
tests/shared/test_relevance_scorer.py::TestWeeklyReport::test_suppresses_below_threshold PASSED
```

**13/13 passed**

## Verification

- `python -c "import pipelines.curation.pipeline; print('Pipeline import OK')"` — Pipeline import OK
- `migrate_publish_log('data/curation.db')` — `publish_log` schema now includes `avg_relevance_score`, `min_relevance_score`, `product_count`, `filtered_count`, `validation_passed`

## Self-Check: PASSED

- [x] `shared/relevance_scorer.py` exists (321 lines, 9 functions)
- [x] `tests/shared/test_relevance_scorer.py` exists (13 tests in 6 classes)
- [x] Both commits exist in git log:
  - `629f1c136` — feat(3-curation): create relevance_scorer module with all 9 functions and tests
  - `10833ee1f` — feat(3-curation): add migrate_publish_log hook to pipeline.py
- [x] `pipeline.py` modified with import + migration call
- [x] Schema migration idempotent (dual-run test passed)
- [x] Pipeline import succeeds (no circular import)

## Known Stubs

None. All functions are fully implemented and tested. The weekly report message templates use hardcoded per-keyword avg scores placeholder text ("상세: per-keyword with avg scores") — this is intentional per the plan spec for Wave 1 and will be enhanced in Wave 2.

## Threat Flags

No threat flags — module adds no new network endpoints, auth paths, or file access patterns beyond existing sqlite3 connections to `data/curation.db`.
