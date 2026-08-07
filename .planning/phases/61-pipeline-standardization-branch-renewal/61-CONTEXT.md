# Phase 61: Pipeline Standardization & Branch Renewal (분기별 파이프라인 표준화 리뉴얼) - Context

**Gathered:** 2026-08-07
**Status:** Ready for planning

<domain>
## Phase Boundary

85개 블로그를 발행하는 7개 파이프라인 분기(car/curation/etap/rap/senior/travel/stock)를
**동일한 표준 골격**으로 재편하는 5000 프로젝트 리뉴얼.

현재 분기별 비일관성(모듈 구조·config 스키마·실행 방식·DB 접근·외부 프로젝트 실행 경로)을
제거하고, 새 분기를 표준 템플릿으로 즉시 생성할 수 있는 기반을 만든다.

**본 Phase의 경계:** 표준 정의 + 공용 기반 구축 + 분기별 staged 전환 + 온보딩 도구.
새 콘텐츠 기능(예: 새 파이프라인 유형 추가, 새 수익 모델)은 본 Phase 범위 밖.

**핵심 제약 (보존 대상):**
- 기존 발행 파이프라인 **무중단** — 단계별 pilot → 확산, 기존 테스트 green 유지
- 코드 수정 원칙: **추가(additive) 우선, 비파괴(non-destructive)** — 동작 변경과 구조 변경 분리 커밋
- AdSense Publisher ID 매핑(8772/6677/5938) 불변 — 광고 관련 파일 표준화 시에도 위반 금지
- 배포는 `dispatcher.py` 경유만 (수동 wrangler 금지, `CLOUDFLARE_API_TOKEN` 제거 규칙 유지)
</domain>

<decisions>
## Implementation Decisions

### 리뉴얼 범위 (사용자 확정 — 전부 포함)
- **D-01:** 파이프라인 코드 구조 통일 — 모든 분기가 동일 모듈 골격(`pipeline.py`/`fetcher`/`topic_manager`/`writer`/`enrich`/`validator`)을 따르도록 재편
- **D-02:** config 스키마 통일 — `blogs.d/*.yaml` 공통 필드를 표준 스키마로 고정 + `shared/config_validator.py`로 검증
- **D-03:** 실행 방식 통일 — STAP/TAP subprocess 러너 중복(`_run_stap`/`_run_tap_subprocess`)을 `shared/subprocess_runner.py`로 통합, 모든 분기가 동일 `run(cfg)` 계약
- **D-04:** 외부 프로젝트(TAP/STAP) 5000 통합 — 독립 저장소 구조는 유지하되 `run(cfg)` 계약 + subprocess_runner로 5000 표준에 정합 (흡수 병합은 아님)
- **D-05:** 새 분기 생성 도구 — `scripts/scaffold_branch.py`로 표준 골격 + config 템플릿 + DB 스키마 자동 생성 (ETAP 35쌍 같은 수동 복제 근절)

### 진행 방식 (사용자 확정)
- **D-06:** 이 계획을 GSD Phase로 공식화 — Phase 61로 ROADMAP 등록 완료, 이후 `/gsd-plan-phase 61`로 세부 계획 수립

### 실행 전략 (Claude 제안, 사용자 승인 대기 — 계획 단계에서 확정)
- **D-07 (안):** 단계 순서 = A(표준 정의·문서화) → B(공용 기반 추가) → C(가장 작은 분기 SEAP/RAP pilot 전환) → D(확산: CAP→travel→curation→ETAP 단일화) → E(외부 STAP/TAP 정합) → F(스캐폴드 도구 + 레거시 정리)
- **D-08 (안):** ETAP 36개 블로그의 `{topic}_pipeline.py`+`{topic}_writer.py` 35쌍 중복은 topic_manager 설정 기반 단일 파이프라인으로 수렴 (가장 큰 변경이므로 pilot 검증 후 마지막 확산 단계)

### Claude's Discretion
- 표준 `run(cfg)` 반환 dict의 정확한 키 세트(`success`/`reason`/`slug`/`title`/`body_md`/`thumbnail_url`/`deploy_error`)는 계획 단계에서 파이프라인별 반환값 실측 후 확정
- 각 분기 전환 시 코드 동작 변경 범위(구조 재편 vs 동작 수정) 분리 기준
- 레거시 `.bak` 파일 정리 대상 목록과 보존 기준

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 5000 중앙 구조
- `dispatcher.py` — 메인 라우터. `_resolve_pipeline()`(L448), `_run_stap`(L380), `_run_tap_subprocess`(L504), `_build_and_deploy_central`(L596), STAP_PIPELINE_MAP(L81), ETAP_PIPELINE_BLOGS(L566), WORKERS_BLOGS(L579) 확인 필수
- `scheduler.py` — launchd 스케줄러 루프 (dispatch 주기 제어)
- `shared/paths.py` — 프로젝트 루트 해석 (STAP_ROOT/TAP_ROOT/ETAP_ROOT/CUAP_ROOT/RAP_ROOT)

### 분기별 파이프라인 구현
- `pipelines/car/pipeline.py` — run(cfg) 진입점 패턴 (post_type 라우팅, 재시도 루프)
- `pipelines/etap/pipeline.py` + `pipelines/etap/{topic}_pipeline.py` 35개 — 표준화 최대 대상
- `pipelines/curation/pipeline.py` (67KB), `pipelines/rap/pipeline.py` (55KB), `pipelines/travel/pipeline.py`, `pipelines/senior/pipeline.py`, `pipelines/stock/pipeline.py`

### config 스키마
- `config/blogs.yaml` + `config/blogs.d/*.yaml` — cap/tap/stap/cuap/seap/rap 6개 분기 스키마 비교 대상
- `shared/config_validator.py` — 기존 검증 로직 (확장 지점)

### 공용 발행 계층
- `shared/publisher.py` (1150줄) — STAP_BLOGS/TAP_TRAVEL_BLOGS 하드코딩 분기 포함
- `shared/publishers/hugo_writer.py`, `shared/publishers/deploy.py`, `shared/publishers/blogger_client.py`
- `shared/problem_registry.py` (Phase 58) — reason → problem_id(P01~P24) 매핑. 표준 오류 코드 참조

### 데이터 계층
- `data/car.db`, `data/curation.db`, `data/rap.db`, `data/senior.db`, `data/travel-en.db`, `data/stap_content.db`, `data/content.db` — 분기별 DB 접근 계층 표준화 대상

### 보존 규칙
- `AGENTS.md` §1 AdSense Publisher ID 매핑 (8772/6677/5938) — 광고 파일 표준화 시 불변
- `AGENTS.md` §3 Hugo + Wrangler 배포 규칙 — CLOUDFLARE_API_TOKEN 해제, dispatcher.py 경유
- `.planning/phase-59-ops-dashboard-and-unification/` — Ops Dashboard + 파이프라인 통합 (본 Phase의 선행 산출물, Phase 59 Wave 4가 ETAP `_write_hugo_post()` 35중복 제거를 이미 계획)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shared/problem_registry.py`: reason 문자열 → 표준 problem_id 매핑 — 표준 오류 코드로 재사용
- `shared/config_validator.py`: config 검증 로직 — 표준 스키마 검증으로 확장
- `shared/publishers/` (hugo_writer/deploy/blogger_client): 발행·배포 공용 경로 — 이미 단일화 진행 중 (Phase 59 Wave 4)
- `shared/paths.py`: 프로젝트 루트 중앙 해석 — 실행 방식 표준화의 기반

### Established Patterns
- 모든 분기가 `run(cfg) -> dict` 반환 (일부는 str/bool 반환하는 레거시 존재 — dispatcher L730-741에서 정규화 중)
- 파이프라인별 독립 SQLite DB + `publish_ledger` 중앙 기록
- STAP/TAP만 subprocess 격리 (독립 venv), 나머지는 in-process importlib

### Integration Points
- `dispatcher.py:_resolve_pipeline()` — 분기 라우팅 단일 지점 (모든 실행 방식 표준화의 접점)
- `dispatcher.py:_build_and_deploy_central()` — 배포 단일 경로 (Workers 11 + Pages 74)
- `shared/publisher.py` — 분기 하드코딩(STAP_BLOGS/TAP_TRAVEL_BLOGS)이 표준화 시 최소 침습 대상

</code_context>

<specifics>
## Specific Ideas

- 사용자 표현: "각 분기는 tap seap stap 등 각 카테고리별로 나눠진다" — 분기(branch) = 카테고리별 파이프라인 그룹
- 사용자 표현: "어떻게 동일하게 각 분기들을 만들면 좋을지" — 목표는 분기 간 동일성(uniformity) 확보
- 사용자 제약: "절대 코드 변경금지. 계획만세운다" — 본 세션은 계획 수립만 수행. 실제 코드 변경은 후속 Phase 실행 단계에서
</specifics>

<deferred>
## Deferred Ideas

- **외부 프로젝트의 5000 단일 저장소로의 물리적 흡수 병합** — D-04에서 계약 정합으로 결정됨. 물리적 통합(디렉터리 이동)이 필요한 경우 별도 Phase로 분리
- **새 파이프라인 유형 추가 (예: 부동산 분기 확장, 새 카테고리 분기 생성)** — 표준 골격 확정 후에만 가능하므로 후속 Phase
- **Ops Dashboard 확장 (Phase 59 후속)** — 파이프라인 표준화 후 대시보드와의 통합 지점 재검토 필요
- **`.bak` 파일/레거시 정리는 Phase 61-F에서 보고서 형태로만 식별** — 실제 삭제는 별도 승인 필요 (파괴적 작업 규칙 적용)

None — discussion stayed within phase scope (외)
</deferred>

---

*Phase: 61-Pipeline Standardization & Branch Renewal*
*Context gathered: 2026-08-07*
