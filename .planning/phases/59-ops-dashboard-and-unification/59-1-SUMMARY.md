---
phase: 59
plan: 1
subsystem: pipelines/etap
tags: [refactor, hugo-writer, deduplication]
dependency_graph:
  requires: [59-0]
  provides: [shared-etap-writer]
  affects: [pipelines/etap/*_pipeline.py]
tech_stack:
  added: []
  patterns: [adapter-pattern, shared-import]
key_files:
  created: []
  modified:
    - pipelines/etap/adventure_pipeline.py
    - pipelines/etap/airlines_pipeline.py
    - pipelines/etap/airports_pipeline.py
    - pipelines/etap/bus_pipeline.py
    - pipelines/etap/citytours_pipeline.py
    - pipelines/etap/cruise_pipeline.py
    - pipelines/etap/culture_pipeline.py
    - pipelines/etap/daytrips_pipeline.py
    - pipelines/etap/deals_pipeline.py
    - pipelines/etap/dining_pipeline.py
    - pipelines/etap/escape_pipeline.py
    - pipelines/etap/esim_pipeline.py
    - pipelines/etap/eurail_pipeline.py
    - pipelines/etap/extreme_pipeline.py
    - pipelines/etap/ferry_pipeline.py
    - pipelines/etap/flight_pipeline.py
    - pipelines/etap/foodtour_pipeline.py
    - pipelines/etap/ghost_pipeline.py
    - pipelines/etap/hiking_pipeline.py
    - pipelines/etap/layover_pipeline.py
    - pipelines/etap/luxury_pipeline.py
    - pipelines/etap/michelin_pipeline.py
    - pipelines/etap/multiday_pipeline.py
    - pipelines/etap/nature_pipeline.py
    - pipelines/etap/nightlife_pipeline.py
    - pipelines/etap/nomad_pipeline.py
    - pipelines/etap/phototour_pipeline.py
    - pipelines/etap/tours_pipeline.py
    - pipelines/etap/trains_pipeline.py
    - pipelines/etap/transfers_pipeline.py
    - pipelines/etap/visa_pipeline.py
    - pipelines/etap/visafree_pipeline.py
    - pipelines/etap/walking_pipeline.py
    - pipelines/etap/watersports_pipeline.py
    - pipelines/etap/watertours_pipeline.py
decisions:
  - "flight_pipeline.py uses adapter pattern instead of direct import due to unique signature (cfg, article)"
  - "All _build_and_deploy functions removed from ETAP pipelines — dispatcher.py _build_and_deploy_central() handles deployment"
metrics:
  duration: "15 minutes"
  completed: "2026-08-06"
---

# Phase 59 Plan 1: Replace per-pipeline _write_hugo_post() Summary

Replaced 34 duplicate `_write_hugo_post()` function definitions across ETAP pipelines with shared import from `shared/publishers/hugo_writer.py`.

## What Was Done

### Staged Rollout
1. **Batch 1 (3 pipelines)**: adventure, airlines, airports — verified Hugo builds pass
2. **Batch 2 (31 pipelines)**: All remaining ETAP pipelines migrated atomically
3. **Special case**: flight_pipeline.py wrapped with adapter pattern

### Changes Per Pipeline
- Removed local `_write_hugo_post()` function definition (50-80 lines each)
- Added import: `from shared.publishers.hugo_writer import _write_hugo_post_etap as _write_hugo_post`
- Removed local `_build_and_deploy()` function and calls (dispatcher handles centrally)

### flight_pipeline.py Adapter
- Created adapter function that wraps shared `_write_hugo_post_etap`
- Preserves original `(cfg, article)` signature for backward compatibility
- Delegates to shared function for internal links, adsense, cross-sell, body images

## Verification

```bash
# No local _write_hugo_post definitions remain (except adapter)
grep -r 'def _write_hugo_post' pipelines/etap/ | wc -l
# Result: 1 (flight_pipeline.py adapter)

# All pipelines have shared import
grep -r 'from shared.publishers.hugo_writer import _write_hugo_post_etap' pipelines/etap/ | wc -l
# Result: 35

# Hugo builds verified for sample blogs
for blog in adventure airlines airports bus cruise culture; do
  cd /Users/twinssn/Projects/ETAP/${blog}-hugo && HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify 2>&1 | tail -1
done
# All passed
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Auto-add missing critical functionality] Removed redundant _build_and_deploy**
- **Found during:** Task 4
- **Issue:** ETAP pipelines had local `_build_and_deploy()` functions that were redundant with `dispatcher.py _build_and_deploy_central()`
- **Fix:** Removed all local `_build_and_deploy()` functions and calls from all 35 pipelines
- **Files modified:** All pipelines/etap/*_pipeline.py
- **Commit:** a64544294

## Known Stubs

None — all stubs have been resolved.

## Threat Flags

None — no new security-relevant surface introduced.

## Self-Check: PASSED

- [✅] All 35 pipelines have shared import
- [✅] Only flight_pipeline.py has local `_write_hugo_post` (adapter pattern)
- [✅] No `_build_and_deploy` calls remain in ETAP pipelines
- [✅] Hugo builds verified for 6 sample blogs
