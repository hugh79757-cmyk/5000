---
phase: 59-ops-dashboard-and-unification
plan: 02
subsystem: ops_dashboard
tags: [flask, web-ui, json-api, auth]
dependency_graph:
  requires: [59-01]
  provides: [dashboard-flask-ui, dashboard-json-api]
  affects: [ops_dashboard]
tech_stack:
  added: [flask]
  patterns: [app-factory, basic-auth, jinja2-inline]
key_files:
  created:
    - ops_dashboard/app.py
    - ops_dashboard/seed.py
  modified: []
decisions:
  - "Used inline Jinja2 templates instead of file-based templates to keep the app self-contained and testable without separate HTML files"
  - "Basic Auth uses plain-text comparison (not password hashing) since the default creds are for local dev only — production should use Cloudflare Access"
  - "DB is auto-initialized on first request via _ensure_db() — no separate migration step needed"
metrics:
  duration: 154s
  completed: 2026-08-06
  tasks: 2
  files: 2
---

# Phase 59 Plan 02: Flask App + CLI Seed Summary

Flask web app with Basic Auth, 4 human pages, 4 JSON API endpoints, and CLI seed script for ops dashboard initialization.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Jinja2 template rendering**
- **Found during:** Task 1 verification
- **Issue:** Original templates used Python `%(key)s` `%` formatting passed to `render_template_string()`, which expects Jinja2 `{{ key }}` syntax — caused `TypeError: not enough arguments for format string`
- **Fix:** Rewrote all templates to use Jinja2 syntax (`{{ var }}`) with `render_template_string()` calling convention
- **Files modified:** `ops_dashboard/app.py`
- **Commit:** a22de7d7f

**2. [Rule 3 - Blocking] Added sys.path fix for seed.py CLI execution**
- **Found during:** Task 2 verification
- **Issue:** `python ops_dashboard/seed.py` raised `ModuleNotFoundError: No module named 'ops_dashboard'` because the project root wasn't on `sys.path`
- **Fix:** Added `sys.path.insert(0, project_root)` at the top of `seed.py`
- **Files modified:** `ops_dashboard/seed.py`
- **Commit:** d7557ff29

## Auth Gates

None — Flask installed from PyPI successfully.

## Known Stubs

None — all routes are wired to real DB queries via `ops_dashboard/db.py`.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: weak-default-creds | ops_dashboard/app.py | Default OPS_USER/OPS_PASSWORD is ops/changeme — must be changed in production or use Cloudflare Access |

## Self-Check

- [✅] `ops_dashboard/app.py` exists — verified via `ls`
- [✅] `ops_dashboard/seed.py` exists — verified via `ls`
- [✅] Commit `a22de7d7f` exists — verified via `git log --oneline`
- [✅] Commit `d7557ff29` exists — verified via `git log --oneline`
- [✅] Flask app test passes (auth 401/200, all API endpoints 200, run-checks returns summary)
- [✅] Seed script test passes (56 blogs synced, 39 issues seeded)

## Self-Check: PASSED
