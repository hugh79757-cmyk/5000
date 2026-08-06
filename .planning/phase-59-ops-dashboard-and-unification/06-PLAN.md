---
phase: 59-ops-dashboard-and-unification
plan: 06
type: execute
wave: 3
depends_on: []
files_modified:
  - shared/themes/README.md
  - shared/themes/blowfish-standard/
autonomous: true
requirements:
  - blowfish-theme-audit
  - blowfish-shared-structure
must_haves:
  truths:
    - "All blog layout overrides are inventoried with file paths"
    - "Shared Blowfish standard source structure is defined"
    - "Before/after disk usage is measured"
  artifacts:
    - path: "shared/themes/README.md"
      provides: "Theme standard documentation + override inventory"
    - path: "shared/themes/blowfish-standard/"
      provides: "Shared Blowfish override source directory"
  key_links:
    - from: "shared/themes/blowfish-standard/"
      to: "pipelines/*/site_path"
      via: "symlink or copy from shared source"
      pattern: "layouts/"
---

<objective>
Audit all blog layout overrides and design the shared Blowfish theme structure.

Purpose: Before migrating themes, understand the current state of overrides across all 75+ blogs and define the single source of truth for shared overrides.
Output: Audit report + shared theme directory structure
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phase-59-ops-dashboard-and-unification/CONTEXT.md
@.planning/phase-59-ops-dashboard-and-unification/RESEARCH.md

<interfaces>
<!-- From CONTEXT.md §4-3 — allowed override files -->
Allowed Blowfish overrides (5 types only):
1. layouts/_default/single.html
2. layouts/partials/extend-head.html
3. layouts/partials/extend_head.html
4. layouts/partials/adsense/*.html
5. assets/css/custom.css
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Audit all blog layout overrides + measure disk usage</name>
  <files>shared/themes/README.md</files>
  <action>
Perform a comprehensive audit of all blog layout overrides and measure disk usage.

**Step 1: Disk usage measurement (before)**
```bash
# Measure total themes directory size
du -sh /Users/twinssn/Projects/5000/themes/ 2>/dev/null
# Measure each blog's layouts/ directory
for site in /Users/twinssn/Projects/*/; do
  if [ -d "$site/layouts" ]; then
    echo "$(du -sh "$site/layouts" 2>/dev/null) — $site"
  fi
done
```

**Step 2: Override inventory**
For each blog with a `site_path` in YAML:
- List all files under `{site_path}/layouts/` and `{site_path}/assets/css/`
- Classify each file as "allowed" (5 types from 지침서 §1) or "unauthorized"
- Record: blog_id, file_path, allowed/unauthorized, file_size

**Step 3: Find non-Blowfish themes**
- From blog_lifecycle: blogs where theme != 'blowfish'
- Expected: hotissue-hugo (PaperMod), stock-hugo (Congo)
- List their full layout override inventory

**Step 4: Find duplicate overrides**
- Compare override files across blogs with the same content
- Identify which overrides are identical (can be shared) vs unique (must stay per-blog)

**Step 5: Write audit report to shared/themes/README.md**
```markdown
# Theme Override Audit Report

## Disk Usage (Before)
- themes/ directory: {X} MB
- Total blog layouts/: {Y} MB across {N} blogs

## Override Inventory
| Blog | File | Allowed | Size |
|------|------|---------|------|

## Non-Blowfish Themes
| Blog | Theme | Overrides |
|------|-------|-----------|

## Duplicate Overrides (Candidates for Sharing)
| File Pattern | Blogs Using It | Identical? |
|-------------|----------------|------------|

## Unauthorized Overrides
| Blog | File | Action Needed |
|------|------|---------------|

## Recommended Shared Structure
(See Task 2)
```
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && python -c "
import os
assert os.path.exists('shared/themes/README.md'), 'README.md missing'
content = open('shared/themes/README.md').read()
assert 'Disk Usage' in content, 'Missing disk usage section'
assert 'Override Inventory' in content, 'Missing override inventory'
assert len(content) > 500, f'README too short ({len(content)} bytes)'
print('PASS: audit report exists')
" && echo "--- Audit Summary ---" && du -sh /Users/twinssn/Projects/5000/themes/ 2>/dev/null && find /Users/twinssn/Projects/*/layouts -name '*.html' 2>/dev/null | wc -l</automated>
  </verify>
  <done>
    - Audit report documents all override files across all blogs
    - Disk usage measured (before state)
    - Non-Blowfish themes identified (hotissue-hugo, stock-hugo)
    - Duplicate overrides identified for sharing candidates
    - Unauthorized overrides flagged
  </done>
</task>

<task type="auto">
  <name>Task 2: Design shared Blowfish standard directory structure</name>
  <files>shared/themes/blowfish-standard/</files>
  <action>
Create the shared Blowfish standard override directory that all Blowfish blogs will reference.

**shared/themes/blowfish-standard/** directory structure:
```
shared/themes/blowfish-standard/
├── layouts/
│   ├── _default/
│   │   └── single.html          # H2 split + prose wrapper (from ADSENSE §3-6)
│   └── partials/
│       ├── extend-head.html      # adsbygoogle.js loader (from ADSENSE §3-2)
│       ├── extend_head.html      # GA4 + mobile correction CSS (from 지침서 §3.3)
│       └── adsense/
│           ├── top.html          # Top ad slot (from ADSENSE §3-4)
│           └── in-article.html   # In-article ad slot (from ADSENSE §3-5)
└── assets/
    └── css/
        └── custom.css            # unfilled removal + dark mode (from ADSENSE §3-8)
```

**Implementation:**
1. Create the directory structure
2. For each file, copy the "golden" version from the best existing blog (e.g., kitchen-hugo or laptop-hugo which were fixed in Phase 52)
3. Add a `README.md` in each directory explaining the file's purpose and the standard it implements
4. Document how blogs should reference these files (symlink, copy, or Hugo module)

**Reference sources for golden versions:**
- `single.html`: Read from kitchen-hugo or laptop-hugo (Phase 52 Wave 1-4 fixed these)
- `extend-head.html`: Read from a blog that was fixed in Phase 52
- `adsense/top.html`: Read from ADSENSE-GUIDE.md §3-4
- `adsense/in-article.html`: Read from ADSENSE-GUIDE.md §3-5
- `custom.css`: Read from a blog with proper custom.css

**Important:**
- These are the REFERENCE implementations, not yet deployed to blogs
- Deployment to individual blogs happens in Plan 07 (PaperMod migration) and subsequent plans
- The shared directory is the single source of truth going forward
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && find shared/themes/blowfish-standard -type f | sort && echo "---" && python -c "
import os
base = 'shared/themes/blowfish-standard'
required = [
    'layouts/_default/single.html',
    'layouts/partials/extend-head.html',
    'layouts/partials/extend_head.html',
    'layouts/partials/adsense/top.html',
    'layouts/partials/adsense/in-article.html',
    'assets/css/custom.css',
]
for f in required:
    path = os.path.join(base, f)
    assert os.path.exists(path), f'Missing: {f}'
    size = os.path.getsize(path)
    assert size > 50, f'{f} too short ({size} bytes)'
print('PASS: shared Blowfish standard directory complete')
"</automated>
  </verify>
  <done>
    - shared/themes/blowfish-standard/ directory exists with all 6 files
    - Each file contains the standard implementation from ADSENSE-GUIDE.md
    - README.md documents the directory purpose and usage
    - Golden versions are copied from best existing blogs
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Shared theme source → individual blogs | Theme files affect Hugo build output — incorrect file breaks blog rendering |
| Audit reads → blog file system | Reading layouts/ from all blog directories |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-59-15 | Tampering | Shared theme files | mitigate | Shared directory is read-only reference; blogs copy/symlink |
| T-59-16 | Denial of Service | Hugo build failure | mitigate | Test Hugo build on one blog before bulk deployment |
</threat_model>

<verification>
- Audit report covers all blogs with override inventory
- Disk usage measured before state
- Shared Blowfish standard directory has all 6 required files
- Each shared file contains valid Hugo template code
- Non-Blowfish themes identified for migration
</verification>

<success_criteria>
- Complete inventory of all blog layout overrides
- Shared Blowfish standard source is ready for deployment
- Disk usage baseline established for before/after comparison
- Unauthorized overrides identified for cleanup
</success_criteria>

<output>
Create `.planning/phases/59-ops-dashboard-and-unification/59-06-SUMMARY.md` when done
</output>
