---
phase: 59
plan: 06
subsystem: theme_standardization
tags: [blowfish, theme-audit, shared-structure, adsense]
requires: []
provides: [blowfish-standard, theme-audit-report]
affects: [shared/themes/]
tech-stack:
  added: []
  patterns: [shared-source, symlink-migration, standard-override]
key-files:
  created:
    - shared/themes/README.md
    - shared/themes/audit_results.json
    - shared/themes/blowfish-standard/README.md
    - shared/themes/blowfish-standard/layouts/_default/single.html
    - shared/themes/blowfish-standard/layouts/partials/extend-head.html
    - shared/themes/blowfish-standard/layouts/partials/extend_head.html
    - shared/themes/blowfish-standard/layouts/partials/adsense/top.html
    - shared/themes/blowfish-standard/layouts/partials/adsense/in-article.html
    - shared/themes/blowfish-standard/assets/css/custom.css
    - scripts/audit_theme_overrides.py
  modified: []
decisions:
  - "Single source of truth for Blowfish overrides in shared/themes/blowfish-standard/"
  - "Standard files based on ADSENSE-GUIDE.md and Blowfish-Hugo-테마-업그레이드-표준-지침서.md"
  - "Symlink recommended over copy for migration (preserves updates)"
  - "GA4 property ID left as placeholder G-XXXXXXXXXX (per-blog customization needed)"
metrics:
  duration: ~15min
  completed: 2026-08-06
  tasks: 2
  files: 10
---

# Phase 59 Plan 06: Theme Override Audit + Shared Blowfish Standard Summary

Comprehensive audit of 85 blogs for layout overrides and creation of shared Blowfish standard source directory.

## What Was Built

**Theme Override Audit (Task 1):**
- Scanned 85 blogs across 8 brands (CAP, CUAP, ETAP, RAP, SEAP, STAP, TAP, MANUAL)
- Found 81 blogs with overrides (651 total files)
- Identified 251 unauthorized overrides
- Found 2 non-Blowfish themes (PaperMod: hotissue-hugo, Congo: stock-hugo)
- Measured disk usage baseline (themes/ = 0B, external repos)
- Saved full audit to `shared/themes/audit_results.json`

**Shared Blowfish Standard Directory (Task 2):**
- Created `shared/themes/blowfish-standard/` with 6 canonical files:
  - `layouts/_default/single.html` — H2 split injection template
  - `layouts/partials/extend-head.html` — adsbygoogle.js loader
  - `layouts/partials/extend_head.html` — GA4 + mobile CSS
  - `layouts/partials/adsense/top.html` — Top ad slot (Display)
  - `layouts/partials/adsense/in-article.html` — In-article ad slot (fluid+in-article)
  - `assets/css/custom.css` — unfilled removal + dark mode
- Created README.md with usage instructions and migration checklist

## Audit Findings

### High-Frequency Duplicates (Shared by 40+ blogs)
| File | Blogs | Status |
|------|-------|--------|
| extend-head.html | 80 | ✅ Standard exists |
| related.html | 78 | ❌ Not in standard |
| single.html | 44 | ✅ Standard exists |
| in-article.html | 44 | ✅ Standard exists |
| top.html | 42 | ✅ Standard exists |
| custom.css | 42 | ✅ Standard exists |
| extend_head.html | 38 | ✅ Standard exists |

### Unauthorized Override Patterns
1. **related.html** (78 blogs) — Related posts display, not in allowed list
2. **head/custom.html** (35 blogs) — ETAP custom head injection
3. **leaderboard.html** (33 blogs) — Legacy ad slot, migrate to top.html
4. **render-link.html** (15 blogs) — CUAP spider links
5. **cuap-spider-links.html** (15 blogs) — CUAP entity linking

### Non-Blowfish Themes
| Blog | Theme | Brand | Migration Needed |
|------|-------|-------|------------------|
| stock-hugo | Congo | STAP | Yes (to Blowfish) |
| hotissue-hugo | PaperMod | CAP | Yes (to Blowfish) |

## Deviations from Plan

None — plan executed exactly as written.

## Verification

**[검증됨]** Plan verification script passed:
```
PASS: theme audit + shared structure
```

**[검증됨]** All required files exist:
- `shared/themes/README.md` — 9,020 bytes
- `shared/themes/blowfish-standard/layouts/_default/single.html` — 1,847 bytes
- `shared/themes/blowfish-standard/layouts/partials/extend-head.html` — 168 bytes
- `shared/themes/blowfish-standard/layouts/partials/extend_head.html` — 653 bytes
- `shared/themes/blowfish-standard/layouts/partials/adsense/top.html` — 283 bytes
- `shared/themes/blowfish-standard/layouts/partials/adsense/in-article.html` — 301 bytes
- `shared/themes/blowfish-standard/assets/css/custom.css` — 452 bytes

**근거:** `python -c` verification script all assertions passed, `find` shows all 7 files.

## Known Stubs

None — all files fully implemented with canonical content from ADSENSE-GUIDE.md.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-59-15 (accepted) | shared/themes/blowfish-standard/ | Shared theme files affect Hugo build — blogs copy/symlink, not direct edit |
| T-59-16 (accepted) | shared/themes/blowfish-standard/ | Hugo build failure risk — test on one blog before bulk deployment |

## Self-Check: PASSED

- [✅] `shared/themes/README.md` created — 9,020 bytes, audit report complete
- [✅] `shared/themes/audit_results.json` created — full audit data saved
- [✅] `shared/themes/blowfish-standard/` created — 6 canonical files + README
- [✅] `scripts/audit_theme_overrides.py` created — audit script
- [✅] Commit 55ebda839 (test) exists — verified via `git log`
- [✅] Commit 432035d28 (feat) exists — verified via `git log`
- [✅] All verification scripts pass — `python -c` assertions passed
- [✅] Standard files match ADSENSE-GUIDE.md — content verified

## Self-Check: PASSED (verification)

All files found on disk. Both commits (55ebda839, 432035d28) exist in git log. Verification scripts pass.
