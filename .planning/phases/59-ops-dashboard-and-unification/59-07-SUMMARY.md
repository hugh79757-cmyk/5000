---
phase: 59
plan: 07
subsystem: hotissue-hugo
tags: [theme-migration, blowfish, papermod]
dependency:
  requires: []
  provides: [hotissue-blowfish]
  affects: [hotissue-hugo]
tech-stack:
  added: [blowfish-theme]
  patterns: [standard-overrides]
key-files:
  created:
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/_default/single.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/extend-head.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/extend_head.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/adsense/top.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/adsense/in-article.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/assets/css/custom.css
  modified:
    - /Users/twinssn/Projects/5000/config/blogs.d/cap.yaml
    - /Users/twinssn/Projects/CAP/hotissue-hugo/hugo.toml
  deleted:
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/_default/archives.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/_default/baseof.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/404.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/index.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/adsense/adsense-loader.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/adsense/auto-display.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/adsense/lazy-ad.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/adsense/leaderboard.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/adsense_lazy.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/cover.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/extend_footer.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/head_preload.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/related.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/related_posts.html
    - /Users/twinssn/Projects/CAP/hotissue-hugo/layouts/partials/share_icons.html
decisions:
  - "Used Blowfish standard overrides from shared/themes/blowfish-standard/"
  - "Added SingleAuthor template definition to fix Hugo build error"
  - "Kept Pretendard font and GA4 tracking in extend_head.html"
metrics:
  duration: "15 minutes"
  completed: "2026-08-06T05:12:00Z"
  tasks: 4
  files: 23
---

# Phase 59 Plan 07: hotissue-hugo PaperMod to Blowfish Migration Summary

## One-liner
Migrated hotissue-hugo from PaperMod to Blowfish theme with standard overrides, fixing Hugo build error by adding missing SingleAuthor template definition.

## What Was Done

### Task 1: Update cap.yaml theme field
- Changed `theme: PaperMod` to `theme: Blowfish` in `config/blogs.d/cap.yaml`
- Committed: `d6ce85165`

### Task 2: Copy standard Blowfish layouts
- Copied from `shared/themes/blowfish-standard/` to hotissue-hugo:
  - `layouts/_default/single.html` (H2 split injection)
  - `layouts/partials/extend-head.html` (AdSense loader)
  - `layouts/partials/extend_head.html` (GA4 + mobile CSS)
  - `layouts/partials/adsense/top.html` (Top ad slot)
  - `layouts/partials/adsense/in-article.html` (In-article ad slot)
  - `assets/css/custom.css` (Ad styling + dark mode)
- Removed 15 PaperMod-specific override files
- Backup created in `layouts_backup_20260806/`
- Committed: `f8c186ed6`

### Task 3: Update hugo.toml for Blowfish
- Changed `theme = "PaperMod"` to `theme = "blowfish"`
- Added Blowfish-specific params:
  - `[params.homepage]` layout = "profile"
  - `[params.article]` showDate, showAuthor, showBreadcrumbs
  - `[params.search]` enable = true
  - `[taxonomies]` tag = "tags", category = "categories"
- Committed: `b3fcdb1`

### Task 4: Verify Hugo build
- Initial build failed: `no such template "SingleAuthor"`
- Fixed by adding SingleAuthor template definition to single.html
- Final build: 2125 pages, 0 errors, 19363ms
- Committed: `e55626b`

## Verification

### Theme field verification
```bash
$ python -c "import yaml; ..."
hotissue-hugo theme: Blowfish
PASS: hotissue migration
```

### Hugo build verification
```bash
$ HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify
Total in 19363 ms
```

### Disk usage
- Before: 81M (PaperMod)
- After: 100M (Blowfish)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Added SingleAuthor template definition**
- **Found during:** Task 4 (Hugo build verification)
- **Issue:** Standard single.html template referenced `{{ template "SingleAuthor" . }}` but template was not defined
- **Fix:** Added SingleAuthor template definition from Blowfish theme to single.html
- **Files modified:** `/Users/twinssn/Projects/CAP/hotissue-hugo/layouts/_default/single.html`
- **Commit:** `e55626b`

## Known Stubs
None - all data sources are wired and functional.

## Threat Flags
None - no new security-relevant surface introduced.

## Self-Check: PASSED
- [✅] cap.yaml hotissue-hugo theme = "Blowfish" (verified via yaml.safe_load)
- [✅] Hugo build passes with 0 errors (2125 pages, 19363ms)
- [✅] Standard Blowfish layouts copied from shared/themes/blowfish-standard/
- [✅] PaperMod-specific overrides removed (15 files deleted)
- [✅] Backup created in layouts_backup_20260806/
