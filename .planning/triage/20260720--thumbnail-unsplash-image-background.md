---
date: 2026-07-20
type: fix
status: resolved
---

# Thumbnail: Unsplash image background + body images for STAP/RAP/SEAP

## What
Replace old text-only thumbnails with Unsplash photo background + title overlay for stock, rap, senior blogs. Add 1-2 Unsplash body images to stock articles. Fix informationhot-hugo single.html cover image (was using raw `absURL`, broke with `cover.relative:true`).

## Why
- Old thumbnails were text-only on colored blocks — visually dull
- informationhot-hugo cover images rendered as `/thumbnail.webp` (site root → 404) instead of resolving the relative path

## Files changed
- `shared/thumbnail_generator/generator.py` — `extra_context` parameter, new `generate_image_thumbnail()` with Unsplash → base64 data URI → image.html template → Playwright render, fallback to text-only on failure
- `shared/thumbnail_generator/templates/image.html` — new template: full-bleed image + dark gradient overlay + category badge + title with year highlight
- `shared/thumbnail_generator/__init__.py` — export `generate_image_thumbnail`
- `pipelines/stock/pipeline.py` — `_make_thumbnail()` → `generate_image_thumbnail`, added `_inject_unsplash_body_images()` (searches Unsplash per category, inserts 1-2 `![](url)` after `##`/`###` headings)
- `pipelines/rap/pipeline.py` — `generate_thumbnail` → `generate_image_thumbnail`
- `pipelines/senior/pipeline.py` — `_make_thumbnail()` → `generate_image_thumbnail`
- `informationhot-hugo/layouts/_default/single.html` — inline `absURL` cover code → `partial "cover.html"`

## How
- `generate_image_thumbnail()`: search Unsplash for category → random pick → httpx download → PIL center-crop 600×600 → WebP base64 data URI → render `image.html` in Playwright → upload to R2
- Fallback on any exception (no Unsplash, HTTP error, PIL error) → silent degradation to `generate_thumbnail()` text-only
- `_inject_unsplash_body_images()`: finds first `## ` heading (1st image) and first `### ` heading (2nd image), inserts markdown image lines

## Verification
- Python import check: `generate_image_thumbnail` importable, syntax valid in all 4 modified files
- Template rendering: both `default.html` and `image.html` render via Jinja2 without error
- Live Unsplash API test: `_inject_unsplash_body_images()` successfully fetched real Unsplash photos and injected markdown
- Existing `generate_thumbnail()` unchanged and backward-compatible
