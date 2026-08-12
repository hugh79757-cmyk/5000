<!-- GSD:project-start source:PROJECT.md -->

## Karpathy Guidelines (LLM 코딩 습관 개선)



## Project

**5000** — 중앙 컨트롤 파이프라인

50+ Korean/English 블로그를 자동 생성·발행하는 콘텐츠 자동화 플랫폼. OpenAI GPT로 글을 생성하고, Cloudflare Pages (Hugo 정적 사이트)와 Blogger/WordPress로 발행한 뒤 IndexNow로 검색 엔진에 알림.

**Core Value:** 파이프라인은 실패 시 명확한 에러를 내야 함 — 조용한 실패 없음, 수동 해결 없음.

### 브랜치 구조 (5000 중앙 통제)

5000은 중앙 컨트롤 파이프라인으로, 아래 브랜치들을 관리:

| 브랜치      | 전체명                        | 역할                 |
| -------- | -------------------------- | ------------------ |
| **CAP**  | Content Auto Publisher     | 일반 콘텐츠 자동 발행       |
| **TAP**  | Travel Auto Publisher      | 여행 콘텐츠 자동 발행 (한국어) |
| **STAP** | Stock Auto Publisher       | 주식/금융 콘텐츠 자동 발행    |
| **CUAP** | Curation Auto Publisher    | 상품 큐레이션 콘텐츠 자동 발행  |
| **SEAP** | Senior Auto Publisher      | 시니어/복지 콘텐츠 자동 발행   |
| **RAP**  | Real Estate Auto Publisher | 부동산 콘텐츠 자동 발행      |

**모든 블로그는 5000에 포함됨.** 외부 프로젝트(TAP, STAP 등)는 5000의 서브프로세스로 격리 실행.

### Constraints

- **Tech stack**: Python 3.14, Hugo, Cloudflare Pages/Workers/R2, SQLite — must keep these

- **Deployment**: macOS host with `launchd`; Cloudflare Pages for hosting

- **Pipelines must keep running**: Refactoring cannot block daily content publication

- **Single developer**: Changes must be incremental, not all-or-nothing
  
  <!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages & Runtimes

| Layer                      | Technology                  | Version | Location                                                 |
| -------------------------- | --------------------------- | ------- | -------------------------------------------------------- |
| Application                | Python                      | 3.14    | `shared/`, `pipelines/`, `dispatcher.py`, `scheduler.py` |
| Static Site                | Hugo (extended)             | ~0.122+ | `/opt/homebrew/bin/hugo`                                 |
| Frontend                   | HTML/CSS/JS                 | —       | `layouts/`, `assets/css/`                                |
| Cloudflare Workers         | JavaScript (Service Worker) | ES2020  | `workers/redirect-worker.js`                             |
| Cloudflare Pages Functions | JavaScript                  | ES2020  | `functions/_middleware.js`                               |
| Build tooling              | Node.js + PostCSS           | ^8.4.35 | `package.json`, `postcss.config.js`                      |

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
  
  | Component      | Provider                      | Purpose                                         |
  | -------------- | ----------------------------- | ----------------------------------------------- |
  | Static sites   | Cloudflare Pages              | 30+ Hugo blog deployments                       |
  | Workers        | Cloudflare Workers            | URL redirects (`rotcha.kr/entry/*` → new paths) |
  | Object storage | Cloudflare R2 (S3-compatible) | Blog images (`shared/r2_uploader.py`)           |
  | Domain         | Cloudflare DNS                | `rotcha.kr` + subdomains                        |
  | CI/CD          | GitHub Actions                | IndexNow submission on push (`indexnow.yml`)    |
  | Scheduler      | macOS `launchd`               | Local `scheduler.py` process                    |
  
  ## Databases
  
  | Database          | Location               | Purpose                               |
  | ----------------- | ---------------------- | ------------------------------------- |
  | `content.db`      | `data/content.db`      | Central publish ledger, articles      |
  | `car.db`          | `data/car.db`          | Automotive pipeline content           |
  | `gap.db`          | `data/gap.db`          | General content pipeline              |
  | `rap.db`          | `data/rap.db`          | Real estate pipeline                  |
  | `senior.db`       | `data/senior.db`       | Senior/welfare pipeline               |
  | `stock.db`        | `data/stock.db`        | Stock/finance pipeline                |
  | `travel-en.db`    | `data/travel-en.db`    | English travel content (Viator, etc.) |
  | `curation.db`     | `data/curation.db`     | Curation pipeline                     |
  | `course.db`       | `data/course.db`       | Course/education content              |
  | `festival.db`     | `data/festival.db`     | Festival content                      |
  | `analytics.db`    | `data/analytics.db`    | Analytics data                        |
  | `scanner.db`      | `data/scanner.db`      | Quality scanner data                  |
  | `stap_content.db` | `data/stap_content.db` | STAP (stock) content                  |
  | `indexnow.db`     | `data/indexnow.db`     | IndexNow submission tracking          |
  
  ## External APIs
  
  | API                   | Package/Protocol                     | Purpose                                                       |
  | --------------------- | ------------------------------------ | ------------------------------------------------------------- |
  | **OpenAI GPT**        | `openai` (REST)                      | Content generation (`shared/ai_writer.py`)                    |
  | **Google Blogger**    | `google-api-python-client` (REST v3) | Blogger.com publishing (`shared/blogger_publisher.py`)        |
  | **WordPress XML-RPC** | `requests` (XML-RPC)                 | WordPress publishing (`shared/wordpress_publisher.py`)        |
  | **Telegram Bot**      | `requests` (REST)                    | Notifications & error alerts (`shared/telegram_notifier.py`)  |
  | **Cloudflare R2**     | `boto3` (S3-compatible)              | Image upload/hosting (`shared/r2_uploader.py`)                |
  | **IndexNow**          | `requests` (REST)                    | Search engine index notification (`scripts/indexnow.py`)      |
  | **Viator Affiliate**  | SQLite + URL param injection         | Travel product affiliate links (`pipelines/etap/pipeline.py`) |
  | **Coupang Partners**  | REST (via API)                       | Affiliate product data (`shared/coupang_senior.py`, etc.)     |
  
  ### LLM Fallback Chain (글쓰기 모델 폴백)
  
  `shared/ai_writer.py` → `config/models.yaml`의 `tier_order`를 따라 16개 무료 모델을 순차 시도하고, 전부 실패 시에만 유료 DeepSeek V4 Flash를 호출.
  
  | 순서 | 모델 | 프로바이더 | 비고 |
  |------|------|-----------|------|
  | 1-4 | Gemini 3.1/3.5 flash-lite, 2.5/3.5 flash | Google | 무료 |
  | 5-8 | Llama 3.3 70B, Qwen3.6 27B, GPT-OSS 120B/20B | Groq | 무료, Qwen은 thinking OFF |
  | 9-10 | Gemma 4 31B, GLM 4.7 | Cerebras | 무료, GLM은 thinking OFF |
  | 11 | DeepSeek V4 Flash Free | OpenCode Zen | 무료 |
  | 12-13 | Nemotron 3 Ultra 550B, Step 3.7 Flash | NVIDIA NIM | 무료, Step은 thinking OFF |
  | 14-15 | MiMo V2.5 Free, Big Pickle | OpenCode Zen | 무료 |
  | 16 | GLM 4.5 Flash | Zhipu AI | 무료 |
  | **17** | **DeepSeek V4 Flash** | **DeepSeek** | **★ 유료 — 최후 수단** |
  
  상세: `LLM_FALLBACK_CHAIN.md`
  
  ## Configuration System
  
  | File             | Purpose                                                        |
  | ---------------- | -------------------------------------------------------------- |
  | `blogs.yaml`     | Master schedule + deploy config                                |
  | `blogs.d/*.yaml` | Individual blog definitions (id, pipeline, schedule, platform) |
  | `prompts.yaml`   | AI writing prompts & SEO rules (1117 lines)                    |
  | `prompts/`       | Per-topic prompt files                                         |
  | `models.yaml`    | LLM provider models (OpenAI, etc.)                             |
  | `api_keys.yaml`  | API secrets (gitignored)                                       |
  
  ## External Project Dependencies
  
  | Project                                  | Path                           | Integration                          |
  | ---------------------------------------- | ------------------------------ | ------------------------------------ |
  | **STAP** (Stock Auto Publisher)          | `/Users/twinssn/Projects/STAP` | Subprocess isolation (`_run_stap()`) |
  | **TAP** (Travel Auto Publisher)          | `/Users/twinssn/Projects/TAP`  | Subprocess + entity linking          |
  | **ETAP** (English Travel Auto Publisher) | `/Users/twinssn/Projects/ETAP` | Hugo site path for 30+ blogs         |
  | **LAP**                                  | `/Users/twinssn/Projects/LAP`  | Publish log reference                |
  | **CUAP**                                 | `/Users/twinssn/Projects/CUAP` | Related Hugo projects                |
  
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

| Pipeline             | Directory             | Blogs | Output Platform         | Content Type          |
| -------------------- | --------------------- | ----- | ----------------------- | --------------------- |
| **etap**             | `pipelines/etap/`     | 30+   | Cloudflare Pages + Hugo | English travel guides |
| **car**              | `pipelines/car/`      | 8     | Cloudflare Pages + Hugo | Korean automotive     |
| **senior**           | `pipelines/senior/`   | ~5    | Cloudflare Pages + Hugo | Senior welfare        |
| **gap**              | `pipelines/gap/`      | ~3    | Cloudflare Pages + Hugo | General content       |
| **rap**              | `pipelines/rap/`      | ~3    | Cloudflare Pages + Hugo | Real estate           |
| **stock** (via STAP) | external              | 6     | Cloudflare Pages + Hugo | Stock/finance         |
| **travel**           | `pipelines/travel/`   | ~5    | Cloudflare Pages + Hugo | Korean travel         |
| **tap** (via TAP)    | external              | 1     | Blogger.com             | Korean travel         |
| **curation**         | `pipelines/curation/` | ~3    | Cloudflare Pages + Hugo | Curated content       |

### 5000 브랜치 관리 구조

| 브랜치      | 프로젝트 경로                        | 파이프라인 유형                     | 블로그 수 |
| -------- | ------------------------------ | ---------------------------- | ----- |
| **CAP**  | 5000 내부                        | curation, gap, car, senior 등 | 20+   |
| **TAP**  | `/Users/twinssn/Projects/TAP`  | travel                       | 5+    |
| **STAP** | `/Users/twinssn/Projects/STAP` | stock                        | 6     |
| **CUAP** | `/Users/twinssn/Projects/CUAP` | curation (상품 큐레이션)           | 10    |
| **SEAP** | 5000 내부                        | senior                       | ~5    |
| **RAP**  | 5000 내부                        | rap (부동산)                    | ~3    |

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
  
  | Entry Point                  | Purpose                                        | Invocation              |
  | ---------------------------- | ---------------------------------------------- | ----------------------- |
  | `dispatcher.py`              | Main router — `python dispatcher.py {blog_id}` | Scheduler / manual      |
  | `scheduler.py`               | Continuous scheduler loop                      | `launchd` / manual      |
  | `scripts/indexnow.py`        | IndexNow URL submission                        | CLI / GitHub Actions    |
  | `workers/redirect-worker.js` | URL redirects                                  | Cloudflare Workers HTTP |
  | `functions/_middleware.js`   | Pages middleware                               | Cloudflare Pages HTTP   |
  
  ## Key Design Decisions

- **중앙 컨트롤**: 5000이 모든 파이프라인(brand)을 통합 관리

- **SQLite per pipeline**: No central DB system — each pipeline owns its data

- **Subprocess isolation**: STAP/TAP run as isolated subprocesses with dedicated venvs

- **Layered config**: `blogs.yaml` + `blogs.d/*.yaml` merged at runtime

- **File-system deploys**: Hugo sites are written to `content/posts/{slug}/index.md` then built

- **Deploy serialization**: `flock()` lock at `/tmp/wrangler_deploy.lock` prevents concurrent wrangler deploys

- **YAML-driven scheduling**: Blog schedules defined in YAML, not code

- **Graceful degradation**: All external API calls wrapped in try/except — failures log but don't crash the pipeline
  
  <!-- GSD:architecture-end -->

<!-- GSD:incidents-start -->

## Recent Incident Analysis (2026-07-11)

### travel2-hugo — `no_result` (10회 연속 실패)

- **원인**: `_travel_sigungu_recently_published()` 가드가 14일 내 23개 시군구를 차단
- **근본 원인**: heritage 유효 데이터 901건 → 16개 도(道)에 분산, 시군구 수 제한
- **메커니즘**: `pipelines/travel/pipeline.py:99` — `_travel_sigungu_recently_published()`가 14일 룩백으로 동일 시군구 중복 차단
- **실행 경로**: `dispatcher.py` → `_resolve_pipeline("travel")` → `pipelines.travel.pipeline.run()` → `_run_single()` → `_fetch_for_blog()` → `fetch_heritage()` → 시군구 중복 가드 → `None` 반환 → dispatcher가 `{"success": false, "reason": "no_result"}` 출력
- **데이터 흐름**: heritage_list.json (5310건) → 품질 필터 (901건) → 중복 제외 (613건) → 랜덤 지역 선택 → 시군구 가드에서 차단
- **일부 성공**: 16:04 성공 (거창군), 20:04 실패 — 랜덤 지역 운에 의존
- **핵심 데이터**: `pipelines/travel/fetcher.py:998` — `fetch_heritage()`가 `/Users/twinssn/Projects/heritage/scripts/data/heritage_list.json` 사용
- **해결 방향**: 시군구 룩백 기간 단축(14→7일), 또는 heritage 가드 로직 완화 필요

### sector-hugo — `no_content` (23회 연속 실패)

- **원인**: `pipelines.sector.pipeline.run()` → `_try_generate()` → 모든 토픽 시도 후 article 생성 실패
- **근본 원인**: `get_unused_data()`는 sector=80건, index=50건, krx=0건 반환하지만, GPT 생성 자체가 실패하거나 제목 중복/업종 중복 가드에 차단
- **메커니즘**: `pipelines/sector/pipeline.py:187` — `article`이 None이거나 title/body_md 없으면 `{"success": False, "reason": "no_content"}` 반환
- **데이터 흐름**: `pipelines/data_collector.py` → `get_unused_data()` → sector/index/krx 테이블 → `generate_sector_article()` → 제목 중복 체크 → 업종 중복 체크 → 성공 시에만 발행
- **일부 성공**: 10:28 성공 (은행업종), 나머지 실패 — 토픽 순환 + 중복 가드가 빡빡함
- **해결 방향**: 토픽 순환 로직 개선, collect_all() 호출 빈도 증가, 중복 가드 완화 필요

### appliance-hugo — `similar_title` (듀스핀 키워드)

- **원인**: `title_similar_exists()`가 유사 제목 감지 → 발행 차단
- **메커니즘**: `shared/content_store.py` — SequenceMatcher 80% 유사도 임계값
- **상태**: 특정 키워드(듀스핀)의 제목 패턴이 반복되어 중복 감지
- **해결 방향**: 키워드별 제목 변형 다양화, 유사도 임계값 조정 검토

### laptop-hugo — 이미지 URL 길이 초과 (해결 완료)

- **원인**: Coupang 이미지 URL이 255자 macOS 파일명 제한 초과 → Hugo 빌드 실패
- **해결**: `shared/publishers/hugo_writer.py` — `sanitize_featureimage_url()` max_len 500→200으로 축소 + IMAGE-GUARD 추가
- **검증**: laptop-hugo 발행 성공 확인

### CUAP 전체 블로그 — lead 단락 과도한 크기 (해결 완료)

- **원인**: Blowfish 테마 기본 `.lead { font-size: 1.5rem }` → 본문 첫 문단 과대
- **해결**: 10개 CUAP 블로그 `custom.css`에 `.lead { font-size: 1rem; }` 추가
- **검증**: CSS 번들에 `.lead{font-size:1rem}` 포함 확인, 전체 배포 성공

### kuta-hugo — `broken_featureimage` (썸네일 깨짐)

- **원인**: `featureimage`가 `img-kuta.informationhot.kr/images/kuta/{slug}/thumbnail.webp`로 설정 — 이 도메인은 WordPress XML-RPC 전용이라 `/images/` 경로 서빙 불가
- **근본 원인**: 포스트가 5000 pipeline 외부 경로로 발행되어 `batch_thumbnails.py`가 실행되지 않음 → R2에 썸네일 없음
- **메커니즘**: Hugo frontmatter `featureimage`가 존재하지 않는 URL을 가리킴 → 브라우저 404
- **실행 경로**: `scripts/batch_thumbnails.py` → `shared/thumbnail_generator/generator.py` → `shared/r2_uploader.py` → `shared/publishers/hugo_writer.py` (frontmatter update)
- **데이터 흐름**: 포스트 slug → batch_thumbnails.py → generator.py (썸네일 생성) → r2_uploader.py (R2 업로드) → hugo_writer.py (featureimage 업데이트)
- **해결**: `batch_thumbnails.py --slug "20260617-212002-부산-동래구-카페-추천-핫플레이스-5곳"` 실행 → 썸네일 생성 + R2 업로드 + frontmatter 수정
- **검증**: R2 URL HTTP 200 확인 (`pub-2f5c7af1c303419a933069212bc25874.r2.dev/thumbnails/kuta/{slug}.webp` → 200)
- **부수적 발견**: blogsmith auto-publisher(`md-editor-nicegui/core/publish/`)는 발행 시 `make_thumb()` → `thumbnail_gen.py`(gradient overlay)로 썸네일 자동 생성 + R2 업로드 함. 5000 pipeline 발행 글만 `batch_thumbnails.py` 수동 실행 필요.

## Pipeline Error Pattern Reference

| 에러 유형                 | 파이프라인             | 원인 패턴                                          | 해결 방향                  |
| --------------------- | ----------------- | ---------------------------------------------- | ---------------------- |
| `no_result`           | travel            | 데이터 수집 성공 → 가드 차단 → None 반환                    | 가드 기간/임계값 조정           |
| `no_content`          | sector/stock      | 토픽 순환 소진 + 중복 가드 → article 생성 실패               | 토픽 다양화, 데이터 수집 빈도      |
| `similar_title`       | curation          | 제목 패턴 반복 → 유사도 80% 초과                          | 키워드별 제목 변형             |
| `broken_featureimage` | kuta-hugo (외부 발행) | featureimage가 WordPress 도메인 경로로 설정, R2에 썸네일 없음 | batch_thumbnails.py 실행 |
| `deploy_error`        | all Hugo          | 이미지 URL 길이 초과, Hugo 빌드 실패                      | URL sanitize, 파일명 제한   |
| `Hugo build failed`   | travel-hugo       | 콘텐츠 문제 → Hugo 빌드 에러                            | 로그 확인, 배포 로직 분리 필요     |

## Key File Reference for Debugging

| 파일                                                 | 용도                                                                    |
| -------------------------------------------------- | --------------------------------------------------------------------- |
| `dispatcher.py`                                    | 메인 라우터 — 파이프라인별 분기, no_result/no_content 분류                           |
| `scripts/batch_thumbnails.py`                      | Hugo 포스트 썸네일 일괄 생성 + R2 업로드                                           |
| `shared/thumbnail_generator/generator.py`          | 썸네일 이미지 생성 로직                                                         |
| `shared/publishers/hugo_writer.py`                 | Hugo 콘텐츠 정리 — H2 가드, IMAGE-GUARD, URL sanitize, featureimage 업데이트     |
| `shared/content_store.py`                          | 콘텐츠 저장 — title_similar_exists(), is_place_used()                      |
| `shared/publishers/deploy.py`                      | Hugo 빌드 + wrangler 배포                                                 |
| `shared/r2_uploader.py`                            | Cloudflare R2 S3 호환 업로드                                               |
| `config/blogs.d/tap.yaml`                          | TAP 블로그 설정 — schedule, pipeline, fetch_sources                        |
| `config/blogs.d/stap.yaml`                         | STAP 블로그 설정                                                           |
| `data/stap_content.db`                             | STAP 콘텐츠 DB — articles 테이블 (sector-hugo 329건 발행)                      |
| `md-editor-nicegui/core/publish/auto_scheduler.py` | blogsmith auto-publisher (30분마다 blogsmith output → Hugo/WordPress 발행) |
| `md-editor-nicegui/core/publish/thumbnail_gen.py`  | auto-publisher용 gradient 썸네일 생성기                                      |
| `md-editor-nicegui/core/publish/hugo.py`           | auto-publisher Hugo 발행 + R2 업로드 + wrangler deploy                     |

## Cloudflare Wrangler Auth Profile (2026-07-14)

> **문제**: OpenCode/Codex agent가 `CLOUDFLARE_API_TOKEN` 환경변수를 설정 → wrangler auth profile(OAuth)보다 **env var가 우선 적용**되어 잘못된 계정으로 배포 실패

### 근본 원인

wrangler 4.x는 인증 우선순위가 다음과 같음:

1. `CLOUDFLARE_API_TOKEN` 환경변수 (최우선)
2. OAuth auth profile (fallback)

Agent 세션에서 `CLOUDFLARE_API_TOKEN`이 설정되면 wrangler가 profile을 무시하고 env var를 사용. token이 다른 계정이거나 권한 부족 시 `Authentication error code: 10000` 발생.

### 적용된 수정

| 파일                                                 | 수정 내용                                                             |
| -------------------------------------------------- | ----------------------------------------------------------------- |
| `dispatcher.py:_build_and_deploy_central()`        | wrangler 호출 시 `CLOUDFLARE_API_TOKEN` env var 제거 (`deploy_env` 빌드) |
| `shared/publishers/deploy.py:_deploy_site_inner()` | `_wrangler_env`에서 `CLOUDFLARE_API_TOKEN` pop + `_cf_token` 로직 제거  |

### Profile 바인딩 현황

| Profile        | 계정                  | Bound Directories                                  |
| -------------- | ------------------- | -------------------------------------------------- |
| `hugh79757`    | hugh79757@gmail.com | `aikorea24`, `5000`, `cuap`, `ETAP`, `TAP`, `STAP` |
| `farmsolution` | farmsolution 계정     | `farmsolution`                                     |
| `yuiying167`   | -                   | `bazi-spattra`                                     |

### 중요 규칙

1. **절대 `CLOUDFLARE_API_TOKEN`를 wrangler subprocess에 전달하지 말 것** — profile이 무시됨

2. 신규 프로젝트 경로 추가 시 `wrangler auth activate hugh79757 <path>`로 바인딩 추가

3. profile 관리 시 `env -u CLOUDFLARE_API_TOKEN wrangler auth ...` 사용 (agent 세션에서)

4. 상세: `aikorea24 AGENTS.md` Section "Cloudflare Auth Profile", `aikorea24 .planning/triage/20260714--wrangler-auth-profile-setup.md`

5. **`~/.env.common` 로드 시 `CLOUDFLARE_API_TOKEN` 반드시 제외** — `export $(grep -v '^#' ~/.env.common | grep -v 'CLOUDFLARE_API_TOKEN' | xargs)` 사용
   
   <!-- GSD:incidents-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.

<!-- GSD:skills-end -->

<!-- GSD:deployment-start -->

## Deployment Rules

### 배포 방식 (중요)

**절대 git push로 배포하지 말 것.** Cloudflare Pages의 git 연동 자동 빌드는 **월 500회 제한**이 있으며, git push할 때마다 1회씩 소진된다. 커밋/푸시는 단순한 형상 관리 용도로만 사용하고, 실제 배포는 반드시 wrangler 직접 업로드로 수행한다.

### 배포는 반드시 dispatcher.py 사용

**절대 수동으로 `wrangler pages deploy`나 `wrangler deploy`를 직접 실행하지 말 것.** `dispatcher.py`가 Worker/Pages 구분, `CLOUDFLARE_API_TOKEN` 제거, Hugo 빌드, 직렬화 락을 전부 처리한다.

```bash
# 단일 블로그 배포 (글 생성 + 발행 + 배포)
python3 /Users/twinssn/Projects/5000/dispatcher.py {blog_id}
```

> ⚠️ dispatcher.py는 **글 생성 → 발행 → 배포**를 전부 수행한다. 배포만 필요한 경우가 아니라면 항상 dispatcher.py 사용.

### 배포만 필요한 경우 — deploy.py

이미 발행된 글의 최신 코드 변경사항만 배포하려면 `shared/publishers/deploy.py`의 `deploy_site()`를 사용한다. 단, 아래 순서를 반드시 따라야 한다:

```bash
# 1. OAuth profile 토큰 추출 (필수)
export CLOUDFLARE_API_TOKEN=$(env -u CLOUDFLARE_API_TOKEN wrangler auth token 2>/dev/null | tail -1)

# 2. Hugo 빌드
hugo --gc --minify --source /path/to/site

# 3. 배포
python3 -c "
import sys; sys.path.insert(0, '/Users/twinssn/Projects/5000')
from shared.publishers.deploy import deploy_site
deploy_site('/path/to/site', '{blog_id}')
"
```

> ⚠️ `wrangler auth token`으로 토큰을 추출하지 않으면 Workers 블로그(WORKERS_BLOGS 6개) 배포 시 인증 오류가 발생한다.

### dispatcher.py가 처리하는 작업

1. **blog_id에 따라 Workers/Pages 자동 선택**
   - WORKERS_BLOGS (6개: health, pet, kitchen, beauty, camping, baby) → `wrangler deploy --config wrangler.toml`
   - 그 외 모든 Pages 블로그 → `wrangler pages deploy public --project-name={blog_id}`
2. **`CLOUDFLARE_API_TOKEN` env var 제거** — wrangler auth profile(OAuth) 우선 적용
3. **Hugo 빌드** — `hugo --gc --minify` 실행
4. **직렬화 락** — `/tmp/wrangler_deploy.lock`으로 중복 배포 방지
5. **배포 실패 시 로그 기록** — 자동 재시도 로직 없음, 실패 원인은 로그 확인

### CLOUDFLARE_API_TOKEN 환경변수 문제

**문제점:** OpenCode/Codex agent가 `CLOUDFLARE_API_TOKEN` 환경변수를 설정한다. 이 token이 wrangler auth profile(OAuth)보다 **우선 적용**되어 잘못된 계정으로 배포하거나 권한 오류가 발생한다.

**해결:** 사용자 `.zshrc`에 `wrangler()` shell 함수가 정의되어 있어, 터미널에서 `wrangler` 실행 시 자동으로 `CLOUDFLARE_API_TOKEN`을 제거하고 OAuth profile을 사용한다. agent 환경에서는 이 함수를 사용할 수 없으므로 `dispatcher.py`를 통해 배포해야 한다 (`dispatcher.py`가 내부에서 token을 제거함).

**Wrangler Workers 배포 인증:** Wrangler 4.x는 `wrangler deploy`(Worker)를 non-interactive 환경에서 실행하려면 반드시 `CLOUDFLARE_API_TOKEN`이 필요하다. OAuth profile로는 부족하다. Pages(`wrangler pages deploy`)는 OAuth profile로 가능하다.

**토큰 갱신 명령어:**

```bash
# OAuth profile 재인증 (브라우저 열림)
env -u CLOUDFLARE_API_TOKEN wrangler auth create hugh79757

# OAuth profile의 토큰을 CLOUDFLARE_API_TOKEN으로 추출
export CLOUDFLARE_API_TOKEN=$(env -u CLOUDFLARE_API_TOKEN wrangler auth token 2>/dev/null | tail -1)
```

### 중요 규칙

1. **절대 수동 wrangler 명령어 금지** — Worker/Pages 구분이 꼬이고 env var 충돌 발생
2. **`--commit-dirty=true` 사용 금지** — git commit 생성 → Cloudflare Pages 자동 빌드 트리거로 배포 횟수 이중 소진
3. git push 후 Cloudflare Pages 대시보드에 **Skipped** 표시는 정상 (git 기반 빌드 비활성화)
4. `CLOUDFLARE_API_TOKEN`이 설정되어 있으면 wrangler auth profile이 무시됨. 반드시 제거 후 실행.

### 배포 확인

```bash
# Pages 프로젝트 배포 확인
wrangler pages deployment list --project-name={blog_id}
```

<!-- GSD:deployment-end -->

<!-- GSD:dashboard-ops-runbook-start -->

## 대시보드 운영 런북 (Dashboard Ops Runbook)

> **목적**: 5000에 붙는 모든 LLM 에이전트가 대시보드를 읽고→문제를 진단·수정하고→사용자에게 보고하는 표준 절차. 별도 SKILL.md 디렉터리는 만들지 않는다(5000에 자동 로드된 전례 없음 — `hugo-blowfish-standardization` 스킬은 계획서에서만 참조되고 실체 파일이 없어 박제된 오류 사례). 이 섹션을 AGENTS.md에 직접 둔다.

### 0. 자동 로드 컨텍스트

- 이 섹션은 `AGENTS.md`(프로젝트 루트, 세션 시작 시 자동 로드)에 있다.
- 대시보드는 5000의 **단일 진실원(single source of truth)**. 대시보드가 말하는 문제만 수정한다. 대시보드 외부 추측으로 코드 수정 금지.
- 대시보드는 `ops_dashboard/app.py` (Flask, 포트 5060)에 의해 제공되며, `ops_dashboard/ops.db`를 읽는다.

---

### 1단계 — 읽기 (READ): 대시보드에서 문제 수집

**대시보드 서버**: `http://localhost:5060`, Basic Auth.

**자격 정보 (평문 하드코딩 금지)**:
- 환경변수 `OPS_USER` / `OPS_PASSWORD`가 있으면 그 값으로 인증.
- 없으면 기본값 `ops` / `112233` 사용 (앱 기본값).
- **스킬 본문에 평문 비밀번호를 하드코딩하지 말 것** — 항상 환경변수 우선, fallback은 "기본값 사용"이라고만 명시.

**핵심 엔드포인트 (GET, 인증 필요)**:

```bash
# 현재 fail·issue 목록 (알림 대상)
curl -s -u "${OPS_USER:-ops}:${OPS_PASSWORD:-112233}" \
  http://localhost:5060/api/attention

# 규칙 14개 + 오류 25개 선언 + 실데이터를 단일 스키마로
curl -s -u "${OPS_USER:-ops}:${OPS_PASSWORD:-112233}" \
  http://localhost:5060/api/registry | python3 -m json.tool
```

**`/api/registry` 응답 스키마 (규칙 1건 예시)**:
```json
{
  "id": "R04",
  "kind": "rule",
  "target": "extend_head.html",
  "status": "fail",
  "severity": "MAJOR",
  "action": "GA4 + 모바일 보정 CSS 필요",
  "evidence": "extend_head: missing GA4, mobile CSS",
  "rule_id": "R04",
  "problem_id": "",
  "bucket": "out_of_scope",
  "threshold": "always"
}
```

**핵심 필드만 보면 됨**:
- `id` + `target` → **무엇이** 실패했는지
- `status` (`"pass"` / `"fail"` / `"unknown"`) → 실패 여부
- `evidence` → **왜** 실패했는지 (구체적인 누락·위반 내용)
- `action` → **어떻게** 고치는지 (조치 안내)
- `severity` → 우선순위 (CRITICAL / MAJOR / MINOR)
- `bucket` → 준수율 산정 방식 (actionable / deferred / out_of_scope)

**`/api/attention`의 `fail_checks` 항목 스키마**:
```json
{
  "blog_id": "techpawz-hugo",
  "check_name": "standard_compliance",
  "pattern": "...",
  "error_msg": "...",
  "rule_id": "R04",
  "problem_id": "standard_compliance",
  "severity": "MAJOR",
  "action": "GA4 + 모바일 보정 CSS 필요"
}
```

`fail_checks`에서 `rule_id`가 있으면 `/api/registry`의 해당 규칙 entry를 조회해 `evidence`·`action`을 얻는다.

---

### 2단계 — 해석 (INTERPRET): 구조필드만 사용, 자유텍스트 파싱 금지

**규칙**: `evidence`가 무엇이 왜 틀렸는지, `action`이 어떻게 고치는지를 담고 있으니 **그대로 따른다**. 자유텍스트(`detail`, `error_msg`, `pattern`) 파싱하지 않는다.

**해석 테이블 (rule_id → evidence → action → severity)**:

| rule_id | target | 실패 시 evidence 패턴 | action (조치) |
|---------|--------|---------------------|---------------|
| R01 | hugo.toml | `showTableOfContents=true` | `showTableOfContents = false`로 변경 |
| R02 | hugo.toml | `[params.advertisement]` 없음 / adsense·slots 누락 | `[params.advertisement]` 섹션 + `adsense`, `topSlot`, `inArticleSlot` 추가 |
| R03 | extend-head.html | `ca-pub-` 하드코딩 | `site.Params`로 교체 |
| R04 | extend_head.html | `missing GA4, mobile CSS` | GA4 스크립트 + `@media (max-width:767px)` 모바일 보정 CSS 추가 |
| R05 | adsense/top.html | `missing overflow:hidden` / `missing min-height` | `overflow:hidden; min-height:100px` 래퍼 + div 밖 push div 추가 |
| R06 | adsense/in-article.html | `missing fluid format` / `data-ad-format=auto (prohibited)` | `data-ad-format="fluid"` + `data-ad-layout="in-article"`, `auto` 제거, `<script>push({})`를 div 밖에 배치 |
| R07 | single.html | `missing H2 split injection, prose wrapper` | H2 분할 인젝션 로직 + `<section class="... prose ...">` 래퍼 추가 |
| R08 | single.html | `.Lead/.Description still present` | `.Lead`/`.Description` 라인 제거 |
| R09 | baseof.html | 커스텀 오버라이드 (5줄 초과) | `layouts/_default/baseof.html` 삭제, 테마 기본값 사용 |
| R10 | custom.css | `No custom.css found` / unfilled·dark 규칙 누락 | `assets/css/custom.css` 생성 (unfilled 제거 + 다크모드 + min-height) |
| R11 | layouts/ | `mobile-sticky.html found` | `layouts/partials/adsense/mobile-sticky.html` 삭제 |
| R12 | layouts/ | `Unauthorized overrides: ...` | 허용 집합 내로 조정하거나 불필요 오버라이드 삭제 |
| THUMBNAIL-01 | content/posts/*/index.md (featureimage) | `썸네일 위반 N건` / R2 아님 / webp 아님 | featureimage를 R2(pub-<hash>.r2.dev) 호스팅 webp로 설정 |
| R2-01 | content/posts/*/index.md (featureimage+본문 이미지) | `R2 패턴 위반 N건` / 비R2 URL | 모든 이미지 URL을 승인된 R2 버킷(pub-<hash>.r2.dev)으로 이전 |

**실제 예시 (이번 세션 관측)**:

1. **techpawz-hugo R2-01 fail**
   ```
   evidence: "R2 패턴 위반 7건 / 검사 7건: 킹스데일cc-20260808-s3/featureimage: https://..."
   action: "모든 이미지 URL을 승인된 R2 버킷(pub-<hash>.r2.dev)으로 설정"
   → 원인: featureimage가 R2 도메인이 아닌 외부 URL. 조치: R2로 이전.
   ```

2. **techpawz-hugo R04 fail**
   ```
   evidence: "extend_head: missing GA4, mobile CSS"
   action: "GA4 + 모바일 보정 CSS 필요"
   → 원인: extend_head.html에 GA4·모바일 CSS 없음. 조치: 추가.
   ```

3. **techpawz-hugo R06 fail**
   ```
   evidence: "in-article.html: missing fluid format, missing in-article format, data-ad-format=auto (prohibited)"
   action: "fluid+in-article format (no auto) + outside push div 필요"
   → 원인: in-article.html에 fluid·in-article 없음 + 금지인 auto 존재. 조치: 규격 맞게 수정.
   ```

**해석 원칙**:
- `status: "unknown"` → 아직 체크 안 됨 (데이터 없음). 무시하거나 체크 실행.
- `bucket: "out_of_scope"` / `"deferred"` → 준수율 산정에서 제외. 지금 고칠 대상 아닐 수 있음 (구조적 문제로 보류).
- `bucket: "actionable"` → 지금 고칠 대상.

---

### 3단계 — 수정 (FIX): action이 지시하는 파일 수정 + 게이트 통과

**수정 원칙**:
1. `action`이 지시하는 파일을 수정한다. 엉뚱한 파일 수정 금지.
2. **설명·의미는 바꾸지 않는다** — 따옴표 이스케이프·컴마·필드명 등 구조적 문제만 수정한다. (이번 세션의 "description 미이스케이프 수정" 패턴 참조)
3. **다른 필드·다른 블로그는 건드리지 않는다** — 해당 blog_id·해당 파일만.

**게이트 (수정 전·중·후 통과 필수)**:

ⓐ **파괴적 작업 전 백업** (신규 명문화 — 이번 세션 정례화):
   - 코드 수정 전: `git tag pre-<작업명>-<YYYYMMDD>`
   - DB 수정 전: `cp data/<db>.db data/<db>.db.bak_<YYYYMMDD>`
   - 예: `git tag pre-r04-fix-20260808` + `cp data/ops.db data/ops.db.bak_r04_20260808`
   - **백업 없이 수정 금지.**

ⓑ **로컬 Hugo 빌드 0에러**:
   ```bash
   HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /경로/블로그
   ```
   - 에러 0건 확인. 에러 있으면 중단·롤백.
   - Hugo 경로는 AGENTS.md §Technology Stack 참조 (`/opt/homebrew/bin/hugo`).

ⓒ **배포는 §Deployment Rules 준수** (AGENTS.md L494~L574 참조, 중복 작성 금지):
   - `dispatcher.py`로 배포: `python3 /Users/twinssn/Projects/5000/dispatcher.py {blog_id}`
   - **절대 수동 wrangler 명령어 금지** (L562).
   - **절대 `--commit-dirty=true` 금지** (L563).
   - **절대 git push로 배포하지 말 것** (L498).
   - Workers 블로그(health, pet, kitchen, beauty, camping, baby)는 `wrangler deploy --config wrangler.toml`, 그 외 Pages 블로그는 `wrangler pages deploy public --project-name={blog_id}` — dispatcher.py가 자동 구분 (L534~L537).
   - 블로그별 **1회 배포**. 동시 배포·반복 배포 금지.

ⓓ **수정 후 재검증 FAIL→PASS 확인** (신규 명문화 — 이번 세션 정례화):
   - 코드 수정 후: `/api/registry`에서 해당 rule_id의 status가 `"fail"` → `"pass"` 또는 `"unknown"`(체크 미실행 상태로 전환)으로 바뀌었는지 확인.
   - 예: R04 fix 후 `/api/registry` → R04 status=`"pass"`, evidence에 `"extend_head: GA4 + mobile CSS found"` 등.
   - **FAIL→PASS 확인 없이 완료 보고 금지.**

**게이트 실패 시**:
- 빌드 에러 → 원복구 (git checkout 또는 백업 복원) 후 재구성.
- 배포 실패 → dispatcher 로그 확인, 재시도하지 말고 원인 보고.
- 재검증 여전히 FAIL → action이 잘못됐거나 추가 문제. 사용자 보고 후 진행.

---

### 4단계 — 보고 (REPORT): 사용자에게 표준 형식

매 작업 종료 시 아래 형식으로 보고한다:

```
## 대시보드 기반 수정 보고

### 대상
- 블로그: {blog_id}
- rule_id: {R04 등}
- status 변경: fail → {pass/unknown}

### 원인 (evidence)
- {/api/registry evidence 필드의 실제 텍스트}

### 조치 (action + 실제 diff)
- 지시: {/api/registry action 필드의 실제 텍스트}
- 수정 파일: {파일 경로}
- diff 요약:
  ```diff
  - 이전 내용
  + 이후 내용
  ```

### 게이트
- [ ] 백업: git tag pre-{작업명}-{YYYYMMDD} + ops.db.bak_{작업명}_{YYYYMMDD}
- [ ] 로컬 Hugo 빌드: 0에러 (로그 링크 또는 "에러 없음")
- [ ] 배포: dispatcher.py로 {blog_id} 1회 배포 (블로그·시간)
- [ ] 재검증: /api/registry {rule_id} status → {pass/unknown} (FAIL→PASS 확인)

### 남은 항목 (백로그)
- {아직 남은 문제 또는 다음 턴으로 넘길 항목}
```

**한 줄 결론 형식**: `"{blog_id} {rule_id} 수정 완료 — evidence: {원인}, action: {조치}, 게이트: 빌드·배포·재검증 통과, 남은: {백로그}."`

---

### 부록 A — 현재 규칙 14개 참조표

| rule_id | kind | target | severity | bucket | action (요약) |
|---------|------|--------|----------|--------|------|
| R01 | rule | hugo.toml | CRITICAL | actionable | showTableOfContents=false |
| R02 | rule | hugo.toml | CRITICAL | actionable | [params.advertisement] + adsense slots |
| R03 | rule | extend-head.html | CRITICAL | out_of_scope | adsbygoogle.js site.Params 사용 |
| R04 | rule | extend_head.html | MAJOR | out_of_scope | GA4 + 모바일 보정 CSS |
| R05 | rule | adsense/top.html | MAJOR | actionable | overflow:hidden;min-height 래퍼 + outside push |
| R06 | rule | adsense/in-article.html | CRITICAL | deferred | fluid+in-article (no auto) + outside push div |
| R07 | rule | single.html | MAJOR | actionable | H2 split injection + prose wrapper |
| R08 | rule | single.html | MAJOR | actionable | Description (lead) 제거 |
| R09 | rule | baseof.html | MAJOR | actionable | 커스텀 오버라이드 없음 — 테마 기본값 |
| R10 | rule | custom.css | MAJOR | actionable | 미채움 공간 제거 + 다크모드 + min-height |
| R11 | rule | layouts/ | MAJOR | actionable | mobile-sticky.html 사용 금지 |
| R12 | rule | layouts/ | MAJOR | actionable | 허용 집합 벗어난 오버라이드 없음 |
| THUMBNAIL-01 | rule | content/posts/*/index.md (featureimage) | MAJOR | actionable | featureimage를 R2 호스팅 webp로 |
| R2-01 | rule | content/posts/*/index.md (featureimage+본문 이미지) | MAJOR | actionable | 모든 이미지 URL R2 버킷으로 |

- 오류 선언: P01~P24 + unknown_failure (25개, errors.py). 문제idio별 detect_fn/hook·action은 `/api/registry` errors 배열에서 확인.

### 부록 B — 새 규칙 추가법

```
새 규칙 추가 = rules.py에 UnifiedEntry 선언 1행 + standard.py에 _check_xxx 함수 1개
```

- **rules.py** (`ops_dashboard/registry/rules.py`): `RULES: list[UnifiedEntry]`에 `UnifiedEntry(id=..., kind="rule", target=..., severity=..., threshold="always", check_fn="_check_xxx", action=..., bucket=...)` 추가.
- **standard.py** (`ops_dashboard/checks/standard.py`): `_check_xxx(site: Path) -> tuple[bool, str]` 함수 구현 + `_CHECK_FUNCTIONS` dict에 등록.
- **W7 확립 패턴**: 선언만으로 자동편입 — `check_standard_compliance`가 `RULES`를 순회 + `_resolve_check_fn`(getattr)로 디스패치. 하드코딩 등록·별도 매핑 불필요.
- **금지**: `check_fn`이 빈 문자열이거나 존재하지 않는 함수명을 가리키는 선언 (W7 검증 게이트: `all(e.check_fn for e in all_entries() if e.kind=="rule")`).

<!-- GSD:dashboard-ops-runbook-end -->

---

## Appendix C — FIX 레시피북 (의도·경계 기반)

> 추가일: 2026-08-08 | 상태: 활성 | 목적: 실행 에이전트가 블로그 구조를 읽고 명령을 생성할 때, 그 생성이 벗어나지 못할 울타리를 정의함. 정확한 명령·정확한 라인은 기록하지 않는다 — 실행 시점에 블로그 구조에서 생성한다.
> 이 레시피북은 AGENTS.md §대시보드 운영 런북의 READ→INTERPRET→FIX 흐름을 대체하지 않으며, FIX 단계의 "무엇을 해도 되고 무엇을 하면 안 되는지"를 성문화한다.

### C.0 등급 요약표

실행 에이전트는 아래 표를 먼저 보고 rule_id/problem_id의 기본등급과 조건부 분기를 확인한다. "결정지점 있음"이면 진행 전 사용자에게 질문 1개를 던진다.

| rule_id / problem_id | 기본등급 | 조건부 분기 (evidence 조건 → 등급) | 사용자 결정지점 |
| ----------------------| -------- | ---------------------------------- | -------------- |
| **R01** | A | `showTableOfContents = true` → A / 이미 false거나 항목 없음 → pass(unknown) / 테마가 TOC를 하드컨트롤해 params로 제어 불가 → B(구조 확인) | 없음 |
| **R02** | A | `[params.advertisement]` 누락 → A(섹션+슬롯 추가) / 섹션 있으나 adsense·슬롯 ID 오류 또는 불명 → B(계정·슬롯 확인) / publisher ID가 계열과 다름 → B(계열 매핑 확인) | 슬롯 ID 실재 여부·계열 확인 필요 시 1회 |
| **R03** | A(단, bucket out_of_scope) | 하드코딩 ca-pub- 없음 + site.Params 사용 → pass / 하드코딩 존재 + site.Params 미사용 → A(사이트.Params 이전) / informationhot 이중관리(STRUCT-15) → B(단일 소스 결정) | informationhot 이중관리 해소 시 단일 소스 결정 1회 |
| **R04** | B | GA4 완전 누락 + mobile CSS 누락 → B(gtag 측정 ID 필요) / GA4 있으나 mobile CSS만 누락 → A(CSS만 추가) / 둘 다 있음 → pass / 측정 ID 제공 불가 → C(측정 ID 결정) | GA4 측정 ID(블로그별) — 없거나 생성 필요시 |
| **R05** | A | overflow:hidden/min-height 누락 → A / push div 위치 오류 → A / 규격 충족 → pass | 없음 |
| **R06** | B(deferred) | auto→fluid 교체만으로 충분 + 슬롯 정책 이슈 없음 → A(파셜 교체) / 슬롯 정책 확인 필요 → B(일괄 승인 1회) / 이미 fluid인데 다른 문제 → B(재Diagnosis) / format 불명 → C | 19블로그 일괄 교체 승인 1회 (B등급 핵심 결정지점) |
| **R07** | A | H2 split injection + prose wrapper 없음 → A / 하나만 없음 → A(없는 쪽 추가) / 둘 다 있음 → pass | 없음 |
| **R08** | A | .Lead/.Description 잔존 → A(삭제) / 이미 제거 → pass / 어떤 요소가 lead인지 불명 → B(식별 확인) | 없음 |
| **R09** | A | 커스텀 baseof.html 존재 → A(삭제, 테마 기본값) / 없음 → pass / 필요 여부 판단 애매 → B(허용 범위 확인) | 특정 오버라이드 필요 여부 애매 시 1회 |
| **R10** | A | custom.css 없음 → A(생성) / 있으나 미채움·다크모드·min-height 누락 → A(보완) / 완비 → pass | 없음 |
| **R11** | A | mobile-sticky.html 존재 → A(삭제) / 없음 → pass | 없음 |
| **R12** | A | 허용 집합 벗어난 오버라이드 + junk 있음 → A(초과 삭제+junk 정리) / 허용 여부 판단 애매 → B(사용자 확인) / junk만 → A(정리) | 허용 판단 애매 시 1회 |
| **THUMBNAIL-01** | B | featureimage 이미 R2 webp → pass / 비R2 → B(원본 R2 존재→A로 전환, 부재→B 유지·재업로드) | 원본 이미지 R2 존재 여부 확인 1회 |
| **R2-01** | B | 모든 이미지 URL R2 → pass / 비R2 존재 → B(원본 R2 존재→A, 부재→B) / featureimage만 위반·본문 이미지 모두 R2 → 영향 축소(A에 가까움) / 본문 이미지 다수 위반 → B 유지·일괄 승인 필요 시 결정 | 원본 이미지 R2 존재 여부 확인 1회 |
| **P02** (no_content) | D(현재 auto_handled) | 재발 시 C(데이터·토픽 보충 결정) / auto_handled 유지 → D | 토픽·데이터 소스 보충 결정 |
| **P06** (broken_featureimage) | B | 썸네일 R2 존재 → A(batch_thumbnails.py) / 원본 소실 → B(재업로드 판단) / 구조적 경로 문제 → B/C(경로 정책 확인) | 원본 재업로드 판단 1회 |
| **P14** (keyword 소진) | C | informational_keyword → C(키워드 소스 보충 결정) / 데이터 소스 보충 완료 → A 재개 / 정책 유지 → D | 키워드 소스 보충 결정 |
| **P17** (매일 소진) | D(quiet, auto_skipped) | 정책 변경 필요 → C / 유지 → D | 정책 변경 결정 |
| **P15** (발행 후 검증 실패) | C | 로그 확인 후 원인 특정 → B / 원인 불명 → C | 원인 조사 범위 결정 |
| **P01** (no_result) | C | 가드 완화로 해결 가능 → B / 데이터 소스 보충 필요 → C / auto_skipped 유지 → D | 가드 조정 vs 데이터 보충 결정 |
| **P10** (title_blocked) | B | 패턴 조정·변형 다양화로 해결 → B / 차단 정책 자체 변경 필요 → C / auto_skipped 유지 → D | 차단 패턴 정책 결정 |
| **P18** (동시 실행 방지) | D(quiet, auto_skipped) | lock 강화 필요 → B / 유지 → D | lock 정책 결정 |
| **leak_detected** | B | 스캔→발견→재현 생성 방지 조치(A) / CoT 누출 경로 모호 → C(재Diagnosis) / 의심만·특정 불가 → C | 재현 경로 확인 |
| **known_issue** | C(또는 D) | 재현·해결책 명확 → B / 불명 → C / 백로그 이연 결정 → D | 해결 우선순위 결정 |
| **dead_entity_link** | B | 404 링크 탐지→교체/제거 결정(B) / 엔티티 재등록 필요 → C / 탐지 불가 → C | 링크 처리 방식 결정 |

> 등급: A=자동, B=반자동(판단 1회), C=사람 필요, D=외부/보류. 기본등급은 현재 증거 기준; evidence 조건이 바뀌면 등급도 바뀐다. 조건부 분기를 먼저 평가한다.

### C.1 후자 방식 공통 원칙

#### C.1.1 의도·경계 기반 실행 모델

실행 에이전트는 레시피의 "목표 상태"와 "허용 범위"를 읽고, 해당 블로그의 실제 파일 구조를 확인한 뒤 **스스로 명령을 생성**한다. 레시피에는 정확한 sed/정규식/라인 번호를 기록하지 않는다 — 그건 블로그마다 다르기 때문이다. 대신 다음만 기록한다:

- **목표 상태**: 어떤 조건을 만족하면 "고쳐졌다"고 볼 수 있는가 (증거 기반)
- **허용 범위**: 수정이 건드려도 되는 파일/영역과 절대 건드리면 안 되는 것
- **STOP 조건**: 생성이 폭주하는 신호를 감지하는 체크포인트
- **사용자 결정지점**: B/C 등급일 때 사람에게 물을 단 하나의 질문

에이전트는 생성된 계획(예상 변경 파일 목록·예상 변경 규모)을 실행 전에 보고하고, STOP 조건에 걸리지 않을 때만 진행한다. 목표 상태가 불명확하거나 허용 범위와 충돌하면 창의적 재해석을 금지하며 즉시 사용자에게 회신한다.

#### C.1.2 필수 공통 게이트 (모든 FIX에 적용)

1. **백업**: 코드 수정 전 `git tag pre-<작업명>-<YYYYMMDD>` + DB 관련 시 `cp data/<db>.db data/<db>.db.bak_<YYYYMMDD>`. 백업 없이 수정 금지.
2. **로컬 Hugo 빌드 0에러**: `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /경로/블로그`. 에러 있으면 중단·롤백.
3. **배포**: `dispatcher.py`로 블로그별 1회 배포. 수동 wrangler·`--commit-dirty=true`·git push 금지. Workers 블로그(health/pet/kitchen/beauty/camping/baby)는 `wrangler deploy --config wrangler.toml`, 그 외 Pages는 `wrangler pages deploy` — dispatcher.py가 자동 구분.
4. **재검사 트리거 (필수, 누락 금지)**: 코드 수정·배포 후 화면이 갱신되려면 반드시 수동 재검사 호출이 필요하다. 대시보드에는 자동 재검사 스케줄이 없으므로, **POST /api/run-checks?blog_id={blog_id}**(개별 블로그) 또는 **POST /api/run-checks**(전체)를 호출하지 않으면 `/api/registry`·`/api/attention`·블로그 상세 페이지에 수정 결과가 반영되지 않는다.
   - 개별 블로그 FIX 후: `curl -s -X POST -u "${OPS_USER:-ops}:${OPS_PASSWORD:-112233}" "http://localhost:5060/api/run-checks?blog_id={blog_id}"` → 반환 직후 check_results 갱신. 그 다음에 `/api/registry` status 확인.
   - 정비 체크리스트 항목(M01~M10) FIX 후: `curl -s -X POST -u "${OPS_USER:-ops}:${OPS_PASSWORD:-112233}" -H "Content-Type: application/json" -d "{\"blog_id\":\"{blog_id}\"}" "http://localhost:5060/api/maintenance/checklist"` → 정비 체크리스트 재실행.
   - **경고**: 이 호출 없이는 FAIL→PASS를 확인할 수 없다. 체크 결과를 "믿고" 완료 보고하는 것은 금지.
5. **재검증 FAIL→PASS 확인**: 재검사 트리거 호출 후 `/api/registry`에서 해당 rule_id의 status가 `"fail"` → `"pass"` 또는 `"unknown"`(체크 미실행 상태로 전환)으로 바뀌었는지 확인. 예: R04 fix 후 `/api/registry` → R04 status=`"pass"`, evidence에 `"extend_head: GA4 + mobile CSS found"` 등. **FAIL→PASS 확인 없이 완료 보고 금지.**
6. **로그**: 파괴적 작업 포함 시 `logs/destructive_YYYY-MM-DD.log`에 한 줄 append. 민감정보 마스킹.

게이트 실패 시: 빌드 에러 → 원복구(git checkout 또는 백업 복원) 후 재구성. 배포 실패 → dispatcher 로그 확인, 재시도 금지. 재검증 여전히 FAIL → action이 잘못됐거나 추가 문제 — 사용자 보고 후 진행. **재검사 트리거를 호출하지 않은 상태에서 "FAIL→PASS 예상"으로 완료 보고하는 것은 게이트 위반.**

#### C.1.2.1 자동 갱신 대기의 STOP 조건

- 현재 대시보드는 **자동 재검사 스케줄이 없다**. "배포했으니 잠시 후 화면이 갱신되길 기다린다"는 계획은 STOP 조건 (e): 목표 상태가 증거 기반으로 특정되지 않음 + "자동 갱신이 언제 올지 불명"에 해당. 에이전트는 재검사를 명시적으로 직접 호출해야 하고, 호출 전까지 화면 상태를 "확정된 것"으로 취급하지 않는다.
- 재검사 트리거 후에도 FAIL이 유지되면, 재시도 무한루프는 금지. 원인 귀속 후 진행(코드 수정 재시도 vs action 오류 판단).

#### C.1.3 STOP 조건 (공통, 실행 에이전트 필수 체크)

실행 에이전트는 계획 실행 전/중/후에 아래 조건을 체크한다. **하나라도 걸리면 즉시 중단하고 사용자에게 보고한다.** 애매하면 실행하지 말고 보고한다.

| # | STOP 조건 | 트리거 예시 |
| -- | -------- | ---------- |
| (a) | **허용 범위 벗어남** | 레시피에서 허용한 파일 외 파일이 diff에 포함됨 |
| (b) | **예상 변경 규모 초과** | 1파일 기대인데 3파일 diff / 예상 7건 교체인데 20건 변경 |
| (c) | **빌드 에러** | Hugo 빌드에서 에러 발생 (로컬 빌드 게이트) |
| (d) | **/api/registry 총량·분포 이상 변화** | 목표 rule_id 외에 인접 규칙까지 fail로 변함 / fail 총량이 레시피 목표와 다르게 움직임 |
| (e) | **목표 상태 불명확** | evidence로 목표 상태가 특정되지 않음 / "유체화"처럼 정성적 표현으로만 정의됨 |
| (f) | **비가역 작업 감지** | DB DELETE/UPDATE/DROP, 테마 변경, 대량 삭제, 실발행 행 덮어쓰기가 계획에 포함됨 → 자동 금지, 별도 웨이브·명시 승인 필요 (C.4 참조) |

> (f)는 하드 STOP이다. 레시피에 "자동 금지" 플래그가 붙은 항목은 에이전트가 스스로 계획을 생성하더라도 실행하지 않는다. 사용자에게 명시적 웨이브 승인 없이는 진행 불가.

### C.2 규칙 레시피 (R01~R12, THUMBNAIL-01, R2-01)

> 각 항목은 아래 스키마를 따른다: rule_id/한 줄 정의 → 등급 결정트리 → 수정 의도(목표 상태) → 허용 범위(경계) → 사용자 결정지점(B/C) → STOP 조건 → 검증 → 비가역 플래그.

#### R01 — hugo.toml: showTableOfContents

- **정의**: Hugo 사이트의 목차(TOC) 표시가 활성화되어 있어 표준과 어긋나는 상태.
- **등급 결정트리**:
  - `showTableOfContents = true` → **A**
  - 이미 `false`거나 항목이 없음 → **unknown**(패스)
  - hugo.toml이 없거나 테마가 TOC를 하드컨트롤해서 params로 제어 불가 → **B**(구조 확인 필요)
- **수정 의도 (목표 상태)**: 사이트 전체 글에서 자동 생성되는 TOC가 비활성화된 상태. `showTableOfContents`가 `false`로 설정되어 있고, Hugo 빌드가 이를 수용하는 상태.
- **허용 범위 (경계)**:
  - ✅ 건드려도 됨: hugo.toml의 `[params]` 또는 최상위 `showTableOfContents` 값.
  - ❌ 건드리면 안 됨: layouts, 콘텐츠, 다른 params, 테마 파일.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) hugo.toml 외의 파일이 변경됨 → 중단
  - (d) R01 외에 다른 rule_id까지 fail로 변함 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 대시보드에는 자동 재검사 스케줄 없음 — 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면을 갱신한 뒤 재검증해야 함. 자동 갱신을 기다리는 계획은 STOP.
- **검증**: `/api/registry` R01 status = `pass` (또는 `unknown`).
- **비가역 플래그**: 없음.

#### R02 — hugo.toml: [params.advertisement] + AdSense slots

- **정의**: hugo.toml에 광고 설정 파라미터가 누락되거나 슬롯 구성이 표준과 다른 상태.
- **등급 결정트리**:
  - `[params.advertisement]` 섹션 자체가 없음 → **A**(섹션 추가 + adsense + topSlot/inArticleSlot 설정)
  - 섹션은 있으나 adsense/publisher ID 오류 또는 슬롯 ID 불명 → **B**(AdSense 콘솔에서 슬롯 ID 확인 필요)
  - publisher ID가 계열의 것과 다름(AdSense ID 매핑 위배) → **B**(계열 확인 후 정정)
- **수정 의도 (목표 상태)**: hugo.toml에 `[params.advertisement]`가 존재하고, `adsense`(publisher ID), `topSlot`, `inArticleSlot`(또는 테마가 요구하는 슬롯 키)가 채워져 있으며, publisher ID가 해당 사이트 계열의 올바른 계정인 상태.
- **허용 범위 (경계)**:
  - ✅ hugo.toml의 `[params.advertisement]` 섹션 및 그 키들.
  - ❌ layouts, 콘텐츠, 다른 설정 파일. 슬롯 ID 자체를 악의적으로 바꾸지 말 것(실제 존재하는 슬롯인지 확인).
- **사용자 결정지점**: 슬롯 ID가 실제 AdSense 계정에 존재하는지 확인이 필요할 때 1회.
- **STOP 조건**:
   - (a) hugo.toml 외 파일 변경 → 중단
   - (d) R02 수정 후 R03/R06 등 연관 광고 규칙이 예상과 다르게 변함 → 중단·보고
   - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R02 status = `pass`.
- **비가역 플래그**: 없음. 단, publisher ID 변경은 수익 영향 → 변경 전 계열 매핑 확인 필수.

#### R03 — extend-head.html: adsbygoogle.js 하드코딩 제거 (site.Params 사용)

- **정의**: extend-head.html에 AdSense 클라이언트 ID가 하드코딩되어 있고, site.Params를 쓰지 않는 상태. (주의: informationhot-hugo는 STRUCT-15로 이중 관리 중 — extend-head.html 하드코딩 + params.toml advertisement.adsense 동시 존재.)
- **등급 결정트리**:
  - 하드코딩 ca-pub- 없음 + site.Params 사용 중 → **pass**
  - 하드코딩 ca-pub- 존재 + site.Params 미사용 → **A**(사이트.Params 기반으로 이전) — 단, bucket이 out_of_scope이므로 준수율 산정에서는 제외. 그래도 수정은 가능.
  - informationhot 계열에서 하드코딩과 params.toml이 이중 존재(STRUCT-15) → **B**(어느 쪽을 소스로 할지 결정: 사이트.Params 기준으로 단일화)
- **수정 의도 (목표 상태)**: AdSense 클라이언트 ID가 사이트 설정(params)에서만 관리되고, extend-head.html 템플릿은 그 값을 참조하는 상태. 하드코딩된 ca-pub- 문자열이 템플릿에서 사라짐.
- **허용 범위 (경계)**:
  - ✅ extend-head.html 내 adsbygoogle.js 로딩 부분의 클라이언트 참조 방식.
  - ❌ 콘텐츠, 다른 파셜, params.toml의 광고 설정을 임의로 삭제(단, 이중 관리 해소 시는 예외 — B등급으로 판단 1회).
- **사용자 결정지점**: informationhot 계열처럼 이중 관리 해소 시, 어느 쪽을 단일 소스로 할지 1회.
- **STOP 조건**:
  - (a) extend-head.html 외 파일 변경 → 중단
  - (f) params.toml 광고 설정을 레시피 의도와 다르게 삭제/변경 → 중단 (의도: 하드코딩 제거 + 사이트.Params 참조. 설정값 자체를 없애는 것 아님.)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R03 status = `pass` (또는 체크 방식상 `unknown`로 전환).
- **비가역 플래그**: 없음. 단, informationhot의 이중 관리 해소는 STRUCT-15 연계 → 변경 전 확인.

#### R04 — extend_head.html: GA4 + 모바일 보정 CSS

- **정의**: extend_head.html에 GA4(gtag) 추적 스니펫이 없고, 일부 블로그는 모바일 보정 CSS(`@media (max-width:767px)`)도 없는 상태.
- **등급 결정트리**:
  - GA4 완전 누락 + 모바일 CSS 누락 → **B**(GA4 측정 ID 필요 + 모바일 CSS 추가)
  - GA4는 있으나 모바일 CSS만 누락 → **A**(모바일 보정 CSS만 추가)
  - 둘 다 있음 → **pass**
  - GA4 측정 ID가 무엇인지 확인 불가/제공 안 됨 → **C**(측정 ID 결정 필요)
- **수정 의도 (목표 상태)**: extend_head.html에 구글 애널리틱스 4(gtag) 스니펫이 블로그별 측정 ID로 삽입되어 있고, 모바일 화면(최대 767px)에서 레이아웃 보정을 위한 CSS가 포함된 상태.
- **허용 범위 (경계)**:
  - ✅ extend_head.html 내 GA4 스니펫 추가 + 모바일 보정 CSS 블록 추가.
  - ❌ 콘텐츠, 레이아웃, 다른 파셜, GA4 측정 ID 자체를 에이전트가 만들어내지 말 것(측정 ID는 사람이 제공).
- **사용자 결정지점**: GA4 측정 ID(블로그별). 없으면 생성 여부·계정을 사람이 결정. **이 질문이 B등급의 유일한 개입 지점.**
- **STOP 조건**:
  - (a) extend_head.html 외 파일 변경 → 중단
  - (e) 측정 ID가 제공되지 않았고 에이전트가 임의로 추정 생성하려 함 → 중단·보고 (추정 금지)
  - (d) R04 수정 후 R03/R17(STRUCT-17 연계) 등 상태 이상 변화 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R04 status = `pass`.
- **비가역 플래그**: 없음. 단, GA4 측정 ID 변경은 추적 단절 → 기존 ID가 있으면 재사용, 없으면 신규 생성 결정은 사람.

#### R05 — adsense/top.html: overflow:hidden;min-height 래퍼 + outside push div

- **정의**: top 광고 파셜에 `overflow:hidden` 및 `min-height`가 없거나, push 스크립트/스타브가 래퍼 밖에 제대로 배치되지 않은 상태.
- **등급 결정트리**:
  - overflow:hidden 및 min-height 누락 → **A**(래퍼 추가)
  - push div가 래퍼 밖에 없음 → **A**(div 밖 배치)
  - 이미 규격 충족 → **pass**
- **수정 의도 (목표 상태)**: top 광고 영역에 `overflow:hidden; min-height:100px` 스타일의 래퍼가 있고, 광고 push를 위한 스크립트(div 밖)가 래퍼 외부에 위치한 상태.
- **허용 범위 (경계)**:
  - ✅ `layouts/partials/adsense/top.html` 내부 구조.
  - ❌ 다른 파셜, 콘텐츠, config.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) top.html 외 파일 변경 → 중단
  - (b) 1파일 기대인데 다수 파일 diff → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R05 status = `pass`.
- **비가역 플래그**: 없음.

#### R06 — adsense/in-article.html: fluid + in-article format (no auto) + outside push div

- **정의**: in-article 광고 파셜이 `data-ad-format="auto"`를 쓰거나 fluid/in-article format이 누락되어 AdSense 표준과 어긋난 상태. bucket은 `deferred` — AdSense 정책 확인 후 처리 권장.
- **등급 결정트리**:
  - auto → fluid/in-article 교체만으로 충분, 슬롯 정책 이슈 없음 → **A**(파셜 교체)
  - 교체 자체는 명확하나 AdSense 계정에서 해당 슬롯의 포맷 정책을 확인해야 함 → **B**(일괄 처리 전 승인 1회)
  - 이미 fluid인데 다른 문제(예: push 위치)가 있음 → **B**(정확히 무엇이 잘못됐는지 재Diagnosis)
  - data-ad-format이 auto도 fluid도 아닌데 불명 → **C**(재Diagnosis)
- **수정 의도 (목표 상태)**: in-article 광고가 fluid 레이아웃으로 렌더되고, `data-ad-format="fluid"` 및 `data-ad-layout="in-article"`이 설정되어 있으며, `<script>push({})</script>`가 `<ins>` 태그 밖에 위치한 상태.
- **허용 범위 (경계)**:
  - ✅ `layouts/partials/adsense/in-article.html` 내부.
  - ❌ layouts 전체, 콘텐츠, config, 다른 광고 파셜(top.html 등 — 이 레시피 범위 아님).
- **사용자 결정지점**: 19개 블로그의 in-article 파셜을 일괄 fluid로 교체할지 1회 승인. (B등급의 핵심 결정지점.)
- **STOP 조건**:
  - (a) in-article.html 외 파일 변경 → 중단
  - (b) 1블로그 1파일 기대인데 여러 파일/블로그가 한 번에 변경됨 → 중단·보고 (레시피는 블로그별 1파일. 일괄이 필요하면 별도 승인.)
  - (e) 목표 상태가 evidence로 특정되지 않음 — 예: "fluid가 뭔지 모호" → 중단. 이 레시피에서는 "data-ad-format=fluid + data-ad-layout=in-article + push div 밖"으로 특정됨 → 통과.
  - (d) R06 수정 후 R05/R11/R12 등 인접 규칙 상태 이상 변화 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R06 status = `pass` + 동일 블로그의 R05·R11·R12 무영향 확인.
- **비가역 플래그**: 없음(파일 내용 수정). 단, AdSense 슬롯 실제 동작은 외부 의존 → 라이브에서 blank 광고 발생 시 별도 조사.

#### R07 — single.html: H2 split injection + prose wrapper

- **정의**: single.html에 H2 분할 인젝션 로직과 prose wrapper(`<section class="... prose ...">`)가 없는 상태.
- **등급 결정트리**:
  - H2 split injection + prose wrapper 없음 → **A**(표준 패턴 추가)
  - 하나만 있고 하나만 없음 → **A**(없는 쪽 추가)
  - 둘 다 있음 → **pass**
- **수정 의도 (목표 상태)**: single.html의 본문 영역에서 H2마다 콘텐츠 분할이 일어나고, 본문이 prose 클래스가 붙은 section 래퍼로 감싸진 상태.
- **허용 범위 (경계)**:
  - ✅ single.html 내 본문 출력 부분의 구조(인젝션 로직 + 래퍼).
  - ❌ 콘텐츠, 다른 레이아웃, config.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) single.html 외 파일 변경 → 중단
  - (b) 예상 1파일 변경인데 다수 템플릿이 영향받음 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R07 status = `pass`.
- **비가역 플래그**: 없음.

#### R08 — single.html: .Lead / .Description 제거

- **정의**: single.html에 `.Lead`/`.Description` 클래스 요소가 남아 있어 표준과 어긋난 상태(정보 없음-hot, senior-hugo 등).
- **등급 결정트리**:
  - .Lead/.Description 잔존 → **A**(해당 라인 제거)
  - 이미 제거됨 → **pass**
  - 어떤 요소가 lead인지 불명확 → **B**(단일 요소 식별 확인)
- **수정 의도 (목표 상태)**: single.html에서 `.Lead`/`.Description` 클래스 요소가 제거되어, 본문 첫 문단이 과대 표시되는 블로우피시 기본 동작이 비활성화된 상태.
- **허용 범위 (경계)**:
  - ✅ single.html 내 .Lead/.Description 관련 라인.
  - ❌ 콘텐츠, 다른 템플릿, 본문 출력 로직 전체.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) single.html 외 파일 변경 → 중단
  - (e) "lead"가 어떤 요소인지 특정 안 됨 → 중단·보고 (이 레시피는 .Lead/.Description 클래스명으로 특정)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R08 status = `pass`.
- **비가역 플래그**: 없음.

#### R09 — baseof.html: 커스텀 오버라이드 없음 (테마 기본값 사용)

- **정의**: baseof.html에 테마 기본값을 벗어나는 커스텀 오버라이드가 있는 상태.
- **등급 결정트리**:
  - 커스텀 baseof.html 존재(5줄 초과 등) → **A**(삭제, 테마 기본값 사용)
  - 커스텀 없음 → **pass**
  - 어떤 오버라이드가 필요한지/불 필요한지 판단 애매 → **B**(허용 범위 확인)
- **수정 의도 (목표 상태)**: `layouts/_default/baseof.html`이 없거나(삭제) 테마 기본값을 그대로 사용하는 상태. 불필요한 커스텀 오버라이드가 없음.
- **허용 범위 (경계)**:
  - ✅ layouts/_default/baseof.html (삭제 가능).
  - ❌ 다른 레이아웃, 파셜, 콘텐츠.
- **사용자 결정지점**: 어떤 baseof.html 오버라이드가 실제로 필요한지 판단 애매할 때 1회.
- **STOP 조건**:
  - (a) baseof.html 외 파일 변경 → 중단
  - (e) "불필요한 오버라이드" 범위가 애매 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R09 status = `pass`.
- **비가역 플래그**: 없음(삭제). 단, 삭제 후 실제 사이트에 필요한 오버라이드였으면 복원 필요 → 삭제 전 diff 기억.

#### R10 — custom.css: 미채움 공간 제거 + 다크모드 + min-height

- **정의**: `assets/css/custom.css`가 없거나, 있어도 미채움(unfilled) 공간 처리·다크모드·min-height 규칙이 누락된 상태.
- **등급 결정트리**:
  - custom.css 없음 → **A**(표준 custom.css 생성)
  - 있으나 미채움·다크모드·min-height 누락 → **A**(규칙 보완)
  - 이미 완비 → **pass**
- **수정 의도 (목표 상태)**: `assets/css/custom.css`가 존재하고, 미채움(unfilled) 요소 공간 제거, 다크모드 대응, 적절한 min-height 조절이 포함되어 있는 상태.
- **허용 범위 (경계)**:
  - ✅ `assets/css/custom.css` (신규 생성 또는 보완).
  - ❌ Hugo config, 테마 파일, 다른 CSS, 콘텐츠.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) custom.css 외 파일 변경 → 중단
  - (b) CSS 생성이 여러 파일로 번짐 → 중단·보고 (1파일 생성 기대)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R10 status = `pass`.
- **비가역 플래그**: 없음.

#### R11 — layouts/: mobile-sticky.html 사용 금지

- **정의**: `layouts/partials/adsense/mobile-sticky.html` 등 mobile-sticky 광고 파셜이 존재하는 상태(사용 금지 대상).
- **등급 결정트리**:
  - mobile-sticky.html 존재 → **A**(삭제)
  - 없음 → **pass**
- **수정 의도 (목표 상태)**: mobile-sticky 광고 파셜이 레이아웃에서 제거되어, 금지된 sticky 광고 패턴이 더이상 사용되지 않는 상태.
- **허용 범위 (경계)**:
  - ✅ `layouts/partials/adsense/mobile-sticky.html` (삭제).
  - ❌ 다른 광고 파셜, 콘텐츠, config.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) mobile-sticky.html 외 파일 변경 → 중단
  - (f) 삭제 대신 비활성화만 하려는 시도가 범위를 넘는지 확인 (이 레시피는 삭제 지향; 다른 방식의 비활성화는 별도 검토)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R11 status = `pass`.
- **비가역 플래그**: 없음(삭제). 단, 삭제 후 필요하면 재생성 가능.

#### R12 — layouts/: 허용 집합 벗어난 오버라이드 없음 (junk 정리 포함)

- **정의**: layouts/ 디렉터리에 허용된 집합을 벗어난 오버라이드 파일이 있거나, `.DS_Store`·`.bak`류 junk가 남아 있는 상태.
- **등급 결정트리**:
  - 허용 집합 벗어난 오버라이드 존재 + junk 있음 → **A**(초과 파일 삭제 + junk 정리)
  - 허용 여부 판단 애매(어느 게 필요한지 불명확) → **B**(사용자 확인 1회)
  - junk만 있음 → **A**(junk만 정리)
- **수정 의도 (목표 상태)**: layouts/ 디렉터리가 허용 집합 내의 오버라이드만 남기고, `.DS_Store`·`.bak`·`.bak2` 등 junk가 제거된 상태.
- **허용 범위 (경계)**:
  - ✅ 허용 집합 외 오버라이드 파일 삭제 + junk(.DS_Store, *.bak, *.bak2 등) 정리.
  - ❌ 허용 집합 내 파일, 콘텐츠, config. "무엇이 허용 집합인지"는 이 레시피가 정하지 않음 — 표준 compliance 체크(standard.py)의 허용 집합을 따름.
- **사용자 결정지점**: 특정 파일이 허용 집합인지 판단이 애매할 때 1회. (B.)
- **STOP 조건**:
  - (a) 허용 집합 내 파일이 diff에 포함됨 → 중단
  - (b) junk 정리가 여러 디렉터리로 번짐 → 중단·보고 (레시피는 layouts/ 내 junk만)
  - (e) "허용 집합" 기준 불명확 → 중단·보고 (이 경우 standard.py의 허용 목록을 먼저 확인)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R12 status = `pass`.
- **비가역 플래그**: 없음(삭제). 단, 삭제 전 어떤 파일을 지웠는지 기록(복원 가능하게).

#### THUMBNAIL-01 — content/posts/*/index.md (featureimage): R2 호스팅 webp

- **정의**: 포스트의 frontmatter `featureimage`가 R2(pub-<hash>.r2.dev)에 호스팅된 webp가 아닌 URL로 설정된 상태.
- **등급 결정트리**:
  - featureimage가 이미 R2 webp URL → **pass**
  - 비R2 URL → **B**(원본 이미지가 R2에 존재하는지 확인)
    - 원본 R2 존재 → 해당 URL로 치환: **A**로 전환
    - 원본 R2 부재 → **B** 유지 (재업로드 필요, batch_thumbnails.py 또는 수동 업로드 판단)
- **수정 의도 (목표 상태)**: 포스트의 `featureimage`가 `pub-<hash>.r2.dev` 도메인의 webp URL을 가리키는 상태.
- **허용 범위 (경계)**:
  - ✅ 해당 포스트의 `content/posts/<slug>/index.md` frontmatter `featureimage` 필드.
  - ❌ 다른 포스트, layouts, config, 본문 이미지(R2-01 영역 — 이 레시피 범위 아님).
- **사용자 결정지점**: 원본 이미지가 R2에 이미 있는지 확인. 없으면 재업로드 여부·방법 판단 1회. (B.)
- **STOP 조건**:
  - (a) featureimage 외 필드/파일 변경 → 중단
  - (b) 1포스트 기대인데 여러 포스트가 한 번에 변경됨 → 중단·보고 (레시피는 포스트별 1건. 일괄이 필요하면 별도 승인.)
  - (f) featureimage를 R2 URL로 바꾸면서 원본 이미지를 삭제/덮어쓰는 행위 → 중단 (원본 보존이 전제)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` THUMBNAIL-01 status = `pass` + 해당 포스트 featureimage가 R2 webp URL인지 확인.
- **비가역 플래그**: 없음(URL 치환). 단, 원본 이미지 소실 시 재업로드가 필요해지면 작업 범위 확대 → 그때 B 유지.

#### R2-01 — content/posts/*/index.md (featureimage + 본문 이미지): 모든 이미지 URL R2 버킷

- **정의**: featureimage 및 본문 내 이미지 URL이 승인된 R2 버킷(pub-<hash>.r2.dev)이 아닌 외부 도메인으로 설정된 상태.
- **등급 결정트리**:
  - 모든 이미지 URL이 R2 → **pass**
  - 비R2 URL 존재 → **B**(원본 R2 존재 여부 확인)
    - 원본 R2 존재 → URL 치환만: **A**로 전환
    - 원본 R2 부재 → **B** 유지 (이미지 재업로드 필요)
  - featureimage만 위반이고 본문 이미지는 모두 R2 → 영향 범위 축소(A에 가까움)
  - 본문 이미지 다수가 비R2 → 규모 확인 후 B 유지, 일괄 치환 승인 필요 시 결정지점
- **수정 의도 (목표 상태)**: 포스트의 featureimage와 본문 내 모든 이미지 URL이 `pub-<hash>.r2.dev` 도메인을 가리키는 상태. 원본 이미지가 R2에 호스팅되어 있고, URL이 그 R2 주소로 치환된 상태.
- **허용 범위 (경계)**:
  - ✅ 해당 포스트의 `content/posts/<slug>/index.md` frontmatter `featureimage` + 본문 Markdown 내 이미지 URL(`![...](...)`).
  - ❌ 다른 포스트, layouts, config, 이미지 원본 파일(삭제/수정 금지 — URL만 치환).
- **사용자 결정지점**: 원본 이미지가 R2에 이미 호스팅돼 있는지 확인. 없으면 재업로드 여부·방법 판단 1회. (B.)
- **STOP 조건**:
  - (a) 해당 포스트 외 파일/포스트 변경 → 중단
  - (b) 예상 변경 건수(예: 7건)를 초과해 다수 포스트·이미지가 변경됨 → 중단·보고
  - (f) 이미지 원본을 삭제/변환/덮어쓰는 행위 → 중단 (URL 치환만 허용)
  - (e) "본문 이미지" 범위가 불명확(예: 어떤 마크업이 이미지인지 식별 곤란) → 중단·보고 (이 레시피는 `![...](url)`와 HTML `<img src=>`를 이미지로 본다; 그 외 애매하면 정지)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R2-01 status = `pass` + 해당 포스트의 featureimage·본문 이미지 URL이 모두 R2 도메인인지 확인.
- **비가역 플래그**: 없음(URL 치환). 단, 원본 이미지가 실제로 R2에 없으면 재업로드가 수반되고, 그때는 작업 범위가 늘어나므로 B 유지.

### C.3 발행 오류 레시피 (select)

> 아래 recipe는 `/api/registry` errors 배열에서 status가 active한 문제idio에 적용한다. status가 `auto_handled`/`auto_skipped`/`logged`이면 현재 활성 fail이 아니므로, 레시피를 "대기" 상태로 두고 재발 시 적용한다. 각 레시피는 status별 사람 개입 필요 여부를 명시한다.

#### P02 — no_content (콘텐츠 생성 실패)

- **정의**: 파이프라인이 토픽을 시도했으나 article을 생성하지 못한 상태.
- **status별**:
  - `auto_handled` (현재): 에이전트가 자동으로 처리함. 추가 개입 불필요 — **D**(현재 상태 유지). 재발 시 아래 적용.
  - `fail`/미처리: **C** — 데이터 소스·토픽 보충 결정 필요. 에이전트가 단독 재개 불가.
- **수정 의도 (목표 상태)**: 파이프라인이 유효한 데이터·토픽으로 content를 생성해 발행하는 상태. 현재 active fail이면 "재시도 가능한 데이터/토픽이 확보된 상태".
- **허용 범위**: 파이프라인 코드·데이터 수집 설정 영역. 콘텐츠 자체 재작성 아님.
- **사용자 결정지점 (C)**: 어떤 데이터 소스·키워드·토픽을 보충할지 결정 1회. 에이전트 단독 불가.
- **STOP 조건**: (e) 목표 상태가 "데이터 보충"으로만 정의되고 구체적 소스·토픽이 없음 → 중단·보고.
- **검증**: 해당 블로그의 freshness·표준 compliance가 정상화되고, 발행이 succeeds.
- **비가역 플래그**: 없음.

#### P14 — keyword 소진 / 제품 멸망 (informational_keyword)

- **정의**: 키워드 소스로 쓸 데이터가 고갈되거나 제품이 멸망해 발행 불가 상태. 현재 `auto_skipped`.
- **status별**:
  - `auto_skipped` (현재): 자동 스킵 중. **D**(현재 상태 유지). 재발·정책 변경 시 아래.
  - 활성 fail: **C** — 키워드 소스 보충·콘텐츠 방향 결정 필요.
- **수정 의도 (목표 상태)**: 유효한 키워드·데이터 소스가 확보되어 파이프라인이 다시 콘텐츠를 생성할 수 있는 상태.
- **허용 범위**: 데이터 소스·키워드 설정 영역.
- **사용자 결정지점 (C)**: 키워드 소스를 어떻게 보충할지(새 소스 추가, 기존 소스 재수집, 콘텐츠 방향 전환 등) 결정 1회.
- **STOP 조건**: (e) "키워드 보충"이 구체적인 소스로 특정되지 않음 → 중단·보고.
- **검증**: 해당 블로그 발행 정상화가 확인됨.
- **비가역 플래그**: 없음.

#### P17 — 매일 소진 (일일 소진 한도)

- **정의**: 일일 발행 한도에 도달해 추가 발행이 막힌 상태. 현재 `auto_skipped`, quiet.
- **status별**:
  - `auto_skipped`/quiet (현재): **D** — 정책 유지로 충분. 변경 필요 시 아래.
  - 정책 변경 필요: **C** — 한도·스케줄 정책 결정.
- **수정 의도 (목표 상태)**: 일일 소진 정책이 의도와 맞게 설정되어 있고, 한도 도달 시 적절히 스킵되는 상태.
- **허용 범위**: 스케줄·설정 영역.
- **사용자 결정지점 (C)**: 일일 한도·스케줄을 how 조정할지 결정 1회. 현 상태 유지는 결정 불필요.
- **STOP 조건**: (e) "한도 조정"이 수치·정책으로 특정되지 않음 → 중단·보고.
- **검증**: 해당 블로그의 daily quota 동작이 의도와 같음.
- **비가역 플래그**: 없음.

#### P15 — 발행 후 검증 실패

- **정의**: 발행한 콘텐츠에 대해 사후 검증에서 실패가 발생한 상태. 현재 `logged`.
- **status별**:
  - `logged` (현재): 로그만 남음. 재발 시 조사. **C**(원인 조사 필요).
  - 원인 특정 후: **B** — 조치 방향이 정해지면 반자동.
  - 원인 불명: **C**.
- **수정 의도 (목표 상태)**: 발행 후 검증이 통과하고, 실패 원인이 해소된 상태.
- **허용 범위**: 콘텐츠·검증 로직 영역. 원인에 따라 다르다 — 레시피는 원인 특정 전에는 범위를 넓게 잡지 않음.
- **사용자 결정지점 (C)**: 원인 조사 범위·방식 결정 1회. (로그 확인 후 B로 강등 가능.)
- **STOP 조건**: (e) "검증 실패"가 어떤 검증 항목인지 특정 안 됨 → 중단·보고.
- **검증**: 동일 유형 검증 통과.
- **비가역 플래그**: 없음.

#### P01 — no_result (데이터 수집 성공 → 가드 차단 → None)

- **정의**: 데이터 수집은 성공했으나 가드(예: 시군구 중복 차단)로 결과를 못 낸 상태. 현재 `auto_skipped`.
- **status별**:
  - `auto_skipped` (현재): **D** — 자동 스킵 중. 가드 조정 또는 데이터 보충 필요 시 아래.
  - 활성: **C** — 가드 조정 vs 데이터 소스 보충 결정 필요.
- **수정 의도 (목표 상태)**: 파이프라인이 유효 결과를 낼 수 있는 상태. 가드 기간을 조정하거나 데이터 소스를 보강해 발행 가능한 결과가 나오는 상태.
- **허용 범위**: 파이프라인 가드 로직·데이터 수집 설정.
- **사용자 결정지점 (C)**: 가드 조정(예: 룩백 기간 단축)인지 데이터 소스 보충인지 결정 1회. 에이전트 단독 결정 불가.
- **STOP 조건**: (e) "가드 완화/데이터 보충" 중 무엇이 필요한지 특정 안 됨 → 중단·보고.
- **검증**: 해당 블로그 발행 성공 + no_result 재발 없음.
- **비가역 플래그**: 없음. 단, 가드 로직 변경은 다른 블로그 영향 가능 → 범위 확인.

#### P06 — broken_featureimage (썸네일 404)

- **정의**: featureimage가 존재하지 않는 URL을 가리켜 썸네일이 깨지는 상태. 현재 error 등록돼 있으나 active fail 여부는 체크리스트에서 확인.
- **등급 결정트리**:
  - 썸네일 R2 존재 → **A**(batch_thumbnails.py 실행 → R2 업로드 → frontmatter 수정)
  - 원본 이미지 소실 → **B**(재업로드 판단 필요)
  - featureimage가 WordPress 전용 도메인 경로 등 구조적 문제 → **B/C**(경로 정책 확인)
- **수정 의도 (목표 상태)**: featureimage가 실제로 존재하는 R2 이미지 URL을 가리키고, 브라우저에서 200이 나오는 상태.
- **허용 범위**: 해당 포스트 frontmatter featureimage + (필요 시) 썸네일 재생성·R2 업로드.
- **사용자 결정지점 (B)**: 원본 이미지가 존재하는지, 재업로드가 필요한지 확인 1회.
- **STOP 조건**:
  - (a) featureimage 외 변경 → 중단
  - (f) 원본 이미지 삭제/변형 → 중단
  - (e) 썸네일이 왜 깨졌는지(URL 오류·R2 부재·경로 정책) 특정 안 됨 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` THUMBNAIL-01·R2-01 관련 상태 + featureimage URL HTTP 200 확인.
- **비가역 플래그**: 없음(원본 보존 전제).

#### P10 — title_blocked (제목 패턴 차단)

- **정의**: 제목이 특정 패턴(예: 블로그/템플릿 패턴 차단)에 걸려 발행이 막힌 상태. 현재 `auto_skipped`.
- **status별**:
  - `auto_skipped` (현재): **D** — 자동 스킵 중. 패턴 조정 필요 시 아래.
  - 활성: **B** — 제목 패턴을 어떻게 조정할지 결정.
  - 패턴 차단 정책 자체의 변경이 필요하면 **C**.
- **수정 의도 (목표 상태)**: 제목이 차단 패턴에 걸리지 않으면서도 콘텐츠 의도를 유지하는 상태로 발행될 수 있는 상태.
- **허용 범위**: 제목 생성·차단 패턴 설정.
- **사용자 결정지점 (B/C)**: 차단 패턴을 어떻게 조정할지(패턴 완화, 제목 변형 다양화, 차단 유지 등) 결정 1회.
- **STOP 조건**: (e) "차단 패턴 조정"이 어떤 패턴을 how 바꾸는지 특정 안 됨 → 중단·보고.
- **검증**: 해당 블로그 발행 정상화 + 유사 제목 차단 재발 없음.
- **비가역 플래그**: 없음.

#### P18 — 동시 실행 방지 (하루 동시 실행)

- **정의**: 같은 날 같은 파이프라인이 중복 실행되는 것을 방지하는 로직 관련. 현재 `auto_skipped`, quiet.
- **status별**:
  - `auto_skipped`/quiet (현재): **D** — 유지. lock 강화 필요 시 아래.
  - lock 강화 필요: **B** — lock 방식을 어떻게 개선할지.
- **수정 의도 (목표 상태)**: 중복 실행이 방지되고, 필요 시에는 정상 실행되는 상태.
- **허용 범위**: 스케줄·lock 설정.
- **사용자 결정지점 (B)**: lock 방식 개선 필요 시 결정 1회. 현 상태 유지는 결정 불필요.
- **STOP 조건**: (e) "lock 강화"가 구체적 방식으로 특정 안 됨 → 중단·보고.
- **검증**: 중복 실행 방지 동작 확인.
- **비가역 플래그**: 없음.

#### leak_detected (프롬프트 릭 / CoT 누출)

- **정의**: 생성된 콘텐츠에 프롬프트 지시문·시스텀 메시지·CoT(추론) 내용 등 누출이 탐지된 상태.
- **등급 결정트리**:
  - 누출 특정 가능(어떤 프롬프트/마커가 누출) → **B**(재현 경로 확인 후 재발 방지 조치)
  - 누출 경로는 보이나 재발 방지 방법이 불명 → **C**(재Diagnosis)
  - 누출 의심만 있고 특정 안 됨 → **C**
- **수정 의도 (목표 상태)**: 생성된 콘텐츠에 프롬프트 지시문·CoT 등 내부 정보가 포함되지 않고, 재발 방지 조치가 적용된 상태.
- **허용 범위**: 프롬프트·발행 전 검증·콘텐츠 검사 영역. 콘텐츠 자체를 임의로 수정하지 말 것(누출 제거는 재발 방지 중심).
- **사용자 결정지점 (C)**: 재현 경로가 모호할 때 조사 범위 결정 1회.
- **STOP 조건**:
  - (e) "누출"이 어떤 내용인지 특정 안 됨 → 중단·보고
  - (a) 허용 범위(프롬프트·검사)를 벗어나 콘텐츠 본문을 임의 수정 → 중단
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: leak 스캔 통과 + 동일 유형 재발 없음.
- **비가역 플래그**: 없음. 단, 프롬프트 변경은 글쓰기 품질에 영향 → 변경 전 확인.

#### known_issue (등록된 known problem)

- **정의**: 대시보드에 known issue로 등록된 문제(STRUCT/QA 계열 등).
- **등급 결정트리**:
  - 재현 경로·해결책 명확 → **B**(조치 가능)
  - 불명 → **C**(Investigation 필요)
  - 백로그 이연 결정됨 → **D**
- **수정 의도 (목표 상태)**: 해당 known issue가 해소되거나, 해소 계획이 명시적으로 백로그에 등록되고 이연 사유가 기록된 상태.
- **허용 범위**: 이슈 유형별 다름 — 레시피는 이슈별 허용 범위를 개별 정의하지 않음. 해당 이슈의 evidence·action을 따른다.
- **사용자 결정지점**: 이슈별 다름. 불명 → **C**로 보고하고 사람이 조사 범위를 정함.
- **STOP 조건**:
  - (e) known issue의 목표 상태가 불명확 → 중단·보고
  - (a) 허용 범위를 벗어난 조치 → 중단
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/attention`·`/api/registry`에서 해당 issue/status 변화 확인.
- **비가역 플래그**: 이슈별 다름 — STRUCT-11/12/13 등 DB 관련은 C.4로.

#### dead_entity_link (끊긴 엔티티 링크)

- **정의**: 크로스블로그 엔티티 링크 중 404/끊긴 링크가 있는 상태.
- **등급 결정트리**:
  - 끊긴 링크 특정 가능 → **B**(교체/제거 결정)
  - 엔티티 재등록 필요 → **C**
  - 어떤 링크가 끊겼는지 탐지 불가 → **C**
- **수정 의도 (목표 상태)**: 크로스블로그 엔티티 링크가 유효한 대상(존재·접근 가능)을 가리키고, 끊긴 링크가 교체/제거된 상태.
- **허용 범위**: 엔티티 링크 정의·타겟 URL. 콘텐츠 본문 자체는 이 레시피의 직접 범위 아님(연결된 엔티티의 존재 여부가 문제).
- **사용자 결정지점 (B/C)**: 끊긴 링크를 어떻게 처리할지(교체/제거/엔티티 재등록) 결정 1회.
- **STOP 조건**:
  - (e) "끊긴 링크" 범위가 특정 안 됨 → 중단·보고
  - (a) 허용 범위(엔티티 링크)를 벗어나 콘텐츠 본문 임의 수정 → 중단
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: 엔티티 링크 검사 통과 + 404 없음.
- **비가역 플래그**: 없음(링크 교체/제거). 단, 엔티티 재등록은 콘텐츠·DB 변경 수반 가능 → 그때 별도 검토.

### C.4 🔴 비가역군 — 자동 금지 (별도 웨이브·명시 승인 필수)

아래 항목은 에이전트가 레시피를 읽더라도 **자동으로 실행하지 않는다.** 아무리 목표 상태가 명확해도, 아래 플래그가 붙은 항목은 별도의 웨이브 승인과 명시적 롤백 계획 없이는 진행하지 않는다.

| 항목 | 사유 | 필수 선행 조건 |
|------|------|---------------|
| **STRUCT-11** (idx_ledger_dedup non-unique → schema migration) | DB 인덱스 DROP+CREATE UNIQUE, 대량 INSERT OR IGNORE 영향 | 콘텐츠 DB 백업 + 롤백 태그 + 스케줄러 정지 확인 + 삭제 예정/영향 카운트 보고 + 사용자 승인 |
| **STRUCT-12** (source='' 중복 2,935건 삭제) | 실발행 행 보존 여부 등 데이터 정책 결정 필요, 대량 DELETE | 백업 + 보존 범위 결정 + 사용자 승인 |
| **STRUCT-13** (backfill_blank_titles 966건 title 덮어씀) | 발행된 title을 원본 제목으로 덮어쓴 오염 복구 — 범위·기준 결정 필요 | 백업 + 복원 범위·기준 결정 + 사용자 승인 |
| **테마 마이그레이션** (STRUCT-03 hotissue-hugo PaperMod→Blowfish / STRUCT-04 stock-hugo Congo→?) | 테마 변경은 레이아웃 전면 재작업, 대규모 변경 | 별도 웨이브 승인 + 영향 블로그 리스트 + 롤백 계획 |
| **index.html 렌더링 의존 검증** | 외부 HTTP/렌더링 결과에 의존하는 검증은 에이전트 단독 완결 불가 | 외부 상태 확인 수단 확보 또는 수동 검증 |
| **콘텐츠 재생성으로 라이브 글 덮어쓰기** | 라이브 발행 글을 파이프라인이 재작성·덮어쓰는 작업 | 별도 웨이브 승인 + 덮어쓰기 범위·대상 명시 + 롤백 계획 |
| **DB 대량 INSERT (run_sync류, 소스 전체 재삽입)** | 이미 발생한 STRUCT-11 류의 재발 가능 | 백업 + 영향 카운트 + 스케줄러 정지 + 사용자 승인 |

> 공통 규칙: 비가역군이 "해체"되려면, 해당 항목을 담당하는 별도 웨이브에서 (1) 사전 카운트/영향 범위 출력, (2) 백업/롤백 수단 확보, (3) 사용자 승인, (4) 사후 대조를 모두 거친 뒤에야 실행 가능하다. 이 레시피북의 그 어떤 A/B 등급 레시피도 위 항목을 우회하지 않는다.

### C.4.1 재검사 트리거 — 수동 갱신 전제 (공통)

> 2026-08-08 추가. 대시보드에 자동 재검사 스케줄이 없어, FIX·배포 후 화면이 갱신되려면 반드시 수동 호출이 필요하다.

- **대시보드 상태**: 현재 Ops 대시보드(`http://localhost:5060`)에는 자동 재검사 스케줄이 없다. 코드 수정·배포 후 `/api/registry`·`/api/attention`·블로그 상세 페이지의 check_results는 **자동으로 갱신되지 않는다.**
- **필수 수동 호출**:
  - 개별 블로그 FIX 후: `POST /api/run-checks?blog_id={blog_id}` — curl 또는 HTTP 클라이언트. 반환 직후 check_results 갱신.
  - 정비 체크리스트(M01~M10) FIX 후: `POST /api/maintenance/checklist` + JSON body `{"blog_id":"{blog_id}"}`.
  - 전체 재검사: `POST /api/run-checks` (blog_id 없이).
- **경고**: 이 호출 없이는 FAIL→PASS를 확인할 수 없다. "배포했으니 잠시 후 화면이 갱신되길 기다린다"는 계획은 STOP 조건 (e)에 해당. 에이전트는 재검사를 명시적으로 직접 호출해야 하고, 호출 전까지 화면 상태를 "확정된 것"으로 취급하지 않는다.
- **UI 부재**: 현재 Ops 대시보드 화면에는 위 세 API를 트리거하는 버튼·폼·JS가 없다. "마스터 갱신 버튼"은 존재하지 않음 — curl로만 호출 가능. UI 버튼 추가는 별도 작업(추가 지점: `ops_dashboard/templates/index.html`에 전체 재검사 폼, `blog.html`에 개별 재검사·정비용 fetch JS 버튼).
- **재검사 트리거 후 검증**: 호출 직후 `/api/registry`에서 해당 rule_id status가 `"fail"` → `"pass"` 또는 `"unknown"`으로 전환됐는지 확인. FAIL→PASS 확인 없이 완료 보고 금지.

### C.5 매뉴얼 시뮬레이션 증명 (문서화 목적, 실제 수정 없음)

> 아래 2건은 이 Appendix C를 완성한 뒤, 레시피만 읽고 "실제 수정 없이" 계획 생성→STOP 대조까지 수행한 기록이다. 실행 에이전트가 블로그 구조를 읽고 생성할 계획이, 이 레시피의 경계 안에서 안전하게 나오는지와, 애매한 지점에서 제대로 멈추는지를 확인한다.

#### 시뮬레이션 1 — R06, pet-hugo (active fail 1건)

- **레시피**: C.2 R06
- **입력 evidence(실제)**: `"in-article.html: missing fluid format, missing in-article format, data-ad-format=auto (prohibited)"`
- **등급 판정**: 
  - 기본등급 B (deferred). 
  - 조건부 분기 평가: "auto→fluid 교체만으로 충분, 슬롯 정책 이슈 없음"인지 불명 → B 유지. 
  - 이유: data-ad-format=auto가 문제인 것은 특정되나, AdSense 계정에서 해당 슬롯이 fluid/in-article을 허용하는지, 기존 auto 슬롯을 유지할지 삭제할지 확인이 필요할 수 있음. 레시피는 "일괄 처리 전 승인 1회"를 요구.
  - → 등급: **B**. 사용자 결정지점 1개: "pet-hugo 포함 19개 블로그 in-article.html을 일괄 fluid로 교체 진행 승인?"
- **목표 상태 서술**: pet-hugo의 `layouts/partials/adsense/in-article.html`에서 `data-ad-format="auto"`가 제거되고 `data-ad-format="fluid"` + `data-ad-layout="in-article"`이 설정되며, `<script>push({})</script>`가 `<ins>` 태그 바깥에 위치하는 상태.
- **예상 변경 계획 (블로그 구조 읽은 뒤 생성)**:
  1. 대상 파일: `pet-hugo/layouts/partials/adsense/in-article.html` (1파일)
  2. 변경:
     - `data-ad-format="auto"` → `data-ad-format="fluid"` 및 `data-ad-layout="in-article"` 추가
     - `<script>push({})</script>`가 `<ins ...>...</ins>` 내부에 있으면 외부로 이동
  3. 예상 규모: 1파일, 소폭 수정(속성 교체 + 요소 위치 이동)
- **STOP 조건 대조**:
  - (a) 허용 범위[in-article.html만] 준수? 예 — 1파일만. 통과.
  - (b) 예상 규모(1파일) 초과? 아니오 — 1파일 기대, 1파일 계획. 통과.
  - (c) 빌드 에러? 계획 단계에선 미확정 — 게이트에서 Hugo 빌드 0에러로 확인 예정. 계획 자체론 STOP 아님.
  - (d) /api/registry 총량·분포 이상 변화? R06만 fail→pass 예상, 인접 R05·R11·R12 무영향 예상. 통과(예상으로는).
  - (e) 목표 상태가 evidence로 명확? 예 — "missing fluid, missing in-article, data-ad-format=auto" 3가지가 evidence로 특정되며, 목표 상태(fluid+in-article+push 밖)가 그 부정형을 해소함. 통과.
  - (f) 비가역 작업? 아니오 — 파일 내용 수정, 삭제 아님. 통과.
- **결과**: STOP 조건 걸리지 않음. **계획 안전.** 단, B등급이므로 실행 전 사용자 승인 1회 필요. 승인 있으면 게이트(백업→빌드→배포→재검증)로 진행.

#### 시뮬레이션 2 — R2-01, techpawz-hugo (active fail, 7건)

- **레시피**: C.2 R2-01
- **입력 evidence(실제)**: `"R2 패턴 위반 7건 / 검사 7건: 킹스데일cc-20260808-s3/featureimage: https://img.techpawz.com/...; ... (R2 아님) 외 4건"` — featureimage 3건 + 본문 이미지 4건이 비R2.
- **등급 판정**:
  - 기본등급 B.
  - 조건부 분기 평가: 
    - "모든 이미지 URL이 R2" 아님 → fail 상태.
    - "원본 R2 존재 여부" 미확인 → B 유지. 
    - featureimage만 위반 아님(본문 이미지도 4건) → 영향 범위 확대. 일괄 치환 필요 시 결정지점.
  - 이유: URL만 보고는 원본이 R2에 업로드돼 있는지 알 수 없음. evidence상 img.techpawz.com 도메인이므로 현재 R2 아님. R2에 재업로드 필요 가능성 있음 → B.
  - → 등급: **B**. 사용자 결정지점 1개: "7건 이미지(킹스데일cc·코스터cc·bmw모델·기타)의 원본이 R2에 이미 존재하는가? 없으면 재업로드 필요한가?"
- **목표 상태 서술**: techpawz-hugo의 해당 포스트(킹스데일cc-20260808-s3, 코스터cc-..., bmw모델-..., 기타)들의 featureimage와 본문 이미지 URL이 `pub-<hash>.r2.dev` 도메인의 webp URL로 치환된 상태. 원본 이미지는 보존됨(삭제·변형 없음).
- **예상 변경 계획 (블로그 구조 읽은 뒤 생성)**:
  1. 대상 포스트들: 해당 7건의 featureimage가 걸린 포스트 각각의 `content/posts/<slug>/index.md` + 해당 포스트 본문 Markdown (이미지 URL 7건).
  2. 변경:
     - 각 포스트 frontmatter `featureimage`를 R2 URL로 치환 (R2에 원본이 존재한다고 가정 시).
     - 본문 내 `![...](img.techpawz.com/...)` / `<img src="img.techpawz.com/...">`도 R2 URL로 치환.
  3. 예상 규모: 포스트 수 N개, 이미지 URL 7건 치환. (정확한 포스트 수·이미지 위치는 블로그 구조 확인 시 결정.)
  4. 전제조건: R2에 원본 이미지가 존재. 없으면 재업로드(batch_thumbnails.py 등)가 선행되어야 함 → 이건 이 계획의 전제, 충족되지 않으면 계획 중단·보고.
- **STOP 조건 대조**:
  - (a) 허용 범위[해당 포스트의 featureimage + 본문 이미지 URL만] 준수? 예 — 다른 포스트·레이아웃·config 건드리지 않음. 통과.
  - (b) 예상 규모 초과? evidence상 7건 특정됨. 계획은 7건 치환 지향. 실제 블로그 구조에서 7건이 맞는지 확인 필요 — 맞으면 통과, 초과면 중단·보고.
  - (c) 빌드 에러? URL 문자열 치환이므로 Hugo 빌드 에러 가능성 낮음 — 게이트에서 확인. 계획 자체론 STOP 아님.
  - (d) /api/registry 총량·분포 이상 변화? R2-01 fail→pass 예상, THUMBNAIL-01도 연관돼 동반 통과 가능. 인접 R06 등 무영향 예상. 통과(예상으로는).
  - (e) 목표 상태가 evidence로 명확? 예 — "7건 이미지가 비R2" + 목표는 "모두 R2". 통과. 단, "본문 이미지" 범위가 특정되는지는 블로그 구조에서 확인 — `![...](...)`·`<img src>`로 한정하며, 그 외 애매하면 정지.
  - (f) 비가역 작업? 아니오 — URL 치환, 원본 보존 전제. 통과. 단, 원본 이미지를 삭제/변환하는 행위가 계획에 섞이면 즉시 STOP.
- **전제조건 실패 시 STOP**: R2에 원본 이미지가 없으면, 이 계획은 "URL 치환"만으로 목표 상태에 도달할 수 없음. 이때는 계획을 중단하고 사용자에게 보고: "7건 중 N건의 원본이 R2에 없음 — 재업로드 필요. 재업로드 진행 승인?" 이 지점에서 멈춘다.
- **결과**: 원본 R2 존재가 확인되면 STOP 없이 진행 가능(규모·범위 재확인 조건). 확인되지 않으면 B 유지, 사용자에게 원본 존재 여부 결정 1회 요청. 계획은 레시피 경계 안에서 생성되며, 애매한 지점(전제조건 불충족)에서 제대로 멈춘다.

---

### C.6 콘텐츠 무결성 검사(C01~C09) 및 정비 체크리스트 레시피

> 추가일: 2026-08-09 | 상태: 활성 | 출처: `ops_dashboard/checks/content_integrity.py`, `ops_dashboard/checks/maintenance.py` 판정 로직 확인 기반.
> 적용 우선순위: c06_mtime_deploy(22건) > c05_draft_publish(14건) > maintenance_checklist M01~M11(7건).
> 나머지 C-계열(gsd_crosscheck, freshness)은 판정 로직 확인·분류만 수록하고 레시피 초안은 선택(🔽 참고). c03_fm_key_leak·c04_prompt_leak은 위 C.6에 정식 등재됨.

#### C06 — 로컬 파일 수정 시각 검사 (c06_mtime_deploy) — INFO 등급 (참고용)

- **정의**: 최근 1일(24시간) 이내 수정된 포스트 파일이 존재하면 checker는 fail(현재 코드 기준)을 반환한다. check_name은 "c06_mtime_deploy"이나, 현재 구현(`_check_c06`, `ops_dashboard/checks/content_integrity.py:152-160`)은 배포 시각과의 비교가 아니라 파일 mtime이 1일 이내인지 여부만 판정한다.
- **INFO 등급 확정**: 현재 c06은 fail/위반이 아니라 참고용 INFO 신호로만 취급한다. `_check_c06()`이 반환하는 "C06 경고" 문자열 자체가 "위반"보다 약한 표현이며, 최근 수정은 대부분 정상 작업(이미지 교체, frontmatter 수정, 콘텐츠 보강 등)의 흔적이다. "배포 시각 vs mtime" 비교가 아니라 "최근 24시간 내 수정" 여부만 보기 때문에, deploy 후 파일이 변조됐는지 감지하는 체크가 아니다.
- **fail 판정 근거 (evidence)**:
  - `_check_c06()`: 파일 mtime이 1일 이내면 `False, f"C06 경고: 최근 수정 ({mtime.strftime('%Y-%m-%d')})"` 반환.
  - check_c06 전체 결과: `"C06 경고 N건: C06 경고: 최근 수정 (YYYY-MM-DD); ..."` (`ops_dashboard/checks/content_integrity.py:360-361`).
  - **"C06 경고" 문자열 사용** — "위반"보다 약한 표현으로, 경고 수준임을 시사.
- **등급**: **INFO (참고용)** — fail로 취급하지 않으며, 등급 계산·주의필요(fail_checks) 표에서 제외 대상. 가장 얕은 신호.
- **조치 방침**: 기본적으로 조치 불필요. 최근 수정은 대부분 정상 작업의 흔적이다. 예외로, "수정됐을 리 없는 파일"(예: 배포 직후 단시간 내 대형 포스트가 mtime 갱신됨, 또는 정상 파이프라인 외부에서 Touch된 파일)이 c06에 뜨면 그때만 변조 여부를 읽기전용으로 조사하고, **자동 수정 금지**. 실제 변조가 확인돼도 자동 삭제·원복하지 않고 보고 후 사람 판단.
- **조치 대상 파일**: 해당 블로그의 `content/posts/<slug>/index.md` (최근 7일 내 포스트 중 mtime 1일 이내인 파일) — 단, INFO 등급이므로 "fail 대응 대상"이 아니라 "참고 확인 대상".
- **STOP 조건**:
  - 코드·DB·블로그 파일 수정, 재배포, 체크 로직 변경을 수반하는 계획은 즉시 중단·보고 (이번 작업은 AGENTS.md 문서 편집으로 한정).
  - "수정됐을 리 없는 파일"이 c06에 뜬 경우 → 읽기전용 조사(mtime 비교, 어떤 프로세스가 Touch했는지, git diff 등)까지만. 변조 확인돼도 자동 원복 금지.
  - **(e) 재검사 트리거 호출이나 대시보드 반영(코드 변경)을 하려는 계획** → 중단. 이번 작업은 AGENTS.md 문서 편집으로 한정, 대시보드 표시 로직 변경은 별도 웨이브에서.
- **비가역 플래그**: 없음 (INFO 등급, 자동 조치 없음). 단, 추후 "무시/참고 처리"를 체크 로직 수준에서 구현하려면 그 자체는 별도 코드 변경으로, 이번 범위 밖.
- **대시보드 표시에 대한 메모 (TODO, 이번엔 구현 안 함)**:
  - c06은 fail이 아닌 INFO/참고 버킷으로 표시하는 것이 바람직하며, 등급 계산·주의필요(fail_checks) 표에서 제외 대상.
  - 별도 웨이브에서 대시보드 반영 예정: `ops_dashboard/checks/content_integrity.py`의 `_check_c06` 반환값을 pass/info로 조정하거나, c06을 fail_checks가 아닌 별도 참고 통계로 분리. (TODO — 이번 세션 미시행)

#### C05 — draft:true 발행 감지 (c05_draft_publish)

- **정의**: 발행된 포스트의 frontmatter에 `draft: true`(대소문자 무관)가 남아 있는 상태. draft:true 포스트는 발행 대상에서 제외되어야 하나 실제 발행된 경우 감지.
- **fail 판정 근거 (evidence)**:
  - `_check_c05()` (`ops_dashboard/checks/content_integrity.py:145-149`): `fm.get("draft", "").lower() == "true"` → `False, "C05 위반: draft:true 발행 대상"`.
  - check_c05 전체 결과: `"C05 위반 N건: <slug>: C05 위반: draft:true 발행 대상; ..."` (`ops_dashboard/checks/content_integrity.py:337-338`).
- **조치 대상 파일**: 해당 블로그의 `content/posts/<slug>/index.md` (draft:true가 적발된 포스트 각각의 frontmatter)
- **조치 내용**:
  - frontmatter의 `draft: true`를 `draft: false`로 변경(또는 `draft: true` 라인 제거).
  - 주의: 이미 발행된 포스트의 frontmatter 수정이므로 수정 후 재배포 필요.
  - draft:true를 그대로 두는 것은 정책 위반 상태이므로 방치 불가.
  - **P09 false positive 수정(2026-08-09, BUG-P09-001)과의 관계**: 무관. P09 수정은 `detect_post_generate`가 본문 전체가 아닌 개별 이미지 URL만 검사하도록 변경한 것(`shared/problem_detectors.py`); c05는 frontmatter draft 플래그 검사로 서로 독립적.
- **등급 결정트리**:
  - draft:true 삭제 + 재배포 → **B**(파일 수정 + 재배포, 판단 1회)
- **사용자 결정지점**: 없음 (B등급이나 조치는 명확 — draft:true 제거 + 재배포).
- **STOP 조건**:
  - (a) 조치 범위가 해당 포스트의 draft 필드 변경으로만 한정되는지 확인. 다른 필드·다른 포스트까지 번지면 중단.
  - (f) 조치 과정에서 원본 콘텐츠 본문이 삭제/변형되지 않도록 주의 (frontmatter만 수정).
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증 방법**: 조치 후 `POST /api/run-checks?blog_id={blog_id}` → c05_draft_publish status가 pass로 전환 확인.
- **비가역 플래그**: 없음 (draft 플래그 변경 + 재배포, 본문 보존 전제).

#### C03 — 프론트매터 키 본문 유출 (c03_fm_key_leak)

- **정의**: 포스트 본문(프론트매터 이후)에 프론트매터 키 형식의 라인(title:, og_image:, featureimage:, date:, slug:, categories:, tags:, description:, draft:, image:, pubDate:, author: 등)이 노출되어 있는 상태. 프론트매터 영역이 아닌 본문에 이런 라인이 있으면 파싱 오류나 표시 문제의 원인이 될 수 있음.
- **fail 판정 근거 (evidence)**:
  - `_check_c03()` (`ops_dashboard/checks/content_integrity.py:123-129`): 본문에 `^\s*(FM_KEYS):\s*` 정규식이 매치되는 라인이 있으면 fail. FM_KEYS = ["title", "og_image", "featureimage", "date", "slug", "categories", "tags", "description", "draft", "image", "pubDate", "author"].
  - fail 증거: `"C03 위반: N건 — leaked_line"` (예: `"C03 위반: 2건 — title: 서울 맛집 top5"`).
  - check_c03 전체 결과: `"C03 위반 {len(violations)}건: {slug}: {detail}; ..."` (`ops_dashboard/checks/content_integrity.py:285-287`).
- **조치 대상 파일**: 해당 블로그의 `content/posts/<slug>/index.md` (본문 내 앞머터 키 라인 노출이 적발된 포스트)
- **조치 내용**:
  - 본문에서 앞머터 키 형식의 라인 제거. 대부분 다음과 같은 원인:
    - LLM이 본문 첫 부분에 프론트매터 복사본을 실수로 생성
    - 앞머터에 넣어야 할 필드를 본문에 적어넣음
    - 이미지 URL이나 제목이 본문 상단에 중복 기재됨
  - 제거 시 본문 내용(실제 글 텍스트)은 보존하고, 키가 노출된 라인만 삭제.
  - 제거 후 재배포 필요 (Hugo 빌드 시 frontmatter 이후 본문 출력).
- **등급**: **B** — 본문에서 노출 라인 제거 + 재배포. 어느 라인이 키 노출인지 개별 확인 1회 필요하나 조치는 명확.
- **사용자 결정지점**: 없음 (B등급이나 조치는 명확 — 노출 라인 제거 + 재배포). 단, 제거 대상 라인이 본문 내용인지 앞머터 키 유출인지 애매하면 판단 1회.
- **STOP 조건**:
  - (a) 조치 범위가 해당 포스트의 본문 내 키 노출 라인 제거로 한정되는지 확인. 다른 포스트·다른 필드까지 번지면 중단.
  - (f) 조치 과정에서 원본 콘텐츠 본문이 삭제/변형되지 않도록 주의 (키 노출 라인만 제거).
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증 방법**: 조치 후 `POST /api/run-checks?blog_id={blog_id}` → c03_fm_key_leak status가 pass로 전환 확인.
- **비가역 플래그**: 없음 (본문 중 키 노출 라인 제거, 본문 내용 보존 전제). 단, 제거 대상이 실제 본문 내용인데 키 노출로 오판한 경우 복원 필요 → 제거 전 해당 라인 보존(복사) 권고.

#### C04 — LLM 프롬프트/사고문 누수 (c04_prompt_leak)

- **정의**: 포스트 본문에 LLM 프롬프트 지시문·사고Chain-of-Thought 마커·시스템 메시지 등 내부 정보가 국문·영문 패턴으로 포함된 상태. 예: "생각해보자", "다음 단계로 넘어", "We need to write", "Let's think step by step" 등.
- **fail 판정 근거 (evidence)**:
  - `_check_c04()` (`ops_dashboard/checks/content_integrity.py:132-142`): C04_KO_PATTERNS + C04_EN_PATTERNS 목록으로 본문 검사. 매치되면 fail.
  - C04_KO_PATTERNS (10개): `생각해보자`, `생각해 보자`, `다음 단계로 넘어`, `단계별로 진행해`, `우선, 우리가 해야`, `우리가 해야 할 것은`, `생각 과정을 통해`, `결론부터 말하면`, `먼저 생각해보자`, `단계별로 생각`.
  - C04_EN_PATTERNS (8개): `Need to think`, `We need to write`, `Let's think step by step`, `think step by step`, `let's break this down`, `here's the plan`, `in order to achieve`, `as an AI language model`. (2026-08-12: firstly/secondly는 오탐 이력으로 제거 — `\bfirstly,?\s+`와 `\b secondly,?\s+`의 `\b` 뒤 공백 오타로 인해 " secondly,"만 잡고 "secondly," 단독은 못 잡는 문제 + 실발행 글에 이 패턴이 실제와 무관하게 검출되는 오탐 빈발)
  - fail 증거: `"C04 위반: 프롬프트 누수 N건 — matched_text"` (예: `"C04 위반: 프롬프트 누수 1건 — 생각해보자"`).
  - check_c04 전체 결과: `"C04 위반 {len(violations)}건: {slug}: {detail}; ..."` (`ops_dashboard/checks/content_integrity.py:302-304`).
  - **leak_detected(C.3)와의 관계**: C04는 "프롬프트/사고문 누수"라는 문제 유형에서 C.3의 leak_detected와 동일 계열. C.3 leak_detected 레시피의 "수정 의도·허용 범위"를 공유한다. C04는 dashboard에서 별도 check_name으로 감지되는 구체적 검사.
- **조치 대상 파일**: 해당 블로그의 `content/posts/<slug>/index.md` (본문 내 누수 패턴 적발 포스트)
- **조치 내용**:
  - 본문에서 누수 패턴 제거 (누수 라인/문장 삭제 또는 자연어로 재작성).
  - 주의: 누수 제거는 재발 방지 중심. 프롬프트·방지 로직도 함께 점검 필요.
  - 누수 패턴 제거 후 재배포 필요.
  - **C.3 leak_detected 레시피 참조**: 허용 범위·비가역 플래그 등 공통 원칙은 C.3 leak_detected 레시피를 따른다. 여기선 check_name별 구체적 판정 로직만 추가 기술.
- **등급**: **B** — 본문 누수 패턴 제거 + 재배포 + 프롬프트 점검. 어느 패턴이 누수인지 개별 확인 필요하나 조치는 명확.
- **사용자 결정지점**: 없음 (B등급이나 조치는 명확 — 누수 패턴 제거 + 재배포 + 프롬프트 점검). 단, 누수 패턴이 프롬프트 지시문인지 실제 콘텐츠인지 불명하면 판단 1회.
- **STOP 조건**:
  - (a) 조치 범위가 해당 포스트의 본문 내 누수 패턴 제거로 한정되는지 확인. 다른 포스트·다른 영역까지 번지면 중단.
  - (a) 허용 범위(프롬프트·검사)를 벗어나 콘텐츠 본문을 임의 수정 → 중단. 누수 제거만 허용.
  - (e) "누출"이 어떤 내용인지 특정 안 됨 → 중단·보고.
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증 방법**: 조치 후 `POST /api/run-checks?blog_id={blog_id}` → c04_prompt_leak status가 pass로 전환 확인.
- **비가역 플래그**: 없음 (본문 중 누수 패턴 제거·재작성, 본문 의도 보존 전제). 단, 프롬프트 변경은 글쓰기 품질에 영향 → 변경 전 확인.

#### maintenance_checklist (M01~M11 정비 체크리스트)

- **정의**: 블로그 정비 대상 블로그(maintenance_status != 'none')에 대해 M01~M11 정비 항목을 일괄 실행하고 전체 통과 여부를 판정. maintenance_checklist 자체가 fail이면 하나 이상의 M-항목이 fail 상태. 현재 7건이 fail (M01~M11 중 하나 이상이 실패한 블로그 7개).
- **fail 판정 근거 (evidence)**:
  - `check_maintenance_checklist()` (`ops_dashboard/checks/maintenance.py:504-567`): MAINTENANCE_CHECKS(M01~M11) 순회 실행 → fail 있으면 `"M-체크리스트: N/M 통과, K개 실패"`, 전체 통과면 `"M-체크리스트: 전체 11항목 통과 — 재개 준비 완료"`.
  - 개별 M-항목 fail은 `set_check_item_status()`로 DB(`maintenance_checklist_items` 테이블)에 기록됨.
- **조치 대상**: fail된 개별 M-항목 (maintenance_checklist_items 테이블에서 blog_id별 체크 항목별 status 확인 가능).
- **M01~M11 각 항목 판정 로직·조치 요약** (판정 로직 출처: `ops_dashboard/checks/maintenance.py`):
  - **M01** (제목 CJK 없음, `_check_cjk_in_title` L30-71): 최근 20개 발행 제목에 한자(\u4e00-\u9fff)·히라가나(\u3040-\u309f)·가타카나(\u30a0-\u30ff) 포함 시 fail. 조치: 제목 재생성(CJK 제거) → **콘텐츠 재생성 수반, 🔴 별도 웨이브 승인 필요.**
  - **M02** (이미지 정상, `_check_image_repetition` L153-198): 최근 20개 포스트 featureimage 중 동일 URL 3회 이상 반복 시 fail. 조치: 중복 이미지 사용 포스트의 featureimage 변경 → **content 수정.**
  - **M03** (크로스링크 주제 일관, `_check_crosslink_relevance` L204-206): `check_crosslink_consistency` 실행, fail 시 크로스링크 관련 조치. 조치: 크로스링크 검토·수정이 필요하면 content 수정. [crosslink.py 상세 참조]
  - **M04** (본문 품질 게이트, `_check_content_quality` L209-225): known_issues에서 issue_id가 Q로 시작하고 open 상태인 이슈 존재 시 fail. 조치: 해당 Q 이슈 해결 → **이슈 종류별 조치 상이.**
  - **M05** (표준 준수, `_check_standard_compliance` L228-239): 최신 standard_compliance check_results가 fail이면 fail. 조치: R01~R12 각 규칙별 조치 → **Appendix C.2 레시피로 위임 (이미 존재).**
  - **M06** (키워드 잔량 충분, `_check_keyword_availability` L242-327): defined 키워드 - published_products 사용 < 24개(남은 키워드)면 fail. 조치: keywords.py/KEYWORD_MAP에 키워드 추가 또는 publish_products 정산 → **키워드 관리.**
  - **M07** (P03 유사제목 안전, `_check_similar_title_safety` L330-357): 최근 7일 내 similar_title 차단 발생(content.db publish_ledger) 시 fail. 조치: 차단 원인 조사·제목 패턴 조정 → **P10(title_blocked) 레시피 참조 가능.**
  - **M08** (CoT/프롬프트 누수 없음, `_check_cot_leak` L360-372): known_issues에서 P07/P08이 open 상태면 fail. 조치: 누수 이슈 해결 → **leak_detected 레시피(C.3) 참조.**
  - **M09** (publish_log 기록 정상, `_check_publish_log_integrity` L375-457): content.db publish_ledger 발행 건수 > 0이나 모든 소스 DB(curation.db, stap_content.db, car.db, stock.db, rap.db 등) 로그 0건이면 fail. 조치: 소스 DB 로그 기록 누락 원인 조사·수정 → **파이프라인 로그 설정 점검.**
  - **M10** (도메인 가용성, `_check_domain_health` L460-482): 도메인 HTTP HEAD가 200-399 범위 아니면 fail, 연결 실패도 fail. 조치: 도메인 상태·배포 확인 → **인프라 점검.**
    - M10 도메인 이상 시: 도메인 HEAD 200 확인 실패면 → 배포 상태 확인 (`wrangler pages deployment list {blog_id}`), DNS 설정 확인, 서버/Cloudflare 상태 확인. 코드/콘텐츠 수정 범위 아님.
  - **M11** (본문·슬러그 CJK 없음, `_check_cjk_in_body_and_slug` L74-150): 최근 20개 포스트 본문 또는 슬러그(디렉토리명)에 한자·히라가나·가타카나 포함 시 fail. 조치: 본문/슬러그 재생성(CJK 제거) → **콘텐츠 재생성 수반, 🔴 별도 웨이브 승인 필요.**
- **등급 결정트리** (전체 maintenance_checklist):
  - 개별 M-항목 fail → 해당 항목 조치로 해결 → `POST /api/maintenance/checklist` (JSON body `{"blog_id": "{blog_id}"}`) 재실행 → 전체 pass 전환 → resume_ready = True.
  - M01/M11(콘텐츠 본문·제목 재생성), M02(콘텐츠 수정) 등 콘텐츠 변경이 필요한 항목은 비가역적 변경 수반 가능 → **🔴 별도 웨이브 승인 필요.**
- **사용자 결정지점**: M01/M11 등 콘텐츠 본문·제목 재생성이 필요한 항목의 조치 범위와 방식 결정 시.
- **STOP 조건**:
  - (f) M01/M11 조치 계획에 콘텐츠 본문·제목 삭제/재생성이 포함 → 재생성 범위·대상 명시한 별도 웨이브 승인 필요. 자동 금지.
  - (a) maintenance_checklist 외 파일·DB 수정으로 번지면 중단.
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 조치 후 반드시 `POST /api/maintenance/checklist` ({blog_id} 대상) 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증 방법**: 개별 M-항목 조치 후 `POST /api/maintenance/checklist` (JSON body `{"blog_id": "{blog_id}"}`) 재실행 → maintenance_checklist status가 pass로 전환 + resume_ready = True 확인.
- **비가역 플래그**: M01/M11(콘텐츠 본문·제목 재생성)은 🔴 별도 웨이브·명시 승인 필요. M02~M10은 조치 내용에 따라 다름(대부분 콘텐츠 수정·설정 변경·인프라 점검 수준, 본문 삭제/변형 없는 범위에서 처리 가능).

---

#### C-계열 기타 검사 — 판정 로직 확인·분류만 (레시피 초안 선택)

아래 C-계열 검사들은 현재 fail 발생하고 있으나, 이번 룩북 추가에서는 판정 로직 확인·분류만 수행하고 레시피 초안은 선택(필요 시 별도 세션에서 작성).

| check_name | fail 건수 | 판정 로직 요약 | 분류 |
|------------|----------|--------------|------|
| **gsd_crosscheck** | 3건 | `check_crosscheck()` (`ops_dashboard/checks/crosscheck.py:19-58`): auto_detectable 이슈가 있으나 해당 블로그의 fail check_results가 없으면 fail. **메타 검사**(다른 체크가 이슈를 제대로 catch했는지 검증). 조치: 근본은 각 auto_detectable 이슈에 대한 개별 체크가 fail을 내도록 하는 것 — gsd_crosscheck 자체보다 해당 이슈의 담당 체크를 정비. **별도 레시피 불필요(메타 검사).** |
| **c03_fm_key_leak** | 3건 | `_check_c03()` (`ops_dashboard/checks/content_integrity.py:123-129`): 본문(프론트매터 이후)에 FM_KEYS(title, og_image, featureimage, date, slug 등) 라인이 regex로 검출되면 fail. 증거: `"C03 위반: N건 — leaked_line"`. 조치: 본문에서 frontmatter 키 형식의 라인 제거 → **content 수정(경미).** 레시피: **위 C.6 C03 참조 (정식 등재).** |
| **c04_prompt_leak** | 1건 | `_check_c04()` (`ops_dashboard/checks/content_integrity.py:132-142`): C04_KO_PATTERNS + C04_EN_PATTERNS(국문·영문 LLM 프롬프트/사고문 패턴)으로 본문 검사, 검출 시 fail. 증거: `"C04 위반: 프롬프트 누수 N건 — matched_text"`. P08/P07(leak_detected)과 밀접. 조치: 본문에서 누수 패턴 제거 + 프롬프트/방지 로직 점검 → **leak_detected 레시피(C.3) 참조, 본문 수정은 별도.** 레시피: **위 C.6 C04 참조 (정식 등재).** |
| **freshness** | 1건 | `check_freshness()` (`ops_dashboard/checks/freshness.py:27-69`): 계열별 stale 기준(cuap=1일, etap/tap/stap/cap/rap/seap=7일, manual=30일) 대비 마지막 성공 발행 후 경과일 초과 시 fail. 조치: 해당 블로그 신규 발행 → **파이프라인 정상 발행으로 해소, 별도 FIX 레시피 불필요(설계상 정상).** |

> 참고: freshness는 "조치가 파이프라인 정상 발행"이라는 점에서 FIX 레시피북의 "코드 수정·콘텐츠 수정" 유형과 성격이 다름. freshness fail은 파이프라인을 정상 가동하면 자동 해소되므로 레시피북에 등재하지 않음.
>
> **freshness 발생 시 확인할 항목 (체크리스트 — 수정 레시피 아님, 운영 액션):**
> - 스케줄러 실행 중인가? (`ps aux | grep scheduler.py`)
> - 해당 블로그 daily_quota 소진됐는가? (`config/blogs.d/*.yaml`)
> - 데이터 소스 고갈? (festival.db, course.db, tap.db content_pool 잔여량)
> - blocked 사유? (P01 no_result, P14 keyword 소진, P17 daily 소진 등)
> - 파이프라인 정상 동작? (`logs/` 최근 오류, dispatcher.log)

---

## Appendix D — Fleet 확장(온보딩) 런북

> 목적: 5000 대시보드에 새 블로그·새 분기를 추가할 때, 코드 구조를 읽지 않고도 안전하게 등록·검증할 수 있는 표준 절차. Appendix C와 동일한 "의도·경계형" 철학 — 정확한 명령은 실행 시점 생성, 목표 상태·허용 범위·STOP 조건만 못 박음.

---

### D.0 등급 요약표

| 작업 | 기본등급 | 조건부 분기 | 사용자 결정지점 |
|------|---------|-----------|--------------|
| 신규 블로그 추가 (active) | A | blog_id 중복·domain 중복 → B(중지·확인) / site_path 실존 확인 불가 → B | 도메인·blog_id 중복 의심 시 1회 |
| 신규 블로그 추가 (inactive/paused) | A | 위와 동일 | 위와 동일 |
| 신규 brand(YAML 파일) 추가 | A | brand명 충돌 → B(중지) / _detect_brand 패턴 불일치 → B | brand명 충돌 시 1회 |
| 신규 pipeline 추가 (코드 처리 필요) | B | pipeline 유형이 기존 STAP_PIPELINE_MAP/CAP_BLOGS 패턴이면 A에 가까움 / 완전 신규 파이프라인이면 B→C | dispatcher 분기 로직 필요 여부 확인 1회 |
| 기존 blog의 brand/pipeline 재분류 | 🔴 비가역 | — | 별도 웨이브 승인 필수 |

---

### D.1 시나리오 1 — 신규 블로그 추가

#### 필요 입력 (사용자 제공 — 하나라도 없으면 STOP)

| 입력값 | 예시 | 필수 여부 | 누락 시 |
|--------|------|----------|---------|
| `blog_id` | `test-hugo` | 필수 | 등록할 ID 없음 → 중단 |
| `brand` (YAML 파일명 유래) | `cuap` | 권장 (파일 선택으로 결정) | 몰르면 `config/blogs.d/testbrand.yaml` 생성 → brand=testbrand |
| `pipeline` | `curation` | 필수 | dispatcher 분기 로직 적용 불가 → B |
| `domain` | `test.informationhot.kr` | 필수 (현실적) | 도메인 없거나 중복 시 B |
| `theme` | `blowfish` | 권장 | 없으면 `theme=''` (표준 검사 R09 등에서 unknown 가능) |
| `site_path` (Hugo 소스 디렉토리) | `/Users/twinssn/Projects/cuap/test-hugo` | 필수 | 없으면 Hugo 빌드·배포 불가 |
| `status` | `active` 또는 `paused` | 필수 | 기본값 없음 → 명시 필요 |
| `daily_quota` | `5` | 권장 | 미지정 시 발행 빈도 통제 불가 |

**STOP-1:** 위 표 필수 입력 중 하나라도 비어 있으면 진행 중단. 사용자에게 나머지를 요청.

#### 등록 순서 (의도)

**목표 상태: 새 blog_id가 `/api/fleet`에 1건으로 뜨고, 표준 검사(R01~R14) 대상에 자동 편입되며, dispatcher가 blog_id→site_path 매핑을 아는 상태.**

1. **YAML 파일 생성** — `config/blogs.d/{brand}.yaml`에 새 블로그 엔트리 추가. 기존 파일이 있으면 그 아래에 `- id: ...` 블록 추가, 없으면 새 파일 생성. YAML 포맷은 기존 엔트리 복사 (필수 필드: id, pipeline, platform, status, domain, site_path, theme, schedule.times[]).
   - 허용: 해당 brand YAML 파일만 수정.
   - 금지: 다른 brand YAML, config/blogs.yaml (블로그 정의 아님) 수정.

2. **DB 동기화** — 대시보드 서버에서 `sync_blog_lifecycle()` 실행. 방법: `POST /api/run-checks` 호출 시 내부적으로 `_ensure_db()` → `sync_blog_lifecycle()` 호출됨. 또는 `python ops_dashboard/seed.py --run-checks`.
   - 목표 상태: `blog_lifecycle`에 새 blog_id 1행 INSERT/UPDATE.
   - 검증: `SELECT * FROM blog_lifecycle WHERE blog_id='{blog_id}'` → 1행 반환, brand/pipeline/site_path 정확.

3. **검사 대상 편입 확인** — `POST /api/run-checks?blog_id={blog_id}` 실행. goal: 해당 blog_id의 check_results 행이 check_name별로 1건씩 생성됨.
   - 허용: 특정 blog_id만 재검사.
   - 금지: 전체 재검사로 다른 블로그 baseline 흔드는 행위 (필요 시에만).

4. **dispatcher 경로 매핑 확인** — dispatcher.py가 blog_id를 인식할 수 있는지. 대부분의 경우 YAML의 `site_path`가 실제 소스 경로와 일치하면 자동 매핑됨. STAP/CAP 계열이면 각각 `STAP_PIPELINE_MAP`/`CAP_BLOGS`에 등록 필요할 수 있음 (파이스라인 유형 확인).

#### 허용 범위

- ✅ 건드려도 됨: `config/blogs.d/{brand}.yaml` (해당 brand 파일만), DB 동기화, 해당 blog_id 재검사.
- ❌ 건드리면 안 됨: 기존 블로그 YAML, dispatcher.py 원본 로직, ops_dashboard/db.py 스키마, 다른 brand 파일, 스케줄러 설정.

#### 검증 게이트

- [ ] `/api/fleet` 응답에 `{blog_id}` 1건 포함 (GET /api/fleet → JSON에서 blog_id 검색)
- [ ] `/api/registry` 또는 `POST /api/run-checks?blog_id={blog_id}` → check_results에 해당 blog_id 행 생성
- [ ] baseline 증가분이 예상 범위 내: active면 check_results +N행(N=check 수 ≈15), inactive/paused면 check_results 행은 생기지만 fail_checks에는 안 들어가고 excluded_fail_checks로만 편입
- [ ] excluded 총량 증가분이 의도대로만: inactive/paused 1건 추가 시 excluded_fail_checks +0건(실패 없으면) ~ +N건(실패 있으면). active면 fail_checks 쪽으로 편입.

#### STOP 조건

- (a) **허용 범위 벗어남** — brand YAML 외 파일이 계획에 포함됨
- (b) **blog_id 중복** — 이미 `blog_lifecycle`에 동일 blog_id 존재 → 중단, 사용자에게 기존 레코드 확인 요청
- (c) **domain 중복** — 다른 블로그가 동일 domain 사용 중 → 중단, 의도 확인
- (d) **baseline 예상 외 변동** — check_results/excluded 증가분이 예측 모델 범위를 벗어남
- (e) **검사가 안 도는 반쪽 상태** — `/api/fleet`에는 뜨나 `/api/registry`나 run-checks 결과에서 해당 blog_id의 check_results가 생성 안 됨
- (f) **dispatcher 경로 매핑 실패** — site_path가 실존하지 않거나 dispatcher가 blog_id 인식 못 함 → 중단, site_path 확인

#### 고친 뒤 화면 반영

- 수동 재검사 트리거: `POST /api/run-checks?blog_id={blog_id}` → check_results 즉시 갱신 → `/api/attention`·`/blog/{blog_id}` 페이지 새로고침 시 반영.
- 대기시간: 수동 실행 시 curl 반환 직후. 자동 갱신 스케줄 없음 (갱신 지도 참조).

---

### D.2 시나리오 2 — 신규 분기(brand/pipeline/카테고리) 추가

#### 분기 유형 판별 (먼저 결정)

| 유형 | 판별 기준 | 처리 방향 |
|------|---------|----------|
| **(a) 새 검사 규칙 축** | 새 R-규칙, 새 M-체크, 새 C-체크를 추가하려는 경우 | **Appendix C.W7 패턴**으로 위임: `rules.py` UnifiedEntry 1줄 + `standard.py`/`maintenance.py` 해당 함수 1개. 자동 편입. 이 런북 범위 밖. |
| **(b) brand/pipeline 분류 축** | 새 YAML 파일(brand) 추가, 기존 파이프라인과 다른 pipeline 값 사용, 카테고리/funnel_stage 확대 | 아래 절차. config 스키마·fleet 분류·excluded 필터·dispatcher 매핑을 건드리는 중량 작업. |

#### (b) brand/pipeline 분류 축 — 등록 순서 (의도)

**목표 상태: 새 brand/pipeline의 블로그가 fleet에 올바르게 분류되고, 표준 검사·excluded 필터·dispatcher가 의도대로 작동하는 상태.**

1. **brand 추가 (새 YAML 파일):**
   - `config/blogs.d/{새brand}.yaml` 생성. 파일명 → `_detect_brand()`로 자동 brand 추출.
   - 목표 상태: `/api/fleet` 응답의 `brand` 필드에 새 brand 값 등장, 해당 brand 블로그들이 함께 분류됨.
   - 허용: 새 YAML 파일 1개 생성 + 내용 작성.
   - 금지: 기존 YAML 파일 수정 (기존 블로그 재분류 위험).

2. **pipeline 값 확인:**
   - YAML의 `pipeline:` 필드가 기존 파이프라인 값(curation/car/stock/etap/travel/rap/senior) 중 하나면 추가 코드 변경 불필요.
   - 새 pipeline 값이 완전 신규면 → dispatcher.py의 파이프라인 분기 로직에 등록 필요할 수 있음 (B등급, 사용자 확인 1회).
   - **결정지점:** "이 pipeline이 dispatcher에서 별도 run() 호출·시범 매핑·DB 처리가 필요한가?" → 예면 B, 아니오면 A.

3. **기존 블로그 재분류 영향 확인 (중요 — STOP 유발 가능):**
   - 새 brand YAML은 기존 블로그를 건드리지 않음 (파일별 독립).
   - 단, 기존 블로그의 `pipeline:` 값을 바꾸거나 `status:`를 바꾸면 baseline·검사 대상 집합 변동 → **🔴 비가역.**
   - **STOP-3:** 기존 블로그의 field 수정이 계획에 포함되면 즉시 중단. 재분류는 별도 웨이브·명시적 승인 필요.

4. **dispatcher 매핑 확인 (필요 시):**
   - STAP 계열 새 블로그 → `STAP_PIPELINE_MAP` (dispatcher.py:79-86)에 blog_id→pipeline명 매핑 추가.
   - CAP 계열 새 블로그 → `CAP_BLOGS` 집합 (dispatcher.py:258-261)에 blog_id 추가.
   - ETAP 계열 → `_ETAP_BLOG_EXCEPTIONS` 확인.
   - cuap/rap/seap/tap 계열 → 일반적으로 YAML site_path로 충분, 추가 매핑 불필요.
   - 허용: dispatcher.py의 해당 매핑 dict/집합에만 추가.
   - 금지: dispatcher.py 분기 로직 전체 재구성.

#### 허용 범위

- ✅ 건드려도 됨: 새 brand YAML 파일, dispatcher.py의 매핑 dict/집합(STAP_PIPELINE_MAP/CAP_BLOGS 등), DB 동기화.
- ❌ 건드리면 안 됨: 기존 brand YAML, dispatcher.py 분기 로직 본문, db.py 스키마, 다른 pipeline의 처리 로직.

#### 검증 게이트

- [ ] `/api/fleet` → 새 brand 값 존재, 해당 블로그들이 brand 기준으로 분류됨
- [ ] `/api/registry` 또는 `POST /api/run-checks` → 새 블로그들의 check_results 생성, 표준 검사 정상 동작
- [ ] excluded 필터 정상: active 블로그는 fail_checks 쪽, inactive/paused는 excluded_fail_checks 쪽
- [ ] dispatcher가 새 blog_id 인식: `_load_all_blogs()` → `get_blog_config(blog_id)` → site_path 반환

#### STOP 조건

- (a) **기존 블로그 재분류** — 기존 YAML 레코드의 field 수정 포함 시 즉시 STOP (🔴 비가역)
- (b) **brand명 충돌** — `_detect_brand()` 결과가 기존 brand와 중복 → 중단, 파일명 변경
- (c) **dispatcher 매핑 누락** — 새 pipeline이 dispatcher에서 처리 못 해 발행·DB 기록 실패 가능성 → 중단, 매핑 추가 또는 승인
- (d) **baseline 흔들림** — 기존 블로그의 check_results/excluded가 의도치 않게 변동
- (e) **검사 반쪽 상태** — 일부 check만 돌고 일부 안 돔 (예: M체크는 maintenance_status 조건상 초기엔 의도적 미실행이나, R체크조차 안 돌면 문제)

#### 비가역 주의

- **기존 blog의 brand/pipeline/status/field 변경 = 🔴 별도 웨이브·명시 승인.** 이 런북은 신규 추가만 다룸. 기존 레코드 수정은 파괴적 작업 프로토콜(사전 카운트→백업→스케줄러 정지→실행→사후 대조) 적용 대상.

---

### D.3 공통 프로토콜

**백업 (매 등록 전):**
```bash
git tag pre-onboard-{blog_id 또는 brand}-{YYYYMMDD}
cp ops_dashboard/ops.db ops_dashboard/ops.db.bak_onboard_{YYYYMMDD}
```
- 코드 변경 전: git tag
- DB 변경 전: ops.db 백업

**스케줄러 정지 (DB 대량 변경 시):**
- launchd 스케줄러 정지 확인 전에는 DB 대량 UPDATE/INSERT 금지.
- 현재 scheduler.py는 계속 실행 중(PID 78295). `sync_blog_lifecycle()`는 단일 INSERT/UPDATE라 스케줄러 정지 불필요하나, 여러 블로그를 한 트랜잭션으로 대량 갱신하는 경우는 정지.

**화면 반영 (매 등록 후):**
```bash
# 신규 블로그 검사 실행 → 화면 즉시 갱신
curl -s -X POST -u ops:112233 "http://localhost:5060/api/run-checks?blog_id={blog_id}"
# 또는 전체 (기존 블로그 영향 감안)
curl -s -X POST -u ops:112233 http://localhost:5060/api/run-checks
```
- 반영 확인: `/api/attention`·`/api/registry`·`/blog/{blog_id}` 페이지에서 새 blog_id의 검사 결과 확인.

**로그:**
- `logs/destructive_YYYY-MM-DD.log`에 한 줄 append: `[시각] 신규 블로그/brand 온보딩: blog_id={id}, brand={brand}, pipeline={pipeline}, status={status}, baseline증가=+{추정행수}행`
- `.planning/worklog/WL-{YYYYMMDD}-onboarding-{blog_id}.md` 작성 (커밋 포함 시 필수).

---

### D.4 매뉴얼 시뮬레이션 증명 (실제 등록 없이)

**가상 입력:** blog_id=`test-hugo`, brand=`cuap`(기존 YAML에 추가 가정), pipeline=`curation`, domain=`test.informationhot.kr`, theme=`blowfish`, site_path=`/Users/twinssn/Projects/cuap/test-hugo`, status=`active`, daily_quota=`5`.

#### 필요 입력 체크

| 입력 | 값 | 충족? |
|------|-----|------|
| blog_id | test-hugo | ✅ |
| brand | cuap (cuap.yaml에 추가) | ✅ |
| pipeline | curation | ✅ |
| domain | test.informationhot.kr | ✅ (기존 도메인과 중복 아님 가정) |
| theme | blowfish | ✅ |
| site_path | /Users/twinssn/Projects/cuap/test-hugo | ✅ (실존은 미확인 — B등급 지점) |
| status | active | ✅ |
| daily_quota | 5 | ✅ |

→ **STOP-1 통과** (필수 입력 전부 있음). site_path 실존 여부는 실행 시점에 확인 — 레시피 범위 내.

#### 등록 순서 계획 (생성)

1. 대상 파일: `config/blogs.d/cuap.yaml` — 기존 15개 엔트리 아래에 새 `- id: test-hugo` 블록 추가 (1파일, 약 20줄 추가)
2. DB 동기화: `POST /api/run-checks?blog_id=test-hugo` → 내부 `_ensure_db()` → `sync_blog_lifecycle()` → blog_lifecycle에 test-hugo 1행 INSERT
3. 검사 확인: 동일 호출로 check_results에 test-hugo × ~15 check_name 행 생성
4. dispatcher 매핑: cuap 계열이므로 `site_path`가 YAML에 명시되어 있으면 추가 매핑 불필요 (dispatcher.py:208 `_load_all_blogs()`로 충분)

예상 변경 규모: 1파일(cuap.yaml) + DB 1행 + check_results 약 15행.

#### baseline 예상 증가분

- blog_lifecycle: +1행 (total 85→86)
- check_results (run-checks 1회): +~15행 (test-hugo active 기준)
- fail_checks: test-hugo에 fail 체크가 있으면 그 건수만큼 증가. 없음(모두 pass/unknown)이면 fail_checks 변화 0.
- excluded_fail_checks: active이므로 0 (excluded로 편입 안 됨)
- standard_compliance aggregate: +1행 (test-hugo)

#### STOP 조건 대조

- (a) 허용 범위[cuap.yaml만] 준수? 예 — 1파일만 수정 계획. 통과.
- (b) blog_id 중복? test-hugo는 현재 blog_lifecycle에 없음(실데이터 85건에 없음) → 통과. 단, 기존 중복 확인은 실행 전 필수.
- (c) domain 중복? test.informationhot.kr은 현재 fleet에 없음 → 통과. 실행 전 확인 필수.
- (d) baseline 예상 외 변동? +1(blog_lifecycle) +~15(check_results) +0~N(fail_checks) → 예측 모델 범위 내. 통과.
- (e) 검사 반쪽 상태? run-checks 호출 시 R체크+M체크 전부 실행 예정 → 통과 (M체크는 maintenance_status='none'이므로 check_maintenance_checklist는 스킵되나, 이는 의도적. R체크는 정상 실행).
- (f) dispatcher 매핑 실패? cuap 계열, site_path YAML 명시 → `_load_all_blogs()`로 충분 → 통과. 단, site_path 디렉토리가 실존하지 않으면 Hugo 빌드·배포 시 실패 → 그건 이 런북 범위 밖(배포 단계 문제).

#### 결과

**STOP 조건 걸리지 않음. 계획 안전.** 단, (b) blog_id 중복·(c) domain 중복·(f) site_path 실존은 실행 전 확인 필수 — 확인 불가면 B등급 지점으로 멈추고 사용자에게 확인 요청.

시뮬레이션 결론: 레시피 경계 안에서 계획이 안전하게 생성되고, 애매한 지점(b/c/f)에서는 제대로 STOP함.

---

커밋: `docs(agents): Appendix D Fleet 확장(온보딩) 런북 추가 — 신규 블로그·분기 두 시나리오.

---

## Subagent Stuck Detection Rules (2026-07-18)

## Subagent Stuck Detection Rules (2026-07-18)

> **Incident:** gsd-planner가 28분간 빈 응답만 반환하며 스턱. session 메시지 2개(프롬프트 + 빈 응답), transcript 0건으로 작업이 전혀 진행되지 않았음. 9분 체크에서 이미 이 패턴이었으나 즉시 취소하지 못해 시간 낭비.

### 1. 9분 룰 — 최초 체크에서 즉시 취소

Subagent 실행 후 **5~10분** 시점에 `session_info()`로 상태 확인:

- **session 메시지가 2개(프롬프트 + 빈 응답)뿐이고 transcript 0건이면 → 즉시 취소**
- 정상 subagent는 5~10분 내 최소 5~10회 tool call transcript가 쌓여야 함
- transcript가 없으면 일을 한 게 아님 (조용한 실패)
- 취소 후 직접 처리 또는 재시도

### 2. delegate vs 직접 판단 — 단순 작업은 직접

Subagent에 위임하기 전 스스로 판단:

- **단순 포매팅, 문서 작성, 이미 수집된 데이터 정리** → 직접 작성 (subagent 필요 없음)
- **새로운 탐색, 대규모 grep, 구조 분석** → subagent 위임 적합
- **판단 기준**: "이 작업에 내가 이미 필요한 모든 데이터를 가지고 있는가?" → Yes면 직접, No면 subagent

### 3. 체크 주기 — 5분 단위 transcript 확인

- 폴링 주기: 30초가 아니라 **5분 단위**
- 체크 포인트: `session_read(session_id, limit=5)`로 **transcript에 새로운 tool call이 있는지만 확인**
- 5분마다 확인해도 동일한 빈 상태면 → 즉시 취소
- 5분이면 subagent가 최소 하나의 유의미한 tool call을 수행할 충분한 시간

### Cheatsheet

```
1. subagent 실행 후 5분 대기
2. session_info() → messages > 2? transcript > 0? 
   - messages ≤ 2 and transcript = 0 → 취소 (9분 룰)
3. session_read()로 5분마다 transcript 증분 확인
4. 2회 연속 동일 상태면 취소
5. 단순 작업은 처음부터 직접 처리
```

<!-- GSD:subagent-stuck-detection-end -->

<!-- GSD:destructive-ops-start -->

## 파괴적 작업 수행 규칙 (2026-08-06)

> 사고 배경: run_sync()이 non-unique 인덱스 위에서 중복 15,514행을 재삽입하고,
> backfill이 1,412곳의 제목을 오염시킴(STRUCT-11). 되돌리기 어려운 작업은
> 항상 사전 계획 + 로그 + worklog를 남긴다. 위반은 조용한 실패로 취급하지 않는다.

### 1. 파괴적 작업 정의 (보수적 기본값)

아래에 해당하면 **파괴적 작업**이다. 경계가 애매하면 파괴적으로 간주한다.

- DB: DELETE / UPDATE / DROP / 테이블·인덱스 재생성 / 스키마 마이그레이션
- 프로덕션 DB(content.db 등)에 대한 **대량 INSERT** (run_sync류, 소스 전체 재삽입)
- wrangler 배포·재배포 (Pages/Workers)
- git push / tag 이동 / force push / history rewrite
- 파일·디렉터리 대량 삭제 (rm -rf, 반복 삭제 루프)
- 스케줄러·데몬 정지·기동 (launchd, scheduler.py 등)
- 콘텐츠 재생성으로 라이브 글을 덮어쓰는 작업
- 기존 기능의 삭제·교체를 수반하는 코드 변경 (추가만이 아닌 경우)

**비파괴(로그 불필요):** 읽기 전용 조회(grep, SELECT, curl -I), 대시보드 로드,
테스트 실행, 문서 작성. 단, SELECT라도 실행 후 데이터가 변하면 파괴적이다.

**영구 보존 대상 (삭제 금지):** content.db의 `source=''` 실발행 행.
실발행 기록 유실 0을 보장해야 한다.

### 2. 파괴적 작업 4단계 프로토콜 (강제)

1. **사전 카운트/영향 범위 출력** — 삭제·변경 예정 건수, 대상 범위를 먼저 출력.
2. **되돌림 수단 확보** — 백업 경로(예: `data/content.db.bak_<ts>`) 또는
   롤백 태그/커밋을 명시하고 확인.
3. **실행** — 사전 확인 후에만.
4. **사후 대조** — before/after 수치를 비교해 출력. 실발행 행수(예: source='' 36행)
   보존 여부를 반드시 재확인.

**필수 사용자 확인:** 대량 삭제·프로덕션 DB 변경은 "삭제 예정 건수"를 먼저
보고하고 사용자 확인을 받은 뒤에만 실행한다. 스스로 판단해 넘어가지 않는다.

**라이브 스케줄러 선행 정지:** 프로덕션 DB에 쓰는 작업(INSERT/UPDATE/DELETE/
마이그레이션)은 라이브 스케줄러·데몬 정지 확인을 선행 조건으로 한다.
정지 확인 전에는 실행 금지.

### 3. 로그·worklog 연동 (필수)

- 파괴적 작업 1건마다 `logs/destructive_YYYY-MM-DD.log`에 한 줄 append:
  `[시각] 명령 | 사전카운트= | 백업= | 사후= | 보존확인=`. 민감정보(토큰/비밀번호)는 마스킹.
- 파괴적 작업이 하나라도 포함된 작업 단위는 종료 시
  `.planning/worklog/WL-<날짜>-<주제>.md`를 남긴다.
  **"커밋 또는 파괴적 작업 → worklog 필수"**. 비파괴 작업만 있으면 worklog 선택.
- worklog 양식/예시: `.planning/worklog/README.md` 참조. 상세 분해 절차는
  `.planning/skills/fleet-ops-audit-playbook.md` 참조(중복 서술 금지).

### 4. 즉시 적용 — 진행 중 사고 대상

content.db 복구 작업이 이 규칙의 첫 적용 대상이다:
- 복구는 4단계 프로토콜(사전 카운트 → 백업 → 실행 → 사후 대조)을 따른다.
- `logs/destructive_2026-08-06.log`와
  `.planning/worklog/WL-20260806-content-db-recovery.md`를 생성한다.
- 복구 절차 상세: `.planning/phase-60-publish-investigation-and-hardening/RECOVERY-content-db-20260806.md`

<!-- GSD:destructive-ops-end -->

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

코드 수정 요청은 일반 채팅 구현으로 즉시 처리하지 않는다. - 단일·작은 수정: `/gsd-quick` - 기존 UI, 광고, SEO, 템플릿, 수익 로직에 영향: `/gsd-quick --validate` - 다수 파일, 구조 변경, 요구사항 불명확: Phase workflow 사용 `/gsd-quick`에서도 대상 파일 전체 덮어쓰기와 계획 밖의 기존 기능 삭제는 금지한다.


## Karpathy Guidelines (LLM 코딩 습관 개선)


Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Dashboard Operations Agent Reference

For any dashboard, publishing, deployment, validation, source, duplicate, freshness, or notification signal, read `ops_dashboard/docs/agent-reference/README.md` before proposing or applying a change. It links the required safety protocol, machine-readable signal policy, and error playbooks. Treat Telegram as a notification channel only; use structured events, raw logs, configuration, data stores, and live evidence to determine root cause.
