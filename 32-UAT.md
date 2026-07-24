# 32-UAT.md — Phase 32: TAP Scheduler Unload

## Summary
- Phase: 32
- Feature: Remove duplicate `tap-blogger` publish trigger by unloading `com.tap.scheduler`
- Tester: GSD verify-work run on 2026-07-24
- Result: PASS — all user-visible acceptance criteria met

---

## Test 1 — Duplicate scheduler is removed from launchd

**User story:**
As an operator, I want only one scheduler triggering `tap-blogger`, so I don't have race-condition risk from two overlapping schedules.

**Steps:**
1. Run `launchctl list | grep -i -E "5000|tap|scheduler"`
2. Confirm `com.tap.scheduler` is absent
3. Confirm `com.5000.scheduler` is still present

**Actual result:**
```
12389	-9	com.5000.dashboard
785	0	com.5000.analytics.watchdog
-	0	com.sap.scheduler
-	1	com.5000.master-backup
792	0	com.5000.analytics
787	0	com.5000.scheduler
```

**Expected result:**
- `com.tap.scheduler` absent
- `com.5000.scheduler` present with PID `787`

**Verdict:** PASS

---

## Test 2 — No orphaned TAP worker remains after unload

**User story:**
As an operator, I want no leftover TAP scheduler child processes after disabling the service, so the system is clean.

**Steps:**
1. Run `ps aux | grep -i -E "app.py run|run_festival|TAP/scheduler" | grep -v grep`
2. Confirm zero matches

**Actual result:**
```
(no output)
```

**Expected result:**
- zero matches

**Verdict:** PASS

---

## Test 3 — TAP publish path is preserved through 5000

**User story:**
As an operator, I want `tap-blogger` to keep publishing through 5000 after TAP scheduler removal, so content flow doesn't break.

**Steps:**
1. Confirm `config/blogs.d/tap.yaml` still has `tap-blogger` with `status: active`
2. Confirm `dispatcher.py` still routes `pipeline: tap` to `_run_tap_subprocess(cfg)`
3. Do not run an actual publish job in this UAT

**Actual result:**
- `tap.yaml` contains active `tap-blogger`
- `dispatcher.py` line 439 defines `_run_tap_subprocess(cfg)`

**Expected result:**
- active config preserved
- dispatch path preserved

**Verdict:** PASS

---

## Test 4 — Backup and rollback material are present

**User story:**
As an operator, I want a restore path and backup plist after changing launchd state, so I can recover if needed.

**Steps:**
1. Confirm backup plist exists
2. Confirm disabled plist exists
3. Confirm rollback commands are documented

**Actual result:**
- `/Users/twinssn/Library/LaunchAgents/com.tap.scheduler.plist.bak_20260724` exists
- `/Users/twinssn/Library/LaunchAgents/com.tap.scheduler.plist.disabled` exists
- Rollback commands are documented in `REPORT_fix_v1.md` STEP 4

**Expected result:**
- backup present
- disabled plist present
- rollback documented

**Verdict:** PASS

---

## Overall Result

| Test | Result |
|------|--------|
| 1 — duplicate scheduler removed | PASS |
| 2 — no orphaned TAP processes | PASS |
| 3 — 5000 publish path intact | PASS |
| 4 — backup/rollback present | PASS |

**Phase 32 UAT status:** PASSED

**Recommendation:**
- No blocking issues found.
- Next action: keep monitoring `tap-blogger` publish logs through `com.5000.scheduler` for the next scheduled windows.
