# Phase 49: Cross-link Creation Bug Fundamental Fix — Research

**Researched:** 2026-07-26
**Domain:** CUAP cross-link (크로스링크) generation and rendering
**Confidence:** HIGH

## Summary

The CUAP cross-link system generates "🛍️ 이런 상품도 좋아하실 거예요" cards at the bottom of blog posts, linking to related posts on other CUAP blogs. Two critical bugs exist:

**Bug 1 (Slug Mismatch — ≥4 links affected):** Every cross-link URL uses a wrong slug (`20260726-{keyword}`) that doesn't exist on disk. This causes 404 on ALL 4 cross-links. Root cause: `hugo_writer._write_hugo_post()` returns `{"success": True, "file": path}` with NO `"url"` key, so the pipeline's `_actual_slug` extraction (line 1062-1064 of pipeline.py) falls back to the keyword-based `_make_slug(keyword)` instead of the title-based `slugify(title)`.

**Bug 2 (4→2 Rendering Drop — transient):** When target blogs have no `cuap_entities` entries, `build_cross_sell_card()` silently skips them via the `if not row: continue` clause. With all 10 blogs now having entities, this is less common but can still occur for blogs that recently started publishing or whose entity registration failed.

**Primary recommendation:** Fix the entity registration to use the correct slug from `result["file"]`, fix existing entities with a batch script, and add a fallback in `build_cross_sell_card()` when no entity exists.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
1. **Cross-link URL must use actual slug**: The URL must use the target post's actual frontmatter `slug` field
2. **4 links guaranteed**: 4 cross-link HTML elements must be rendered when specified
3. **Batch fix script**: Create a script to fix existing broken cross-link URLs across all content
4. **Phase 48 compat**: Do not break `shared/publishers/hugo_writer.py` changes from Phase 48
5. **Git commits**: Split cross-link fix commits from batch fix commits for rollback safety

### the agent's Discretion
- How to fix the slug extraction from publish result
- Whether to add fallback URLs (blog homepage) for blogs without entities
- Exact algorithm for batch fix (HTTP HEAD vs disk scan vs DB lookup)
- Whether to add logging/monitoring for failed cross-link generation

### Deferred Ideas (OUT OF SCOPE)
- None explicitly listed
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PER-REQ-01 | Fix cross-link URL slug to match actual post slug | Root cause identified: `hugo_writer._write_hugo_post()` has no URL in return value |
| PER-REQ-02 | Guarantee all 4 cross-links render in HTML | Root cause identified: `build_cross_sell_card()` skips blogs without entities |
| PER-REQ-03 | Batch fix script for existing broken links | Existing entity DB has both correct and incorrect slugs; on-disk directories are ground truth |
| PER-REQ-04 | Verify health blog cholesterol post 4 links all 200 | All 4 current links use wrong slug → all 404 |
| PER-REQ-05 | Verify 5 CUAP blogs cross-links | Cross-link generation code in `pipelines/curation/pipeline.py` |
| PER-REQ-06 | Hugo build 0 errors | Phase 48 changes in `hugo_writer.py` are independent from cross-link code |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Cross-link card generation | Pipeline (shared lib) | — | `shared/cuap_entity_linker.py` — Python code that builds HTML |
| Entity registration | Pipeline (per-blog) | — | `pipelines/curation/pipeline.py:1068` — called after each publish |
| URL slug correctness | Pipeline (shared lib) | — | `shared/publishers/hugo_writer._write_hugo_post()` missing URL in return |
| Cross-link display | Hugo (static site) | — | Rendered from baked HTML in `index.md` |
| Batch fix (existing posts) | CLI script | — | Script scans `content/posts/*/index.md` and replaces URLs |

## Standard Stack

### Core
| Library | Location | Purpose | Why Standard |
|---------|----------|---------|--------------|
| `cuap_entity_linker.py` | `shared/cuap_entity_linker.py` | Cross-link card generation + entity registration | Single source of truth for CUAP cross-links |
| `pipeline.py` (curation) | `pipelines/curation/pipeline.py` | Blog publishing pipeline, calls both cuap_entity_linker and publisher | All 10 CUAP blogs route through this |
| `publisher.py` | `shared/publisher.py` | Hugo post writing + publishing | Re-exports from `hugo_writer.py` (import override at line 762-770) |
| `hugo_writer.py` | `shared/publishers/hugo_writer.py` | Hugo post file writer (frontmatter + body) | ACTUAL `_write_hugo_post()` called at runtime (due to import override) |

### Supporting
| Library | Location | Purpose | When to Use |
|---------|----------|---------|-------------|
| `_tmp_fix_stale_cards.py` | `scripts/_tmp_fix_stale_cards.py` | Fixes old-format URLs (without `/posts/` prefix) | Already applied — not for new cards |
| `backfill_cuap_entities.py` | `scripts/backfill_cuap_entities.py` | Registers entities from on-disk posts (using directory names as slugs) | Already applied — uses correct on-disk name |
| `migrate_ascii_slugs.py` | `scripts/migrate_ascii_slugs.py` | Korean→ASCII slug migration (not executed yet) | Separate concern |

**Installation:** No new packages. All code is existing Python stdlib + project imports.

## Import Chain (CRITICAL)

```
pipelines/curation/pipeline.py
  └─ from shared.publisher import publish
       └─ publish() [publisher.py:852]
            └─ _write_hugo_post() ← OVERRIDDEN by:
                 └─ from shared.publishers.hugo_writer import _write_hugo_post [publisher.py:769]
                      └─ hugo_writer._write_hugo_post() [hugo_writer.py:820]
                           └─ returns {"success": True, "file": file_path}
                           └─ NO "url" KEY IN RETURN DICT ← ROOT CAUSE
```

**Critical finding:** `publisher.py` has its OWN `_write_hugo_post()` at line 530 that DOES return a URL. But the import at line 762-770 **overrides** it with `hugo_writer._write_hugo_post()` which does NOT return a URL. The duplicate is in `hugo_writer.py`, not `publisher.py`'s local version.

## Data Flow Diagram

```
                    ┌──────────────────────────────────────────────┐
                    │          pipelines/curation/pipeline.py      │
                    │                                              │
 keyword ─────────→│  _make_slug(keyword) → slug (WRONG for URLs) │
                    │         ↓                                    │
                    │  publish(blog_id, title, body_md, ...)       │
                    │         ↓                                    │
                    │  [publisher.py] → [hugo_writer.py]           │
                    │  _write_hugo_post()                          │
                    │    └─ slug = slugify(title) [CORRECT slug]   │
                    │    └─ writes content/posts/{slug}/index.md   │
                    │    └─ returns {"success": True, "file": ...} │
                    │         ↓                        ↗ NO "url"  │
                    │  result.get("url") = None ───────┘ in return │
                    │         ↓                                    │
                    │  _actual_slug = slug (WRONG fallback!)       │
                    │         ↓                                    │
                    │  register_cuap_entity(post_slug=_actual_slug)│
                    │         ↓                                    │
                    │  post_url = domain/posts/{WRONG_SLUG}/       │
                    │         ↓                                    │
                    │  [NEXT POST] build_cross_sell_card()         │
                    │    └─ reads post_url from cuap_entities      │
                    │    └─ embeds WRONG URL in HTML               │
                    └──────────┬───────────────────────────────────┘
                               │
                               ▼
                    content/posts/{actual-slug}/index.md
                    └─ "🛍️ 이런 상품도 좋아하실 거예요" cross-link card
                         └─ <a href="https://baby.informationhot.kr/posts/20260726-젖병-건조대-추천/">
                         └─ *** 404 — directory jeojbyeong-geonjodae.../ exists, not 20260726-.../
```

## Package Legitimacy Audit

> **Not applicable** — this phase modifies only existing Python code. No external packages are installed.

## Code Locations

### Core Files

| File | Lines | Role |
|------|-------|------|
| `shared/cuap_entity_linker.py` | 1-412 | Entity registration (`register_cuap_entity`), cross-link card generation (`build_cross_sell_card`), funnel header (`build_funnel_header`), in-body link injection (`inject_cross_blog_links`) |
| `shared/publishers/hugo_writer.py` | 820-903 | **`_write_hugo_post()`** — writes Hugo post + frontmatter to disk. Returns `{"success": True, "file": file_path}` — **NO `url` key** |
| `shared/publisher.py` | 762-770 | Import override: re-exports `_write_hugo_post` **FROM** `hugo_writer.py` (replacing local version at line 530) |
| `shared/publisher.py` | 852-1040 | `publish()` — orchestrates slug generation (`slugify(title)`), post writing, and deployment |
| `pipelines/curation/pipeline.py` | 995-1006 | Cross-link injection call site: `inject_cross_blog_links()` + `build_cross_sell_card()` |
| `pipelines/curation/pipeline.py` | 1060-1079 | **Entity registration call site** — where wrong slug gets registered |
| `pipelines/curation/pipeline.py` | 634-638 | `_make_slug(keyword)` — produces `20260726-{keyword}` format (WRONG for cross-links) |
| `pipelines/curation/pipeline.py` | 1037 | `publish()` call — returns `result` dict without `"url"` key |
| `config/blogs.d/cuap.yaml` | — | Config for 10 CUAP blogs |

### Helper/Script Files

| File | Role |
|------|------|
| `scripts/_tmp_fix_stale_cards.py` | Fixes old-format (non-`/posts/`) hrefs in baked cards. Already applied. |
| `scripts/backfill_cuap_entities.py` | Registers entities from on-disk directory names. Uses CORRECT on-disk slugs. |
| `scripts/register_sample_cuap_entities.py` | Test data (hardcoded dummy slugs). |
| `scripts/migrate_ascii_slugs.py` | Korean→ASCII slug migration (not yet executed). |
| `scripts/fix_cuap_entity_urls.py` | Fixes cuap_entities DB URLs. |
| `scripts/fix_cuap_all_entities.py` | Bulk entity management. |

## Root Cause Analysis

### Bug 1: Slug Mismatch — All 4 Cross-Link URLs 404

**Root cause chain:**

1. `pipeline.py:905` — `slug = _make_slug(keyword)` creates keyword-based slug: `20260726-{keyword}`
2. `pipeline.py:1037` — `result = publish(blog_id, title, body_md, ...)` 
3. `publisher.py:988` — `publish()` calls `_write_hugo_post()` which is OVERRIDDEN at line 762-770 by `hugo_writer._write_hugo_post()`
4. `hugo_writer.py:903` — `_write_hugo_post()` returns `{"success": True, "file": file_path}` — **NO `"url"` key**
5. `pipeline.py:1064` — fixes were added: `_actual_slug = result.get("url", "").rstrip("/").split("/")[-1] if result.get("url") else slug` — but `result.get("url")` is **always None** because `hugo_writer._write_hugo_post()` never returns a URL
6. `pipeline.py:1064` — falls back to `slug` (from `_make_slug(keyword)`) = `20260726-{keyword}`
7. `pipeline.py:1072` — `register_cuap_entity(post_slug=_actual_slug)` registers WRONG slug
8. `cuap_entity_linker.py:193` — `post_url = f"{domain}/posts/{post_slug}/"` creates URL with WRONG slug
9. `cuap_entity_linker.py:331` — `build_cross_sell_card()` reads this wrong `post_url` from DB
10. Result: All cross-link URLs point to `domain/posts/20260726-{keyword}/` which doesn't exist on disk

**Why it was thought to be fixed (line 1062-1064):** The comment says "2026-07-22: publish()가 실제로 사용한 slug를 result["url"]에서 추출." But the developer assumed `publisher.py`'s local `_write_hugo_post()` was being called (which returns `"url"`), not realizing it was overridden by `hugo_writer._write_hugo_post()` (which doesn't).

**Evidence:**
- `cuap_entities` DB shows both slug formats:
  - WRONG: `20260726-젖병-브러쉬-추천` (rowid 220, baby-hugo)
  - CORRECT: `jeojbyeong-geonjodae-recommend-...` (rowid 211, baby-hugo)  
- ALL directories on disk use `slugify(title)` format (Korean/Romanized hybrid)
- The `20260726-젖병-건조대-추천` directory does NOT exist on disk

### Bug 2: 4→2 Cross-Link Rendering Drop

**Root cause chain:**

1. `cuap_entity_linker.py:320-331` — `_target_blogs()` returns up to 4 blogs from `CROSS_GRAPH`
2. `cuap_entity_linker.py:324-331` — For each target blog: `conn.execute(... LIMIT 1).fetchone()`
3. `cuap_entity_linker.py:332-333` — If result is None (no published entity): `continue` → link is dropped
4. Result: Only blogs WITH at least one entity in `cuap_entities` appear in the card

**Why it happens:** `build_cross_sell_card()` is called at pipeline.py:998, but entities for OTHER blogs are registered at pipeline.py:1068 (AFTER publish). This creates a window where:
- New blog: No entities at all → all links dropped → empty card
- Blog with few entities: Only blogs that have already published at least once appear
- Blog A published, but its entity was registered with the WRONG slug (Bug 1)

**Current state:** All 10 blogs now have published=1 entities (9-20 per blog). The CURRENT health blog post shows all 4 links. However, the 4→2 still CAN occur if:
- A new blog is added to the system
- Entity registration fails silently (try/except with `fail-open`)
- The `published=1` flag is not set

**Evidence from current data:**
- `cuap_entities` has entities for all 10 blogs (9-20 per blog, all `published=1`)
- Current cross-link card in health blog shows ALL 4 links (with wrong URLs due to Bug 1)

## Existing Published Post Analysis

### Slug Format Comparison

**Frontmatter slug** (from on-disk `index.md`):
```yaml
slug: "jeojbyeong-geonjodae-recommend-mam-aenliteulbebepeullo-u-yug-a-choboleul-wihan-practical-seontaeg"
```
Format: `{romanized-title}` — from `slugify(title)` in `publisher.py:863`
This is what Hugo uses for the actual URL path and directory name.

**Cross-link URL** (from generated HTML card):
```html
<a href="https://baby.informationhot.kr/posts/20260726-젖병-건조대-추천/">
```
Format: `20260726-{keyword}` — from `_make_slug(keyword)` in `pipeline.py:634-638`
This does NOT exist on disk → 404.

**On-disk directory naming:**
```
/Users/twinssn/Projects/cuap/baby-hugo/content/posts/
├── jeojbyeong-geonjodae-recommend-.../     ← CORRECT (matches frontmatter slug)
├── 06gae-wol-agi-yongpum-recommend-.../     ← CORRECT
├── 06개월-아기용품-추천-.../                  ← CORRECT (Korean variant)
└── ...
```
All 400+ posts per blog use the correct `slugify(title)` directory name.

### cuap_entities DB State

| Blog | Published Entities | Correct Slugs | Wrong Slugs (`20260726-{keyword}` format) |
|------|-------------------|---------------|------------------------------------------|
| baby-hugo | 20 | ~18 (romanized/Korean) | ~2 (date-prefixed keyword) |
| beauty-hugo | 19 | ~17 | ~2 |
| fitness-hugo | 17 | ~16 | ~1 |
| kitchen-hugo | 9 | ~8 | ~1 |
| All 10 blogs | ~154 | ~145 | ~9 |

The wrong-slug entities have the HIGHEST rowid (most recent), so `build_cross_sell_card()` picks them first via `ORDER BY rowid DESC`.

## Phase 48 Impact Assessment

**Phase 48** modified `shared/publishers/hugo_writer.py` to fix YAML frontmatter generation (single-quote YAML strategy, `str()` list fix, slug sanitization, etc.).

**Phase 49** modifies:
- `shared/cuap_entity_linker.py` — Entity registration / URL generation
- `pipelines/curation/pipeline.py` — Slug extraction logic
- `shared/publishers/hugo_writer.py` — POTENTIALLY: add `"url"` to return dict
- New batch fix script

**Conflict risk: LOW.** Phase 48 only touched YAML string construction functions. Phase 49 touches the cross-link system and the `_write_hugo_post()` return value. The only shared file is `hugo_writer.py`, but changes are in different functions (frontmatter builders vs `_write_hugo_post()` return value).

**However, if Phase 49 modifies `_write_hugo_post()` in `hugo_writer.py`, ensure:**
1. The existing return value `"file"` key is preserved
2. The `"url"` key is ADDED (not replacing anything)
3. The URL format matches what Hugo generates: `https://{domain}/posts/{slug}/`

## Risk Areas

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **`_write_hugo_post()` URL format mismatch** | MEDIUM | HIGH | Verify URL format matches actual Hugo output (trailing slash, domain encoding) |
| **Batch script corrupts existing correct URLs** | LOW | HIGH | Backup each file before modifying; use diff after; test on single file first |
| **cuap_entities has both correct/wrong slugs** | HIGH | MEDIUM | Fix all existing wrong entities; ensure new entities get correct slugs |
| **Hugo URL encoding of Korean characters** | MEDIUM | MEDIUM | Korean slugs in URL work in Hugo; verify with HTTP HEAD after fix |
| **Race condition: post created between card generation and entity registration** | LOW | LOW | Cross-link card reads OTHER blogs' entities, not current blog's |
| **`published=1` flag not set for new entities** | LOW | HIGH | Verify `published=1` is always set in `register_cuap_entity()` call |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL slug extraction | Custom URL construction | Extract from `result["file"]` path or make `_write_hugo_post()` return URL | File path already contains correct slug |
| Batch fix HTTP check | Custom HTTP checker | `requests.head()` with timeout + retry | Stdlib, handles redirects and errors |
| Cross-link fallback for empty blogs | Empty card | Show blog homepages or hide section | Better UX than empty section |
| Entity slug fix | Manual DB updates | Script that reads on-disk directory names | Ground truth is on disk, not DB |

## Architecture Patterns

### Recommended Project Structure
No structural changes — modifications stay in existing files.

### Pattern 1: Slug Extraction from File Path
For fixes where `result["url"]` is unavailable, extract slug from `result["file"]`:
```python
# result = {"success": True, "file": "/path/to/content/posts/{slug}/index.md"}
_actual_slug = Path(result["file"]).parent.name if result.get("file") else slug
```

### Pattern 2: Return URL from _write_hugo_post()
Add URL to the return dict of `hugo_writer._write_hugo_post()`:
```python
domain = blog_cfg.get("domain", "")
result_url = f"https://{domain}/posts/{slug}/"
return {"success": True, "file": file_path, "url": result_url}
```
This matches what `publisher.py`'s local version already does (line 605, though overridden).

### Anti-Patterns to Avoid
- **Relying on `result["url"]` without verifying it exists**: The `hugo_writer._write_hugo_post()` returns NO URL. Either fix the return value or extract slug differently.
- **Using `_make_slug(keyword)` for entity registration**: Always use the actual on-disk slug from `slugify(title)`, not the keyword-based slug.
- **`LIMIT 1 ORDER BY rowid DESC` without priority**: The top-1 entity may be the wrong one (old format slug). Add priority filtering or slug format validation.

## Common Pitfalls

### Pitfall 1: Dead Import Override
**What goes wrong:** `publisher.py` imports `_write_hugo_post` from `hugo_writer.py` (line 769), overriding the local version at line 530. The local version returns `"url"`, but the imported version doesn't. Future changes are applied to the wrong version.
**Why it happens:** The file has TWO implementations of the same function, one dead (line 530) and one active (imported). Developers fix the dead one.
**How to avoid:** Either remove the dead code from `publisher.py` or ensure BOTH versions return the same keys.
**Warning signs:** `result.get("url")` always returns None; `"url"` key is missing from the returned dict.

### Pitfall 2: Entity Registration After Card Generation
**What goes wrong:** `register_cuap_entity()` is called at line 1068 AFTER `build_cross_sell_card()` at line 998. New posts' entities aren't visible to their OWN cross-link card generation.
**Why it happens:** The cross-link card links to OTHER blogs' posts, so the current blog's entities don't need to be registered yet. But this creates a timing dependency for NEW blogs.
**How to avoid:** N/A for CUAP — all 10 blogs already have entities. For new blogs, run `backfill_cuap_entities.py` first.
**Warning signs:** Cross-link card is empty for a new blog's first few posts.

### Pitfall 3: Korean Characters in Slugs
**What goes wrong:** `slugify(title)` preserves Korean characters. Hugo serves these URLs correctly. But the `_make_slug(keyword)` produces a different Korean format that doesn't match.
**Why it happens:** `_make_slug()` and `slugify()` are different functions with different outputs.
**How to avoid:** Always use `slugify(title)` output (from the actual publish process) for entity URLs.
**Warning signs:** Cross-link URLs don't match on-disk directory names.

## Code Examples

### Fix 1: Make `_write_hugo_post()` Return URL (minimal change)
```python
# In shared/publishers/hugo_writer.py, around line 903:
# ADD URL to return value
domain = blog_cfg.get("domain", "")
result_url = f"https://{domain}/posts/{slug}/"
return {"success": True, "file": file_path, "url": result_url}
```

### Fix 2: Extract Slug from File Path (defensive fallback)
```python
# In pipelines/curation/pipeline.py, around line 1062-1064:
from pathlib import Path

# Try result["url"] first, then result["file"], then fallback
_actual_slug = None
if result.get("url"):
    _actual_slug = result["url"].rstrip("/").split("/")[-1]
elif result.get("file"):
    _actual_slug = Path(result["file"]).parent.name
else:
    _actual_slug = slug  # fallback to _make_slug(keyword)

# OR just use the file path approach (more reliable since ALL _write_hugo_post() forms return "file")
```

### Fix 3: Fix Existing Wrong Entities
```python
# In batch fix script — update all cuap_entities slugs from on-disk directories:
import sqlite3
from pathlib import Path

CUAP_ROOT = "/Users/twinssn/Projects/cuap"
DB = "/Users/twinssn/Projects/5000/data/travel-en.db"
BLOG_DOMAINS = { ... }  # from cuap_entity_linker

conn = sqlite3.connect(DB)
for blog_id in BLOG_DOMAINS:
    posts_dir = Path(CUAP_ROOT) / blog_id / "content" / "posts"
    if not posts_dir.is_dir():
        continue
    for slug_dir in posts_dir.iterdir():
        if not slug_dir.is_dir():
            continue
        actual_slug = slug_dir.name
        domain = BLOG_DOMAINS[blog_id]
        correct_url = f"{domain}/posts/{actual_slug}/"
        conn.execute("""
            UPDATE cuap_entities
            SET post_slug = ?, post_url = ?
            WHERE blog_id = ? AND post_slug != ?
              AND published = 1
              AND (post_slug LIKE ? OR post_slug NOT IN (
                SELECT DISTINCT post_slug FROM cuap_entities WHERE blog_id = ?
              ))
            -- Use entity_name matching as tiebreaker
        """, (actual_slug, correct_url, blog_id, actual_slug, "2026%", blog_id))
conn.commit()
```

### Fix 4: Fix Baked Cross-Link Cards in Existing Posts
```python
# Scan all content/posts/*/index.md files for wrong cross-link URLs
# Replace with correct URLs from cuap_entities (after fixing entities first)
import re
import glob

CUAP_ROOT = "/Users/twinssn/Projects/cuap"
CUAP_BLOGS = ["baby-hugo", "beauty-hugo", ...]  # all 10

# Pattern: href="https://{sub}.informationhot.kr/posts/{WRONG_SLUG}/"
WRONG_HREF_RE = re.compile(
    r'href="https://(\w+)\.informationhot\.kr/posts/([^"/]+)/"'
)

for blog in CUAP_BLOGS:
    for md_file in glob.glob(
        f"{CUAP_ROOT}/{blog}/content/posts/*/index.md"
    ):
        with open(md_file) as f:
            content = f.read()
        # Check if card section exists
        if "이런 상품도 좋아하실 거예요" not in content:
            continue
        # For each wrong href, look up correct URL from cuap_entities
        # (using the link_label as the lookup key)
        new_content = _fix_card_urls(content)
        if new_content != content:
            # backup and write
            ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Entity registered with `_make_slug(keyword)` | Entity registered with `result["url"]` slug | 2026-07-22 (line 1062-1064) | The fix was INEFFECTIVE because `hugo_writer._write_hugo_post()` has no URL |
| `_write_hugo_post` in `publisher.py` (with URL) | Overridden by `hugo_writer._write_hugo_post()` (no URL) | Phase 48 / historically | Created the hidden discrepancy |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Import override at `publisher.py:762-770` is the definitive call path for CUAP blogs | Import Chain | If a different `_write_hugo_post` is called, the slug extraction might work. Verified: `hugo_writer._write_hugo_post()` is called (line 903 returns no URL, which matches the bug observation). |
| A2 | The 4→2 drop is due to missing entities | Bug 2 Analysis | If the drop has a different cause (e.g., HTML truncation, markdown rendering), the fix approach would differ. Verified: `if not row: continue` is the only mechanism that drops items. |
| A3 | Korean slugs work in Hugo URLs | Existing Post Analysis | If Hugo normalizes Korean characters differently, the URL format might need encoding. Verified: existing posts with Korean in directory names serve correctly. |

## Open Questions

1. **Should `_write_hugo_post()` in `hugo_writer.py` be made to return a URL?**
   - What we know: `publisher.py:530`'s local version returns `url`, but it's overridden by `hugo_writer.py:903`'s version which doesn't.
   - What's unclear: Whether adding `url` to the return could break other callers that use only `success` and `file` keys.
   - Recommendation: Add `url` to `hugo_writer._write_hugo_post()` return — it's additive, can't break existing callers.

2. **Should the dead `_write_hugo_post()` in `publisher.py` be removed?**
   - What we know: It's dead code (overridden by import). It has a different implementation.
   - What's unclear: Whether any code path calls it directly without going through the import override.
   - Recommendation: Out of scope for Phase 49. Note for future cleanup.

3. **What's the best fallback for blogs without entities?**
   - Options: (a) link to blog homepage, (b) show fewer links, (c) hide the entire card
   - Recommendation: `build_cross_sell_card()` should already handle this — if fewer than 4 links are available, show what's available. The 4→2 drop is only a problem if the card looks incomplete.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | Code execution | ✓ | 3.14 | — |
| SQLite3 | cuap_entities DB | ✓ | stdlib | — |
| `requests` | HTTP HEAD for batch fix | ✓ | installed | `httpx` or `curl` |
| `hugo` (extended) | Build verification | ✓ | v0.160.1 | — |

**Missing dependencies with no fallback:** None.

## Validation Architecture

> `nyquist_validation` is absent from `.planning/config.json` — treat as enabled.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Verification Method |
|--------|----------|-----------|-------------------|
| PER-REQ-01 | Entity slug matches actual post slug | Unit + DB | Register an entity, verify `post_slug` equals `slugify(title)` output |
| PER-REQ-02 | 4 cross-links render | Integration | Generate card for health-hugo → verify 4 `<a>` tags in HTML |
| PER-REQ-03 | Batch fix script corrects wrong URLs | Integration | Run on 1 test post, verify URLs match on-disk slugs |
| PER-REQ-04 | Fixed URLs return HTTP 200 | E2E | `requests.head()` for each cross-link URL |
| PER-REQ-05 | Hugo build 0 errors | Integration | `hugo --gc --minify --source /path/to/blog` |
| PER-REQ-06 | Phase 48 changes preserved | Regression | `diff` `hugo_writer.py` frontmatter functions before/after |

### Wave 0 Gaps

- [ ] `tests/test_cuap_entity_linker.py` — tests for `build_cross_sell_card()` and `register_cuap_entity()`
- [ ] `tests/test_crosslink_slug.py` — tests for slug correctness after registration

## Security Domain

> Not applicable — this phase modifies content linking logic only. No new authentication, authorization, input validation, or cryptography concerns.

## Sources

### Primary (HIGH confidence)
- [CITED: `shared/cuap_entity_linker.py`] — Full review of entity registration and card generation
- [CITED: `shared/publishers/hugo_writer.py:903`] — `_write_hugo_post()` returns `{"success": True, "file": file_path}` with NO URL
- [CITED: `shared/publisher.py:762-770`] — Import override of `_write_hugo_post` from `hugo_writer.py`
- [CITED: `pipelines/curation/pipeline.py:1062-1064`] — Broken `_actual_slug` extraction
- [CITED: `pipelines/curation/pipeline.py:634-638`] — `_make_slug(keyword)` function
- [CITED: `shared/publisher.py:863`] — `slugify(title)` is the correct slug source
- [CITED: `/Users/twinssn/Projects/5000/data/travel-en.db`] — sqlite3 query of cuap_entities shows both correct/wrong slugs
- [CITED: `/Users/twinssn/Projects/cuap/baby-hugo/content/posts/`] — Actual directory names use `slugify(title)` format
- [CITED: `/Users/twinssn/Projects/cuap/health-hugo/content/posts/kolleseutelol-.../index.md`] — Actual cross-link card HTML shows all 4 URLs with wrong slugs

### Secondary (MEDIUM confidence)
- [CITED: `config/blogs.d/cuap.yaml`] — Blog configuration for 10 CUAP blogs
- [CITED: `scripts/backfill_cuap_entities.py`] — Existing backfill script uses correct on-disk slugs
- [CITED: Phase 48 RESEARCH.md / PLAN.md] — Confirms Phase 48 scope is `hugo_writer.py` only

### Tertiary (LOW confidence)
- None — all claims verified from codebase, DB queries, or on-disk file inspection

## Metadata

**Confidence breakdown:**
- Bug 1 root cause: HIGH — verified by reading `hugo_writer.py:903` return value; confirmed via DB query showing wrong slugs
- Bug 2 root cause: HIGH — verified by reading `build_cross_sell_card()` loop logic; confirmed all 4 links render now
- Import chain: HIGH — verified by reading `publisher.py:762-770` import statements
- Phase 48 impact: HIGH — independent files; no intersection with cross-link code
- Batch fix complexity: MEDIUM — script approach depends on exact URL format and edge cases

**Research date:** 2026-07-26
**Valid until:** Stable — no fast-moving dependencies
