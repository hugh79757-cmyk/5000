---
phase: 50-cta-button-center
plan: 01
subsystem: CTA-button-center-cuap
tags:
  - cuap
  - css
  - cross-sell-card
  - funnel-header
  - cta-box
  - btn-price-check
requires: []
provides:
  - "10x custom.css with cross-sell/funnel/cta-box classes"
  - "cuap_entity_linker.py inline style migration"
  - "pipeline.py CTA fallback + markdown post-processing"
  - "scripts/fix_cta_links.py batch conversion script"
affects:
  - cuap/*/assets/css/custom.css
  - shared/cuap_entity_linker.py
  - pipelines/curation/pipeline.py
  - scripts/fix_cta_links.py
tech-stack:
  added:
    - "CSS custom properties for cross-sell, funnel, and CTA components"
  patterns:
    - "CSS class-based styling replacing inline `style=` attributes"
    - "dark mode (`html.dark`) variants for all new visual components"
    - "runtime markdown-to-HTML CTA link conversion in pipeline"
    - "batch post-processing script with dry-run mode"
key-files:
  created:
    - "scripts/fix_cta_links.py"
  modified:
    - "10x cuap/*/assets/css/custom.css"
    - "shared/cuap_entity_linker.py"
    - "pipelines/curation/pipeline.py"
decisions:
  - "display: table + margin: auto for btn-price-check centering (works inside <p> tags)"
  - "funnel link color kept inline (per-blog dynamic from THEME_COLORS)"
  - "markdown CTA conversion targets only link.coupang.com and www.coupang.com"
  - "re.sub() for all-link replacement (not just first match) in post-processing"
metrics:
  duration: "27m"
  completed_date: "2026-07-26"
---

# Phase 50 Plan 01: CTA Button Center — CSS 클래스 표준화 + 인라인 스타일 마이그레이션

10개 CUAP 블로그의 CTA 버튼 중앙 정렬, cross-sell/funnel/cta-box CSS 클래스 추가, 인라인 스타일 → CSS 클래스 마이그레이션, Hugo 빌드 + 배포 완료.

## Tasks Completed

| # | Task | Status | Commit(s) |
|---|------|--------|-----------|
| 1 | CSS Classes — 10 CUAP custom.css (btn-price-check centering + cross-sell/funnel/cta-box classes) | ✅ | CUAP: f17ab25 (health), 845582c (beauty), 756ed14 (fitness), 8a18f96 (kitchen), c3846cc (baby), 9a3fd2c (camping), ebce5b2 (laptop), d2d57c5 (appliance), dfb3e03 (interior), ee97a07 (pet) |
| 2 | Inline Style → CSS Class Migration (cuap_entity_linker.py) | ✅ | 5000: 0be348f0b |
| 3 | CTA Fallback + Post-processing (pipeline.py) | ✅ | 5000: 521dcfc0f |
| 4 | Batch Script (scripts/fix_cta_links.py) | ✅ | 5000: f43a3a990 |
| 5 | Hugo Build Verification + Deploy (10 CUAP blogs) | ✅ | (deployed live) |

### Task 1: CSS Classes — 10 CUAP custom.css

**btn-price-check centering:**
- `display: inline-block` → `display: table` (shrink-to-fit width + margin:auto centering)
- `margin: 1.5rem 0` → `margin: 1.5rem auto` (horizontal centering)
- All other properties preserved exactly (padding, background, color, font-weight, border-radius, hover/active/dark variants)

**New CSS classes added (3 sections, ~100 lines each):**
1. `.cross-sell-card`, `.cross-sell-card__title`, `.cross-sell-card__links`, `.cross-sell-card__link` — with dark mode variants
2. `.funnel-header`, `.funnel-header__label`, `.funnel-header__links`, `.funnel-header__link` — with dark mode variants
3. `.cta-box`, `.cta-box p:first-child`, `.cta-box p:last-child` — with dark mode variants

**Variant handling:**
- Group A (8 blogs): Identical files, same SHA256 before and after
- Group B (kitchen-hugo): Retained all unique theme styles (kitchen-hero, tag-badge, floating decor, scroll-to-top)
- Group C (pet-hugo): Retained simplified AdSense layout, unfilled ad hiding, dark mode background guard

### Task 2: Inline Style → CSS Class Migration (cuap_entity_linker.py)

**build_cross_sell_card() (lines 311-369):**
- Container: `style="margin:20px 0;padding:16px;background:#fafbfc;..."` → `class="cross-sell-card"`
- Title: `style="margin:0 0 10px;font-weight:600;..."` → `class="cross-sell-card__title"`
- Links wrapper: `style="display:flex;flex-wrap:wrap;gap:4px"` → `class="cross-sell-card__links"`
- Link items: `style="display:inline-flex;align-items:center;gap:6px;..."` → `class="cross-sell-card__link"`

**build_funnel_header() (lines 372-421):**
- Container: `style="margin:0 0 16px;padding:12px 16px;..."` → `class="funnel-header"`
- Label: `style="margin:0 0 6px;font-size:13px;color:#6b7280"` → `class="funnel-header__label"`
- Links wrapper: `style="display:flex;flex-wrap:wrap"` → `class="funnel-header__links"`
- Link items: `style="display:inline-flex;align-items:center;gap:4px;..."` → `class="funnel-header__link"` (color stays inline — per-blog dynamic from THEME_COLORS)

### Task 3: CTA Fallback + Post-processing (pipeline.py)

**Part A — _FALLBACK_CTA all inline styles removed:**
```python
# BEFORE: 4 style="..." attributes on div.container + p + p
# AFTER:  <div class="cta-box"><p>💡 구매 팁</p><p>...</p></div>
```

**Part B — fix_markdown_cta_links() added:**
- Regex: `r'\[([^\]]+)\]\((https?://(?:link\.coupang\.com|www\.coupang\.com)[^)]+)\)'`
- Replacement: `<div style="text-align:center;margin:1.5rem 0"><a class="btn-price-check" href="\2">🛒 \1</a></div>`
- Called after CTA fallback check, before CUAP spider injection
- Only targets coupang affiliate links (link.coupang.com, www.coupang.com)
- `re.sub()` handles all CTA links in a post, not just the first

### Task 4: Batch Script (scripts/fix_cta_links.py)

- Scans `content/posts/*/index.md` in all 10 CUAP blogs
- Same regex pattern as pipeline post-processing
- Also strips inline styles from existing `<div class="cta-box">` patterns
- **Modes:** `--dry-run` (preview), `--blog <id>` (single blog), default (all blogs)
- **Safety:** SHA256 verification, `.bak` backup, error logging
- **Dry-run on health-hugo verified:** 392 files scanned, CTA links converted with full URL param preservation

### Task 5: Hugo Build + Deploy

**Build results (all 0 errors):**

| Blog | Pages | Build Time |
|------|-------|-----------|
| health-hugo | 945 | 1022ms |
| beauty-hugo | 1143 | 1052ms |
| fitness-hugo | 1267 | 1960ms |
| kitchen-hugo | 873 | 1048ms |
| baby-hugo | 1409 | 1879ms |
| camping-hugo | 771 | 1095ms |
| laptop-hugo | 667 | 999ms |
| appliance-hugo | 1223 | 1560ms |
| interior-hugo | 1506 | 2618ms |
| pet-hugo | 699 | 877ms |

**Deploy results:** 10/10 ✅ (health, beauty, fitness, kitchen, baby, pet, camping, laptop, appliance, interior)
**Live URL verification:** health.informationhot.kr → 200, beauty.informationhot.kr → 200

## CSS Classes Added Per Blog

| Blog | cross-sell-card | funnel-header | cta-box | dark-mode selectors | Lines |
|------|:----------:|:----------:|:----:|:---------------:|:-----:|
| health-hugo | ✅ | ✅ | ✅ | 11 | 187 |
| beauty-hugo | ✅ | ✅ | ✅ | 11 | 187 |
| fitness-hugo | ✅ | ✅ | ✅ | 11 | 187 |
| baby-hugo | ✅ | ✅ | ✅ | 11 | 187 |
| camping-hugo | ✅ | ✅ | ✅ | 11 | 187 |
| laptop-hugo | ✅ | ✅ | ✅ | 11 | 187 |
| appliance-hugo | ✅ | ✅ | ✅ | 11 | 187 |
| interior-hugo | ✅ | ✅ | ✅ | 11 | 187 |
| kitchen-hugo | ✅ | ✅ | ✅ | 11 | 341 (with theme extensions) |
| pet-hugo | ✅ | ✅ | ✅ | 11 | 172 (simplified layout) |

## Verification Results

### 1. CSS completeness ([검증됨])
- All 10 blogs: `grep '\.cross-sell-card\|\.funnel-header\|\.cta-box'` returns matches
- Kitchen retains kitchen-hero (11 occurrences), pet retains unfilled ad handling (2 occurrences)
- btn-price-check uses `display: table` and `margin: 1.5rem auto` in all 10 blogs

### 2. Python AST ([검증됨])
```
ALL AST OK — cuap_entity_linker.py, pipeline.py, fix_cta_links.py all parse clean
```

### 3. Hugo build ([검증됨])
- All 10 blogs build with 0 errors (verified output: Pages, Paginator pages, Non-page files)
- css classes appear in compiled Hugo output (cross-sell-card, btn-price-check, cta-box all found)

### 4. Affiliate URL params ([검증됨])
- Dry-run output confirms: `[쿠팡에서 최저가 확인하기](https://link.coupang.com/re/AFFSDP?lptag=...&pageKey=...&traceid=...)` → URL preserved exactly with all params

### 5. Deploy ([검증됨])
- 10/10 blogs deployed successfully via `deploy_site()`
- health.informationhot.kr → HTTP 200
- beauty.informationhot.kr → HTTP 200

### 6. Dark mode ([검증됨])
- All 10 CSS files have `html.dark` variants for cross-sell-card, funnel-header, and cta-box
- 11 dark mode selectors each (matches: 3 cross-sell + 2 funnel + 2 cta-box + 2 existing btn-price-check + 2 existing)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all CSS classes are defined, all Python code uses the classes, batch script is ready for execution.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced. All changes are CSS class references and HTML generation within the existing pipeline.

## 잔존 위험

- **배치 스크립트 미실행**: `scripts/fix_cta_links.py`는 dry-run으로만 검증되었고 실제 기존 포스트 변환은 실행되지 않음. 이는 방침(기존 포스트는 배치 스크립트로 선택적 실행)이며, 신규 발행부터 `fix_markdown_cta_links()`가 적용됨. 기존 포스트 변환이 필요한 경우 `python3 scripts/fix_cta_links.py` 실행 필요.
- **cross-sell-card/funnel-header 라이브 검증**: 이 클래스들은 pipeline 런타임에만 생성되므로 Hugo 정적 빌드에서는 확인 불가. 실제 CUAP 발행 시 visual 확인 필요.
- **다크모드 테스트**: CSS `html.dark` 셀렉터는 정의되었으나, 라이브 사이트에서 다크모드 전환 시 visual 확인 필요 (자동 테스트 불가 영역).
