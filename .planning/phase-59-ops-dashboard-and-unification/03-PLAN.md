---
phase: 59-ops-dashboard-and-unification
plan: 03
type: execute
wave: 1
depends_on:
  - 59-02
files_modified:
  - ops_dashboard/templates/base.html
  - ops_dashboard/templates/index.html
  - ops_dashboard/templates/blog.html
  - ops_dashboard/templates/issues.html
  - ops_dashboard/templates/standards.html
  - ops_dashboard/templates/404.html
  - ops_dashboard/static/style.css
  - ops_dashboard/static/app.js
autonomous: true
requirements:
  - dashboard-responsive-ui
must_haves:
  truths:
    - "Dashboard renders on mobile (320px) and desktop (1920px)"
    - "Index page shows fleet matrix with brand × status"
    - "Blog detail page shows health checks + issues + publish history"
    - "Issues page shows gsd_status × current_detection matrix"
    - "Standards page shows compliance rates per brand"
    - "Mobile card view collapses tables into cards"
  artifacts:
    - path: "ops_dashboard/templates/base.html"
      provides: "Responsive layout with nav + mobile card view"
    - path: "ops_dashboard/templates/index.html"
      provides: "Fleet summary dashboard"
    - path: "ops_dashboard/templates/blog.html"
      provides: "Per-blog detail view"
    - path: "ops_dashboard/templates/issues.html"
      provides: "Known issues matrix"
    - path: "ops_dashboard/templates/standards.html"
      provides: "Standard compliance matrix"
    - path: "ops_dashboard/static/style.css"
      provides: "Responsive CSS with mobile breakpoints"
    - path: "ops_dashboard/static/app.js"
      provides: "Mobile card view toggle + auto-refresh"
  key_links:
    - from: "ops_dashboard/templates/*.html"
      to: "ops_dashboard/app.py"
      via: "Jinja2 template context variables"
      pattern: "render_template"
---

<objective>
Create responsive HTML templates and minimal CSS/JS for the ops dashboard UI.

Purpose: The Flask app (Plan 02) serves data — these templates make it visually usable on mobile and desktop.
Output: 6 HTML templates + 1 CSS file + 1 JS file
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@ops_dashboard/app.py
@.planning/phase-59-ops-dashboard-and-unification/CONTEXT.md

<interfaces>
<!-- Template context variables from app.py routes -->

From app.py index route:
```python
# render_template('index.html', blogs=blogs, attention=attention, check_summary=summary)
# blogs: list[dict] — all blogs from blog_lifecycle
# attention: dict — {fail_checks: [...], open_issues: [...], stale_blogs: [...]}
# check_summary: dict — {total, pass, fail, unknown}
```

From app.py blog detail route:
```python
# render_template('blog.html', blog=blog_detail)
# blog_detail: dict — {blog: {...}, checks: [...], issues: [...]}
```

From app.py issues route:
```python
# render_template('issues.html', issues=issues)
# issues: list[dict] — all known_issues
```

From app.py standards route:
```python
# render_template('standards.html', standards=standards, brand_compliance=brand_compliance)
# standards: list[dict] — check_results grouped by check_name
# brand_compliance: dict — {brand: {pass: N, fail: N, total: N}}
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Base template + index + blog detail templates</name>
  <files>
    ops_dashboard/templates/base.html,
    ops_dashboard/templates/index.html,
    ops_dashboard/templates/blog.html,
    ops_dashboard/static/style.css,
    ops_dashboard/static/app.js
  </files>
  <action>
Create the core responsive templates.

**ops_dashboard/templates/base.html:**
- Responsive HTML5 skeleton with `<meta name="viewport" content="width=device-width, initial-scale=1.0">`
- CSS link to `/static/style.css`
- Navigation bar: brand logo/title + links to /, /issues, /standards + "Run Checks" button (POST /api/run-checks)
- `{% block content %}{% endblock %}` for child templates
- Mobile: nav collapses to hamburger menu
- Footer: last check timestamp + "Powered by ops_dashboard"

**ops_dashboard/templates/index.html:**
Extends base.html. Sections:
1. **Fleet Summary Cards** (top row): Total blogs, Active, Stale, Failed checks, Open issues — each as a metric card
2. **Attention Needed** section: Cards for each fail_check, open_issue, stale_blog — sorted by severity
3. **Brand Matrix** table: rows=brands (cap, cuap, etap, rap, seap, stap, tap), columns=status (active, inactive, stale, unknown) — cell counts
4. **Recent Checks** table: last 20 check_results with blog_id, check_name, status (color-coded), detail, checked_at
- Mobile: tables collapse to card lists via CSS `.mobile-card-view` class
- Data: uses `blogs`, `attention`, `check_summary` template variables

**ops_dashboard/templates/blog.html:**
Extends base.html. Sections:
1. **Blog Header**: blog_id, brand, domain, theme, pipeline_path, lifecycle_status (color badge)
2. **Health Checks** table: check_name, status (pass=fail=unknown badges), detail, checked_at — last 50 results
3. **Related Issues** table: issue_id, category, symptom, gsd_status — from known_issues matching this blog
4. **Action Buttons**: "Run Checks for This Blog" (POST /api/run-checks?blog_id=xxx)
- Mobile: check results as cards with status badge on top

**ops_dashboard/static/style.css:**
- CSS variables for colors: `--pass: #22c55e`, `--fail: #ef4444`, `--unknown: #eab308`, `--stale: #f97316`
- Mobile breakpoint: `@media (max-width: 768px)` — tables become `.mobile-card-view` cards
- Card styles: border, padding, shadow, rounded corners
- Status badges: colored pill badges for pass/fail/unknown
- Table styles: striped rows, hover, responsive overflow
- Nav: flexbox, sticky top, z-index
- Metric cards: grid layout (2-col mobile, 4-col desktop)
- Button styles: primary (blue), danger (red), subtle (gray)

**ops_dashboard/static/app.js:**
- Mobile card view toggle: if screen <768px, auto-add `.mobile-card-view` class to tables
- "Run Checks" button: POST /api/run-checks via fetch(), show loading spinner, refresh page on completion
- Auto-refresh: optional `?auto_refresh=30` query param refreshes page every 30 seconds
- No external dependencies (vanilla JS)
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && python -c "
import os
templates = [
    'ops_dashboard/templates/base.html',
    'ops_dashboard/templates/index.html',
    'ops_dashboard/templates/blog.html',
]
for t in templates:
    assert os.path.exists(t), f'Missing: {t}'
    content = open(t).read()
    assert len(content) > 100, f'{t} too short ({len(content)} bytes)'

css = 'ops_dashboard/static/style.css'
js = 'ops_dashboard/static/app.js'
assert os.path.exists(css), f'Missing: {css}'
assert os.path.exists(js), f'Missing: {js}'

# Check CSS has mobile breakpoint
css_content = open(css).read()
assert '@media' in css_content, 'No mobile breakpoints in CSS'
assert '--pass' in css_content or 'pass' in css_content, 'No pass color variable'

# Check JS has fetch for run-checks
js_content = open(js).read()
assert 'fetch' in js_content or 'XMLHttpRequest' in js_content, 'No fetch/XHR in JS'

print('PASS: templates + static files exist and have content')
"</automated>
  </verify>
  <done>
    - base.html provides responsive layout with nav
    - index.html shows fleet summary with metric cards + brand matrix
    - blog.html shows per-blog detail with health checks + issues
    - CSS has mobile breakpoints (768px) with card view
    - JS has run-checks button handler + auto-refresh
    - All templates handle empty data gracefully
  </done>
</task>

<task type="auto">
  <name>Task 2: Issues + standards templates + 404 page</name>
  <files>
    ops_dashboard/templates/issues.html,
    ops_dashboard/templates/standards.html,
    ops_dashboard/templates/404.html
  </files>
  <action>
Create the remaining templates for issues view, standards compliance, and error page.

**ops_dashboard/templates/issues.html:**
Extends base.html. Sections:
1. **Issue Stats**: Total issues, Open, Resolved, Auto-detectable, Manual-only — metric cards
2. **Issues Matrix**: Table with columns: issue_id, category, symptom, gsd_status (badge), auto_detectable (yes/no), current_detection, blog_ids
3. **Filter controls**: Filter by category (dropdown), filter by gsd_status (dropdown), search by symptom (text input)
4. Mobile: issue cards with status badge + expandable detail
- Data: uses `issues` template variable (list of known_issues dicts)

**ops_dashboard/templates/standards.html:**
Extends base.html. Sections:
1. **Compliance Overview**: Total rules, Overall pass rate (%) — metric card
2. **Brand Compliance Matrix**: Table with rows=brands, columns=rule_ids (R01-R12), cells=pass count / total count (percentage)
3. **Recent Standard Violations**: Last 20 fail check_results for R-rules, with blog_id + detail
4. **Rule Reference**: Collapsible section listing all 12 rules with description + severity
- Data: uses `standards` and `brand_compliance` template variables

**ops_dashboard/templates/404.html:**
Extends base.html. Simple "Page not found" message with link back to /.
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && python -c "
import os
templates = [
    'ops_dashboard/templates/issues.html',
    'ops_dashboard/templates/standards.html',
    'ops_dashboard/templates/404.html',
]
for t in templates:
    assert os.path.exists(t), f'Missing: {t}'
    content = open(t).read()
    assert len(content) > 100, f'{t} too short'
    assert 'extends' in content or 'block' in content, f'{t} missing Jinja2 blocks'

# Count all templates
all_templates = os.listdir('ops_dashboard/templates')
print(f'Templates: {len(all_templates)} files')
assert len(all_templates) >= 6, f'Expected 6+ templates, got {len(all_templates)}'

print('PASS: remaining templates complete')
"</automated>
  </verify>
  <done>
    - issues.html shows gsd_status × current_detection matrix with filters
    - standards.html shows brand × rule compliance matrix
    - 404.html provides friendly error page
    - All 6 templates extend base.html
    - All templates handle empty/missing data gracefully
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser → Flask templates | Template injection via Jinja2 auto-escaping |
| Template data → HTML output | XSS prevention via Jinja2 auto-escaping (default) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-59-08 | Tampering | Template injection | mitigate | Jinja2 auto-escaping enabled by default, never use `|safe` on user data |
| T-59-09 | Information Disclosure | Blog detail page | accept | Shows domain/path info — required for ops, behind Basic Auth |
</threat_model>

<verification>
- All 6 HTML templates exist and are valid Jinja2
- CSS file has mobile breakpoint at 768px
- JS file handles run-checks button and auto-refresh
- Templates render without errors when given empty data
- Mobile view collapses tables to cards
</verification>

<success_criteria>
- Complete responsive UI for all 4 human pages
- Mobile-first design with card view at 768px breakpoint
- Color-coded status badges (pass/fail/unknown)
- Run checks button triggers API and refreshes
- All templates handle edge cases (empty DB, missing data)
</success_criteria>

<output>
Create `.planning/phases/59-ops-dashboard-and-unification/59-03-SUMMARY.md` when done
</output>
