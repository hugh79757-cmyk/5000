<!-- GSD:project-start source:PROJECT.md -->
## Project

**5000** — 중앙 컨트롤 파이프라인

50+ Korean/English 블로그를 자동 생성·발행하는 콘텐츠 자동화 플랫폼. OpenAI GPT로 글을 생성하고, Cloudflare Pages (Hugo 정적 사이트)와 Blogger/WordPress로 발행한 뒤 IndexNow로 검색 엔진에 알림.

**Core Value:** 파이프라인은 실패 시 명확한 에러를 내야 함 — 조용한 실패 없음, 수동 해결 없음.

### 브랜치 구조 (5000 중앙 통제)

5000은 중앙 컨트롤 파이프라인으로, 아래 브랜치들을 관리:

| 브랜치 | 전체명 | 역할 |
|--------|--------|------|
| **CAP** | Content Auto Publisher | 일반 콘텐츠 자동 발행 |
| **TAP** | Travel Auto Publisher | 여행 콘텐츠 자동 발행 (한국어) |
| **STAP** | Stock Auto Publisher | 주식/금융 콘텐츠 자동 발행 |
| **CUAP** | Curation Auto Publisher | 상품 큐레이션 콘텐츠 자동 발행 |
| **SEAP** | Senior Auto Publisher | 시니어/복지 콘텐츠 자동 발행 |
| **RAP** | Real Estate Auto Publisher | 부동산 콘텐츠 자동 발행 |

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
### 5000 브랜치 관리 구조
| 브랜치 | 프로젝트 경로 | 파이프라인 유형 | 블로그 수 |
|--------|--------------|---------------|----------|
| **CAP** | 5000 내부 | curation, gap, car, senior 등 | 20+ |
| **TAP** | `/Users/twinssn/Projects/TAP` | travel | 5+ |
| **STAP** | `/Users/twinssn/Projects/STAP` | stock | 6 |
| **CUAP** | `/Users/twinssn/Projects/CUAP` | curation (상품 큐레이션) | 10 |
| **SEAP** | 5000 내부 | senior | ~5 |
| **RAP** | 5000 내부 | rap (부동산) | ~3 |
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

| 에러 유형 | 파이프라인 | 원인 패턴 | 해결 방향 |
|-----------|-----------|-----------|-----------|
| `no_result` | travel | 데이터 수집 성공 → 가드 차단 → None 반환 | 가드 기간/임계값 조정 |
| `no_content` | sector/stock | 토픽 순환 소진 + 중복 가드 → article 생성 실패 | 토픽 다양화, 데이터 수집 빈도 |
| `similar_title` | curation | 제목 패턴 반복 → 유사도 80% 초과 | 키워드별 제목 변형 |
| `broken_featureimage` | kuta-hugo (외부 발행) | featureimage가 WordPress 도메인 경로로 설정, R2에 썸네일 없음 | batch_thumbnails.py 실행 |
| `deploy_error` | all Hugo | 이미지 URL 길이 초과, Hugo 빌드 실패 | URL sanitize, 파일명 제한 |
| `Hugo build failed` | travel-hugo | 콘텐츠 문제 → Hugo 빌드 에러 | 로그 확인, 배포 로직 분리 필요 |

## Key File Reference for Debugging

| 파일 | 용도 |
|------|------|
| `dispatcher.py` | 메인 라우터 — 파이프라인별 분기, no_result/no_content 분류 |
| `scripts/batch_thumbnails.py` | Hugo 포스트 썸네일 일괄 생성 + R2 업로드 |
| `shared/thumbnail_generator/generator.py` | 썸네일 이미지 생성 로직 |
| `shared/publishers/hugo_writer.py` | Hugo 콘텐츠 정리 — H2 가드, IMAGE-GUARD, URL sanitize, featureimage 업데이트 |
| `shared/content_store.py` | 콘텐츠 저장 — title_similar_exists(), is_place_used() |
| `shared/publishers/deploy.py` | Hugo 빌드 + wrangler 배포 |
| `shared/r2_uploader.py` | Cloudflare R2 S3 호환 업로드 |
| `config/blogs.d/tap.yaml` | TAP 블로그 설정 — schedule, pipeline, fetch_sources |
| `config/blogs.d/stap.yaml` | STAP 블로그 설정 |
| `data/stap_content.db` | STAP 콘텐츠 DB — articles 테이블 (sector-hugo 329건 발행) |
| `md-editor-nicegui/core/publish/auto_scheduler.py` | blogsmith auto-publisher (30분마다 blogsmith output → Hugo/WordPress 발행) |
| `md-editor-nicegui/core/publish/thumbnail_gen.py` | auto-publisher용 gradient 썸네일 생성기 |
| `md-editor-nicegui/core/publish/hugo.py` | auto-publisher Hugo 발행 + R2 업로드 + wrangler deploy |

## Cloudflare Wrangler Auth Profile (2026-07-14)

> **문제**: OpenCode/Codex agent가 `CLOUDFLARE_API_TOKEN` 환경변수를 설정 → wrangler auth profile(OAuth)보다 **env var가 우선 적용**되어 잘못된 계정으로 배포 실패

### 근본 원인

wrangler 4.x는 인증 우선순위가 다음과 같음:
1. `CLOUDFLARE_API_TOKEN` 환경변수 (최우선)
2. OAuth auth profile (fallback)

Agent 세션에서 `CLOUDFLARE_API_TOKEN`이 설정되면 wrangler가 profile을 무시하고 env var를 사용. token이 다른 계정이거나 권한 부족 시 `Authentication error code: 10000` 발생.

### 적용된 수정

| 파일 | 수정 내용 |
|------|----------|
| `dispatcher.py:_build_and_deploy_central()` | wrangler 호출 시 `CLOUDFLARE_API_TOKEN` env var 제거 (`deploy_env` 빌드) |
| `shared/publishers/deploy.py:_deploy_site_inner()` | `_wrangler_env`에서 `CLOUDFLARE_API_TOKEN` pop + `_cf_token` 로직 제거 |

### Profile 바인딩 현황

| Profile | 계정 | Bound Directories |
|---------|------|-------------------|
| `hugh79757` | hugh79757@gmail.com | `aikorea24`, `5000`, `cuap`, `ETAP`, `TAP`, `STAP` |
| `farmsolution` | farmsolution 계정 | `farmsolution` |
| `yuiying167` | - | `bazi-spattra` |

### 중요 규칙

1. **절대 `CLOUDFLARE_API_TOKEN`를 wrangler subprocess에 전달하지 말 것** — profile이 무시됨
2. 신규 프로젝트 경로 추가 시 `wrangler auth activate hugh79757 <path>`로 바인딩 추가
3. profile 관리 시 `env -u CLOUDFLARE_API_TOKEN wrangler auth ...` 사용 (agent 세션에서)
4. 상세: `aikorea24 AGENTS.md` Section "Cloudflare Auth Profile", `aikorea24 .planning/triage/20260714--wrangler-auth-profile-setup.md`
<!-- GSD:incidents-end -->

<!-- GSD:adsense-start -->
## AdSense Publisher ID Mapping

Google AdSense 퍼블리셔 ID는 **루트 도메인 기준으로 할당**되며, 모든 서브도메인이 동일한 ID를 공유함.

| Publisher ID | 소유 도메인 | 적용 사이트 |
|---|---|---|
| `ca-pub-6677996696534146` | **informationhot.kr** (+ 모든 하위 도메인) | CUAP 10개, RAP 5개, SEAP senior-hugo, CAP pick/rank, informationhot-hugo, STAP stock-hugo 등 `*.informationhot.kr` 전역 |
| `ca-pub-8772455780561463` | **rotcha.kr** | 5000(rotcha.kr 메인), rotcha-blog |
| `ca-pub-8772455780561463` | **techpawz.com** (+ 하위 도메인) | techpawz-hugo, biz.techpawz-hugo, issue-techpawz-hugo, info.techpawz-hugo |
| `ca-pub-8772455780561463` | **farmsolutionint.com** | farmsolution 관련 사이트 |

### 중요 규칙
1. **informationhot.kr 계열 사이트는 `ca-pub-8772455780561463`로 변경 절대 금지** — 해당 도메인은 `ca-pub-6677996696534146`에 바인딩되어 있음
2. 신규 도메인 추가 시 Cloudflare Pages 도메인 바인딩 + Google AdSense 승인 완료 후 적용
3. Hugo 사이트 AdSense 설정 방식: CUAP는 `config/_default/params.toml`의 `[adsense] clientID`, 그 외는 `layouts/partials/adsense/*.html` 또는 `extend-head.html`에 직접 하드코딩

---

## AdSense Standard Configuration (rotcha-blog 기준)

이 섹션은 **rotcha-blog**(rotcha.kr)의 광고 설정을 표준으로 삼아 문서화한다. 새 사이트를 만들거나 기존 사이트의 광고에 문제가 있을 때 이 구성을 참고한다.

### 1. Auto ads — `extend_head.html`

**앵커광고(Anchor ad)를 포함한 모든 Auto ads**를 활성화하려면 `<head>` 내에 다음 meta tag를 추가한다. (필수는 아니지만 권장 — `adsbygoogle.js?client=ca-pub-{ID}` 형태로 script를 로드하면 meta tag 없이도 Auto ads가 동작함)

```html
<meta name="google-adsense-account" content="ca-pub-{PUBLISHER_ID}">
```

- Hugo 테마에서 `extend_head.html` 또는 `extend-head.html` partial을 지원하면 해당 파일에 추가
- PaperMod 테마: `layouts/partials/extend_head.html`
- Blowfish 테마: `layouts/partials/extend-head.html` 또는 `config/_default/params.toml`의 `[adsense]` 섹션
- 위치: `<head>` 내 최상단 (다른 meta tag보다 앞에)

### 2. AdSense script 로딩 (성능 최적화)

**rotcha-blog 표준 — Interaction/Timeout lazy load:**

```html
<script>
var _ad=0;function _ld(){if(_ad)return;_ad=1;var s=document.createElement("script");s.src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-{PUBLISHER_ID}";s.async=1;s.crossOrigin="anonymous";document.head.appendChild(s);}["scroll","click","touchstart","keydown"].forEach(function(e){window.addEventListener(e,_ld,{once:1,passive:1});});setTimeout(_ld,7000);
</script>
```

- 사용자 인터랙션(scroll/click/touch/keydown) 중 최초 1회 로드
- 7초 후에도 인터랙션 없으면 자동 로드 (타임아웃)
- Core Web Vitals(LCP)에 영향을 주지 않도록 지연 로딩
- `adsbygoogle.js`는 반드시 `client=ca-pub-{ID}` 쿼리 파라미터 포함

### 3. Preconnect / dns-prefetch (성능 최적화)

```html
<link rel="preconnect" href="https://pagead2.googlesyndication.com" crossorigin>
<link rel="dns-prefetch" href="https://www.googletagmanager.com">
```

### 4. Display ad units partials (선택 — 인프라)

필요시 `layouts/partials/adsense/` 디렉토리에 아래 partial들을 생성한다. pub ID는 Hugo params에서 읽거나 fallback 값을 사용:

```html
data-ad-client="{{ site.Params.adsense.client | default "ca-pub-{PUBLISHER_ID}" }}"
```

| Partial 파일 | 용도 | 포맷 |
|---|---|---|---|
| `adsense/in-article.html` | 본문 내 삽입형 광고 | `display:block`, `data-ad-format="auto"` |
| `adsense/leaderboard.html` | 데스크톱 상단 리더보드 | `display:inline-block;width:728px;height:90px` |
| ~~`adsense/mobile-sticky.html`~~ | ~~모바일 하단 고정 광고~~ | **⚠︎ 사용 금지 — Auto ads(앵커)와 충돌함** |
| `adsense/lazy-load.html` | IntersectionObserver 기반 지연 push | `rootMargin: '100px 0px'` |

> **⚠︎ mobile-sticky.html 주의:** 하단 스티키 광고(`mobile-sticky.html`)는 `(adsbygoogle...).push({})` 호출이 AdSense Auto ads(앵커광고) 초기화를 선점하여 충돌한다. 이 충돌로 앵커광고가 비활성화되거나 스티키 슬롯이 공란으로 남는다. **반드시 제거하고 Auto ads 앵커광고로 대체할 것.**

**in-article.html 표준:**
```html
<div class="ad-inarticle not-prose my-8">
  <ins class="adsbygoogle"
       style="display:block"
       data-ad-client="{{ site.Params.adsense.client | default "ca-pub-{PUBLISHER_ID}" }}"
       data-ad-slot="{AD_SLOT_ID}"
       data-ad-format="auto"
       data-full-width-responsive="true"></ins>
</div>
```

**lazy-load.html 표준** (IntersectionObserver로 ad units 지연 push):
```html
<script>
(function() {
  if (window._adsenseLazyLoaded) return;
  window._adsenseLazyLoaded = true;
  var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        var ad = entry.target;
        if (ad.getAttribute('data-adsbygoogle-status') === 'pushed') return;
        ad.setAttribute('data-adsbygoogle-status', 'pushed');
        try { (adsbygoogle = window.adsbygoogle || []).push({}); }
        catch (e) { console.error('AdSense push error:', e); }
        observer.unobserve(ad);
      }
    });
  }, { rootMargin: '100px 0px' });
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('ins.adsbygoogle[data-ad-slot]').forEach(function(ad) {
      observer.observe(ad);
    });
  });
})();
</script>
```

### 5. AdSense CSS (광고 중앙 정렬)

```css
ins.adsbygoogle {
  display: block !important;
  width: 100% !important;
  max-width: 100% !important;
  text-align: center !important;
  margin: 8px auto !important;
  box-sizing: border-box !important;
}
```

### 6. Hugo params.toml 설정 (params 기반 사이트용)

```toml
[adsense]
  client = "ca-pub-{PUBLISHER_ID}"
```

### 체크리스트 — 신규 사이트 광고 설정

- [ ] `google-adsense-account` meta tag 추가 (Auto ads 필수)
- [ ] `adsbygoogle.js` script 로딩 코드 추가 (lazy load 권장)
- [ ] Preconnect/dns-prefetch 추가 (성능)
- [ ] ad units partials 생성 (in-article, leaderboard)
- [ ] mobile-sticky.html **절대 추가 금지** — Auto ads(앵커)와 충돌
- [ ] lazy-load.html 추가 (IntersectionObserver)
- [ ] AdSense CSS 추가 (중앙 정렬)
- [ ] params.toml `[adsense] client` 설정 (해당 시)
- [ ] Cloudflare Pages 도메인 바인딩 확인
- [ ] Google AdSense 대시보드에 도메인 승인 완료 확인
- [ ] AdSense 대시보드 Auto ads → Anchor ads ON
- [ ] `extend-head.html`에 `adsbygoogle.js` 스크립트 **직접 확인** — 누락 시 `<ins>` 태그 초기화 안 됨 → 흰 박스 현상 발생 (참고: kitchen-hugo 20260715 트리아지)
- [ ] `custom.css`에 `.ad-inarticle { min-height }` **절대 금지** — 광고 미게재 시 흰 빈 박스로 본문 밀려남
<!-- GSD:adsense-end -->

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
