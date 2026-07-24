# RESEARCH.md — Phase 32: TAP Scheduler Unload

## Source of truth
- `REPORT_verify.md` V-1: dual scheduling risk confirmed.
- `REPORT_fix_v1.md`: executed fix steps and results.

## Finding 1: dual scheduler is real
- `launchctl list` shows both `com.5000.scheduler` (PID 787) and `com.tap.scheduler` (PID 38430) loaded.
- `config/blogs.d/tap.yaml` has `tap-blogger` with `status: active` and 10 schedule times.
- 5000 `scheduler.py` registers every active blog's schedule times via `schedule.every().day.at(t).do(queue_publish, blog_id)`.
- TAP `scheduler.py` also runs `app.py run` at the same 9 general times + 11:00 festival.

## Finding 2: 5000 dispatcher already owns tap-blogger
- `dispatcher.py` routes `pipeline: tap` to `_run_tap_subprocess(cfg)`.
- The subprocess runner loads TAP `.env` and calls `app.run_publish()`.
- So removing TAP scheduler does not remove tap-blogger publishing; 5000 scheduler remains the publisher.

## Finding 3: TAP dedup is intra-process only
- TAP `app.py` uses `ContentPool.is_published` for dedup.
- No inter-process lock (flock/semaphore) was found between the two schedulers.
- This confirms race-condition risk if both schedulers fire simultaneously.

## Finding 4: safe removal target
- The only change needed to remove the duplicate trigger is disabling `com.tap.scheduler`.
- `com.5000.scheduler` must remain untouched.
- No code/DB/env changes required.

## Rollback evidence
- Original plist backed up to `~/Library/LaunchAgents/com.tap.scheduler.plist.bak_20260724`.
- Rollback commands are documented in `REPORT_fix_v1.md` STEP 4.
