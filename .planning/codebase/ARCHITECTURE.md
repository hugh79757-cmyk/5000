---
focus: arch
last_mapped: 2026-06-30
version: 1
---

# Architecture

## System Overview

The system is a **multi-pipeline automated content generation and publishing platform** targeting 50+ Korean and English blogs. It generates articles via OpenAI GPT, publishes to Cloudflare Pages (Hugo static sites) and legacy Blogger/WordPress, then notifies search engines via IndexNow.

```
┌──────────────────────────────────────────────────────────┐
│                    Scheduler (scheduler.py)                │
│  launchd → schedule loop → dispatcher.py {blog_id}        │
└─────────────────────────┬────────────────────────────────┘
                          │ blog_id + config
                          ▼
┌──────────────────────────────────────────────────────────┐
│                 Dispatcher (dispatcher.py)                 │
│  Routes by pipeline type → loads config from blogs.yaml   │
│  Records in publish_ledger, handles failures              │
└──┬────┬────┬────┬────┬────┬────┬────┬────┬────┬─────────┘
   │    │    │    │    │    │    │    │    │    │
   ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼
 car  etap  gap  rap  senior  stock  travel  tap  curation
```

## Pipeline Architecture

Each pipeline follows a **fetch → generate → publish → deploy** flow:

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Fetch    │ → │ Generate │ → │ Publish  │ → │  Deploy  │
│ (data)    │   │ (OpenAI) │   │ (Hugo/   │   │(Wrangler)│
│           │   │          │   │ Blogger) │   │          │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
                     │
                     ▼
              ┌──────────────┐
              │  Humanizer   │
              │(ai output→   │
              │ natural text)│
              └──────────────┘
```

### Pipeline Types

| Pipeline | Directory | Blogs | Output Platform | Content Type |
|----------|-----------|-------|-----------------|--------------|
| **etap** | `pipelines/etap/` | 30+ | Cloudflare Pages + Hugo | English travel guides |
| **car** | `pipelines/car/` | 8 | Cloudflare Pages + Hugo | Korean automotive |
| **senior** | `pipelines/senior/` | ~5 | Cloudflare Pages + Hugo | Senior welfare |
| **gap** | `pipelines/gap/` | ~3 | Cloudflare Pages + Hugo | General content |
| **rap** | `pipelines/rap/` | ~3 | Cloudflare Pages + Hugo | Real estate |
| **stock** (via STAP) | external | 6 | Cloudflare Pages + Hugo | Stock/finance |
| **travel** | `pipelines/travel/` | ~5 | Cloudflare Pages + Hugo | Korean travel |
| **tap** (via TAP) | external | 1 | Blogger.com | Korean travel |
| **curation** | `pipelines/curation/` | ~3 | Cloudflare Pages + Hugo | Curated content |

## Data Flow

### Content Generation Flow
1. **Scheduler** (`scheduler.py:1`) checks `blogs.yaml` schedule, calls dispatcher per blog_id
2. **Dispatcher** (`dispatcher.py:272`) routes by pipeline type:
   - In-process: car, etap, gap, rap, senior, travel, curation
   - Subprocess (isolated): tap (TAP), stock (STAP)
3. **Pipeline** fetches source data from SQLite, calls `shared/ai_writer.py` for generation
4. **Humanizer** (`shared/humanizer.py`) post-processes AI output (removes AI-isms)
5. **Publisher** writes Hugo markdown or calls Blogger/WordPress API
6. **Deployer** runs Hugo build → wrangler pages deploy (Cloudflare Pages)

### Cross-Blog Entity Linking
- `shared/entity_linker.py` injects internal links across blogs
- TAP entity manager provides card-style cross-references for travel blogs
- ETAP pipelines inject product cards, AdSense blocks, cross-sell blocks

### Monitoring Flow
- `shared/monitor.py`: Daily publish counts per blog
- `shared/daily_report.py`: Cross-project aggregation (TAP, LAP, etc.)
- `shared/ledger_sync.py`: Syncs publish logs from pipeline DBs to central `content.db`

## Entry Points

| Entry Point | Purpose | Invocation |
|-------------|---------|------------|
| `dispatcher.py` | Main router — `python dispatcher.py {blog_id}` | Scheduler / manual |
| `scheduler.py` | Continuous scheduler loop | `launchd` / manual |
| `scripts/indexnow.py` | IndexNow URL submission | CLI / GitHub Actions |
| `workers/redirect-worker.js` | URL redirects | Cloudflare Workers HTTP |
| `functions/_middleware.js` | Pages middleware | Cloudflare Pages HTTP |

## Key Design Decisions

- **SQLite per pipeline**: No central DB system — each pipeline owns its data
- **Subprocess isolation**: STAP/TAP run as isolated subprocesses with dedicated venvs
- **Layered config**: `blogs.yaml` + `blogs.d/*.yaml` merged at runtime
- **File-system deploys**: Hugo sites are written to `content/posts/{slug}/index.md` then built
- **Deploy serialization**: `flock()` lock at `/tmp/wrangler_deploy.lock` prevents concurrent wrangler deploys
- **YAML-driven scheduling**: Blog schedules defined in YAML, not code
- **Graceful degradation**: All external API calls wrapped in try/except — failures log but don't crash the pipeline
