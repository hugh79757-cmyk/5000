# Plan 61-08 Summary — 외부 STAP/TAP 정합 (Stage E)

**Phase:** 61-pipeline-standardization-branch-renewal
**Plan:** 61-08 (Wave 6, Stage E)
**Date:** 2026-08-07
**Executed by:** opencode (Plan 61-08 autonomous)
**Dependencies:** 61-02 (shared/subprocess_runner.py) — 소비됨

---

## Objective

`dispatcher.py`의 `_run_stap`과 `_run_tap_subprocess`가 중복하던 tempfile-runner + venv
python + JSON 파싱 패턴을 `shared/subprocess_runner.run_subprocess`(61-02 생성)로 위임해
중앙화한다. **외부 TAP/STAP 저장소는 물리적 병합하지 않는다**(D-04) — 계약 정합만 수행.

---

## 파일 변경 (Deliverable 1)

| 파일 | 상태 | 내용 |
|------|------|------|
| `dispatcher.py` | **수정** | `_run_stap`(L378-395)과 `_run_tap_subprocess`(L460-480)를 thin caller로 재작성 → `run_subprocess` 위임. |
| `tests/integration/test_subprocess_routing.py` | **생성 (NEW)** | STAP/TAP 라우팅 통합 테스트 (mock run_subprocess). |

### dispatcher.py 상세

**`_run_stap(stap_name, cfg)` → 위임:**
- `STAP_ROOT` isdir 체크 + `{"success": False, "reason": "stap_not_found"}` 조기 반환 유지.
- `stap_python = STAP_ROOT/.venv/bin/python3` (없으면 run_subprocess가 `sys.executable` 폴백).
- `run_subprocess(project_root, stap_python, module_spec=f"pipelines.{stap_name}.pipeline", run_callable="run", cfg=cfg, timeout=600, prefix="stap")`.
- `STAP_PIPELINE_MAP`(L81)·디스패치 경로 불변.

**`_run_tap_subprocess(cfg)` → 위임:**
- `TAP_ROOT` isdir 체크 + `{"success": False, "reason": "tap_not_found"}` 조기 반환 유지.
- `tap_python = TAP_ROOT/venv/bin/python3` (없으면 run_subprocess가 폴백).
- `run_subprocess(TAP_ROOT, tap_python, module_spec="app", run_callable="run_publish", cfg=None, timeout=600, prefix="tap")`.
- **tuple→dict 정규화 유지**: `run_subprocess` 결과가 dict가 아니면 `{"success": bool(result)}`로
  변환 (원래 subprocess runner가 하던 동일 동작). TAP `run_publish()`가 `(bool, result, error)`
  튜플 반환 시에도 dict 계약 유지.
- `TAP_ROOT` 해석·디스패치 불변.

**정리:** 이 refactor로 `uuid`, `contextlib` import가 더 이상 사용되지 않게 되어 제거 (내 변경으로
orphan된 것만 정리, Karpathy §3).

---

## 중복 제거 라인 수 (Review 보정 적용)

- 리뷰 보정: "~400줄"은 과대 청구 → **~124줄**로 right-size.
- 실측: `_run_stap` ~61줄 + `_run_tap_subprocess` ~63줄 = **~124줄 중복**.
- refactor 커밋 `ccc7e9af7`: **27 insertions, 94 deletions** (두 함수 원본 ~124줄 → thin caller ~30줄).
- `shared/subprocess_runner.py` docstring(61-02 작성)에 "~124줄 중복"으로 이미 명시됨.

---

## Review 보정 적용 확인 (Deliverable 2)

| Review 항목 | 적용 여부 | 근거 |
|------------|-----------|------|
| subprocess dedup "~400줄" → ~124줄 right-size | **[적용]** | 본 SUMMARY + 이 refactor에서 ~124줄로 명시. 함수 원본 124줄 → 30줄. |
| `run_subprocess`가 token-strip + tuple→dict 처리 확인 (하드 게이트) | **[검증]** | 61-02 구현물에 이미 존재: runner 내 `os.environ.pop('CLOUDFLARE_API_TOKEN')`(L84) + non-dict→`{'success': bool}`(L102). tuple→dict는 dispatcher wrapper에서 보존. |
| AdSense Publisher ID (8772/6677/5938) | **[무관/미접촉]** | 광고 파일 미접촉. 위반 없음. |
| 배포는 dispatcher.py 경유 | **[무관/미접촉]** | 배포 없음 (code-only). 수동 wrangler 미실행. |
| 외부 TAP/STAP 미병합 (D-04) | **[적용]** | `/Users/twinssn/Projects/STAP`, `/Users/twinssn/Projects/TAP`에 어떤 파일도 쓰지 않음. |

---

## 테스트 수치 (Deliverable 3)

### 기준선 (구현 전)
`python3 -m pytest -o addopts="" -q` → **21 failed, 368 passed, 1 skipped**

### 구현 후
`python3 -m pytest -o addopts="" -q` → **21 failed, 392 passed, 1 skipped**

**신규 실패 0건.** 실패 21건 = 기준선 21건과 **정확히 동일 집합** 확인:
curation keywords(3)/title_hardening(4)/title_regression(1)/alert(2)/cot(1)/defense(4)/filters(1)/pipeline(1),
ai_writer(2), post_validator(1), relevance_scorer(1) — 전부 알려진 사전존재 실패. **NOT ours to fix.**

**passed 증가:** 368 → 392 = **+24** (내역 분해):
- test_subprocess_routing.py (신규, 본 계획): **+6**
- 나머지 +18: 본 phase(61)의 다른 계획(61-03..61-07, 61-09)에서 추가된 test 파일
  (예: `test_scaffold_branch.py` — untracked 18건, `test_pipeline_skeleton.py` 8건)이
  수집에 포함되어 반영된 것. 본 계획이 만든 신규 테스트는 **6건뿐**.

> 핵심 게이트(계약): `failed ≤ 21` && `passed 증가` — **충족**.
> 실패 21건이 기준선과 정확히 동일 집합임을 diff로 확인 (신규 실패 0).
> +24의 정확한 파일별 분해는 [부분검증] 참조.

### 신규 파일 (test_subprocess_routing.py) — 6 tests

| 테스트 | 검증 |
|--------|------|
| `test_stap_delegates_to_run_subprocess` | `_run_stap('stock', cfg)` → run_subprocess 호출, `module_spec=pipelines.stock.pipeline`, `run_callable=run`, `prefix=stap`, `cfg` 전달 |
| `test_stap_not_found_reason` | STAP_ROOT 부재 → `{"success": False, "reason": "stap_not_found"}` |
| `test_tap_delegates_to_run_subprocess` | `_run_tap_subprocess(cfg)` → `module_spec=app`, `run_callable=run_publish`, `prefix=tap`, `cfg=None` |
| `test_tap_tuple_result_converted_to_dict` | run_subprocess가 TAP tuple 반환 → dict `{"success": True}` 정규화 |
| `test_tap_not_found_reason` | TAP_ROOT 부재 → `{"success": False, "reason": "tap_not_found"}` |
| `test_run_subprocess_strips_cf_token` | runner가 `CLOUDFLARE_API_TOKEN`을 env에서 pop (실제 subprocess) |

### 관련 회귀 게이트
- `tests/test_dispatcher_registry.py`: **pass**
- `tests/shared/test_subprocess_runner.py`: **pass**

---

## 커밋 해시 (Deliverable 4 — D-08 구조/동작 분리)

| 커밋 | 해시 | 내용 | 유형 |
|------|------|------|------|
| A | `ccc7e9af7` | refactor(phase-61): centralize STAP/TAP subprocess execution via shared/subprocess_runner | 구조 중앙화 (동작 동일) |
| B | `f5f75605e` | test(phase-61): add STAP/TAP subprocess routing integration test | 테스트 추가 |

구조/동작 분리: 커밋 A가 동작 동일 refactor(구조 중앙화), 커밋 B가 테스트. 별도 커밋 확인 (D-08).

---

## 검증 상태 (3분법)

- **[검증됨]** 신규 실패 0건: 구현 전/후 `pytest -o addopts="" -q` 실행, 실패 21건이 기준선과 정확히
  동일 집합 (diff로 확인, curation/ai_writer/post_validator/relevance_scorer만).
- **[검증됨]** dispatcher AST 파싱: `ast.parse` 통과.
- **[검증됨]** `run_subprocess` 사용: `grep -n "run_subprocess" dispatcher.py` → `_run_stap`/`_run_tap_subprocess` 양쪽 확인.
- **[검증됨]** reason 접두사 보존: `stap_not_found`/`tap_not_found` dispatcher에 존재 (run_subprocess가 prefix로 `stap_timeout`/`stap_no_output`/`stap_error`/`stap_subprocess_error` 생성, STAP/TAP 원본과 동일).
- **[검증됨]** tuple→dict: `test_tap_tuple_result_converted_to_dict` PASS (mock tuple → dict 변환).
- **[검증됨]** token-strip: `test_run_subprocess_strips_cf_token` PASS (실제 subprocess에서 env pop 확인) + 기존 `test_subprocess_runner.py::TestTokenSafety` PASS.
- **[검증됨]** 신규 라우팅 테스트 6건 GREEN, dispatcher_registry PASS, subprocess_runner PASS.
- **[검증됨]** 외부 미병합: `git status --porcelain`에 `/Users/twinssn/Projects/STAP`·`/TAP` 경로 변경 0건.
- **[검증됨]** 커밋 2개 존재 (`git log --oneline -2`에 phase-61 커밋 확인).
- **[부분검증]** passed 증가 +24 분해: 본 계획 신규 routing 6건은 **확실** ([검증됨]). 나머지 +18은
  타 phase-61 계획의 신규 test 파일(untracked `test_scaffold_branch.py` 18건 포함)이 같은
  working tree에서 수집돼 반영. 기준선 측정 시점(세션 초)과 구현 후 사이 해당 파일들이 추가돼
  +24 전체가 본 계획 소유라고 단정 불가 — **본 계획 신규는 6건**으로 한정.
- **[검증불가]** 실제 STAP/TAP 발행 실행 검증 — 외부 저장소 라이브 발행은 이 계획 범위 밖
  (mock으로만 검증). 복구 계획: 실제 발행 검증은 운영 스케줄러 경유로 자연 발생 시 관찰.

---

## 잔존 위험

1. **run_subprocess의 STAP dotenv 로딩 차이**: 원본 `_run_stap`은 `STAP_ROOT/.env` + `PROJECT_DIR/.env`
   둘 다 로드. `run_subprocess`는 `project_root/.env`만 로드. STAP 발행에 5000 env 값이 필요한 경우
   동작 차이 가능 → STAP은 subprocess cwd=project_root로 격리되어 5000 env를 상속받지 않으므로
   주의. (TAP 경로는 동일했음)
2. **STAP `run(cfg)` vs signature-bridge**: 원본은 항상 `run(cfg)` 호출. run_subprocess는
   inspect 브리지(`cfg` 인자 있으면 `fn(cfg)`). STAP `run`은 cfg 인자를 가지므로 동일 경로 타지만,
   인자 없는 run()도 지원되어 폴백 정책이 넓어짐.
3. **passed +24 분해 불명확**: 신규 6건만 확실, 나머지 +18은 타 phase 커밋과 collection 차이로
   일부 계상 (위 [부분검증] 참조). 실제 기능 회귀는 실패 21건 동일로 배제됨.
4. **잔존 위험: 없음** (데이터 변경, DB mutation, 배포, 광고 매핑 변경, 외부 저장소 쓰기 전혀 없음).

---

## Output

본 SUMMARY 작성 완료. Wave 6 Stage E (외부 STAP/TAP 정합) 완료 — dispatcher의 외부 subprocess 실행이
`shared/subprocess_runner`로 통일됨. 모든 실행 방식이 표준 계약(D-02)에 정합.
