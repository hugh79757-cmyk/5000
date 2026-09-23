---
date: 2026-09-23
type: fix
status: resolved
---

# INFRA-PAUSE-20260920: car.db checker fix + pick-hugo reactivation

## What
- `shared/candidate_availability.py:_connect_car_db_with_retry()` timeout 30→60, retries 3→5, macOS sandbox fallback (non-URI read-only connection)
- pick-hugo lifecycle: paused → active, resume_ready=1, maintenance_status=complete

## Why
- 9/11~9/20: `sqlite3.OperationalError: unable to open database file` on car.db read-only URI mode under launchd
- Previously misclassified as "data exhaustion" — actual root cause was checker DB open failure
- Recovery plan: Step 2 (fix checker) + Step 4 (reactivate pick-hugo)

## Files changed
- `shared/candidate_availability.py` (checker fix)
- `ops_dashboard/ops.db` (blog_lifecycle update — gitignored)

## How
- Increased timeout for transient lock recovery
- Added fallback: if URI read-only fails, try non-URI connection with `PRAGMA query_only=ON`
- Verified car.db connectivity: 135 rows, no errors since 9/20
- pick-hugo reactivated per recovery plan Step 4

## Verification
- `python3 -c "from shared.candidate_availability import _connect_car_db_with_retry; conn=_connect_car_db_with_retry('data/car.db'); print(conn.execute('SELECT COUNT(*) FROM cars').fetchone()[0])"` → 135
- Hugo build OK after reactivation
- No "unable to open database file" in scheduler.log after 9/20
