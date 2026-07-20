# Phase 22-C: Funnel Card Implementation (v2 Rewrite)

> **Rewrite rationale:** v1 plan assumed pre-execution state. Implementation exists but has critical flaws discovered during plan-check: batch-publish wipes prior posts' cards (Hugo rebuild overwrites injected HTML), BS4 undeclared in requirements, Korean keyword filter ineffective (no morpheme analyzer), double Hugo build per post.

**Objective:** Fix the 4 critical issues in the existing funnel card implementation with minimal changes. No new files, no new abstractions.

---

## Current State (Already Implemented — Do Not Redo)

| Component | Status | Location |
|-----------|--------|----------|
| Funnel YAML config (6 files) | ✓ Done | `config/blogs.d/{stap,cap,rap,...}.yaml` |
| `_build_and_inject_funnel_cards()` | ✓ Exists (flawed) | `shared/publishers/hugo_writer.py:721` |
| `_write_hugo_post()` integration | ✓ Exists | `shared/publishers/hugo_writer.py:936` |
| `_resolve_funnel_card_post()` w/ thumbnail_url | ✓ Done | `shared/publishers/hugo_writer.py` |
| `_extract_keywords()` + `_keywords_overlap_check()` | ✓ Exists (ineffective) | `shared/publishers/hugo_writer.py:675,705` |
| `_build_funnel_card_html()` (depth + bridge templates) | ✓ Exists | `shared/publishers/hugo_writer.py` |
| `content_enhancer._inject_funnel_links()` deprecated stub | ✓ Done | `shared/publishers/content_enhancer.py:253` |

---

## Issues Found in v1 Implementation

### Issue 1 — BS4 undeclared dependency (silent failure risk)
- `bs4==4.15.0` is installed locally but missing from `requirements.txt`
- `BS4_AVAILABLE` guard at `hugo_writer.py:722` silently skips injection on fresh installs
- **AGENTS.md violation**: "조용한 실패 없음"

### Issue 2 — Double Hugo build (perf waste)
- `_build_and_inject_funnel_cards()` calls `hugo --gc --minify` at `hugo_writer.py:740`
- `deploy.py:84` calls `hugo --gc --minify` again
- For 5-post batch publish: 6 Hugo builds (5 funnel + 1 deploy) instead of 1

### Issue 3 — Batch publish wipes prior posts' cards (CRITICAL)
- Post 1 publish: write .md → Hugo build (whole site) → inject cards into `public/posts/post-1/index.html`
- Post 2 publish: write .md → Hugo build (whole site) → **`public/posts/post-1/index.html` rebuilt from .md, post-1 cards LOST**
- Net effect: only the LAST post in a batch keeps its funnel cards
- This is a design flaw in v1's HTML-level injection approach

### Issue 4 — Korean keyword filter ineffective
- `_extract_keywords()` tokenizes by whitespace, removes stopwords
- Korean is agglutinative: "노트북을", "노트북은", "노트북이" are 3 different tokens
- Jaccard overlap with threshold 0.15 produces near-zero matches for Korean text
- Filter blocks legitimate bridge cards (false negatives)
- No morpheme analyzer (konlpy, mecab) installed — out of scope to add now

### Issue 5 — ETAP 10 pipelines bypass funnel (out of scope)
- 10 ETAP pipelines (`culture`, `phototour`, `hiking`, `airlines`, `tours`, `ghost`, `eurail`, `trains`, `ferry`, `michelin`) each define their own `_write_hugo_post()`
- They do not call the shared `_write_hugo_post()` → no funnel injection
- **Decision: OUT OF SCOPE for Phase 22-C v2.** ETAP refactor tracked separately.

---

## v2 Plan — 3 Waves

### Wave 1 — Fix BS4 dependency declaration

**File:** `requirements.txt`

**Change:** Add `beautifulsoup4>=4.12.0` line.

**Why:** Declares the already-used dependency. Fresh installs and CI environments get BS4 automatically. Removes the silent-skip failure mode.

**Verification:**
- [ ] `pip install -r requirements.txt` succeeds and installs bs4
- [ ] `python3 -c "from bs4 import BeautifulSoup; print('ok')"` passes in fresh venv

---

### Wave 2 — Migrate injection back to markdown-level (fixes Issues 2 + 3)

**Core insight:** v1's HTML-level injection was chosen for "rich card templates" but Hugo's Goldmark passes raw HTML through unchanged. We can inject the same rich HTML cards INTO `body_md` before writing the .md file. Hugo builds once, cards survive batch publishing, no double build.

**Files:** `shared/publishers/hugo_writer.py`

**Changes:**

1. **Rename + repurpose `_build_and_inject_funnel_cards()` → `_build_funnel_cards_md()`**
   - Signature: `_build_funnel_cards_md(blog_cfg, body_md) -> str`
   - Returns: the body_md with depth card HTML appended + bridge card HTML inserted at midpoint
   - No Hugo build, no file I/O, no BeautifulSoup parse of built HTML
   - Still uses `_resolve_funnel_card_post()`, `_build_funnel_card_html()`, `_extract_keywords()`, `_keywords_overlap_check()` as-is

2. **Midpoint insertion (markdown-level)**
   - Split body_md by `\n\n` into paragraphs
   - Insert bridge card after `int(len(paragraphs) * 0.5)` paragraph
   - Rejoin with `\n\n`

3. **Depth card at end**
   - Append depth card HTML to body_md

4. **Call site change in `_write_hugo_post()` (line 924 area)**
   - Before: `content = fm + body_md` at line 924, then post-write `_build_and_inject_funnel_cards()` at line 936
   - After: `body_md = _build_funnel_cards_md(blog_cfg, body_md)` BEFORE `content = fm + body_md`
   - Remove the post-write call at line 936

5. **Remove Hugo build + HTML parsing from `_build_and_inject_funnel_cards()`**
   - Delete lines 739-765 (subprocess.run + BeautifulSoup file parse)
   - Delete container finding logic (lines 767-774)
   - Delete the `f.write(str(soup))` save logic (lines 841-849)

6. **Keep `_extract_keywords()` and `_keywords_overlap_check()`** but see Wave 3.

**Why this works:**
- Hugo's Goldmark renderer passes raw HTML in markdown through to output unchanged
- Cards become part of the .md source of truth — visible in git, editable, reproducible
- Batch publish: each post's .md has its own cards, Hugo builds once, all cards preserved
- Deploy's Hugo build suffices, no second build needed

**Verification:**
- [ ] `requirements.txt` includes bs4 (Wave 1)
- [ ] `python3 -c "import shared.publishers.hugo_writer"` imports cleanly
- [ ] Publish 2 posts to same blog in one batch → BOTH have cards in deployed HTML
- [ ] Hugo build count per publish cycle = 1 (in deploy), not N+1
- [ ] No `subprocess.run([HUGO_PATH...])` call remains in `_build_funnel_cards_md()`

---

### Wave 3 — Disable Korean keyword filter (threshold=0)

**File:** `shared/publishers/hugo_writer.py`

**Change:** In `_keywords_overlap_check()`, change default `threshold=0.15` to `threshold=0.0`.

**Why:** Korean morphological analysis is out of scope. Current stopword-only filter produces false negatives (blocks legitimate bridge cards). threshold=0.0 disables filtering entirely — bridge cards always inject if a target post exists. This is the safe default until a proper morpheme analyzer (konlpy) is added.

**Mark with ponytail comment:** `# ponytail: threshold=0 disables broken Korean filter; install konlpy if precision needed`

**Verification:**
- [ ] Bridge cards inject regardless of keyword overlap
- [ ] Depth cards unaffected (always injected)
- [ ] Comment explains the deferral

---

## Out of Scope

- ETAP 10 pipelines funnel integration (separate refactor)
- Korean morpheme analyzer (konlpy) integration (separate phase)
- Card CSS polish (cards already render with inline styles)
- AI/LLM 2nd-stage context check (Wave 5 of v1 — speculative, skipped per YAGNI)

---

## Rollback Plan

| Scenario | Action |
|----------|--------|
| Markdown-level injection breaks Hugo build | Remove `_build_funnel_cards_md()` call from `_write_hugo_post()`. Cards disappear, pipeline continues. |
| Card HTML renders wrong in Goldmark | Check Hugo `markup.goldmark.parser` config — `unsafe=true` may be needed for raw HTML passthrough. |
| Bridge card at midpoint breaks paragraph flow | Move bridge card to end (same as depth card). |

---

## Execution Order

```
Wave 1 (1 line in requirements.txt) → Wave 2 (hugo_writer.py edits) → Wave 3 (1 line threshold change) → Verify
```

All three waves touch only 2 files: `requirements.txt` and `shared/publishers/hugo_writer.py`.

---

## Post-Execution Verification

1. `python3 -c "from shared.publishers.hugo_writer import _build_funnel_cards_md; print('ok')"`
2. `grep "beautifulsoup4" requirements.txt`
3. `grep "threshold=0.0" shared/publishers/hugo_writer.py`
4. `grep "subprocess.run.*HUGO_PATH" shared/publishers/hugo_writer.py` → should return 0 matches in funnel function
5. Manual publish test: `python3 dispatcher.py stock-hugo` → verify HTML output contains `data-funnel-link` attributes
