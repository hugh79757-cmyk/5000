# Plan 61-06 Summary — curation(CUAP) 표준 골격 전환 (Stage D3)

**Phase:** 61-pipeline-standardization-branch-renewal
**Plan:** 61-06 (Wave 4, Stage D3 — curation, CUAP 15 blogs)
**Date:** 2026-08-07
**Executed by:** opencode (Plan 61-06 autonomous)
**Dependencies:** 61-02 (shared/db.py) — 적용됨

---

## Objective

가장 큰 분기 curation(67KB pipeline.py, CUAP 15 블로그)을 표준 6-모듈
골격(pipeline/fetcher/topic_manager/writer/enrich/validator)에 정렬. 부재 모듈만
얇은 wrapper로 추가하고, 기존 모듈은 유지·배선하며, DB path를 `shared/db.py`로 중앙화.
모든 변경 additive + 비파괴, 구조/동작 분리 커밋(D-08).

---

## 파일 생성/배선 (Deliverable 1)

### 신규 wrapper (pass-through placeholder, D-01 additive)

| 파일 | 제공 함수 | 위임/성격 |
|------|-----------|-----------|
| `pipelines/curation/fetcher.py` | `fetch_data(cfg) -> list` | **pass-through placeholder** — 기존 `collector.collect_keyword()` + `get_products()` 위임 |
| `pipelines/curation/topic_manager.py` | `select_topic(cfg)` | **pass-through placeholder** — 기존 `pipeline._select_keyword()` 위임 |
| `pipelines/curation/validator.py` | `validate_post(cfg, article) -> (ok, errors)` | `shared.validators.validate_post()` 위임 |
| `pipelines/curation/enrich.py` | `enrich_content(cfg, products)` | **신규 표준 이름** — 기존 `enricher.enrich_products` 배선 |

> **설계 결정 (파일 목록 보정):** 플랜 must_have "curation exposes the standard
> 6-module skeleton (pipeline/fetcher/topic_manager/writer/**enrich**/validator)" 는
> 표준 이름 `enrich` 모듈을 요구한다. curation은 `enricher.py`만 존재해 표준 이름과 불일치.
> 플랜 key_link "existing enricher preserved and wired to the **enrich** module" 에 따라
> 표준 이름 `enrich.py`(thin wrapper)를 추가해 기존 `enricher.py`를 유지한 채 배선했다.
> `files_modified` frontmatter는 이 파일을 나열하지 않았으나, must_have가 우선임을 판단해 추가.
> **기존 `enricher.py`는 1줄도 수정하지 않음** (유지, D-01).

### DB path 배선 (D-06, additive — 파일 무이동)

| 파일 | 변경 | 성격 |
|------|------|------|
| `pipelines/curation/pipeline.py` | `DB_PATH = Path(get_db_path("curation"))` | `shared/db.py` 중앙 해석 + `from shared.db import get_db_path` import 추가 |

- `Path(get_db_path("curation"))` 가 기존 `PROJECT_DIR / "data" / "curation.db"` 와
  **경로·타입 모두 동일**함을 확인 (`== True`, 여전히 `Path` 타입).
- `DB_PATH`는 pipeline.py 내 14곳(`str(DB_PATH)` 13곳 + `get_adaptive_threshold(DB_PATH,...)` 1곳)에서
  사용. Path 타입을 유지해 **모든 사용처 동작 불변**.
- curation의 나머지 인라인 DB 상수(auto_collector.py:32, collector.py:50,
  keyword_expander.py:26, naver_datalab_sync.py:31, keyword_health.py:21)는 **인라인 유지** —
  61-09 dead-code 보고용으로 기록.

### 신규 테스트

| 파일 | 내용 |
|------|------|
| `tests/shared/test_skeleton_curation.py` (NEW) | 3 tests — curation 6-모듈 존재 + enricher 보존 + run() callable (pkgutil, run() 미호출) |

---

## 동작 보존 확인 (Deliverable 2 — draft-skip + run() dict 불변)

- **draft-skip 수정 보존 (commit 39f005084):** `pipelines/curation/pipeline.py:1273-1276`
  `if is_draft: register_cuap_entity 스킵` 로직이 그대로 존재. 이 commit은 phase-61 커밋들
  아래 히스토리에 유지되며, 내 diff는 import 1줄 + DB_PATH 1줄뿐이라 draft-skip 코드 미접촉.
- **`run(cfg)` 반환 계약 불변:** `def run(cfg)` (현재 line 837, import 추가로 +1 shift) 의
  반환 dict(`{"success": ..., "reason": ...}`) 본문은 **1줄도 수정하지 않음**.
- `git diff pipelines/curation/pipeline.py` = 정확히 2줄(import 추가, DB_PATH 값 교체). 그 외 무변경.

---

## 테스트 수치 (Deliverable 3 — 기준선 vs 구현 후)

### 기준선 (구현 전)
`python3 -m pytest -o addopts="" -q` → **21 failed, 361 passed, 1 skipped**

### 구현 후
`python3 -m pytest -o addopts="" -q` → **21 failed, 364 passed, 1 skipped**

**신규 실패 0건.** 실패 21건 집합을 `-rf`로 수집해 nodeid diff → 기준선 21건과 **동일** (아래 [검증됨]).

**passed 증가:** 361 → 364 = **+3** (분해):
- test_skeleton_curation.py: 3 (curation 6-모듈 / enricher 보존 / run callable)
- 합계 = 3 ✓ (합 일치)

**curation 서브셋:** `pytest tests/curation/ -o addopts="" -q` → **17 failed, 131 passed**.
17건 실패는 21건 기준선 중 curation 소속 pre-existing 실패(relevance/keywords/title_hardening/
cot/alert/filters)이며, 기준선과 동일 — 신규 회귀 아님.

---

## 커밋 해시 (Deliverable 4 — D-08 구조/동작 분리)

| 커밋 | 해시 | 내용 | 유형 |
|------|------|------|------|
| A | `a8e96f542` | feat(phase-61): add curation standard-skeleton wrappers (fetcher/topic_manager/validator/enrich) | 구조 추가 |
| B | `63ca50572` | refactor(phase-61): centralize curation DB path via shared/db.py | 구조/유틸 (DB path) |
| C | `64ba04fe3` | test(phase-61): add curation skeleton presence test | 테스트 추가 |

구조(신규 모듈), 유틸(DB path), 테스트를 별도 커밋으로 분리 (D-08). 구조 vs 동작 분리 충족.

---

## Review 보정 적용 확인 (Deliverable 5)

| Review 항목 | 적용 여부 | 근거 |
|------------|-----------|------|
| wrapper는 pass-through placeholder로 명시 | **[적용]** | 4개 wrapper docstring에 placeholder/위임 대상 명시 |
| enricher.py 보존 + enrich 모듈 배선 | **[적용]** | `enricher.py` 미수정, `enrich.py`가 위임. 테스트로 보존 검증 |
| curation 인라인 DB 상수(6개) 인라인 유지 | **[적용]** | pipeline.py만 배선, 나머지는 그대로 (61-09 보고용) |
| D-01 additive + 기존 모듈 보존 | **[적용]** | 기존 pipeline/writer/enricher/collector 1줄도 제거 없음. run() 본문 불변 |
| AdSense Publisher ID (8772/6677/5938) | **[무관/미접촉]** | 광고 파일 접촉 없음. 위반 없음 |
| 배포는 dispatcher.py 경유 | **[무관/미접촉]** | 배포 없음 (code-only). 수동 wrangler 미실행 |

---

## 검증 상태 (3분법)

- **[검증됨]** 신규 실패 0건: `-rf`로 실패 21건 nodeid 수집 후 기준선과 nodeid diff → 동일 집합.
- **[검증됨]** passed +3: 361→364, 분해(3 skeleton tests) 합 일치.
- **[검증됨]** curation DB path 동일 해석: `Path(get_db_path("curation")) == PROJECT_DIR/"data"/"curation.db"` → `== True`, 타입도 `Path` 유지 확인.
- **[검증됨]** 4개 wrapper AST + import + 함수 존재: `ast.parse`, `from pipelines.curation import ...`
  → `fetch_data`/`select_topic`/`validate_post`/`enrich_content` 전부 `hasattr==True`.
- **[검증됨]** `data/*.db` 무이동: `git status --porcelain | grep data/` 에 tracked `.db` 변경 0건.
  (보이는 `data/content.db.*` 등은 사전부터 존재하던 untracked 복구 백업 — 내 작업과 무관.)
- **[검증됨]** draft-skip 보존: `pipeline.py:1273-1276` `if is_draft` 스킵 로직 존재, diff 미접촉.
- **[검증됨]** 커밋 3개 존재 (`git log --oneline`에 phase-61 curation 커밋 3건 확인).
- **[부분검증]** curation `run()` 실제 실행 반환 dict — run()은 live API/DB를 필요로 해
  직접 호출하지 않음. **구조적으로 본문 불변 + DB path 동일 문자열**로 보존을 검증했으나,
  런타임 실행까지는 커버하지 않음 (스모크 테스트는 run() 미호출 의도).

---

## 잔존 위험

1. **런타임 발행 동작 미실행 확인:** run() 호출이 live API/DB를 필요로 해 실제 발행 경로를
   실행으로 검증하지 못함. 구조·path 동일성으로 보존을 보증하나, 실제 파이프라인 런은 스케줄러의
   다음 발행 주기에서 자연 검증됨.
2. **wrapper 미소비 상태:** 신규 4개 wrapper는 골격 존재를 위해 추가됐고, 아직 pipeline.run()이
   호출하지 않음 (비파괴 원칙상 기존 경로 유지). rollout(61-07) 및 scaffold(61-09)에서 소비 예정.
   소비 전까지는 dead-ish 코드로 남음 (의도된 placeholder).
3. **curation 인라인 DB 상수 잔존:** pipeline.py 외 5개 모듈(auto_collector/collector/
   keyword_expander/naver_datalab_sync/keyword_health)의 인라인 `*_DB` 상수는 그대로 남음.
   DB 경로 전면 중앙화는 61-09 dead-code 보고에서 처리 예정 (본 플랜 스코프 밖, 의도적).
4. **잔존 위험: 없음** (구조적 데이터 변경, DB mutation, 배포, 광고 매핑 변경 전혀 없음).

---

## Output

본 SUMMARY 작성 완료. Stage D3 (curation) 완료 — CUAP 표준 골격 6-모듈 완비
(pipeline/fetcher/topic_manager/writer/enrich/validator), DB path 중앙화, 신규 테스트 3건 green,
회귀 0. 전환 패턴(얇은 wrapper + DB path 중앙화 + skeleton 테스트 + 분리 커밋)을 최대 분기에서 검증.
rollout(61-07 ETAP)에 동일 패턴 적용 대기.
