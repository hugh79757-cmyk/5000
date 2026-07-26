# Phase 48 Context — Hugo Frontmatter Generation Fix

> Created: 2026-07-26
> Source: Post-incident analysis of CUAP 10-blog YAML frontmatter failures

---

## Problem

`_build_frontmatter_blowfish()` in `shared/publishers/hugo_writer.py` generates YAML frontmatter that fails under Hugo v0.160.1's stricter YAML parser. Three classes of issues were identified and confirmed across 3,074 files:

### Issue 1: tags/categories use Python `str()` repr

Line 123: `fm += "tags: " + str(tag_list) + "\n"`  
Line 121: `fm += "categories: " + str([category]) + "\n"`

Produces: `tags: "['tag1', 'tag2']"`  
This is a Python string representation, not valid YAML. Hugo parsers this as:
- A single string value `"['tag1', 'tag2']"` instead of a YAML list
- Blowfish theme tries `range` on the string → iterates characters, producing malformed tag display like `[ ' t a g 1 ' ,`

The `_build_frontmatter_papermod()` has the same bug (line 84):
`fm += "tags: " + str(tag_list) + "\n"`

The `_build_frontmatter_congo()` already generates correct YAML flow sequences (lines 44-45):
`fm += "tags: [" + ", ".join('"' + t + '"' for t in tag_list) + "]\n"`

### Issue 2: `_sanitize_yaml_value()` escaping breaks Hugo YAML parser

Lines 14-21:
```python
def _sanitize_yaml_value(s, max_len=None):
    ...
    return s.replace("\\", "\\\\").replace('"', '\\"')
```

This escapes `"` to `\"` inside double-quoted YAML strings. When content (slug, title, description) has trailing backslash-like artifacts from AI generation or inline markdown conversion, the result is a `\"` sequence that Hugo's YAML parser interprets as an escaped quote character. The parser then looks for the closing `"` of the string, consuming all subsequent frontmatter lines, causing "map key-value is pre-defined" errors.

Example: `slug: "some-value\"` — the `\"` at the end is parsed as escaped `"`, so the string value is never terminated.

Affected uses of `_sanitize_yaml_value()`:
- Line 36 (congo): `title: "..."` 
- Line 40 (congo): `description: "..."`
- Line 77 (papermod): `title: "..."`
- Line 82 (papermod): `description: "..."`
- Line 114 (blowfish): `title: "..."`
- Line 118 (blowfish): `description: "..."`

### Issue 3: slug field not sanitized at all

Line 119: `fm += 'slug: "' + slug + '"\n'`  
slug is concatenated directly without any `_sanitize_yaml_value()` call. If slug contains characters that break YAML parsing (double quotes, colons, etc.), the frontmatter becomes invalid.

### Issue 4: Cover block for fallback images (minor)

Lines 131-132, 136-137: Inline `\n` in f-strings for the cover fallback blocks produce potentially inconsistent indentation:
```python
fm += 'cover:\n  image: "' + _url + '"\n'
fm += '  relative: true\n'
```
This works but is fragile compared to the explicit multi-line approach used in the non-fallback path (lines 125-127).

---

## Prior Work

A retrospective fix script `scripts/fix_frontmatter_v3.py` was created and applied to all 3,074 files across 10 CUAP blogs:
- 692 files were fixed (had at least one of the 3 issues)
- The fix converted Python repr lists to YAML flow sequences, stripped trailing `\"` artifacts, and fixed cover block indentation
- This was applied AFTER the files were written, so it was a post-processing band-aid

The Pipeline Fix (Phase 48) is to fix the *generation* code so future posts never produce broken frontmatter.

---

## Required Changes

### 1. `_sanitize_yaml_value()` — Safe YAML escaping

Replace or augment with a function that uses single-quoted YAML strings (safe for content without single quotes):
- If value contains no single quotes (`'`), wrap in single quotes
- If value contains single quotes, wrap in double quotes and escape only `\` and `"`
- Strip any trailing `\` that could break quoting

### 2. `tags` / `categories` — YAML flow sequence

Change from `str(list)` to explicit flow sequence:
- `tags: ["tag1", "tag2"]` instead of `tags: "['tag1', 'tag2']"`
- Each tag value inside the sequence should still be sanitized
- Empty list → `tags: []`

### 3. `slug` — Proper sanitization

Add sanitization to the slug field — same safe-quoting approach as title/description.

### 4. `cover` block — Consistent indentation

Ensure both paths (thumbnail_url present and fallback) produce identical, correctly indented output.

---

## Verification

1. Unit test: Call `_build_frontmatter_blowfish()` with known inputs and validate YAML output
2. Hugo build test: Run `hugo --gc --minify` on a test blog and confirm 0 errors
3. The existing 3,074 already-fixed files should not regress (the fix script was applied to existing files; the code fix prevents new files from having issues)
4. Also fix `_build_frontmatter_papermod()` which has the same `str(tag_list)` bug

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `shared/publishers/hugo_writer.py` | 14-21 | Fix `_sanitize_yaml_value()` — use single-quote YAML strategy |
| `shared/publishers/hugo_writer.py` | 119 | Add sanitization to `slug:` field |
| `shared/publishers/hugo_writer.py` | 121 | `categories:` → YAML flow sequence |
| `shared/publishers/hugo_writer.py` | 123 | `tags:` → YAML flow sequence |
| `shared/publishers/hugo_writer.py` | 83-84 | Fix same `str(tag_list)` in papermod |
| `shared/publishers/hugo_writer.py` | 131-137 | Normalize cover fallback indentation |

---

## Non-goals

- Do NOT add new dependencies (PyYAML, etc.)
- Do NOT change function signatures
- Do NOT modify `_build_frontmatter_congo()` — it already works correctly
- Do NOT modify existing content files — only the generation code
- Do NOT modify `_build_schema_json()`, `_clean_body()`, or any other function in the file
- Do NOT change `_convert_inline_md_to_html()` behavior
