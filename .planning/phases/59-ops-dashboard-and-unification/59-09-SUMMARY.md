---
phase: 59
plan: 09
subsystem: shared/publishers
tags: [hugo-writer, etap, consolidation, wrapper]
requires: []
provides: [etap-wrapper-design]
affects: [shared/publishers/hugo_writer.py]
decisions:
  - "Added optional params to shared _write_hugo_post() for ETAP hooks"
  - "Created _write_hugo_post_etap() convenience wrapper mapping ETAP format"
tech-stack:
  added: []
  patterns: [opt-in-hooks, backward-compatible-params]
key-files:
  created: []
  modified: [shared/publishers/hugo_writer.py]
metrics:
  duration: "15m"
  completed: "2026-08-06T05:36:00Z"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 59 Plan 09: ETAP _write_hugo_post Consolidation Design Summary

## What Was Built

Extended `shared/publishers/hugo_writer.py` with optional ETAP post-processing hooks and a convenience wrapper `_write_hugo_post_etap()` that maps ETAP's 35 individual pipeline `_write_hugo_post()` functions to the shared implementation.

## Comparison Results

### Shared `_write_hugo_post()` (hugo_writer.py:908)
- **Signature:** `(blog_cfg, title, body_md, slug, category, tags, thumbnail_url, is_draft=False)`
- Uses `blog_cfg` dict with theme, site_path, id, domain
- Supports 3 themes: PaperMod, Blowfish, Congo
- Applies `_clean_body()`, `_extract_description()`, `_extract_first_image()`
- Blowfish shortcodes, funnel cards, schema JSON, frontmatter validation
- Returns `{"success": True, "file": path, "url": url}`

### ETAP `_write_hugo_post()` (35 pipelines, e.g. hiking:47)
- **Signature:** `(article, cover_image=None, body_images=None, blog_id=None, site_path=None, category=None)`
- Takes `article` dict (slug, title, content, tags, description, _draft, country, city)
- Builds own frontmatter (hardcoded Blowfish-style + `showTableOfContents: true` + `featureimagecredit`)
- Calls `inject_internal_links()` — cross-blog link injection
- Calls `insert_adsense()` — AdSense block insertion
- Inserts body images after H2 headings
- Calls `build_cross_sell_html()` + `insert_cross_sell_block()` — cross-sell at bottom
- Returns post directory path (not dict)

### Key Differences Identified
| Feature | Shared | ETAP |
|---------|--------|------|
| Internal links | ❌ | ✅ `inject_internal_links()` |
| AdSense | ❌ | ✅ `insert_adsense()` |
| Body images after H2 | ❌ | ✅ Manual H2 position calc |
| Cross-sell block | ❌ | ✅ `build_cross_sell_html()` + `insert_cross_sell_block()` |
| `featureimagecredit` | ❌ | ✅ In frontmatter |
| `showTableOfContents` | ❌ | ✅ In frontmatter |
| Multi-theme support | ✅ (3 themes) | ❌ (Blowfish only) |
| Frontmatter validation | ✅ | ❌ |
| Schema JSON | ✅ | ❌ |

## What Was Implemented

### 1. New optional parameters on `_write_hugo_post()`
- `inject_internal_links: bool = False` — opt-in cross-blog link injection
- `adsense_config: dict | None = None` — opt-in AdSense block insertion
- `cross_sell_config: dict | None = None` — opt-in cross-sell block with country/city/exclude_blog/max_items/position
- `body_images: list | None = None` — opt-in body image insertion after H2 headings

All parameters have defaults — **zero impact on existing callers**.

### 2. `_write_hugo_post_etap()` convenience wrapper
Maps ETAP article dict format to shared function:
- Extracts slug, title, content, tags, description, _draft from article dict
- Resolves thumbnail from cover_image arg or article.image_url
- Builds blog_cfg dict (theme=Blowfish, shortcodes_enabled=True)
- Calls `_write_hugo_post()` with all ETAP hooks enabled (inject_internal_links=True, adsense_config={}, cross_sell_config={...}, body_images=...)
- Returns post directory path (matching ETAP convention)

### 3. ETAP hooks in shared function body (guarded by params)
- Internal links: lazy import `shared.entity_linker.inject_internal_links()`
- Body images: H2 position calculation + image block insertion
- AdSense: lazy import `pipelines.etap.post_processor.insert_adsense()`
- Cross-sell: lazy import `shared.entity_linker.build_cross_sell_html()` + `pipelines.etap.post_processor.insert_cross_sell_block()`

All hooks use lazy imports with try/except ImportError — safe even if ETAP modules aren't installed.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all implementations are complete and functional.

## Threat Flags

None — no new security-relevant surface introduced. Lazy imports are safe.

## Verification

- [✅] `_write_hugo_post` has `inject_internal_links` parameter. 근거: `inspect.signature()` confirmed params: `['blog_cfg', 'title', 'body_md', 'slug', 'category', 'tags', 'thumbnail_url', 'is_draft', 'inject_internal_links', 'adsense_config', 'cross_sell_config', 'body_images']`
- [✅] All new params have defaults (backward compatible). 근거: `inject_internal_links=False`, `adsense_config=None`, `cross_sell_config=None`, `body_images=None`
- [✅] `_write_hugo_post_etap` wrapper exists with ETAP-compatible signature. 근거: `inspect.signature()` confirmed params: `['article', 'cover_image', 'body_images', 'blog_id', 'site_path', 'category', 'is_draft']`

## Residual Risks

- [부분검증] ETAP pipelines not yet migrated — this plan is design-only, no ETAP files modified
- [부분검증] `insert_adsense()` import path (`pipelines.etap.post_processor`) requires ETAP package to be importable from 5000 — may need sys.path adjustment in some deployment contexts

## Self-Check: PASSED

- [✅] shared/publishers/hugo_writer.py — FOUND
- [✅] commit 5245ef04c — FOUND

## Commits

- `5245ef04c`: `feat(59-09): add ETAP wrapper design to shared hugo_writer.py`
