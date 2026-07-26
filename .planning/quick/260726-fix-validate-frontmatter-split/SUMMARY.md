---
quick_id: 260726-fix-validate-frontmatter-split
slug: fix-validate-frontmatter-split
date: 2026-07-26
status: complete
---

# Summary: Fix _validate_frontmatter split("---") Regression

## What was done

Fixed `_validate_frontmatter()` in `shared/publishers/hugo_writer.py` to use regex-based frontmatter extraction instead of naive `split("---")`.

## Root cause

Commit `67cc067dc` (2026-06-30) refactored `publisher.py` → `hugo_writer.py` submodule. During this refactor, `_validate_frontmatter` was rewritten from the original `find("---", 3)` approach to `split("---")`, which naively splits on ALL `---` occurrences including those inside quoted YAML values.

When `_extract_description()` captures markdown table separators (`---`) in the first 200 chars of the body, the `split("---")` breaks the YAML, causing "unexpected end of stream" errors.

## Fix

Replaced `split("---")` with regex `\n---\s*$` (MULTILINE) to find the closing frontmatter marker on its own line, ignoring `---` inside quoted values.

**Before:**
```python
parts = fm_text.split("---")
yaml.safe_load(parts[1])
```

**After:**
```python
if not re.match(r"^---\s*\n", fm_text):
    return False, "front matter does not start with ---"
m = re.search(r"\n---\s*$", fm_text, re.MULTILINE)
if not m:
    return False, "no closing front matter ---"
fm_body = fm_text[4:m.start()].strip()
parsed = yaml.safe_load(fm_body)
```

## Verification

All 6 tests pass:
1. Description with `---` (the bug case) → PASS
2. Empty frontmatter → PASS
3. No markers → PASS
4. Normal frontmatter → PASS
5. Malformed YAML → PASS
6. Real rap3-hugo case with `---` in description → PASS

## Files modified

- `shared/publishers/hugo_writer.py` — `_validate_frontmatter()` function (lines 606-625)

## Impact

Fixes publish failures for rap3-hugo (3 posts), rap4-hugo (1 post), rap5-hugo (1 post) — 5 total failures caused by this regression.
