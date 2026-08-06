---
phase: 59
plan: 03
subsystem: ops_dashboard
tags: [templates, css, js, ui, responsive]
requires: [59-02]
provides: [templates, static_assets]
affects: [ops_dashboard/app.py]
tech-stack:
  added: [jinja2-templates, css-custom-properties]
  patterns: [mobile-first, dark-theme, table-card-toggle]
key-files:
  created:
    - ops_dashboard/templates/base.html
    - ops_dashboard/templates/index.html
    - ops_dashboard/templates/blog.html
    - ops_dashboard/templates/issues.html
    - ops_dashboard/templates/standards.html
    - ops_dashboard/templates/404.html
    - ops_dashboard/static/style.css
    - ops_dashboard/static/app.js
  modified:
    - ops_dashboard/app.py
decisions:
  - "Replaced inline render_template_string with proper Jinja2 template files"
  - "Dark theme with CSS custom properties for easy theming"
  - "Mobile-first: tables collapse to stacked cards below 768px"
metrics:
  duration: ~15min
  completed: 2026-08-06
  tasks: 8
  files: 9
---

# Phase 59 Plan 03: Dashboard UI Templates Summary

Responsive dashboard UI with dark theme, mobile card view, and sortable tables for the ops dashboard.

## What Was Built

**6 Jinja2 templates** + **1 CSS file** + **1 JS file** replacing the inline `render_template_string` approach:

- **base.html** — Dark theme layout with sticky top nav (Fleet/Issues/Standards), active page highlighting, system-ui font stack
- **index.html** — Fleet summary (total/active/stale/issues stat cards), attention alert banner, sortable blog table with mobile card toggle
- **blog.html** — Blog detail page: info table (brand, theme, domain, failures), health checks table, related issues cards
- **issues.html** — Open/resolved issues split view, each with table + mobile card toggle, sortable columns
- **standards.html** — Brand compliance overview with stat cards per brand (themed/domain counts)
- **404.html** — Not found page with link back to fleet
- **style.css** — CSS custom properties dark theme (`--bg: #1a1a2e`, `--card: #16213e`, `--accent: #0f3460`, `--highlight: #e94560`), responsive breakpoints at 768px/480px, status colors (pass/fail/unknown/open/resolved), mobile card view hidden by default
- **app.js** — Mobile card/table toggle buttons, simple th-click table sort

**app.py updates:**
- Import changed: `render_template_string` → `render_template`
- Removed `_BASE` template string (~40 lines), `_render()`, `_dot()` helpers
- All 4 human routes now use `render_template()` with proper context variables
- Added custom 404 error handler
- API routes unchanged

## Deviations from Plan

None — plan executed exactly as written.

## Verification

**[검증됨]** All template routes return 200 with valid HTML:
- `GET /` → 200 (Fleet Overview with stat cards + table)
- `GET /issues` → 200 (Issues with open/resolved split)
- `GET /standards` → 200 (Standards with brand compliance)
- `GET /blog/nonexistent` → 404 (custom 404 page)
- `GET /nope` → 404 (custom 404 page)
- Static files: `style.css` + `app.js` exist in `ops_dashboard/static/`

**근거:** `python -c` verification script passed all assertions.

## Known Stubs

None — all templates render real data from the database.

## Threat Flags

None — no new network endpoints, auth paths, or security surface introduced.

## Self-Check: PASSED

- [✅] All 9 files exist on disk — verified via `ls`
- [✅] Commit c61adf1ca exists — verified via `git log`
- [✅] Verification script passed all assertions — 200 on `/`, `/issues`, `/standards`; 404 on `/blog/nonexistent` and `/nope`; static files present
