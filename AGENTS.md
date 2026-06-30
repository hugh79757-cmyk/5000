<!-- GSD:project-start source:PROJECT.md -->
## Project

**5000**

An automated content generation and publishing platform that uses OpenAI GPT to create articles for 50+ Korean and English blogs, publishes them to Cloudflare Pages (Hugo static sites) and legacy Blogger/WordPress blogs, then notifies search engines via IndexNow.

**Core Value:** Pipelines run reliably with clear errors when they don't — no silent failures, no manual firefighting.

### Constraints

- **Tech stack**: Python 3.14, Hugo, Cloudflare Pages/Workers/R2, SQLite — must keep these
- **Deployment**: macOS host with `launchd`; Cloudflare Pages for hosting
- **Pipelines must keep running**: Refactoring cannot block daily content publication
- **Single developer**: Changes must be incremental, not all-or-nothing
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

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
| File | Purpose |
|------|---------|
| `blogs.yaml` | Master schedule + deploy config |
| `blogs.d/*.yaml` | Individual blog definitions (id, pipeline, schedule, platform) |
| `prompts.yaml` | AI writing prompts & SEO rules (1117 lines) |
| `prompts/` | Per-topic prompt files |
| `models.yaml` | LLM provider models (OpenAI, etc.) |
| `api_keys.yaml` | API secrets (gitignored) |
## External Project Dependencies
| Project | Path | Integration |
|---------|------|-------------|
| **STAP** (Stock Auto Publisher) | `/Users/twinssn/Projects/STAP` | Subprocess isolation (`_run_stap()`) |
| **TAP** (Travel Auto Publisher) | `/Users/twinssn/Projects/TAP` | Subprocess + entity linking |
| **ETAP** (English Travel Auto Publisher) | `/Users/twinssn/Projects/ETAP` | Hugo site path for 30+ blogs |
| **LAP** | `/Users/twinssn/Projects/LAP` | Publish log reference |
| **CUAP** | `/Users/twinssn/Projects/CUAP` | Related Hugo projects |
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Python Style
- **snake_case** for all functions, variables, file names
- **PascalCase** for classes (rarely used — most code is module-level functions)
- **UPPER_CASE** for constants, env var names
- **Type hints**: Partial adoption — some files use `typing` annotations, many don't
- **Docstrings**: Some modules have module-level docstrings (`"""..."""`), inline comments are sparse
- **Line length**: Not enforced — varies widely (some lines exceed 120 chars in `dispatcher.py`)
- **F-strings**: Preferred over `%` formatting or `.format()`
- **Imports**: Standard library → third-party → local, separated by blank lines
## Code Organization
### Module Pattern
### Pipeline Pattern
### Error Handling
- **try/except** everywhere — external calls always wrapped
- **Graceful degradation**: On failure, log error + continue; never crash the pipeline
- **`_tg_error()`**: Critical failures sent to Telegram
- **`logger.error/fatal`**: Pipeline errors logged at module level
- **`sys.exit(1)`**: Only on catastrophic startup failures (import checks)
### Configuration Loading
## Naming Conventions
- **Blog IDs**: `{category}-hugo` for Hugo sites, `{category}-blogger` for Blogger
- **Pipeline names**: Short acronyms (`etap`, `gap`, `rap`, `car`)
- **Config keys**: `snake_case` in YAML (`daily_quota`, `site_path`)
- **SQLite DB files**: `{pipeline}.db` (e.g., `car.db`, `rap.db`)
- **Lock files**: `data/.lock_{blog_id}` for pipeline concurrency
- **Private functions**: `_leading_underscore` for module-internal functions
## Configuration Conventions
### `blogs.d/*.yaml` Blog Definition
- id: rap-hugo
### `prompts.yaml` Structure
## Conditional Import Pattern
## Deployment Pattern
## Version Control
- **Branch**: `main` — single branch development
- **Commit style**: Concise, no conventional commits format observed
- **`.gitignore`**: Aggressive — `.bak*`, `.venv/`, `__pycache__/`, `.env`, `api_keys.yaml`, `.db` files
- **Themes**: `themes/` is gitignored (git submodule or manual install)
- **Resources**: `resources/` is gitignored (Hugo cache)
## Shell/PATH Dependencies
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```
```
## Pipeline Architecture
```
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
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
