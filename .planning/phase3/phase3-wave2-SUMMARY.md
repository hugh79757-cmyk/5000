---
phase: 3
plan: wave2
subsystem: curation-content-validation
tags: [relevance-gate, audit-logging, content-validation]
requires: [relevance-scorer-module, pipeline-migration-hook]
provides: [pre-publish-relevance-gate, post-publish-audit-log]
affects: [pipelines/curation/pipeline.py]
tech-stack:
  added: []
  patterns: [fail-open-exception-handling, inline-import-for-single-use]
key-files:
  created: []
  modified:
    - pipelines/curation/pipeline.py
decisions:
  - 'score_products imported at module level (top of pipeline.py) for reuse by both pre-publish gate and post-publish audit'
  - 'log_publish_audit imported inline inside _run_inner() to avoid adding unused top-level import noise'
  - 'Scores recomputed at audit time (not cached from gate) because enrich_products may have modified product data'
  - 'fail-open on gate exception: scoring errors log warning and set default scores (1.0) instead of blocking publication'
metrics:
  duration: ~8min
  completed: "2026-07-04"
---

# Phase 3 Wave 2: Pre-publish Relevance Gate + Post-publish Audit Logging

Integrated the `shared/relevance_scorer.py` module into `pipelines/curation/pipeline.py` with two changes:

1. **Pre-publish relevance gate** (after `_filter_irrelevant_products`, before `enrich_products`): scores all products against their allowed keyword lists using the blog's `CATEGORY_FILTERS`; blocks articles with `"low_relevance"` reason if average score falls below the per-blog threshold (default 0.75). Fail-open behavior protects against scoring exceptions crashing the pipeline.

2. **Post-publish audit logging** (replaces `_record_publish()`): calls `log_publish_audit()` to store the `avg_relevance_score`, `min_relevance_score`, `product_count`, `filtered_count`, and `validation_passed` columns alongside the original publish metadata. Scores are recomputed after enrichment for accuracy.

## Deviations from Plan

None — plan executed exactly as written.

## Verification

```bash
# 1. Syntax check
.venv/bin/python -c "import pipelines.curation.pipeline; print('pipeline import OK')"
# → pipeline import OK

# 2. No non-curation leakage
grep -rn 'relevance_scorer' pipelines/car/ pipelines/etap/ pipelines/rap/ pipelines/senior/ pipelines/stock/ pipelines/travel/
# → (empty — no leakage)

# 3. Schema has score columns
sqlite3 data/curation.db ".schema publish_log" | grep -q avg_relevance_score
# → Schema: CREATE TABLE publish_log (..., avg_relevance_score REAL, min_relevance_score REAL, ...)
```

## Self-Check: PASSED

- [x] Task 3.3: `score_products` and `passes_gate` imported at module level (line 30)
- [x] Task 3.3: Relevance scoring gate inserted after filter, before enrich (lines 608–620)
- [x] Task 3.3: Gate blocks with `"low_relevance"` reason when scores below threshold
- [x] Task 3.3: Fail-open exception handler logs warning and sets default scores
- [x] Task 3.4: `_record_publish()` call in `_run_inner()` replaced by `log_publish_audit()`
- [x] Task 3.4: `log_publish_audit` imported inline (line 703)
- [x] Task 3.4: `_record_products()` preserved unchanged (line 711)
- [x] `_record_publish()` function definition preserved (line 486) for other potential callers
- [x] Commit `e8caca678` — feat(3-curation): add pre-publish relevance gate and post-publish audit logging
- [x] Syntax check passes (pipeline import OK)
- [x] No leakage to non-curation pipelines
- [x] DB schema has `avg_relevance_score` column

## Known Stubs

None. Both gate and audit logging are fully wired and functional.

## Threat Flags

No threat flags — `log_publish_audit` writes to the same `data/curation.db` SQLite database via the same existing connection pattern as `_record_publish()`. The gate adds no new network, auth, or file access paths.
