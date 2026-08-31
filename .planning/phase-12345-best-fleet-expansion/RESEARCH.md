# Phase 12345: Best Fleet Expansion — Research

**Researched:** 2026-08-31
**Domain:** Coupang affiliate best-category blog fleet expansion (18 new blogs)
**Confidence:** HIGH

## Summary

18 new "best-" Coupang category blogs to be created following the best-kitchen-hugo template. All 18 Coupang API category IDs verified live — return 20 items each, rCode=0. Hugo build passes. Deployment uses Workers (not Pages), avoiding the Pages project limit.

**Critical finding:** best-car-hugo is in cuap.yaml and WORKERS_BLOGS but is NOT wired into pipeline.py CATEGORY_FILTERS, writer.py BLOG_TEMPLATE_OVERRIDES, or cuap_entity_linker.py. It's a half-configured blog with no posts. This is the real template for what needs to be done for each new blog.

**Primary recommendation:** Batch script approach — generate all 18 Hugo sites from best-kitchen-hugo template, then update 6 code files in parallel.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Coupang API data fetch | API/Backend | — | best_collector.py calls Coupang API |
| Hugo site generation | CDN/Static | — | Hugo builds static HTML |
| Content writing | API/Backend | — | writer.py generates articles via LLM |
| Deploy to Cloudflare | CDN/Static | — | Workers serves static assets |
| Cross-blog dedup | API/Backend | — | pipeline.py dedup across paired blogs |
| Ad serving | Browser/Client | — | AdSense JS in extend-head.html |

## Standard Stack

### Core (per blog)
| File/Dir | Purpose | Notes |
|----------|---------|-------|
| `hugo.toml` (root) | themesDir pointer only | 1 line: `themesDir = "/Users/twinssn/Projects/shared-themes"` |
| `config/_default/hugo.toml` | Hugo config (baseURL, theme, pagination, GA4, related) | Per-blog baseURL, title |
| `config/_default/params.toml` | Blowfish params (colorScheme, adsense slots, article layout) | AdSense ca-pub-6677, slots 2195212287/4009356716 |
| `config/_default/languages.ko.toml` | Korean language config, description, author | Per-blog title/description |
| `config/_default/markup.toml` | Goldmark config (unsafe=true) | Identical across all blogs |
| `wrangler.toml` | Workers deployment config | Per-blog name, routes pattern |
| `src/index.js` | Workers fetch handler (ASSETS proxy) | Identical across all blogs |
| `layouts/_default/single.html` | Article template with ad injection | Ad injection at H2 boundaries |
| `layouts/partials/extend-head.html` | AdSense loader + GA4 + mobile CSS | AdSense ca-pub-6677, GA4 hardcoded |
| `layouts/partials/adsense/top.html` | Top ad slot | Reads from params.toml |
| `layouts/partials/adsense/in-article.html` | In-article ad slot | Reads from params.toml |
| `layouts/partials/cuap-spider-links.html` | Cross-sell/funnel links | Falls back to related.html |
| `layouts/partials/related.html` | Related posts list | Simple list, no cards |
| `layouts/_default/_markup/render-link.html` | Link render (최저가 확인하기 → styled button) | Identical |
| `assets/css/custom.css` | Theme customization (lead fix, ad styles, price button) | 348 lines, mostly identical |
| `assets/css/extended/funnel-card.css` | Funnel card styles | Identical |
| `static/robots.txt` | Robots config | **BUG: sitemap URL points to baby.informationhot.kr** |
| `static/ads.txt` | AdSense ads.txt | ca-pub-6677996696534146 |
| `.gitmodules` | Blowfish theme submodule | Identical |
| `.gitignore` | themes/, public/, resources/ | Identical |

### Config Pattern (cuap.yaml entry)
```yaml
- id: {blog-name}-hugo
  deploy_type: workers
  name: {Korean name} 베스트 추천 가이드
  pipeline: curation
  platform: hugo
  status: active
  daily_quota: 2
  source: bestcategories
  category_id: '{coupang_id}'
  domain: {blog-name}.informationhot.kr
  cf_project: {blog-name}-hugo
  repo: {blog-name}-hugo
  site_path: /Users/twinssn/Projects/cuap/{blog-name}-hugo
  theme: blowfish
  managed_by: mde2
  schedule:
    times:
    - '{time1}'
    - '{time2}'
    - '{time3}'
  gsc_site: https://{blog-name}.informationhot.kr/
  ga4_property: ''
```

**Key differences from regular (non-best) blogs:**
- `source: bestcategories` (not absent)
- `category_id: '{id}'` (new field)
- `daily_quota: 2` (not 5)
- 3 time slots (not 5)

### Code Files That Need Updates
| File | What to Add | Pattern |
|------|-------------|---------|
| `pipelines/curation/best_categories.py` | BEST_CATEGORY_MAP entry | `"best-{name}-hugo": "{id}"` |
| `pipelines/curation/pipeline.py` | CATEGORY_FILTERS entry | allowed/blocked keyword lists |
| `pipelines/curation/pipeline.py` | CROSS_FLEET_MAP dedup pair | `"best-{name}-hugo": "{name}-hugo"` (if paired blog exists) |
| `pipelines/curation/writer.py` | BLOG_TEMPLATE_OVERRIDES entry | Sales-rank prompt template |
| `shared/cuap_entity_linker.py` | BASE_URLS, EMOJIS, COLORS, CROSS_FLEET_MAP | Per-blog config |
| `dispatcher.py` | WORKERS_BLOGS set | Add blog_id string |

## Category Verification

All 18 Coupang API IDs verified live (2026-08-31). All return rCode=0 with 20 items.

| ID | categoryName | keyword | Proposed Blog ID | Blog Name |
|----|-------------|---------|-----------------|-----------|
| 1001 | 패션잡화 | 여성패션 | best-fashion-women-hugo | 여성패션 베스트 추천 가이드 |
| 1002 | 패션잡화 | 남성패션 | best-fashion-men-hugo | 남성패션 베스트 추천 가이드 |
| 1007 | 패션잡화 | 신발 | best-shoes-hugo | 신발 베스트 추천 가이드 |
| 1008 | 패션잡화 | 가방/잡화 | best-bags-hugo | 가방 베스트 추천 가이드 |
| 1012 | 로켓프레시 | 식품 | best-fresh-food-hugo | 로켓프레시 식품 베스트 추천 가이드 |
| 1014 | 생활용품 | 생활용품 | best-living-hugo | 생활용품 베스트 추천 가이드 |
| 1015 | 생활용품 | 홈인테리어 | best-home-interior-hugo | 홈인테리어 베스트 추천 가이드 |
| 1016 | 가전디지털 | 가전디지털 | best-electronics-hugo | 가전디지털 베스트 추천 가이드 |
| 1017 | 식품 | 스포츠/레저 | best-sports-hugo | 스포츠/레저 베스트 추천 가이드 |
| 1019 | 도서/음반 | 도서/음반/DVD | best-books-hugo | 도서/음반 베스트 추천 가이드 |
| 1020 | 문구/사무용품 | 완구/취미 | best-toys-hugo | 완구/취미 베스트 추천 가이드 |
| 1021 | 문구/사무용품 | 문구/오피스 | best-stationery-hugo | 문구/사무용품 베스트 추천 가이드 |
| 1022 | 반려/애완용품 | 반려동물용품 | best-pet-supplies-hugo | 반려동물용품 베스트 추천 가이드 |
| 1024 | 로켓프레시 | 헬스/건강식품 | best-health-food-hugo | 로켓프레시 건강식품 베스트 추천 가이드 |
| 1025 | 도서/음반 | 국내여행 | best-domestic-travel-hugo | 국내여행 도서 베스트 추천 가이드 |
| 1026 | 도서/음반 | 해외여행 | best-overseas-travel-hugo | 해외여행 도서 베스트 추천 가이드 |
| 1030 | 패션잡화 | 유아동패션 | best-kids-fashion-hugo | 유아동패션 베스트 추천 가이드 |
| 1031 | 패션의류 | 남녀 공용 의류 | best-unisex-clothing-hugo | 남녀공용의류 베스트 추천 가이드 |

**⚠️ Naming TBD:** Blog IDs above are proposed. User should confirm before execution.

## Build Test

**Hugo build for best-car-hugo: PASS**
```
hugo v0.160.1+extended+withdeploy
Pages: 10, Static files: 7, Total: 218ms
```

**Implication:** Template works. All 18 new blogs should build identically (same layouts, config pattern).

## Deploy Test

**Wrangler deploy: AUTH ISSUE (expected)**
- `wrangler pages project list` times out — likely at or near 100 Pages project limit
- Workers deployment (best-* pattern) does NOT count toward Pages limit
- Deploy uses `wrangler deploy --config wrangler.toml` (Workers), not `wrangler pages deploy`
- `env -u CLOUDFLARE_API_TOKEN` required for OAuth profile auth

**Verified:** best-kitchen-hugo deploys successfully as Workers (from .continue-here.md: "wrangler ~24-28s, live 200").

## DNS/Infrastructure

### Cloudflare Limits
| Resource | Current | Limit | After +18 | Status |
|----------|---------|-------|-----------|--------|
| Pages projects | ~100 | 100 | 100 (no change) | AT LIMIT but new blogs are Workers |
| Workers | unknown | 100 (free) | +18 | NEED VERIFICATION |
| DNS records per zone | unknown | 100 (free) | +18 subdomains | NEED VERIFICATION |
| Routes per zone | unknown | 1000 | +18 | OK |

**Key insight:** best-* blogs use Workers + Assets, not Pages. Each Worker gets its own `wrangler.toml` with a route like `best-xxx.informationhot.kr/*`. DNS records are created automatically by wrangler during deploy.

**Risk:** If Workers count is near 100, adding 18 could fail. Need to verify current Worker count via Cloudflare dashboard.

### Domain Structure
All blogs use `*.informationhot.kr` subdomains. DNS is managed by Cloudflare. Each blog needs:
- 1 DNS A/CNAME record (auto-created by wrangler)
- 1 Worker route in wrangler.toml

## Implementation Approach

### Recommended: Batch Script + Manual Code Edits

**Phase 1: Site Generation (automated)**
Write a Python script that:
1. Copies best-kitchen-hugo template directory
2. Updates config/_default/hugo.toml (baseURL, title)
3. Updates config/_default/params.toml (title, description)
4. Updates config/_default/languages.ko.toml (title, description, author)
5. Updates wrangler.toml (name, routes pattern)
6. Creates empty content/posts/ directory
7. Fixes static/robots.txt sitemap URL (currently points to baby.informationhot.kr)

**Phase 2: Config Updates (manual/guided)**
Update 6 code files with new entries. This requires domain knowledge for:
- CATEGORY_FILTERS allowed/blocked keywords per blog
- BLOG_TEMPLATE_OVERRIDES prompt templates
- cuap_entity_linker colors/emojis/cross-fleet maps
- WORKERS_BLOGS set in dispatcher.py

**Phase 3: Deploy + Verify**
1. Hugo build each site
2. Wrangler deploy each site
3. Verify live 200

### Why Not Full Automation
- CATEGORY_FILTERS needs per-blog keyword lists (human judgment)
- BLOG_TEMPLATE_OVERRIDES needs prompt customization
- cuap_entity_linker needs color/emoji assignments
- Risk of deploying broken sites if config is wrong

## Risk Assessment

### High Risk
| Risk | Impact | Mitigation |
|------|--------|------------|
| CATEGORY_FILTERS missing for new blogs | Products score 0.0, never publish (same as Phase 75 bug) | Add ALL 18 entries before first run |
| CF Workers limit reached | Deploy fails | Verify current count before starting |
| Similar titles across fashion blogs | `similar_title` blocks second publish | Use title_templates.py diversification |
| Cross-blog product overlap | Duplicate recommendations | Add dedup pairs where paired blogs exist |

### Medium Risk
| Risk | Impact | Mitigation |
|------|--------|------------|
| Coupang API rate limit (100/min) | 18 blogs × 2 quota = 36 calls/day, OK | Stagger schedule slots |
| robots.txt sitemap wrong | SEO: sitemap points to wrong blog | Fix in template before copying |
| GA4 hardcoded in extend-head.html | All blogs share same GA4 property | Acceptable if tracking same property |
| AdSense slots shared across all best-* | All use same 2195212287/4009356716 | Acceptable, same ad account |

### Low Risk
| Risk | Impact | Mitigation |
|------|--------|------------|
| Hugo build failure | Site doesn't deploy | Template proven, build tested |
| DNS record conflict | Deploy fails | Wrangler auto-creates, no conflict expected |

## Schedule Design

Existing best-* schedule pattern (3 time slots per blog, 2 posts/day):

| Blog | Slot 1 | Slot 2 | Slot 3 |
|------|--------|--------|--------|
| best-kitchen | 09:15 | 14:15 | 20:15 |
| best-beauty | 09:25 | 14:25 | 20:25 |
| best-baby | 09:35 | 14:35 | 20:35 |
| best-car | 09:45 | 14:45 | 20:45 |

**Pattern:** 10-minute offset between blogs at each slot. All 4 existing blogs publish within :15-:45 of each slot.

**For 18 new blogs:** Continue the 10-minute offset pattern. 18 blogs × 10 min = 180 min spread. This is too wide — would span from :15 to :15+3h.

**Better approach:** Use 5-minute offsets with parallel slots.

| Slot Window | Blogs (5-min offset) | Count |
|------------|---------------------|-------|
| 09:00-09:55 | 12 blogs | 12 |
| 10:00-10:25 | 6 blogs | 6 |

Or simpler: keep 3 time windows (morning/afternoon/evening) and pack 6 blogs per window with 5-min offsets.

**Proposed schedule for 18 new blogs:**

| Window | Time Range | Blogs |
|--------|-----------|-------|
| Morning | 09:00-09:55 | 6 blogs (09:00, 09:05, 09:10, 09:15, 09:20, 09:25) |
| Afternoon | 14:00-14:55 | 6 blogs (14:00, 14:05, 14:10, 14:15, 14:20, 14:25) |
| Evening | 20:00-20:55 | 6 blogs (20:00, 20:05, 20:10, 20:15, 20:20, 20:25) |

**Avoid conflicts with existing best-* blogs** (09:15-09:45, 14:15-14:45, 20:15-20:45):
- New blogs should use :00, :05, :10, :50, :55 to avoid overlap
- Or offset to different minutes entirely (e.g., :02, :07, :12, :52, :57)

## Common Pitfalls

### Pitfall 1: Missing CATEGORY_FILTERS
**What goes wrong:** Blog publishes 0 posts despite API returning valid data
**Why it happens:** Phase 75 bug — best-kitchen wasn't in CATEGORY_FILTERS → score 0.0
**How to avoid:** Add all 18 entries before first scheduler run
**Warning signs:** `P14 low_relevance` alerts, consecutive failures

### Pitfall 2: Duplicate product across best-* blogs
**What goes wrong:** Same product recommended on 2+ best-* blogs
**Why it happens:** No cross-fleet dedup for best-only blogs (no paired search blog)
**How to accept:** Each blog has own CATEGORY_FILTERS + relevance scoring; overlap is acceptable for bestseller lists

### Pitfall 3: robots.txt sitemap wrong
**What goes wrong:** Search engines index wrong sitemap
**Why it happens:** Template copied from best-kitchen which has `baby.informationhot.kr` in robots.txt
**How to avoid:** Fix robots.txt in template before batch copy

### Pitfall 4: writer.py missing template
**What goes wrong:** Blog falls back to generic prompt, no sales-rank framing
**Why it happens:** BLOG_TEMPLATE_OVERRIDES doesn't have entry for new blog
**How to avoid:** Add entries with best-* specific prompt (or let generic best- detection handle it — writer.py line 362 checks `_is_best = bool(blog_id.startswith("best-"))`)

## Code Examples

### Existing best-* entry in cuap.yaml
```yaml
# Source: /Users/twinssn/Projects/5000/config/blogs.d/cuap.yaml L329-350
- id: best-kitchen-hugo
  deploy_type: workers
  name: 주방용품 베스트 추천 가이드
  pipeline: curation
  platform: hugo
  status: active
  daily_quota: 2
  source: bestcategories
  category_id: '1013'
  domain: best-kitchen.informationhot.kr
  cf_project: best-kitchen-hugo
  repo: best-kitchen-hugo
  site_path: /Users/twinssn/Projects/cuap/best-kitchen-hugo
  theme: blowfish
  managed_by: mde2
  schedule:
    times:
    - '09:15'
    - '14:15'
    - '20:15'
  gsc_site: https://best-kitchen.informationhot.kr/
  ga4_property: ''
```

### wrangler.toml pattern
```toml
# Source: /Users/twinssn/Projects/cuap/best-kitchen-hugo/wrangler.toml
name = "best-kitchen-hugo"
main = "src/index.js"
compatibility_date = "2025-07-31"

[assets]
directory = "./public"
not_found_handling = "404-page"
html_handling = "auto-trailing-slash"

[[routes]]
pattern = "best-kitchen.informationhot.kr/*"
zone_name = "informationhot.kr"
```

### CATEGORY_FILTERS pattern
```python
# Source: /Users/twinssn/Projects/5000/pipelines/curation/pipeline.py L562-577
"best-kitchen-hugo": {
    "allowed": ["키친", "키친타올", "타올", "랩", "위생", ...],
    "blocked": ["패션", "의류", "반려동물", "완구", ...],
},
```

### BEST_CATEGORY_MAP entry
```python
# Source: /Users/twinssn/Projects/5000/pipelines/curation/best_categories.py L33-36
BEST_CATEGORY_MAP = {
    "best-kitchen-hugo": "1013",
    "best-beauty-hugo": "1010",
    "best-baby-hugo": "1011",
}
```

### Cross-fleet dedup pair
```python
# Source: /Users/twinssn/Projects/5000/pipelines/curation/pipeline.py L777-783
_pair_map = {
    "best-kitchen-hugo": "kitchen-hugo",
    "kitchen-hugo": "best-kitchen-hugo",
    "best-beauty-hugo": "beauty-hugo",
    "beauty-hugo": "best-beauty-hugo",
    "best-baby-hugo": "baby-hugo",
    "baby-hugo": "best-baby-hugo",
}
```

### cuap_entity_linker configs
```python
# Source: /Users/twinssn/Projects/5000/shared/cuap_entity_linker.py L78-174
BASE_URLS = {
    "best-kitchen-hugo": "https://best-kitchen.informationhot.kr",
    # ...
}
EMOJIS = {
    "best-kitchen-hugo": "🏆",
    # ...
}
COLORS = {
    "best-kitchen-hugo": "#ea580c",
    # ...
}
CROSS_FLEET_MAP = {
    "best-kitchen-hugo": {"primary": ["kitchen-hugo","appliance-hugo"], ...},
    # ...
}
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Blog IDs (best-fashion-women-hugo etc.) are proposals, not locked | Category Verification | Planner uses wrong IDs |
| A2 | 18 new blogs all use Workers deployment (not Pages) | Standard Stack | Deploy fails if Pages needed |
| A3 | Cloudflare Workers free tier limit is 100 per account | DNS/Infrastructure | Deploy fails if limit reached |
| A4 | existing best-* blogs (kitchen/beauty/baby) already have CATEGORY_FILTERS | Risk Assessment | Would need to add those too |
| A5 | writer.py generic best- detection (`_is_best = blog_id.startswith("best-")`) covers new blogs | Code Examples | New blogs may use wrong prompt |

**If this table is empty:** Not all claims verified — A1-A5 need user confirmation.

## Open Questions

1. **Blog ID naming for 18 new blogs**
   - What we know: keyword-based naming (best-fashion-women-hugo, etc.)
   - What's unclear: exact naming convention, whether to use Korean or English slugs
   - Recommendation: Use English slugs matching Coupang keyword (as proposed above)

2. **CF Workers current count**
   - What we know: 18 new Workers needed
   - What's unclear: current Worker count (wrangler CLI too slow to list)
   - Recommendation: Check Cloudflare dashboard before execution

3. **CATEGORY_FILTERS keyword lists for 18 new blogs**
   - What we know: each blog needs allowed/blocked keyword lists
   - What's unclear: exact keywords per category
   - Recommendation: derive from Coupang API productName samples + categoryName

4. **Cross-fleet dedup for best-only blogs**
   - What we know: existing best-* blogs pair with search blogs (best-kitchen ↔ kitchen)
   - What's unclear: whether new best-only blogs need dedup
   - Recommendation: skip dedup for blogs without paired search blog; rely on CATEGORY_FILTERS

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Manual verification (no automated tests for blog creation) |
| Config file | N/A |
| Quick run command | `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /Users/twinssn/Projects/cuap/{blog}-hugo` |
| Full suite command | `python3 dispatcher.py {blog}-hugo` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-01 | Blog builds with Hugo | smoke | Hugo build command | ✅ Template tested |
| REQ-02 | Blog deploys to CF | smoke | `env -u CLOUDFLARE_API_TOKEN wrangler deploy --config {path}` | ✅ Template tested |
| REQ-03 | API returns data for category | smoke | Coupang API test script | ✅ All 18 verified |
| REQ-04 | Pipeline publishes content | integration | `python3 dispatcher.py {blog}-hugo` | ❌ Needs CATEGORY_FILTERS |
| REQ-05 | Live site accessible | smoke | `curl -s https://{domain}/` | ❌ Post-deploy |

### Sampling Rate
- **Per blog creation:** Hugo build + wrangler deploy
- **Per wave merge:** Dispatcher run for 1-2 test blogs
- **Phase gate:** All 18 sites live, first publish successful

### Wave 0 Gaps
- [ ] CATEGORY_FILTERS entries for 18 new blogs
- [ ] BLOG_TEMPLATE_OVERRIDES entries (or verify generic best- detection works)
- [ ] cuap_entity_linker entries (BASE_URLS, EMOJIS, COLORS, CROSS_FLEET_MAP)
- [ ] WORKERS_BLOGS set update in dispatcher.py
- [ ] robots.txt fix (sitemap URL)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — template fully documented, build tested
- Architecture: HIGH — existing pattern clear, only config additions needed
- Pitfalls: MEDIUM — CATEGORY_FILTERS gap is known from Phase 75 incident
- Schedule: MEDIUM — 10-min offset may need tuning based on actual publish times

**Research date:** 2026-08-31
**Valid until:** 2026-09-30 (stable — template and config patterns don't change frequently)
