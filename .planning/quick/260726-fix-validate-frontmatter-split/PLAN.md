---
quick_id: 260726-fix-validate-frontmatter-split
slug: fix-validate-frontmatter-split
date: 2026-07-26
description: "Fix _validate_frontmatter naive split('---') regression that breaks YAML when description contains markdown table separators"
---

# Quick Task: Fix _validate_frontmatter split("---") Regression

## Problem

`_validate_frontmatter()` in `shared/publishers/hugo_writer.py:606-618` uses `fm_text.split("---")` to extract YAML content between frontmatter markers. This naively splits on ALL `---` occurrences, including those inside quoted YAML values.

When the description field contains `---` (from markdown table separators captured in the first 200 chars by `_extract_description()`), the split breaks the YAML, causing "unexpected end of stream" errors.

**Affected blogs:** rap3-hugo (3 posts), rap4-hugo (1 post), rap5-hugo (1 post) — 5 total failures.

## Root Cause

**Commit:** `67cc067dc` (2026-06-30) — `publisher.py` → `hugo_writer.py` submodule split

During refactoring, the original `_validate_frontmatter` implementation was replaced:

**Original (correct) — `publisher.py` commit `00a064ad` (2026-05-01):**
```python
def _validate_frontmatter(fm_text):
    if not fm_text.startswith("---"):
        return False, "front matter does not start with ---"
    end = fm_text.find("---", 3)          # Find next "---" after position 3
    if end < 0:
        return False, "front matter has no closing ---"
    fm_body = fm_text[3:end].strip()
    parsed = yaml.safe_load(fm_body)
    ...
```

**Regression — `hugo_writer.py` commit `67cc067dc` (2026-06-30):**
```python
def _validate_frontmatter(fm_text):
    parts = fm_text.split("---")     # Splits on ALL "---" — breaks quoted values
    yaml.safe_load(parts[1])          # Parses truncated YAML
```

## Fix

Revert `_validate_frontmatter` to use `find("---", 3)` instead of `split("---")`.

### File: `shared/publishers/hugo_writer.py`

**Current (broken):**
```python
def _validate_frontmatter(fm_text):
    """간단한 front matter 문법 검증"""
    if not fm_text or "---" not in fm_text:
        return False, "no front matter"
    try:
        import yaml
        parts = fm_text.split("---")
        if len(parts) < 2:
            return False, "invalid yaml"
        yaml.safe_load(parts[1])
        return True, ""
    except Exception as e:
        return False, str(e)
```

**Fixed:**
```python
def _validate_frontmatter(fm_text):
    """간단한 front matter 문법 검증 — find() 기반으로 description 내 --- 분리 방지"""
    if not fm_text or "---" not in fm_text:
        return False, "no front matter"
    try:
        import yaml
        # find("---", 3)로 여는 marker 다음의 첫 번째 ---만 찾음
        # split("---")는 값 안의 ---까지 끊어서 YAML 깨짐 유발
        end = fm_text.find("---", 3)
        if end < 0:
            return False, "no closing front matter ---"
        fm_body = fm_text[3:end].strip()
        if not fm_body:
            return False, "empty front matter"
        parsed = yaml.safe_load(fm_body)
        if not isinstance(parsed, dict):
            return False, "front matter is not a dict"
        return True, ""
    except Exception as e:
        return False, str(e)
```

## Verification

1. Test with description containing `---`:
```python
fm = '---\ntitle: "Test"\ndescription: \'text --- more text\'\nslug: "test"\n---'
assert _validate_frontmatter(fm) == (True, "")
```

2. Test with empty/missing frontmatter:
```python
assert _validate_frontmatter("") == (False, "no front matter")
assert _validate_frontmatter("no markers") == (False, "no front matter")
```

3. Test with malformed YAML:
```python
fm = '---\ntitle: [\n---'
ok, err = _validate_frontmatter(fm)
assert ok == False
```

## Files to Modify

- `shared/publishers/hugo_writer.py` — `_validate_frontmatter()` function (lines 606-618)
