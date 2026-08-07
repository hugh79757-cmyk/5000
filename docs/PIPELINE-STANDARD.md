# Pipeline Standard — Canonical Reference (D-02 / D-04)

> **Phase 61 · Stage A (Plan 61-01).** 이 문서는 5000 프로젝트의 7개 파이프라인 분기
> (car / curation / etap / rap / senior / travel / stock)를 하나의 표준 골격으로 묶기 위한
> **규범적(normative) 기준**이다. 이후 모든 전환 플랜(61-02..61-09)은 이 문서를 근거로 구현한다.
> 이 문서에 적힌 계약은 실행 중인 워킹 트리(dispatcher.py, shared/, pipelines/*)에 대해
> 코드 검증된 사실이다.
>
> **비파괴 원칙 (D-08):** 모든 전환은 추가(additive) 위주다. 기존에 동작하던 발행 파이프라인은
> 절대 깨뜨리지 않는다. 구조 변경과 동작 변경은 반드시 분리 커밋으로 수행한다.

---

## Section 1 — 목적 및 경계 (Purpose & Boundary)

### 1.1 목적

7개 파이프라인 분기가 발산한 모듈 구조·config 스키마·`run()` 계약·DB 접근·외부 프로젝트 방식을
**동일한 표준 골격**으로 수렴시킨다. 목표:

- 분기별 표준을 단일 문서로 고정해 이후 전환 플랜이 분기마다 제각각 다시 갈라지지 않게 한다.
- 새 분기를 표준 템플릿으로 즉시 생성할 수 있는 기반(`scripts/scaffold_branch.py`, Plan 61-09)을 마련한다.
- 기존 발행 파이프라인의 무중단을 보장한다(모든 변경 additive).

### 1.2 경계 (Scope Boundary)

| 항목 | 범위 |
|------|------|
| **대상** | 7개 분기: car, curation, etap, rap, senior, travel, stock |
| **외부 프로젝트 (TAP/STAP)** | **계약 정합만.** 물리 병합 금지. `run(cfg)` 반환 계약 + subprocess 라우팅만 정렬 (Plan 61-08). |
| **새 콘텐츠 기능** | 범위 밖 (새 파이프라인 유형·새 수익 모델 금지). |
| **신규 third-party 패키지** | 범위 밖 — stdlib + 기존 `requirements.txt`만 사용. 설치 금지. |
| **DB 데이터 통합** | 범위 밖 — 분기별 DB 파일 유지, 데이터 이동 금지 (Section 6). |
| **`.bak` 파일 실제 삭제** | 범위 밖 — 보고서만 (Plan 61-09). 별도 승인 필요. |

---

## Section 2 — 표준 모듈 골격 (D-01)

### 2.1 6-모듈 골격

모든 파이프라인 분기는 다음 6개 모듈을 표준 골격으로 가진다:

| 모듈 | 책임 |
|------|------|
| `pipeline.py` | `run(cfg) -> dict` 진입점. 분기별 실행 오케스트레이션. |
| `fetcher` | 데이터 수집 (외부 API·DB·정적 소스). |
| `topic_manager` | 토픽 선택/중복 가드/할당량. |
| `writer` | 글 생성 (AI 프롬프트·LLM 폴백 체인). |
| `enrich` | 엔리치먼트 (광고 삽입·내부 링크·이미지·크로스셀). |
| `validator` | 발행 전/후 검증 (품질 게이트·이미지 URL·CJK 누수). |

### 2.2 추가 규칙 (Additive Wrapper Rule, D-01)

1. **이미 존재하는 모듈은 유지**하고 골격에 배선(wire)한다.
2. **부재 모듈은 얇은(thin) wrapper로 추가**해 기존 `shared/` 코드로 위임한다.
3. **기존 코드는 제거하지 않는다.** 동작하는 발행 로직을 재작성하지 않는다.
4. wrapper가 위임할 기존 모듈이 없으면(pass-through placeholder) **placeholder로 명시**한다.
   기존 로직을 위임하는 척 이름만 붙이지 않는다.

### 2.3 분기별 현재 모듈 → 표준 골격 매핑

현재 모듈 존재(✓)는 워킹 트리 기준이며, 전환 계획은 부재 모듈을 wrapper/placeholder로 추가한다.

| 분기 | pipeline | fetcher | topic_manager | writer | enrich | validator | 전환 플랜 | 골격 적용 범위 |
|------|----------|---------|---------------|--------|--------|-----------|-----------|----------------|
| senior (SEAP) | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | 61-03 (C) | 완전 골격 |
| rap (RAP) | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | 61-03 (C) | 완전 골격 |
| car (CAP) | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ | 61-04 (D1) | 완전 골격 |
| travel (TAP 인트리) | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | 61-05 (D2) | 완전 골격 |
| curation (CUAP) | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ | 61-06 (D3) | 완전 골격 |
| etap (ETAP, 35쌍) | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ | 61-07 (D4) | 완전 골격 (최고 위험, 최후) |
| stock (STAP 외부) | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | 61-08 (E) | **계약만** |

> **스코프 명시 (D-04 계약 정합):** `stock`(STAP) 분기는 독립 저장소 물리 병합 금지이므로
> 표준 골격 전체(fetcher/topic_manager/enrich/validator wrapper 추가)가 아니라
> **`run(cfg)` 반환 계약 + subprocess 라우팅만** 적용한다.
> 매핑 테이블에서 stock의 골격 적용 범위는 "계약만"이다. 나머지 6개 인-트리 분기
> (car / curation / etap / rap / senior / travel)만 완전 골격을 보장한다.
> 따라서 ROADMAP 수용 기준 #1 "7개 분기 동일 골격"은 **6개 인-트리 완전 골격 + stock 계약 정합**으로 해석한다.

---

## Section 3 — 실행 계약 `run(cfg) -> dict` (D-01/D-02)

### 3.1 표준 진입점 시그니처

```python
def run(cfg: dict) -> dict:
```

- 단일 인자 `cfg` (블로그 설정 dict).
- 반환은 반드시 `dict`.

### 3.2 표준 반환 dict 키

| 키 | 타입 | 필수 | 설명 |
|----|------|------|------|
| `success` | bool | **필수** | 성공 여부. |
| `reason` | str | **필수** | 실패 사유 — Section 5의 폐쇄 어휘에서 선택. |
| `slug` | str | 선택 | 발행 슬러그. |
| `title` | str | 선택 | 발행 제목. |
| `body_md` | str | 선택 | 본문 Markdown. |
| `thumbnail_url` | str | 선택 | 썸네일 URL. |
| `deploy_error` | str | 선택 | 배포 실패 사유 (P04 계열). |

### 3.3 반환 정규화 규칙

- **dict가 아닌 반환은 허용하지 않는다.** 표준 계약은 모듈 레벨에서 dict만 반환해야 한다.
- 비-dict 반환은 다음 규칙으로 정규화한다:
  - `None` → `{"success": False, "reason": "no_result"}`
  - `bool` → `{"success": <bool>}`
  - `str` → dispatcher `dispatch()` L740 매핑(`quota_met` / `fetch_error` 등)에 따른다.
- **기존 dispatcher `dispatch()` 정규화는 유지한다.** 모듈 계약만 통일하고,
  dispatcher의 기존 정규화 로직(L740 부근)을 대체하지 않는다.
- travel 분기는 `_run_single`이 할당량/데이터 부족 시 `None`을 반환하므로(가드 차단),
  Plan 61-05에서 wrapper로 `None` → `{"success": False, "reason": "no_result"}` 정규화한다 (RESEARCH Pitfall 3).

### 3.4 ETAP 혼합 계약 처리

- ETAP 하위 토픽 모듈은 `run()` / `run(cfg)` 시그니처가 혼재한다.
  표준은 `run(cfg)` adapter wrapper로 위임한다.
- `dispatcher.py:_resolve_pipeline`의 `_ETAP_BLOG_EXCEPTIONS` + `inspect.signature` 브리지
  (dispatcher.py:444-465)는 **반드시 유지**한다. 이 브리지를 깨면 조용히 동작 변경이 일어난다 (RESEARCH Pitfall 1).
- ETAP topic pipeline이 `return True`/`return False`(직접 bool)뿐 아니라
  `return result`(bool 변수) 형태로도 bool을 반환할 수 있으므로,
  adapter 정규화는 간접 bool 반환도 포함해야 한다 (Review #6).

### 3.5 ETAP `flight_pipeline` 예외 처리 (Review #2 — 명시적 결정)

`pipelines/etap/flight_pipeline.py`의 `run(cfg)`는 **`success` 키 없이 `{"status": ...}` dict를 반환**한다.
`status` 값: `"skip"` / `"error"` / `"draft"` / `"ok"`.

- `dispatcher.py:dispatch()`는 `result.get("success")`(dispatcher.py:743)로 판단하므로,
  이 dict는 그대로 두면 flight 성공이 오분류될 수 있다.
- **결정: 표준은 flight의 `{"status": ...}` dict를 `success`/`reason` 형태로 정규화할 것을 요구한다.**
  Plan 61-07의 adapter에서 `{"status": "ok"}` → `{"success": True, "reason": "ok", ...}`로,
  `{"status": "skip"}` → `{"success": False, "reason": "no_topic"}`로,
  `{"status": "error"}` → `{"success": False, "reason": "generation_failed"}`로,
  `{"status": "draft"}` → `{"success": False, "reason": "content_quality_gate"}`로 매핑한다.
- 표준 컨포미스를 위해 예외로 두지 않고 **정규화**한다 (Review "Divergent Views" 권고안 채택).
- flight는 `run(cfg)` 시그니처(1건)로 `_ETAP_BLOG_EXCEPTIONS`에 포함된다. adapter 배선 시 브리지 유지.

---

## Section 4 — 통합 config 스키마 (D-04)

### 4.1 표준 스키마

`config/blogs.d/*.yaml` 각 blog entry의 표준 필드 정의.
필드는 워킹 트리의 `config/blogs.d/*.yaml` 실측 키를 근거로 한다.

#### 필수 (required)

| 필드 | 설명 |
|------|------|
| `id` | 블로그 ID (예: `rap-hugo`). |
| `pipeline` | 파이프라인 분기명 (car/curation/etap/rap/senior/travel/stock). |
| `platform` | 발행 플랫폼: `hugo` / `blogger` / `wordpress`. |

#### 표준 (standard — 공통 필수값)

| 필드 | 설명 |
|------|------|
| `name` | 블로그 이름. |
| `domain` | 도메인. |
| `daily_quota` | 일일 발행 할당량. |
| `schedule` | 스케줄 (`times` 하위 목록). |
| `status` | 활성 상태 (`active` / `inactive`). |
| `managed_by` | 관리 모드 — **`managed_by: pipeline`** 을 표준 관리 모드로 명시. |

#### 확장/선택 (optional — 분기별 보존, 삭제 금지)

| 필드 | 설명 |
|------|------|
| `cf_project` | Cloudflare Pages 프로젝트명. |
| `repo` | 저장소 경로. |
| `site_path` | Hugo 사이트 경로. |
| `theme` | Hugo 테마. |
| `funnel_stage` | 퍼널 단계. |
| `depth_next` | 다음 깊이. |
| `bridge_to` | 크로스블로그 브리지 대상. |
| `post_type` | 글 유형. |
| `prompt` | 프롬프트. |
| `ga4_property` | GA4 속성 (선언형 확장; 모든 분기에 일괄 존재하지는 않음). |
| `gsc_site` | Google Search Console 사이트. |
| `blogger_blog_id` | Blogger 블로그 ID. |
| `force_draft` | 강제 초안 여부. |
| `language` | 언어 (예: `ko`, `en`). |

### 4.2 스키마 규칙

1. `managed_by: pipeline` 을 표준 관리 모드로 명시한다.
2. **분기별 확장 키는 optional 로 보존한다 (삭제 금지).** 기존 config 무중단.
   실측된 추가 키(`fetch_sources`, `prompt_map`, `bridge_context`, `shortcodes_enabled`,
   `blog_type` 등) 역시 optional 확장으로 취급하며, 보존한다.
3. 이 스키마는 Plan 61-02의 `shared/config_validator.py` 확장의 근거다.
   `REQUIRED_BLOG_FIELDS = ["id", "pipeline", "platform"]` 유지,
   `OPTIONAL_BLOG_FIELDS`와 `VALID_PLATFORMS = ["hugo", "blogger", "wordpress"]` 확장.

---

## Section 5 — 표준 reason-key 어휘 (closed vocabulary)

### 5.1 표준 어휘 선언

`shared/problem_registry.py`의 **P01~P24 + `unknown_failure`** (총 25개 spec)를
표준 폐쇄 어휘로 선언한다. 분기가 반환하는 모든 `reason` 문자열은 반드시 이 레지스트리에서
정확히 1개 spec으로 해석되어야 한다 (`lookup_reason()`).

### 5.2 미등록 reason — 추가 예정 목록 (Plan 61-02에서 registry에 반영)

RESEARCH/Plan이 열거한 "11개" 중 `language_error`는 **이미 P12(content_quality_gate)의
`reason_keys`로 등록**되어 있다 (shared/problem_registry.py:272, Review #5).
따라서 **진짜 미등록 reason은 10개**이며, 그중 9개는 워킹 트리에서 실측 발행되고
`no_topics`는 현재 트리에서 실측되지 않는 방어적(defensive) 추가 후보다:

| reason | 실측 발행 위치 | 현재 상태 |
|--------|----------------|-----------|
| `daily_quota_reached` | pipelines/etap/pipeline.py | 미등록 → P17 계열 매핑 |
| `expired_service` | pipelines/senior/pipeline.py | 미등록 → P19 계열 매핑 |
| `generation_failed` | pipelines/{car,curation}/… | 미등록 → P02 계열 매핑 |
| `no_subscription_data` | pipelines/rap/pipeline.py | 미등록 → P01 계열 매핑 |
| `no_topic` | pipelines/{car,etap}/… | 미등록 → P01 계열 매핑 |
| `no_topics` | (실측 없음 — 방어적) | 미등록 → P01 계열 매핑 |
| `no_trade_data` | pipelines/rap/pipeline.py | 미등록 → P01 계열 매핑 |
| `prompt_not_found` | pipelines/car/pipeline.py | 미등록 → P02/P21 계열 매핑 |
| `publish_failed` | pipelines/rap/pipeline.py | 미등록 → P02 계열 매핑 |
| `write_failed` | pipelines/rap/pipeline.py | 미등록 → P02 계열 매핑 |

> **`language_error` 는 목록에서 제외** (이미 P12 등록, Review #5). 추가하지 않는다.

### 5.3 reason-key 규칙

1. **신규 reason은 반드시 registry에 등록하거나 가장 가까운 P-code로 매핑한다.**
2. **`unknown_failure` 로의 소실 금지.** 미등록 reason이 `unknown_failure`로 분류되면 알림 특이성이 사라진다.
3. Plan 61-02는 위 10개 reason을 `problem_registry.py`에 추가하고,
   기존 발행 파이프라인이 반환하는 모든 reason이 `lookup_reason()`으로 1개 spec에 해석되는지 재검증한다.

### 5.4 분기별 현재 사용 reason ↔ P-code 매핑 (예)

| 분기 | 현재 사용 reason (일부) | 표준 P-code |
|------|------------------------|-------------|
| car | `no_topic`, `generation_failed`, `prompt_not_found` | P01 / P02 / P02 |
| curation | `language_error`, `generation_failed`, `no_content` | P12 / P02 / P02 |
| etap | `daily_quota_reached`, `no_topic`, `generation failed`(flight) | P17 / P01 / P02 |
| rap | `no_trade_data`, `no_subscription_data`, `publish_failed`, `write_failed` | P01 / P01 / P02 / P02 |
| senior | `expired_service`, `language_error` | P19 / P12 |
| travel | `no_result` (시군구 가드) | P01 |

---

## Section 6 — DB 접근 규칙 (D-06)

1. **DB 파일은 분기별로 유지**한다. 데이터 통합·데이터 이동 금지.
2. **`shared/db.py` (Plan 61-02)가 path+connection을 중앙화**한다. 역할은 path/connection 해석에 한정.
   데이터 이동·mutation 금지 (테스트가 `data/*.db` 불변을 단언).
3. **`shared/db_paths.py`는 확장해 사용 (replace 금지).** 기존 심볼명 보존.
4. **travel 분기 실제 DB 의존성 (Review #3 — 정확 기록):**
   travel 파이프라인은 **`travel-en.db`를 사용하지 않는다.**
   `pipelines/travel/pipeline.py`·`fetcher.py`는 다음 DB를 사용한다:
   - `PUBLISH_LEDGER_DB` → `data/content.db` (shared/db_paths.py:11)
   - `ARTICLES_DB` → `data/stap_content.db` (shared/db_paths.py:14)
   - `FESTIVAL_DB` → festival DB (fetcher.py:230)
   > **후속 플랜(61-02/61-05) 주의:** travel에 `get_db_path('travel') → travel-en.db` 를
   > 배선하지 말 것. `shared/db_paths.py:19 TRAVEL_DB = travel.db` 는 **stale** (실제 파일은
   > travel-en.db) — Plan 61-02에서 공용 `shared/db.py`에 세 번째 충돌 travel 경로를 추가하지 않도록
   > 주의한다 (Review #4).
5. 인라인 `*_DB_PATH` 상수를 각 분기에서 인라인하는 대신 `shared/db.py` 경유로 중앙화한다
   (car: CAR_DB_PATH pipeline.py:26 + DB_PATH daily_refresh.py:18, curation: 6개 상수,
   rap: RAP_DB_PATH + GAP_DB_PATH 등 — 61-09 dead-code 보고에서 전체 목록).

---

## Section 7 — 배포 및 보존 규칙

### 7.1 배포 규칙

1. **배포는 반드시 `dispatcher.py` / `deploy.py` 경유만.** 수동 `wrangler deploy` 금지.
   `dispatcher.py`가 Worker/Pages 자동 선택, Hugo 빌드, 직렬화 락, `CLOUDFLARE_API_TOKEN` 제거를 처리한다.
2. **`CLOUDFLARE_API_TOKEN` 제거 규칙:** wrangler subprocess 호출 전 반드시 env var 제거.
   `env -u CLOUDFLARE_API_TOKEN` (또는 env에서 pop). wrangler 4.x는 env var > OAuth profile 우선.
3. **git push로 배포 금지** — Cloudflare Pages 자동 빌드 월 500회 제한. 커밋/푸시는 형상 관리 용도만.

### 7.2 AdSense Publisher ID 불변 (AGENTS.md §1)

- Publisher ID ↔ 사이트 계열 매핑은 불변: `ca-pub-8772455780561463` (rotcha.kr 계열),
  `ca-pub-6677996696534146` (informationhot.kr 계열), `ca-pub-5938862195544185` (aikorea24.kr 계열).
- 광고 파일 표준화 시에도 위 매핑 위반 금지. 한 페이지 = 하나의 Publisher ID.
- `adsbygoogle.js` 로더의 `?client=` 와 모든 `<ins data-ad-client>` 가 동일 계정이어야 한다.
- ID 불일치 시 광고 백지(blank) — 도메인 불일치로 AdSense가 슬롯을 reject.

### 7.3 보존 규칙 (D-08)

1. **구조 변경과 동작 변경은 분리 커밋.**
2. 기존 모듈·함수·시그니처 보존. 변경은 추가 위주.
3. 기존 테스트 green 유지.
4. `content.db`의 `source=''` 실발행 행은 영구 보존 (삭제 금지).
5. 파괴적 작업(DB 변경, 재배포, 대량 삭제)은 사전 카운트 → 백업 → 실행 → 사후 대조
   4단계 프로토콜 준수 (AGENTS.md §destructive-ops).

---

## 부록 — 변경 이력

| 일자 | 변경 |
|------|------|
| 2026-08-07 | Plan 61-01 최초 작성. Review #2(flight 정규화), #3(travel DB), #5(language_error 제외) 반영. |
