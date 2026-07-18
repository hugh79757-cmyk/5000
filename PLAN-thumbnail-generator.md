# Plan: Centralized Editorial Thumbnail Generator

## Goal
Move the Playwright-based editorial thumbnail generator into 5000's `shared/` module, making it the **single source of thumbnails** for all blogs. Retire the 3 PIL-based thumbnail generators and provide batch backfill for 7 standalone Hugo sites.

## Current State

### Existing PIL generators (to retire)
| Pipeline | File | R2 Path | Color System |
|----------|------|---------|--------------|
| `senior` | `pipelines/senior/thumbnail.py` | `senior-images/thumbnails/` | Category-based blue/teal/warm tones |
| `stock` | `pipelines/stock/thumbnail.py` | `stock-thumbnails/{date}-{hash}.webp` | Navy/slate/green categories |
| `rap` | `pipelines/rap/thumbnail.py` | `rap-thumbnails/{date}-{hash}.webp` | Blue/green/purple categories |

### Playwright generator (to centralize)
- **Location**: `informationhot-hugo/scripts/generate_thumbnail.py` + `thumbnail-template.html`
- **Method**: Jinja2 HTML → Playwright screenshot → WebP → R2 upload
- **Format**: 600×600, 2x retina, 50KB max
- **R2 Path**: `images/informationhot/{slug}/thumbnail.webp`
- **Color system**: Category-based accent colors (blue, red, green, etc.)

### Target Hugo Sites (standalone, not in 5000 pipeline)
| Site | Theme | Posts | Frontmatter cover field | Domain |
|------|-------|-------|------------------------|--------|
| kuta-hugo | blowfish | 2,037 | `featureimage:` | img-kuta.informationhot.kr |
| rotcha-blog | PaperMod | 1,326 | (none currently) | — |
| informationhot-hugo | PaperMod | 534 | `cover.image:` | img.informationhot.kr |
| techpawz-hugo | blowfish | 1,513 | `featureimage:` | img.techpawz.com |
| issue-techpawz-hugo | blowfish | 281 | `thumbnail:` | img-issue.techpawz.com |
| biz.techpawz-hugo | blowfish | 610 | (to be added) | img-biz.techpawz.com |
| info.techpawz-hugo | blowfish | 542 | (to be added) | img.techpawz.com |

## Architecture

```
5000/
├── shared/
│   └── thumbnail_generator/
│       ├── __init__.py              # Public API
│       ├── generator.py             # Playwright render + R2 upload
│       ├── colors.py                # Blog-specific + category color palettes
│       ├── templates/
│       │   ├── default.html         # Editorial split-layout (current informationhot design)
│       │   └── minimal.html         # Alternative minimal layout
│       └── batch.py                 # Batch scan + generate for Hugo sites
├── pipelines/
│   ├── senior/pipeline.py           # Replace _make_thumbnail() → shared generator
│   ├── stock/pipeline.py            # Replace _make_thumbnail() → shared generator
│   └── rap/pipeline.py              # Replace upload_thumbnail() → shared generator
└── scripts/
    └── batch_thumbnails.py          # Generalized batch script for all Hugo sites
```

### Color Palette Strategy

Each blog gets a **primary brand color** derived from its PIL thumbnail heritage + category mapping:

```python
BLOG_PALETTES = {
    "senior":    {"primary": "#2563eb", "secondary": "#0ea5e9", "badge_bg": "rgba(255,255,255,0.2)"},
    "stock":     {"primary": "#1e3a5f", "secondary": "#3b82f6", "badge_bg": "rgba(255,255,255,0.2)"},
    "rap":       {"primary": "#3498db", "secondary": "#2ecc71", "badge_bg": "rgba(255,255,255,0.2)"},
    "kuta":      {"primary": "#e11d48", "secondary": "#f43f5e", "badge_bg": "rgba(255,255,255,0.2)"},
    "rotcha":    {"primary": "#8b5cf6", "secondary": "#a78bfa", "badge_bg": "rgba(255,255,255,0.2)"},
    "informationhot": {"primary": "#dc2626", "secondary": "#f97316", "badge_bg": "rgba(255,255,255,0.2)"},
    "techpawz":  {"primary": "#6366f1", "secondary": "#818cf8", "badge_bg": "rgba(255,255,255,0.2)"},
    "issue-techpawz": {"primary": "#f59e0b", "secondary": "#fbbf24", "badge_bg": "rgba(255,255,255,0.2)"},
    "biz.techpawz": {"primary": "#059669", "secondary": "#10b981", "badge_bg": "rgba(255,255,255,0.2)"},
    "info.techpawz": {"primary": "#0284c7", "secondary": "#38bdf8", "badge_bg": "rgba(255,255,255,0.2)"},
}
```

Each pipeline also keeps its **category-based accent color** mapping from the existing PIL generators (e.g., senior's 의료지원=blue, stock's 공시분석=navy) — but applied through the new Playwright template with blog colors as base.

## Implementation Steps

### Phase 1: Create `shared/thumbnail_generator/` core module
1. Move `generate_thumbnail.py` from informationhot-hugo to `shared/thumbnail_generator/generator.py`
2. Create `colors.py` with blog-specific palettes (extracted from existing PIL generators)
3. Move the HTML template to `shared/thumbnail_generator/templates/default.html`
4. Add `site_id` parameter to select blog-specific colors + R2 path
5. **Verify**: Run a single test thumbnail for each target blog

### Phase 2: Replace pipeline PIL generators
1. **Senior**: `pipelines/senior/pipeline.py` — import from shared generator instead of `pipelines.senior.thumbnail`
2. **Stock**: `pipelines/stock/pipeline.py` — import from shared generator  
3. **RAP**: `pipelines/rap/pipeline.py` — import from shared generator
4. Update R2 paths to a unified scheme: `thumbnails/{site_id}/{slug}.webp`
5. Keep old PIL files as fallback (don't delete immediately)
6. **Verify**: Run each pipeline's thumbnail generation and confirm R2 upload + URL

### Phase 3: Batch backfill for target Hugo sites
1. Create `shared/thumbnail_generator/batch.py` with:
   - Site config loader (paths, theme type, cover field name)
   - Single-browser-session batch processing
   - Frontmatter updater (theme-aware: blowfish `featureimage:`, PaperMod `cover.image:`)
   - Progress tracking + resume support
2. Adapt `scripts/batch_thumbnails.py` as the CLI entry point
3. **Verify**: Run dry-run for one site (kuta-hugo), confirm 5-10 posts

### Phase 4: Fill missing cover fields (rotcha-blog, biz.techpawz, info.techpawz)
These sites have no cover image in frontmatter — batch will add them.

## R2 Key Scheme
```
thumbnails/{site_id}/{slug}.webp
```
Examples:
- `thumbnails/kuta/2026-온더고-도시락-인기-메뉴.webp`
- `thumbnails/rotcha/LH-관악봉천-행복주택.webp`
- `thumbnails/stock/공시분석-삼성전자-실적.webp`

## Key Decisions
1. **Playwright is bundled in 5000's venv** — needs `playwright install chromium`
2. **Template per blog flavor**: Same base template, different colors/brand text
3. **Frontmatter update is site-specific**: blowfish uses `featureimage:`, PaperMod uses `cover: image:`
4. **Fallback**: Old PIL files remain untouched during Phase 1-2, deleted in Phase 3 cleanup
5. **No Hugo site config conversion**: These sites stay standalone — batch script runs independently
