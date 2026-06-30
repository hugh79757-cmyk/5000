---
phase: 3
plan: 03-03
completed: 2026-06-30
status: complete
---

# Plan 03-03 Summary: External Dependency Isolation

## Objective

Wrap TAP/STAP/ETAP subprocess calls with clear error handling.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 3.1 | `b3fa52e6e` | Add guard checks for missing TAP/STAP with clear error messages |

## Status

- [x] STAP: directory existence check at start of `_run_stap()`
- [x] TAP: directory existence check at start of `_run_tap_subprocess()`
- [x] Error messages: "TAP/STAP 프로젝트를 찾을 수 없음: {path}. {ENV_VAR} 환경변수를 확인하세요."
- [x] 43/43 tests pass, ruff clean, mypy clean

## Notes

- TAP entity import in `shared/publisher.py` already has try/except from original code
- The subprocess approach is preserved — the isolation is about graceful failure, not technical decoupling
