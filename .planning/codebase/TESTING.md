---
focus: quality
last_mapped: 2026-06-30
version: 1
---

# Testing

## Current State

**No testing framework is configured.** There are no automated tests for the application code.

## Test Files Found

| File | Purpose | Lines |
|------|---------|-------|
| `scripts/test_sigungu_check.py` | Manual test for sigungu (administrative district) validation | ~50 |
| `scripts/test_sigungu_distribution.py` | Manual test for sigungu distribution logic | ~100 |

These are standalone Python scripts, NOT compatible with any test runner (pytest, unittest, etc.). They are run manually:
```bash
python scripts/test_sigungu_check.py
```

## What Is Not Tested

- **All pipelines**: car, etap, gap, rap, senior, stock, travel, curation — no tests
- **Shared modules**: ai_writer, humanizer, publisher, entity_linker, r2_uploader, etc. — no tests
- **Dispatcher routing**: `dispatcher.py` — no tests
- **Scheduler logic**: `scheduler.py` — no tests
- **Config parsing**: `blogs.yaml` loading — no tests
- **Database operations**: SQL queries, ledger recording — no tests
- **Deployment**: Hugo build, wrangler deploy — no tests
- **Cloudflare Workers**: `redirect-worker.js` — no tests

## CI/CD

- **GitHub Actions**: Single workflow (`indexnow.yml`) — only submits IndexNow after push to main
- **No test step in CI**: No `npm test`, `pytest`, or equivalent in any workflow
- **No linting**: No ruff, flake8, mypy, or eslint configuration
- **No pre-commit hooks**: No husky, pre-commit, or similar

## Verification Methods Used Instead

| Method | Where Used |
|--------|------------|
| **Startup import checks** | `scheduler.py:33` `_check_imports()`, `dispatcher.py:31` `check_package_imports()` |
| **boto3 deep health check** | `scheduler.py:46` `_check_boto3_deep()` — creates client + R2 health check |
| **Network connectivity check** | `scheduler.py` — tests DNS/API connectivity |
| **Runtime error logging** | Throughout — `logger.error()` captures failures |
| **Telegram alerts** | Critical failures sent to Telegram for manual review |
| **Quality guard** | `pipelines/etap/quality_guard.py` — runtime content quality validation |
| **Topic exhaustion check** | `pipelines/etap/topic_manager.py` — prevents publishing exhausted topics |

## Recommendations

1. **Pytest setup**: Add `pytest` to `requirements.txt`, create `tests/` directory
2. **Unit tests for shared modules**: Start with `validators.py`, `humanizer.py`, `telegram_notifier.py`
3. **Pipeline smoke tests**: Test `run(cfg)` with mock data for each pipeline
4. **Integration tests**: Test dispatcher routing with mock blog config
5. **CI test step**: Add `pytest` to GitHub Actions workflow
6. **Config validation**: Add schema validation for `blogs.yaml` and `prompts.yaml`
7. **Redirect worker tests**: Add Vitest or similar for `redirect-worker.js`
