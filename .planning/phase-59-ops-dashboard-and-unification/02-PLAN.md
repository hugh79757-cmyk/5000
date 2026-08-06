---
phase: 59-ops-dashboard-and-unification
plan: 02
type: execute
wave: 1
depends_on:
  - 59-01
files_modified:
  - ops_dashboard/app.py
  - ops_dashboard/seed.py
autonomous: true
requirements:
  - dashboard-flask-ui
  - dashboard-json-api
must_haves:
  truths:
    - "Flask app serves on port 5060 with 4 human pages + 4 JSON endpoints"
    - "Basic Auth protects all routes"
    - "GET /api/fleet returns full fleet status as JSON"
    - "GET /api/attention returns items needing human attention"
    - "Manual trigger endpoint runs all checks and updates ops.db"
  artifacts:
    - path: "ops_dashboard/app.py"
      provides: "Flask application with routes, auth, JSON API"
      exports: ["app", "create_app"]
    - path: "ops_dashboard/seed.py"
      provides: "CLI entry for init_db + sync + seed + check run"
  key_links:
    - from: "ops_dashboard/app.py"
      to: "ops_dashboard/checks/__init__.py"
      via: "import run_all_checks"
      pattern: "from ops_dashboard.checks import"
    - from: "ops_dashboard/app.py"
      to: "ops_dashboard/db.py"
      via: "import get_conn, get_all_blogs, get_attention_items, get_blog_detail"
      pattern: "from ops_dashboard.db import"
---

<objective>
Build the Flask web application with routes, Basic Auth, JSON API, and CLI seed entry point.

Purpose: The health check engine (Plan 01) produces data — this plan makes it visible to humans and agents via web UI and JSON API.
Output: Flask app (app.py) + CLI seed script (seed.py)
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@ops_dashboard/db.py
@ops_dashboard/checks/__init__.py
@.planning/phase-59-ops-dashboard-and-unification/CONTEXT.md

<interfaces>
<!-- From Plan 01 output — check engine API -->
From ops_dashboard/checks/__init__.py:
```python
CHECKS: dict[str, Callable] = {}
def register_check(name: str): ...
def run_all_checks(conn, blog_ids: list[str] | None = None) -> dict:
    """Returns {total, pass, fail, unknown, attention_items: list}"""
```

<!-- From ops_dashboard/db.py — data access layer -->
```python
def get_conn(db_path=None) -> sqlite3.Connection: ...
def init_db(conn) -> None: ...
def sync_blog_lifecycle(conn) -> int: ...
def get_all_blogs(conn) -> list[dict]: ...
def get_attention_items(conn) -> dict: ...
def get_blog_detail(conn, blog_id) -> dict | None: ...
def record_check(conn, blog_id, check_name, status, detail="", evidence_url="") -> None: ...
def seed_known_issues(conn) -> int: ...
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Flask app with routes, auth, and JSON API</name>
  <files>ops_dashboard/app.py</files>
  <action>
Create the Flask application with all routes and Basic Auth middleware.

**ops_dashboard/app.py:**

```python
import os
from functools import wraps
from flask import Flask, render_template, jsonify, request, redirect, url_for
from ops_dashboard.db import (
    get_conn, init_db, sync_blog_lifecycle, get_all_blogs,
    get_attention_items, get_blog_detail, seed_known_issues,
)
from ops_dashboard.checks import run_all_checks, CHECKS
```

**App factory:** `create_app()` — creates Flask app, sets `ops_dashboard/templates` as template folder, `ops_dashboard/static` as static folder.

**Basic Auth middleware:**
- Read `OPS_USER` and `OPS_PASSWORD` from environment variables (default: `ops` / `changeme`)
- Apply to all routes via `@require_auth` decorator
- Use `werkzeug.security.check_password_hash` if password is hashed, else plain comparison
- Return 401 with `WWW-Authenticate: Basic` header on failure

**Human routes:**
- `GET /` — render `index.html` with: fleet summary (all blogs grouped by brand), attention items from `get_attention_items()`, check summary counts
- `GET /blog/<blog_id>` — render `blog.html` with: `get_blog_detail(blog_id)` result (blog info, recent checks, related issues)
- `GET /issues` — render `issues.html` with: all known_issues from DB, grouped by gsd_status
- `GET /standards` — render `standards.html` with: standard_rules summary, compliance rates per brand

**JSON API routes (no template rendering):**
- `GET /api/fleet` — `jsonify(get_all_blogs(conn))`
- `GET /api/attention` — `jsonify(get_attention_items(conn))`
- `GET /api/issues` — query all known_issues, `jsonify([dict(r) for r in rows])`
- `GET /api/standards` — query standard_rules from check_results, `jsonify(standards_summary)`

**Manual trigger endpoint:**
- `POST /api/run-checks` — runs `run_all_checks(conn)`, returns summary JSON `{total, pass, fail, unknown}`
- Optional: `?blog_id=xxx` query param to run checks on a single blog
- This is the endpoint that triggers a full check suite run

**Startup:**
- On first request (or at import time): `init_db(conn)`, `sync_blog_lifecycle(conn)`, `seed_known_issues(conn)`
- Store conn in Flask `g` object or create per-request

**Error handling:**
- 404 → render `404.html` or return JSON `{"error": "not found"}`
- 500 → return JSON `{"error": "internal server error"}` + log traceback

**Important:**
- Port 5060 hardcoded in `if __name__ == "__main__": app.run(port=5060, debug=False)`
- debug=False in production (security)
- All routes must handle empty DB gracefully (no crashes on empty state)
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && python -c "
from ops_dashboard.app import create_app
app = create_app()
client = app.test_client()

# Test without auth → 401
resp = client.get('/')
assert resp.status_code == 401, f'Expected 401, got {resp.status_code}'

# Test with auth → 200
import base64
creds = base64.b64encode(b'ops:changeme').decode()
resp = client.get('/', headers={'Authorization': f'Basic {creds}'})
assert resp.status_code == 200, f'Expected 200, got {resp.status_code}'

# Test JSON API
resp = client.get('/api/fleet', headers={'Authorization': f'Basic {creds}'})
assert resp.status_code == 200
data = resp.get_json()
assert isinstance(data, list), f'Expected list, got {type(data)}'

# Test run-checks trigger
resp = client.post('/api/run-checks', headers={'Authorization': f'Basic {creds}'})
assert resp.status_code == 200
summary = resp.get_json()
assert 'total' in summary
print('PASS: Flask app routes + auth + JSON API')
"</automated>
  </verify>
  <done>
    - Flask app serves on port 5060
    - Basic Auth protects all routes (401 without credentials)
    - 4 human pages: /, /blog/<id>, /issues, /standards
    - 4 JSON API endpoints: /api/fleet, /api/attention, /api/issues, /api/standards
    - POST /api/run-checks triggers health check suite
    - App handles empty DB gracefully
  </done>
</task>

<task type="auto">
  <name>Task 2: CLI seed script (ops_dashboard/seed.py)</name>
  <files>ops_dashboard/seed.py</files>
  <action>
Create a standalone CLI entry point for initializing and seeding the ops database.

**ops_dashboard/seed.py:**
```python
"""CLI entry: init DB, sync YAML, seed issues, optionally run checks."""
import argparse
import sys
from ops_dashboard.db import get_conn, init_db, sync_blog_lifecycle, seed_known_issues
from ops_dashboard.checks import run_all_checks

def main():
    parser = argparse.ArgumentParser(description="Ops Dashboard DB setup")
    parser.add_argument("--run-checks", action="store_true", help="Run all checks after seeding")
    parser.add_argument("--db-path", default=None, help="Custom DB path")
    args = parser.parse_args()

    conn = get_conn(args.db_path)
    init_db(conn)

    blog_count = sync_blog_lifecycle(conn)
    print(f"Synced {blog_count} blogs from YAML")

    issue_count = seed_known_issues(conn)
    print(f"Seeded {issue_count} known issues")

    if args.run_checks:
        print("Running all checks...")
        summary = run_all_checks(conn)
        print(f"Checks complete: {summary}")

    conn.close()

if __name__ == "__main__":
    main()
```

Also add `ops_dashboard/__init__.py` if it doesn't exist (empty file for package import).
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && python ops_dashboard/seed.py && python -c "
from ops_dashboard.db import get_conn
conn = get_conn()
blogs = conn.execute('SELECT COUNT(*) FROM blog_lifecycle').fetchone()[0]
issues = conn.execute('SELECT COUNT(*) FROM known_issues').fetchone()[0]
print(f'Blogs: {blogs}, Issues: {issues}')
assert blogs > 0, 'No blogs synced'
assert issues > 0, 'No issues seeded'
print('PASS: seed script')
"</automated>
  </verify>
  <done>
    - seed.py initializes DB, syncs YAML, seeds issues
    - --run-checks flag triggers full check suite
    - Blog count matches YAML files (79+ blogs)
    - Issue count matches SEED_ISSUES (52 issues)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| HTTP request → Flask app | Unauthenticated requests must be rejected by Basic Auth |
| Environment → auth credentials | OPS_USER/OPS_PASSWORD from env — weak default must be changed |
| API endpoint → check trigger | POST /api/run-checks could be abused for resource exhaustion |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-59-04 | Spoofing | Basic Auth bypass | mitigate | Check auth on every request, no bypass routes |
| T-59-05 | Tampering | check_results writes | mitigate | Only POST /api/run-checks writes, authenticated |
| T-59-06 | Denial of Service | /api/run-checks resource use | accept | Rate limiting not in scope; manual trigger only |
| T-59-07 | Information Disclosure | /api/* endpoints | mitigate | All endpoints require Basic Auth |
</threat_model>

<verification>
- Flask app starts on port 5060 without errors
- All 4 human pages return 200 with auth
- All 4 JSON API endpoints return valid JSON with auth
- Unauthenticated requests return 401
- POST /api/run-checks runs checks and returns summary
- seed.py initializes DB with 79+ blogs and 52 issues
</verification>

<success_criteria>
- Flask app is a complete web application with all required routes
- Basic Auth protects every endpoint
- JSON API returns structured data for agent consumption
- Manual check trigger works end-to-end
- CLI seed script provides standalone DB initialization
</success_criteria>

<output>
Create `.planning/phases/59-ops-dashboard-and-unification/59-02-SUMMARY.md` when done
</output>
