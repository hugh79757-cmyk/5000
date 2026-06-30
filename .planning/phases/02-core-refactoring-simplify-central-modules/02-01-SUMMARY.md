---
phase: 2
plan: 02-01
completed: 2026-06-30
status: complete
---

# Plan 02-01 Summary: Dispatcher Registry

## Objective

Replace the brittle 35+ elif chain in dispatcher.py with a dynamic pipeline registry.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1.1-1.2 | `401fc84d4` | Replace elif chain with dynamic pipeline registry |
| — | `78fbd0da7` | Remove GAP pipeline (no active blogs) |
| 1.3 | `dca937f36` | Add registry integration test |
| 1.4 | `7856a3464` | Fix import style |

## Status

- [x] `_resolve_pipeline()` creates dynamic imports by convention
- [x] ETAP blog-specific routing uses convention-based naming
- [x] TAP/STAP subprocess isolation preserved
- [x] Integration test covers all active blogs
- [x] 43/43 tests pass, ruff clean, mypy clean

## Deviations

- GAP pipeline removed entirely (both blogs were `status: inactive`)
- `_run_tap_subprocess()` extracted as separate function for clarity
