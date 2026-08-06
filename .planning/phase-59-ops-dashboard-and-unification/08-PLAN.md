---
phase: 59-ops-dashboard-and-unification
plan: 08
type: execute
wave: 3
depends_on:
  - 59-07
files_modified:
  - config/blogs.d/stap.yaml
autonomous: false
requirements:
  - blowfish-congo-migration
  - blowfish-duplicate-cleanup
must_haves:
  truths:
    - "stock-hugo uses Blowfish theme instead of Congo"
    - "stock-hugo Hugo build passes with 0 errors"
    - "Duplicate theme files across blogs are removed"
    - "After-state disk usage is lower than before"
  artifacts:
    - path: "config/blogs.d/stap.yaml"
      provides: "Updated theme field for stock-hugo"
  key_links:
    - from: "config/blogs.d/stap.yaml"
      to: "stock-hugo site_path"
      via: "theme field changes from Congo to Blowfish"
      pattern: "theme.*blowfish"
---

<objective>
Migrate stock-hugo from Congo to Blowfish and remove duplicate theme files across all blogs.

Purpose: stock-hugo is the last non-Blowfish blog. After migration, all blogs use Blowfish. Duplicate theme files waste disk space and create maintenance burden.
Output: Updated stap.yaml + disk usage reduction
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@config/blogs.d/stap.yaml
@shared/themes/blowfish-standard/
@.planning/phase-59-ops-dashboard-and-unification/CONTEXT.md

<interfaces>
<!-- From stap.yaml — stock-hugo entry -->
```yaml
- id: stock-hugo
  status: active
  theme: Congo            # ← CHANGE TO: blowfish
  site_path: /Users/twinssn/Projects/STAP/stock-hugo
  domain: stock.informationhot.kr
```
</interfaces>
</context>

<tasks>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 1: Migrate stock-hugo Congo → Blowfish + remove duplicate themes</name>
  <what-built>
stock-hugo theme changed from Congo to Blowfish:
1. stap.yaml: theme field changed to 'blowfish'
2. Blowfish theme installed at stock-hugo/themes/blowfish/
3. Standard overrides applied from shared/themes/blowfish-standard/
4. Congo theme files removed from stock-hugo/themes/cairo/
5. Hugo build tested with 0 errors
6. Duplicate theme files across all Blowfish blogs documented for removal
  </what-built>
  <how-to-verify>
1. Check stap.yaml: `grep 'stock-hugo' -A5 config/blogs.d/stap.yaml | grep theme`
   Expected: `theme: blowfish`

2. Verify Blowfish theme: `ls /Users/twinssn/Projects/STAP/stock-hugo/themes/blowfish/`

3. Verify Congo removed: `ls /Users/twinssn/Projects/STAP/stock-hugo/themes/cairo/ 2>&1`
   Expected: "No such file or directory"

4. Hugo build:
   ```bash
   cd /Users/twinssn/Projects/STAP/stock-hugo && HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify 2>&1 | tail -5
   ```
   Expected: Build successful, 0 errors

5. Verify all themes are now Blowfish:
   ```bash
   grep -r 'theme:' config/blogs.d/*.yaml | grep -v blowfish | grep -v '#'
   ```
   Expected: No output (all blogs use blowfish)

6. Disk usage comparison:
   ```bash
   # After state
   du -sh /Users/twinssn/Projects/5000/themes/ 2>/dev/null
   du -sh /Users/twinssn/Projects/*/themes/ 2>/dev/null | sort -rh | head -10
   ```
   Compare with before-state from Plan 06 audit
  </how-to-verify>
  <resume-signal>Type "approved" if Hugo build passes and stock-hugo renders correctly with Blowfish</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Theme change → Hugo build | Congo-specific features may not exist in Blowfish |
| Duplicate removal → blog rendering | Removing files that blogs depend on |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-59-19 | Denial of Service | Hugo build failure | mitigate | Test build on stock-hugo before any bulk removal |
| T-59-20 | Tampering | Duplicate file removal | mitigate | Only remove files confirmed identical across blogs |
</threat_model>

<verification>
- stock-hugo theme field = 'blowfish' in stap.yaml
- Congo theme directory removed
- Hugo build passes with 0 errors
- All blogs now use blowfish theme (grep confirms)
- Disk usage reduction documented
</verification>

<success_criteria>
- stock-hugo successfully migrated to Blowfish
- All 75+ blogs use Blowfish theme
- Hugo build produces correct output for stock-hugo
- Disk usage before/after comparison documented
</success_criteria>

<output>
Create `.planning/phases/59-ops-dashboard-and-unification/59-08-SUMMARY.md` when done
</output>
