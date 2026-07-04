# Phase 12: Body Content Rescan & Keyword Validation Gate

## Goal
1. **Body rescan**: Scan full post body (not just title/tags) for blocked keywords, find posts Phase 8 missed (~118 expected).
2. **Keyword validation**: Add guard that prevents generic/non-relevant keywords from being added to any blog.

## Tasks

### Task 12.1: Extend detection script with body scan

**File:** `scripts/phase8/detect_problematic_posts.py`

Add `--scan-body` flag. When set, scan each post's full `index.md` body (after frontmatter) using Korean word-boundary regex `(?<![가-힣]){kw}(?![가-힣])` instead of simple `in` matching.

- Title/tag scan stays same (for backward compat)
- Body scan uses word-boundary regex to eliminate false positives like "도서관" → "도서"
- Output: appended to same `flagged_posts.yaml` with `source: body` field

### Task 12.2: Run body rescan

```bash
cd /Users/twinssn/Projects/5000 && python scripts/phase8/detect_problematic_posts.py --scan-body
```

Catalog results. Do NOT auto-delete (body context is more ambiguous than title).

### Task 12.3: Create keyword validation function

**File:** `pipelines/curation/keywords.py` (append)

```python
def validate_keyword(keyword: str, blog_id: str) -> tuple[bool, str]:
    """Check keyword against blog's CATEGORY_FILTERS allowed list.
    
    Rules:
    1. Must contain at least 1 allowed keyword from blog's CATEGORY_FILTERS
    2. Must NOT contain any blocked keyword
    3. Single generic words (non-brand/non-ingredient) → warning
    
    Returns: (True, "") or (False, "reason: ...")
    """
    from pipelines.curation.pipeline import CATEGORY_FILTERS
    filters = CATEGORY_FILTERS.get(blog_id)
    if not filters:
        return (True, "")
    allowed = filters["allowed"]
    blocked = filters["blocked"]
    kw_lower = keyword.lower()
    
    has_allowed = any(aw.lower() in kw_lower for aw in allowed)
    has_blocked = any(bw.lower() in kw_lower for bw in blocked)
    
    if has_blocked:
        return (False, f"blocked keyword in '{keyword}' for {blog_id}")
    if not has_allowed:
        return (False, f"no allowed keyword in '{keyword}' for {blog_id}")
    return (True, "")
```

### Task 12.4: Add validation call to keyword_expander.py

**File:** `pipelines/curation/keyword_expander.py`

After `update_keywords_py()` generates new keywords, run each through `validate_keyword()` and log warnings for invalid ones.

### Task 12.5: Verify

1. Body rescan yields ~118 new flagged posts
2. `validate_keyword("세럼 추천", "beauty-hugo")` returns True
3. `validate_keyword("개선", "beauty-hugo")` returns False
4. `validate_keyword("가성비", "beauty-hugo")` returns False
5. keyword_expander.py integration does not break existing expansion

## Rollback

| Change | Rollback |
|--------|----------|
| detect script changes | `git checkout HEAD -- scripts/phase8/detect_problematic_posts.py` |
| validate_keyword() | `git checkout HEAD -- pipelines/curation/keywords.py` |
| keyword_expander change | `git checkout HEAD -- pipelines/curation/keyword_expander.py` |
