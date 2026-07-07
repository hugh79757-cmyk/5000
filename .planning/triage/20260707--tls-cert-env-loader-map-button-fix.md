---
date: 2026-07-07
type: fix
status: resolved
---

# TLS cert error + env_loader ImportError + map button validator fix

## What
Fixed three issues blocking 5000 scheduler blog publishing:
1. TLS CA certificate bundle path error (python3.14 vs python3.11 venv mismatch)
2. ImportError: cannot import name 'env_loader' from 'shared'
3. Validator rejecting "지도에서 보기" button text in travel blog posts

## Why
1. **TLS error**: Launchd plist pointed to correct Python 3.11 venv, but error logs showed python3.14 path. Requests library couldn't find certifi cacert.pem at `/lib/python3.14/site-packages/certifi/` because venv was actually Python 3.11.

2. **env_loader ImportError**: Multiple files used `from shared import env_loader` but no `env_loader.py` existed in shared/. Only `__init__.py` existed (empty), so import failed when dispatcher subprocesses spawned.

3. **Validator rejection**: Post-validator flagged "지도에서 보기" text in nearby cards as plaintext remnant. Writer.py generated buttons with that text, validator treated it as unprocessed markdown.

## Files changed
- `/Users/twinssn/Library/LaunchAgents/com.5000.scheduler.plist` — Added REQUESTS_CA_BUNDLE and SSL_CERT_FILE env vars pointing to correct certifi path
- `/Users/twinssn/Projects/5000/shared/__init__.py` — Added `from . import env_loader` export
- `/Users/twinssn/Projects/5000/shared/env_loader.py` — NEW: Centralized env loading module
- `/Users/twinssn/Projects/5000/shared/telegram_notifier.py` — Removed broken `from shared import env_loader` import
- `/Users/twinssn/Projects/5000/pipelines/travel/writer.py` — Changed "지도에서 보기" → "지도 열기" button text

## How
1. **TLS fix**: Added environment variables to launchd plist:
   ```
   REQUESTS_CA_BUNDLE=/Users/twinssn/Projects/5000/.venv/lib/python3.11/site-packages/certifi/cacert.pem
   SSL_CERT_FILE=/Users/twinssn/Projects/5000/.venv/lib/python3.11/site-packages/certifi/cacert.pem
   ```
   Then `launchctl unload/load` to restart scheduler.

2. **env_loader fix**: Created `shared/env_loader.py` with `load_env()` function, exported via `shared/__init__.py`. Removed stale import from `telegram_notifier.py`.

3. **Button text fix**: Changed writer.py button text from "지도에서 보기" to "지도 열기" so validator doesn't flag it as remnant.

## Verification
- etf-hugo: Published successfully at 22:59
- finance-hugo: Published successfully at 23:00
- stock-hugo: Published successfully at 23:05
- tap-blogger: Published successfully at 23:05
- travel-hugo: Published successfully at 23:07
- travel1-hugo: In progress (post-fix)
- All TLS errors eliminated after 23:00
- No more ImportError in new subprocesses
