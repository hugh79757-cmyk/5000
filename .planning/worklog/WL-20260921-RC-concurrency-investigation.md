# Worklog: RC-1~RC-4 Concurrency Investigation

## Date
2026-09-21

## Context
User verdict accepted all workstreams (X-0~X-5, Y-0~Y-5). V-3 root cause investigation ordered: 'cancelled' not 'failed'. RC-1 through RC-4 investigation required before next slot.

## RC-1: Concurrency Eviction — CONFIRMED

### Evidence
- Run 35551785126 (publish-rank.yml): created 01:42:47Z, cancelled 01:43:17Z (30s), 0 jobs
- ev-hugo was active in `publish-lock-car` group (started 01:41:36, completed 01:43:28)
- compare-hugo (created 28s later) succeeded because ev-hugo completed within its queue window
- All workflows share `publish-lock-car` with `cancel-in-progress: false`

### Root Cause
GitHub Actions cron jitter (±2h) compresses triggers into narrow windows. ev-hugo(23:45 cron) + rank-hugo(23:50 cron) fired within 90s of each other due to jitter. rank-hugo entered queue behind active ev-hugo, hit 30s pending timeout.

### Timeline (2026-09-21 UTC)
| Time | Workflow | Duration |
|---|---|---|
| 01:36:17 | guide-hugo | 1m49s |
| 01:39:38 | deal-hugo | 1m55s |
| 01:41:21 | ev-hugo | 2m7s |
| **01:42:47** | **rank-hugo → cancelled** | **30s, 0 jobs** |
| 01:43:15 | compare-hugo | 1m54s |

## RC-2: Workflow Cross-Table

### Active workflows sharing publish-lock-car
| Workflow | Cron | cancel-in-progress |
|---|---|---|
| rank-hugo | 23:50 | false |
| compare-hugo | 22:40 | false |
| deal-hugo | 22:35 | false |
| daily_refresh | 00:00 (→00:30 after RC-4) | false |
| pick-hugo | 23:55 | false |

### Contention window
23:50–01:50 UTC (rank-hugo jitter range) overlaps with hotissue/ev/guide/deal/compare schedules. All share same concurrency group → serial execution → queue saturation.

### Recommended fix
1. Schedule spacing (quick): 10-35min separation between deal/compare/rank
2. Group separation (structural): Split publish-lock-car into car-core vs cap-non-car

## RC-3: State Integrity — CLEAN

- STATE_FILES: No partial state files from cancelled run
- publish_ledger: No INSERT at 01:43 UTC window. Last rank entry: 2026-09-20 06:50:35
- Blogger orphans: N/A (rank-hugo is Hugo platform)
- Lock files: Only stale .hugo_build.lock (2026-04-14), not from cancelled run

## RC-4: Conditional Hotfix — APPLIED

### Change
`.github/workflows/daily_refresh.yml`:
- Cron: `"0 0 * * *"` → `"30 0 * * *"` (00:00 → 00:30 UTC)
- Rationale: RC-1 confirmed concurrency eviction. daily_refresh at 00:00 competes with rank-hugo(23:50±2h). Moving to 00:30 adds 40min buffer.

### Impact
- daily_refresh runs at 07:30 +07 instead of 07:00 +07
- R2 put avoidance window: rank 23:50 + 40min (was +10min)
- No change to PHASE 1 dry-run behavior

## Y-2 Worklog Addition
P28 "completed 2026-09-07" date: source is airlines_pipeline.py verification run on Sep 7. P28 was registered in problem_registry during Phase 76 Wave 2-4. Airlines pipeline returns standard dict (P28-safe in normal flow). Only P28 exposure: uncaught exception in _run_impl() propagating to dispatcher.

## Files Modified
- `.github/workflows/daily_refresh.yml` — cron 00:00→00:30 (RC-4)

## Constraints Verified
- rank 4/4 before batch 1.5/pick commits: NOT ACHIEVED (cancelled run)
- cap.yaml/blogs.d/shared code edits: daily_refresh.yml is .github/workflows (not restricted)
- No real secrets, dry_run=false: respected
- R2 put avoidance window: 40min buffer maintained
