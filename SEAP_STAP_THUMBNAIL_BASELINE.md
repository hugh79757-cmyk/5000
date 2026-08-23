# SEAP/STAP Thumbnail Baseline Reconciliation

> **Date:** 2026-08-19 23:25 KST
> **Status:** READ-ONLY — no code, config, R2, DB, or deployment changes

---

## 1. Adapter Files: NOT FOUND

### Finding
`adapter.py`, `hugo_adapter.py`, `blogger_adapter.py` do **not exist** on disk.

```
shared/thumbnail_generator/
├── __init__.py
├── colors.py
├── generator.py
└── templates/
    ├── default.html
    ├── image.html
    └── ...
```

git status: 0 staged, 0 unstaged, 0 untracked changes.

### Correction
Previous session's "플랫폼 어댑터 설계 완료" was a **design spec**, not implemented code. The claim of "코드 변경 없음" was accurate (no files were written), but the design was never committed to code.

---

## 2. SEAP Blogger Thumbnail Failure (8/19)

### Root Cause: Chromium Not Installed at Publish Time

| Event | Timestamp | Thumbnail Status |
|-------|-----------|-----------------|
| 8/17 publish (id=11488) | 2026-08-17 08:04 UTC | ✅ `thumbnails/senior/20260817-9b301d827f.webp` |
| 8/17 publish (id=11492) | 2026-08-17 08:12 UTC | ✅ `thumbnails/senior/20260817-fe5a61f4d5.webp` |
| 8/19 publish (id=11505) | 2026-08-19 02:05 UTC | ❌ empty |
| 8/19 publish (id=11518) | 2026-08-19 04:10 UTC | ❌ empty |
| 8/19 publish (id=11532) | 2026-08-19 07:11 UTC | ❌ empty |
| 8/19 publish (id=11544) | 2026-08-19 10:10 UTC | ❌ empty |
| 8/19 publish (id=11556) | 2026-08-19 14:10 UTC | ❌ empty |
| Chromium installed | 2026-08-19 22:07 UTC+7 | — |

**Chromium was installed AFTER all 8/19 publishes.** The `_make_thumbnail()` → `generate_image_thumbnail()` → Playwright `chromium.launch()` failed silently, returning `""`. The scheduler logged "발행 성공" because pipeline exit code was 0 — stderr (containing "Thumbnail failed:") was discarded.

### Verification: 8/20 Scheduler
- **No 8/20 entries** in scheduler log (as of 23:25 KST). Next senior-blogger run: 8/20 08:10 KST.
- Chromium is now installed at `/Users/twinssn/Library/Caches/ms-playwright/chromium_headless_shell-1228/`
- Venv test: `pw.chromium.launch()` → OK

### Live Site Confirmation
- `https://2.techpawz.com/2026/08/55.html` — og:image absent, body img 0, twitter:card=summary_large_image with no image
- Blogger feed: no `media_thumbnail`, no `<img>` in content

---

## 3. Body-First Image vs Card Thumbnail (Separate Metrics)

| Metric | Definition | Current Status |
|--------|-----------|---------------|
| **A: DB body_html img** | `thumbnail_url` non-empty in stap_content.db | 8/19: 0/5 (all empty) |
| **B: Live body img** | `<img>` tag visible in published HTML | 8/19: 0/5 (no images) |
| **C: Card thumbnail** | Homepage/search card shows thumbnail | Blogger template dependent (no og:image, no media_thumbnail found) |

**Key distinction:** Metric A (DB) is a prerequisite for Metric B (live), which is a prerequisite for Metric C (card). All three are currently 0 for 8/19 posts.

Blogger's thumbnail mechanism: first `<img>` in post content → used as search/feed thumbnail. No frontmatter concept, no og:image support in template.

---

## 4. Fallback Groups: Design Only (R2 Not Populated)

### Proposed 7 Groups (from THUMBNAIL_STANDARD_PROPOSAL.md)

| # | Group ID | Label | Blogs | R2 Path | Status |
|---|----------|-------|-------|---------|--------|
| 1 | rotcha-auto | 핫이슈·비교분석 | 6 CAP | `common/fallback-rotcha-auto.webp` | ❌ Not uploaded |
| 2 | infohot-car | 랭킹·내차찾기 | 2 CAP | `common/fallback-infohot-car.webp` | ❌ Not uploaded |
| 3 | infohot-general | 시니어·복지·부동산 | 1 SEAP + 5 RAP | `common/fallback-infohot-general.webp` | ❌ Not uploaded |
| 4 | cuap-curation | 추천 가이드 | 15 CUAP | `common/fallback-cuap-curation.webp` | ❌ Not uploaded |
| 5 | stap-stock | 주식·투자 분석 | 6 STAP | `common/fallback-stap-stock.webp` | ❌ Not uploaded |
| 6 | tap-travel | 여행·코스 추천 | 5 TAP | `common/fallback-tap-travel.webp` | ❌ Not uploaded |
| 7 | etap-travel-en | Travel Guide | 27 ETAP | `common/fallback-etap-travel-en.webp` | ❌ Not uploaded |

### Visual Distinction Requirement
Each group should be visually distinct (different color palette, category label) to serve as a meaningful branded fallback. Currently only 2 defaults exist:
- `common/default-thumbnail.webp` (generic)
- `common/stock-default-thumbnail.webp` (stock only — used by 5000's hugo_writer, NOT by STAP publisher)

STAP publisher uses its own `DEFAULT_THUMBNAILS` dict (see §6).

---

## 5. Canary Targets (Revised)

| Target | blog_id | Platform | Reason | Status |
|--------|---------|----------|--------|--------|
| **senior-hugo** | senior-hugo | Hugo/Blowfish | Chromium now installed, thumbnail generation should work | ✅ Ready |
| **stock-hugo** | stock-hugo | Hugo/Blowfish | `thumbnail_factory.py` path, DEFAULT_THUMBNAILS dict | ✅ Ready |
| **SEAP Blogger draft** | senior-blogger | Blogger | R2+WebP proven (8/17), 8/19 failure was chromium timing | ✅ Ready |
| ~~sector-hugo~~ | sector-hugo | Hugo/Blowfish | **EXCLUDED** — paused (no_content) | ❌ |

### Canary Verification Checklist
1. **senior-hugo**: `dispatcher.py senior-hugo` → check featureimage URL ≠ default, R2 200, resolution, permalink
2. **stock-hugo**: `dispatcher.py stock-hugo` → check featureimage URL = `thumbnails/stock/...`, R2 200, resolution
3. **SEAP Blogger draft**: `BloggerClient.publish_post()` draft → check body `<img>` exists, R2 URL accessible, Blogger renders image

---

## 6. stock-hugo thumbnail/featureimage Code Path

### STAP Publisher (NOT 5000's hugo_writer)

STAP has its **own publisher** at `STAP/shared/publisher.py`:

```python
# line 115-124
DEFAULT_THUMBNAILS = {
    "stock": "https://pub-...r2.dev/common/default-stock.webp",
    "dividend": "https://pub-...r2.dev/common/default-dividend.webp",
    "etf": "https://pub-...r2.dev/common/default-etf.webp",
    "sector": "https://pub-...r2.dev/common/default-sector.webp",
    "ipo": "https://pub-...r2.dev/common/default-ipo.webp",
    "finance": "https://pub-...r2.dev/common/default-finance.webp",
}
DEFAULT_THUMBNAIL = "https://pub-...r2.dev/common/default-thumbnail.webp"

# line 214-216
if not thumbnail_url:
    thumbnail_url = DEFAULT_THUMBNAILS.get(blog_id, DEFAULT_THUMBNAIL)

# line 175
fm += 'featureimage: "' + (thumbnail_url or DEFAULT_THUMBNAIL) + '"\n'
```

### Flow
1. `stock pipeline:_make_thumbnail()` → `thumbnail_factory.py:make_and_upload("stock", title, category)` → returns R2 URL or `""`
2. If `""` → `_extract_first_image(body_md)` attempt
3. If still empty → `DEFAULT_THUMBNAILS.get("stock-hugo", DEFAULT_THUMBNAIL)` → **`default-stock.webp`**
4. Frontmatter: `featureimage: "https://pub-...r2.dev/common/default-stock.webp"`

### Verification
- stock-hugo id=11206 (8/13): `featureimage: thumbnails/stock/20260813-...webp` ✅ (thumbnail_factory succeeded)
- stock-hugo id=10412 (7/30): `featureimage: default-thumbnail.webp` ❌ (old posts, before DEFAULT_THUMBNAILS was added)
- stock-hugo recent posts (휴온스, 힘스): `featureimage: default-thumbnail.webp` — these use STAP publisher's fallback

### Minimum Fix (NOT applied — READ-ONLY baseline)
The `DEFAULT_THUMBNAILS` dict correctly maps `stock-hugo` → `default-stock.webp`. Recent empty-thumbnail posts should get `default-stock.webp`, not `default-thumbnail.webp`. If they show `default-thumbnail.webp`, the blog_id may not be matching — verify `blog_cfg.get("id")` returns `"stock-hugo"` (not `"stock"`).

---

## 7. DB Path Clarification

| DB | Path | Purpose |
|----|------|---------|
| `content.db` | `5000/data/content.db` | Legacy publish ledger (senior-blogger 93 records) |
| `stap_content.db` | `5000/data/stap_content.db` | **Current** articles table (senior-blogger 416 records) |

`shared/db_paths.py:16`: `ARTICLES_DB = stap_content.db`

Senior-blogger's 8/19 records are in **stap_content.db**, not content.db.

---

## 8. What Changed Since Last Audit

| Item | Previous Claim | Corrected Status |
|------|---------------|-----------------|
| adapter.py files | "설계 완료" | **NOT FOUND** — design only |
| stock-hugo featureimage bug | "thumbnail vs featureimage 불일치" | **STAP publisher DEFAULT_THUMBNAILS 정상** — blog_id별 고유 default |
| 7 fallback groups | "확정" | **R2 미업로드** — design only |
| senior-blogger 8/19 | "_thumbnail 실패" | **Chromium 미설치가 원인** — now installed |
| sector-hugo canary | "포함" | **EXCLUDED** — paused (no_content) |

---

## 9. Risks

1. **8/20 scheduler**: Chromium now installed, but first run not yet observed. If `_make_thumbnail()` fails for a different reason (Unsplash API, network), thumbnail will still be empty.
2. **STAP publisher vs 5000 hugo_writer**: Two separate code paths for featureimage. Changes to one don't affect the other.
3. **Blogger og:image**: Template doesn't support it. Social sharing thumbnails won't show on Blogger.
4. **7 fallback groups**: Need R2 upload before any code changes can reference them.
