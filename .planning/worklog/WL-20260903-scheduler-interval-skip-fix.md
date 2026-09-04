# Worklog: scheduler.py interval_skip consecutive_failures fix

**Date**: 2026-09-03
**Issue**: P02 consecutive_failures 5/5 for best-kitchen-hugo, best-beauty-hugo (and 7 more best-* blogs)
**Root cause**: Scheduler `_track_publish_result()` counted `interval_skip` (intentional pipeline skip) as failure
**Severity**: FALSE-POSITIVE P02 alerts

## What changed

### `scheduler.py`
- Added `_SILENT_SKIP_REASONS = frozenset({"interval_skip", "quota_met", "similar_title", "already_running"})`
- Added optional `reason=None` param to `_track_publish_result(blog_id, success, reason=None)`
- Guard: if `reason in _SILENT_SKIP_REASONS` → log `[SKIP]`, return without incrementing counter
- Plumb `_last_publish_reason` global through `run_publish()` → `_drain_queue()` → `_catchup_missed_inner()`
- Exception path (`_drain_queue:500`) passes no reason → real failures still tracked

### Files modified
- `scheduler.py` — 6 surgical edits (1 frozenset, 1 function signature, 1 guard block, 3 caller sites)

## Verification
- Unit test: `_track_publish_result` correctly ignores `interval_skip`, `quota_met`, `similar_title`, `already_running`
- Real failure (no reason) still increments counter
- Success still resets counter
- Dispatcher dry-run: `best-kitchen-hugo` returns `{"success": false, "reason": "interval_skip", "pipeline_status": "FAILED_TRANSIENT"}` with returncode=0
- Scheduler restarted, PID 45719, no errors

## Impact
- 9 best-* blogs (kitchen, beauty, pet-supplies, stationery, books, electronics, fitness, homeappliances, auto) will no longer trigger P02 alerts during 3-day interval gate
- All other blogs unaffected (interval_skip not returned by non-best-* curation blogs currently)

## Residual risk
- **interval_skip gate expires 2026-09-04** for all 9 best-* blogs → they'll publish normally tomorrow
- **Catchup attempts exhausted today** (3/3 for both blogs) → no more catchup dispatches today
- **Test compatibility**: `tests/test_candidate_availability.py:108,532` monkeypatch uses 2-arg lambda — backward compatible (reason is optional kwarg)
- **`similar_title` is not plumbed at scheduler level yet** — rare in practice, no current P02 false-positives from it
