# Phase 58 실행 요약 (SUMMARY)

이 파일은 Phase 58 태스크들의 실행 결과를 누적 기록하는 공유 아티팩트다.
각 태스크는 자기 섹션만 ADD(추가)하고, 기존 섹션을 덮어쓰지 않는다.

---

## Task 5 [PRODUCTION CODE] — dispatcher.py 통합: 결과 파싱 + 배포 캡처 + 카운터 확장

> 작성: 2026-08-06
> 수정 파일: `dispatcher.py` (단일 파일, additive only)
> 실행: `.venv/bin/python` (3.11, `.venv/bin/python -V` 기준)

### baseline (수정 전, orchestrator 기록): 228 passed, 22 failed, 1 skipped

본 태스크 시작 시점 독립 확인 — 수정 후 전체 스위트 재실행 결과:
`22 failed, 228 passed, 1 skipped in 1.14s` — baseline 수치와 동일 (신규 실패 0건).

### dispatcher 관련 테스트 결과

| 항목 | 결과 | 근거 |
| --- | --- | --- |
| `tests/test_dispatcher_registry.py` | 1 passed | `.venv/bin/python -m pytest tests/test_dispatcher_registry.py -q` |
| `py_compile dispatcher.py` | OK | `.venv/bin/python -m py_compile dispatcher.py` |
| import sanity (`PROBLEM_ALERT_DRY_RUN=1`) | ok | `import dispatcher; print('ok')` |
| reason→problem 매핑 유닛 | OK | `no_result→P01`, `deploy_error→P04`, `llm_fallback_exhausted→P22` assert 통과 |
| counter helpers 기능 | OK | `{blog_id}`+`{blog_id}:{problem_id}` 동시 증분 / 확장 전용 증분 / 확장 키 성공 리셋 (임시 JSON으로 검증) |
| 실패 분기 훅 (functional, dry-run) | OK | similar_title→P03(hook=result_parse, consecutive=1, 양 카운터 증분), unknown reason 로그만, quota_met(침묵) 무증분·무발송, no_result는 기존 증분 1회 + 확장 키 동기화 |
| 성공 분기 배포 캡처 (functional, dry-run) | OK | `_build_and_deploy_central()` False→`report(blog_id, {"reason":"deploy_error"}, phase="post_deploy", extra={})` + 확장 키 삭제, True→무발송 |
| 전체 스위트 회귀 | 22 failed, 228 passed, 1 skipped | baseline과 동일. 22건 전부 사전 존재 실패(아래 분해) |

22건 실패 분해 (전부 [사전 존재] — dispatcher.py 미수정 상태(stash)에서도 동일 실패 확인):
`test_alert_thresholds 2 + test_cot_threshold_validation 1 + test_defense_layers_independent 4 +
test_filters_allblogs 1 + test_keywords 4 + test_pipeline 1 + test_title_hardening 4 +
test_title_regression 1 + test_ai_writer 2 + test_post_validator 1 + test_relevance_scorer 1 = 22`

### `_tg_error` grep 카운트 (before/after — 불변 확인)

| 패턴 | before | after |
| --- | --- | --- |
| `grep -c '_tg_error(blog_id, "deploy"'` | 1 | 1 |
| `grep -c '_tg_error(blog_id, "quota"'` | 0 | 0 |

`_build_and_deploy_central(` 호출부는 2곳(정의 577, 호출 729) — 기존 호출 1곳은 반환 캡처로 변경.

### 구현 요약

1. **imports (모듈 최상단, additive)**: `from shared.problem_registry import lookup_reason`,
   `from shared.problem_monitor import get_monitor`.
2. **결과 파싱 훅 (실패 분기 내부, M-11)**: `else:`(success=False) 분기 내 `reason` → `lookup_reason()`.
   None이면 `logger.warning("unknown failure reason: %s")` 로그만, 매핑 성공 시
   `get_monitor().report(blog_id, {"reason": reason}, phase=spec.hook, extra={"consecutive_failures": <카운트>})`.
   `phase`는 spec.hook 그대로 사용 (Task 4 hook 불일치 가드 통과). 침묵 reason
   (`quota_met`/`already_running`/`duplicate_title`)은 기존대로 카운터 증분·모니터 발송 제외.
3. **배포 반환 캡처**: `deploy_ok = _build_and_deploy_central(blog_id)` → False 시
   `report(blog_id, {"reason": "deploy_error"}, phase="post_deploy", extra={})` (P04).
   기존 `_tg_error(blog_id, "deploy", ...)`(deploy_err 경로)는 유지.
4. **카운터 공용화 (W-1)**: `_increment_failure_count(blog_id, problem_id=None)` — problem_id
   주어지면 `{blog_id}`+`{blog_id}:{problem_id}` 둘 다 증분, 기본값은 기존 동작 불변.
   no_result 계열은 기존 분기(:714)가 `{blog_id}`를 이미 증분하므로 `_increment_extended_failure_count`
   (확장 키 전용)로 이중 증분을 방지. 성공 분기에 `_reset_extended_failure_keys` 추가 — `{blog_id}`는
   기존 `_reset_failure_count` 불변, `{blog_id}:{problem_id}` 확장 키만 일괄 삭제.
5. **에러 로그 패턴**: 모든 신규 훅은 `logger.warning`에 blog_id + reason + problem_id 명시.

### Q3 부분 답변 — `similar_title` reason이 dispatcher 정규화를 통과하는가?

**통과함 (보존됨).** 근거:
- curation `pipeline.py:1109/1128`이 `{"success": False, "reason": "similar_title", "keyword": keyword}`
  dict를 반환 (README 확인 완료).
- dispatcher 정규화 구간은 `result is None`/`isinstance str`/`isinstance bool`일 때만 변환하고,
  **dict는 그대로 통과** — `reason` 키에 대한 재작성/일반화 코드 없음 (dispatcher.py:710-722 읽기 확인).
- 따라서 실패 분기 훅은 `reason="similar_title"`을 verbatim으로 받아 P03(hook=result_parse)으로 매핑.
- Task 6에서 curation 쪽 reason 보존을 추가 확인하더라도 dispatcher는 받은 reason 그대로 사용.

### P05 vs P04 (Hugo/Wrangler 구분) 배선 여부

**구분 배선하지 않음 — 기본 P04 deploy_error로 통일.** `_build_and_deploy_central`은 bool만 반환하고
실패 종류(내부 로그 문구 `[deploy] Hugo 빌드 실패` vs `[deploy] Wrangler 배포 실패`)를 호출부에
노출하지 않는다. 반환 계약 변경(튜플/모듈 전역)은 additive 원칙을 벗어나는 restructuring이라
기본값 P04로 보고하고, P05(hugo_build_failed) 구분은 후속 작업으로 남김. Pages-CAP 경로의
`deploy_error`(publisher.py:1074)는 기존 `deploy_err` 소비 경로가 그대로 유지되어 Task 6 범위.

### 잔존 위험

- `_build_and_deploy_central`의 P05(Hugo 빌드)와 P04(Wrangler) 구분 미배선 — Hugo 빌드 실패도 P04로
  분류됨 (정확성 개선은 후속 작업 필요).
- ipo-hugo+no_content 특수 분기(:708-712)는 `_increment_failure_count`를 호출하지 않아 P02 확장
  카운터가 누적되지 않음 — 기존 1회 알림 + daily cooldown이 그대로 동작하므로 회귀는 없으나,
  monitor의 P02 연속 카운터는 이 경로에서 사실상 미동작 (부분검증 — functional 테스트는 비-ipo
  경로로만 커버).
- 본 태스크 검증은 dry-run(`PROBLEM_ALERT_DRY_RUN=1`) 기준 — 실발송 모드에서의 쿨다운/중복 흡수는
  실 운영 데이터 필요 (검증불가 → Task 8/모니터링으로 확인).

---

## Task 8 [TEST CODE] — 통합 테스트 + 회귀 게이트 + dry-run 실발송 0건

> 작성: 2026-08-06
> 수정 파일: `tests/curation/test_problem_monitor_integration.py` (신규, TEST CODE — production/기존 테스트 미수정)
> 실행: `.venv/bin/python -m pytest` (3.11)

### baseline (orchestrator 기록, Task 5와 동일): 228 passed, 22 failed, 1 skipped

본 태스크 시작 직전 독립 재확인 — `228 passed, 22 failed, 1 skipped` (baseline과 동일).

### 통합 테스트 (tests/curation/test_problem_monitor_integration.py — 8 passed)

| 시나리오 | 테스트 | 결과 | 검증 근거 |
| --- | --- | --- | --- |
| P01 no_result | `test_curation_run_no_result_reports_p01` | PASSED | curation run() 실패 블록(pipeline.py:859-876) 실제 경로 — `_run_inner`를 mock해 `{"reason":"no_result"}` 반환. wrapped `monitor.report` 호출 args: `{"reason":"no_result"}`, `phase="result_parse"`(P01 hook), `extra={"consecutive_failures":1}`. `_tg_error` 1회 호출 확인(기존 경로 유지) |
| P08 CoT | `test_writer_raw_hook_reports_p08_on_cot_body` | PASSED | `ai_generate` patch → `'이제 글을 작성하겠습니다.'` 본문 주입. raw 훅(writer.py:764-771)에서 detect→P08 Detection 보고 `phase="post_generate"`. P08 CRITICAL always → dry_run=0에서 `send` 1회(patch) |
| P08 미감지 | `test_writer_raw_hook_no_report_on_normal_body` | PASSED | 정상 한국어 500자 미만 본문 → detect [] → report 0건, send 0건 |
| P15 | `test_publisher_run_validation_reports_p15` | PASSED | `_validate_post_html` patch → `{"issues":[{"check":"thumbnail","msg":"...","severity":"error"}]}`. detect_validation_issue→P15 보고 `phase="post_validate"`. 기존 `_tg_err(validation)` 1회 호출 확인 |
| P04 | `test_dispatcher_deploy_fail_capture_p04` | PASSED | `_build_and_deploy_central` patch→False. dispatcher 배포 캡처 → `{"reason":"deploy_error"}`, `phase="post_deploy"`. P04 always → send 1회 |
| P05 | `test_dispatcher_reason_mapping_p05` | PASSED | `_run_pipeline` patch→`{"reason":"hugo_build_failed"}`. dispatcher 실패 분기 매핑 → P05, `phase="post_deploy"`, send 1회 |
| P22 | `test_writer_p22_llm_fallback_exhausted` | PASSED | `ai_generate` side_effect=RuntimeError → `{"reason":"llm_fallback_exhausted"}`, `phase="result_parse"` 보고 + `pytest.raises(RuntimeError)`로 re-raise 확인(no_content 흡수 경로 보존). P22 MAJOR consecutive:3 → 1회차 발송 0건 |
| deploy_error phase | `test_curation_run_deploy_error_phase_post_deploy` | PASSED | curation run() stage="deploy_error" → P04(hook="post_deploy") 매핑 → `phase="post_deploy"` 보고, hook 가드 차단 없음. send 1회 |

`py_compile tests/curation/test_problem_monitor_integration.py`: OK.

### 회귀 게이트 (전체 스위트)

| 실행 | 결과 | baseline 대비 |
| --- | --- | --- |
| normal (`tests/ -q`) | **22 failed, 295 passed, 1 skipped** | 신규 실패 0건 (실패 목록 diff: baseline 22건과 byte-identical) |
| dry-run (`PROBLEM_ALERT_DRY_RUN=1 tests/ -q`) | **22 failed, 295 passed, 1 skipped** | normal과 동일 (dry-run은 결과 무변화) |

- 295 passed = 228(baseline) + 13(registry T7) + 36(detectors T7) + 10(monitor T7) + 8(통합 T8) = 295. T7 파일 3종은 병렬 태스크로 이 실행 시점에 병합됨.
- 실패 22건 전부 [사전 존재] — test_alert_thresholds 2, test_cot_threshold_validation 1, test_defense_layers_independent 4, test_filters_allblogs 1, test_keywords 4, test_pipeline 1, test_title_hardening 4, test_title_regression 1, test_ai_writer 2, test_post_validator 1, test_relevance_scorer 1. 신규 파일(shared/problem_*.py, dispatcher.py, curation writer/pipeline, publisher)과 무관.

### dry-run 실발송 0건 근거

1. **1차 근거 (patch assert)**: T7 `tests/shared/test_problem_monitor.py` dry_run=1 전 severity 발송 0건 assert(`call_count == 0`) **7건 전부 통과**. 통합 테스트도 모든 시나리오에서 `shared.problem_monitor.telegram_notifier.send`를 항상 patch → 실전 send 호출 자체가 0회.
2. **2차 근거**: dry-run 전 스위트 실행에서 결과가 normal과 동일(22/295/1) — 발송 여부가 결과를 바꾸지 않음. 통합 테스트의 send 관찰은 전부 patch된 mock call_count로만 수행.

### 발견 사항 (production 코드, TEST CODE 태스크라 수정하지 않음)

- **P23 오탐**: `detect_post_generate(content, ...)`가 본문 전체를 `detect_image_url_length`에 넘겨 **500자 초과 본문마다 P23(quiet, 로그만) 보고 발생**. 발송은 quiet라 0건이지만 report 호출은 매 글마다 발생 — 실운영 모니터 카운트 오염 가능. 후속 Phase에서 P23 감지 대상을 "본문 내 이미지 URL"로 한정하는 수정 권장 (이번 태스크는 TEST CODE만 수정 원칙 — 미수정).

### 잔존 위험

- P23 오탐(위 발견) — quiet라 알림/실발송은 없으나 report 호출 잡음. 복구 계획: detect_post_generate에서 P23 대상 분리(본문 내 URL 추출) 후 재검증.
- dispatcher P04/P05 검증은 `_build_and_deploy_central` 반환값(bool) 기반 mock — Hugo/Wrangler 구분(P05 세분화)은 Task 5에서 이미 "미배선"으로 명시, 이번 통합 테스트도 해당 범위 유지.
- 실발송 모드 쿨다운/중복 흡수 실운영 검증은 dry-run 해제 후 다음 Phase 필요 (기존 Task 5 잔존 위험과 동일).
