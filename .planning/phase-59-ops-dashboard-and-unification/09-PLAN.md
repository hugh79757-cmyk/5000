---
phase: 59-ops-dashboard-and-unification
plan: 09
type: execute
wave: 4
depends_on: []
files_modified:
  - shared/publishers/hugo_writer.py
autonomous: true
requirements:
  - etap-write-hugo-comparison
  - etap-wrapper-design
must_haves:
  truths:
    - "ETAP _write_hugo_post versions are compared with shared version"
    - "ETAP-specific features (adsense, cross-sell, internal links) are identified"
    - "Wrapper function design is defined that calls shared + post-processing hooks"
  artifacts:
    - path: "shared/publishers/hugo_writer.py"
      provides: "Enhanced _write_hugo_post with ETAP post-processing hooks"
  key_links:
    - from: "shared/publishers/hugo_writer.py"
      to: "pipelines/etap/*_pipeline.py"
      via: "new _write_hugo_post_etap() wrapper function"
      pattern: "_write_hugo_post_etap"
---

<objective>
Compare ETAP _write_hugo_post versions with the shared version and design a wrapper function that consolidates them.

Purpose: 35 ETAP pipelines each have their own _write_hugo_post with ETAP-specific features (adsense, cross-sell, internal links). The shared version lacks these features. A wrapper function bridges the gap.
Output: Enhanced hugo_writer.py with _write_hugo_post_etap() wrapper
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@shared/publishers/hugo_writer.py
@pipelines/etap/adventure_pipeline.py
@pipelines/etap/flight_pipeline.py
@pipelines/etap/pipeline.py
@.planning/phase-59-ops-dashboard-and-unification/CONTEXT.md
@.planning/phase-59-ops-dashboard-and-unification/RESEARCH.md

<interfaces>
<!-- Shared _write_hugo_post (hugo_writer.py line 908) -->
```python
def _write_hugo_post(blog_cfg, title, body_md, slug, category, tags, thumbnail_url, is_draft=False):
    """Write a Hugo post with theme-aware frontmatter.
    Returns: {"success": bool, "url": str, "file_path": str}
    """
```

<!-- ETAP individual _write_hugo_post (34 files) -->
```python
def _write_hugo_post(article, cover_image=None, body_images=None, blog_id=None, site_path=None, category=None):
    """ETAP version with inject_internal_links, insert_adsense, cross-sell.
    Returns: post_dir (str)
    """
```

<!-- ETAP flight_pipeline _write_hugo_post (1 file) -->
```python
def _write_hugo_post(cfg, article):
    """Simplified version — no cross-sell, no adsense, no internal links.
    Returns: filepath (str)
    """
```

<!-- ETAP-specific features to preserve -->
from pipelines/etap/adventure_pipeline.py:
```python
from shared.content_enhancer import inject_internal_links, insert_adsense
from shared.coupang_senior import build_cross_sell_html, insert_cross_sell_block

# In _write_hugo_post:
content = inject_internal_links(content, current_blog=blog_id, max_links=5)
content = insert_adsense(content)
cross_html = build_cross_sell_html(country=country, city=city, exclude_blog=blog_id, max_items=3)
content = insert_cross_sell_block(content, cross_html, position="bottom")
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Design _write_hugo_post_etap() wrapper in hugo_writer.py</name>
  <files>shared/publishers/hugo_writer.py</files>
  <action>
Add a new wrapper function `_write_hugo_post_etap()` to shared/publishers/hugo_writer.py that combines the shared _write_hugo_post with ETAP-specific post-processing.

**Design principle:** The shared _write_hugo_post handles frontmatter + file write. The ETAP wrapper calls it, then applies ETAP-specific transformations to the written file.

**New function to add (after existing _write_hugo_post at line ~993):**

```python
def _write_hugo_post_etap(blog_cfg, title, body_md, slug, category, tags,
                          thumbnail_url, is_draft=False, country=None, city=None,
                          inject_links=True, inject_ads=True, inject_crosssell=True):
    """ETAP wrapper: calls shared _write_hugo_post + applies ETAP post-processing.

    This function replaces the 35 individual _write_hugo_post copies in
    pipelines/etap/*_pipeline.py. It adds:
    - inject_internal_links() — internal blog cross-linking
    - insert_adsense() — AdSense code injection
    - build_cross_sell_html() + insert_cross_sell_block() — product cross-sell

    Args:
        blog_cfg: Blog configuration dict (same as _write_hugo_post)
        title: Post title
        body_md: Post body in Markdown (will be enhanced before writing)
        slug: URL slug
        category: Post category
        tags: Post tags
        thumbnail_url: Thumbnail image URL
        is_draft: Whether post is a draft
        country: Country name for cross-sell (optional)
        city: City name for cross-sell (optional)
        inject_links: Whether to inject internal links (default True)
        inject_ads: Whether to inject AdSense (default True)
        inject_crosssell: Whether to inject cross-sell blocks (default True)

    Returns:
        dict: {"success": bool, "url": str, "file_path": str}
    """
    # Step 1: Apply ETAP enhancements to body_md BEFORE writing
    enhanced_body = body_md

    if inject_links:
        blog_id = blog_cfg.get("id", "")
        try:
            from shared.content_enhancer import inject_internal_links
            enhanced_body = inject_internal_links(enhanced_body, current_blog=blog_id, max_links=5)
        except ImportError:
            logger.warning("[ETAP] inject_internal_links not available, skipping")

    if inject_ads:
        try:
            from shared.content_enhancer import insert_adsense
            enhanced_body = insert_adsense(enhanced_body)
        except ImportError:
            logger.warning("[ETAP] insert_adsense not available, skipping")

    # Step 2: Write the post using shared _write_hugo_post
    result = _write_hugo_post(blog_cfg, title, enhanced_body, slug, category,
                               tags, thumbnail_url, is_draft=is_draft)

    # Step 3: Post-write cross-sell injection (modifies the written file)
    if inject_crosssell and result.get("success") and result.get("file_path"):
        try:
            from shared.coupang_senior import build_cross_sell_html, insert_cross_sell_block
            cross_html = build_cross_sell_html(
                country=country, city=city,
                exclude_blog=blog_cfg.get("id", ""),
                max_items=3
            )
            if cross_html:
                _inject_cross_sell_into_file(result["file_path"], cross_html)
        except ImportError:
            logger.warning("[ETAP] cross-sell not available, skipping")

    return result


def _inject_cross_sell_into_file(file_path: str, cross_html: str) -> None:
    """Inject cross-sell HTML block at the bottom of a written Hugo post."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Find the end of the content (after last --- frontmatter delimiter)
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[0] + "---" + parts[1] + "---"
            body = parts[2]
            new_content = frontmatter + body + "\n\n" + cross_html + "\n"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            logger.info(f"[ETAP] Cross-sell injected into {file_path}")
    except Exception as e:
        logger.error(f"[ETAP] Failed to inject cross-sell into {file_path}: {e}")
```

**Important constraints:**
- This is ADDITIVE — existing _write_hugo_post is unchanged
- ETAP pipelines will be updated to call this wrapper in Plan 10
- All imports are try/except guarded (graceful degradation)
- The wrapper has the same return format as _write_hugo_post (dict with success/url/file_path)
- flight_pipeline.py has a different signature — handled separately in Plan 10
  </action>
  <verify>
    <automated>cd /Users/twinssn/Projects/5000 && python -c "
from shared.publishers.hugo_writer import _write_hugo_post_etap
import inspect
sig = inspect.signature(_write_hugo_post_etap)
params = list(sig.parameters.keys())
print('Parameters:', params)
assert 'blog_cfg' in params, 'Missing blog_cfg'
assert 'title' in params, 'Missing title'
assert 'body_md' in params, 'Missing body_md'
assert 'slug' in params, 'Missing slug'
assert 'country' in params, 'Missing country'
assert 'inject_links' in params, 'Missing inject_links'
assert 'inject_ads' in params, 'Missing inject_ads'
assert 'inject_crosssell' in params, 'Missing inject_crosssell'
print('PASS: _write_hugo_post_etap wrapper defined')
"</automated>
  </verify>
  <done>
    - _write_hugo_post_etap() function added to hugo_writer.py
    - Wrapper calls shared _write_hugo_post + ETAP post-processing
    - All ETAP features preserved: internal links, adsense, cross-sell
    - Graceful degradation with try/except for missing imports
    - Return format matches shared _write_hugo_post
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Wrapper → shared _write_hugo_post | Wrapper must not break shared function's contract |
| Post-processing → written file | Cross-sell injection modifies file after write |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-59-21 | Tampering | File modification after write | mitigate | _inject_cross_sell_into_file uses same file handle, no race condition |
| T-59-22 | Denial of Service | Import failure | mitigate | All imports guarded with try/except, graceful skip |
</threat_model>

<verification>
- _write_hugo_post_etap() is importable from hugo_writer.py
- Function signature includes all ETAP-specific params (country, city, inject_*)
- Wrapper calls _write_hugo_post then applies post-processing
- All imports are try/except guarded
- Return format is dict with success/url/file_path
</verification>

<success_criteria>
- Wrapper function bridges shared and ETAP-specific functionality
- No changes to existing _write_hugo_post (additive only)
- ETAP pipelines can call the wrapper without changing their logic
- Graceful degradation when ETAP-specific modules are unavailable
</success_criteria>

<output>
Create `.planning/phases/59-ops-dashboard-and-unification/59-09-SUMMARY.md` when done
</output>
