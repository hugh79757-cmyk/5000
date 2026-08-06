---
phase: 59
plan: 11
subsystem: dispatcher
tags: [etap, naming, consistency, deploy-routing]
requires: [etap-deploy-consolidation]
provides: [etap-naming-fix]
affects: [dispatcher.py]
decisions:
  - "Fixed flights-hugo/flight-hugo naming inconsistency in ETAP_PIPELINE_BLOGS"
tech-stack:
  added: []
  patterns: [naming-consistency, deploy-routing]
key-files:
  created: []
  modified: [dispatcher.py]
metrics:
  duration: "5m"
  completed: "2026-08-06T06:00:00Z"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 59 Plan 11: ETAP Deploy Routing + Naming Fix Summary

## What Was Built

Fixed the `flights-hugo`/`flight-hugo` naming inconsistency in `dispatcher.py` that prevented `flights-hugo` from being deployed via the central deploy path.

## Problem Analysis

### Naming Chain (Before Fix)
```
YAML config: flights-hugo (etap.yaml line 257)
Dispatcher: flight-hugo (ETAP_PIPELINE_BLOGS line 551) ← BUG
ETAP exceptions: flights-hugo → pipelines.etap.flight_pipeline (correct)
Cloudflare: flights-hugo (CF Pages project name)
```

### Impact
- `flights-hugo` was NOT in `ETAP_PIPELINE_BLOGS` set
- When `flights-hugo` published successfully, line 728 check `if blog_id in ETAP_PIPELINE_BLOGS` would fail
- Central deploy path `_build_and_deploy_central()` would NOT be called
- `flights-hugo` would not be deployed after successful content generation

## What Was Implemented

### Fixed `ETAP_PIPELINE_BLOGS` set
- Changed `flight-hugo` to `flights-hugo` on line 551
- Now matches YAML config and Cloudflare Pages project name

### Naming Chain (After Fix)
```
YAML config: flights-hugo (etap.yaml line 257)
Dispatcher: flights-hugo (ETAP_PIPELINE_BLOGS line 551) ✓ FIXED
ETAP exceptions: flights-hugo → pipelines.etap.flight_pipeline (correct)
Cloudflare: flights-hugo (CF Pages project name)
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all implementations are complete and functional.

## Threat Flags

None — no new security-relevant surface introduced.

## Verification

- [✅] `flights-hugo` in `ETAP_PIPELINE_BLOGS`. 근거: Python verification confirmed `flights-hugo in ETAP_PIPELINE_BLOGS: True`
- [✅] `flight-hugo` NOT in `ETAP_PIPELINE_BLOGS`. 근거: Python verification confirmed `flight-hugo in ETAP_PIPELINE_BLOGS: False`
- [✅] No remaining `flight` references without 's'. 근거: `grep -n 'flight' dispatcher.py | grep -v flights` returned empty
- [✅] `_ETAP_BLOG_EXCEPTIONS` mapping correct. 근거: `flights-hugo → pipelines.etap.flight_pipeline`
- [✅] No individual ETAP pipeline deploy calls remain. 근거: `grep -r '_build_and_deploy\|_deploy_site' pipelines/etap/*_pipeline.py | wc -l` returned 0

## Residual Risks

None — fix is minimal and targeted.

## Self-Check: PASSED

- [✅] dispatcher.py — FOUND. 근거: file exists at /Users/twinssn/Projects/5000/dispatcher.py
- [✅] commit 05ff4df89 — FOUND. 근거: git log shows commit on main branch

## Commits

- `05ff4df89`: `fix(59-11): fix flights-hugo naming in ETAP_PIPELINE_BLOGS`
