---
phase: 59-ops-dashboard-and-unification
plan: 07
type: execute
wave: 3
depends_on:
  - 59-06
files_modified:
  - config/blogs.d/cap.yaml
autonomous: false
requirements:
  - blowfish-papermod-migration
must_haves:
  truths:
    - "hotissue-hugo uses Blowfish theme instead of PaperMod"
    - "hotissue-hugo Hugo build passes with 0 errors"
    - "hotissue-hugo layout overrides match Blowfish standard"
    - "Before/after disk usage recorded"
  artifacts:
    - path: "config/blogs.d/cap.yaml"
      provides: "Updated theme field for hotissue-hugo"
  key_links:
    - from: "config/blogs.d/cap.yaml"
      to: "hotissue-hugo site_path"
      via: "theme field changes from PaperMod to Blowfish"
      pattern: "theme.*blowfish"
---

<objective>
Migrate hotissue-hugo from PaperMod to Blowfish theme and apply standard overrides.

Purpose: hotissue-hugo is the only PaperMod blog remaining. Migrating it to Blowfish unifies the theme to a single standard.
Output: Updated cap.yaml + Hugo build verification
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@config/blogs.d/cap.yaml
@shared/themes/blowfish-standard/
@.planning/phase-59-ops-dashboard-and-unification/CONTEXT.md

<interfaces>
<!-- From cap.yaml — hotissue-hugo entry -->
```yaml
- id: hotissue-hugo
  status: active
  theme: PaperMod          # ← CHANGE TO: blowfish
  site_path: /Users/twinssn/Projects/CAP/hotissue-hugo
  domain: hotissue.informationhot.kr
```

<!-- From shared/themes/blowfish-standard/ (Plan 06 output) -->
Shared Blowfish overrides:
- layouts/_default/single.html
- layouts/partials/extend-head.html
- layouts/partials/extend_head.html
- layouts/partials/adsense/top.html
- layouts/partials/adsense/in-article.html
- assets/css/custom.css
</interfaces>
</context>

<tasks>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 1: Migrate hotissue-hugo PaperMod → Blowfish</name>
  <what-built>
hotissue-hugo theme changed from PaperMod to Blowfish:
1. cap.yaml: theme field changed to 'blowfish'
2. Blowfish theme installed at hotissue-hugo/themes/blowfish/
3. Standard overrides applied from shared/themes/blowfish-standard/
4. PaperMod theme files removed from hotissue-hugo/themes/PaperMod/
5. Hugo build tested with 0 errors
  </what-built>
  <how-to-verify>
1. Check cap.yaml: `grep 'hotissue-hugo' -A5 config/blogs.d/cap.yaml | grep theme`
   Expected: `theme: blowfish`

2. Verify Blowfish theme exists: `ls /Users/twinssn/Projects/CAP/hotissue-hugo/themes/blowfish/`

3. Verify PaperMod removed: `ls /Users/twinssn/Projects/CAP/hotissue-hugo/themes/PaperMod/ 2>&1`
   Expected: "No such file or directory"

4. Verify Hugo build:
   ```bash
   cd /Users/twinssn/Projects/CAP/hotissue-hugo && HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify 2>&1 | tail -5
   ```
   Expected: Build successful, 0 errors

5. Verify overrides applied:
   ```bash
   ls /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/_default/single.html
   ls /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/extend-head.html
   ls /Users/twinssn/Projects/CAP/hotissue-hugo/assets/css/custom.css
   ```

6. Record disk usage:
   ```bash
   du -sh /Users/twinssn/Projects/CAP/hotissue-hugo/themes/
   ```
   Compare with before (PaperMod was ~1.1MB, Blowfish should be similar or smaller)
  </how-to-verify>
  <resume-signal>Type "approved" if Hugo build passes and blog renders correctly, or describe issues</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Theme change → Hugo build | Changing theme could break blog rendering |
| Override files → blog content | Incorrect overrides could break post layout |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-59-17 | Denial of Service | Hugo build failure | mitigate | Test build before deploying; rollback to PaperMod if fails |
| T-59-18 | Tampering | Override files | mitigate | Copy from shared/themes/blowfish-standard (verified source) |
</threat_model>

<verification>
- hotissue-hugo theme field = 'blowfish' in cap.yaml
- PaperMod theme directory removed
- Hugo build passes with 0 errors
- Standard overrides present (single.html, extend-head.html, custom.css)
- Disk usage recorded (before/after)
</verification>

<success_criteria>
- hotissue-hugo successfully migrated to Blowfish
- Hugo build produces correct output
- No visual regression on the blog
- Disk usage documented
</success_criteria>

<output>
Create `.planning/phases/59-ops-dashboard-and-unification/59-07-SUMMARY.md` when done
</output>
