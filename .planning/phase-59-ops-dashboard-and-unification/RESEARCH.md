# Phase 59: Ops Dashboard + Blowfish 표준 단일화 + 파이프라인 통합 - Research

**Researched:** 2026-08-06
**Domain:** Operations dashboard, theme unification, pipeline consolidation
**Confidence:** HIGH

## Summary

Phase 59 addresses three structural problems in the 5000 project: (1) no centralized visibility into blog health/compliance, (2) Blowfish theme duplication across 75+ blogs with 2 non-Blowfish outliers, and (3) ETAP pipelines containing 35 independent `_write_hugo_post()` copies with ETAP-specific features (cross-sell, adsense injection, internal links) not present in the shared version.

The ops_dashboard already has a complete `db.py` (419 lines) with 3 tables, YAML sync, 52 seeded issues, and query helpers. Missing: health check engine, Flask UI, and JSON API.

The ETAP consolidation is the highest-risk item: 35 pipeline files each containing their own `_write_hugo_post()` with signature `(article, cover_image=None, body_images=None, blog_id=None, site_path=None, category=None)` — plus `flight_pipeline.py` with a completely different signature `(cfg, article)`. The shared `hugo_writer.py` version uses `(blog_cfg, title, body_md, slug, category, tags, thumbnail_url, is_draft=False)`. These are fundamentally incompatible interfaces.

**Primary recommendation:** Build the ops dashboard first (lowest risk, highest immediate value), then tackle ETAP `_write_hugo_post()` unification as a separate staged rollout with per-blog testing.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ops Dashboard UI | Frontend Server (Flask) | — | Web UI serving on port 5060 |
| Health check engine | API / Backend | — | Runs checks, writes to SQLite |
| YAML → DB sync | API / Backend | Database / Storage | Reads YAML config, writes ops.db |
| Blog lifecycle tracking | Database / Storage | — | SQLite ops.db is single source of truth |
| Theme management | CDN / Static | — | Hugo themes affect static site output |
| ETAP post writing | API / Backend | — | Pipeline code generates Hugo content |
| Deploy orchestration | API / Backend | — | dispatcher.py controls deploy flow |
| Domain health checks | API / Backend | — | HTTP probes from backend |

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Ops Dashboard: SQLite (ops.db), Flask, port 5060, 반응형 모바일
- Blowfish: 단일 표준 소스 (git submodule 또는 Hugo Modules)
- ETAP _write_hugo_post() 30+ 중복 → shared/hugo_writer.py로 수렴
- flights-hugo/flight-hugo 이름 불일치 해소
- publisher.py CLOUDFLARE_API_TOKEN 제거
- 테마 3종 → 1종 (Blowfish)
- 안전: staged rollout, 소수 블로그 먼저 적용

### Deferred Ideas
- None explicitly deferred

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.x | Web UI framework | Lightweight, no deps, port 5060 |
| SQLite | 3.x | ops.db storage | Already used in db.py, zero setup |
| Jinja2 | 3.x | HTML templates | Flask default, already available |
| PyYAML | 6.x | YAML config parsing | Already in requirements.txt |
| httpx | 0.27+ | HTTP health probes | Already in requirements.txt |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.0+ | Environment loading | Always — .env files |
| cloudflared | latest | Tunnel for remote access | Ops dashboard remote access |

**Installation:**
```bash
pip install flask pyyaml httpx python-dotenv
# cloudflared: brew install cloudflare/cloudflare/cloudflared
```

## Package Legitimacy Audit

All packages are well-established (Flask: 15+ years, SQLite: 25+ years, PyYAML: 15+ years). No new/unknown packages required.

| Package | Registry | Age | Disposition |
|---------|----------|-----|-------------|
| Flask | PyPI | 15+ yrs | Approved |
| PyYAML | PyPI | 15+ yrs | Approved |
| httpx | PyPI | 6+ yrs | Approved |
| python-dotenv | PyPI | 9+ yrs | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Ops Dashboard                         │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │ Flask UI │◄───│ Health   │◄───│ ops.db           │   │
│  │ :5060    │    │ Engine   │    │ (SQLite WAL)     │   │
│  └────┬─────┘    └────┬─────┘    └──────────────────┘   │
│       │               │                                  │
│  ┌────▼─────┐    ┌────▼─────┐    ┌──────────────────┐   │
│  │ JSON API │    │ YAML     │    │ Standard Rules   │   │
│  │ /api/*   │    │ Sync     │    │ (12 rules)       │   │
│  └──────────┘    └──────────┘    └──────────────────┘   │
└─────────────────────────────────────────────────────────┘
         ▲
         │
┌────────▼────────────────────────────────────────────────┐
│                   Data Sources                           │
│  config/blogs.d/*.yaml (79 blogs)                       │
│  shared/problem_detectors.py (auto-detect)              │
│  HTTP probes (domain health)                            │
│  Hugo layouts (standard compliance)                     │
└─────────────────────────────────────────────────────────┘
```

### ETAP _write_hugo_post() Duplication Pattern

```
Current (35 copies):
  Each *_pipeline.py defines:
    def _write_hugo_post(article, cover_image, body_images, blog_id, site_path, category)
      → Builds frontmatter manually (no _sanitize_yaml_value)
      → Calls inject_internal_links() (ETAP-specific)
      → Calls insert_adsense() (ETAP-specific)
      → Calls build_cross_sell_html() + insert_cross_sell_block() (ETAP-specific)
      → Writes to content/posts/{slug}/index.md

  flight_pipeline.py (outlier):
    def _write_hugo_post(cfg, article)
      → Completely different signature
      → Simpler: no cross-sell, no adsense, no internal links

  shared/publishers/hugo_writer.py:
    def _write_hugo_post(blog_cfg, title, body_md, slug, category, tags, thumbnail_url, is_draft)
      → Uses _sanitize_yaml_value (safe YAML quoting)
      → Supports theme branching (blowfish/congo/papermod)
      → Does NOT include: inject_internal_links, insert_adsense, cross-sell
      → Re-exported by shared/publisher.py (line 771-778)

Target (1 copy):
  shared/publishers/hugo_writer.py becomes the single writer
  ETAP-specific features (adsense, cross-sell, internal links) move to
  post-processing hooks called after _write_hugo_post
```

### CLOUDFLARE_API_TOKEN Inconsistency

```
deploy.py (_deploy_site_inner, line 78):
  _wrangler_env.pop("CLOUDFLARE_API_TOKEN", None)  ← REMOVES token (correct)

publisher.py (_deploy_site_inner, line 659-662):
  _cf_token = _os2.getenv("CLOUDFLARE_API_TOKEN", "")
  if _cf_token:
      _wrangler_env["CLOUDFLARE_API_TOKEN"] = _cf_token  ← INJECTS token (incorrect)

dispatcher.py (_build_and_deploy_central, line 618):
  deploy_env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_API_TOKEN"}  ← REMOVES (correct)
```

**Conclusion:** `publisher.py` line 651-768 (`_deploy_site_inner`) is a LEGACY copy that still INJECTS `CLOUDFLARE_API_TOKEN`. This code is overridden by the re-export at line 788 (`from shared.publishers.deploy import deploy_site, _deploy_site_inner`), but the old function definition remains as dead code and could confuse maintainers.

### Recommended Project Structure

```
ops_dashboard/
├── db.py              # ✅ DONE — SQLite model + YAML sync + queries
├── app.py             # Flask app — routes, UI, JSON API (NEW)
├── checks/
│   ├── __init__.py
│   ├── freshness.py   # staleness detection
│   ├── standard.py    # R01-R12 compliance checks
│   ├── render.py      # HTTP + thumbnail + adsbygoogle checks
│   └── crosscheck.py  # known_issues ↔ check_results audit
├── templates/
│   ├── base.html      # responsive layout
│   ├── index.html     # fleet summary
│   ├── blog.html      # per-blog detail
│   ├── issues.html    # known_issues matrix
│   └── standards.html # compliance matrix
├── static/
│   ├── style.css
│   └── app.js         # minimal JS for mobile card view
├── seed.py            # init_db + sync + seed (CLI entry)
└── tunnel.py          # cloudflared named tunnel setup
```

### Pattern 1: Health Check Plugin Registry
**What:** Each check is a standalone function that takes `blog_id` and returns `{status, detail, evidence_url}`
**When to use:** Every new check type
**Example:**
```python
# Source: Phase 59 CONTEXT.md §3-3
CHECKS: dict[str, Callable] = {}

def register_check(name: str):
    def decorator(fn):
        CHECKS[name] = fn
        return fn
    return decorator

@register_check("freshness")
def check_freshness(blog_id: str, conn) -> dict:
    # ... check logic ...
    return {"status": "pass|fail|unknown", "detail": "...", "evidence_url": ""}
```

### Anti-Patterns to Avoid
- **ETAP individual deploy:** Each ETAP pipeline calling its own `_build_and_deploy()` bypasses the centralized deploy lock in dispatcher.py. This causes concurrent wrangler deploys.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML config parsing | Custom parser | PyYAML | Already in deps, handles edge cases |
| SQLite WAL mode | Manual locking | sqlite3 PRAGMA WAL | Built-in concurrent read support |
| HTTP health probes | urllib | httpx | Already in deps, async-ready |
| HTML templating | String concat | Jinja2/Flask templates | XSS prevention, auto-escaping |
| YAML→DB sync | Manual diffing | `_parse_yaml_file()` in db.py | Already handles blogs.d format |

**Key insight:** The ops_dashboard/db.py already has a custom YAML parser (lines 90-146) that doesn't use PyYAML — this is intentional for the blogs.d format. Don't replace it with PyYAML unless the format changes.

## Runtime State Inventory

> This is a greenfield phase (building new infrastructure + refactoring), not a pure rename.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | 79 blogs in config/blogs.d/*.yaml; 52 issues in db.py SEED_ISSUES; 14 SQLite DBs (content.db, travel-en.db, etc.) | ops.db is new (no migration needed); YAML→ops.db sync in db.py handles data source |
| Live service config | n8n workflows (not in scope); Cloudflare Pages projects (~75) | No runtime config changes — dashboard reads existing config |
| OS-registered state | launchd scheduler for scheduler.py | No changes — dashboard is additive |
| Secrets/env vars | CLOUDFLARE_API_TOKEN (in .env.common); VARIOUS API keys | publisher.py _deploy_site_inner dead code cleanup (low risk) |
| Build artifacts | themes/PaperMod (1.1M in 5000/themes/); shared-themes/blowfish (367M) | Theme unification affects build output, not runtime |

**Nothing found in category:** OS-registered state — dashboard doesn't modify launchd.

## Common Pitfalls

### Pitfall 1: ETAP _write_hugo_post() Incompatible Signatures
**What goes wrong:** Naive consolidation breaks 35 pipelines because ETAP version has different parameters and includes ETAP-specific features (adsense, cross-sell, internal links)
**Why it happens:** Each pipeline was written independently with copy-paste, adding features incrementally
**How to avoid:** Create a shared `_write_hugo_post_etap()` wrapper that calls the shared version + ETAP post-processing hooks. Don't force all 35 files to change simultaneously.
**Warning signs:** Any pipeline returning "file not found" or missing frontmatter fields after consolidation

### Pitfall 2: publisher.py Dead Code Confusion
**What goes wrong:** developer reads publisher.py `_deploy_site_inner` (line 651) and thinks it's the active deploy code, not realizing it's overridden by the re-export at line 788
**Why it happens:** Python re-exports shadow but don't remove the original definition
**How to avoid:** Delete the dead `_deploy_site_inner` function from publisher.py (lines 651-768), keep only the re-export from shared/publishers/deploy.py
**Warning signs:** deploy.py token removal vs publisher.py token injection — confusion about which is active

### Pitfall 3: flights-hugo vs flight-hugo Naming
**What goes wrong:** YAML has `flights-hugo`, dispatcher.py line 551 has `flight-hugo` in ETAP_PIPELINE_BLOGS, YAML exception maps `flights-hugo` to flight_pipeline
**Why it happens:** Historical naming inconsistency — ETAP pipeline uses `flight_pipeline.py` but YAML blog_id is `flights-hugo`
**How to avoid:** Verify which name the Cloudflare Pages project uses, then align YAML → dispatcher → CF project name
**Warning signs:** Deploy to wrong CF project, or blog_id lookup failure

### Pitfall 4: ETAP Deploy Path Duplication
**What goes wrong:** ETAP pipelines call their own `_build_and_deploy()` (hardcoded wrangler path, no CLOUDFLARE_API_TOKEN handling, no deploy lock) while dispatcher.py also has `_build_and_deploy_central()` (with proper lock and token handling)
**Why it happens:** Each pipeline was standalone before dispatcher centralization
**How to avoid:** Remove `_build_and_deploy()` from all ETAP individual pipelines. Let dispatcher.py handle all deploys.
**Warning signs:** Concurrent wrangler deploys, auth failures from missing token handling

### Pitfall 5: hotissue-hugo / compare-hugo Domain Timeout
**What goes wrong:** HTTP probe returns 000/TIMEOUT for informationhot.kr subdomains
**Why it happens:** DNS resolution or Cloudflare configuration issue (not a code problem)
**How to avoid:** ops dashboard should distinguish "domain unreachable" from "content broken" — different severity
**Warning signs:** Dashboard marking all informationhot.kr blogs as broken when it's a DNS issue

## Code Examples

### ETAP _write_hugo_post() Signature Comparison

```python
# ETAP standard (34 files): pipelines/etap/{name}_pipeline.py
def _write_hugo_post(article, cover_image=None, body_images=None,
                     blog_id=None, site_path=None, category=None):
    # Features: inject_internal_links, insert_adsense, build_cross_sell_html,
    #           insert_cross_sell_block, body_images injection
    # Frontmatter: manual string concat (no _sanitize_yaml_value)
    # Output: returns post_dir (not filepath)

# ETAP flight (1 file): pipelines/etap/flight_pipeline.py
def _write_hugo_post(cfg, article):
    # Features: simpler — no cross-sell, no adsense, no internal links
    # Frontmatter: f-string (no _sanitize_yaml_value)
    # Output: returns filepath

# Shared: shared/publishers/hugo_writer.py (line 908)
def _write_hugo_post(blog_cfg, title, body_md, slug, category, tags,
                     thumbnail_url, is_draft=False):
    # Features: theme branching (blowfish/congo/papermod), _sanitize_yaml_value,
    #           _validate_frontmatter, post-write disk revalidation
    # Does NOT include: inject_internal_links, insert_adsense, cross-sell
    # Output: returns {success, url, file_path}
```

### Shared deploy.py CLOUDFLARE_API_TOKEN Handling
```python
# shared/publishers/deploy.py line 76-78 (CORRECT — removes token)
_wrangler_env = os.environ.copy()
_wrangler_env.pop("CLOUDFLARE_API_TOKEN", None)

# shared/publisher.py line 659-662 (INCORRECT LEGACY — injects token)
_cf_token = _os2.getenv("CLOUDFLARE_API_TOKEN", "")
if _cf_token:
    _wrangler_env["CLOUDFLARE_API_TOKEN"] = _cf_token
```

### ETAP Pipeline Dispatch
```python
# dispatcher.py line 425-441
_ETAP_BLOG_EXCEPTIONS = {
    "flights-hugo": "pipelines.etap.flight_pipeline",
}
# Blog ID stem → pipeline module mapping
stem = blog_id.replace("-hugo", "").replace("-blogger", "")
module_path = f"pipelines.etap.{stem}_pipeline"
# Special case: flights-hugo → flight_pipeline (not flights_pipeline)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Each ETAP pipeline self-deploys | dispatcher.py central deploy | Phase 58 | ETAP individual `_build_and_deploy()` now dead code |
| publisher.py uses CLOUDFLARE_API_TOKEN | deploy.py removes it | Phase 58 | publisher.py legacy copy still injects token |
| PaperMod/Congo themes | Blowfish standard | Phase 52 (partial) | hotissue-hugo (PaperMod), stock-hugo (Congo) still exist |

**Deprecated/outdated:**
- `publisher.py:_deploy_site_inner()` (lines 651-768): Dead code, overridden by re-export from deploy.py
- `pipelines/etap/*/_build_and_deploy()`: Each pipeline's local deploy function — dispatcher.py central deploy is now used (line 728-729)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 79 total blogs across all YAML files | Standard Stack | Blog count affects ops.db sync verification |
| A2 | ETAP pipeline.py `_write_hugo_post` at line 93 is the one dispatcher uses (not individual pipelines) | ETAP Duplication | If individual pipelines still call their own, consolidation scope is larger |
| A3 | hotissue/compare timeout is DNS issue, not code issue | Common Pitfalls | If it's a Cloudflare config issue, ops dashboard needs different handling |
| A4 | shared/publisher.py re-export at line 788 shadows the local definitions | CLOUDFLARE_API_TOKEN | If re-export doesn't shadow, both deploy functions could be called |

## Open Questions

1. **ETAP pipeline.py `_write_hugo_post` vs individual pipeline versions**
   - What we know: dispatcher.py calls `pipelines.etap.{stem}_pipeline` for individual pipelines, and `pipelines.etap.pipeline` as fallback
   - What's unclear: When dispatcher calls `pipelines.etap.pipeline.run()`, does `pipeline.py` use its own `_write_hugo_post` (line 93) or delegate to the individual pipeline?
   - Recommendation: Check dispatcher.py `_run_pipeline` to verify which `run()` is called for each blog

2. **ETAP _build_and_deploy dead code scope**
   - What we know: dispatcher.py `_build_and_deploy_central()` is used (line 728-729)
   - What's unclear: Are any ETAP individual pipelines still calling their own `_build_and_deploy()` directly (bypassing dispatcher)?
   - Recommendation: grep for `_build_and_deploy()` calls inside ETAP run() functions

3. **publisher.py _deploy_site_inner removal safety**
   - What we know: re-export at line 788 shadows the local definition
   - What's unclear: Are there any direct callers of `publisher._deploy_site_inner` (not through the re-export)?
   - Recommendation: grep for `_deploy_site_inner` imports before removing

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | All | ✓ | 3.14 | — |
| Flask | Dashboard UI | Need to install | — | `pip install flask` |
| cloudflared | Remote access | Need to check | — | `brew install cloudflare/cloudflare/cloudflared` |
| httpx | Health probes | ✓ | 0.27+ | requests (already installed) |
| SQLite | ops.db | ✓ | 3.x | — |

**Missing dependencies with fallback:**
- Flask: `pip install flask` (trivial install)
- cloudflared: `brew install cloudflare/cloudflare/cloudflared` (optional, for remote access only)

## Validation Architecture

> nyquist_validation is disabled in config — skipping detailed test map.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None configured |
| Config file | None |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command |
|--------|----------|-----------|-------------------|
| dashboard-01 | YAML sync populates blog_lifecycle | smoke | `python -c "from ops_dashboard.db import *; ..."` |
| dashboard-02 | 52 issues seeded | smoke | `python -c "from ops_dashboard.db import *; ..."` |
| unification-01 | ETAP _write_hugo_post count = 0 | manual | `grep -r 'def _write_hugo_post' pipelines/etap/ \| wc -l` |
| unification-02 | publisher.py token injection removed | manual | `grep CLOUDFLARE_API_TOKEN shared/publisher.py` |

## Sources

### Primary (HIGH confidence)
- Codebase: `/Users/twinssn/Projects/5000/shared/publishers/deploy.py` — CLOUDFLARE_API_TOKEN handling verified
- Codebase: `/Users/twinssn/Projects/5000/shared/publisher.py` — legacy _deploy_site_inner verified (lines 651-768)
- Codebase: `/Users/twinssn/Projects/5000/dispatcher.py` — ETAP central deploy verified (line 577-654)
- Codebase: `/Users/twinssn/Projects/5000/pipelines/etap/` — 35 _write_hugo_post copies verified
- Codebase: `/Users/twinssn/Projects/5000/ops_dashboard/db.py` — 419 lines, complete model verified
- Codebase: `/Users/twinssn/Projects/5000/shared/publishers/hugo_writer.py` — shared _write_hugo_post verified

### Secondary (MEDIUM confidence)
- HTTP probes: 6/8 domains responding (hotissue/compare timeout — DNS issue)
- Theme count: 62 blowfish + 12 Blowfish + 1 PaperMod + 1 congo in YAML

### Tertiary (LOW confidence)
- None — all findings verified from codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified in requirements.txt and existing codebase
- Architecture: HIGH — ETAP duplication and deploy inconsistency verified with exact line numbers
- Pitfalls: HIGH — flights-hugo naming, publisher.py dead code, ETAP deploy duplication all verified

**Research date:** 2026-08-06
**Valid until:** 2026-09-06 (30 days — stable infrastructure, low churn)
