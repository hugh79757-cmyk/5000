# Plan 61-03 Summary — Pilot 전환: SEAP(senior)·RAP 표준 골격 정렬 (Stage C)

**Phase:** 61-pipeline-standardization-branch-renewal
**Plan:** 61-03 (Wave 3, Stage C — Pilot)
**Date:** 2026-08-07
**Executed by:** opencode (Plan 61-03 autonomous)
**Dependencies:** 61-02 (shared/db.py) — 적용됨

---

## Objective

Stage C Pilot: 가장 작은 분기 SEAP(senior, 2 blogs)·RAP(rap, 5 blogs)를 표준 6-모듈
골격(pipeline/fetcher/topic_manager/writer/enrich/validator)에 정렬한다. 전환 패턴을
저위험 분기에서 검증해 rollout(61-04..07)에 동일 패턴을 안전하게 적용하는 것이 목적.
모든 변경 additive + 비파괴, 구조/동작 분리 커밋(D-08).

---

## 파일 생성/배선 (Deliverable 1)

### 신규 wrapper (pass-through placeholder, D-01 additive)

| 파일 | 제공 함수 | 위임/성격 |
|------|-----------|-----------|
| `pipelines/senior/topic_manager.py` | `select_topic(cfg, services=None)` | **pass-through placeholder** — 기존 `pipeline._pick_topic()` 위임 |
| `pipelines/senior/enrich.py` | `enrich_content(cfg, body_md) -> body_md` | **pass-through placeholder** — 원문 반환 (독립 enrich 단계 없음) |
| `pipelines/senior/validator.py` | `validate_post(cfg, article) -> (ok, errors)` | `shared.validators.validate_post_extended(pipeline="senior")` 위임 |
| `pipelines/rap/topic_manager.py` | `select_topic(cfg) -> (keyword, category)` | **pass-through placeholder** — 기존 `pipeline._pick_keyword()` 위임 |
| `pipelines/rap/enrich.py` | `enrich_content(cfg, body_md) -> body_md` | **pass-through placeholder** — 원문 반환 (독립 enrich 단계 없음) |
| `pipelines/rap/validator.py` | `validate_post(cfg, article) -> (ok, errors)` | `shared.validators.validate_post()` 위임 |

Review #71(추가 보정): senior/rap wrapper는 부재 모듈이므로 **docstring에 pass-through
placeholder임을 명시**했다. enrich 2종은 원문 그대로 반환(실제 enrich는 pipeline 내부 수행,
중복 삽입 방지). topic_manager 2종은 기존 인라인 선택 함수를 위임.

### DB path 배선 (D-06, additive — 파일 무이동)

| 파일 | 변경 | 성격 |
|------|------|------|
| `pipelines/rap/pipeline.py` | `RAP_DB_PATH = get_db_path("rap")` | `GAP_DB_PATH`(gap.db)는 **인라인 유지** (Review 보정) |
| `pipelines/senior/fetcher.py` | `SENIOR_DB_PATH = get_db_path("senior")` | `shared/db.py` 중앙 해석 |

- `get_db_path("rap")` / `get_db_path("senior")` 가 기존 `data/rap.db` / `data/senior.db` 와
  **정확히 동일 경로**임을 확인 (`== True`).
- senior `pipeline.py`는 fetcher에서 `SENIOR_DB_PATH`를 import하므로 자동 배선됨.

### 신규 테스트

| 파일 | 내용 |
|------|------|
| `tests/shared/test_pipeline_skeleton.py` (NEW) | 4 tests — senior/rap 6-모듈 존재 + run() callable (pkgutil, run() 미호출) |

---

## 동작 보존 확인 (Deliverable 2 — senior/rap run() dict 불변)

- **변경 사유**: `run(cfg)` / `run(blog_cfg)` 함수 본문은 **1줄도 수정하지 않았다.** DB path
  상수값만 중앙 해석으로 교체했고, 해석 결과가 기존과 **문자열 동일**하므로 발행 동작 불변.
- senior: `pipelines/senior/pipeline.py:116 def run(cfg)` 반환 dict 구조 그대로.
- rap: `pipelines/rap/pipeline.py:962 def run(blog_cfg)` 반환 dict 구조 그대로.
- `dispatcher.py` 경로: senior/rap은 이미 dict 반환 파이프라인이며, 정규화 지점(dispatcher.py:730-741)에
  영향 없음. dispatcher registry 테스트 `test_dispatcher_registry.py` **1 passed** 유지.

---

## 테스트 수치 (Deliverable 3 — 기준선 vs 구현 후)

### 기준선 (구현 전)
`python3 -m pytest -o addopts="" -q` → **21 failed, 346 passed, 1 skipped**

### 구현 후
`python3 -m pytest -o addopts="" -q` → **21 failed, 350 passed, 1 skipped**

**신규 실패 0건.** 실패 21건 집합을 `-rf` 로 수집해 diff — 기준선 21건과 **동일** (아래 [검증됨]).

**passed 증가:** 346 → 350 = **+4** (분해):
- test_pipeline_skeleton.py: 4 (senior 6-모듈 / rap 6-모듈 / senior run callable / rap run callable)
- 합계 = 4 ✓ (합 일치)

**신규 skeleton 테스트:** `tests/shared/test_pipeline_skeleton.py` → **4 passed**.
**dispatcher registry:** `tests/test_dispatcher_registry.py` → **1 passed**.

실패 21건 구성 (기준선 선언과 일치, KNOWN — 본 task 범위 아님):
- relevance_scorer 1, ai_writer 2, post_validator 1, curation keywords 3 + title_hardening 4 +
  title_regression 1 + cot 1 + alert 2 + filters 1 + defense_layers 4 + pipeline 1 = 21 ✓

---

## 커밋 해시 (Deliverable 4 — D-08 구조/동작 분리)

| 커밋 | 해시 | 내용 | 유형 |
|------|------|------|------|
| A | `1ce8d5031` | feat(phase-61): add senior standard-skeleton wrappers (topic_manager/enrich/validator) | 구조 추가 |
| B | `0e062f351` | feat(phase-61): add rap standard-skeleton wrappers (topic_manager/enrich/validator) | 구조 추가 |
| C | `c88ec5b4d` | refactor(phase-61): centralize senior/rap DB path via shared/db.py | 구조/유틸 (DB path) |
| D | `308e3e54c` | test(phase-61): add pipeline skeleton presence test | 테스트 추가 |

구조(신규 모듈), 유틸(DB path), 테스트를 별도 커밋으로 분리 (D-08).

---

## Review 보정 적용 확인 (Deliverable 5)

| Review 항목 | 적용 여부 | 근거 |
|------------|-----------|------|
| rap은 RAP_DB_PATH + GAP_DB_PATH 둘 다 사용. RAP만 shared/db.py로, gap.db는 인라인 | **[적용]** | `RAP_DB_PATH = get_db_path("rap")`, `GAP_DB_PATH`는 원래 인라인 유지 (pipeline.py:20). |
| senior/rap wrapper는 pass-through placeholder로 명시 | **[적용]** | 6개 wrapper docstring에 placeholder 명시 (enrich 2종 원문 반환, topic_manager 기존 함수 위임). |
| D-01 additive + 기존 모듈 보존 | **[적용]** | 기존 pipeline/fetcher/writer 1줄도 제거 없음. run() 본문 불변. |
| AdSense Publisher ID (8772/6677/5938) | **[무관/미접촉]** | 광고 파일 접촉 없음. 위반 없음. |
| 배포는 dispatcher.py 경유 | **[무관/미접촉]** | 배포 없음 (code-only). 수동 wrangler 미실행. |

---

## 검증 상태 (3분법)

- **[검증됨]** 신규 실패 0건: `-rf`로 실패 21건 nodeid 수집 후 기준선과 nodeid diff → 동일 집합.
- **[검증됨]** passed +4: 346→350, 분해(4 skeleton tests) 합 일치.
- **[검증됨]** senior/rap DB path 동일 해석: `get_db_path("senior")==SENIOR_DB_PATH`,
  `get_db_path("rap")==RAP_DB_PATH` 를 직접 비교해 `== True` 확인.
- **[검증됨]** GAP_DB_PATH 인라인 유지: pipeline.py에 원래 경로 상수 남음.
- **[검증됨]** 6개 wrapper AST + import + 함수 존재: `ast.parse`, `from pipelines.senior import ...` 확인.
  - `select_topic`/`enrich_content`/`validate_post` 전부 `hasattr==True`.
- **[검증됨]** `data/*.db` 무이동: `git status --porcelain`에 tracked `data/*.db` 변경 0건.
  (보이는 `data/content.db.*` 4건은 사전부터 존재하던 untracked 복구 백업 — 내 작업과 무관,
  none ends in `.db`.)
- **[검증됨]** 커밋 4개 존재 (`git log --oneline -4`에 phase-61 커밋 확인).
- **[검증됨]** `test_dispatcher_registry.py` 1 passed (파이프라인 등록 무중단).
- **[부분검증]** senior/rap `run()` 실제 실행 반환 dict — run()은 live 서비스(API/DB)를
  필요로 해 직접 호출하지 않음. **구조적으로 본문 불변 + DB path 동일 문자열**로 보존을 검증했으나,
  런타임 실행까지는 커버하지 않음 (스모크 테스트는 run() 미호출 의도).
- **[검증불가]** 없음.

---

## 잔존 위험

1. **런타임 발행 동작 미실행 확인**: run() 호출이 live API/DB를 필요로 해 실제 발행 경로를
   실행으로 검증하지 못함. 구조·path 동일성으로 보존을 보증하나, 실제 파이프라인 런은 스케줄러의
   다음 발행 주기에서 자연 검증됨.
2. **wrapper 미소비 상태**: 신규 6개 wrapper는 골격 존재를 위해 추가됐고, 아직 pipeline.run()이
   호출하지 않음 (비파괴 원칙상 기존 경로 유지). rollout(61-04..07) 및 scaffold(61-09)에서
   소비 예정. 소비 전까지는 dead-ish 코드로 남음 (의도된 placeholder).
3. **enrich placeholder**: senior/rap enrich가 원문 그대로 반환 — 실제 enrich는 pipeline 내부에서
   수행 중이라 기능 손실 없음. 향후 enrich 단계를 모듈로 승격 시 재배선 필요.
4. **잔존 위험: 없음** (구조적 데이터 변경, DB mutation, 배포, 광고 매핑 변경 전혀 없음).

---

## Output

본 SUMMARY 작성 완료. Stage C (Pilot) 완료 — SEAP/RAP 표준 골격 6-모듈 완비.
전환 패턴(얇은 wrapper 추가 + DB path 중앙화 + skeleton 테스트 + 분리 커밋)이 검증됨.
rollout(61-04 car / 61-05 travel / 61-06 curation / 61-07 ETAP)에 동일 패턴 적용 대기.
