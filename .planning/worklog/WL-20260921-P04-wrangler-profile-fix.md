# Worklog: P04 Wrangler Profile Fix

**Date:** 2026-09-21
**Issue:** rank-hugo (and all cap blogs) deploy failures since 2026-09-18
**Root Cause:** `~/.wrangler/config/default.toml` points to twinssn@gmail.com (wrong account)
**Fix:** `--profile hugh79757` added to wrangler subprocess commands

## Timeline

| Date | Event |
|------|-------|
| 09-11 to 09-13 | rank-hugo deploy SUCCESS (rc=0, 16-17s) |
| 09-14 to 09-17 | W5 image gate blocked (separate issue) |
| 09-18 to 09-20 | Wrangler auth error 10000 (this fix) |
| 09-21 | Fix applied, deploy verified (rc=0) |

## Root Cause Analysis

`build_wrangler_env()` pops `CLOUDFLARE_API_TOKEN` from env, forcing wrangler to use OAuth profile. Wrangler selects profile from `~/.wrangler/config/default.toml`. At some point before 09-18, `default.toml` was changed to twinssn@gmail.com instead of hugh79757@gmail.com. twinssn account doesn't have access to cap blog Pages projects → auth error 10000.

## Changes

| File | Change |
|------|--------|
| `dispatcher.py:1235,1244` | Added `"--profile", "hugh79757"` to wrangler deploy commands |
| `shared/publishers/deploy.py:382,390,440,448` | Added `"--profile", "hugh79757"` to wrangler deploy commands (initial + retry) |

## Verification

- rank-hugo deploy: rc=0, 100 files uploaded, deployment complete
- Test command: `python3 -c "from shared.publishers.deploy import build_wrangler_env; ..."` with `--profile hugh79757`

## Impact

- Fixes P04 deploy CRITICAL for rank-hugo (open since 2026-09-19)
- Fixes deploy for all cap blogs (compare, deal, guide, pick, hotissue, ev, tco)
- 6 articles (09-16 to 09-20) were published but not deployed — will deploy on next run

## Related Issues

- **STAP**: `STAP/shared/publisher.py:297-305` has inline wrangler deploy WITHOUT --profile and WITHOUT CLOUDFLARE_API_TOKEN stripping. Separate fix needed.
- **STRUCT-02**: `publisher.py` CLOUDFLARE_API_TOKEN inconsistency — pre-existing, not introduced by this fix.

## Commit

`67b72c79d` — fix(deploy): add --profile hugh79757 to wrangler commands
