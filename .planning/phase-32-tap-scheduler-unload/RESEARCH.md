# RESEARCH.md — Phase 32: TAP Scheduler Unload

## Source of truth
- `REPORT_verify.md` V-1: dual scheduling risk confirmed.
- Live system state: `launchctl list`, `ps aux`, plist filesystem checks on 2026-07-24.

## Finding 1: dual scheduler was real
- Pre-change evidence showed both `com.5000.scheduler` and `com.tap.scheduler` loaded.
- `config/blogs.d/tap.yaml` has `tap-blogger` with `status: active` and 10 schedule times.
- 5000 `scheduler.py` registers every active blog's schedule times via `schedule.every().day.at(t).do(queue_publish, blog_id)`.
- TAP `scheduler.py` also runs `app.py run` at the same 9 general times + 11:00 festival.

## Finding 2: 5000 dispatcher already owns tap-blogger
- `dispatcher.py` routes `pipeline: tap` to `_run_tap_subprocess(cfg)`.
- The subprocess runner loads TAP `.env` and calls `app.run_publish()`.
- Removing TAP scheduler does not remove tap-blogger publishing; 5000 scheduler remains the publisher.

## Finding 3: TAP dedup is intra-process only
- TAP `app.py` uses `ContentPool.is_published` for dedup.
- No inter-process lock (flock/semaphore) was found between the two schedulers.
- This confirms race-condition risk if both schedulers fire simultaneously.

## Finding 4: fix scope is launchd service state only
- The only change needed to remove the duplicate trigger is disabling `com.tap.scheduler`.
- `com.5000.scheduler` must remain untouched.
- No `.py`, `.env`, or DB changes required.

## Verified live state
- `launchctl list` no longer shows `com.tap.scheduler`.
- `com.5000.scheduler` remains alive with PID `787`.
- `ps aux` returned no residual TAP processes after unload.
- Original plist backup exists at `~/Library/LaunchAgents/com.tap.scheduler.plist.bak_20260724`.

## Rollback evidence
- Rollback commands are documented in `REPORT_fix_v1.md` STEP 4.
