# Phase 32 — TAP Scheduler Unload (Dual Scheduling Risk Removal)

**Goal:** Eliminate the duplicate `tap-blogger` publish trigger by unload-disabling TAP's own launchd scheduler, leaving 5000 dispatcher as the sole publisher.

**Mode:** execution-complete (retrospective — executed 2026-07-24)

## Context

`REPORT_verify.md` confirmed V-1 dual scheduling risk:
- Both `com.5000.scheduler` and `com.tap.scheduler` were loaded and running.
- `tap-blogger` schedule times overlapped 100% (9 general + 1 festival).
- TAP dedup is intra-process only; no inter-process lock exists between the two schedulers.

Fix scope is limited to launchd service state. No `.py`, `.env`, or DB changes were made.

## Tasks

### Task 32-01 — Pre-change snapshot and backup
- [x] Capture `launchctl list` output showing both schedulers loaded.
- [x] Back up `~/Library/LaunchAgents/com.tap.scheduler.plist` to `.bak_20260724`.
- [x] Confirm backup file size matches original.

### Task 32-02 — Unload and disable TAP scheduler
- [x] Run `launchctl bootout gui/$(id -u)/com.tap.scheduler`.
- [x] Move active plist to `com.tap.scheduler.plist.disabled` to prevent relaunch on reboot.
- [x] Record exit codes and errors from each command.

### Task 32-03 — Post-change verification
- [x] Re-run `launchctl list | grep -i -E "5000|tap|scheduler"` and confirm `com.tap.scheduler` is no longer loaded.
- [x] Confirm `com.5000.scheduler` still has PID and exit 0.
- [x] Check for residual child processes (`ps aux | grep -i -E "app.py run|run_festival|TAP/scheduler"`).

### Task 32-04 — Publishing-path integrity check (read-only)
- [x] Confirm `config/blogs.d/tap.yaml` still has `tap-blogger` with `status: active`.
- [x] Confirm `dispatcher.py` still routes `pipeline: tap` to `_run_tap_subprocess(cfg)`.
- [x] No actual `python dispatcher.py tap-blogger` execution performed.

## Verification Criteria

| Criterion | Evidence | Status |
|-----------|----------|--------|
| TAP scheduler unloaded | `launchctl list` no longer shows `com.tap.scheduler` | verified |
| 5000 scheduler alive | PID 787 present with exit 0 | verified |
| No residual TAP processes | `ps aux` grep returned none | verified |
| Backup exists | `.bak_20260724` file present, size 1085 | verified |
| 5000 tap-blogger path intact | `tap.yaml` active + `_run_tap_subprocess` exists | verified |
| No code/DB/env mutation | Only plist moved; no `.py`/`.env`/DB edits | verified |

## Rollback Procedure (documented, not executed)

If restoration is needed:
1. `mv ~/Library/LaunchAgents/com.tap.scheduler.plist.disabled ~/Library/LaunchAgents/com.tap.scheduler.plist`
2. `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tap.scheduler.plist`
3. Verify with `launchctl list | grep com.tap.scheduler`

## Residual Risks

- **R1 (low):** If TAP scheduler is later needed for non-blogger jobs, it must be re-enabled and its schedule decoupled from `tap-blogger`.
- **R2 (none):** 5000 dispatcher remains the sole publisher for `tap-blogger`; no functionality lost.
- **R3 (none):** Child-process cleanup was verified; no orphaned TAP workers remain.

## Deliverables

- `com.tap.scheduler` unloaded and disabled.
- Backup plist preserved at `~/Library/LaunchAgents/com.tap.scheduler.plist.bak_20260724`.
- `REPORT_fix_v1.md` with STEP 0–4 execution log.
- This `PLAN.md` for phase tracking.
