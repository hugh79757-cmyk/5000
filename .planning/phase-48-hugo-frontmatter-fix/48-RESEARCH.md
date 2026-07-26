# Phase 48: Fix Hugo Frontmatter Generation — Research

**Researched:** 2026-07-26
**Domain:** YAML frontmatter generation for Hugo static sites
**Confidence:** HIGH

## Summary

The file `shared/publishers/hugo_writer.py` has three frontmatter builder functions (`_build_frontmatter_blowfish`, `_build_frontmatter_papermod`, `_build_frontmatter_congo`) that generate YAML frontmatter with known correctness issues. Two of the three functions (blowfish and papermod) have the `str(list)` bug that produces Python string representations instead of YAML flow sequences for tags and categories. The `_sanitize_yaml_value()` helper uses an overly aggressive double-quote escaping strategy (`"` → `\"`) that creates trailing escape artifacts which break Hugo v0.160.1's stricter YAML parser (`goccy/go-yaml`). Additionally, slug values in blowfish and congo are concatenated without any sanitization.

**Primary recommendation:** Replace the double-quote-only escaping strategy with a single-quote-first approach for `_sanitize_yaml_value()`, emit proper YAML flow sequences for tags/categories instead of `str(list)`, and add slug sanitization. This aligns with the fix strategy already proven in `scripts/fix_frontmatter_v3.py`.

## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **Safe YAML quoting**: Replace `_sanitize_yaml_value()` to use single-quoted YAML strings when possible (no single quotes in value), double-quoted with escaping only when value contains single quotes
2. **`str(list)` → YAML flow sequence**: Change `tags`/`categories` generation in blowfish and papermod to emit `["tag1", "tag2"]` instead of `str(tag_list)`
3. **Empty lists → `tags: []`**: Empty tag/category lists should produce `tags: []` not `tags:` or `tags: ""`
4. **Slug sanitization**: Add proper sanitization to slug field in all three builders
5. **Cover block consistency**: Normalize fallback cover path indentation to match the explicit multi-line approach

### Files to Modify (locked)

| File | Change |
|------|--------|
| `shared/publishers/hugo_writer.py` lines 14-21 | Fix `_sanitize_yaml_value()` |
| `shared/publishers/hugo_writer.py` line 119 | Add slug sanitization (blowfish) |
| `shared/publishers/hugo_writer.py` line 121 | Fix `categories:` in blowfish |
| `shared/publishers/hugo_writer.py` line 123 | Fix `tags:` in blowfish |
| `shared/publishers/hugo_writer.py` lines 83-84 | Fix `tags:` in papermod |
| `shared/publishers/hugo_writer.py` lines 131-137 | Normalize cover fallback indentation |

### Non-goals (locked)

- Do NOT add new dependencies (PyYAML, etc.)
- Do NOT change function signatures
- Do NOT modify `_build_frontmatter_congo()` — already correct
- Do NOT modify existing content files
- Do NOT modify `_build_schema_json()`, `_clean_body()`, or any other function
- Do NOT change `_convert_inline_md_to_html()` behavior

### the agent's Discretion

- Whether to also fix `_validate_frontmatter()` to block writes on invalid YAML (currently only logs warning — see Risk #4)
- Whether to fix the same issues in `shared/publisher.py`'s local (overridden) frontmatter functions (they're dead code but could confuse future readers)
- Whether to add a regression test for frontmatter generation

### Deferred Ideas (OUT OF SCOPE)

- None explicitly listed

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| YAML frontmatter generation | Pipeline (shared lib) | — | Generated at publish time in the Python pipeline, not at build time |
| Hugo YAML parsing | Hugo binary | — | Hugo v0.160.1 uses `goccy/go-yaml` — the parser that rejects malformed output |
| Fix script (post-hoc) | CLI tool | — | `scripts/fix_frontmatter_v3.py` — one-time fix, not part of pipeline |
| Frontmatter validation | Pipeline (shared lib) | Hugo build | `_validate_frontmatter()` runs before write, but only logs warning (not blocking) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.14 | Runtime | Project constraint |
| Hugo (extended) | v0.160.1 | Static site generator | Project constraint — YAML parser is the consumer |
| `yaml.safe_load` | stdlib via PyYAML | Frontmatter validation | Used in `_validate_frontmatter()` — no new deps |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `ast.literal_eval` | stdlib | Parse Python repr strings | Only in fix script — not needed in generation code |

**There are no new dependencies for this phase. The fix uses only Python stdlib `yaml` (already imported).**

## Package Legitimacy Audit

> **Not applicable** — this phase modifies only existing Python stdlib code. No external packages are installed.

## Blog Count per Theme

### Theme → Function Mapping

| Theme | Builder Function | File Location | Tags/Categories Strategy |
|-------|-----------------|---------------|--------------------------|
| `blowfish` (case-insensitive) | `_build_frontmatter_blowfish()` | `hugo_writer.py:98` | `str(list)` — **BROKEN** |
| `PaperMod` (case-insensitive) | `_build_frontmatter_papermod()` | `hugo_writer.py:61` | `str(tag_list)` + manual `categories` — tags **BROKEN**, categories OK |
| `congo` (case-insensitive) | `_build_frontmatter_congo()` | `hugo_writer.py:23` | Proper flow sequences — **ALREADY CORRECT** |
| Default (no theme) | `_build_frontmatter_papermod()` | `hugo_writer.py:831` | Same as PaperMod — tags **BROKEN** |

### Blog Count Detail

**Blowfish blogs** (use `_build_frontmatter_blowfish` — **both tags and categories broken**):
| Group | Count | Active | Config File |
|-------|-------|--------|-------------|
| CUAP (appliance, baby, fitness, interior, laptop, health, pet, kitchen, beauty, camping) | 10 | 10 active | `config/blogs.d/cuap.yaml` |
| CAP (compare, deal, ev, guide, tco, rank, pick) | 7 | 3 active (compare, rank, pick) | `config/blogs.d/cap.yaml` |
| STAP (finance, dividend, etf, sector, ipo) | 5 | 5 active | `config/blogs.d/stap.yaml` |
| RAP (rap, rap2, rap3, rap4, rap5) | 5 | 5 active | `config/blogs.d/rap.yaml` |
| SEAP (senior) | 1 | 1 active | `config/blogs.d/seap.yaml` |
| TAP (travel, travel1, travel2, travel3, travel4) | 5 | 5 active | `config/blogs.d/tap.yaml` |
| ETAP (adventure, airlines, airports, bus, cruise, culture, daytrips, deals, dining, esim, eurail, ferry, flights, foodtour, michelin, multiday, nature, phototour, tour, tours, trains, transfers, visa, visafree, walking, watersports, luxury, citytours, watertours, hiking, escape, extreme, nightlife, ghost, layover, nomad) | ~34 | **mostly inactive** | `config/blogs.d/etap.yaml` |
| **Blowfish total** | **~57** | **~29 active** | |

**PaperMod blogs** (use `_build_frontmatter_papermod` — **tags broken only**):
| Group | Count | Active | Config File |
|-------|-------|--------|-------------|
| CAP (hotissue-hugo) | 1 | 1 active | `config/blogs.d/cap.yaml` |
| Manual (rotcha-blog, informationhot-hugo, techpawz-hugo, biz-techpawz-hugo, issue-techpawz-hugo) | 5 | 5 active | `config/blogs.d/manual_blog_for_backup.yaml` |
| **PaperMod total** | **~6** | **6 active** | |

**Congo blogs** (use `_build_frontmatter_congo` — **already correct**):
| Group | Count | Active | Config File |
|-------|-------|--------|-------------|
| STAP (stock-hugo) | 1 | 1 active | `config/blogs.d/stap.yaml` |
| **Congo total** | **1** | **1 active** | |

**Blogs affected by frontmatter fixes: ~63 total** (57 blowfish + 6 PaperMod), of which ~35 are actively publishing daily.

## Complete Issue Inventory

### Issue 1: `str(list)` for Tags (blowfish + papermod)

**Location:**
- `hugo_writer.py:123` (blowfish): `fm += "tags: " + str(tag_list) + "\n"`
- `hugo_writer.py:84` (papermod): `fm += "tags: " + str(tag_list) + "\n"`

**Produces:**
```yaml
tags: "['tag1', 'tag2']"   # A single string, not a list!
```

**Hugo behavior:** Hugo's YAML parser reads this as the string value `"['tag1', 'tag2']"` (with quotes stripped to `['tag1', 'tag2']`). When Blowfish/PaperMod templates iterate with `range`, they iterate over characters, producing broken tag display.

**Congo status:** Already correct — line 45: `fm += "tags: [" + ", ".join('"' + t + '"' for t in tag_list) + "]\n"`

### Issue 2: `str(list)` for Categories (blowfish only)

**Location:**
- `hugo_writer.py:121` (blowfish): `fm += "categories: " + str([category]) + "\n"`

**Produces:**
```yaml
categories: "['가전제품']"   # A single string, not a list!
```

**PaperMod status:** Already correct — line 86: `fm += "categories: ['" + category + "']\n"`

### Issue 3: `_sanitize_yaml_value()` Double-Quote Escaping Breaks YAML

**Location:** `hugo_writer.py:14-21`

**Current code:**
```python
def _sanitize_yaml_value(s, max_len=None):
    ...
    return s.replace("\\", "\\\\").replace('"', '\\"')
```

**Problem:** When content has trailing backslash artifacts (from AI generation, markdown conversion, or just edge cases), the result produces `\"` at the end of a double-quoted YAML string. Hugo's YAML parser interprets `\"` as an escaped quote character, so it continues looking past the intended closing `"`, consuming subsequent frontmatter lines until it hits the next `"` — causing "map key-value is pre-defined" errors.

**Example broken output:**
```yaml
slug: "some-product-name\"    # \" consumed as escape, string never closes
```

**Affected invocations (all three builders):**

| Builder | Line | Field | Current Output |
|---------|------|-------|----------------|
| congo | 36 | `title: "..."` | `_sanitize_yaml_value(title)` |
| congo | 40 | `description: "..."` | `_sanitize_yaml_value(description, max_len=200)` |
| papermod | 77 | `title: "..."` | `_sanitize_yaml_value(title)` |
| papermod | 82 | `description: "..."` | `_sanitize_yaml_value(description, max_len=200)` |
| papermod | 91 | `alt: "..."` | `_sanitize_yaml_value(title)` |
| blowfish | 114 | `title: "..."` | `_sanitize_yaml_value(title)` |
| blowfish | 118 | `description: "..."` | `_sanitize_yaml_value(description, max_len=200)` |

### Issue 4: Slug Not Sanitized (blowfish + congo)

**Locations:**
- `hugo_writer.py:119` (blowfish): `fm += 'slug: "' + slug + '"\n'`
- `hugo_writer.py:41` (congo): `fm += 'slug: "' + slug + '"\n'`

**PaperMod status:** Already uses single quotes: `slug: '` + slug + `'` — safer but still unsanitized.

**Risk:** While `slugify()` in `shared/publisher.py:79-82` strips special characters, defensive sanitization at the frontmatter builder level protects against edge cases. A slug containing `"` or `:` would break YAML.

### Issue 5: Cover Block Fallback Indentation (blowfish only)

**Locations:** `hugo_writer.py:131-132, 136-137`

**Non-fallback path** (lines 125-128): Proper multi-line with consistent indentation:
```python
fm += "cover:\n"
fm += '  image: "' + thumbnail_url + '"\n'
fm += '  relative: true\n'
```

**Fallback path** (lines 131-132, 136-137): Inline `\n` in f-strings:
```python
fm += 'cover:\n  image: "' + _url + '"\n'
fm += '  relative: true\n'
```

Both produce correct output currently, but the fallback path is fragile (harder to read, easier to break with future edits). Fix: use the same explicit multi-line pattern as the non-fallback path.

### Issue 6: Weak `_validate_frontmatter()` (warning-only)

**Location:** `hugo_writer.py:856-858`

```python
_ok, _err = _validate_frontmatter(fm)
if not _ok:
    logger.warning(f"[PUBLISH] Invalid front matter: {_err}")
```

**Problem:** Invalid frontmatter is only logged, not blocked. This means broken YAML gets written to disk and only fails at Hugo build time. In contrast, `shared/publisher.py:577-581` treats frontmatter validation failure as a *hard error* that prevents writing.

**This is a discretion item, not a locked requirement.** The Planner should decide whether to make validation blocking in `hugo_writer.py` to match `publisher.py`'s behavior.

## Hugo v0.160.1 YAML Parser Specifics

### The Change

Hugo migrated from `gopkg.in/yaml.v2` to `github.com/goccy/go-yaml` in **v0.152.0** (2024-11-13, PR #13033). This change:

1. **Stricter parsing**: The `goccy/go-yaml` parser is more strict about YAML spec compliance
2. **Type changes**: Values like `yes`, `no`, `on`, `off` are now parsed as **strings** instead of booleans (this affects any `bool`-typed frontmatter that uses these values)
3. **Duplicate key rejection**: Hugo v0.160+ rejects duplicate mapping keys in frontmatter (confirmed by incident report at ricklamers/blog)
4. **Billion Laughs protection**: Alias limit of 10,000 for non-scalar nodes
5. **Error format**: Errors use `[line:col]` format instead of previous format

### What Breaks Our Frontmatter

The specific breakage patterns in our frontmatter:

| Pattern | What Hugo v0.160.1 Does | Error |
|---------|------------------------|-------|
| `tags: "['tag1', 'tag2']"` | Parses as single string, not YAML list | Template iterates chars — display corruption |
| `slug: "value\"` | Trailing `\"` consumed as escape | "map key-value is pre-defined" — string never closes |
| `description: "...\\"` | Trailing `\\` starts escape sequence | Same as above |
| `categories: "['cat']"` | Same as tags — string, not list | Theme display corruption |

The `goccy/go-yaml` parser is stricter about:
- Properly terminated quoted strings
- YAML flow sequence syntax (must be `[a, b]` not `"['a', 'b']"`)
- Unexpected end-of-file in multi-line strings

### Confirmed Fix from Production

The fix script `scripts/fix_frontmatter_v3.py` was applied to **3,074 files** across 10 CUAP blogs, fixing **692 files** (22.5% had issues). This confirms the bugs are real and the fix patterns work.

## Safe YAML Quoting Strategies

### Option 1: Single-quote by default, double-quote fallback (RECOMMENDED)

Single-quoted YAML strings (`'value'`) are the safest choice because:
- No escape sequence processing — `\` and `"` are literal
- Single quotes inside are escaped by doubling them (`'` → `''`)
- Korean/English text rarely contains single quotes
- Compatible with Hugo's YAML parser

**Strategy:**
1. If value has no single quotes → wrap in single quotes: `'value'`
2. If value has single quotes → wrap in double quotes with forward escaping: `"va\"lue"`

```python
def _sanitize_yaml_value(s, max_len=None):
    if s is None:
        return ""
    s = str(s)
    if max_len:
        s = s[:max_len]
    # Use single-quoted YAML (safe for Korean — no escape processing)
    if "'" in s:
        # Fall back to double-quoted with proper escaping
        s = s.replace("\\", "\\\\").replace('"', '\\"')
    return s
```

**Usage:**
- If single-quoted: `title: 'value'`
- If double-quoted: `title: "value"` (with proper escaping)

### Option 2: Trim trailing escape artifacts (current fix script approach)

The `scripts/fix_frontmatter_v3.py` uses `_fix_escaped_value()` to strip trailing `\` and `\"` artifacts. This is a recovery approach — it fixes broken content but doesn't prevent future breakage.

### Option 3: YAML library serialization (rejected by CONTEXT.md)

Using `yaml.dump()` would produce correct YAML but requires PyYAML and is explicitly excluded ("Do NOT add new dependencies").

### Recommendation: Option 1

The single-quote-first approach is the simplest, most maintainable fix that prevents the root cause (trailing escape artifacts) while being compatible with all content types.

## Existing Test Coverage

### Current State: ZERO test coverage for frontmatter generation

| Test File | Tests Related to Frontmatter |
|-----------|------------------------------|
| `tests/test_hugo_writer.py` | **Does not exist** |
| `tests/test_frontmatter.py` | **Does not exist** |
| `tests/conftest.py` | Minimal — only `sample_text` fixture |
| All other `tests/` | Covers curation, validators, notifiers — nothing related to hugo_writer |

**The frontmatter generation functions have zero unit tests.** This is a critical gap because:
1. Changes to escaping logic cannot be validated without manual Hugo builds
2. Regression from future changes is undetectable
3. The fix in `scripts/fix_frontmatter_v3.py` addresses 3 distinct bug classes that all went undetected

### Validation Path in Production

The `_validate_frontmatter()` function (line 523-535) uses `yaml.safe_load()` to check YAML validity:
```python
def _validate_frontmatter(fm_text):
    try:
        import yaml
        parts = fm_text.split("---")
        yaml.safe_load(parts[1])
        return True, ""
    except Exception as e:
        return False, str(e)
```

But it's only a **warning** in `hugo_writer.py` (line 857-858), not an error. In `shared/publisher.py` (line 577-581), the same validation is a **hard error** that blocks writes.

### Recommended Test Strategy

| Test | What It Validates | Command |
|------|-------------------|---------|
| Unit: blowfish tags | `tags: ["a", "b"]` format | `pytest tests/ -k "blowfish"` |
| Unit: blowfish categories | `categories: ["cat"]` format | Same |
| Unit: papermod tags | `tags: ["a", "b"]` format | Same |
| Unit: sanitize single-quote | `title: 'text'` output | Same |
| Unit: sanitize with single quotes | `title: "it's text"` (double-quoted) | Same |
| Unit: sanitize trailing backslash | trailing `\` stripped | Same |
| Unit: slug sanitization | slug with special chars is escaped | Same |
| Unit: empty tags | `tags: []` not `tags:` | Same |
| Unit: empty categories | `categories: []` | Same |
| Integration: Hugo build | `hugo --gc --minify` on test blog | Manual |

## Risks and Edge Cases

### Risk 1: Regressions in Existing Fixed Content

**Risk:** The fix script `scripts/fix_frontmatter_v3.py` was already applied to 3,074 existing files across 10 CUAP blogs. The generator fix changes how NEW files are written. If the generator and fix script produce *different* output for the same inputs, there's a risk of inconsistency.

**Mitigation:** Re-run `_validate_frontmatter()` on output from the fixed generator with representative inputs. The validation would have caught all 692 fixed files if it had been blocking.

### Risk 2: Single Quotes in Content

**Risk:** Korean/English blog content sometimes contains single quotes (e.g., `O'Brien`, `'가전제품'` in title). The single-quote-first strategy must handle this by falling back to double-quoting.

**Mitigation:** The proposed implementation checks for `"'" in s` and falls back to double-quoted mode. This is covered by the recommended test strategy.

### Risk 3: Cover Block Indentation Change

**Risk:** The fallback cover block indentation is currently correct but uses inline `\n`. The fix changes to explicit multi-line. If indentation is subtly different (different number of spaces), the YAML parser could reject it.

**Mitigation:** Use the exact same indentation pattern as the non-fallback path (2 spaces for `image:` and `relative:`). Verify with `_validate_frontmatter()`.

### Risk 4: `_validate_frontmatter()` Warning-Only

**Risk:** The frontmatter validation in `hugo_writer.py` is a warning, not an error. If the fix introduces any new YAML issue, the broken file would be written to disk and only fail at Hugo build time (30+ seconds later).

**Recommendation:** Make `_validate_frontmatter()` failure a blocking error, matching `shared/publisher.py`'s behavior. This is a defense-in-depth measure.

### Risk 5: Inactive ETAP Blogs

**Risk:** ~34 ETAP blogs use Blowfish theme but are mostly inactive. Their frontmatter generation happens in local `_write_hugo_post()` functions within each pipeline file (e.g., `pipelines/etap/cruise_pipeline.py:58`), NOT through `hugo_writer.py`. These local generators have their own issues (`"` → `'` replacement, raw f-strings).

**Impact:** The fix in `hugo_writer.py` does NOT affect ETAP blogs. If they're reactivated, their frontmatter issues would need separate fixes. This is outside the scope of Phase 48.

### Risk 6: `shared/publisher.py` Dead Code Confusion

**Risk:** `shared/publisher.py` has its own copies of `_sanitize_yaml_value()`, `_build_frontmatter_*()`, and `_write_hugo_post()` that are overridden by imports at line 762-770 (`from shared.publishers.hugo_writer import ...`). These local copies are dead code but have bug fixes that the active `hugo_writer.py` lacks (e.g., smart quote normalization in `_sanitize_yaml_value()`).

**Recommendation:** Consider removing the dead code from `shared/publisher.py` to prevent confusion, or at minimum port the smart quote normalization to `hugo_writer.py`'s `_sanitize_yaml_value()`.

### Risk 7: PaperMod Category Already Correct

**Risk:** The papermod builder (line 86) already uses `categories: ['cat']` — a correct YAML flow sequence. The blowfish builder (line 121) uses `str([category])` — producing `categories: "['cat']"`. Both are in the same file but have different category strategies.

**Impact:** Only blowfish's `categories:` needs fixing. PaperMod's `categories:` is already correct.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML serialization | Custom string concatenation | `yaml.dump()` | **Blocked by CONTEXT.md** — "Do NOT add new dependencies" |
| Post-hoc frontmatter repair | Rewrite fix scripts | Keep `scripts/fix_frontmatter_v3.py` | Already proven on 3,074 files; generator fix prevents new issues |

**Key insight:** The CONTEXT.md explicitly prohibits adding PyYAML or any new dependency, so hand-rolled string construction is the constraint, not a choice. The fix focuses on making the string construction produce valid YAML.

## Code Examples

### Current broken output vs Expected fixed output

**Blowfish `_build_frontmatter_blowfish()`:**

```yaml
# BROKEN (current):
---
title: "가전제품 추천"
slug: "appliance-guide"
categories: "['가전제품']"          # str(list) — single string!
tags: "['냉장고', '세탁기']"         # str(list) — single string!
# ... cover block
---

# FIXED (expected):
---
title: '가전제품 추천'              # single-quoted
slug: 'appliance-guide'             # single-quoted
categories: ['가전제품']             # YAML flow sequence
tags: ['냉장고', '세탁기']            # YAML flow sequence
# ... cover block
---
```

**PaperMod `_build_frontmatter_papermod()`:**

```yaml
# BROKEN (current):
---
title: "자동차 비교 분석"
tags: "['SUV', '세단']"              # str(list) — single string!
categories: ['자동차']               # already correct
# ... cover block
---

# FIXED (expected):
---
title: '자동차 비교 분석'             # single-quoted
tags: ['SUV', '세단']                # YAML flow sequence
categories: ['자동차']
# ... cover block
---
```

**Edge case: Content with single quotes:**

```yaml
title: "O'Brien's Guide"            # double-quoted because value has '
description: "Bob's picks"
```

**Edge case: Empty tags:**

```yaml
# BROKEN (current): tags: "" (empty string)
# FIXED (expected):
tags: []
categories: ['가전제품']
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | All pipelines route through `shared.publisher.publish()` → `shared.publishers.hugo_writer._write_hugo_post()` | Standard Stack | Some pipeline may have its own frontmatter generation that bypasses hugo_writer. Verified: ETAP pipelines have local `_write_hugo_post()` functions — they do NOT route through hugo_writer.py. These are mostly inactive. |
| A2 | Hugo v0.160.1's YAML parser strictness is the root cause | Hugo Parser | The old parser might also have rejected the same patterns but with different error messages. Confirmed: `goccy/go-yaml` migration in v0.152.0 is the known change point. |
| A3 | The 10 CUAP blogs' 692 fixed files are representative of all blogs | Issue Inventory | Other blogs (CAP, STAP, etc.) use the same generator code but different themes. The same bugs produce slightly different output depending on theme-specific frontmatter fields. |

## Architecture Patterns

### System Architecture Diagram

```
Pipeline Code                      Shared Library                      Hugo Site
===============                    ==============                      =========

pipelines/car/pipeline.py          shared/publisher.py                 content/posts/
  └─→ publish(blog_id, ...)          ├─ slugify(title)                   {slug}/index.md
  ┌─→ _build_and_deploy()              │  └─→ "slug" value               ├─ frontmatter YAML
  │                                    ├─ _write_hugo_post()             └─ body markdown
  │                                    │    ├─ theme == "blowfish" ───→
  │                                    │    │   _build_frontmatter_blowfish()     Hugo v0.160.1
  │  pipelines/curation/pipeline.py   ├─→ │   ├─ _sanitize_yaml_value()  ───→    ├─ YAML parser
  │  pipelines/stock/pipeline.py      │  │   ├─ str(tag_list) [BUG]              │    [goccy/go-yaml]
  │  pipelines/rap/pipeline.py        │  │   ├─ str([category]) [BUG]            ├─ Goldmark (body)
  │  pipelines/senior/pipeline.py     │  │   └─ slug unsanitized [BUG]           └─ Hugo build
  │  pipelines/travel/pipeline.py     │    ├─ theme == "congo" ───→
  │                                   │    │   _build_frontmatter_congo() ✅
  │  pipelines/etap/*.py (inactive)   │    └─ default (PaperMod) ───→
  │    └─→ local _write_hugo_post()   │        _build_frontmatter_papermod()
  │      (NOT through hugo_writer)   │          ├─ _sanitize_yaml_value() [BUG]
  │                                  │          └─ str(tag_list) [BUG]
  └──────────────────────────────────┘
                                      ^
                                      │ imports from
                                      │
shared/publishers/hugo_writer.py ◄────┘  (SINGLE POINT OF FIX)
  ├─ _sanitize_yaml_value()     [lines 14-21]  ← FIX escaping
  ├─ _build_frontmatter_congo() [lines 23-58]  ← DO NOT MODIFY
  ├─ _build_frontmatter_papermod() [lines 61-95]  ← FIX tags
  ├─ _build_frontmatter_blowfish() [lines 98-140]  ← FIX tags/categories/slug/cover
  └─ _write_hugo_post()          [lines 783-865]  ← FIX validation severity? (discretion)
```

### Caller → Callee Chain

```
publish() [publisher.py:852]
  └─ _write_hugo_post() [hugo_writer.py:783]  [imported, overriding local]
       ├─ _build_frontmatter_blowfish() [hugo_writer.py:98]   ← FIX
       ├─ _build_frontmatter_papermod() [hugo_writer.py:61]   ← FIX
       ├─ _build_frontmatter_congo() [hugo_writer.py:23]      ← NO CHANGE
       ├─ _validate_frontmatter() [hugo_writer.py:523]        ← discretion to harden
       └─ writes {slug}/index.md to disk
```

## Anti-Patterns to Avoid

1. **Escaping a value that's already inside double quotes with `\"`**: The `\"` sequence is correctly interpreted by the YAML parser as an escaped quote, meaning the parser continues looking for the real closing `"`. Using single-quoted YAML strings avoids this entirely.

2. **Using `str()` for list serialization**: `str(['a', 'b'])` produces `"['a', 'b']"` which looks like a YAML-quoted string. Always build YAML flow sequences explicitly: `["a", "b"]`.

3. **Partial sanitization**: Applying sanitization to `title` and `description` but not `slug` creates inconsistent coverage — any field that becomes part of YAML must be sanitized.

## Common Pitfalls

### Pitfall 1: Trailing `\"` from Escaping
**What goes wrong:** `_sanitize_yaml_value()` escapes `"` to `\"`. If the last character before the closing YAML `"` is `\`, the result is `\"` which the parser sees as an escaped quote.
**Why it happens:** AI-generated content sometimes ends with backslash artifacts; `_convert_inline_md_to_html()` might produce ending with `\`.
**How to avoid:** Use single-quoted strings (no escape processing). Fall back to double-quoting only when content contains single quotes.
**Warning signs:** Hugo build errors containing "map key-value is pre-defined" — the string value consumed multiple frontmatter keys.

### Pitfall 2: `str(list)` Confuses List vs String
**What goes wrong:** `str(['tag1', 'tag2'])` produces `"['tag1', 'tag2']"` — a single string, not a YAML list.
**Why it happens:** `str()` is Python's repr formatting, not YAML formatting.
**How to avoid:** Build flow sequences explicitly with `[" + ", ".join(...) + "]`.
**Warning signs:** Tags appear as characters `[ ' t a g 1 ' ,` in the rendered page.

### Pitfall 3: Forgetting Slug Sanitization
**What goes wrong:** Slug containing `"` or `:` breaks YAML quoting.
**Why it happens:** Slug is assumed "clean" because `slugify()` strips special chars. But defensive sanitization is still needed.
**How to avoid:** Apply the same quoting strategy to slug as to title/description.
**Warning signs:** Hugo build errors on slug field.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `gopkg.in/yaml.v2` | `github.com/goccy/go-yaml` | Hugo v0.152.0 (2024-11) | Stricter YAML parsing — our frontmatter bugs surfaced |
| `str(list)` for tags | YAML flow sequence | This phase | Fixes corrupted tag/category display |
| Double-quote-only escaping | Single-quote-first strategy | This phase | Prevents trailing escape artifacts |

## Sources

### Primary (HIGH confidence)
- [CITED: `shared/publishers/hugo_writer.py` source code] — All 3 frontmatter builders and `_sanitize_yaml_value()` reviewed in full
- [CITED: `config/blogs.d/*.yaml`] — Blog-to-theme mapping for all 64+ blogs verified
- [CITED: `scripts/fix_frontmatter_v3.py`] — Fix strategy already proven on 3,074 files / 692 fixes
- [CITED: `shared/publisher.py:762-770`] — Import chain confirmed: `publisher.py` imports from `hugo_writer.py`
- [CITED: Hugo v0.160.1 installed on this system] — `hugo v0.160.1+extended+withdeploy darwin/arm64`
- [CITED: Hugo PR #13033] — `gopkg.in/yaml` → `github.com/goccy/go-yaml` migration at v0.152.0

### Secondary (MEDIUM confidence)
- [CITED: Hugo issue #14886] — Confirms duplicate mapping keys rejected in v0.160+
- [CITED: ricklamers/blog commit 9711951] — Confirms `disableHLJS` duplicate key fix required for Hugo v0.160+

### Tertiary (LOW confidence)
- None — all claims verified from codebase or installed tools

## Open Questions

1. **Should `_validate_frontmatter()` be a hard error?** The `hugo_writer.py` version only logs a warning (line 857-858), while `publisher.py` version blocks writes (line 577-581). Making it a hard error in `hugo_writer.py` would provide defense-in-depth but could break pipelines if the validation has false positives.
   - Recommendation: Make it a hard error (matching `publisher.py` behavior) since the validation uses `yaml.safe_load()` which is reliable.

2. **Should the dead code in `shared/publisher.py` be cleaned up?** The local copies of `_build_frontmatter_*()` and `_write_hugo_post()` in `shared/publisher.py` are overridden by imports. They're dead code but contain some fixes (`_sanitize_yaml_value()` has smart quote normalization) that the active `hugo_writer.py` lacks.
   - Recommendation: Out of scope for Phase 48, but note for future cleanup.

3. **Should the `_sanitize_yaml_value()` in `hugo_writer.py` also get smart quote normalization from `publisher.py`'s version?** The publisher.py version normalizes smart quotes (`"`, `"`, `'`, `'`, etc.) to ASCII equivalents. This is a quality improvement but not required for YAML correctness.
   - Recommendation: Include it — it's a one-line extension and prevents potential YAML issues from Unicode quotes.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | Code execution | ✓ | 3.14 | — |
| Hugo v0.160.1 | Build verification | ✓ | v0.160.1+extended | — |
| PyYAML | YAML validation | ✓ | stdlib | — |

**Missing dependencies with no fallback:** None — all required tools are available.

## Validation Architecture

> `nyquist_validation` is set to `false` in `.planning/config.json` — this section applies phase-internal validation only.

### Phase Requirements → Test Map

While nyquist_validation is disabled for the workflow, the phase itself would benefit from these specific tests:

| Req ID | Behavior | Test Type | Verification Method |
|--------|----------|-----------|-------------------|
| REQ-01 | `_sanitize_yaml_value()` produces single-quoted output for plain text | manual | Python assertion on output |
| REQ-02 | `_sanitize_yaml_value()` produces double-quoted output for text with `'` | manual | Python assertion on output |
| REQ-03 | `_sanitize_yaml_value()` strips trailing `\` artifacts | manual | Python assertion on output |
| REQ-04 | `_build_frontmatter_blowfish()` tags are YAML flow sequence | manual | Assert `"[", "]"` not `"str("` in output |
| REQ-05 | `_build_frontmatter_blowfish()` categories are YAML flow sequence | manual | Same |
| REQ-06 | `_build_frontmatter_blowfish()` slug is single-quoted | manual | Assert single-quote encapsulation |
| REQ-07 | `_build_frontmatter_papermod()` tags are YAML flow sequence | manual | Same as REQ-04 |
| REQ-08 | Cover fallback block has 2-space indentation | manual | Assert whitespace |
| REQ-09 | All 3 builders pass `_validate_frontmatter()` | manual | Call with representative inputs |
| REQ-10 | Hugo build succeeds on generated content | manual | `hugo --gc --minify` on test blog |

**No existing test files cover these requirements** — any tests created for this phase would be net-new.

## Security Domain

> `security_enforcement` is absent from `.planning/config.json` (default: enabled). However, this phase has no security-sensitive changes — it modifies YAML string construction only.

No new authentication, authorization, input validation (beyond YAML correctness), cryptography, or session management concerns. The `_sanitize_yaml_value()` function is already present; the fix changes quoting strategy but does not weaken existing protections. YAML injection is not a meaningful threat here (Hugo processes untrusted frontmatter in the same way; the pipeline controls both the content and the parser).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Verified from codebase
- Architecture: HIGH — Import chain confirmed from codebase
- Issues inventory: HIGH — All issues verified by reading source code
- Blog counts: HIGH — Verified from config files
- Hugo YAML parser: MEDIUM — WebSearch confirmed migration PR, but exact error messages vary

**Research date:** 2026-07-26
**Valid until:** No fast-moving dependencies — valid indefinitely until Hugo makes another YAML parser change
