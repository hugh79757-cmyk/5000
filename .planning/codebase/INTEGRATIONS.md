---
focus: tech
last_mapped: 2026-06-30
version: 1
---

# External Integrations

## API Integrations

### OpenAI GPT (`shared/ai_writer.py`)
- **Purpose**: Content generation for all pipelines
- **Auth**: API key via `OPENAI_API_KEY` env var
- **Config**: `config/models.yaml` — per-pipeline model selection
- **Timeout**: 60s per request
- **Usage**: `generate()` function called from `shared/humanizer.py`, pipeline writers
- **Endpoints**: OpenAI REST API (configurable `base_url` in `models.yaml`)

### Google Blogger v3 (`shared/blogger_publisher.py`)
- **Purpose**: Publish to Blogger.com blogs (e.g., `travel.rotcha.kr`)
- **Auth**: OAuth 2.0 via `client_secret_hugh7973.json` + stored token
- **Scopes**: `https://www.googleapis.com/auth/blogger`
- **Config**: Per-blog `blog_id` mapped to Blogger blog URL

### WordPress XML-RPC (`shared/wordpress_publisher.py`)
- **Purpose**: Publish to WordPress sites
- **Auth**: Username + password via env vars
- **Protocol**: XML-RPC over HTTP
- **Endpoint**: `https://{domain}/xmlrpc.php`

### Telegram Bot (`shared/telegram_notifier.py`)
- **Purpose**: Error alerts, daily reports, publish notifications
- **Auth**: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` env vars
- **Format**: HTML parse mode
- **Used by**: All pipelines, `dispatcher.py`, `scheduler.py`

### Cloudflare R2 (`shared/r2_uploader.py`)
- **Purpose**: Blog image hosting
- **Auth**: S3-compatible credentials (`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`)
- **Endpoint**: `R2_ENDPOINT` env var
- **Buckets**: `hotissue-images` (default), `senior-images` — configured in `BUCKET_PUBLIC_URLS`
- **Library**: `boto3` with S3 API

### IndexNow (`scripts/indexnow.py`, `.github/workflows/indexnow.yml`)
- **Purpose**: Submit new/updated URLs to search engines
- **Auth**: Static key `b8f4e2a1c3d5e6f7a8b9c0d1e2f3a4b5` served at `rotcha.kr/{key}.txt`
- **Engines**: api.indexnow.org, Bing, Yandex
- **Trigger**: GitHub Actions on push to main (after 60s delay)

### Viator Affiliate (`pipelines/etap/pipeline.py`)
- **Purpose**: Product card insertion in English travel posts
- **Auth**: `VIATOR_PID` + `VIATOR_MCID` env vars
- **Data**: Local SQLite `travel-en.db` → `viator_tours` table
- **Method**: SQL query by city → URL parameter injection with affiliate IDs

### Coupang Partners (`shared/coupang_senior.py`, `shared/coupang_car.py`, `shared/coupang_travel.py`)
- **Purpose**: Affiliate product linking for Korean blogs
- **Method**: API calls with Coupang Partner API keys
- **Usage**: Product recommendations within blog posts

## Deployment Pipeline

### Hugo Build → Cloudflare Pages
1. Hugo builds static site with `--gc --minify`
2. Wrangler deploys to Cloudflare Pages: `wrangler pages deploy public --project-name {blog_id}`
3. Worker-only blogs deploy via `wrangler deploy --config wrangler.toml`
4. Deploy lock at `/tmp/wrangler_deploy.lock` serializes concurrent deploys (600s timeout)
5. Post-deploy: GitHub Actions submits IndexNow after 60s

### Cloudflare Workers URL Redirect (`workers/redirect-worker.js`)
- **Purpose**: Legacy URL redirects for `rotcha.kr`
- **Routes**: `rotcha.kr/entry/*`, `rotcha.kr/m/entry/*`, `rotcha.kr/posts/*`
- **Workers KV**: Not used (static redirect rules)
- **Deployment**: `wrangler.toml` in `workers/`

## Cross-Project Integration

### STAP (Stock Auto Publisher) via Subprocess
- **Trigger**: `_run_stap()` in `dispatcher.py:212`
- **Mechanism**: Temp Python file → subprocess with STAP venv
- **Pipelines**: stock, dividend, etf, sector, ipo, finance
- **Timeout**: 600s
- **DB**: `/Users/twinssn/Projects/STAP/data/stap_content.db`

### TAP (Travel Auto Publisher) via Subprocess
- **Trigger**: `_run_pipeline()` pipeline=="tap" in `dispatcher.py:377`
- **Mechanism**: Temp Python file → subprocess with TAP venv
- **Timeout**: 600s
- **Entity linking**: Cross-blog card injection via `tap_entity_manager`

### ETAP (English Travel) File-System Integration
- **Trigger**: Hugo content published to per-blog site paths under `/Users/twinssn/Projects/ETAP/`
- **Mechanism**: Write `content/posts/{slug}/index.md` → Hugo build → Cloudflare Pages deploy
- **Blogs**: 30+ English travel blogs

## Monitoring & Alerting

- **Telegram alerts**: Pipeline failures, deploy errors, disk space warnings
- **Daily report**: `shared/daily_report.py` queries all DBs for publish count
- **Scheduler health**: `scheduler.py` checks: package imports, network, boto3 deep health, boto3 R2 connectivity
- **Lock files**: `/tmp/*.lock` for deploy serialization; `data/.lock_{blog_id}` for pipeline serialization
