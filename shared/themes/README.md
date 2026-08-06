# Theme Override Audit Report

> **Phase**: 59-ops-dashboard-and-unification
> **Plan**: 06
> **Date**: 2026-08-06
> **Purpose**: Audit all blog layout overrides and design shared Blowfish theme structure

---

## Disk Usage (Before)

- **themes/ directory**: 0B (empty, themes are in external repos)
- **Total blog layouts/**: 651 override files across 81 blogs
- **Shared themes directory**: `/Users/twinssn/Projects/shared-themes/` (contains Blowfish theme)

---

## Override Inventory Summary

| Metric | Count |
|--------|-------|
| Total blogs in config | 85 |
| Blogs with overrides | 81 |
| Total override files | 651 |
| Allowed overrides | ~400 |
| Unauthorized overrides | ~251 |
| Forbidden files (mobile-sticky) | 0 |

---

## Non-Blowfish Themes

| Blog | Theme | Brand | Status |
|------|-------|-------|--------|
| stock-hugo | Congo | STAP | Active |
| hotissue-hugo | PaperMod | CAP | Active |

**Note**: These blogs use different theme structures and require separate migration plans.

---

## Override Inventory by Brand

| Brand | Files | Allowed | Unauthorized |
|-------|-------|---------|--------------|
| CAP | 105 | ~60 | ~45 |
| CUAP | 153 | ~100 | ~53 |
| ETAP | 106 | ~70 | ~36 |
| MANUAL_BLOG_FOR_BACKUP | 123 | ~80 | ~43 |
| RAP | 55 | ~30 | ~25 |
| SEAP | 10 | ~8 | ~2 |
| STAP | 52 | ~35 | ~17 |
| TAP | 47 | ~30 | ~17 |

---

## Duplicate Overrides (Candidates for Sharing)

### High-Frequency Files (Shared by 40+ blogs)

| File Pattern | Blogs Using It | Identical? |
|-------------|----------------|------------|
| `layouts/partials/extend-head.html` | 80 | Yes (adsbygoogle.js loader) |
| `layouts/partials/related.html` | 78 | Partially (varies by blog) |
| `layouts/_default/single.html` | 44 | Yes (H2 split injection) |
| `layouts/partials/adsense/in-article.html` | 44 | Yes (fluid+in-article format) |
| `layouts/partials/adsense/top.html` | 42 | Yes (Display slot) |
| `assets/css/custom.css` | 42 | Yes (unfilled removal + dark mode) |
| `layouts/partials/extend_head.html` | 38 | Yes (GA4 + mobile CSS) |
| `layouts/partials/head/custom.html` | 35 | Yes (ETAP standard) |
| `layouts/partials/adsense/leaderboard.html` | 33 | Yes (legacy format) |

### Medium-Frequency Files (10-35 blogs)

| File Pattern | Blogs Using It | Notes |
|-------------|----------------|-------|
| `layouts/_default/_markup/render-link.html` | 15 | CUAP spider links |
| `layouts/partials/cuap-spider-links.html` | 15 | CUAP entity linking |
| `layouts/partials/extend-head-uncached.html` | 8 | RAP/TAP variant |
| `layouts/partials/adsense/adsense-loader.html` | 8 | CAP rotcha variant |
| `layouts/partials/adsense/auto-display.html` | 8 | CAP rotcha variant |
| `layouts/partials/adsense/lazy-ad.html` | 8 | CAP rotcha variant |
| `layouts/partials/header/components/translations.html` | 7 | CAP rotcha variant |

### Low-Frequency Files (2-7 blogs)

| File Pattern | Blogs Using It | Notes |
|-------------|----------------|-------|
| `layouts/partials/tradingview-widget.html` | 6 | STAP stock blogs |
| `layouts/partials/adsense/halfpage.html` | 5 | RAP legacy |
| `layouts/partials/adsense/lazy-loader.html` | 5 | RAP legacy |
| `layouts/partials/extend-article-link.html` | 5 | STAP stock blogs |
| `layouts/shortcodes/article.html` | 5 | TAP travel blogs |
| `layouts/shortcodes/lead.html` | 5 | TAP travel blogs |
| `layouts/index.html` | 4 | CAP/ETAP |
| `layouts/partials/related-single.html` | 4 | CAP legacy |

---

## Unauthorized Overrides

### Common Unauthorized Patterns

1. **`layouts/partials/related.html`** (78 blogs)
   - Purpose: Related posts display
   - Status: Not in allowed list, but commonly used
   - Recommendation: Evaluate for inclusion in standard

2. **`layouts/partials/head/custom.html`** (35 blogs)
   - Purpose: ETAP custom head injection
   - Status: Not in allowed list
   - Recommendation: Consolidate into extend-head.html

3. **`layouts/partials/adsense/leaderboard.html`** (33 blogs)
   - Purpose: Legacy leaderboard ad slot
   - Status: Not in allowed list (only top/in-article allowed)
   - Recommendation: Migrate to top.html

4. **`layouts/_default/_markup/render-link.html`** (15 blogs)
   - Purpose: CUAP spider link rendering
   - Status: Not in allowed list
   - Recommendation: Evaluate for inclusion

5. **`layouts/partials/cuap-spider-links.html`** (15 blogs)
   - Purpose: CUAP entity linking
   - Status: Not in allowed list
   - Recommendation: Evaluate for inclusion

### Forbidden Files

**None found** — No `mobile-sticky.html` files detected.

---

## Blog-Specific Overrides

### CAP (rotcha.kr family)

| Blog | Unique Overrides |
|------|------------------|
| rotcha-blog | 25 files (extensive customization) |
| informationhot-hugo | 20 files (legacy adsense variants) |
| techpawz-hugo | 15 files (custom shortcodes) |
| biz-techpawz-hugo | 14 files (custom partials) |
| issue-techpawz-hugo | 12 files (reference implementation) |

### CUAP (informationhot.kr family)

| Blog | Unique Overrides |
|------|------------------|
| All 15 CUAP blogs | `render-link.html`, `cuap-spider-links.html`, `leaderboard.html` |

### ETAP (various domains)

| Blog | Unique Overrides |
|------|------------------|
| All 35 ETAP blogs | `head/custom.html`, `related.html` |

### RAP (rotcha.kr family)

| Blog | Unique Overrides |
|------|------------------|
| All 5 RAP blogs | `extend-head-uncached.html`, `related.html`, `halfpage.html`, `lazy-loader.html`, `leaderboard.html` |

### STAP (stock/finance)

| Blog | Unique Overrides |
|------|------------------|
| All 6 STAP blogs | `tradingview-widget.html`, `related.html`, `extend-article-link.html` |

### TAP (travel)

| Blog | Unique Overrides |
|------|------------------|
| All 5 TAP blogs | `article.html`, `lead.html`, `related.html` |

---

## Recommended Shared Structure

### Standard Blowfish Overrides (5 files only)

```
shared/themes/blowfish-standard/
├── layouts/
│   ├── _default/
│   │   └── single.html          # H2 split + prose wrapper
│   └── partials/
│       ├── extend-head.html      # adsbygoogle.js loader
│       ├── extend_head.html      # GA4 + mobile CSS
│       └── adsense/
│           ├── top.html          # Top ad slot
│           └── in-article.html   # In-article ad slot
└── assets/
    └── css/
        └── custom.css            # unfilled removal + dark mode
```

### Migration Priority

1. **Phase 1**: Create shared Blowfish standard directory (this plan)
2. **Phase 2**: Migrate CUAP blogs to shared structure
3. **Phase 3**: Migrate CAP blogs to shared structure
4. **Phase 4**: Migrate ETAP blogs to shared structure
5. **Phase 5**: Migrate RAP/SEAP/TAP blogs to shared structure
6. **Phase 6**: Migrate STAP blogs (requires Congo→Blowfish migration)

---

## Appendix: Audit Data

Full audit data saved to: `shared/themes/audit_results.json`

---

**Next Steps**: See Task 2 for shared Blowfish standard directory creation.
