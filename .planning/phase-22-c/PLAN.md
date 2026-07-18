# Phase 22-C: Funnel Card Implementation

**Objective:** Move funnel card injection from Markdown level (`content_enhancer.py`) to HTML level (`hugo_writer.py`) with depth/bridge position separation, rich card templates, 2-stage AI context fit check, and deploy coordination.

---

## Prerequisites

- Phase 21 complete (funnel YAML config, data attributes, basic `_inject_funnel_links()`)
- No pending changes on `shared/publishers/hugo_writer.py`, `shared/publishers/content_enhancer.py`, `shared/publishers/deploy.py`, `shared/content_store.py`
- Understanding of PaperMod theme HTML structure (target for BeautifulSoup parsing)

---

## WAVES

### Wave 1 — hugo_writer.py: Post-build HTML injection engine

**Goal:** After `_write_hugo_post()` writes `.md`, run Hugo build, parse output HTML, and inject funnel cards via BeautifulSoup.

**Files to modify:**

| File | Change |
|------|--------|
| `shared/publishers/hugo_writer.py` | Add `_inject_funnel_cards_into_html()` function. Add Hugo build call to `_write_hugo_post()` return path. |

**Detailed steps:**

1. **`_write_hugo_post()` modification (after existing .md writing logic, around line 684)**
   - After `f.write(content)` and the success log, call `_build_and_inject_funnel_cards(site_path, slug, blog_cfg)`
   - Pass `blog_cfg` (already available), `slug`, `site_path` to the new function
   - Guard: only run if `blog_cfg` has `depth_next` or `bridge_to`
   - Guard: wrap in try/except, log warning on failure, do NOT crash publish

2. **New function: `_build_and_inject_funnel_cards(site_path, slug, blog_cfg)`**
   ```python
   def _build_and_inject_funnel_cards(site_path, slug, blog_cfg):
       # 1. Run hugo --gc --minify --source {site_path}
       # 2. Read public/posts/{slug}/index.html with BeautifulSoup
       # 3. Parse article content container
       # 4. Build depth card HTML → insert at bottom of article
       # 5. Build bridge card HTML → insert at 40-60% midpoint
       # 6. Write modified HTML back
   ```

3. **Hugo build execution**
   - `subprocess.run([HUGO_PATH, "--gc", "--minify"], cwd=site_path, ...)` — same as deploy.py:83-87
   - Use existing `HUGO_PATH` from `shared.paths`
   - env: no special vars needed (no wrangler)
   - Timeout: 120s

4. **Article container detection (PaperMod theme)**
   - PaperMod: `<div class="post-content">` contains the rendered article body
   - Fallback: `<article>` tag or first `<main>` → first `<div>` with text content
   - Find all `<p>` elements within the container for midpoint calculation

5. **Bridge card position: 40-60% midpoint**
   - Count `<p>` elements inside article container
   - Insert at `int(total_p * 0.5)` position (middle paragraph)
   - Use `BeautifulSoup` `insert()` on the container tag

6. **Depth card position: bottom of article**
   - `container.append(depth_card_soup)` or insert before last element
   - After all existing content, before any post-content siblings

7. **Modified HTML save**
   - Write `str(soup)` back to `public/posts/{slug}/index.html`
   - No prettify (avoids whitespace changes)

**Verification:**
- [ ] `_write_hugo_post()` returns `{"success": true}` even if card injection fails (graceful degradation)
- [ ] After Wave 1, `public/posts/{slug}/index.html` exists and is valid HTML
- [ ] Hugo build output contains no errors in logs
- [ ] Article HTML structure preserved (no broken tags)

---

### Wave 2 — Card HTML Templates

**Goal:** Create rich funnel card templates with thumbnail, title, excerpt, blog name, CTA, and 5 data attributes.

**Files to modify:**

| File | Change |
|------|--------|
| `shared/publishers/hugo_writer.py` | Add `_build_card_html()` with depth/bridge variants |
| (no new CSS files — inline styles or theme-compatible classes) | |

**Design:**

1. **`_build_card_html(post_info, funnel_type, blog_cfg)`**
   - `post_info` dict from `_resolve_funnel_post()` (title, url, blog_id, slug, thumbnail_url)
   - Returns BeautifulSoup tag or HTML string

2. **Depth card template** ("이 카테고리의 다음 글")
   ```html
   <div class="funnel-card funnel-depth not-prose my-10" data-funnel-link data-source-blog="{src}" data-target-blog="{tgt}" data-funnel-type="depth" data-funnel-id="{id}">
     <div class="funnel-card-inner">
       {thumbnail_html}
       <div class="funnel-card-body">
         <span class="funnel-card-label">이 카테고리의 다음 글</span>
         <h4 class="funnel-card-title">{title}</h4>
         <p class="funnel-card-excerpt">{excerpt}</p>
         <span class="funnel-card-cta">continue reading →</span>
       </div>
     </div>
   </div>
   ```

3. **Bridge card template** ("관련 카테고리 살펴보기")
   - Same structure, different label text, `data-funnel-type="bridge"`
   - Slightly different visual treatment (accent color)

4. **Thumbnail handling**
   - If `post_info` has `thumbnail_url`: render `<img class="funnel-card-thumb" src="...">`
   - If no thumbnail: render placeholder div with blog name initials
   - Use `sanitize_featureimage_url()` for URL safety

5. **CSS classes** (inline `<style>` or theme-compatible)
   - Reuse existing PaperMod utility classes where possible
   - `.funnel-card` — flex row, border, rounded, shadow, hover effect
   - `.funnel-card-inner` — flex container
   - `.funnel-card-thumb` — 120x80px, object-fit cover, rounded
   - `.funnel-card-body` — flex column, padding
   - `.funnel-card-label` — small uppercase label (blog name)
   - `.funnel-card-title` — medium bold, 2-line clamp
   - `.funnel-card-excerpt` — subtle gray, 1-line clamp
   - `.funnel-card-cta` — colored CTA text

**Verification:**
- [ ] Depth card renders with correct label and data attributes
- [ ] Bridge card renders with correct label and data attributes
- [ ] Thumbnail renders when available; placeholder when not
- [ ] Card is responsive (mobile-friendly)
- [ ] CSS doesn't leak outside card container (`.not-prose` guard)

---

### Wave 3 — content_enhancer.py Migration

**Goal:** Migrate funnel logic from `content_enhancer.py` to `hugo_writer.py`. Keep backward compatibility.

**Files to modify:**

| File | Change |
|------|--------|
| `shared/publishers/content_enhancer.py` | Remove `_inject_funnel_links()` export/call. Keep as inert fallback OR remove. |
| `shared/publishers/hugo_writer.py` | Port `_resolve_funnel_post()`, `_build_funnel_link_html()`, `_render_funnel_section()` |
| `shared/publishers/publisher.py` | If funnel hook in `publish()` calls `_inject_funnel_links`, update the call point. |

**Detailed steps:**

1. **Port `_resolve_funnel_post()` to hugo_writer.py** (or keep in content_store.py)
   - Move to `hugo_writer.py` as `_resolve_funnel_card_post()`
   - Extend to return `thumbnail_url` from content.db `articles.thumbnail_url` column
   - Keep fallback import from content_enhancer.py for backward compat (optional)

2. **Port `_build_funnel_link_html()` to hugo_writer.py**
   - Integrate into `_build_card_html()` (Wave 2)
   - The old `<a>` tag version is superseded by rich cards

3. **Port `_render_funnel_section()` to hugo_writer.py**
   - Superseded by HTML-level card template (Wave 2)

4. **Update publisher.py** (if funnel hook exists at line ~789)
   - Change call from `content_enhancer._inject_funnel_links()` to new hugo_writer path
   - Actually: since injection moves to `_write_hugo_post()`, **remove the body_md-level hook entirely**
   - publisher.py publish() should no longer call `_inject_funnel_links()`

5. **Keep `_inject_funnel_links()` in content_enhancer.py** as legacy stub with deprecation warning
   - Log: `"[FUNNEL] _inject_funnel_links is deprecated — card injection moved to hugo_writer.py"`
   - Return body_md unchanged with 0 links

**Verification:**
- [ ] publisher.py publish() no longer calls `_inject_funnel_links()`
- [ ] No import errors from content_enhancer.py changes
- [ ] funnel hook removed from publish() flow (no double injection)

---

### Wave 4 — content_store.py Thumbnail Support

**Goal:** `_resolve_funnel_post()` returns `thumbnail_url` for card rendering.

**Files to modify:**

| File | Change |
|------|--------|
| `shared/content_store.py` OR `shared/publishers/content_enhancer.py` | Add `thumbnail_url` to funnel post query |

**Current query (content_enhancer.py:192-196):**
```sql
SELECT slug, title, published_url, blog_id FROM articles
WHERE blog_id=? AND status='published' AND published_url IS NOT NULL
ORDER BY created_at DESC LIMIT 1
```

**New query:**
```sql
SELECT slug, title, published_url, blog_id, thumbnail_url FROM articles
WHERE blog_id=? AND status='published' AND published_url IS NOT NULL
ORDER BY created_at DESC LIMIT 1
```

**Return dict:**
```python
return {
    "title": row["title"],
    "url": row["published_url"],
    "blog_id": row["blog_id"],
    "slug": row["slug"],
    "thumbnail_url": row.get("thumbnail_url") or "",
}
```

**Verification:**
- [ ] `_resolve_funnel_post()` now returns `thumbnail_url` key
- [ ] No KeyError for rows without thumbnail_url (`.get()` fallback)
- [ ] Card template receives thumbnail_url correctly

---

### Wave 5 — 2-Stage Keyword Context Filter

**Goal:** Prevent bridge card injection when source article context doesn't match target blog topic. 1st stage: keyword overlap (0 AI cost). 2nd stage: optional LLM for borderline cases.

**Files to modify:**

| File | Change |
|------|--------|
| `shared/publishers/hugo_writer.py` | Add `_extract_keywords()`, `_keywords_overlap_check()`, `_contextual_fit_llm()` |
| `config/prompts/_global.yaml` | (optional) Add funnel context fit prompt |

**Detailed steps:**

1. **`_extract_keywords(text, top_n=10)`**
   - Tokenize: split by spaces, lowercase, strip punctuation
   - Filter Korean stop words (`이/가/은/는/을/를/의/에/에서/하다/있다/되다/같다/...`)
   - Filter English stop words (`the/a/an/in/of/to/is/and/...`)
   - Count frequency, return top N keywords as `list[str]`
   - No external libraries — pure Python

2. **`_keywords_overlap_check(src_keywords, tgt_keywords, threshold=0.15)`**
   - `overlap = len(set(src_keys) & set(tgt_keys)) / max(len(set(src_keys | tgt_keys)), 1)`
   - Return `True` (pass) if overlap >= threshold
   - Return `False` (fail) if overlap < threshold → skip bridge card
   - Adjustable threshold via blog_cfg (default 0.15)

3. **`_contextual_fit_llm(src_body, tgt_keywords, tgt_blog_name)` — optional 2nd stage**
   - Only called when overlap is between 0.10 and 0.25 (borderline zone)
   - Configurable sampling rate: `blog_cfg.get("funnel_llm_sample", 0.1)` — 10% default
   - Use `openai.ChatCompletion.create()` with minimal prompt
   - Prompt: `"Does the topic of this article fit well with [{blog_name}]? Answer YES or NO only.\n\nArticle: {src_body[:1000]}"`
   - Return `True` if "YES", `False` if "NO"
   - On API error: default to `True` (allow through)

4. **Integration in card injection flow**
   - Before building bridge card: extract keywords from source article body
   - Get target post info (already from `_resolve_funnel_post()`)
   - Extract keywords from target post title + excerpt
   - Run `_keywords_overlap_check()` → if fail, skip bridge card
   - Optionally run `_contextual_fit_llm()` for borderline cases

5. **depth cards skip context check** — depth is always same-category, always relevant

**Verification:**
- [ ] Keyword extraction returns non-empty results for Korean text
- [ ] Overlap check correctly filters clearly mismatched topics
- [ ] LLM check (when enabled) doesn't crash pipeline on API error
- [ ] Depth cards always inserted regardless of context check
- [ ] Sampling rate configurable, defaults to 10%

---

### Wave 6 — deploy.py Skip-build Coordination

**Goal:** Prevent double Hugo build when `_write_hugo_post()` already ran it.

**Files to modify:**

| File | Change |
|------|--------|
| `shared/publishers/deploy.py` | Add pre-build check in `_deploy_site_inner()` |

**Approach: File-based signal (simplest, survives process boundary)**

1. **Signal file convention**
   - After `_write_hugo_post()` runs Hugo build successfully, touch a sentinel file:
     `{site_path}/.hugo_built_{slug}` (empty marker file)
   - Or more globally: `{site_path}/.hugo_built` (timestamp file)

2. **`_deploy_site_inner()` modification**
   - Before running `subprocess.run([HUGO_PATH, "--gc", "--minify"], ...)`:
     - Check if `{site_path}/.hugo_built` exists and is recent (< 5 minutes old)
     - If yes: **skip** Hugo build, log "skipping hugo build (already done by _write_hugo_post)"
     - If no: run Hugo build normally
   - After successful Hugo build: touch `.hugo_built` file

3. **Safety**
   - Stale sentinel (older than 5 min) = rebuild (catches edge cases)
   - No sentinel = full build (backward compat for non-funnel posts)
   - `deploy_site()` is called after ALL posts in a batch are written, so the last post's build suffices

4. **Alternative (simpler): Always rebuild, but use `--themesDir` cache**
   - Hugo incremental build is fast (1-3s for small sites)
   - Could just always rebuild and accept the tiny cost
   - Decision: if Hugo build time per site < 3s, skip the complexity of skip-build
   - **Default: always rebuild (simple), add skip-build only if performance issue arises**

**Verification:**
- [ ] deploy_site() succeeds with pre-built site
- [ ] Hugo rebuild doesn't break cards (cards are in public/ which is rebuilt)
- [ ] No duplicate wrangler deploys

---

## Verification Plan (Post-All-Waves)

1. **Unit: Card injection**
   - Deploy a test post via `_write_hugo_post()` with depth_next/bridge_to configured
   - Verify `public/posts/{slug}/index.html` contains:
     - 1x depth card at bottom with `data-funnel-type="depth"`
     - 1x bridge card at 40-60% position with `data-funnel-type="bridge"`
     - All 5 data attributes present

2. **Unit: No funnel = no change**
   - Deploy a post from blog without funnel config
   - Verify HTML is unchanged (no funnel-related markup)

3. **Unit: Bridge jump guard**
   - Landing blog with bridge_to → verify depth card only, no bridge card
   - Non-landing blog → verify both cards present

4. **Integration: publisher.py flow**
   - Run full pipeline: `python dispatcher.py {funnel_blog_id}`
   - Verify post is published AND cards appear in deployed HTML
   - Verify no pipeline crash if card injection fails

5. **Integration: deploy coordination**
   - Run publish → deploy sequence
   - Verify no double Hugo build (or verify second build is incremental/no-op)

6. **Edge: Thumbnail missing**
   - Resolve post without thumbnail_url → card renders with placeholder
   - No broken image in HTML

7. **Edge: Context filter active**
   - Source article about cars → bridge card to finance → keyword overlap < 0.15 → skip bridge
   - Source article about stock → bridge card to finance → keyword overlap > 0.15 → inject bridge
   - LLM sample enabled → borderline cases checked without crash

---

## Rollback Plan

| Scenario | Action |
|----------|--------|
| Card injection crashes publish | Remove funnel card call from `_write_hugo_post()`. Funnel links fall back to Phase 21 markdown-level behavior. |
| BeautifulSoup parsing error | try/except → log warning → return original HTML (no cards, no crash) |
| Hugo build in hugo_writer breaks existing sites | Remove the Hugo build call from `_write_hugo_post()`. deploy.py builds normally. No cards (back to Phase 21). |
| Context filter wrongly blocks good bridge | Disable filter by setting `threshold=0.0` in blog_cfg or removing the check |
| deploy.py double-build causes delay | Remove sentinel check → always rebuild (2-3s cost per site, acceptable) |

---

## Files Summary

| Wave | Files Changed | Nature of Change |
|------|---------------|------------------|
| W1 | `hugo_writer.py` | Add Hugo build + BeautifulSoup injection engine |
| W2 | `hugo_writer.py` | Add card HTML templates |
| W3 | `content_enhancer.py`, `publisher.py` | Remove body_md funnel hook, migrate logic |
| W4 | `content_enhancer.py` or `content_store.py` | Add thumbnail_url to query |
| W5 | `hugo_writer.py` | Add keyword + LLM context filters |
| W6 | `deploy.py` | Optional: skip-build coordination |

**No new files.** All changes are modifications to existing files.

---

## Execution Order

```
Wave 1 → Wave 2 → Wave 3 → Wave 4 → Wave 5 → Wave 6 → Verification
```

Waves 2 and 4 can run in parallel (independent). Waves 1 and 3 are sequential (W1 adds engine, W3 removes old code). Wave 5 depends on W1+W2 (needs injection engine + cards). Wave 6 is independent.
