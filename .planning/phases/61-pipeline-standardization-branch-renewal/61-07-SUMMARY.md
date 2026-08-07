# 61-07 Summary — ETAP (35쌍) 단일화: run()→dict 계약 정규화 (최고 위험)

> phase: 61-pipeline-standardization-branch-renewal | plan: 07 (wave 5, D4)
> 실행자: opencode | 완료: 2026-08-07

## 목적 달성 (deliverables)

- **35/35** ETAP topic pipeline이 `run(cfg) -> dict` 표준 계약을 노출하도록 adapter wrapper 추가.
  기존 `run()` 진입 함수명은 보존하고(`_run_impl` 로 rename 후 새 `run()` adapter 위임), dispatcher `inspect.signature` 브리지 유지.
- `pipelines/etap/_contract.py` 신규 — `_normalize_result` 공용 헬퍼.
- ETAP 6-모듈 골격 완비: fetcher/enrich/validator skeleton wrapper 추가 (pipeline/topic_manager/writer는 기존 존재).
- `topic_manager.resolve_topic_pipeline(blog_id)` config-driven 수렴 기반 추가 (additive).
- `tests/shared/test_pipeline_skeleton.py`에 ETAP skeleton + 브리지 테스트 4건 추가.

## 사용한 시그니처 카운트 (검증됨)

| 시그니처 | 카운트 | dispatcher 호출 |
|---|---|---|
| `run()` (zero-arg) | **24** | `run()` |
| `run(cfg=None)` | **10** | `run(cfg)` |
| `run(cfg)` (flight) | **1** | `run(cfg)` |
| 합계 | **35** | — |

근거: `pipelines/etap/*_pipeline.py`(writer 제외, pipeline.py 제외)를 AST/regex로 전수 측정.
**61-REVIEWS.md 수정사항 #1 반영 (21/14가 아니라 24/10/1).**

## flight 정규화 결과 (Review #2)

`flight_pipeline.run(cfg)`의 `{"status": ...}` dict(success 키 없음)를 `_normalize_result`로 표준 `success`/`reason`로 정규화.

| status | → success | → reason |
|---|---|---|
| `ok` | True | `ok` |
| `skip` | False | `no_topic` |
| `error` | False | `generation_failed` |
| `draft` | False | `content_quality_gate` |
| `exhausted` | False | `daily_quota_reached` |
| `build_fail` | False | `deploy_error` |

- `flight.run_batch`은 내부에서 `_run_impl(cfg)`(원본 status dict)를 사용해 `result["status"]` 로직 유지(동작 보존). `__main__` 테스트 경로만 새 `run(cfg)` adapter(정규화 dict) 호출.
- `docs/PIPELINE-STANDARD.md §3.5`는 이미 "예외로 두지 않고 정규화"로 갱신되어 있음 — 별도 doc 수정 불필요 (re-view #2의 doc 요구 충족).

## dispatcher 브리지 보존 (검증됨)

- `git diff dispatcher.py` → **비어 있음** (`_ETAP_BLOG_EXCEPTIONS`, `_resolve_pipeline`, `inspect.signature`, `ETAP_PIPELINE_BLOGS` 무변경).
- smoke import: `python3 -c`로 35개 topic pipeline 전부 import, 실패 0.
- `inspect.signature` 분해 재확인: 24×`run()`, 10×`run(cfg)`, 1×flight `run(cfg)` → dispatcher가 올바른 경로 호출.

## 테스트 (검증됨)

- 기준선(before): `21 failed, 364 passed, 1 skipped`
- 종료(after): `21 failed, 368 passed, 1 skipped`
- `passed` +4 = ETAP skeleton/bridge 테스트 4건 추가. **신규 실패 0.** 21개 실패는 기존 baseline(relevance_scorer/ai_writer/post_validator/curation 계열)으로 이 plan의 범위 밖.
- `tests/shared/test_pipeline_skeleton.py`: 8 passed.

## 커밋 (D-08 구조/동작 분리, 검증됨)

| 해시 | 메시지 | 유형 |
|---|---|---|
| `53ce7f71e` | fix: repair misplaced hugo_writer import in 10 etap topic pipelines (syntax) | 구조 버그 수정 |
| `cbbae1418` | refactor: normalize ETAP topic run() return to standard dict contract | 동작 계약 정규화 (36파일) |
| `1e49bf48d` | feat: add etap skeleton wrappers + config-driven topic_manager convergence | 구조 추가 |
| `010f8d03f` | test: add etap skeleton presence test | 테스트 추가 |

## Review 수정사항 적용 확인

1. **시그니처 카운트 24/10/1** — 반영 (위 표). [검증됨]
2. **flight status-dict 정규화** — `_normalize_result` status 매핑 + §3.5 정규화 상태 문서 확인. [검증됨]
3. **간접 bool 반환** — `_run_impl` rename + 새 `run()` adapter가 `_normalize_result`로 모든 반환 형태(direct/indirect bool, None, int)를 정규화. 검증 테스트 `test_etap_topic_pipelines_expose_run_adapter`로 35개 전부 확인. [검증됨]
4. **6-모듈 골격 + `resolve_topic_pipeline`** — fetcher/enrich/validator 신규, topic_manager에 resolver 추가. import/동작 테스트로 확인. [검증됨]

## 실행 중 발견된 사전 결함 (위반 감지 → 별도 보고)

- **10개 topic pipeline** (citytours/escape/extreme/ghost/hiking/layover/luxury/nightlife/nomad/watertours)의 `entity_linker` import 괄호 안에 `from shared.publishers.hugo_writer import _write_hugo_post_etap as _write_hugo_post`가 잘못 삽입되어 **문법 오류(SyntaxError)** 상태였음. HEAD 커밋 상태로 존재(전 단계 Phase 59 수렴 과정에서 오염 추정).
- 이를 커밋 `53ce7f71e`에서 import 위치를 정상화(나머지 25개 파일 패턴과 동일하게 이동)하여 수정. 이는 구조 수정이며 동작 변경 아님(D-08 분리 커밋).
- 영향: 이 수정 없이는 35개 모듈 전부 import/AST-parse 불가 → plan의 smoke deliverable("35개 모듈 import 무오류")을 충족할 수 없었음.

## 부수 확인

- **AdSense Publisher ID 불변**: 4개 커밋 변경 파일에서 `ca-pub-` ID 0건 (광고 코드 무접촉). [검증됨]
- **data/*.db**: tracked DB 변경 없음. `git status`의 data/ untracked 파일은 20260806 복구 백업(사전 존재). [검증됨]
- **신규 third-party 패키지**: 0 (stdlib + 기존 모듈만). [검증됨]
- **배포**: dispatcher.py 경유만 — 이 plan은 배포/발행을 수행하지 않음 (adapter 위임만). [검증됨]

## 잔존 위험

1. **flight 정규화의 end-to-end 미검증** — `_normalize_result`의 status→success 매핑은 단위 확인했으나, 라이브 dispatcher `dispatch()` 경유 실발행은 수행하지 않아 전체 경로 통합 검증은 미실시. [부분검증] 한계: 실발행은 실제 네트워크/DB/배포 수반으로 plan 범위에서 제외.
2. **run_batch 경로 동작** — `run_batch` 내부가 `_run_impl`(bool/status) 호출로 유지됨을 구조적으로 확인했으나, `pipelines.etap.pipeline.run`이 `_BLOG_PIPELINE_MAP`으로 `run_batch`를 호출하는 통합 경로는 실발행 검증 안 함. [부분검증]
3. **35개 모듈의 generation 로직 무변경** — git diff로 `run` def rename + adapter 추가 + run_batch 내부 호출 변경만 발생했음을 확인. generation 로직 본문은 미접촉. [검증됨] 단, 이는 diff 검사 기반이므로 "생성 결과물 동일"은 실발행 비교로는 미검증.
4. **§3.5 doc** — 정규화 결정이 이미 문서화되어 있어 수정 불필요. 향후 다른 status 값 추가 시 매핑 확장 필요.
5. **잔존 위험 없음 사항**: AdSense ID, DB 불변, dispatcher 무변경은 각각 검증 완료.

## 자가 점검 (report rules)

- 3분법 사용: [검증됨]/[부분검증]만 사용, [검증불가] 항목 없음 (모든 deliverable에 독립 검증 수단 존재).
- 금지어 미사용: "전부 통과/all passing/사실상/레거시 호환" 미기재. 테스트 수치는 분해 근거 명시(21 실패 = 사전 baseline 동일, passed 368 = 364 baseline + 4 ETAP 테스트).
- 근거 동반: 각 항목에 git diff/테스트/측정 근거 명기.
- 잔존 위험 섹션 포함.
