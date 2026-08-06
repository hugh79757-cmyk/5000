# Phase 59 Plan 08: stock-hugo Congo→Blowfish Migration & Duplicate Theme Cleanup Summary

## One-Liner
Migrated stock-hugo from Congo to Blowfish theme with param-driven AdSense injection, removed ~840MB of duplicate Blowfish theme copies across 3 repos.

## Tasks

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | Migrate stock-hugo theme: Congo → Blowfish | ✅ Done | STAP@b92293f, 5000@5d9e8df |
| 2 | Remove duplicate Blowfish theme copies (~840MB) | ✅ Done | Filesystem only (gitignored) |

## Key Changes

### Task 1: stock-hugo Theme Migration

**Config changes:**
- `config/blogs.d/stap.yaml`: `theme: congo` → `theme: blowfish`
- `config/_default/hugo.toml`: `theme = "congo"` → `theme = "blowfish"`
- `config/_default/module.toml`: Removed Congo module import (uses themesDir directly)
- `config/_default/params.toml`: Added `[advertisement]` section with adsense/topSlot/inArticleSlot params
- Removed `go.mod`/`go.sum` (no Hugo modules needed — themesDir points to shared-themes)

**Layout changes:**
- Replaced `layouts/single.html` (Congo) with `layouts/_default/single.html` (Blowfish standard + TradingView widget integration)
- Added `layouts/partials/adsense/top.html` and `in-article.html` from blowfish-standard
- Updated `layouts/partials/extend-head.html`: param-driven AdSense loader (`site.Params.advertisement.adsense`) + stock-specific GA4 tag
- Removed Congo-specific overrides: `layouts/_partials/functions/warnings.html`, `layouts/_partials/article-link.html`

**AdSense Publisher ID:** ca-pub-6677996696534146 (informationhot family — correct for stock.informationhot.kr)

**Hugo build verified:** 2071 pages, 0 errors, 657ms

### Task 2: Duplicate Theme Cleanup

| Location | Before | After | Savings |
|----------|--------|-------|---------|
| STAP/themes/ | 154M (blowfish + congo) | 0B (symlink) | 154M |
| TAP/travel4-hugo/themes/ | 610M (blowfish copy) | 0B (symlink) | 610M |
| rotcha-blog/themes/ | 76M (blowfish copy) | 0B (symlink) | 76M |
| **Total** | **840M** | **0B** | **~840M** |

All symlinks point to `/Users/twinssn/Projects/shared-themes/blowfish`. Hugo builds verified for travel4-hugo and rotcha-blog.

## Deviations from Plan

### Rule 3 - Blocking Issue: Hugo module cache contamination
- **Found during:** Task 1, Hugo build verification
- **Issue:** `go.mod` referenced Congo module, Hugo downloaded and cached Congo templates. Even after changing theme to blowfish, cached Congo templates caused `SingleAuthor` template errors.
- **Fix:** Removed `go.mod`/`go.sum` entirely, cleared module imports from `module.toml`. stock-hugo uses `themesDir` directly (same pattern as finance-hugo).
- **Files modified:** go.mod, go.sum (deleted), module.toml
- **Commit:** STAP@b92293f

### Rule 2 - Missing Functionality: SingleAuthor template definition
- **Found during:** Task 1, Hugo build verification
- **Issue:** blowfish-standard `single.html` uses `{{ template "SingleAuthor" . }}` but doesn't define the `SingleAuthor` block. Base Blowfish theme defines it in its own single.html, which gets overridden.
- **Fix:** Added `{{ define "SingleAuthor" }}` block to stock-hugo's single.html (copied from finance-hugo's working template).
- **Files modified:** layouts/_default/single.html
- **Commit:** STAP@b92293f

## Known Stubs

None — all AdSense params wired, all layouts functional.

## Threat Flags

None — no new security surface introduced. AdSense Publisher ID unchanged.

## Self-Check

- [x] `config/blogs.d/stap.yaml` — stock-hugo theme is blowfish (verified via Python)
- [x] Hugo build passes with 0 errors (2071 pages)
- [x] travel4-hugo build passes with symlink
- [x] rotcha-blog build passes with symlink
- [x] ~840MB disk savings confirmed
- [x] COMMIT: STAP@b92293f (12 files changed)
- [x] COMMIT: 5000@5d9e8df (stap.yaml)

## Self-Check: PASSED
