# CONTEXT.md — Phase 32: TAP Scheduler Unload

## Problem
V-1 dual scheduling risk was confirmed in `REPORT_verify.md`:
- `com.5000.scheduler` and `com.tap.scheduler` were both loaded.
- `tap-blogger` had 10 overlapping schedule times with TAP scheduler.
- No inter-process dedup lock existed between the two schedulers.

## Decision
Remove the duplicate trigger by unloading `com.tap.scheduler` only.
Keep `com.5000.scheduler` as the sole publisher for `tap-blogger`.

## Constraints
- Do not modify `.py`, `.env`, or DB files.
- Do not stop `com.5000.scheduler`.
- Do not execute actual publish jobs during verification.

## References
- `.planning/phase-32-tap-scheduler-unload/RESEARCH.md`
- `.planning/phase-32-tap-scheduler-unload/PLAN.md`
- `REPORT_verify.md`
- `REPORT_fix_v1.md`
