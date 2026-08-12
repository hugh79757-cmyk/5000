# Phase 70 — Research: Pipeline Exception → Dashboard Exposure (재검증판)

**Researched:** 2026-08-10 (재검증: 기존 RESEARCH.md의 모든 file:line을 라이브 코드베이스로 재조회 — 2차 리서치 실행이 파일을 쓰지 않아 전량 재검증 수행)
**Domain:** 파이프라인 예외 → 규격화 reason → Ops Dashboard 표현 (dispatcher/scheduler/problem_registry/ops_dashboard)
**Confidence:** HIGH (모든 핵심 file:line 참조는 코드베이스 직접 조회로 재검증됨 — `[VERIFIED: 코드베이스 직접 조회]`)
**이전 문서 대비 변경:** 본 문서는 기존 RESEARCH.md 구조(Summary → user_constraints → phase_requirements → Architecture Map → 실행경로 추적 → 변경 지점 → 표현 설계 → 테스트 → 결론 → Sources)를 유지하되, drift는 `[REVISED]: ...`로 표기했다.

## Summary

오늘(2026-08-10) 71회 crash(`AttributeError: 'list' object has no attribute 'split'`, 28개 ETAP 블로그)가 대시보드에 안
보인 근본 원인은 그대로 유효하다: dispatcher `dispatch()`가 `_run_pipeline(cfg)`(dispatcher.py:849, [VERIFIED])를
try/except 없이 bare 호출해 예외가 `main()`(dispatcher.py:1079, [VERIFIED]) 밖으로 전파 → subprocess가
traceback + exit code 1로 죽고, scheduler `run_publish()`의 returncode!=0 경로(scheduler.py:282-285, [VERIFIED])가
`_tg_error(blog_id, "scheduler", result.stderr[-300:])` raw traceback만 발송한다. stdout에 JSON이 없어 dispatcher 내부의
실패 기록 로직(`_record_failure` / `lookup_reason` / `_record_summary_event` / monitor)이 전부 미도달한다.

**재검증 결과 변경 지점은 여전히 4곳** (전부 기존 동작 보존, 추가만):

1. **dispatcher.py:849** — `_run_pipeline(cfg)` 호출을 try/except로 감싸
   `{"success": False, "reason": "pipeline_exception", "error": "Type: msg"}` 반환 [VERIFIED: 코드베이스 직접 조회 — 라인 정확]
2. **shared/problem_registry.py** — P25 spec 등록 (`unknown_failure` 542-556 하단 append). `/api/registry` errors 배열은
   `ops_dashboard/registry/errors.py:39`의 **import 시 자동 미러링**([VERIFIED])이므로 ops_dashboard 측 별도 선언 불필요.
   ⚠️ `errors.py:17` docstring "PROBLEM_REGISTRY 자체는 절대 수정하지 않는다" — 해석 checkpoint (§2-②)
3. **dispatcher.py:903-983 실패 분기 — 여전히 필요** ([VERIFIED]): `_record_summary_event()`는
   `no_result` 계열(927-928)·`deploy_error`(894-895, **리터럴 "deploy_error" 문자열 사용**)·`duplicate_*`(941-942) 3곳에만
   하드코딩되어 있고, 일반 reason 분기(Phase 58 모니터 매핑 블록 960-983 = `_spec = lookup_reason(reason)` 962 →
   `get_monitor().report(..., phase=_spec.hook, ...)` 979-983)에서는 **호출되지 않는다(재확인)**. P25 등록만으로는
   `daily_summary_events` 0건 → `/api/daily-summary`·index.html 요약 카드에 안 보인다. summary 기록 추가(additive) 필수.
4. **scripts/auto_triage.py:1042-1076 `_reason_to_problem_id()`** — 하드코딩 매핑 dict(1044-1075)에
   `"pipeline_exception"` **없음**(원본 그대로, [VERIFIED]). 추가하지 않으면 scheduler.log 파싱 트라이아지
   (parse_scheduler_notifications 630-678 → run_triage 874-897)가 `unknown_failure`(897)로 분류한다.

**또 하나의 기존 결론은 그대로 검증됨**: "/api/attention 노출"은 레지스트리 등록만으로 달성 불가 —
`/api/attention` fail_checks는 **check_results 테이블 전용**(db.py:793-918, 쿼리 804-818 `FROM check_results ...
WHERE cr.status='fail'`, [VERIFIED])이라 P-문제는 원래 안 들어온다. P01~P24도 현재 attention에 없고
`/api/registry` errors 배열 + `/api/daily-summary`로 노출된다.

**신규 발견 (이전 RESEARCH 미확인 — A3 가정이 실제로 확인됨)**:
- `tests/shared/test_problem_registry.py`에 **하드 카운트 단언 2건 존재**:
  `:48 assert len(PROBLEM_REGISTRY) == 25`와 `:52-55 assert len(problems) == 24` + `MAJOR == 12`.
  P25 append 시 **이 2개 테스트는 실패**한다 (25→26, 24→25, MAJOR 12→13). 이는 "스펙 변경 반영"으로 분류된
  [TEST CODE] 수정이 계획에 포함되어야 한다. 또한 `:58 assert MINOR == 7`은 **P25가 MINOR면 깨지므로 P25 severity는
  MAJOR/CRITICAL이어야 한다**. `:115-129` 템플릿 렌더 테스트(context 9키 고정)는 **P25 alert_template에 `{error}`
  placeholder를 넣으면 KeyError로 실패**한다 — P20~P22 형식(6개 placeholder)을 따라야 한다.
- ops.db 실데이터 재확인: `daily_summary_events` 2026-08-10 = P16 31건 + deploy_error 4건뿐 (08-09 = P01 6건 + P16 1건 +
  deploy_error 4건). ETAP 71회 crash 기록 0건 — CONTEXT의 "0건" 메커니즘 주장 일치 (건수는 라이브 데이터라 CONTEXT
  스냅샷값과 차이, 메커니즘 영향 없음).

**Primary recommendation:** ① dispatcher try/except + ③ summary 이벤트 기록(+2건 TEST [정합] 수정) + ② P25 등록 +
④ auto_triage 매핑 추가. 대시보드·템플릿·DB 스키마 변경 없이 index.html 요약 카드·`/api/registry` errors 배열·
`/api/daily-summary`에 자동 노출된다.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- ① dispatcher.py `_run_pipeline(cfg)` 호출부를 try/except로 감싸, 예외 시
  `{"success": false, "reason": "pipeline_exception", "error": "Type: msg"}` JSON 반환 (crash 대신)
- ② pipeline_exception reason → 문제 레지스트리 등록 (후보 id P25) — `shared/problem_registry.py`에 spec 추가
  → `/api/registry` errors 배열에 표시
- 대시보드 표현이 이번 페이즈의 **1순위 주제** (단순 crash 방지가 아님)
- 성공 기준 6개: S1 dispatcher crash 없이 JSON 출력 / S2 scheduler가 stage=pipeline_exception 정상 파싱 /
  S3 P25가 registry errors + 노출 / S4 daily_summary_events N회 기록 → `/api/daily-summary` 집계 /
  S5 기존 P01~P24 spec·동작 불변 + auto_triage 매핑 정합 / S6 기존 테스트 스위트 green 유지
- 계약: 기존 기능 보존 / 증분 수정(4곳만) / additive only(P25는 append) / 비파괴(DB 스키마·배포 변경 없음)

### the agent's Discretion
- (컨텍스트상) P25 spec의 세부 필드(severity/threshold/alert_template/action) 값 — RESEARCH 결과 추천
- (컨텍스트상) `/api/attention` 표현 방식 — RESEARCH 결과 옵션 제시
- (컨텍스트상) ③의 summary 기록 범위(일반 분기 공통 vs pipeline_exception 전용) — RESEARCH 결과 옵션 제시 (§2-③)

### Deferred Ideas (OUT OF SCOPE)
- 문제 B (dining-hugo stage=unknown, reason 없는 실패) 근본 원인 조사 — 별도 조사
- `scheduler.py:280` `except (_json.JSONDecodeError, Exception)` 중복 튜플 정리 — 사소 정리 [REVISED: 위치 287→280]
- Telegram 전체 발송 건수 검증 (수신 측 확인 수단 부재)
- 71회 crash 원인 자체 (`hugo_writer.py:198 tags.split`) — 2d47afd51로 수정 완료. 이 페이즈에서 계획 금지
- **RESOLVED checkpoint**: "dispatcher.py:894 `_problem_id` 선 참조(NameError 가능)" — 재검증 결과 **해당 NameError는
  존재하지 않음** (894-895는 리터럴 "deploy_error" 문자열 사용). 계획에서 checkpoint 제거 (§2-③)
</user_constraints>

<phase_requirements>
## Phase Requirements

> orchestrator가 공식 REQ-ID를 제공하지 않았으나, CONTEXT.md 성공 기준 6개가 이 페이즈의 요구사항이다.

| ID | Description (CONTEXT 성공 기준) | Research Support |
|----|---------------------------------|------------------|
| S1 | dispatcher가 예외 시 crash 없이 JSON 출력 | §2-① 정확 삽입점 (dispatcher.py:849), 기존 정규화 851-864 [VERIFIED] |
| S2 | scheduler가 stage=pipeline_exception 정상 파싱 | scheduler.py:272-281 last-line JSON 파싱은 reason 독립적 [VERIFIED] |
| S3 | P25가 registry errors 배열 (+노출) | problem_registry 등록 → ops_dashboard/registry/errors.py:39 자동 미러링 [VERIFIED] |
| S4 | daily_summary_events N회 기록 → `/api/daily-summary` 집계 | **추가 변경 필요** — §2-③ (기존 코드로는 0건) [VERIFIED] |
| S5 | 기존 P01~P24 spec·동작 불변 + auto_triage 정합 | P25는 append만; `_to_entry`가 전 spec 미러링 [VERIFIED]; ④ 매핑 추가 필요 [VERIFIED] |
| S6 | 기존 테스트 스위트 green 유지 (23개를 더 늘리지 않음) | baseline 392/23/1 [VERIFIED — 재실행]; **P25 관련 2건 [TEST CODE] 카운트 단언 수정 필요 (§4)** |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 파이프라인 예외 포착·규격화 | API/Backend (dispatcher.py) | — | 예외는 `dispatch()` 실행 스레드에서 발생 — 여기서 reason dict로 변환돼야 scheduler·summary·monitor가 소비 가능 |
| reason → problem_id 매핑 | API/Backend (shared/problem_registry.py) | — | 26개 spec 단일 소스; dashboard errors 배열이 import 시 미러링 |
| 실패 기록 (ledger/summary/monitor 알림) | API/Backend (dispatcher 실패 분기) | — | dispatcher가 카운터·요약 이벤트 소유자 (W-1 설계); 모니터는 extra만 소비 |
| 대시보드 노출 (registry errors / daily-summary / attention) | Frontend Server (ops_dashboard, Flask) | — | ops.db read-only 렌더; 스키마 변경 불필요 |
| 트라이아지 분류 (scheduler.log 경로) | API/Backend (scripts/auto_triage.py) | — | scheduler.log의 stage= 파싱 → reason → P-id 매핑 (하드코딩 dict) |
| 문제 레지스트리 정합성 검증 | Test (tests/shared/test_problem_registry.py) | — | 카운트 단언 2건(.48/.52-55)이 P25 append 시 수정 필요 — [TEST CODE] 변경 [VERIFIED] |

핵심: 변경은 전부 "API/Backend 티어의 생산자(dispatcher) + 레지스트리 + 검증 테스트"에만 있다. 대시보드 티어는
수정 불필요 (기존 소비 패턴이 이미 reason/event 기반이기 때문).

---

## 1. 실행 경로 추적 (현재 상태 — 재검증 결과)

> 모든 file:line은 코드베이스 직접 재조회 기준 — `[VERIFIED: 코드베이스 직접 조회]` / drift는 `[REVISED]`

### 1.1 dispatcher.py — dispatch() 흐름 (1087줄, 이전 1083줄 — 4줄 증가 [REVISED])

| 위치 | 코드 | 역할 |
|------|------|------|
| **dispatcher.py:849** | `result = _run_pipeline(cfg)` | **핵심 — try/except 없는 bare 호출 [VERIFIED 라인 정확]. 예외 시 dispatch() → main()(1079, try/except 없음 [VERIFIED]) → traceback + exit 1** |
| dispatcher.py:498-502 | `_run_pipeline()` = `_resolve_pipeline(blog_id, pipeline, cfg)` | pipeline별 run(cfg) 라우팅 (STAP/TAP subprocess 포함) [VERIFIED] |
| dispatcher.py:417-470 | `_resolve_pipeline()` — `run(cfg)` 호출부 433/470, `_run_stap` 439 | **예외 발생 지점 후보 — `run(cfg)` 내부 예외가 849까지 전파됨** [VERIFIED] |
| dispatcher.py:851-864 | None → `{"success": False, "reason": "no_result"}` + cooldown(852-854); str → reason 매핑(855-861); bool → `{"success": result}`(862-863); dict는 864 통과 | 결과 정규화 — 여기로 흘러들면 이후 로직 전부 동작 [VERIFIED] |
| dispatcher.py:865-881 | success 시 `_record_ledger`/`_reset_failure_count`/`_reset_extended_failure_keys` + **ETAP/WORKERS deploy 분기**(869-880; `_build_and_deploy_central` 실패 시 monitor.report phase="post_deploy") | 성공 경로 [VERIFIED]. WORKERS_BLOGS 525-537 = 11개 [REVISED — 이전 문서 미기재] |
| dispatcher.py:882-902 | `deploy_err` 처리 → `_record_failure` + `_debounce_push` + `_tg_error` + **`_record_summary_event(_ops_conn, ..., "deploy_error", blog_id)` (894-895)** | 배포 실패 — summary 기록 예. **894-895는 리터럴 "deploy_error" 문자열 — `_problem_id` 참조 없음 [REVISED — checkpoint 해소]** |
| dispatcher.py:903-933 | 실패: `reason = result.get("reason", "unknown")` (904); `_record_failure(blog_id, reason, ...)` (906); no_result 계열(908) → `_problem_id = lookup_reason(reason).problem_id if lookup_reason(reason) else reason` (**917 — None 가드 존재 [REVISED — 이전 문서는 bare 참조로 기재]**) + **`_record_summary_event(..., _problem_id, blog_id)` (927-928)** | no_result 계열 — summary 기록 예 [VERIFIED] |
| dispatcher.py:934-945 | `duplicate_slug/duplicate_source_id` → **`_record_summary_event(..., "P16", blog_id)` (941-942)** | P16 — summary 기록 예 [VERIFIED] |
| dispatcher.py:960-983 | **Phase 58 모니터 매핑 블록 (additive)**: `_spec = lookup_reason(reason)` (962); None → 경고만 (963-966); 있으면 no_result 계열 이중 증분 방지(968-972) / `_consec = _increment_failure_count(blog_id, _spec.problem_id)` (974) + `get_monitor().report(blog_id, {"reason": reason}, phase=_spec.hook, extra={"consecutive_failures": _consec})` (979-983) | **일반 reason 분기 — summary 기록 없음(재확인). pipeline_exception이 여기 도달하면 monitor 알림은 가지만 daily_summary_events는 0건** |
| dispatcher.py:1078-1083 | `import json` (1078); `result = dispatch(cmd)` (1079, try/except 없음 — **crash 전파 지점**); `print(json.dumps(result, ensure_ascii=False))` (1081); else `dispatch_returned_none` (1083) | stdout JSON = scheduler 파싱 대상 [VERIFIED] |
| dispatcher.py:29-33 | `_tg_error`, `lookup_reason`, `get_monitor`, `_record_summary_event`/`init_daily_summary_tables`, `_debounce_push`/`init_debounce_tables` import | **필요 import 전부 이미 존재 — try/except 추가 시 import 변경 없음** [VERIFIED] |
| dispatcher.py:802-815 | `_record_failure(blog_id, stage, error_msg)` → publish_ledger INSERT status='failed' | 실패 ledger — ① 적용 후 `stage="pipeline_exception"`으로 기록됨 [VERIFIED] |
| dispatcher.py:512-522 | `ETAP_PIPELINE_BLOGS` = 35개 | CONTEXT "전체 35개"와 일치 [VERIFIED] |
| dispatcher.py:820-847 | dispatch() 조기 반환 3경로: config_error(825-827), inactive(830-831), duplicate_title(835-836), cooldown 2종(839-847) | **전역 pause 커밋(cd1accf02)과 무관 — ①의 try/except는 849 이후에만 필요** [VERIFIED] |

### 1.2 scheduler.py — run_publish() (244-294, 파일 903줄 [REVISED — 이전 296줄])

| 위치 | 코드 | 역할 |
|------|------|------|
| scheduler.py:263-267 | `subprocess.run([PYTHON, "dispatcher.py", blog_id], capture_output=True, text=True, timeout=600)` | dispatcher subprocess 실행 [VERIFIED] |
| scheduler.py:268-281 | stdout 마지막 줄 `json.loads` (272-274); `parsed.get("success")` → 성공(276); 아니면 `reason = parsed.get("reason", "unknown"); logger.error(f"[PUBLISH] {blog_id} 발행 실패 — stage={reason}")` (278-279) | **JSON 파싱은 reason 값과 무관 — stage=pipeline_exception 그대로 로그됨. "정상 파싱" 재확인됨** [VERIFIED] |
| scheduler.py:282-285 | `if result.returncode != 0 and result.stderr:` → `logger.error("ERR: " + stderr[-200:])` + `_tg_error(blog_id, "scheduler", stderr[-300:])` + `return False` | **현재 crash 경로의 raw traceback 발송 지점** — ① 적용 후 returncode=0 → 미도달 [VERIFIED] |
| scheduler.py:287-294 | TimeoutExpired / 일반 Exception → `_tg_error` | subprocess 자체 예외 (스코프 외) [VERIFIED] |
| scheduler.py:280 | `except (_json.JSONDecodeError, Exception):` 중복 튜플 | **[REVISED: 287 → 280으로 이동]** — 기능 결함 아님, 스코프 외 |

### 1.3 shared/problem_registry.py — 구조 (575줄, [VERIFIED — 라인 전부 일치])

- `SEVERITIES/HOOKS/THRESHOLDS` (16-18): `("CRITICAL","MAJOR","MINOR")` / `("result_parse","post_generate","post_validate","post_publish","post_deploy")` / `("always","consecutive:N","quiet")`
- `ProblemSpec` dataclass (21-34): `problem_id, name_ko, severity, reason_keys(tuple), hook, alert_template, threshold, cooldown_minutes=60, action="", detect_fn=""`
- `PROBLEM_REGISTRY` dict + `_register()` (47-51)
- P01~P24 등록 (54-538): CRITICAL/always 계열 P04/P05/P06/P07/P08/P09(54-159); MAJOR/consecutive:3 계열 P01/P02/P03/P10/P11/P12/P13/P14/P20/P21/P22(161-432); MINOR/quiet 계열 P16/P17/P18/P19/P23/P24(434-538)
- **P20~P24 형태**: `reason_keys`에 reason 문자열 튜플(373행에 `dispatch_returned_none` 포함 — **P20**); `hook="result_parse"` (P20/P21/P22, P16/P17/P18); alert_template에 `{blog_id}/{problem_id}/{name_ko}/{phase}/{consecutive}/{action}` placeholders ([VERIFIED])
- **`unknown_failure`** (542-556): problem_id="unknown_failure", reason_keys=() **빈 튜플** → `lookup_reason()`은 어느 reason도 여기로 매핑하지 않음 (미등록 reason은 None; dispatcher.py:963-966에서 경고 후 monitor 생략) [VERIFIED]
- `lookup_reason()` (559-564): reason → spec 역방향 탐색, **미등록이면 None**
- `lookup_problem()` (567-569) / `lookup_hook()` (572-575)
- **현재 spec 수: P01~P24 + unknown_failure = 25개** (docstring: "24개 + unknown_failure = 총 25개") — P25 append 시 26개 [VERIFIED]

**P22 선례 (예외 포착 → reason 변환)** [VERIFIED: pipelines/curation/writer.py:838-846]:
```python
except RuntimeError as _re:
    try:
        from shared.problem_monitor import get_monitor
        get_monitor().report(blog_id, {"reason": "llm_fallback_exhausted"}, phase="result_parse", extra={})
    except Exception as _me:
        logger.error(f"[problem_monitor] P22 보고 실패: {_me}")
    raise
```
→ P22(ai_writer.py:315 `raise RuntimeError(msg)`)를 잡아 reason으로 보고 후 재전파하는 선례. 이 페이즈는
**re-raise가 아니라 결과 dict 변환**이므로 방향만 다름.

### 1.4 shared/problem_detectors.py + problem_monitor.py — 배선 ([VERIFIED])

- `problem_detectors.py` (186줄 — 변경 없음): `detect_post_generate`(P07/P08/P09/P23), `detect_validation_issue`(P15)
  존재 — **result_parse 훅용 탐지 함수 없음. P25는 reason_keys 기반이므로 detectors 변경 불필요.**
- `problem_monitor.py` (247줄 [REVISED — 이전 157줄, report()는 동일 라인]):
  - `report()` (53-106): `_resolve()` → spec; `spec.hook != phase`면 발송 차단 (68-73); threshold 분기 always/consecutive:/quiet (78-104). **신규 spec 안전 확인 — 모두 제네릭 처리** [VERIFIED]
  - `_resolve()` (108-156): reason 경로 `lookup_reason(reason)` (137-142), 미등록 reason 경고(140-142) → None; **detail은 `result.get("detail") or result.get("error_msg")`에서만 읽음(143) — dispatcher Phase 58 블록은 `{"reason": reason}`만 전달하므로 matched=""** [VERIFIED]
  - **P25 hook="result_parse"로 지정하면 dispatcher.py:982의 phase 전달과 일치** → 발송 정상 [VERIFIED]
- dispatcher → monitor 배선: dispatcher.py:979-983 `get_monitor().report(...)` — 이미 존재. 신규 배선 불필요 [VERIFIED]

### 1.5 daily_summary — 표기·집계 ([VERIFIED])

- `shared/daily_summary.py` (178줄 [REVISED — 이전 63줄, record_event 동일 라인]):
  - `init_daily_summary_tables(conn)` (27-28) / `record_event(conn, summary_date, problem_id, blog_id, count=1)` (31-43) → `INSERT INTO daily_summary_events` [VERIFIED 라인 일치]
  - `generate_summary()` 신규 추가(46+) — debounce 반영 요약 (스코프 외, 일관성 있음)
- dispatcher.py:32 `from shared.daily_summary import record_event as _record_summary_event, init_daily_summary_tables` [VERIFIED]
- ops_dashboard/db.py:1242-1278 `get_daily_summary()`: `SELECT problem_id, blog_id, SUM(count) ... GROUP BY problem_id, blog_id ORDER BY cnt DESC` → breakdown/blog_by_problem(1255-1261). **problem_id 문자열을 그대로 집계 — 스키마 변경 없이 "P25"든 "pipeline_exception"이든 동작** [VERIFIED — 1251에 ORDER BY 추가된 것 외 동일]

### 1.6 ops_dashboard — 소비 경로 ([VERIFIED])

- `ops_dashboard/registry/errors.py:39` — `ERRORS = [_to_entry(spec) for spec in PROBLEM_REGISTRY.values()]`
  → **shared/problem_registry에 P25 추가 시 /api/registry errors 배열에 자동 편입** (import 시 동적 미러링, [VERIFIED])
  - ⚠️ `errors.py:17` docstring: **"PROBLEM_REGISTRY 자체는 절대 수정하지 않는다"** — 38행 "기존 dict는 변경하지 않음"과 함께
    읽으면 = "기존 spec(엔트리) 불변, append는 미러링 대상 확장"으로 해석하는 것이 Phase 69 W1/W2 설계 의도.
    **planner checkpoint: 사용자에게 이 해석을 1회 확인할 것** (literal하게 읽으면 P25 append 자체가 금지되는 모순)
- `ops_dashboard/db.py:1057-1237 get_registry_view()`: errors 항목 = `by_kind("error")` 선언(1227) + `triage_classifications`
  최신 1행(1229-1234). **triage 행 없으면 status="unknown"** — P25 등록 직후엔 unknown, auto_triage 분류 후 갱신 [VERIFIED]
- `ops_dashboard/db.py:793-918 get_attention_items()`: fail_checks = **check_results 테이블 fail 행 전용**
  (`FROM check_results ... WHERE cr.status = 'fail'`, 804-818). P-문제(오류 선언)는 이 경로에 없음 [VERIFIED — 재확인]
- `ops_dashboard/checks/__init__.py:27-74 run_all_checks()`: 등록 CHECKS(standard/freshness/render/crosscheck/maintenance/
  crosslink/content_integrity — 77-110 import)만 check_results에 기록 — 오류 선언은 실행 대상 아님 [VERIFIED]
- `ops_dashboard/templates/index.html:57-79`: `daily_summary.breakdown` 렌더 — **P25 이벤트 기록 시 자동 표시**
  (`{% for pid, cnt in daily_summary.breakdown.items() %}` 66-72). 배지 색상(68행): `'fail' if pid.startswith('P0') else
  'warn' if pid.startswith('P1') else 'unknown'` → **"P25"는 gray(unknown) 배지** (표시는 되나 색상 개선 선택지 — §3 옵션 C)
- `ops_dashboard/app.py:464` `/api/attention` → get_attention_items; `:545` `/api/daily-summary` → get_daily_summary;
  `:564` `/api/registry` → get_registry_view; `:299-303` index.html에 attention + daily_summary 전달 [VERIFIED]
- `scripts/auto_triage.py:630-678 parse_scheduler_notifications()`: scheduler.log에서 `[PUBLISH] ... 발행 실패 — stage=(\S+)`
  파싱(639-644), reason 없으면 stage를 reason으로 사용(657-662). `run_triage` 874-897: scheduler 알림 →
  `_reason_to_problem_id(reason)` (893); **미매핑이면 `unknown_failure`로 분류 (897)** [VERIFIED]
- `scripts/auto_triage.py:1042-1076 _reason_to_problem_id()`: 하드코딩 dict(1044-1075) — **`"pipeline_exception"` 없음** [VERIFIED]
- `shared/notification_classifier.py:15-22`: `REALTIME_PUSH_PROBLEMS` frozenset(P01/P02/P04/P05/P06/unknown_failure) — P25 미포함
  → daily_summary 실시간 푸시 분류에서 "summary" 버킷 (요약 집계에는 무관) [VERIFIED]
- **"pipeline_exception" 문자열은 코드베이스 전체에 기존 참조 0건** — 완전 신규 reason [VERIFIED: rg 전체 스캔]

---

## 2. 변경 지점 확정 (4곳 + 테스트 정합 2건 + 성공 기준 검증)

> 빨간줄 유지: CONTEXT의 2곳은 정확했으나, **S4(daily_summary 0건) 문제로 ③이 필수** 추가되었고,
> **⑤/⑥에서 ④(auto_triage)도 추가 필요**가 확인됐다. "attention 노출"은 레지스트리 등록만으로 불가능 (§3).
> **신규: S6 달성을 위해 tests/shared/test_problem_registry.py 카운트 단언 2건 수정이 계획에 반드시 포함되어야 한다 (§2-⑤).**

### ① dispatcher.py:849 — try/except 래핑 (CONTEXT.md와 일치) [VERIFIED: 코드베이스 직접 조회]

```python
# dispatcher.py:849 현재 (그대로)
result = _run_pipeline(cfg)
# 변경: bare 호출을 try/except로 감싸 JSON 반환 (additive)
try:
    result = _run_pipeline(cfg)
except Exception as _e:
    if not isinstance(_e, KeyboardInterrupt):
        logger.exception(f"[dispatch] {blog_id} pipeline 예외 (type={type(_e).__name__})")
    result = {"success": False, "reason": "pipeline_exception",
              "error": f"{type(_e).__name__}: {_e}"}
```
- 정규화(851-864) 검증: dict는 851 None 체크 → 855 str 체크 → 862 bool 체크를 모두 통과해 마지막 흐름으로 착지. [VERIFIED]
- import 변경 불필요 (dispatcher.py:29-33 전부 존재) [VERIFIED]
- `error` 키는 기존 소비자에 영향 없음: scheduler는 reason만 읽고(scheduler.py:278), 모니터는 `result["reason"]`(904)만 소비 [VERIFIED]
- **S1 충족**: stdout JSON 출력(1081)은 dispatch() 반환을 찍으므로 crash 없이 반환되면 JSON 보장 [VERIFIED]
- 예외 발생 지점: `_resolve_pipeline`의 `run(cfg)` 호출(433/470) 및 `_run_stap`(439) — 전부 849 try/except가 포괄 [VERIFIED]
- `pipeline_exception`은 dispatcher.py:905-906의 `_record_failure(blog_id, reason, ...)`로 publish_ledger에
  `stage="pipeline_exception"`으로 기록되고, 960-983 블록에서 `lookup_reason` → P25로 매핑·모니터 푸시 [VERIFIED 실증]

### ② shared/problem_registry.py — P25 spec 등록 (CONTEXT.md와 일치, append) [VERIFIED]

P24(524-538) → `unknown_failure`(542-556) 하단에 append (기존 spec 미수정):
```python
_register(ProblemSpec(
    problem_id="P25",
    name_ko="파이프라인 예외 (pipeline_exception)",
    severity="MAJOR",
    reason_keys=("pipeline_exception",),
    hook="result_parse",
    alert_template=(
        "⚠️ [MAJOR] 파이프라인 예외\n"
        "블로그: {blog_id}\n"
        "문제: {problem_id} — {name_ko}\n"
        "감지 단계: {phase}\n"
        "연속 실패: {consecutive}회\n"
        "조치: {action}"
    ),
    threshold="consecutive:3",
    cooldown_minutes=60,
    action="dispatcher 로그에서 예외 원인(유형/메시지) 확인 후 수정",
))
```
- **⚠️ alert_template에 `{error}` placeholder 금지** [REVISED — 신규 확인]: `test_all_templates_render_with_full_context_within_500_chars`
  (test_problem_registry.py:115-129)가 고정 context 9키로 `.format()`을 수행하므로 `{error}`는 KeyError.
  위 템플릿은 P20~P22와 동일한 6개 placeholder로 안전 (렌더 길이 ≤500자 확인됨).
- **severity는 MAJOR(또는 CRITICAL) 필수** [REVISED — 신규 확인]: `test_unknown_failure_minor_makes_total_minor_7`
  (test_problem_registry.py:57-58)이 `MINOR == 7`을 단언 — P25를 MINOR로 하면 실패. MAJOR가 CONTEXT 권장과 일치.
- threshold `consecutive:3` → monitor.report의 `check_consecutive_failures` 경로(problem_monitor.py:86-98)에서
  3회 연속 시 알림 [VERIFIED — 제네릭 처리 확인]
- **5의 카운트 불일치 구조적 불가**: `/api/registry`의 by_kind("error")는 ERRORS 리스트 길이에서 계산 → P25 append 시
  25개 errors 자동 갱신 [VERIFIED]
- `lookup_reason("pipeline_exception")` → P25 즉시 반환 → dispatcher.py:962 일반 블록에서 `_spec = P25` +
  monitor.report phase="result_parse" 일치 → 발송 정상 [VERIFIED]
- **planner checkpoint**: `errors.py:17` "PROBLEM_REGISTRY 자체는 절대 수정하지 않는다" 해석 — append 확장이
  Phase 69 W1/W2 의도(자동 미러링 설계)에 부합함을 사용자에게 1회 확인 권장 (blocking 아님)

### ③ dispatcher.py:903-983 — summary 기록 추가 (신규, CONTEXT.md 반영 — S4 필수) [VERIFIED]

현재 일반 reason 분기(960-983, Phase 58 블록)에는 `_record_summary_event`가 **없음(재확인)**. P25 등록만으로는
daily_summary_events 0건 = S4 불충족. 변경 (additive):
```python
# 기존 선례 (변경 없음):
#   no_result 계열: 927-928 (917행의 None-가드 패턴 사용)
#   deploy_error:   894-895 (리터럴 "deploy_error" 문자열 — _problem_id 아님! [REVISED])
#   P16:            941-942
# 신규 (제안 — 일반 블록 962 `_spec = lookup_reason(reason)` 이후):
#   _spec이 None이 아니고 reason=="pipeline_exception"일 때
_record_summary_event(_ops_conn, datetime.now().strftime("%Y-%m-%d"), _spec.problem_id, blog_id)
```
- **범위 결정 지점 (discretion — planner 판단)**: CONTEXT ③ 문구는 "일반 분기에 lookup_reason(reason).problem_id로
  기록 1줄 추가" — **공통 기록**으로 하면 pipeline_exception 외에도 960+ 블록으로 흐르는 모든 reason(similar_title/P03,
  title_blocked/P10, rate_limited/P13, unknown 등)이 daily_summary_events에 새로 등장한다. 이는 "additive"로는 맞지만
  **대시보드 daily-summary 콘텐츠가 다른 reason에 대해 확장**되는 부수 효과가 있다.
  - **권장 (a) 좁은 범위**: `reason == "pipeline_exception"`(또는 `_spec.problem_id == "P25"`)일 때만 기록 → S4 정확 충족,
    기존 reason 노출 0 변화. 제로-리스크.
  - 대안 (b) CONTEXT 문구대로 공통 기록 → "표준화" 관점 일관성은 높으나 다른 reason들의 대시보드 노출이 확장됨.
  - 계획 단계에서 (a)/(b) 1회 결정 권장 (기본값: (a))
- `_record_summary_event(_ops_conn, summary_date, problem_id, blog_id)` 시그니처 (daily_summary.py:31-43, 4+1 인자) —
  dispatcher가 `init_daily_summary_tables(_ops_conn)` 소유 (921/940행 선례) [VERIFIED]
- **"P25" 문자열로 기록 권장**: `/api/daily-summary`는 problem_id를 그대로 집계(1255-1261) — "P25"로 기록하면
  index.html 배지(startswith 'P0'/'P1') 로직과 부합하고, 기존 P16·deploy_error 혼재 기록과 동일 관행 [VERIFIED]
- **RESOLVED (checkpoint 제거)**: 이전 RESEARCH의 "dispatcher.py:894 deploy_error 경로 `_problem_id` 선 참조(NameError
  가능)" — **재검증 결과 해당 참조는 존재하지 않음**. 894-895는 `"deploy_error"` 리터럴 문자열이다. NameError 없음,
  계획에서 checkpoint로 남길 필요 없음. [REVISED — 이전 문서의 MEDIUM 의심 해소]

### ④ scripts/auto_triage.py:1042-1076 — 매핑 추가 (신규, ⑤⑥ 정합성) [VERIFIED]

```python
# _reason_to_problem_id() dict(1044-1075)에 추가
"pipeline_exception": "P25",
```
- 없으면: scheduler.log 알림(`stage=pipeline_exception`, 639-644 파싱 → reason=stage, 659-662)을 트라이아지가
  `unknown_failure`로 분류(897) → `/api/registry` P25의 triage status가 fail로 안 바뀌고 severity/count 집계가
  "unknown_failure"로 새어나감 (P25 status=unknown 유지) [VERIFIED]
- 대안: 630-678 파싱 후 `lookup_reason(stage)` 사용으로 교체 (더 근본적이나 변경 범위 확대 — discretion)

### ⑤ S6 달성을 위한 테스트 정합 — tests/shared/test_problem_registry.py 수정 (신규 필수 발견) [VERIFIED]

> 기존 RESEARCH의 A3("길이 단언 테스트 존재 가능성 — 미확인")가 **실제 존재로 확인됨**. P25 append 시 실패하는
> 테스트를 그대로 두면 S6("23개를 더 늘리지 않는 것")에 위배된다. 이는 [TEST CODE] 수정이며, AGENTS.md §5
> (테스트 수정 vs production code 수정 분리)에 따라 [TEST CODE]로 명시한다.

| 테스트 (라인) | 단언 | P25 append 영향 | 필요한 수정 |
|---------------|------|-----------------|------------|
| `test_total_specs_is_25` (:47-48) | `len(PROBLEM_REGISTRY) == 25` | **실패 (25→26)** | `== 26` |
| `test_severity_counts_among_24_problems` (:50-55) | `len(problems)==24`, `CRITICAL==6`, `MAJOR==12`, `MINOR==6` | **실패 (24→25, MAJOR 12→13)** | `len(problems)==25`, `MAJOR==13` (P25=MAJOR) |
| `test_unknown_failure_minor_makes_total_minor_7` (:57-58) | `MINOR == 7` | 통과 (P25=MAJOR이면) | 없음 — **P25가 MINOR면 실패하므로 severity 고정 근거** |
| `test_registry_contains_all_p01_to_p24` (:60-62) | `{P01..P24} <= ids` | 통과 | 없음 |
| `test_every_inventory_reason_resolves_to_exactly_one_spec` (:79-85) | DEPLOY-PATHS.md Section C reason 전부 1 spec | 통과 ("pipeline_exception"은 인벤토리 미포함) | 없음 |
| `test_no_reason_key_shared_across_specs` (:87-93) | reason key 중복 없음 | 통과 (신규 유일 키) | 없음 |
| `test_all_templates_render_with_full_context_within_500_chars` (:115-129) | 전 spec 템플릿 ≤500자, 고정 context로 format | **P25 템플릿에 `{error}` 있으면 KeyError 실패** | 템플릿을 6-placeholder 형식으로 (②안 준수) |

- 신규 테스트 권장(추가, 기존 수정 아님): `lookup_reason("pipeline_exception").problem_id == "P25"`,
  dispatcher 예외 → JSON 변환(mock `_run_pipeline` raise RuntimeError), auto_triage
  `_reason_to_problem_id("pipeline_exception") == "P25"`.

### ⑥ /api/attention 노출 (CONTEXT.md 수정 반영 — 연구 발견 유지) [VERIFIED]

- **레지스트리 등록만으로는 불가능**: fail_checks는 `check_results` (db.py:793-918) 전용. P01~P24도 현재 attention에 없음.
- dashboard index 카드 표기 (index.html:57-79 daily_summary.breakdown 렌더) + 배지 색상: "P25"는 gray(bg-unknown).
  색상 1줄 개선은 선택 (68행: `elif pid.startswith('P2')` → 'warn')
- **실제로 이 페이즈가 "대시보드 표현" 1순위를 달성하는 경로 = ①+②+③+④가 만들어내는 3개 노출**:
  1. `/api/registry` errors 배열 — P25 자동 편입 (errors.py:39 import 미러) [VERIFIED]
  2. `/api/daily-summary` — daily_summary_events 기록분 집계 (③ 후) [VERIFIED]
  3. index.html 대시보드 홈 요약 카드 — daily_summary.breakdown 자동 렌더 (66-72행) [VERIFIED]
- ⑥(attention) 권장: 이번 페이즈 별도 변경 없음 — "P25가 registry/daily-summary에 보인다"를 성공 기준으로 유지.
  attention 확장(get_attention_items에 오류 선언 포함)은 별도 페이즈 후보.

---

## 3. 대시보드 표현 설계 (옵션)

| 옵션 | 설명 | 변경 범위 | 추천 |
|------|------|-----------|------|
| **A (권장)** | registry errors + daily-summary + index 카드 (66-72행) 자연 노출. P25 등록·요약 기록만으로 달성 | dispatcher + registry + auto_triage + test 정합 2건. ops_dashboard 0 변경 | ✅ — "대시보드 표현 1순위"를 최소 변경으로 충족, Phase 69 W1/W2 설계에 부합 |
| B | + attention fail_checks에 오류 선언 포함 (get_attention_items 확장) | ops_dashboard/db.py:793-918 수정 — P01~P24 전체 노출 동반 (파급 큼) | 보류 — 별도 페이즈 후보 |
| C | + index.html 배지 색상 1줄 (`P2` → warn) | 템플릿 1줄 (68행) | 옵션 — A에 곁들일 수 있음 |

선택 권장: **A + (선택) C**. B는 이 페이즈 스코프에서 제외 (기존 24개 동작 불변 원칙 ⑤와 충돌 방지).

---

## 4. 회귀 위험 & 테스트 (baseline — 재실행 [VERIFIED])

- **기준선 (재실행, 2026-08-10)**: `pytest tests -q` = **23 failed / 392 passed / 1 skipped / 25 warnings (2.18s)** —
  이전 RESEARCH와 정확히 일치. 23 failed는 pre-existing (이번 변경 무관). S6 목표 = "이 23개를 더 늘리지 않는 것".
- **problem_registry 필터 (재실행)**: `pytest tests -q -k problem_registry` = **17 passed, 399 deselected (0.53s)** —
  현재 25개 spec 기준 전부 green. **P25 append 시 17개 중 2개(test_total_specs_is_25, test_severity_counts_among_24_problems)가
  실패** (§2-⑤ 표의 수정 필요).
- 관련 테스트 위치 (변경 영향 선별용):
  - `tests/shared/test_problem_registry.py` — 위 §2-⑤ 표 참조. **계획에 [TEST CODE] 수정 태스크 필수 포함**.
  - `tests/test_dispatcher_registry.py` — dispatcher 동작 검증 (현재 23 failed 중 1건 `test_all_active_blogs_resolve` 포함 —
    pre-existing, 이번 변경 무관)
  - `tests/shared/test_problem_monitor.py` — 보고·차단 로직. P25 hook="result_parse"는 dispatcher phase 전달과 일치 —
    영향 없음 (dispatcher.py:982 phase=_spec.hook, problem_monitor.py:68-73 일치 확인)
- 테스트 신규 권장 (AGENTS.md "기존 기능 보존" — 추가 방식, §2-⑤ 말미):
  - dispatcher 예외 → `{"success": false, "reason": "pipeline_exception"}` JSON 반환 (mock `_run_pipeline` raise RuntimeError)
  - `lookup_reason("pipeline_exception")` → P25
  - auto_triage `_reason_to_problem_id("pipeline_exception")` → "P25"
  - daily_summary에 P25 기록 → `/api/daily-summary` breakdown에 나타남 (ops_dashboard/db.py get_daily_summary)
- 회귀 주의 1건: ③의 (b) 공통 기록 선택 시, 기존 reason(similar_title/P03 등)이 daily-summary에 새로 나타나는
  "표시 변화"를 대시보드 QA에서 확인할 것 (권장 (a) 좁은 범위라면 해당 없음)

---

## 5. 결론

| # | 변경 | 파일·라인 | CONTEXT.md와의 관계 | 성공 기준 |
|---|------|-----------|---------------------|-----------|
| 1 | try/except + reason 변환 | dispatcher.py:849 | 일치 | S1, S2 |
| 2 | P25 spec 등록 (MAJOR/consecutive:3/result_parse) | shared/problem_registry.py (556 unknown_failure 하단 append) | 일치 | S3, S5 |
| 3 | summary 이벤트 기록 (추천: pipeline_exception 전용) | dispatcher.py:960-983 블록 (additive) | CONTEXT 반영 — **S4 필수** | S4 |
| 4 | auto_triage reason 매핑 | scripts/auto_triage.py:1044-1075 dict | **신규 발견 — S5 정합성** | S5, S3(status fail 전환) |
| 5 | test 카운트 정합 2건 ([TEST CODE]) | tests/shared/test_problem_registry.py:48, 52-55 | **신규 발견 — S6 필수** | S6 |
| 6 | (~ 선택) 배지 색상 1줄 | index.html:68 | discretion | 표기 개선 |

**컨텍스트 반영/해소 사항 (2+1건):**
1. "P25 → attention 노출" → 실제 모델상 **registry errors + daily-summary로 노출** (attention은 check_results 전용 —
   P01~P24도 미노출). 성공 기준을 registry/daily-summary로 확정 (RESEARCH 2026-08-10 반영됨).
2. **RESOLVED**: "dispatcher.py:894 `_problem_id` 선 참조(NameError 가능)" checkpoint — 894-895는 리터럴
   `"deploy_error"` 사용으로 **NameError 없음**. 계획에서 checkpoint 제거.
3. **신규 checkpoint 2건**: (a) `errors.py:17` "PROBLEM_REGISTRY 절대 수정 금지" 해석(append 허용) 사용자 확인 1회;
   (b) ③ summary 기록 범위 (a) pipeline_exception 전용 vs (b) 일반 분기 공통 — 계획 단계 결정 1회 (기본값 (a)).

---

## Sources

### Primary (HIGH confidence) — 코드베이스 직접 재조회 (2026-08-10)
- dispatcher.py (1087줄): dispatch() 820-984, main() 1044-1087, _resolve_pipeline 417-470, _run_pipeline 498-502,
  ETAP_PIPELINE_BLOGS 512-522 (35개), WORKERS_BLOGS 525-537 (11개), _record_failure 802-815, imports 29-33
- scheduler.py (903줄): run_publish() 244-294 (중복 튜플 280), returncode 경로 282-285
- shared/problem_registry.py (575줄): P01~P24 54-538, unknown_failure 542-556, lookup_reason 559-564
- shared/problem_detectors.py (186줄), shared/problem_monitor.py (247줄): report() 53-106, _resolve() 108-156
- shared/daily_summary.py (178줄): init 27-28, record_event 31-43
- ops_dashboard/registry/errors.py (43줄): 미러링 39, docstring 17
- ops_dashboard/db.py (1992줄): get_attention_items 793-918, get_registry_view 1057-1237, get_daily_summary 1242-1278
- ops_dashboard/checks/__init__.py (111줄): run_all_checks 27-74, CHECKS import 77-110
- ops_dashboard/templates/index.html (286줄): breakdown 렌더 57-79, 배지 68
- ops_dashboard/app.py: /api/attention 464, /api/daily-summary 545, /api/registry 564, index 렌더 299-303
- scripts/auto_triage.py (1213줄): parse_scheduler_notifications 630-678, run_triage 874-897,
  _reason_to_problem_id 1042-1076
- shared/notification_classifier.py (36줄): REALTIME_PUSH_PROBLEMS 15-22
- tests/shared/test_problem_registry.py (183줄): 카운트 단언 47-58, 템플릿 115-129
- pipelines/curation/writer.py:838-846 (P22 선례)
- ops.db 읽기전용 조회: daily_summary_events (08-09/08-10), triage_classifications

### Secondary (MEDIUM confidence)
- CONTEXT.md (Phase 70 사용자 결정) — 2026-08-10 RESEARCH 반영본 그대로 유효
- 이전 RESEARCH.md (2026-08-10, 커밋 ec44527bf) — 재검증 기준선. drift 전부 [REVISED]로 표기

### Tertiary (LOW confidence)
- 없음 — 이전 문서의 유일한 LOW 항목("dispatcher.py:894 `_problem_id` NameError")은 재검증으로 **해소**됨 (리터럴 문자열 확인)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 코드베이스 직접 재조회. 신규 라이브러리 없음 (기존 패턴 재사용)
- Architecture: HIGH — 소비 경로(registry/daily-summary/attention) 전부 재검증
- Pitfalls: HIGH — 테스트 단언 2건 + template placeholder 제약 + severity 제약이 코드로 확인됨 (이전 MEDIUM → HIGH 상향)

**Research date:** 2026-08-10 (재검증: 2026-08-10 2차 실행)
**Valid until:** 2026-09-09 (코드베이스 정적 사실 기반, 30일 유효)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ~~dispatcher.py:894 deploy_error 경로 NameError 가능~~ — **해소됨**: 894-895는 리터럴 `"deploy_error"` 사용. NameError 없음 | §2-③ | 없음 — checkpoint 제거 |
| A2 | `pytest tests -q`의 23 failed가 pre-existing | §4 | 낮음 — baseline 동일(392/23/1) 재실행 확인 |
| A3 | ~~problem_registry 길이 단언 테스트 존재 가능성(미확인)~~ — **확인됨**: test_problem_registry.py:48(25) and :52-55(24/12) 존재. P25 append 시 실패 → [TEST CODE] 수정 태스크 계획 필수 | §2-⑤ | 중간 — 수정 누락 시 S6 위배 |
| A4 | errors.py:17 "PROBLEM_REGISTRY 절대 수정 금지"가 append를 허용한다는 해석 | §2-② | 중간 — 사용자 확인 checkpoint 1회 권장 |
| A5 | ③의 summary 기록 범위를 pipeline_exception 전용((a))으로 기본 선택 | §2-③ | 낮음 — (b) 공통 기록은 대시보드 콘텐츠 확장 부수 효과 |

## Environment Availability

Step 2.6: SKIPPED (외부 도구 의존 없음 — 코드 변경만. Python 3.14 + 로컬 파일 수정. 배포/wrangler/DB
변경 없음. 파괴적 작업 프로토콜 불필요 — 단, 테스트 2건 [TEST CODE] 수정은 파괴적 아님)