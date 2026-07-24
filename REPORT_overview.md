# TAP 여행 종합 발행 프로젝트 — 전체 구조 조사 보고서

## 3줄 요약

- **5000**은 중앙 컨트롤 파이프라인(dispatcher + scheduler + shared 모듈)이고, **TAP(/Users/twinssn/Projects/tap)**은 그 하위 여행 전용 분기다.
- 발행 대상은 **6개 블로그(1개 Blogger + 5개 Hugo)**이며, 실제 운영 주체는 **5000 dispatcher**다. TAP은 Blogger 1개 + 데이터/모듈 일부를 제공하는 서브시스템 역할을 한다.
- 데이터 흐름은 `공공API/로컬DB → fetcher → writer → publisher → Hugo 파일 쓰기/ Blogger 발행 → wrangler 배포`이며, 스케줄은 5000 scheduler가 blogs.yaml 기반으로 전담한다.

---

## 1) 최상위 구조 파악

### 1.1 `/Users/twinssn/projects/5000` (5000 중앙 파이프라인 루트)

| 폴더/파일 | 역할 (추정) |
|---|---|
| `config/` | 블로그 정의(`blogs.d/*.yaml`), 프롬프트, API 키, OAuth 설정 |
| `pipelines/` | 파이프라인별 발행 로직: `travel/`, `car/`, `etap/`, `curation/`, `senior/`, `stock/`, `rap/` |
| `shared/` | 공통 모듈: 발행, AI, 콘텐츠 저장, 유효성 검사, 배포, 알림 등 |
| `data/` | SQLite DB들 (`content.db`, `stap_content.db`, `tap.db`, `festival.db` 등) |
| `scripts/` | 배치/보조 스크립트 (IndexNow, 배포, 동기화 등) |
| `dispatcher.py` | 중앙 라우터 — `blog_id`를 받아 pipeline을 실행하고 ledger를 기록 |
| `scheduler.py` | 중앙 스케줄러 — `blogs.yaml` 스케줄에 따라 dispatcher를 호출 |
| `hugo.toml` | 5000 자체 Hugo 사이트(`rotcha.kr`) 설정 — TAP 6개 블로그와는 무관 |
| `content/`, `layouts/`, `assets/`, `static/` | 5000 Hugo 사이트 리소스 |
| `workers/` | Cloudflare Workers(`redirect-worker.js`) |
| `functions/` | Cloudflare Pages Functions |
| `.env` | 5000 환경변수 (Cloudflare, R2, OpenAI 등) |
| `.venv/` | 5000 Python 가상환경 |

### 1.2 `/Users/twinssn/Projects/tap` (TAP 분기)

| 폴더/파일 | 역할 (추정) |
|---|---|
| `core/` | TAP 자체 코어: AI 작성, 데이터 수집, Blogger 발행, 축제, 캠핑, 관광 API 등 |
| `travel-hugo/` ~ `travel4-hugo/` | 5개 Hugo 블로그 정적 사이트 (각각 독립 hugo repo) |
| `config/` | TAP 설정: 지역, 테마, 키워드, 필드 매핑, 제목 템플릿 |
| `data/` | TAP 전용 DB (`tap.db`, `festival.db`, `tap_entity.db`) |
| `app.py` | TAP 메인 엔트리포인트 — **Blogger 발행 전용** |
| `scheduler.py` | TAP 전용 스케줄러 — 일반/축제 발행만 담당 (Hugo 미포함) |
| `run_festival.py` | 축제 전용 발행 스크립트 |
| `.env` | TAP 환경변수 (Blogger, TourAPI, Naver, OpenAI, WordPress 등) |
| `venv/` | TAP Python 가상환경 |
| `scripts/` | 섹션 인덱스 가드 등 보조 스크립트 |
| `tests/` | TAP 단위/통합 테스트 |

---

## 2) 6개 블로그 식별

소스: `/Users/twinssn/projects/5000/config/blogs.d/tap.yaml`

### 활성 6개 블로그

| 블로그 ID | 타입 | 폴더 경로 | 설정/인증 파일 | 주제 | 비고 |
|---|---|---|---|---|---|
| `tap-blogger` | Blogger | `/Users/twinssn/Projects/tap` (가상) | `config/blogger_token.json`, `blogger_token.pickle`, `client_secret.json`, `service_account.json` | 문화재/캠핑/축제/관광지 등 **여행 전반** | TAP app.py가 발행 |
| `travel-hugo` | Hugo | `/Users/twinssn/Projects/tap/travel-hugo` | `config/_default/hugo.toml` | 캠핑·아웃도어 | 도메인 `tour1.rotcha.kr` |
| `travel1-hugo` | Hugo | `/Users/twinssn/Projects/tap/travel1-hugo` | `config/_default/hugo.toml` | 축제·행사 | 도메인 `travel1.rotcha.kr` |
| `travel2-hugo` | Hugo | `/Users/twinssn/Projects/tap/travel2-hugo` | `config/_default/hugo.toml` | 문화유산 | 도메인 `travel2.rotcha.kr` |
| `travel3-hugo` | Hugo | `/Users/twinssn/Projects/tap/travel3-hugo` | `config/_default/hugo.toml` | 맛집·카페 | 도메인 `tour2.rotcha.kr` |
| `travel4-hugo` | Hugo | `/Users/twinssn/Projects/tap/travel4-hugo` | `config/_default/hugo.toml` | 여행코스 | 도메인 `tour3.rotcha.kr` |

### 비활성 2개 블로그 (config에는 존재)

| 블로그 ID | 타입 | 도메인 | 상태 |
|---|---|---|---|
| `tvshow-blogger` | Blogger | `tv-show.informationhot.kr` | inactive |
| `ud-blogger` | Blogger | `ud.informationhot.kr` | inactive |

### 공통 설정
- 모든 Hugo 사이트는 테마로 **Blowfish** 사용, `themesDir = "/Users/twinssn/Projects/shared-themes"` 하드코딩.
- `site_path`는 `config/blogs.d/tap.yaml`에 절대경로로 명시됨.

---

## 3) 파이프라인 흐름 파악

### 3.1 전체 흐름 (큰 그림)

```
5000 scheduler.py
  └─ schedule 기반으로 blog_id별 queue_publish()
       └─ dispatcher.py dispatch(blog_id)
            ├─ pipeline: tap → _run_tap_subprocess()
            │    └─ TAP/app.py run_publish()
            │         ├─ source 선택 (camping/heritage/festival)
            │         ├─ data fetch (TAP core)
            │         ├─ AI 생성 (TAP core/ai_writer.py)
            │         └─ Blogger 발행 (TAP core/blogger_publisher.py)
            │
            └─ pipeline: travel → 5000/pipelines/travel/pipeline.py
                 ├─ _fetch_for_blog() → fetcher (5000 travel/fetcher.py)
                 │    └─ 내부에서 TAP core 모듈 재사용 (sys.path로 TAP_ROOT 주입)
                 ├─ generate_content() → writer (5000 travel/writer.py)
                 │    └─ build prompt → shared/ai_writer.py
                 ├─ 중복 체크 (publish_ledger / articles)
                 └─ shared/publisher.py publish()
                      ├─ Hugo frontmatter + markdown 파일 생성
                      └─ (성공 시) dispatcher → _build_and_deploy_central()
                           ├─ hugo --gc --minify
                           └─ wrangler pages deploy / wrangler deploy
```

### 3.2 진입점

| 진입점 | 위치 | 역할 |
|---|---|---|
| `dispatcher.py` | `/Users/twinssn/projects/5000/dispatcher.py` | 중앙 진입점 — `python dispatcher.py {blog_id}` |
| `scheduler.py` | `/Users/twinssn/projects/5000/scheduler.py` | 중앙 스케줄러 — launchd에서 실행 |
| `app.py` | `/Users/twinssn/Projects/tap/app.py` | TAP 단독 실행 — `python app.py run` (Blogger만) |
| `run_festival.py` | `/Users/twinssn/Projects/tap/run_festival.py` | 축제 단독 발행 |
| `pipelines/travel/pipeline.py` | `/Users/twinssn/projects/5000/pipelines/travel/pipeline.py` | 5개 Hugo travel 블로그 파이프라인 |

### 3.3 스케줄/자동화

| 스케줄러 | 위치 | 대상 | 방식 |
|---|---|---|---|
| 5000 scheduler | `/Users/twinssn/projects/5000/scheduler.py` | **전체 6개 TAP 블로그 포함 모든 블로그** | `schedule` 라이브러리 + launchd (추정) |
| TAP scheduler | `/Users/twinssn/Projects/tap/scheduler.py` | **Blogger(tap-blogger)만** | `schedule` 라이브러리 + launchd (`com.tap.scheduler`) |

**주의**: 5000 scheduler가 `config/blogs.d/tap.yaml`의 스케줄을 읽어 6개 블로그 전부를 실행한다. TAP 자체 scheduler도 `app.py run`을 별도로 실행할 수 있는데, 이 경우 **동일 블로그에 대한 이중 발행 위험**이 존재한다. (현재 운영 상태에서 실제로 둘 다 실행 중인지 확인 필요)

---

## 4) 공통 모듈 vs 블로그별 개별 코드

### 4.1 5000 공통 모듈 (`shared/`)

5000 `shared/` 디렉토리에 파이프라인/블로그 공통 모듈이 집중되어 있다:

| 모듈 | 주요 기능 |
|---|---|
| `shared/publisher.py` | Hugo markdown 쓰기, frontmatter 빌드, 관련글 카드 삽입 |
| `shared/ai_writer.py` | OpenAI 기반 AI 글 생성 |
| `shared/prompt_builder.py` | 프롬프트 빌드 |
| `shared/content_store.py` | articles/publish_ledger INSERT, used_places, 이미지 등록 |
| `shared/validators.py` | 제목/본문 유효성 검사 |
| `shared/blogger_publisher.py` | Blogger API 발행 (5000 측) |
| `shared/telegram_notifier.py` | 텔레그램 알림 |
| `shared/image_handler.py` | 이미지 처리 |
| `shared/r2_uploader.py` | Cloudflare R2 업로드 |
| `shared/paths.py` | 프로젝트 루트 경로 해석 |
| `shared/db_paths.py` | DB 경로 상수 |
| `shared/hugo_builder.py` | Hugo 빌드/배포 헬퍼 |

### 4.2 TAP 자체 모듈 (`core/`)

TAP은 독자적인 `core/` 모듈을 가진다:

| 모듈 | 주요 기능 |
|---|---|
| `core/ai_writer.py` | TAP 전용 AI 생성 (Blogger 포맷) |
| `core/blogger_publisher.py` | Blogger 발행 (TAP 측) |
| `core/content_generator.py` | 데이터 → 아이템 구성 |
| `core/content_processor.py` | 후처리 |
| `core/fetcher.py` | 소스 관리자, 데이터 수fetch |
| `core/camping_data.py` | 캠핑 API |
| `core/korservice_data.py` | 관광 API |
| `core/heritage_data.py` | 문화유산 데이터 |
| `core/tour_api.py` | TourAPI 클라이언트 |
| `core/nearby_info.py` | 주변 맛집/관광지 |
| `core/tap_entity_manager.py` | TAP 엔티티 카드 관리 |
| `core/festival/` | 축제 전용 파이프라인 |

### 4.3 공유/중복 패턴

- **5000 travel pipeline**은 `sys.path`에 `TAP_ROOT`를 주입하여 TAP `core/` 모듈을 직접 import한다. (`pipelines/travel/fetcher.py`, `pipelines/travel/pipeline.py`, `pipelines/travel/writer.py`)
- **중복 의심 모듈**: `ai_writer`, `image_handler`, `validators`, `blogger_publisher` 등이 5000 `shared/`와 TAP `core/` 양쪽에 존재한다. (기능은 유사하나 구현이 분리되어 있음)
- **Hugo 5개 사이트**는 정적 콘텐츠/테마만 각 폴더에 있고, 발행 로직은 공통 `shared/publisher.py`가 담당한다.

---

## 5) 설정/시크릿/의존성 점검

### 5.1 환경변수 파일 위치

| 파일 | 위치 | 비고 |
|---|---|---|
| 5000 .env | `/Users/twinssn/projects/5000/.env` | Cloudflare, R2, OpenAI 관련 변수 포함 |
| TAP .env | `/Users/twinssn/Projects/tap/.env` | Blogger, TourAPI, Naver, OpenAI, WordPress 등 포함 |
| `~/.env.common` | 사용자 홈 | `shared/paths.py`가 fallback으로 참조 (로드 시 CLOUDFLARE_API_TOKEN 제외 규칙 존재) |

### 5.2 설정/인증 파일 위치 (값 노출 금지 — 경로만 표기)

| 파일 | 위치 | 용도 |
|---|---|---|
| `config/api_keys.yaml` | `/Users/twinssn/projects/5000/config/api_keys.yaml` | API 키 관리 |
| `config/client_secret_hugh7973.json` | `/Users/twinssn/projects/5000/config/` | Google OAuth 클라이언트 시크릿 |
| `blogger_token.pickle` | `/Users/twinssn/projects/5000/` | Blogger OAuth 토큰 |
| `config/blogger_token.json` | `/Users/twinssn/projects/5000/config/` | Blogger 토큰 |
| `client_secret.json` | `/Users/twinssn/Projects/tap/` | TAP Blogger OAuth |
| `service_account.json` | `/Users/twinssn/Projects/tap/` | 서비스 계정 키 |
| `token.pickle` | `/Users/twinssn/Projects/tap/` | TAP OAuth 토큰 |

### 5.3 의존성

| 의존성 파일 | 위치 | 비고 |
|---|---|---|
| `requirements.txt` | `/Users/twinssn/projects/5000/requirements.txt` | openai, google-api, boto3, schedule, Pillow 등 |
| `pyproject.toml` | `/Users/twinssn/projects/5000/pyproject.toml` | ruff, mypy, pytest 설정 |
| `package.json` | `/Users/twinssn/projects/5000/package.json` | PostCSS/PurgeCSS (Hugo 빌드 최적화) |
| `requirements.txt` | `/Users/twinssn/Projects/tap/requirements.txt` | google-auth, openai, pandas, sqlalchemy, markdown 등 |
| `pyproject.toml` | `/Users/twinssn/Projects/tap/pyproject.toml` | ruff, pytest, mypy 설정 |
| Hugo 테마 | `/Users/twinssn/Projects/shared-themes` | Blowfish (TAP 5개 Hugo 사이트 공통) |
| Hugo 테마 | `/Users/twinssn/projects/5000/themes/PaperMod` | git submodule (5000 rotcha.kr 전용) |

---

## 6) 리스크 & 특이사항 (수정 후보, 실제 수정 아님)

### 6.1 구조/아키텍처 리스크

| ID | 리스크 | 상세 |
|---|---|---|
| R-01 | **이중 스케줄링 가능성** | 5000 scheduler 와 TAP scheduler 가 별도로 존재. 둘 다 `app.py run`을 실행할 수 있어 tap-blogger 이중 발행 위험. 현재 운영에서 실제로 둘 다 가동 중인지 확인 필요. |
| R-02 | **TAP ↔ 5000 강한 결합** | 5000 `pipelines/travel/*.py`가 `sys.path`에 TAP_ROOT를 주입하고 TAP core를 직접 import. TAP 구조 변경 시 5000 travel pipeline이 깨질 수 있음. |
| R-03 | **모듈 기능 중복** | `ai_writer`, `image_handler`, `validators`, `blogger_publisher` 등이 5000 shared와 TAP core 양쪽에 분산. 유지보수 시 양쪽을 함께 봐야 함. |
| R-04 | **Blogger ID 불일치 가능성** | 5000 `config/blogs.d/tap.yaml`의 `tap-blogger`와 TAP `.env`의 `BLOGGER_BLOG_ID`가 실제로 같은 값을 가리키는지 확인 필요. |

### 6.2 코드/데이터 리스크

| ID | 리스크 | 상세 |
|---|---|---|
| R-05 | **대량 .bak 파일** | TAP `core/` 디렉토리에 다수의 `.bak`, `.bak2`, `.v1.0.bak` 파일 존재. 정리되지 않고 방치됨. |
| R-06 | **백업 포스트 잔여** | `travel-hugo/_backup_deleted_posts`, `travel1-hugo/content_backup_20260501_105638`, `travel2-hugo/_backup_deleted_posts`, `travel4-hugo/_backup_deleted_posts` 등에 삭제된 글 데이터가 실제로 남아있음. |
| R-07 | **하드코딩 경로 다수** | `/Users/twinssn/Projects/TAP`, `/Users/twinssn/Projects/5000`, `/Users/twinssn/Projects/heritage`, `/Users/twinssn/Projects/shared-themes` 등이 코드에 하드코딩되어 있어 경로 변경 시 다수 파일 수정 필요. |
| R-08 | **Heritage JSON 경로 하드코딩** | TAP `app.py`의 `_get_heritage_content()`가 `/Users/twinssn/Projects/heritage/scripts/data/heritage_list.json`을 직접 참조. |
| R-09 | **travel3-hugo 단일 소스 의존** | `BLOG_FETCH_MAP`에서 `travel3-hugo`는 `fetch_food` 100% 의존. 데이터 없으면 즉시 `None` 반환 → `no_result` 빈발 가능. |
| R-10 | **wrangler 배포 시 `--commit-dirty=true` 사용** | 5000 `dispatcher.py`에서 Pages 배포 시 `--commit-dirty=true` 사용. AGENTS.md에서 금지된 옵션으로, Cloudflare Pages git 연동 빌드를 트리거하여 월 빌드 횟수를 불필요하게 소진함. |
| R-11 | **비활성 Blogger 설정 혼재** | `tvshow-blogger`, `ud-blogger`가 config에 남아있으나 `status: inactive`. 도메인이 `informationhot.kr` 계열로 TAP rotcha.kr 계열과 다름. |

### 6.3 실행/배포 리스크

| ID | 리스크 | 상세 |
|---|---|---|
| R-12 | **CLOUDFLARE_API_TOKEN 충돌** | 5000 dispatcher는 `_build_and_deploy_central()` 내에서 `CLOUDFLARE_API_TOKEN`을 제거하지만, TAP 측 배포 로직은 확인되지 않음. TAP Hugo 사이트 배포가 어디서 이루어지는지 명확하지 않음. (5000 dispatcher가 담당하는 것으로 추정) |
| R-13 | **데이터 DB 경로 이중화** | 발행 이력이 `content.db(publish_ledger)`와 `stap_content.db(articles)` 두 곳에 분산 저장됨. 경로 불일치로 중복 체크가 어긋날 가능성이 과거에 있었음(AGENTS.md 참조). |

---

## 7) 질문 / 확인 필요

| Q-ID | 질문 |
|---|---|
| Q-01 | TAP `scheduler.py`가 현재도 실제 실행 중인가? 5000 scheduler와 중복되지 않는가? |
| Q-02 | 5개 Hugo travel 블로그의 배포는 5000 dispatcher가 전담하는가? TAP 측 배포 스크립트는 존재하지 않는가? (wrangler.toml 미발견) |
| Q-03 | `shared/`와 `core/`의 중복 모듈(`ai_writer`, `validators`, `image_handler` 등)은 의도적 분리인가, 아니면 리팩터링 대상인가? |
| Q-04 | `tvshow-blogger`, `ud-blogger`는 재사용 예정인가, 삭제해도 되는가? |
| Q-05 | `travel-hugo` ~ `travel4-hugo`의 `themes/blowfish`는 `/Users/twinssn/Projects/shared-themes` 심볼릭 링크인가, 복사본인가? |
| Q-06 | `.bak` 파일들과 `_backup_deleted_posts` 폴더는 정리해도 되는가? |

---

## 부록: 핵심 파일 위치 맵

```
5000/
├── dispatcher.py                    # 중앙 라우터
├── scheduler.py                     # 중앙 스케줄러
├── config/
│   ├── blogs.yaml
│   ├── blogs.d/tap.yaml             # TAP 6개 블로그 설정
│   └── api_keys.yaml
├── pipelines/travel/
│   ├── pipeline.py                  # 5개 Hugo travel 블로그 파이프라인
│   ├── fetcher.py                   # 데이터 수집 (TAP core 재사용)
│   └── writer.py                    # AI 프롬프트 + 생성
├── shared/
│   ├── publisher.py                 # Hugo 발행
│   ├── ai_writer.py                 # 공통 AI 생성
│   ├── content_store.py             # DB 저장
│   └── db_paths.py                  # DB 경로 상수
└── data/
    ├── content.db                   # publish_ledger
    └── stap_content.db              # articles

TAP/
├── app.py                           # Blogger 발행 전용
├── scheduler.py                     # TAP 독자 스케줄러
├── core/
│   ├── ai_writer.py                 # TAP 전용 AI
│   ├── blogger_publisher.py         # Blogger 발행
│   ├── fetcher.py                   # 소스 관리
│   ├── camping_data.py / korservice_data.py / heritage_data.py
│   └── festival/festival_main.py    # 축제 파이프라인
├── travel-hugo/ ~ travel4-hugo/     # 5개 Hugo 정적 사이트
│   └── config/_default/hugo.toml
└── data/
    ├── tap.db
    └── festival.db
```

---

*보고서 생성일: 2026-07-24*
*근거: 파일 시스템 탐색, 설정 파일 읽기, 코드 흐름 추적 (읽기 전용)*
