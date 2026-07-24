# CUAP Title Generation Pipeline — Research

**Researched:** 2026-07-22
**Domain:** AI title generation, post-processing, slugification
**Confidence:** HIGH
**Audience:** Planner for fixing title quality issues in CUAP curation pipeline

---

## Executive Summary

The CUAP curation pipeline generates Korean product recommendation blog posts for `informationhot.kr` subdomains (baby, laptop, pet, beauty, kitchen, camping, appliance, interior, fitness, health). Titles are entirely AI-generated — the system prompt in `writer.py` provides 4 pattern examples the model follows, but **no post-processing on the title exists** between AI generation and publishing.

Key finding: The pipeline has **no title-specific post-processing**. The `sanitize_title()` function in `validators.py` only removes markdown artifacts (`**`, `__`) and deduplicates words. It does **not** strip date prefixes, em dashes, special characters, or enforce length limits. The `slugify()` function in `publisher.py` does strip special characters for the URL slug, but the **displayed title** retains them.

The humanizer (`humanizer.py`) operates on `body_md` only — it never touches the title. All five title issues stem from the AI prompt design and lack of post-processing sanitization.

---

## Issue 1: Date Prefix in Titles ("2026년 7월")

### Current Behavior
Many AI-generated titles start with `"2026년 7월 "` — e.g., `"2026년 7월 기저귀 추천: 하기스 네이처메이드..."`, `"2026년 7월 스펙 비교: 갤럭시북6..."`.

### Sources (all are AI prompt, NOT post-processing)

| Source | File:Line | Mechanism |
|--------|-----------|-----------|
| System prompt year/month injection | `writer.py:234-235` | `{year}년 {month}월 기준 "{keyword}" 관련 추천 상품 글을 작성합니다.` — primes AI with current date |
| Title Pattern 1 example | `writer.py:240-241` | `"[연도]년 [월]월 [제품명] 추천 — [구체적 혜택/특징]"` with live example `"2026년 7월 립밤 추천 리엔케이·바세린 — 하루 종일 촉촉한 선택"` — teaches AI to use date in title |
| AIDA funnel instruction | `writer.py:265` | `"{year}년 {month}월 기준"` embedded in funnel description |
| Title templates (ranking, buying_guide, spec_style) | `title_templates.py:19,22,25` | Templates include `{year}년 {month}월` — used as `style_hint` (advisory input to AI, not enforced) |
| Fallback title | `writer.py:490` | `f"{keyword} 추천 TOP5 ({datetime.now().year}년)"` — only used if AI produces no `# ` heading |
| Title template picker | `title_templates.py:211-212` | `"year": str(now.year)`, `"month": str(now.month)` — variables for templates |

### Why It Happens
The AI adopts Pattern 1 from the prompt examples because:
1. It's the **first** pattern listed (primacy effect on LLMs)
2. The system prompt opens with `"2026년 7월 기준"` — reinforcing the date at the context head
3. The `style_hint` from `title_templates.py` may also include date when "ranking", "spec_style", or "buying_guide" is selected
4. **No post-processing exists to strip the date prefix** from the extracted title

### Proposed Fix
Three approaches (recommended: combine all):

**Option A — Prompt engineering (reduce date priming):**
- `writer.py:235`: Change `{year}년 {month}월 기준 "{keyword}" 관련...` to `"{keyword}" 관련...` (remove date from context head)
- `writer.py:241`: Change Pattern 1 example to not start with date — e.g., `"립밤 추천 리엔케이·바세린 — 하루 종일 촉촉한 선택"`

**Option B — Post-processing strip:**
- Add logic in `pipeline.py` after `sanitize_title()` (line 837) to strip `YYYY년 MM월 ` prefix from title if it matches current date

**Option C — Make Pattern 1 less prominent:**
- Reorder patterns so non-date patterns come first, or add a lint rule "제목에 'YYYY년 MM월'로 시작하지 마세요"

---

## Issue 2: Special Characters in Titles and Slugs

### Current Behavior
Titles contain em dashes (`—`), middle dots (`·`), colons (`:`), parentheses, and question marks. These come from:
1. **Em dash `—`**: Used in all 4 title pattern examples (`writer.py:241,243,245,247`) and in `title_templates.py:18` ("comparison" template)
2. **Colon `:`**: AI-generated titles use `:` as separator (e.g., `"기저귀 추천: 하기스..."`)
3. **Middle dot `·`**: Used in prompt example `writer.py:241` (`"리엔케이·바세린"`) — AI copies this pattern

### What Gets Stripped Where

| Function | File:Line | Strips | Retains | Affects |
|----------|-----------|--------|---------|---------|
| `sanitize_title()` | `validators.py:17-60` | `**`, `__` only | `—`, `·`, `:`, `()`, `?`, `,` | **Displayed title** — does NOT strip special chars |
| `slugify()` | `publisher.py:79-82` | All except `\w`, `\s`, `가-힣`, `-` | Hangul, alphanumeric, hyphens | **URL slug** — strips correctly |
| `_make_slug()` | `pipeline.py:627-631` | All except `a-z`, `0-9`, `가-힣`, `-` | Hangul, alphanumeric, hyphens | **DB recording only** — strips correctly |

### Result
- **Visible title** retains special chars: `"기저귀 추천: 하기스...어떤 선택이 현명할까?"`
- **URL slug** strips them: `/2026년-7월-기저귀-추천-하기스-...-어떤-선택이-현명할까` (verified from live URLs on informationhot.kr)
- Hugo frontmatter `title:` field stores the raw title with special chars (via `_sanitize_yaml_value()` which only normalizes smart quotes, `publisher.py:249-250`)
- This means the **h1 heading on the page** has em dashes and colons

### Proposed Fix
**Add special character stripping to `sanitize_title()` (`validators.py:17-60`):**
```python
# After existing code, add:
# Strip em dash, en dash, middle dot, bullet
t = re.sub(r"[—–·•·]", " ", t)
# Strip special punctuation that shouldn't be in displayed titles
t = re.sub(r"[\u2013\u2014\u00B7\u2022]", " ", t)
# Deduplicate spaces after removal
t = re.sub(r"\s+", " ", t).strip()
```

Alternatively, keep `sanitize_title()` clean and add a new `sanitize_display_title()` function.

---

## Issue 3: Title Length Inconsistency

### Current Behavior
Titles vary wildly:
- Short: `"강아지슬링백 (2026년)"` (~15 chars)
- Long: `"2026년 7월 옥희독희 위로열림 이동장과 반려동물 우주선 — 고양이 이동장 선택 가이드"` (~60 chars)

### What Controls Title Length
| Control | File:Line | Effect |
|---------|-----------|--------|
| System prompt patterns | `writer.py:239-258` | 4 patterns define structure but not length limit |
| Body length constraint | `writer.py:333-334` | `"총 2500~3500자 (한글 기준)"` — body only, no title length rule |
| `style_hint` | `title_templates.py:217` | Template rendered to string — influences structure, not length |
| `_build_user_prompt()` | `writer.py:356-363` | Says `"1~2개를 반드시 제목에 포함하세요"` — keyword inclusion, not length |
| `sanitize_title()` | `validators.py:17` | No length limit — only markdown striping and dedup |
| `validate_post()` | `validators.py:302-303` | Flags `_MAX_TITLE_LEN = 80` — but this is validation only, not enforced in pipeline |
| Fallback title | `writer.py:490` | `f"{keyword} 추천 TOP5 ({datetime.now().year}년)"` — only when AI produces no `# ` heading |

### Why Short Titles Happen
When the AI generates a "budget" or "review_style" template title, the pattern naturally produces shorter strings. The template `"실제 써본 사람이 말하는 {keyword} TOP 5"` is short. Short titles are not inherently bad — they only become problematic when:
- They are shorter than `_MIN_TITLE_LEN = 10` (validators.py:63) — triggers validation warning
- They lack keyword inclusion (SEO issue)

### Why Long Titles Happen
When the AI follows Pattern 1 or the spec_style template with multiple brand names:
- `"2026년 7월 [제품명] 추천 — [구체적 혜택/특징]"` — the product names and benefits can be verbose
- Template `"{year}년 {month}월 스펙 비교: {brand1} vs {brand2} vs {brand3}"` — multiple brands + keyword

### Proposed Fix
**Add title length guidance to the AI prompt** (`writer.py`, around line 256):
```python
"[제목 길이]\n"
"- 제목은 20~50자 사이로 작성하세요.\n"
"- 너무 긴 제목(60자 이상)은 검색 결과에서 잘립니다.\n"
```

**AND/OR add post-processing truncation** in `pipeline.py` around line 837:
```python
MAX_TITLE_LEN = 55
if len(title) > MAX_TITLE_LEN:
    # Truncate at last space before MAX_TITLE_LEN, add "..."
    truncated = title[:MAX_TITLE_LEN]
    last_space = truncated.rfind(" ")
    if last_space > 20:
        title = title[:last_space] + "..."
```

---

## Issue 4: The Humanizer

### File
`shared/humanizer.py` (212 lines)

### Call Site
`publisher.py:888-892` — called AFTER `slugify(title)` (line 876) and AFTER article dict creation (line 895-914), but BEFORE writing the Hugo file.

### What It Does
- Operates on `body_md` only — **title is an input parameter but used only for logging/context** (line 148: `_title_part = f"제목: {title}\n...`)
- Uses AI (OpenAI, tier="economy") to rewrite AI-sounding Korean into natural Korean
- Has extensive rules for translationese, English overuse, structural AI patterns, hedging, etc.
- Returns original `body_md` on any failure (fail-open)

### Does It Fix or Worsen Title Issues?
**Neither.** The humanizer **does not touch the title at all**. It operates on `body_md` only. The title is extracted from the AI output before the humanizer is called (in `generate_curation_article()`, `writer.py:481-488`), and the humanizer receives the title as a context parameter but never modifies it.

### Relevant Detail
```python
# publisher.py:876 — slug from raw title
slug = slugify(title)

# publisher.py:888-892 — humanize body ONLY
if blog_id in _KO_BLOG_IDS and body_md:
    body_md = humanize_korean(body_md, blog_id, title)  # title is context-only
```

### Implications
Any fix for title issues must be applied BEFORE `publish()` is called (i.e., in `pipeline.py` or in `generate_curation_article()`), since the slug is already computed from the raw title by the time humanizer runs.

---

## Issue 5: Slugify in publisher.py

### File:Line
`shared/publisher.py:79-82`

### Current Code
```python
def slugify(text):
    text = re.sub(r"[^\w\s가-힣-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text.lower()[:80]
```

### What It Strips (Verified)
- `—` (em dash, U+2014) → removed ✓
- `·` (middle dot, U+00B7) → removed ✓
- `(` `)` → removed ✓
- `:` → removed ✓
- `?` → removed ✓
- `,` → removed ✓
- `"` `'` → removed ✓
- `!` `@` `#` etc. → removed ✓

### What It Retains
- Hangul (가-힣) ✓
- Alphanumeric (a-z, A-Z, 0-9 via `\w`) ✓
- Underscore (`_` via `\w`) ✓ — **this is a quirk, underscores shouldn't be in Korean slugs**
- Hyphens (`-`) ✓
- Spaces (before being converted to hyphens by second regex) ✓

### Does It Properly Strip Special Characters?
**Yes.** The regex `[^\w\s가-힣-]` correctly removes all the special characters mentioned in the issues. The em dash (`—`) is NOT in `\w`, `\s`, `가-힣`, or `-`, so it gets removed. Verified against actual published URLs on informationhot.kr.

### The Real Slug Problem
There are **two different slug systems** that creates inconsistency:

| Slug | Source | Used For |
|------|--------|----------|
| `pipeline.py:842` → `_make_slug(keyword)` | Keyword-based, date-prefixed (`YYYYMMDD-keyword-slug`) | DB recording only (`_record_publish()`, `log_publish_audit()`) |
| `publisher.py:876` → `slugify(title)` | Title-based, no date prefix | Actual Hugo post filename and URL |

The pipeline creates a slug from the keyword for DB, but `publish()` **ignores this** and creates a NEW slug from the title. This means:
1. The URL is title-based, not keyword-based
2. A small title change produces a completely different URL (SEO fragmentation risk)
3. The `slug` parameter in `publish()` is not used — it's not even in the function signature

### Minor Improvements
- Add underscore removal: `[^\w\s가-힣-]` → `[^\w\s가-힣-]` + strip `_` (underscores look ugly in Korean URLs)
- The 80 char limit is fine but could cause truncation issues for very long Korean titles (each Hangul character is ~3 bytes in URL encoding)

---

## Data Flow Summary

```
writer.py / generate_curation_article()
  │
  │ 1. _build_system_prompt() → system prompt with year/month, 4 title patterns
  │ 2. ai_generate(system, user, temperature=0.85) → AI returns full article with H1 title
  │ 3. Title extracted from first "# " heading (line 482-488)
  │ 4. Fallback: f"{keyword} 추천 TOP5 ({year}년)" if no heading
  │
  ├── Returns {"title": title, "body_md": body, ...}
  │
  ▼
pipeline.py / run()
  │
  │ 5. article = generate_curation_article()  ← line 825
  │ 6. title = sanitize_title(article["title"])  ← line 837
  │    → Only removes ** __ and deduplicates words
  │    → Does NOT strip date prefix, em dash, middle dot, etc.
  │ 7. slug = _make_slug(keyword)  ← line 842 (DB-only, not used for URL!)
  │ 8. publish(blog_id, title, body_md, ...)  ← line 974
  │
  ▼
publisher.py / publish()
  │
  │ 9. slug = slugify(title)  ← line 876 (actual URL slug)
  │ 10. humanize_korean(body_md, blog_id, title)  ← line 891 (body only, not title)
  │ 11. _write_hugo_post() with slug from title  ← line 1001
  │
  ▼
Hugo file: content/posts/{YYYY-MM-DD}-{title-slug}.md
  │ Frontmatter title: raw title with special chars
  │ Slug: cleaned title
  │
  ▼
Published URL: https://{blog}.informationhot.kr/posts/{title-slug}/
```

---

## Fix Priority Matrix

| Issue | Effort | Impact | Recommended Approach | File Changes |
|-------|--------|--------|---------------------|--------------|
| Date prefix | Low (prompt edit) | HIGH — affects SEO + visual quality | Remove date from prompt examples + add post-processing strip | `writer.py:241`, `writer.py:235`, `pipeline.py:837` |
| Special chars in titles | Low | HIGH — affects visual quality + slug cleanliness | Add strip to `sanitize_title()` | `validators.py:17-60` |
| Title length | Medium | MEDIUM — affects SEO snippet | Add prompt constraint + soft truncation | `writer.py:256`, `pipeline.py:837` |
| Humanizer doesn't fix titles | No change needed | N/A | Document as known behavior | None (informational) |
| Slugify works correctly | No change needed | N/A | Minor: add `_` removal | `publisher.py:80` (optional) |
| Two slug systems | High | LOW — DB slug unused for URL | Fix: pass `pipeline.py slug` to publish or sync systems | `publisher.py`, `pipeline.py` |

---

## Files to Modify (Summary)

| File | Lines | Changes |
|------|-------|---------|
| `pipelines/curation/writer.py` | 234-258, 333-334 | Reduce date priming in prompt, add title length guidance, reorder patterns |
| `shared/validators.py` | 17-60 | Add special char stripping (`—`, `·`, `:` etc.) to `sanitize_title()` |
| `pipelines/curation/pipeline.py` | 837 | Add optional title length truncation after `sanitize_title()` |
| `shared/publisher.py` | 80 | (Optional) add `_` removal in `slugify()` |

---

## Verification Checklist

- [ ] After fix: generated titles do NOT start with "YYYY년 MM월"
- [ ] After fix: titles do not contain em dash (`—`), middle dot (`·`), or special punctuation
- [ ] After fix: titles are between 20-55 characters
- [ ] After fix: URL slugs are clean (no double hyphens, no special chars)
- [ ] After fix: Hugo frontmatter `title:` field matches display title
- [ ] After fix: existing published posts are NOT affected (fix only applies to new generations)
- [ ] Verify with test: run pipeline for one blog_id, inspect generated title, slug, and Hugo frontmatter

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Date prefix sources | HIGH | All confirmed via code inspection of `writer.py`, `title_templates.py` |
| Special char handling | HIGH | Both `sanitize_title()` and `slugify()` behavior verified by reading code |
| Humanizer scope | HIGH | `humanize_korean()` signature and body-only operation confirmed |
| Slugify behavior | HIGH | Regex logic verified + live URL inspection on informationhot.kr |
| Title length controls | MEDIUM | AI behavior is probabilistic — prompt constraints reduce but don't guarantee length |
| Two-slug problem | HIGH | Both `_make_slug()` and `slugify()` paths traced through pipeline flow |

---

## Sources

### Primary (code inspection)
- `pipelines/curation/writer.py` — system prompt, title patterns, title extraction
- `shared/title_templates.py` — template definitions, render function
- `shared/validators.py` — `sanitize_title()`, title validation limits
- `shared/humanizer.py` — `humanize_korean()` — body-only operation confirmed
- `shared/publisher.py` — `slugify()`, `publish()`, `_write_hugo_post()`
- `pipelines/curation/pipeline.py` — `run()`, `_make_slug()`, flow orchestration

### Secondary (live verification)
- Web search: `site:informationhot.kr 2026년 7월` — verified actual URL slugs and title patterns on baby.informationhot.kr, laptop.informationhot.kr, etc.
- Web search: `site:*.informationhot.kr` — verified URL encoding of Hangul slugs

### Tertiary
- My training data for Python regex behavior and Hugo static site conventions
