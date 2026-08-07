# Plan 61-09 Summary — 온보딩 도구 + 레거시 정리 (Stage F)

**Phase:** 61-pipeline-standardization-branch-renewal
**Plan:** 61-09 (Wave 6, Stage F)
**Date:** 2026-08-07
**Executed by:** opencode (Plan 61-09 autonomous)
**Dependencies:** 61-01 (PIPELINE-STANDARD), 61-02 (shared/db.py) — 소비됨

---

## Objective

새 파이프라인 분기 생성을 자동화하는 온보딩 도구 `scripts/scaffold_branch.py`(D-05)를 만들어
ETAP 35쌍 같은 수동 복제를 근절한다. 레거시(`.bak` 파일, 인라인 DB 상수)는 **보고서로만 식별** —
실제 삭제는 별도 승인 필요(파괴적 작업 규칙, destructive-ops).

본 plan은 **아무 `.bak`/코드/DB 를 삭제·수정하지 않는다.** 신규 파일 생성 + 보고서 2건뿐.

---

## 파일 변경 (Deliverable 1)

| 파일 | 상태 | 내용 |
|------|------|------|
| `scripts/scaffold_branch.py` | **생성 (NEW)** | 표준 6-모듈 골격 + config 템플릿 + DB 경로 배선 자동 생성 (D-05) |
| `tests/shared/test_scaffold_branch.py` | **생성 (NEW)** | 분기명 검증 + 골격 생성 + import 검증 (Wave-0, 18 tests) |
| `.planning/.../61-F-LEGACY-CLEANUP-REPORT.md` | **생성 (NEW, report-only)** | `.bak` 59건 인벤토리, 삭제 DEFERRED |
| `.planning/.../61-F-DEAD-CODE-REPORT.md` | **생성 (NEW, report-only)** | 인라인 DB 상수 식별, 삭제 없음 |

---

## `scripts/scaffold_branch.py` 기능

- **분기명 검증**: `^[a-z][a-z0-9_]*$` (`re.fullmatch`) — `../evil`, `a b`, `with.dot`,
  `Uppercase`, `has/hyphen`, `1startsDigit`, `""` 전부 `ValueError` (threat T-61-09-01,
  경로/모듈 주입 방지).
- **표준 골격 생성**: `pipelines/{branch}/` 에 `__init__.py` + 6모듈
  (`pipeline/fetcher/topic_manager/writer/enrich/validator`) 생성.
- **`run(cfg) -> dict` 계약**: 생성된 `pipeline.py` 는 `def run(cfg)` 를 표준 순서
  (fetcher → topic_manager → writer → enrich → validator)로 오케스트레이션하고
  `{"success": False, "reason": "no_topic"}` placeholder 반환.
- **DB 경로 배선 (D-06)**: `from shared.db import get_db_path` 사용, 인라인 하드코딩 경로 없음.
  신규 분기가 아직 `shared/db.py::_BRANCH_DB` 에 없어도 import 가 깨지지 않도록 DB 경로는
  `run()` 안에서 lazy + 안전(fallback None)하게 해석.
- **config 템플릿**: `config/blogs.d/{branch}.yaml` 생성 — 표준 필수/표준 필드
  (`id/pipeline/platform/name/domain/daily_quota/schedule/status`) + `managed_by: pipeline`.
- **refuse-overwrite**: `pipelines/{branch}/` 가 이미 존재하면 `FileExistsError` (T-61-09-02).
- **--dry-run**: 실제 파일을 쓰지 않고 예상 생성 항목만 출력.
- **CLI**: `python scripts/scaffold_branch.py --branch <name> [--base-dir] [--config-dir] [--dry-run]`.

**중요 명시:** scaffold된 분기는 **import-verifiable** (테스트로 입증) 이지만
**end-to-end 발행 검증은 아님** — fetch/write/validate 가 전부 placeholder 이므로
실제 네트워크/DB/발행 경로는 실행하지 않는다 (PIPELINE-STANDARD §2.2 "placeholder로 명시").

---

## `.bak` 인벤토리 (Deliverable 2) — 실제 수치

실측: `find . -name "*.bak*" -not -path "./.git/*" | wc -l` = **59** (플랜 명시 59와 일치).

| 디렉터리 | 건수 |
|----------|-----|
| `config/blogs.d/` | 16 |
| `public/posts/**/` | 16 |
| `data/` | 7 |
| `pipelines/curation/` | 5 |
| `pipelines/rap/` | 4 |
| `pipelines/travel/` | 4 |
| `config/` | 3 |
| `shared/publishers/` | 2 |
| `shared/` | 1 |
| 루트 `/` | 1 |
| **합계** | **59** |

- **git 추적 여부**: `git ls-files | grep .bak` = **0건** → 전부 untracked 수동 스냅샷.
- **총 크기**: ~46.3 MB (대부분 `data/content.db.bak_20260806_202605` 43.4MB).
- **삭제 실행**: **안 함.** 보고서에 권장 정리 목록(우선순위 1~5)을 제시하되 전부
  **DEFERRED / 별도 승인 필요**로 표시. `content.db` `source=''` 실발행 행 영구 보존 규칙 명시.
- **자동검증**: 보고서에 `DEFERRED|별도` 포함 `grep -c` = 7.

---

## Dead-Code 보고서 (Deliverable 3) — 내용 요약

`grep -rn "_DB_PATH\s*=\|DB_PATH\s*=" pipelines/ shared/` 실측, 각 상수 3분류:
**[중앙화됨]** / **[인라인-대체후보]** / **[비대체]**.

**인라인-대체후보 (get_db_path() 로 치환 가능, 미래 제거 후보) 총 6개:**

| 분기 | 파일:라인 | 상수 |
|------|-----------|------|
| car | `daily_refresh.py:18` | `DB_PATH` → car.db |
| rap | `rap_data_sync.py:24` | `RAP_DB_PATH` → rap.db |
| curation | `auto_collector.py:32` | `DB_PATH` → curation.db |
| curation | `collector.py:50` | `DB_PATH` → curation.db |
| curation | `keyword_expander.py:26` | `DB_PATH` → curation.db |
| curation | `naver_datalab_sync.py:31` | `DB_PATH` → curation.db |

**이미 중앙화됨 (배선 확인, 삭제 아님):** car/pipeline.py:27, rap/pipeline.py:22,
senior/fetcher.py:143, curation/pipeline.py:96.

**비대체 (중앙화 범위 밖):** rap `GAP_DB_PATH`(gap.db, `get_db_path()` 미매핑 · 의도적 유지),
curation `keyword_health`(상수 없음, 생성자 인자), stock(`stock.db` ≠ `get_db_path("stock")`→stap_content.db),
**etap**(전부 `travel-en.db` 로 `get_db_path()` 대체 불가), **travel**(인라인 상수 0개).

**명시:** `shared/db_paths.py` 는 확장해 유지 (replace 금지, D-06/D-08). 본 plan 에서 코드 삭제 없음.
**자동검증:** 보고서에 `get_db_path|shared/db.py` 포함 `grep -c` = 23.

---

## Review 보정 적용 확인 (Deliverable 4)

| Review 항목 | 적용 여부 | 근거 |
|------------|-----------|------|
| car: CAR_DB_PATH(pipeline.py:27) + DB_PATH(daily_refresh.py:18) | **[적용]** | 두 상수 열거 (각각 중앙화됨 / 인라인-대체후보). |
| rap: RAP_DB_PATH + GAP_DB_PATH | **[적용]** | 열거 (중앙화됨 / 비대체-gap). |
| senior: SENIOR_DB_PATH(fetcher.py) | **[적용]** | 열거 (중앙화됨). |
| curation: 6개 상수 | **[부분적용 → 실측 보정]** | **인라인-대체후보는 실측 4개.** `pipeline.py:96` 은 이미 `get_db_path()`(중앙화됨), `keyword_health.py:21` 은 **docstring 예시일 뿐 상수 아님**(상수 0개). 6개가 아니라 4개임을 보고서에 명시. |
| travel / etap 인라인 DB 상수 없음(함의 금지) | **[적용]** | travel: `*_DB_PATH` 0개. etap: `DB_PATH` 할당 72개 / `travel-en.db` 참조 144개가 있으나 전부 `get_db_path()` 대체 불가 → 중앙화 범위 밖으로 서술, "etap 이 dead code" 함의 금지. |
| scaffold 보고: import-verifiable 이지 end-to-end 아님 | **[적용]** | 본 SUMMARY + 코드 주석에 명시 (placeholder 전용). |
| `.bak` 실수 확인 (59) | **[적용]** | 실측 59로 검증. |

---

## 테스트 수치 (Deliverable 5)

### 기준선 (구현 전)
`python3 -m pytest -o addopts="" -q` → **21 failed, 368 passed, 1 skipped**

### 구현 후
`python3 -m pytest -o addopts="" -q` → **21 failed, 392 passed, 1 skipped**

**신규 실패 0건.** 실패 21건 = 기준선 21건과 **정확히 동일 집합**:
curation keywords/title_hardening/title_regression/alert/cot_threshold/defense_layers/filters/pipeline,
ai_writer(2), post_validator, relevance_scorer — 전부 알려진 사전존재 실패. **NOT ours to fix.**

**passed 증가:** 368 → 392 = **+24** (분해):
- 본 계획 신규 `test_scaffold_branch.py`: **+18**
- 61-08 신규 `test_subprocess_routing.py` (같은 wave, 이미 커밋): **+6**
- 합 = +24. 본 plan 소유 신규 테스트는 **18건** ([검증됨]).

### 신규 테스트 (test_scaffold_branch.py) — 18 tests

| 클래스 | 테스트 | 검증 |
|--------|--------|------|
| TestScaffoldCreatesSkeleton | `test_scaffold_creates_skeleton` | 6모듈 + `__init__.py` 생성 |
| | `test_scaffold_creates_config_template` | config 필수 9개 필드 + `managed_by: pipeline` |
| | `test_scaffold_wires_db_path` | `from shared.db import get_db_path` + `get_db_path(` 포함 |
| TestScaffoldValidatesBranchName | `test_rejects_invalid_names` (parametrize 7) | `../evil` 등 7개 → `ValueError` |
| | `test_accepts_valid_names` (parametrize 4) | car/rap2/my_branch/x 생성 성공 |
| TestScaffoldOverwriteAndDryRun | `test_refuses_overwrite_existing_dir` | 기존 dir → `FileExistsError` |
| | `test_dry_run_writes_nothing` | dry-run 시 파일 미생성 |
| TestScaffoldedPipelineImport | `test_scaffolded_pipeline_imports_and_run_returns_dict` | 생성 골격 import + `run(cfg)` dict 계약 + `_resolve_db_path() is None` |
| | `test_scaffold_generates_run_contract` | `def run(cfg):` 존재 |

- `test_scaffold_branch.py`: **18 passed**
- `tests/shared/test_scaffold_branch.py` 최종: `18 passed` (GREEN)
- `python3 -c "import ast; ast.parse(...)"` → `AST OK`
- CLI smoke: `--dry-run` 정상 출력, `bad/name` → `ValueError` + exit 1

---

## 커밋 해시 (Deliverable 6 — D-08 구조/동작 분리)

| 커밋 | 해시 | 내용 | 유형 |
|------|------|------|------|
| A | `11399cc47` | feat(phase-61): add scripts/scaffold_branch.py (standard-skeleton branch generator) | 기능 (스캐폴드 + 테스트) |
| B | `443f51c3f` | docs(phase-61): add .bak legacy cleanup inventory report (deletion deferred) | 보고서 |
| C | `959a2dabd` | docs(phase-61): add dead-code report for inline DB constants superseded by shared/db.py | 보고서 |

세 커밋이 각각 분리되어 `git log --oneline -3` 로 확인 (D-08).

---

## 검증 상태 (3분법)

- **[검증됨]** 신규 실패 0건: 구현 전/후 `pytest -o addopts="" -q`, 실패 21건이 기준선과 정확히
  동일 집합 (diff로 확인, curation/ai_writer/post_validator/relevance_scorer만).
- **[검증됨]** `test_scaffold_branch.py` 18건 GREEN (`18 passed`).
- **[검증됨]** scaffold AST: `python3 -c "import ast; ast.parse(...)"` → `AST OK`.
- **[검증됨]** 분기명 검증: `re.fullmatch` 존재 + `--branch bad/name` CLI 가 `ValueError`+exit 1.
- **[검증됨]** 6-모듈 생성: temp-dir smoke가 `__init__/enrich/fetcher/pipeline/topic_manager/validator/writer` 전부 생성.
- **[검증됨]** refuse-overwrite + dry-run: `FileExistsError` / 파일 미생성 각각 테스트 PASS.
- **[검증됨]** `.bak` 실측 59: `find ... | wc -l` = 59, git 추적 0건 (`git ls-files`).
- **[검증됨]** dead-code 실측: 인라인-대체후보 6개, 중앙화 4개, 비대체 군 분류. curation 보정(6→4) 반영.
- **[검증됨]** `.bak`/코드 미삭제: `git status --porcelain` 에 `.bak` 삭제·파이프라인 코드 변경 0건.
- **[검증됨]** 커밋 3개 분리: `git log --oneline -3` (feature / report / report).
- **[부분검증]** passed +24 분해: 신규 18건(본 plan) + 6건(61-08) — 61-08 은 이 plan 소유가 아니므로
  본 plan 신규는 18건으로 한정. 기준선(세션 초)과 구현 후 사이 다른 phase-61 커밋들이 수집에
  포함됐을 수 있어 전체 +24 소유 단정은 불가.
- **[검증불가]** scaffold 분기 end-to-end 발행 검증 — fetch/write/validate placeholder 라
  실제 발행 경로는 실행하지 않음 (설계상). 복구 계획: 실제 발행은 새 분기 구현 후 운영
  스케줄러 경유로 자연 검증.

---

## 잔존 위험

1. **scaffold 분기 end-to-end 미검증**: 생성 골격은 import·run() 계약만 검증. 실발행 로직
   (LLM 폴백, 이미지, 배포)은 새 분기 구현 후 별도 검증 필요.
2. **신규 분기 DB 미등록**: scaffold 는 `shared/db.py` 를 import 하지만 신규 분기를
   `_BRANCH_DB` 에 자동 등록하지 않음 → `_resolve_db_path()` 가 None 반환. 분기 활성화 시
   `shared/db.py` 등록 작업이 추가로 필요 (보고서에는 기록, 자동화 안 함).
3. **curation 인라인 상수 4개**: 중앙화로 치환하면 동작은 동일하지만, 기존 코드의 `BASE_DIR`
   계산과 `get_db_path()`(프로젝트 루트 기준)가 실제로 같은 파일을 가리키는지 치환 전 재확인 필요.
4. **stock `stock.db` vs `stap_content.db`**: `get_db_path("stock")` 은 `stap_content.db` 를
   반환하므로 stock 의 인라인 `stock.db` 상수를 무단 치환하면 경로가 바뀜 — 계약 정합 범위 밖,
   별도 판단 필요.
5. **`.bak` 삭제**: 본 plan 에서 수행 안 함. 별도 Phase 승인 후 4단계 프로토콜로만 가능.
   `content.db` `source=''` 실발행 행 보존 최우선.
6. **잔존 위험: 없음** (DB mutation, wrangler 배포, AdSense ID 변경, 외부 저장소 쓰기 전혀 없음).

---

## Output

본 SUMMARY 작성 완료. Wave 6 Stage F (온보딩 도구 + 레거시 정리) 완료 — `scaffold_branch.py` 로
새 분기를 표준 골격으로 즉시 생성 가능, `.bak`/인라인 DB 상수는 보고서로만 식별.
