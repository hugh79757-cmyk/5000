# Phase 25: CUAP 거미줄 엔티티 시스템 — Research

**Researched:** 2026-07-20
**Domain:** Cross-blog entity linking, content funnels, curation pipeline integration
**Confidence:** HIGH

## Summary

Phase 25 builds a "spider web" entity linking system for CUAP's 10 curation blogs. The system injects cross-blog links, cross-sell cards, and funnel headers into blog posts at publish time, enabling user navigation between related CUAP blogs and increasing pageviews/ad exposure.

The existing ETAP `entity_linker.py` (337 lines) provides a proven pattern: register entities on publish → inject links into body markdown → build cross-sell HTML. The CUAP implementation adapts this pattern for category-based linking (instead of city/country) with a fixed `CROSS_GRAPH` dictionary.

**Primary recommendation:** Create `shared/cuap_entity_linker.py` modeled on `shared/entity_linker.py`, inject into `pipelines/curation/pipeline.py` between CTA fallback (line 917) and `publish()` call (line 948), and create `layouts/partials/cuap-spider-links.html` Hugo partial for the 10 identical Blowfish single.html layouts.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| R1 | CUAP 엔티티 링크 DB 구축 | travel-en.db에 cuap_entities + cuap_link_graph 테이블 추가 — 기존 entity_links 테이블 스키마 패턴 재사용 |
| R2 | 엔티티 등록 시스템 | register_cuap_entity() — ETAP register_entity() 패턴 재사용, pipeline.py 발행 완료 후 호출 |
| R3 | 인라인 크로스 링크 삽입 | inject_cross_blog_links() — ETAP inject_internal_links() 로직 재사용, 키워드 매칭 → 링크 삽입 |
| R4 | 크로스셀 카드 생성 | build_cross_sell_card() — ETAP build_cross_sell_html() 패턴 재사용, blog별 아이콘 + 제목 + 링크 |
| R5 | 퍼널 헤더 생성 | build_funnel_header() — 본문 상단에 관련 카테고리 3개 링크 |
| R6 | Hugo 레이아웃 통합 | cuap-spider-links.html partial — 10개 블로그 전부 동일 single.html (md5: 4407c6c) |
| R7 | 10개 블로그 연결 그래프 정의 | CROSS_GRAPH 딕셔너리 — primary/secondary/use_cases + weight |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Decision 1: CUAP 엔티티 DB 위치** — travel-en.db 통합 (기존 ETAP entity_linker.py의 travel-en.db에 CUAP 테이블 추가)
- **Decision 2: 인라인 링크 삽입 시점** — 발행 시 본문 삽입 (pipeline.py에서 publish() 호출 전)
- **Decision 3: 크로스셀 카드 생성 방식** — Python에서 미리 생성 (HTML 문자열로 마크다운에 삽입)
- **Decision 4: 퍼널 헤더 생성 방식** — Python에서 미리 생성 (크로스셀 카드와 동일 패턴)
- **Decision 5: Hugo 레이아웃 통합 방식** — 통일 레이아웃 (10개 블로그 전부 동일 cuap-spider-links.html)
- **Decision 6: 퍼널 경로 설정 방식** — 고정 경로 (CROSS_GRAPH 딕셔너리)

### the agent's Discretion

- CROSS_GRAPH 퍼널 경로의 구체적 가중치(weight) 값
- 인라인 링크당 최대 삽입 수 (SPEC: 3개)
- 크로스셀 카드에 표시할 블로그 수 (SPEC: 타 블로그 3개 + 같은 블로그 1개)

### Deferred Ideas (OUT OF SCOPE)

- ETAP 기존 entity_linker.py 수정
- STAP/TAP 외부 프로젝트 연동
- 실시간 사용자 트래킹/분석
- A/B 테스트 프레임워크
- 광고 수익 직접 최적화 (AdSense 설정 변경)
- 기존 발행된 글 수정 (다음 발행분부터 적용)
</user_constraints>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Entity registration | API/Backend (pipeline.py) | Database (travel-en.db) | Pipeline publishes → registers entity in DB |
| Cross-blog link injection | API/Backend (pipeline.py) | — | Body markdown modified before publish() call |
| Cross-sell card HTML generation | API/Backend (cuap_entity_linker.py) | — | Python generates HTML, inserted into markdown |
| Funnel header generation | API/Backend (cuap_entity_linker.py) | — | Python generates HTML, inserted at body top |
| Hugo layout rendering | CDN/Static (Blowfish theme) | — | cuap-spider-links.html partial renders at page load |
| Entity DB persistence | Database (travel-en.db) | — | cuap_entities + cuap_link_graph tables |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | Entity DB queries | Already used by entity_linker.py, zero dependency |
| re | stdlib | Markdown link injection | Already used by entity_linker.py for pattern matching |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Blowfish theme | installed | Hugo theme for all 10 CUAP blogs | All CUAP blogs use Blowfish (cuap.yaml: `theme: blowfish`) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| travel-en.db | cuap_links.db (separate) | CONTEXT.md Decision 1 locked on travel-en.db — unified management |
| Python HTML generation | Hugo partial templates | CONTEXT.md Decision 3 locked on Python pre-generation — pattern match with ETAP |
| Fixed CROSS_GRAPH | Dynamic DB-driven graph | CONTEXT.md Decision 6 locked on fixed paths — simpler, immediately deployable |

## Package Legitimacy Audit

> No external packages are installed in this phase. All code uses Python stdlib (sqlite3, re, logging, os) and existing project modules.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none) | — | — | — | — | — | N/A — stdlib only |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
CUAP Pipeline Flow (pipeline.py)
═══════════════════════════════════

  keyword → products → AI article → body_md
                                         │
         ┌───────────────────────────────┤
         │                               │
         ▼                               ▼
  ┌──────────────┐              ┌────────────────┐
  │ CTA fallback │              │ CROSS_GRAPH    │
  │ (line 905)   │              │ lookups        │
  └──────┬───────┘              └───────┬────────┘
         │                               │
         │                    ┌──────────┴──────────┐
         │                    │                      │
         │                    ▼                      ▼
         │         ┌─────────────────┐    ┌─────────────────┐
         │         │ inject_cross_   │    │ build_funnel_   │
         │         │ blog_links()    │    │ header()        │
         │         │ (inline links)  │    │ (top of body)   │
         │         └────────┬────────┘    └────────┬────────┘
         │                  │                      │
         │                  ▼                      │
         │         ┌─────────────────┐            │
         │         │ build_cross_    │            │
         │         │ sell_card()     │            │
         │         │ (bottom of body)│            │
         │         └────────┬────────┘            │
         │                  │                      │
         │         ┌────────┴──────────────────────┘
         │         │
         ▼         ▼
    ┌────────────────────┐
    │  body_md modified  │
    │  (links + cards +  │
    │   funnel header)   │
    └─────────┬──────────┘
              │
              ▼
    ┌────────────────────┐
    │  publish(blog_id,  │
    │  title, body_md)   │
    └─────────┬──────────┘
              │
              ▼
    ┌────────────────────┐
    │  Hugo site →       │
    │  cuap-spider-links │
    │  .html partial     │
    │  (renders cards)   │
    └────────────────────┘
```

### Recommended Project Structure

```
shared/
├── cuap_entity_linker.py     # NEW — CUAP entity linking system
│   ├── CROSS_GRAPH           # 10-blog connection graph
│   ├── BLOG_DOMAINS          # blog_id → domain mapping
│   ├── ICONS                 # blog_id → emoji mapping
│   ├── register_cuap_entity()
│   ├── inject_cross_blog_links()
│   ├── build_cross_sell_card()
│   └── build_funnel_header()
├── entity_linker.py          # EXISTING — ETAP (do not modify)

pipelines/curation/
├── pipeline.py               # MODIFY — inject cuap_entity_linker calls
│   ├── Line ~810: after AI article generation
│   ├── Line ~917: after CTA fallback, before publish()
│   └── Line ~969: after publish success, register entity

layouts/partials/
├── cuap-spider-links.html    # NEW — cross-blog card renderer
```

### Pattern 1: ETAP Entity Registration (reuse pattern)

**What:** Register entity in DB on publish, mark published after Hugo deploy
**When to use:** Every CUAP blog post publish
**Example:**
```python
# Source: shared/entity_linker.py:73-96 (register_entity)
# ETAP pattern: register on publish, mark published after deploy
def register_cuap_entity(entity_type, entity_name, blog_id, post_slug,
                         link_label, priority=50, published=0):
    """CUAP 발행 시 엔티티 등록"""
    if not entity_name or len(entity_name) <= 2:
        return
    domain = BLOG_DOMAINS.get(blog_id, "")
    if not domain:
        return
    post_url = f"{domain}/posts/{post_slug}/"
    conn = _get_db()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO cuap_entities
            (entity_type, entity_name, blog_id, post_slug, post_url,
             link_label, priority, published)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (entity_type, entity_name, blog_id, post_slug,
              post_url, link_label, priority, published))
        conn.commit()
    except Exception as e:
        logger.exception(f"register_cuap_entity failed: {e}")
    finally:
        conn.close()
```

### Pattern 2: ETAP Link Injection (reuse pattern)

**What:** Scan markdown for entity keywords, replace first occurrence with hyperlink
**When to use:** Before publish() call in pipeline.py
**Example:**
```python
# Source: shared/entity_linker.py:163-274 (inject_internal_links)
# Key rules to preserve:
# - Same keyword linked only once per post
# - H1/H2 headings skipped
# - Already-linked text in []() skipped
# - Max max_links per post
# - published=1 entities only
```

### Pattern 3: ETAP Cross-Sell HTML (reuse pattern)

**What:** Generate styled HTML card block with blog icons and links
**When to use:** Append to body markdown before publish
**Example:**
```python
# Source: shared/entity_linker.py:277-337 (build_cross_sell_html)
# Pattern: inline-style HTML for Hugo raw HTML rendering
# Cards: icon + label + link in flex-wrap layout
# Container: background, border-radius, padding
```

### Pattern 4: Pipeline Injection Point

**What:** Insert cross-blog processing between CTA fallback and publish() call
**When to use:** In pipeline.py `_run_inner()`, after line 917 (CTA fallback), before line 948 (publish)
**Example:**
```python
# Source: pipelines/curation/pipeline.py:905-948
# Current flow:
#   Line 905: _HAS_CTA check
#   Line 917: body_md += _FALLBACK_CTA
#   Line 920: tag_set creation
#   Line 948: result = publish(blog_id, title, body_md, ...)
#
# INSERT between line 917 and line 920:
#   body_md = inject_cross_blog_links(body_md, blog_id)
#   body_md = build_funnel_header(body_md, blog_id) + body_md
#   body_md += build_cross_sell_card(blog_id)
```

### Anti-Patterns to Avoid

- **Don't modify entity_linker.py:** CUAP has its own separate module — ETAP must not be affected
- **Don't inject links in Hugo templates:** Links must be in markdown at publish time (ETAP proven pattern)
- **Don't use dynamic DB queries for link graph:** Fixed CROSS_GRAPH dictionary per CONTEXT.md Decision 6
- **Don't create separate DB file:** Use travel-en.db per CONTEXT.md Decision 1

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown link injection | Custom regex engine | Reuse ETAP `inject_internal_links()` pattern | Already handles H1/H2 skip, existing link detection, placeholder logic |
| Entity DB operations | Raw SQL everywhere | Reuse ETAP `register_entity()` / `mark_entity_published()` pattern | Connection management, error handling, logging already handled |
| Cross-sell HTML | Custom CSS framework | Reuse ETAP `build_cross_sell_html()` inline-style pattern | Hugo renders raw HTML from markdown, inline styles are necessary |
| Blog domain mapping | Hardcode in every function | Single `BLOG_DOMAINS` dictionary | One source of truth, matches ETAP pattern |

## Common Pitfalls

### Pitfall 1: Injecting Links Inside Existing Markdown Links
**What goes wrong:** `[already linked text](url)` gets double-linked → broken markdown
**Why it happens:** Simple regex without link-aware parsing
**How to avoid:** Use the ETAP placeholder technique — temporarily replace `[...](...)` with `__LINK_PH_N__` before matching, restore after (see `entity_linker.py:230-256`)
**Warning signs:** Markdown rendering artifacts, visible `__LINK_PH_` strings

### Pitfall 2: Linking in H1/H2 Headings
**What goes wrong:** Navigation links in headings break page structure and SEO
**Why it happens:** Regex matches across all lines without heading detection
**How to avoid:** Skip lines starting with `# ` or `## ` (see `entity_linker.py:219-220`)
**Warning signs:** Links appearing in page titles or table of contents

### Pitfall 3: Coupang API Rate Limit During Entity Registration
**What goes wrong:** Entity registration triggers DB writes that slow pipeline under rate limit
**Why it happens:** Pipeline has rate limiting for Coupang API but not for DB operations
**How to avoid:** Entity DB writes are local SQLite — negligible performance impact. But log registration failures gracefully (don't block publish on entity registration failure)
**Warning signs:** Pipeline timeout during publish phase

### Pitfall 4: Hugo Raw HTML in Markdown
**What goes wrong:** HTML entities escaped, cards render as text
**Why it happens:** Hugo markdown processor escapes `<` and `>` by default
**How to avoid:** Use raw HTML blocks (blank line before and after `<div>`) — Blowfish theme supports this. Test with `hugo server` before deploy.
**Warning signs:** `<div>` visible as text on rendered page

### Pitfall 5: Identical single.html Across 10 Blogs
**What goes wrong:** Modifying one blog's single.html doesn't affect others
**Why it happens:** Each CUAP blog is a separate Hugo site with its own layouts/ directory
**How to avoid:** Create `cuap-spider-links.html` partial in all 10 blogs (same content, same md5: `4407c6c`). Consider a deployment script or shared template approach.
**Warning signs:** Some blogs showing old layout after deploy

## Code Examples

### ETAP Entity Registration Flow (proven pattern)

```python
# Source: pipelines/etap/culture_pipeline.py:241-243
# Registration happens AFTER publish success:
register_entity("city", city, BLOG_ID, article["slug"], "culture tours in " + city, 55, 1)
register_entity("country", country, BLOG_ID, article["slug"], "art tours in " + country, 40, 1)

# CUAP equivalent (after publish success):
register_cuap_entity("category", keyword, blog_id, slug, f"{keyword} 추천", 50, 1)
```

### ETAP Link Injection in Pipeline (proven pattern)

```python
# Source: pipelines/etap/culture_pipeline.py:81
# Injection happens BEFORE publish:
content = inject_internal_links(content, current_blog=blog_id, max_links=5)

# CUAP equivalent (before publish):
body_md = inject_cross_blog_links(body_md, blog_id, max_links=3)
```

### ETAP Cross-Sell HTML Generation (proven pattern)

```python
# Source: pipelines/etap/culture_pipeline.py:96-98
cross_html = build_cross_sell_html(country=country, city=city, exclude_blog=blog_id, max_items=3)
if cross_html:
    content = insert_cross_sell_block(content, cross_html, position="bottom")

# CUAP equivalent:
cross_html = build_cross_sell_card(blog_id, max_items=4)
if cross_html:
    body_md = insert_cross_sell_block(body_md, cross_html, position="bottom")
```

### CUAP Blog Domain Mapping (from cuap.yaml)

```python
# Source: config/blogs.d/cuap.yaml
BLOG_DOMAINS = {
    "appliance-hugo": "https://appliance.informationhot.kr",
    "baby-hugo":      "https://baby.informationhot.kr",
    "fitness-hugo":   "https://fitness.informationhot.kr",
    "interior-hugo":  "https://interior.informationhot.kr",
    "laptop-hugo":    "https://laptop.informationhot.kr",
    "health-hugo":    "https://health.informationhot.kr",
    "pet-hugo":       "https://pet.informationhot.kr",
    "kitchen-hugo":   "https://kitchen.informationhot.kr",
    "beauty-hugo":    "https://beauty.informationhot.kr",
    "camping-hugo":   "https://camping.informationhot.kr",
}
```

### CUAP Cross-Sell Icons (from writer.py ADSENSE_AD pattern)

```python
# CUAP blog icons (category-based):
ICONS = {
    "laptop-hugo":    "💻",
    "appliance-hugo": "🏠",
    "interior-hugo":  "🪑",
    "baby-hugo":      "👶",
    "fitness-hugo":   "💪",
    "health-hugo":    "💊",
    "pet-hugo":       "🐾",
    "kitchen-hugo":   "🍳",
    "beauty-hugo":    "✨",
    "camping-hugo":   "⛺",
}
```

### Blowfish Theme single.html Key Integration Points

```html
<!-- Source: cuap/*/layouts/_default/single.html -->
<!-- Line 80-86: Article content area -->
<div class="article-content max-w-prose mb-20">
  {{ $content }}
</div>
{{ partial "series/series-closed.html" . }}
{{ partial "sharing-links.html" . }}
{{ partial "related.html" . }}                    <!-- LINE 85: REPLACE with cuap-spider-links.html -->
```

**Integration:** Replace `{{ partial "related.html" . }}` with `{{ partial "cuap-spider-links.html" . }}` on line 85 of all 10 CUAP single.html files.

### CUAP Pipeline Injection Point

```python
# Source: pipelines/curation/pipeline.py:905-948
# CURRENT FLOW:
#   Line 905: _HAS_CTA = "cta-box" in body_md or "cta_box" in body_md
#   Line 907-916: FALLBACK_CTA injection
#   Line 917: body_md += _FALLBACK_CTA
#   Line 920-946: tag_set creation
#   Line 948: result = publish(blog_id, title, body_md, ...)
#
# INSERT AFTER LINE 917 (after CTA fallback, before tags):
from shared.cuap_entity_linker import (
    inject_cross_blog_links,
    build_cross_sell_card,
    build_funnel_header,
    register_cuap_entity,
)
body_md = inject_cross_blog_links(body_md, blog_id, max_links=3)
cross_card = build_cross_sell_card(blog_id, max_items=4)
if cross_card:
    body_md += "\n\n" + cross_card
funnel = build_funnel_header(blog_id)
if funnel:
    body_md = funnel + "\n\n" + body_md

# INSERT AFTER LINE 969 (after publish success, before quality metrics):
register_cuap_entity("category", keyword, blog_id, slug, f"{keyword} 추천", 50, 1)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ETAP entity_linker.py (travel-en.db, city/country) | CUAP cuap_entity_linker.py (travel-en.db, category) | This phase | Separate modules, shared DB |
| related.html (same-blog only) | cuap-spider-links.html (cross-blog) | This phase | 10x more link targets |
| No cross-sell cards | build_cross_sell_card() (Python HTML) | This phase | Ad exposure opportunity |
| No funnel header | build_funnel_header() (Python HTML) | This phase | User navigation entry point |

**Deprecated/outdated:**
- `related.html` partial: Still exists but replaced by `cuap-spider-links.html` in CUAP blogs

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | pipeline.py | ✓ | 3.14 | — |
| sqlite3 (stdlib) | Entity DB | ✓ | stdlib | — |
| Hugo (extended) | Build | ✓ | ~0.122+ | — |
| Blowfish theme | Layouts | ✓ | installed | — |
| travel-en.db | Entity storage | ✓ | exists | — |
| wrangler | Deploy | ✓ | installed | — |

**Missing dependencies with no fallback:** None
**Missing dependencies with fallback:** None

## Validation Architecture

> Skip this section entirely — workflow.nyquist_validation is explicitly set to false in .planning/config.json.

## Security Domain

> Required when `security_enforcement` is enabled (absent = enabled). Omit only if explicitly `false` in config.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Entity names validated (len > 2), SQL parameterized queries |
| V4 Access Control | no | Internal system, no user auth |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via entity_name | Tampering | Parameterized queries (sqlite3 `?` placeholders) |
| XSS via entity link URLs | Tampering | URLs from trusted BLOG_DOMAINS dictionary only |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | All 10 CUAP single.html files are identical (md5: 4407c6c) | Hugo Layout | Low — verified by md5sum comparison |
| A2 | Blowfish theme renders raw HTML in markdown without escaping | Hugo Layout | Medium — test with `hugo server` before deploy |
| A3 | travel-en.db is writable by pipeline.py process | Database | Low — ETAP already uses it |
| A4 | CUAP pipeline has same publish() call signature as ETAP | Pipeline | Low — verified by reading both files |
| A5 | `showRelatedContent = false` in params.toml means related.html is NOT auto-rendered by Blowfish | Hugo Layout | Medium — need to verify if Blowfish calls related.html independently or only via single.html |

## Open Questions

1. **Does Blowfish theme auto-call related.html independent of single.html?**
   - What we know: `params.toml` has `showRelatedContent = false` — suggests Blowfish has its own related content mechanism
   - What's unclear: Whether `{{ partial "related.html" . }}` in single.html is the only call site
   - Recommendation: Verify by checking Blowfish theme source or testing with `hugo server`. If Blowfish has its own related mechanism, we may need to disable it in params.toml.

2. **Should cuap-spider-links.html fall back to related.html if no cross-blog links found?**
   - What we know: ETAP `build_cross_sell_html()` returns empty string if no links found
   - What's unclear: Whether CUAP should gracefully degrade to same-blog related posts
   - Recommendation: Yes — render `related.html` as fallback when `cuap-spider-links.html` has no data

3. **CROSS_GRAPH weight values — what initial weights?**
   - What we know: CONTEXT.md Decision 6 says fixed paths, weight values are agent's discretion
   - What's unclear: Specific weight numbers for primary vs secondary connections
   - Recommendation: Primary connections weight=100, secondary weight=50, use_cases weight=30 (can be tuned later)

## Sources

### Primary (HIGH confidence)
- `shared/entity_linker.py` — Full ETAP entity linking implementation (337 lines)
- `pipelines/curation/pipeline.py` — CUAP pipeline flow (1003 lines)
- `pipelines/curation/writer.py` — CUAP article generation (519 lines)
- `config/blogs.d/cuap.yaml` — All 10 CUAP blog definitions (212 lines)
- `pipelines/etap/culture_pipeline.py` — ETAP pipeline with entity_linker usage (262 lines)
- `pipelines/etap/post_processor.py:151-182` — insert_cross_sell_block() function
- `cuap/beauty-hugo/layouts/_default/single.html` — Blowfish single.html (125 lines)
- `cuap/beauty-hugo/layouts/partials/related.html` — Current related posts partial (18 lines)
- `cuap/beauty-hugo/config/_default/params.toml` — Blowfish theme config

### Secondary (MEDIUM confidence)
- `shared/publisher.py:865-924` — publish() function signature and flow
- Blowfish theme documentation — showRelatedContent behavior

### Tertiary (LOW confidence)
- (none — all findings verified against codebase)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are Python stdlib or existing project modules
- Architecture: HIGH — directly modeled on proven ETAP entity_linker.py pattern
- Pitfalls: HIGH — all pitfalls identified from existing code comments and ETAP experience

**Research date:** 2026-07-20
**Valid until:** 2026-08-20 (stable — stdlib + existing patterns)
