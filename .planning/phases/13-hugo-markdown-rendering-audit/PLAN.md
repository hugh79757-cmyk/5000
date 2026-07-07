# Phase 13 Plan: Hugo Markdown Rendering Audit & Fix — Cross-Project

## Phase Overview
- **Phase**: 13
- **Title**: Hugo Markdown Rendering Audit & Fix — Cross-Project
- **Mode**: mvp (vertical slices per pipeline)
- **Estimated Duration**: 2 days
- **Dependencies**: Phase 10 (Blowfish shortcodes), Phase 12 (content enrichment)

---

## Wave 1: Inventory & Baseline Scan (Parallel)

### Task 13-01: Discover All Active Hugo Sites
- **Owner**: orchestrator
- **Action**: Parse all `config/blogs.d/*.yaml` for `platform: hugo` and `status: active`
- **Output**: `inventory.json` with site_id, pipeline, theme, site_path, cf_project, domain
- **Verification**: Count matches manual inventory (20 active)

### Task 13-02: Baseline Rendering Scan
- **Owner**: orchestrator (parallel subagents per site)
- **Action**: For each site:
  1. Build: `hugo --gc --minify -s {site_path}`
  2. Scan `public/**/*.html` for visible raw markdown in `<article>`:
     - `**text**` (bold)
     - `~~text~~` (strike)
     - `*text*` (italic, word boundaries)
     - `` `text` `` (inline code)
  3. Exclude `<script>`, `<meta>`, `<style>`, comments
- **Output**: `baseline-findings.csv` with columns: site, file, issue_type, count, context_snippet
- **Verification**: Total issues > 0 confirms problem exists

---

## Wave 2: Pipeline-Level Fix Verification (Parallel)

### Task 13-03: Verify `hugo_writer.py` Global Conversion
- **Owner**: orchestrator
- **Action**: 
  1. Confirm `_convert_inline_md_to_html()` called at end of `_write_hugo_post()` for ALL themes (not just Blowfish)
  2. Verify function handles: `**`, `~~`, `*`, `` ` `` with code block protection
  3. Run pipeline dry-run for each pipeline (travel, stock, curation) to generate test content
- **Verification**: Generated test markdown has zero raw inline markdown in HTML output

### Task 13-04: Extend Conversion to All HTML Contexts
- **Owner**: orchestrator
- **Action**: Audit `hugo_writer.py` shortcode functions for HTML wrapper creation:
  - `_apply_figure_shortcode()` → `<figure>`, `<figcaption>`
  - `_apply_gallery_shortcode()` → gallery HTML
  - `_apply_accordion_shortcode()` → accordion HTML
  - `_apply_chart_shortcode()` → chart HTML
  - Any other HTML-generating functions
- **Fix**: Ensure `_convert_inline_md_to_html()` runs AFTER all shortcode transforms
- **Verification**: All shortcode-generated HTML content has converted inline markdown

---

## Wave 3: Legacy Content Remediation (Parallel)

### Task 13-05: Remediate Existing Markdown Files
- **Owner**: orchestrator (parallel per site)
- **Action**: For each site's `content/posts/**/index.md`:
  1. Split frontmatter / body
  2. Apply `_convert_inline_md_to_html()` to body (with code block protection)
  3. Write back with `.bak` backup
- **Verification**: Post-remediation scan shows zero raw markdown in rebuilt HTML

### Task 13-06: Clean Stale Public Artifacts
- **Owner**: orchestrator
- **Action**: Remove `public/` directories for all sites before rebuild
- **Verification**: Fresh build from clean state

---

## Wave 4: Rebuild & Deploy (Parallel)

### Task 13-07: Full Rebuild All Sites
- **Owner**: orchestrator (parallel per site)
- **Action**: `hugo --gc --minify -s {site_path}` for all 20 sites
- **Verification**: All builds succeed, zero visible raw markdown in final HTML

### Task 13-08: Cloudflare Pages Redeploy
- **Owner**: orchestrator (parallel per site)
- **Action**: `npx wrangler pages deploy --project-name {cf_project} {site_path}/public/`
- **Verification**: All deployments succeed, preview URLs accessible

---

## Wave 5: Live Verification

### Task 13-09: Live Site Sampling
- **Owner**: orchestrator
- **Action**: For each site, fetch 3-5 recent posts via live domain:
  1. Parse `<article>` content
  2. Confirm zero visible raw markdown
  3. Verify specific patterns: bold in lead, bold in figcaption, strike in accordion
- **Output**: `live-verification-report.md` with PASS/FAIL per site

### Task 13-10: Regression Test — New Content Generation
- **Owner**: orchestrator
- **Action**: Trigger one dry-run publish per pipeline (travel, stock, curation)
- **Verification**: Newly generated content renders cleanly on live preview URLs

---

## Deliverables

| File | Description |
|------|-------------|
| `inventory.json` | Complete Hugo site inventory |
| `baseline-findings.csv` | Pre-fix issue baseline |
| `remediation-report.md` | Files modified, issues fixed |
| `rebuild-log.txt` | Build output for all sites |
| `deploy-log.txt` | CF Pages deployment results |
| `live-verification-report.md` | Final PASS/FAIL per site |
| `regression-test-results.md` | New content pipeline verification |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Hugo build failures | Build in isolation per site; rollback `.bak` files if needed |
| CF Pages deploy timeout | Deploy in batches of 5; monitor dashboard |
| Theme-specific shortcode differences | Test each theme (Blowfish, Congo) separately |
| Code block conversion breaking examples | Regex skips ``` ``` blocks; verify with test cases |
| Duplicate content between TAP/5000 | Focus on 5000 project; TAP is separate |

---

## Exit Criteria

- [ ] All 20 active Hugo sites pass baseline scan (zero visible raw markdown)
- [ ] Pipeline-level fix verified for travel, stock, curation pipelines
- [ ] All legacy `content/posts/**/index.md` files remediated
- [ ] All sites rebuild successfully from clean state
- [ ] All 20 sites redeployed to Cloudflare Pages
- [ ] Live verification: 100% PASS on sampled posts
- [ ] Regression test: new content generates cleanly

---

## Next Phase

Upon completion, proceed to **Phase 14: Cross-Project Content Quality Dashboard** — unified monitoring of markdown rendering health, content length, and engagement metrics across all Hugo sites.