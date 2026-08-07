# Plan 61-04 Summary — CAP(car, 8 blogs) 표준 골격 전환 (Stage D1)

**Phase:** 61-pipeline-standardization-branch-renewal
**Plan:** 61-04 (Wave 4, Stage D1 — CAP rollout 첫 단계)
**Date:** 2026-08-07
**Executed by:** opencode (Plan 61-04 autonomous)
**Dependencies:** 61-02 (shared/db.py), 61-03 (pilot pattern) — 적용됨

---

## Objective

Stage D1 rollout 첫 단계: car(CAP, 8 blogs) 분기를 표준 6-모듈 골격
(pipeline/fetcher/topic_manager/writer/enrich/validator)에 정렬한다. 61-03 pilot에서 검증된
패턴(얇은 wrapper 추가 + DB path `shared/db.py` 중앙화 + skeleton 테스트 + D-08 분리 커밋)을
첫 rollout 분기에 적용. car는 기존 `pipeline/topic_manager/title_engine/data_builder/daily_refresh`만
있어 fetcher/writer/enrich/validator가 부재 → 얇은 wrapper로 추가. 모든 변경 additive + 비파괴.

---

## 파일 생성/배선 (Deliverable 1)

### 신규 wrapper (D-01 additive)

| 파일 | 제공 함수 | 위임/성격 |
|------|-----------|-----------|
| `pipelines/car/fetcher.py` | `fetch_data(cfg, conn, topic, db_path=None) -> dict|None` | 기존 `data_builder.build_input()` 위임 (car의 데이터 수집은 run() 내부에서 build_input으로 수행) |
| `pipelines/car/writer.py` | `write_article(cfg, topic, data, prompt_text) -> str|None` | `shared.ai_writer.generate_car` + `topic_manager.validate_body` 위임 |
| `pipelines/car/enrich.py` | `enrich_content(cfg, body_md) -> body_md` | **pass-through placeholder** — 원문 반환 (car는 독립 enrich 단계 없음) |
| `pipelines/car/validator.py` | `validate_post(cfg, article) -> (ok, errors)` | `shared.validators.validate_post_extended(pipeline="car")` 위임 |

Review #71(추가 보정) 적용: fetcher/writer는 기존 car 로직을 **위임**하고, enrich는 위임할
기존 모듈이 없어 docstring에 **pass-through placeholder임을 명시** (원문 그대로 반환, 실제 본문
정제는 pipeline 내부 `validate_body()`에서 수행 중이라 기능 손실 없음). validator는 senior 패턴과
동일하게 shared 위임.

### DB path 배선 (D-06, additive — 파일 무이동)

| 파일 | 변경 | 성격 |
|------|------|------|
| `pipelines/car/pipeline.py` | `from shared.db import get_db_path as _get_db_path` + `CAR_DB_PATH = Path(_get_db_path("car"))` | 중앙 해석 |

- `Path(_get_db_path("car"))` 가 기존 `PROJECT_DIR / "data" / "car.db"` 와 **정확히 동일 경로**
  (`/Users/twinssn/Projects/5000/data/car.db`)이며 **Path 타입 유지** → `sqlite3.connect(str(CAR_DB_PATH))`
  및 data_builder에 db_path 전달 경로 모두 그대로 동작.
- `daily_refresh.py:18 DB_PATH` 는 Review 보정에 따라 **인라인 유지** (동작 무손실; 61-09 dead-code
  보고에서 목록화 예정).
- 기존 `PROJECT_DIR` 상수는 PROMPTS_DIR 등에 여전히 사용되므로 유지.

### 신규 테스트

| 파일 | 내용 |
|------|------|
| `tests/shared/test_skeleton_car.py` (NEW) | 7 tests — car 6-모듈 존재 + run() callable + wrapper 함수 존재 + DB path 배선 검증 (pkgutil, run() 미호출) |

---

## 동작 보존 확인 (Deliverable 2 — car run(blog_cfg) dict 불변)

- **변경 사유**: `pipelines/car/pipeline.py::run(blog_cfg)` **함수 본문은 1줄도 수정하지 않았다.**
  DB path 상수값만 중앙 해석으로 교체했고, 해석 결과가 기존과 **문자열/타입 동일**(Path)하므로
  발행 동작 불변. 반환 dict 구조 그대로.
- `dispatcher.py` 경로: car는 dict 반환 파이프라인이며 정규화 지점 영향 없음.
- `daily_refresh.py`, `data_builder.py`, `title_engine.py`, `topic_manager.py` — **전혀 수정하지 않음.**

---

## 테스트 수치 (Deliverable 3 — 기준선 vs 구현 후)

### 기준선 (구현 전)
`python3 -m pytest -o addopts="" -q` → **21 failed, 350 passed, 1 skipped**

### 구현 후
`python3 -m pytest -o addopts="" -q` → **21 failed, 361 passed, 1 skipped**

**신규 실패 0건.** 실패 21건은 기준선과 **동일 집합** (relevance_scorer 1, ai_writer 2,
post_validator 1, curation keywords 3 + title_hardening 4 + title_regression 1 + cot 1 + alert 2 +
filters 1 + defense_layers 4 + pipeline 1 = 21 ✓). KNOWN baseline, 본 task 범위 아님.

**passed 증가:** 350 → 361 = **+11** (분해):
- `test_skeleton_car.py`: 7 (car 6-모듈 / run callable / fetcher·writer·enrich·validator 함수 존재 / DB path 배선)
- `test_pipeline_skeleton.py`(61-03, 기준선 측정에 미포함분): 4 (senior/rap 6-모듈 + run callable)
- 합계 = 11 ✓

**신규 skeleton 테스트 (내 작업 순수 기여):** `tests/shared/test_skeleton_car.py` → **7 passed** (격리 확인).
`--ignore=tests/shared/test_skeleton_car.py` 시 → **21 failed, 354 passed, 1 skipped** (즉 내 변경은
순수 +7 통과, 실패 21건 불변).

---

## 커밋 해시 (Deliverable 4 — D-08 구조/동작 분리)

| 커밋 | 해시 | 내용 | 유형 |
|------|------|------|------|
| A | `08e74188f` | feat(phase-61): add car standard-skeleton wrappers (fetcher/writer/enrich/validator) | 구조 추가 |
| B | `e3259ba2a` | refactor(phase-61): centralize car DB path via shared/db.py | 구조/유틸 (DB path) |
| C | `2a9488a8b` | test(phase-61): add car skeleton presence test | 테스트 추가 |

구조(신규 모듈), 유틸(DB path), 테스트를 별도 커밋으로 분리 (D-08). 커밋 내 `data/*.db` 변경 0건
(`git diff --name-only HEAD~3 HEAD | grep '^data/'` → NONE).

---

## Review 보정 적용 확인 (Deliverable 5)

| Review 항목 | 적용 여부 | 근거 |
|------------|-----------|------|
| car는 CAR_DB_PATH(pipeline.py:26) + DB_PATH(daily_refresh.py:18) 둘 다 보유. RAP만 아니라 car도 인라인 상수 | **[적용]** | `CAR_DB_PATH = Path(get_db_path("car"))`로 중앙화, `daily_refresh.py:18 DB_PATH`는 인라인 유지 (61-09 보고 항목으로 남김). |
| car wrapper는 pass-through placeholder로 명시 (fetcher/writer 제외, enrich는 placeholder) | **[적용]** | enrich docstring에 placeholder 명시. fetcher는 data_builder 위임, writer는 shared.ai_writer 위임, validator는 shared.validators 위임 — 기존 로직 위임, 재작성 아님. |
| D-01 additive + 기존 모듈 보존 | **[적용]** | 기존 car 모듈 1줄도 제거 없음. run() 본문 불변. daily_refresh/data_builder/title_engine/topic_manager 무수정. |
| AdSense Publisher ID (8772/6677/5938) | **[무관/미접촉]** | 광고 파일 접촉 없음. 위반 없음. |
| 배포는 dispatcher.py 경유 | **[무관/미접촉]** | 배포 없음 (code-only). 수동 wrangler 미실행. |
| 신규 third-party 패키지 0개 | **[준수]** | stdlib + 기존 모듈만 사용. 설치 없음. |

---

## 검증 상태 (3분법)

- **[검증됨]** 신규 실패 0건: 구현 후 실패 21건 nodeid 집합이 기준선과 동일 (21 건 동일 파일·테스트).
- **[검증됨]** car skeleton 테스트 7 passed (격리: `pytest tests/shared/test_skeleton_car.py -q` → 7 passed).
- **[검증됨]** car DB path 동일 해석: `str(pipeline.CAR_DB_PATH) == get_db_path("car")` → `True`
  (`/Users/twinssn/Projects/5000/data/car.db`).
- **[검증됨]** wrapper AST + import + 함수 존재: `ast.parse` OK, `from pipelines.car import fetcher,
  writer, enrich, validator` 성공, `hasattr(fetch_data/write_article/enrich_content/validate_post)`
  전부 `True`.
- **[검증됨]** `data/*.db` 무이동: 커밋 diff에 `data/` 변경 0건. (`data/content.db.*` 4건은 사전
  존재하던 untracked 복구 백업 — 내 작업과 무관.)
- **[검증됨]** 커밋 3개 존재 (구조/유틸/테스트 분리, D-08).
- **[검증됨]** `run(blog_cfg)` 본문 불변: pipeline.py diff가 import 1줄 + CAR_DB_PATH 상수값 교체
  1줄뿐 (2 insertions, 1 deletion).
- **[부분검증]** car `run()` 실제 실행 반환 dict — run()은 live 서비스(API/DB)를 필요로 해 직접
  호출하지 않음. **구조적으로 본문 불변 + DB path 동일 문자열/타입**으로 보존을 검증했으나,
  런타임 실행까지는 커버하지 않음 (스모크 테스트는 run() 미호출 의도).
- **[검증불가]** 없음.

---

## 잔존 위험

1. **런타임 발행 동작 미실행 확인**: run() 호출이 live API/DB를 필요로 해 실제 발행 경로를 실행으로
   검증하지 못함. 구조·path 동일성으로 보존을 보증하나, 실제 파이프라인 런은 스케줄러의 다음 발행
   주기에서 자연 검증됨.
2. **wrapper 미소비 상태**: 신규 4개 wrapper는 골격 존재를 위해 추가됐고 아직 pipeline.run()이 호출하지
   않음 (비파괴 원칙상 기존 경로 유지). rollout 및 scaffold(61-09)에서 소비 예정. 소비 전까지는
   의도된 placeholder로 남음.
3. **enrich placeholder**: car enrich가 원문 그대로 반환 — 실제 본문 정제는 topic_manager.validate_body()
   에서 수행 중이라 기능 손실 없음. 향후 enrich 단계를 모듈로 승격 시 재배선 필요.
4. **daily_refresh.py:18 DB_PATH 인라인 잔존**: 이번에 중앙화하지 않음 (동작 무손실 목적). 61-09
   dead-code 보고에서 목록화 예정 — 신규 위험 아님, 의도된 보류.
5. **잔존 위험: 없음** (구조적 데이터 변경, DB mutation, 배포, 광고 매핑 변경 전혀 없음).

---

## Output

본 SUMMARY 작성 완료. Stage D1 (CAP/car rollout 첫 단계) 완료 — car 표준 골격 6-모듈 완비.
61-03에서 검증된 전환 패턴(얇은 wrapper + DB path 중앙화 + skeleton 테스트 + 분리 커밋)을
car에 안전하게 적용. 이후 rollout(61-05 travel / 61-06 curation / 61-07 ETAP)에 동일 패턴 적용 대기.
