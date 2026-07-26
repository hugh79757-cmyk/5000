# Phase 48 Plan: Hugo Frontmatter Generation Fix

## Overview

Fix `_sanitize_yaml_value()`, `_build_frontmatter_blowfish()`, `_build_frontmatter_papermod()`, and `_build_frontmatter_congo()` in `shared/publishers/hugo_writer.py` to generate Hugo v0.160.1 compatible YAML frontmatter.

**Blogs affected:** ~63 total (57 Blowfish, 6 PaperMod, 1 Congo), ~35 actively publishing daily.

**Root cause:** `str(list)` for tags/categories produces Python repr instead of YAML flow sequences. `_sanitize_yaml_value()` escaping `"` → `\"` inside double-quoted YAML strings creates trailing `\"` artifacts that Hugo's `goccy/go-yaml` (since v0.152.0) rejects.

**Success criteria:**
1. All 3 frontmatter builders generate YAML that passes `yaml.safe_load()`
2. No `str(list)` output anywhere in frontmatter
3. All string fields properly sanitized without broken escaping
4. Hugo build on a test blog produces 0 errors
5. Existing 3,074 already-fixed files remain valid post-fix

---

## Tasks

### Wave 1: Core fix — `_sanitize_yaml_value()` (1 file, ~7 lines)

**File:** `shared/publishers/hugo_writer.py`

**Task 1.1 — Rewrite `_sanitize_yaml_value()`**

Current (line 14-21):
```python
def _sanitize_yaml_value(s, max_len=None):
    if s is None:
        return ""
    s = str(s)
    if max_len:
        s = s[:max_len]
    return s.replace("\\", "\\\\").replace('"', '\\"')
```

Replace with single-quote-safe YAML strategy:
```python
def _sanitize_yaml_value(s, max_len=None):
    if s is None:
        return ""
    s = str(s)
    if max_len:
        s = s[:max_len]
    # Strip trailing/leading backslash artifacts that break YAML quoting
    s = s.strip()
    for _ in range(3):
        if s.endswith('\\') and not s.endswith('\\\\'):
            s = s[:-1]
        else:
            break
    for _ in range(3):
        if s.startswith('\\') and not s.startswith('\\\\'):
            s = s[1:]
        else:
            break
    # Use single-quoted YAML when safe (no single quotes in value)
    # Single-quoted YAML means NO escaping inside — literal content
    if "'" in s:
        # Fall back to double-quoted with safe escaping
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    else:
        return f"'{s}'"
```

This function now returns a *wrapped* value (with quotes). All callers must be updated to NOT add their own quotes.

**Validation:** Call with edge cases → verify output.
- Input `hello` → `'hello'`
- Input `it's good` → `"it's good"` (no trailing `\"`)
- Input `value\` → `'value'` (trailing `\` stripped)
- Input `value\\` → `'value\\'` (double backslash preserved)
- Input `value"quote` → `"value\"quote"` (double-quoted fallback)

---

### Wave 2: Fix `_build_frontmatter_blowfish()` (1 file, ~12 lines)

**File:** `shared/publishers/hugo_writer.py`, lines 98-140

**Task 2.1 — Fix title line (line 114)**

Current:
```python
fm += 'title: "' + _sanitize_yaml_value(title) + '"\n'
```
Fix — `_sanitize_yaml_value()` now returns pre-quoted value:
```python
fm += 'title: ' + _sanitize_yaml_value(title) + '\n'
```

**Task 2.2 — Fix description line (line 117-118)**

Current:
```python
fm += 'description: "' + _sanitize_yaml_value(description, max_len=200) + '"\n'
```
Fix:
```python
fm += 'description: ' + _sanitize_yaml_value(description, max_len=200) + '\n'
```

**Task 2.3 — Fix slug line (line 119)**

Current (no sanitization at all!):
```python
fm += 'slug: "' + slug + '"\n'
```
Fix — add sanitization:
```python
fm += 'slug: ' + _sanitize_yaml_value(slug) + '\n'
```

**Task 2.4 — Fix categories line (line 121)**

Current:
```python
fm += "categories: " + str([category]) + "\n"
# Produces: categories: "['category']" — Python repr!
```
Fix — YAML flow sequence:
```python
if category:
    fm += 'categories: [' + _sanitize_yaml_value(category) + ']\n'
```
Note: `_sanitize_yaml_value()` returns `'category'` (single-quoted) or `"category"` (double-quoted), so the result is `categories: ['category']` or `categories: ["cat'egory"]`.

**Task 2.5 — Fix tags line (line 123)**

Current:
```python
fm += "tags: " + str(tag_list) + "\n"
# Produces: tags: "['tag1', 'tag2']" — Python repr!
```
Fix — YAML flow sequence:
```python
if tag_list:
    fm += "tags: [" + ", ".join(_sanitize_yaml_value(t) for t in tag_list) + "]\n"
```

**Task 2.6 — Normalize cover fallback blocks (lines 129-138)**

Current: uses inline `\n` in f-strings for fallback cover blocks:
```python
fm += 'cover:\n  image: "' + _url + '"\n'
fm += '  relative: true\n'
```
Fix — use same multi-line approach as non-fallback path (lines 125-127):
```python
fm += "cover:\n"
fm += '  image: ' + _sanitize_yaml_value(_url) + '\n'
fm += '  relative: true\n'
```

---

### Wave 3: Fix `_build_frontmatter_papermod()` (1 file, ~8 lines)

**File:** `shared/publishers/hugo_writer.py`, lines 61-95

**Task 3.1 — Fix title line (line 77)**

Same pattern as blowfish:
```python
fm += 'title: ' + _sanitize_yaml_value(title) + '\n'
```

**Task 3.2 — Fix description line (line 82)**

```python
fm += 'description: ' + _sanitize_yaml_value(description, max_len=200) + '\n'
```

**Task 3.3 — Fix tags line (line 84)**

Current:
```python
fm += "tags: " + str(tag_list) + "\n"
```
Fix:
```python
if tag_list:
    fm += "tags: [" + ", ".join(_sanitize_yaml_value(t) for t in tag_list) + "]\n"
```

(Note: papermod categories line 86 uses `['" + category + "']` which is already correct YAML. No change needed.)

**Task 3.4 — Fix cover block lines (line 89-92)**

Use sanitized values:
```python
fm += '  image: ' + _sanitize_yaml_value(thumbnail_url) + '\n'
fm += '  relative: true\n'
fm += '  alt: ' + _sanitize_yaml_value(title) + '\n'
```

---

### Wave 4: Fix `_build_frontmatter_congo()` (1 file, ~5 lines)

**File:** `shared/publishers/hugo_writer.py`, lines 23-58

Note: Congo already generates correct YAML flow sequences for tags (lines 44-45). Only escaping and slug fixes needed.

**Task 4.1 — Fix title line (line 36)**

```python
fm += 'title: ' + _sanitize_yaml_value(title) + '\n'
```

**Task 4.2 — Fix description line (line 40)**

```python
fm += 'description: ' + _sanitize_yaml_value(description, max_len=200) + '\n'
```

**Task 4.3 — Fix slug line (line 41)**

Current (no sanitization):
```python
fm += 'slug: "' + slug + '"\n'
```
Fix:
```python
fm += 'slug: ' + _sanitize_yaml_value(slug) + '\n'
```

**Task 4.4 — Fix tags line (line 45)**

Current:
```python
fm += "tags: [" + ", ".join('"' + t + '"' for t in tag_list) + "]\n"
```
Fix — use `_sanitize_yaml_value()` for each tag (it returns pre-quoted):
```python
if tag_list:
    fm += "tags: [" + ", ".join(_sanitize_yaml_value(t) for t in tag_list) + "]\n"
```

---

### Wave 5: Validation hardening (1 file, ~10 lines)

**File:** `shared/publishers/hugo_writer.py`

**Task 5.1 — Make `_validate_frontmatter()` blocking (lines 856-858)**

Current — warning only:
```python
_ok, _err = _validate_frontmatter(fm)
if not _ok:
    logger.warning(f"[PUBLISH] Invalid front matter: {_err}")
```

Fix — make it a hard error:
```python
_ok, _err = _validate_frontmatter(fm)
if not _ok:
    logger.error(f"[PUBLISH] Invalid front matter: {_err}")
    return {"success": False, "error": f"invalid_frontmatter: {_err}"}
```

---

### Wave 6: Verification

**Task 6.1 — Python YAML validation test**

Run a Python one-liner to verify frontmatter output:
```python
python3 -c "
import sys; sys.path.insert(0, '.')
from shared.publishers.hugo_writer import _build_frontmatter_blowfish
import yaml

# Test 1: normal case
fm, _ = _build_frontmatter_blowfish('Test Title', 'test-slug', 'Category', 'tag1,tag2', '', 'A description', blog_id='test')
parts = fm.split('---')
if len(parts) >= 2:
    parsed = yaml.safe_load(parts[1])
    assert parsed['title'] == 'Test Title', f'title mismatch: {parsed[\"title\"]}'
    assert parsed['slug'] == 'test-slug', f'slug mismatch'
    assert parsed['tags'] == ['tag1', 'tag2'], f'tags: {parsed[\"tags\"]}'
    print('TEST 1 PASS: normal case')
else:
    print('TEST 1 FAIL: no frontmatter')

# Test 2: trailing backslash
fm, _ = _build_frontmatter_blowfish('Title\\', 'slug\\', 'Cat', 'tag1', '', 'Desc\\', blog_id='test')
parts = fm.split('---')
parsed = yaml.safe_load(parts[1])
assert parsed['title'] == 'Title', f'title: {parsed[\"title\"]}'
assert parsed['slug'] == 'slug', f'slug: {parsed[\"slug\"]}'
print('TEST 2 PASS: trailing backslash stripped')

# Test 3: single quote in value
fm, _ = _build_frontmatter_blowfish(\"It's good\", \"it's-slug\", 'Cat', \"tag'1,tag2\", '', \"It's desc\", blog_id='test')
parts = fm.split('---')
parsed = yaml.safe_load(parts[1])
assert parsed['title'] == \"It's good\", f'title: {parsed[\"title\"]}'
assert \"tag'1\" in parsed['tags'], f'tags: {parsed[\"tags\"]}'
print('TEST 3 PASS: single quote in value')

# Test 4: empty tags
fm, _ = _build_frontmatter_blowfish('Title', 'slug', 'Cat', '', '', '', blog_id='test')
parts = fm.split('---')
parsed = yaml.safe_load(parts[1])
print('TEST 4 PASS: empty tags')

print('ALL TESTS PASSED')
"
```

**Task 6.2 — Hugo build test**

```bash
# Pick one blog (e.g., appliance-hugo from CUAP)
cd /Users/twinssn/Projects/cuap/appliance-hugo
hugo --gc --minify 2>&1 | tail -20
# Expect: 0 errors
```

**Task 6.3 — Blog suite test**

Run Hugo build on all 10 CUAP blogs to verify no regression:
```bash
for blog in appliance-hugo baby-hugo beauty-hugo camping-hugo fitness-hugo health-hugo interior-hugo kitchen-hugo laptop-hugo pet-hugo; do
    echo "=== $blog ==="
    hugo --gc --minify --source "/Users/twinssn/Projects/cuap/$blog" 2>&1 | tail -3
done
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `_sanitize_yaml_value()` changes break existing callers | Medium | High | Audit all 3 callers before/after; run Hugo build on all blogs |
| Single-quote YAML breaks on values with newlines or special chars | Low | Medium | Hugo YAML spec supports single quotes for multi-line; test with edge cases |
| PaperMod cover block indent regression | Low | Low | Visual comparison of generated frontmatter |
| Hugo build already passing blogs break | Low | High | Run full blog suite (Task 6.3) before committing |
| Existing 3,074 files not regenerated correctly | Low | Low | They were already fixed by `fix_frontmatter_v3.py` — generator change only affects NEW files |

## Rollback Plan

1. `git diff` to see all changes in `shared/publishers/hugo_writer.py`
2. `git checkout -- shared/publishers/hugo_writer.py` to revert
3. Run Hugo build to confirm rollback works (expected: existing files still build fine since generator only affects new files)

---

## Estimated Effort

| Wave | Description | Est. Time | Files |
|------|-------------|-----------|-------|
| W1 | `_sanitize_yaml_value()` rewrite | 5 min | 1 |
| W2 | Blowfish frontmatter builder | 10 min | 1 |
| W3 | PaperMod frontmatter builder | 5 min | 1 |
| W4 | Congo frontmatter builder | 5 min | 1 |
| W5 | Validation hardening | 5 min | 1 |
| W6 | Verification | 15 min | N/A |
| **Total** | | **45 min** | **1 file** |
