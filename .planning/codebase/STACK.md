---
focus: tech
last_mapped: 2026-06-30
version: 1
---

# Technology Stack

## Languages & Runtimes

| Layer | Technology | Version | Location |
|-------|-----------|---------|----------|
| Application | Python | 3.14 | `shared/`, `pipelines/`, `dispatcher.py`, `scheduler.py` |
| Static Site | Hugo (extended) | ~0.122+ | `/opt/homebrew/bin/hugo` |
| Frontend | HTML/CSS/JS | — | `layouts/`, `assets/css/` |
| Cloudflare Workers | JavaScript (Service Worker) | ES2020 | `workers/redirect-worker.js` |
| Cloudflare Pages Functions | JavaScript | ES2020 | `functions/_middleware.js` |
| Build tooling | Node.js + PostCSS | ^8.4.35 | `package.json`, `postcss.config.js` |

## Core Frameworks & Libraries

### Python Dependencies (`requirements.txt`)
- **`openai>=1.30.0`** — GPT model API for content generation (`shared/ai_writer.py`)
- **`google-api-python-client>=2.130.0`** — Google Blogger API v3 (`shared/blogger_publisher.py`)
- **`google-auth-oauthlib>=1.2.0`** — Blogger OAuth flow
- **`httpx>=0.27.0`** — HTTP client for API calls
- **`pyyaml>=6.0.1`** — YAML config parsing
- **`markdownify>=0.13.1`** — HTML→Markdown conversion
- **`markdown>=3.6`** — Markdown→HTML conversion
- **`apscheduler>=3.10.4`** — Advanced scheduling (available but `schedule` is used in prod)
- **`schedule>=1.2.0`** — Simple cron-like scheduler (`scheduler.py`)
- **`python-dotenv>=1.0.1`** — Environment variable loading
- **`python-frontmatter>=1.1.0`** — YAML frontmatter parsing
- **`requests>=2.32.0`** — HTTP requests (legacy, superseded by httpx in newer code)
- **`Pillow`** — Image processing (`shared/image_handler.py`)
- **`boto3`** — AWS SDK v3 / Cloudflare R2 S3-compatible API (`shared/r2_uploader.py`)

### Node.js Dev Dependencies (`package.json`)
- **`postcss@^8.4.35`** + **`postcss-cli@^11.0.0`** — CSS post-processing
- **`@fullhuman/postcss-purgecss@^6.0.0`** — CSS size optimization
- **`autoprefixer@^10.4.17`** — CSS vendor prefixing

### Hugo Theme
- **PaperMod** — Hugo theme for `rotcha.kr` (`hugo.toml:5`)

## Infrastructure & Hosting

| Component | Provider | Purpose |
|-----------|----------|---------|
| Static sites | Cloudflare Pages | 30+ Hugo blog deployments |
| Workers | Cloudflare Workers | URL redirects (`rotcha.kr/entry/*` → new paths) |
| Object storage | Cloudflare R2 (S3-compatible) | Blog images (`shared/r2_uploader.py`) |
| Domain | Cloudflare DNS | `rotcha.kr` + subdomains |
| CI/CD | GitHub Actions | IndexNow submission on push (`indexnow.yml`) |
| Scheduler | macOS `launchd` | Local `scheduler.py` process |

## Databases

All SQLite — one DB per pipeline/domain:

| Database | Location | Purpose |
|----------|----------|---------|
| `content.db` | `data/content.db` | Central publish ledger, articles |
| `car.db` | `data/car.db` | Automotive pipeline content |
| `gap.db` | `data/gap.db` | General content pipeline |
| `rap.db` | `data/rap.db` | Real estate pipeline |
| `senior.db` | `data/senior.db` | Senior/welfare pipeline |
| `stock.db` | `data/stock.db` | Stock/finance pipeline |
| `travel-en.db` | `data/travel-en.db` | English travel content (Viator, etc.) |
| `curation.db` | `data/curation.db` | Curation pipeline |
| `course.db` | `data/course.db` | Course/education content |
| `festival.db` | `data/festival.db` | Festival content |
| `analytics.db` | `data/analytics.db` | Analytics data |
| `scanner.db` | `data/scanner.db` | Quality scanner data |
| `stap_content.db` | `data/stap_content.db` | STAP (stock) content |
| `indexnow.db` | `data/indexnow.db` | IndexNow submission tracking |

## External APIs

| API | Package/Protocol | Purpose |
|-----|-----------------|---------|
| **OpenAI GPT** | `openai` (REST) | Content generation (`shared/ai_writer.py`) |
| **Google Blogger** | `google-api-python-client` (REST v3) | Blogger.com publishing (`shared/blogger_publisher.py`) |
| **WordPress XML-RPC** | `requests` (XML-RPC) | WordPress publishing (`shared/wordpress_publisher.py`) |
| **Telegram Bot** | `requests` (REST) | Notifications & error alerts (`shared/telegram_notifier.py`) |
| **Cloudflare R2** | `boto3` (S3-compatible) | Image upload/hosting (`shared/r2_uploader.py`) |
| **IndexNow** | `requests` (REST) | Search engine index notification (`scripts/indexnow.py`) |
| **Viator Affiliate** | SQLite + URL param injection | Travel product affiliate links (`pipelines/etap/pipeline.py`) |
| **Coupang Partners** | REST (via API) | Affiliate product data (`shared/coupang_senior.py`, etc.) |

## Configuration System

Config files in `config/` — all YAML:

| File | Purpose |
|------|---------|
| `blogs.yaml` | Master schedule + deploy config |
| `blogs.d/*.yaml` | Individual blog definitions (id, pipeline, schedule, platform) |
| `prompts.yaml` | AI writing prompts & SEO rules (1117 lines) |
| `prompts/` | Per-topic prompt files |
| `models.yaml` | LLM provider models (OpenAI, etc.) |
| `api_keys.yaml` | API secrets (gitignored) |

## External Project Dependencies

The system orchestrates content generation across multiple sibling projects:

| Project | Path | Integration |
|---------|------|-------------|
| **STAP** (Stock Auto Publisher) | `/Users/twinssn/Projects/STAP` | Subprocess isolation (`_run_stap()`) |
| **TAP** (Travel Auto Publisher) | `/Users/twinssn/Projects/TAP` | Subprocess + entity linking |
| **ETAP** (English Travel Auto Publisher) | `/Users/twinssn/Projects/ETAP` | Hugo site path for 30+ blogs |
| **LAP** | `/Users/twinssn/Projects/LAP` | Publish log reference |
| **CUAP** | `/Users/twinssn/Projects/CUAP` | Related Hugo projects |
