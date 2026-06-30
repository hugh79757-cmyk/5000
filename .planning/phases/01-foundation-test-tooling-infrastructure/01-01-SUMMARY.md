---
phase: 1
plan: 01-01
completed: 2026-06-30
status: complete
---

# Plan 01-01 Summary: Tooling & Test Infrastructure

## Objective

Create the tooling foundation: `pyproject.toml` with all configs, `tests/` directory structure, CI workflow, and verify Python 3.14 compatibility.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1.1-1.5 | `5b1a820dd` | Add tooling infra — pyproject.toml, tests/, CI, remove compat check |
| 1.6 | `d9a624b7b` | ruff + mypy config, auto-fixes, syntax fix in wordpress_publisher |

## Status

- [x] `pyproject.toml` created with pytest, ruff, mypy config
- [x] `requirements.txt` updated with ruff, mypy, pytest, pytest-cov
- [x] `tests/` directory structure created
- [x] `.github/workflows/ci.yml` created
- [x] `check_package_imports()` removed from `dispatcher.py`
- [x] ruff check passes (exit 0)
- [x] mypy passes (no issues)
- [x] pytest runs (no tests to run yet — placeholder structure)
- [x] Syntax error fixed in `wordpress_publisher.py`

## Deviations

- Mypy strict mode was too strict for legacy codebase — configured as "strict-lite" (disable untyped def/call errors, various error codes disabled). Strictness can be increased incrementally as type annotations are added.
