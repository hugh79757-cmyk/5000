# Phase 70 — Research: Pipeline Exception → Dashboard Exposure

**Researched:** 2026-08-10
**Domain:** 파이프라인 예외 → 규격화 reason → Ops Dashboard 표현 (dispatcher/scheduler/problem_registry/ops_dashboard)
**Confidence:** HIGH (모든 file:line 참조는 코드베이스 직접 조회로 검증됨 — CONTEXT.md의 2건 오류 발견, §2 참조)

## Summary

오늘(2026-08-10) 71회 crash(`AttributeError: 'list' object has no attribute 'split'`)가 대시보드에 안
보인 근본 원인은 dispatcher `dispatch()`가 `_run_pipeline(cfg)`(dispatcher.py:849)를 try/except
없이 호출해 subprocess가 traceback + exit 1로 죽고, scheduler `run_publish()`의 returncode!=0
경로(scheduler.py:282-285)가 `_tg_error(blog_id, "scheduler", stderr[-300:])` raw traceback만
발송하기 때문이다. stdout에 JSON이 없어 dispatcher 내부의 실패 기록 로직(`_record_failure` /
`lookup_reason` / `_record_summary_event` / monitor)이 전부 미도달한다.

조사 결과 변경 지점은 CONTEXT.md의 2곳이 아니라 **4곳**이다:

1. **dispatcher.py:849** — `_run_pipeline(cfg)` 호출을 try/except로 감싸
   `{"success": False, "reason": "pipeline_exception", "error": "Type: msg"}` 반환 (CONTEXT.md와 일치)
2. **shared/problem_registry.py** — P25 spec 등록 (일치. `/api/registry` errors 배열은 이 파일에서
   **import 시 자동 미러링**되므로 ops_dashboard 측 별도 선언 불필요)
3. **dispatcher.py:903-983 실패 분기** — ⚠️ **CONTEXT.md 예상과 다름**: `_record_summary_event()`는
   `no_result` 계열(927-928)·`deploy_error`(894-895)·`duplicate_*`(941-942) 3곳에만 하드코딩되어
   있고, 일반 reason 분기(Phase 58 모니터 매핑 블록 960-983)에서는 호출되지 않는다. **P25 등록만으로는
   `daily_summary_events` 0건** → `/api/daily-summary`·index.html 요약 카드에 안 보인다.
   dispatcher에 summary-event 기록 추가(additive)가 필수이다.
4. **scripts/auto_triage.py:1042-1076 `_reason_to_problem_id()`** — 하드코딩 매핑에
   `"pipeline_exception": "P25"` 추가 (또는 `lookup_reason` 교체). 없으면 scheduler.log 파싱
   트라이아지 경로가 `unknown_failure`로 분류한다.

또 하나의 CONTEXT.md 오류: "P25 → /api/attention에 노출"은 레지스트리 등록만으로 달성 불가 —
`/api/attention` fail_checks는 **check_results 테이블 전용**(db.py:793-918)이라 P-문제는 원래
안 들어온다. P01~P24도 현재 attention에 없고 `/api/registry` errors 배열 + `/api/daily-summary`로
노출된다 (§3 옵션 A/B).

**Primary recommendation:** ① dispatcher try/except + ③ (신) 요약 이벤트 기록 + ② P25 등록 +
④ auto_triage 매핑 추가. 대시보드·템플릿·DB 스키마 변경 없이 index.html 요약 카드·
`/api/registry` errors 배열·`/api/daily-summary`에 자동 노출된다.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- ① dispatcher.py `_run_pipeline(cfg)` 호출부를 try/except로 감싸, 예외 시
  `{"success": false, "reason": "pipeline_exception", "error": "Type: msg"}` JSON 반환 (crash 대신)
- ② pipeline_exception reason → 문제 레지스트리 등록 (후보 id P25) — `shared/problem_registry.py` /
  `shared/problem_detectors.py`에 spec 추가 → `/api/registry` errors 배열에 표시
- 대시보드 표현이 이번 페이즈의 **1순위 주제** (단순 crash 방지가 아님)
- 성공 기준 6개: ① dispatcher가 crash 없이 JSON 출력 ② scheduler가 stage=pipeline_exception 정상
  파싱 ③ P25가 registry errors + 노출 ④ daily_summary_events에 N회 기록 → `/api/daily-summary` 집계
  ⑤ 기존 P01~P24 spec·동작 불변 ⑥ 기존 테스트 스위트 green 유지

### the agent's Discretion
- (컨텍스트상) P25 spec의 세부 필드(severity/threshold/alert_template/action) 값 — RESEARCH 결과 추천
- (컨텍스트상) `/api/attention` 표현 방식 — RESEARCH 결과 옵션 제시

### Deferred Ideas (OUT OF SCOPE)
- 문제 B (dining-hugo stage=unknown, reason 없는 실패) 근본 원인 조사 — 별도 조사
- `scheduler.py:287` `except (_json.JSONDecodeError, Exception)` 중복 튜플 정리 — 사소 정리
- Telegram 전체 발송 건수 검증 (수신 측 확인 수단 부재)
- 71회 crash 원인 자체 (`hugo_writer.py:198 tags.split`) — 2d47afd51로 수정 완료. 이 페이즈에서 계획 금지
</user_constraints>

<phase_requirements>
## Phase Requirements

> orchestrator가 공식 REQ-ID를 제공하지 않았으나, CONTEXT.md 성공 기준 6개가 이 페이즈의 요구사항이다.

| ID | Description (CONTEXT 성공 기준) | Research Support |
|----|---------------------------------|------------------|
| S1 | dispatcher가 예외 시 crash 없이 JSON 출력 | §2-① 정확 삽입점 (dispatcher.py:849), 기존 정규화 851-863 |
| S2 | scheduler가 stage=pipeline_exception 정상 파싱 | scheduler.py:272-281 last-line JSON 파싱은 reason 독립적 — 확인됨 |
| S3 | P25가 registry errors 배열 (+노출) | problem_registry 등록 → ops_dashboard/registry/errors.py:39 자동 미러링 [검증됨] |
| S4 | daily_summary_events N회 기록 → `/api/daily-summary` 집계 | **추가 변경 필요** — §2-③ (기존 코드로는 0건) [검증됨] |
| S5 | 기존 P01~P24 spec·동작 불변 | P25는 append만; `_to_entry`가 전 spec 미러링 → 카운트 불일치 구조적 불가 [검증됨] |
| S6 | 기존 테스트 스위트 green 유지 | baseline 392 passed / 23 pre-existing failed / 1 skipped (§4) [검증됨] |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 파이프라인 예외 포착·규격화 | API/Backend (dispatcher.py) | — | 예외는 `dispatch()` 실행 스레드에서 발생 — 여기서 reason dict로 변환돼야 scheduler·summary·monitor가 소비 가능 |
| reason → problem_id 매핑 | API/Backend (shared/problem_registry.py) | — | 25개 spec 단일 소스; dashboard errors 배열이 import 시 미러링 |
| 실패 기록 (ledger/summary/monitor 알림) | API/Backend (dispatcher 실패 분기) | — | dispatcher가 카운터·요약 이벤트 소유자 (W-1 설계); 모니터는 extra만 소비 |
| 대시보드 노출 (registry errors / daily-summary / attention) | Frontend Server (ops_dashboard, Flask) | — | ops.db read-only 렌더; 스키마 변경 불필요 |
| 트라이아지 분류 (scheduler.log 경로) | API/Backend (scripts/auto_triage.py) | — | scheduler.log의 stage= 파싱 → reason → P-id 매핑 (하드코딩 dict) |

핵심: 변경은 전부 "API/Backend 티어의 생산자(dispatcher) + 레지스트리"에만 있다. 대시보드 티어는
수정 불필요 (기존 소비 패턴이 이미 reason/event 기반이기 때문).

---

## 1. 실행 경로 추적 (현재 상태)

> 모든 file:line은 코드베이스 직접 조회 기준 — `[VERIFIED: 코드베이스 직접 조회]`

### 1.1 dispatcher.py — dispatch() 흐름

| 위치 | 코드 | 역할 |
|------|------|------|
| **dispatcher.py:849** | `result = _run_pipeline(cfg)` | **핵심 — try/except 없는 bare 호출. 예외 시 dispatch() 자체가 죽음** |
| dispatcher.py:498-502 | `_run_pipeline()` = `_resolve_pipeline(blog_id, pipeline, cfg)` | pipeline별 run(cfg) 라우팅 (STAP/TAP subprocess 포함) |
| dispatcher.py:851-863 | None → `{"success": False, "reason": "no_result"}` + cooldown(852-854); str → reason 매핑(855-861); bool → `{"success": result}`(862-863) | 결과 정규화 — 여기로 흘러들면 이후 로직 전부 동작 |
| dispatcher.py:865-882 | success 시 `_record_ledger`/`_reset_failure_count`/`_reset_extended_failure_keys` + **ETAP/WORKERS deploy 분기**(869-880; `_build_and_deploy_central` 실패 시 monitor.report phase="post_deploy") | 성공 경로 |
| dispatcher.py:882-902 | `deploy_err` 처리 → `_record_failure` + `_debounce_push` + `_tg_error` + **`_record_summary_event(..., "deploy_error", blog_id)` (894-895)** | 배포 실패 — summary 기록 예 |
| dispatcher.py:903-921 | 실패: `reason = result.get("reason", "unknown")` (904); `_record_failure(blog_id, reason, ...)` (906); `no_result` 계열(908) → `_problem_id = lookup_reason(reason).problem_id` (917) + **`_record_summary_event(..., _problem_id, blog_id)` (927-928)** | no_result 계열 — summary 기록 예 |
| dispatcher.py:934-945 | `duplicate_slug/duplicate_source_id` → `_record_summary_event(..., "P16", blog_id)` (941-942) | P16 — summary 기록 예 |
| dispatcher.py:960-983 | **Phase 58 모니터 매핑 블록 (additive)**: `_spec = lookup_reason(reason)` (962); None → 경고만 (963-966); 있으면 `_increment_failure_count(blog_id, _spec.problem_id)` (971/974) + `get_monitor().report(blog_id, {"reason": reason}, phase=_spec.hook, extra={"consecutive_failures": _consec})` (979-983) | **일반 reason 분기 — summary 기록 없음. pipeline_exception이 여기 도달하면 monitor 알림은 가지만 daily_summary_events는 0건** |
| dispatcher.py:1078-1083 | `result = dispatch(cmd); print(json.dumps(result, ensure_ascii=False))` (1081) | stdout JSON = scheduler 파싱 대상 |
| dispatcher.py:29-33 | `_tg_error`, `lookup_reason`, `get_monitor`, `_record_summary_event`/`init_daily_summary_tables`, `_debounce_push`/`init_debounce_tables` import | **필요 import 전부 이미 존재** — try/except 추가 시 import 변경 없음 |

### 1.2 scheduler.py — run_publish() (244-294)

| 위치 | 코드 | 역할 |
|------|------|------|
| scheduler.py:262-267 | `subprocess.run([PYTHON, "dispatcher.py", blog_id], capture_output=True, text=True, timeout=600)` | dispatcher subprocess 실행 |
| scheduler.py:268-281 | stdout 마지막 줄 `json.loads` (272-274); `parsed.get("success")` → 성공; 아니면 `reason = parsed.get("reason", "unknown"); logger.error(f"[PUBLISH] {blog_id} 발행 실패 — stage={reason}")` (278-279) | **JSON 파싱은 reason 값과 무관 — stage=pipeline_exception 그대로 로그됨. "정상 파싱" 확인됨** |
| scheduler.py:282-285 | `if result.returncode != 0 and result.stderr:` → `_tg_error(blog_id, "scheduler", stderr[-300:])` + `return False` | **현재 crash 경로의 raw traceback 발송 지점** — ① 적용 후 returncode=0 → 미도달 |
| scheduler.py:287-294 | TimeoutExpired / 일반 Exception → `_tg_error` | subprocess 자체 예외 (스코프 외) |

### 1.3 shared/problem_registry.py — 구조 (575줄, [VERIFIED])

- `SEVERITIES/HOOKS/THRESHOLDS` (16-18): `("CRITICAL","MAJOR","MINOR")` / `("result_parse","post_generate","post_validate","post_publish","post_deploy")` / `("always","consecutive:N","quiet")`
- `ProblemSpec` dataclass (21-34): `problem_id, name_ko, severity, reason_keys(tuple), hook, alert_template, threshold, cooldown_minutes=60, action="", detect_fn=""`
- `PROBLEM_REGISTRY` dict + `_register()` (47-51)
- P01~P24 등록 (54-538): CRITICAL/always 계열 P04/P05/P06/P07/P08/P09; MAJOR/consecutive:3 계열 P01/P02/P03/P10/P11/P12/P13/P14/P15/P20/P21/P22; MINOR/quiet 계열 P16/P17/P18/P19/P23/P24
- **P20~P24 형태** (357-538): `reason_keys`에 reason 문자열 튜플; `hook="result_parse"` (P20/P21/P22); alert_template에 `{blog_id}/{problem_id}/{name_ko}/{phase}/{consecutive}/{action}` placeholders
- **`unknown_failure`** (542-556): reason_keys=() **빈 튜플** → `lookup_reason()`은 어느 reason도 여기로 매핑하지 않음 (unregistered reason은 None 반환; dispatcher.py:963-966에서 경고 후 monitor 생략)
- `lookup_reason()` (559-564): reason → spec 역방향 탐색, **미등록이면 None**
- `lookup_problem()` / `lookup_hook()` (567-575)

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
→ P22(ai_writer.py:315 `raise RuntimeError(msg)` — 폴백 체인 전부 소진)를 잡아 reason으로 보고 후
재전파하는 선례. 이 페이즈는 **re-raise가 아니라 결과 dict 변환**이므로 방향만 다름.

### 1.4 shared/problem_detectors.py + problem_monitor.py — 배선 ([VERIFIED])

- `problem_detectors.py` (186줄): `detect_post_generate`(P07/P08/P09/P23), `detect_validation_issue`(P15)
  존재 — **result_parse 훅용 탐지 함수 없음. P25는 reason_keys 기반이므로 detectors 변경 불필요.**
- `problem_monitor.py::report()` (53-106): `_resolve()`가 `{"reason": ...}` → `lookup_reason()` (137-153).
  P25를 registry에 등록하면 자동 해석 (미등록 reason은 141행 경고 후 []). spec.hook != phase면 발송 차단
  (68-73) — **P25 hook="result_parse"로 지정하면 dispatcher.py:982의 phase 전달과 일치**
- dispatcher → monitor 배선: dispatcher.py:979-983 `get_monitor().report(...)` — 이미 존재. 신규 배선 불필요

### 1.5 daily_summary — 표기·집계 ([VERIFIED])

- `shared/daily_summary.py:31-43` `record_event(conn, summary_date, problem_id, blog_id, count=1)`
  → `INSERT INTO daily_summary_events`
- dispatcher.py:32 `from shared.daily_summary import record_event as _record_summary_event, init_daily_summary_tables`
- ops_dashboard/db.py:1242-1278 `get_daily_summary()`: `SELECT problem_id, blog_id, SUM(count) FROM
  daily_summary_events WHERE summary_date=? GROUP BY problem_id, blog_id` → breakdown/blog_by_problem.
  **problem_id 문자열을 그대로 집계 — 스키마 변경 없이 "P25"든 "pipeline_exception"이든 동작** (기존에도
  "deploy_error" 문자열과 "P16" 문자열이 혼재 기록되는 비일관성 있음)

### 1.6 ops_dashboard — 소비 경로 ([VERIFIED])

- `ops_dashboard/registry/errors.py:39` — `ERRORS = [_to_entry(spec) for spec in PROBLEM_REGISTRY.values()]`
  → **shared/problem_registry에 P25 추가 시 /api/registry errors 배열에 자동 편입** (import 시 동적 미러링,
  Phase 69 W1 설계; PROBLEM_REGISTRY 수정 금지 조항은 "기존 spec 미수정" 의미 — append는 허용 및 의도된 확장)
- `ops_dashboard/db.py:1057-1237 get_registry_view()`: errors 항목 = `by_kind("error")` 선언 +
  `triage_classifications` 최신 1행 (1229-1234). **triage 행 없으면 status="unknown"** — P25 등록 직후엔
  unknown으로 표시, auto_triage가 분류한 뒤 fail/auto_handled 등으로 갱신
- `ops_dashboard/db.py:793-918 get_attention_items()`: fail_checks = **check_results 테이블 fail 행 전용**.
  P-문제(오류 선언)는 이 경로에 없음 → `/api/attention`에 P25가 뜨려면 별도 작업 필요 (§3)
- `ops_dashboard/checks/__init__.py:27-74 run_all_checks()`: 등록 CHECKS(standard/freshness/render/
  crosscheck/maintenance/crosslink/content_integrity)만 check_results에 기록 — 오류 선언은 실행 대상 아님
- `ops_dashboard/templates/index.html:57-79`: `daily_summary.breakdown` 렌더 — **P25 이벤트 기록 시 자동 표시**
  (`{{ pid }}` ×`{{ cnt }}` (blog 목록)). 배지 색상 로직(68행): `'fail' if pid.startswith('P0') else
  'warn' if pid.startswith('P1') else 'unknown'` → **"P25"는 'P2'로 시작해 gray(unknown) 배지** (표시는 되나
  색상이 warn/fail이 아님 — 선택적 1줄 개선 지점)
- `scripts/auto_triage.py:630-675 parse_scheduler_notifications()`: scheduler.log에서 `stage=(\S+)` 파싱
  (643), reason 없으면 stage를 reason으로 사용 (656-662). `run_triage` 874-897: scheduler 알림 →
  `_reason_to_problem_id(reason)` (893); **미매핑이면 `unknown_failure`로 분류 (897)**
- `scripts/auto_triage.py:1042-1076 _reason_to_problem_id()`: 하드코딩 dict — `"pipeline_exception"` **없음**
- `shared/notification_classifier.py:15-22`: `REALTIME_PUSH_PROBLEMS` 하드코딩 frozenset — P25 미포함
  → daily_summary의 실시간 푸시 분류에서 "summary" 버킷 (요약 집계에는 무관)---

## 2. 변경 지점 확정 (4곳 + 성공 기준 검증)

> 빨간줄: CONTEXT.md의 2곳은 정확했으나, **S4(daily_summary 0건) 문제로 ③이 필수 추가**되었고,
> **⑤/⑥에서 ④(auto_triage)도 추가 필요**가 확인됐다. 또한 "/api/attention 노출"은 레지스트리
> 등록만으로 불가능함이 확인됐다 (§3).

### ① dispatcher.py:849 — try/except 래핑 (CONTEXT.md와 일치) [VERIFIED]

```python
# dispatcher.py:849 현재
result = _run_pipeline(cfg)
# 변경: bare 호출을 try/except로 감싸 JSON 반환
try:
    result = _run_pipeline(cfg)
except Exception as _e:
    if not isinstance(_e, KeyboardInterrupt):
        logger.exception(f"[dispatch] {blog_id} pipeline 예외 (type={type(_e).__name__})")
    result = {"success": False, "reason": "pipeline_exception",
              "error": f"{type(_e).__name__}: {_e}"}
```
- 정규화(851-863)는 result가 dict면 그대로 통과(`result.get` 사용 — 854/860행의 str/bool 분기와
  무관하게 dict는 851-852의 None 체크 후 862-863의 dict 반환 경로로 흘러간다. 확인: 851행
  `if result is None` → 855 `elif isinstance(result, str)` → 862 `elif isinstance(result, bool)` →
  dict는 마지막 `return result`(863) 착지)
- import 변경 불필요 (dispatcher.py:29-33 전부 존재) — additive 수정
- `error` 키는 기존 소비자에 영향 없음: scheduler는 reason만 읽고, 모니터는 `result["reason"]`(904)
  만 소비. `PYSET/PYENV` 등은 스코프 외.
- **S1 충족 확인**: stdout JSON 출력(1081)은 dispatch() 반환을 찍는 것이므로 crash 없이 반환되면
  JSON 보장.

### ② shared/problem_registry.py — P25 spec 등록 (CONTEXT.md와 일치) [VERIFIED]

P20~P24 블록(357-538) 하단에 append (기존 spec 미수정 — Phase 69 "PROBLEM_REGISTRY 수정 금지"는
기존 항목 불변 의미, W2 확장 허용):
```python
_register(ProblemSpec(
    problem_id="P25",
    name_ko="파이프라인 예외 (pipeline_exception)",
    severity="MAJOR",
    reason_keys=("pipeline_exception",),
    hook="result_parse",
    alert_template="{blog_id} {problem_id} {name_ko} phase={phase} consecutive={consecutive} — {error}",
    threshold="consecutive:3",
    cooldown_minutes=60,
    action="dispatcher.py:849 예외를 reason으로 규격화 — dispatcher 로그에서 원인 확인",
))
```
- **5의 카운트 불일치 구조적 불가**: `/api/registry`의 `total_by_severity`/`by_kind("error")`는
  `ERRORS` 리스트 길이에서 계산 (errors.py:39 → get_registry_view) → P25 append 시 25개가 되어
  기존 24개 표기의 헬스체크/카운트 자동 갱신 (get_registry_view의 cross-phase 계약은 "선언과
  실데이터 단일 스키마" — append가 설계된 확장)
- `lookup_reason("pipeline_exception")` → P25 바로 반환 → dispatcher.py:917(no_result 블록)이 아닌
  962(일반 블록)에서 `_spec = P25` + monitor.report phase="result_parse" 일치 → 발송 정상
- alert_template은 P20~P24와 동일 placeholder 구조. `{error}`는 dispatcher 결과 dict의 "error" 키가
  아니고 monitor.report extra로 전달되는 "consecutive"만 존재 — 템플릿에 `{error}`를 넣으면
  **P20~P24와 동일한 placeholder 미치환 패턴**으로 남는다 (P21 템플릿도 `{action}` 미치환 확인). 이는
  기존 계열과 일관된 관행이므로 유지하되, 연구 권장: `extra={"error": ...}` 전달 선택사항으로 명시.

### ③ dispatcher.py:903-983 — summary 기록 추가 (신규, CONTEXT.md에 없음 — S4 필수) [VERIFIED]

현재 일반 reason 분기(960-983)에는 `_record_summary_event`가 없다. **P25 등록만으로는
daily_summary_events 0건** = success criteria ④ 불충족. 변경 (additive):
```python
# dispatcher.py:903-921 실패 블록 내, _record_summary_event 호출 위치의 선례:
#   no_result 계열: 927-928 (단, no_result는 cooldown stack으로 잡혀 927로 안 오는 케이스 존재)
#   deploy_error: 894-895, P16: 941-942
# 신규: 904행 reason 확정 직후 공통 기록 (기존 reason별 분기와 독립)
_record_summary_event(run_date, _problem_id, blog_id)   # _problem_id는 lookup_reason(reason).problem_id (917행 패턴)
```
- 문제: `_problem_id`는 no_result 블록(908) 안에서만 정의됨 (917행). 일반 블록(960+)에서는
  `_spec = lookup_reason(reason)` 후 `_spec.problem_id`로 동일 값을 얻을 수 있음.
  **함수 시그니처/기존 동작 변경 없이** 960-966 근처에 summary 기록 1줄 추가하는 것을 권장
  (구현 세부는 플래너 판단 영역 — RESEARCH는 위치·선례만 확정).
- `_record_summary_event(run_date, problem_id, blog_id)` 시그니처 (daily_summary.py:31-43, 4개 인자:
  conn, summary_date, problem_id, blog_id) — dispatcher가 `init_daily_summary_tables(conn)` 소유.
  P16 선례(941-942)가 정확한 호출 형태.
- **"P25" 문자열 vs reason 문자열**: `/api/daily-summary`는 problem_id를 그대로 집계하므로 "P25"로
  기록하면 문제 ID로 표기되고, 기존 "deploy_error" 문자열 기록과 혼재된다. P16처럼 **problem_id
  (="P25")로 기록**하는 것이 대시보드 배지 로직(startswith 'P0'/'P1')에 부합.
- **빠진 검증 1건 (연구 중 발견)**: dispatcher.py:894-895 deploy_error의 summary 기록도
  `_problem_id`를 쓰는데 이는 실패 블록(903+)의 로컬 변수 — 894행 시점에 정의돼 있지 않다.
  **기존 코드가 이미 동작 중인지 확인 필요** (왜 안 죽는지: 894행 실행 시점에 `_problem_id`가
  이전 반복에서 남아있거나 NameError일 수 있음). → 계획 전에 dispatcher.py 실행 경로 확인을
  checkpoint로 남길 것 (flag: MEDIUM 의심 — `deploy_err` 경로 실행 시 NameError 가능성).

### ④ scripts/auto_triage.py:1042-1076 — 매핑 추가 (신규, CONTEXT.md에 없음 — ⑤⑥ 정합성) [VERIFIED]

```python
# _reason_to_problem_id() dict에 추가
"pipeline_exception": "P25",
```
- 없으면: scheduler.log 알림(단계문자 `stage=pipeline_exception`)을 트라이아지가
  `unknown_failure`로 분류 → `/api/registry` P25의 triage status가 fail로 안 바뀌고
  severity/count 집계가 "unknown_failure"로 새어나감 (P25 status=unknown 유지)
- 대안: 630-675의 파싱 후 `lookup_reason(stage)` 사용으로 교체 (더 근본적이나 변경 범위 확대 —
  discretion)

### ⑤ /api/attention 노출 (CONTEXT.md 수정 필요 — 연구 발견) [VERIFIED]

- **레지스트리 등록만으로는 불가능**: fail_checks는 `check_results` (db.py:793-918 관찰) 전용.
  P01~P24도 현재 attention에 없음 — 즉 P25를 attention에 넣는 것은 기존 24개와 다른 경로로
  "특별 대우"가 되며, 컨텍스트의 기대("P25 → attention")가 실제 대시보드 모델과 어긋난다.
- dashboard index 카드·페이지 표기 (index.html:57-79 daily_summary.breakdown 렌더) + 배지 색상:
  "P25"는 gray(bg-neutral). 색상 1줄 개선은 선택 (240: `elif pid.startswith('P2')` → 'warn')
- **실제로 이 페이즈가 "대시보드 표현" 1순위를 달성하는 경로 = ①+②+③+④가 만들어내는
  3개 노출**:
  1. `/api/registry` errors 배열 — P25 자동 편입 (errors.py:39 import 미러)
  2. `/api/daily-summary` — daily_summary_events 기록분 집계 (③ 후)
  3. index.html 대시보드 홈 요약 카드 — daily_summary.breakdown 자동 렌더
- ⑤(attention)에 대한 권장: **이번 페이즈에서는 별도 변경 없음** — 대신 "P25가 registry/daily-summary
  에 보인다"를 성공 기준으로 재정의할 것을 사용자에게 제안 (또는 원하면 attention 확장은 별도
  작업으로 분리). planner는 discretionary하게 결정하되, attention 수정은 ops_dashboard/db.py
  get_attention_items() 확장(오류 선언 포함)이라는 **플랫폼-wide 변경**임을 명시.

---

## 3. 대시보드 표현 설계 (옵션)

| 옵션 | 설명 | 변경 범위 | 추천 |
|------|------|-----------|------|
| **A (권장)** | registry errors + daily-summary + index 카드 (67행) 자연 노출. P25 등록·요약 기록만으로 달성 | dispatcher + registry + auto_triage (코드 4곳). ops_dashboard 0 변경 | ✅ — "대시보드 표현 1순위"를 최소 변경으로 충족, Phase 69 W1/W2 설계에 부합 |
| B | + attention fail_checks에 오류 선언 포함 (get_attention_items 확장) | ops_dashboard/db.py:793-918 수정 — P01~P24 전체 노출 동반 (파급 큼) | 보류 — 별도 페이즈 후보 |
| C | + index.html 배지 색상 1줄 (`P2` → warn) | 템플릿 1줄 | 옵션 — A에 곁들일 수 있음 |

선택 권장: **A + (선택) C**. B는 이 페이즈 스코프에서 제외 (기존 24개 동작 불변 원칙 ⑤와 충돌 방지).

---

## 4. 회귀 위험 & 테스트 (baseline [VERIFIED])

- 기준선: `pytest tests -q` = **392 passed / 23 failed / 1 skipped** (23 failed는 2026-08-10 이전부터
  존재하던 pre-existing — 리서치 전/후 변동 없음 관찰). S6 목표 = "이 23개를 더 늘리지 않는 것".
- 관련 테스트 위치 (변경 영향 선별용):
  - `tests/test_dispatcher.py::test_dispatch_*` — dispatch() 반환 구조 검증. ①③ 변경 시 반환 dict
    형태 유지하면 green.
  - `tests/test_scheduler.py::test_run_publish_*` — subprocess 파싱. ①로 returncode=0이 되면
    기존 stderr 경로 테스트가 다른 시나리오로 남음 — **테스트 수정이 아닌 추가 관찰** 필요
    (기존 테스트가 crash stderr 케이스를 어떻게 mocking하는지 확인).
  - `tests/test_problem_registry.py` (또는 동일 파일 내): `PROBLEM_REGISTRY` 길이·reason_keys
    uniqueness 단언이 있을 수 있음 (grep: `pytest tests -q -k problem_registry`). P25 append로
    "25개" 단언이 있다면 수정 필요 — **연구에서 확인 필요 지점 (plan 전 grep 1회)**.
  - `tests/test_problem_monitor.py`: 보고·차단 로직. P25 hook="result_parse"는 기존 dispatch
    phase 전달과 일치하므로 영향 없음 (확인: dispatcher.py:982 phase=_spec.hook).
- 테스트 신규 권장 (단, AGENTS.md "기존 기능 보존" — 추가 방식):
  - dispatcher 예외 → JSON 반환 (mock `_run_pipeline` raise RuntimeError)
  - lookup_reason("pipeline_exception") → P25
  - auto_triage `_reason_to_problem_id("pipeline_exception")` → "P25"
  - daily_summary에 P25 기록 → `/api/daily-summary` breakdown에 나타남 (ops_dashboard/get_daily_summary)

---

## 5. 결론

| # | 변경 | 파일·라인 | CONTEXT.md와의 관계 | 성공 기준 |
|---|------|-----------|---------------------|-----------|
| 1 | try/except + reason 변환 | dispatcher.py:849 | 일치 | S1, S2 |
| 2 | P25 spec 등록 | shared/problem_registry.py (537행 P24 하단) | 일치 | S3, S5 |
| 3 | summary 이벤트 기록 (common) | dispatcher.py:960-983 블록 (additive) | **신규 발견 — S4 필수** | S4 |
| 4 | auto_triage reason 매핑 | scripts/auto_triage.py:1042-1076 | **신규 발견 — S5 정합성** | S5, S3(status fail 전환) |
| 5 | (~ 선택) 배지 색상 1줄 | index.html:68 | discretion | 표기 개선 |

**컨텍스트 수정 요청 (2건):**
1. "P25 → attention 노출" → 실제 모델상 **registry errors + daily-summary로 노출** (attention은
   check_results 전용 — P01~P24도 미노출). 이 페이즈달성 목표를 registry/daily-summary로 재정의 제안.
2. 구현 단계에서 **dispatcher.py:894 `_problem_id` 선 참조 의심(NameError 가능)** 확인 — 배포 실패
   경로의 기존 동작 검증 1회 (연구가 발견한 기존 잠재 버그, 이 페이즈 수정 범위 아님).

---

## Sources

### Primary (HIGH confidence)
- 코드베이스 직접 조회 (grep/read, 2026-08-10): dispatcher.py(1083줄), scheduler.py(296줄),
  shared/problem_registry.py(575줄), shared/problem_detectors.py(186줄),
  shared/problem_monitor.py(157줄), shared/daily_summary.py(63줄), ops_dashboard/registry/errors.py,
  ops_dashboard/db.py(get_attention_items 793-918, get_registry_view 1057-1237, get_daily_summary
  1242-1278), ops_dashboard/checks/__init__.py(run_all_checks 27-74),
  ops_dashboard/templates/index.html(57-79), scripts/auto_triage.py(parse_scheduler_notifications
  630-675, run_triage 874-897, _reason_to_problem_id 1042-1076),
  shared/notification_classifier.py(15-22), pipelines/curation/writer.py(838-846 P22 선례)

### Secondary (MEDIUM confidence)
- CONTEXT.md (Phase 70 사용자 결정) — 2곳 오류 지적은 이 문서와의 대조로 발생

### Tertiary (LOW confidence)
- "dispatcher.py:894 `_problem_id` NameError" — 이동 경로에서의 변수 생존 가정 (MEDIUM 의심,
  실행 확인 필요)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 코드베이스 직접 조회. 신규 라이브러리 없음 (기존 패턴 재사용)
- Architecture: HIGH — 소비 경로(registry/daily-summary/attention) 전부 검증
- Pitfalls: MEDIUM — `_problem_id` 선 참조 의심은 실행 확인 필요 (LOW~MEDIUM)

**Research date:** 2026-08-10
**Valid until:** 2026-09-09 (코드베이스 정적 사실 기반, 30일 유효)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | dispatcher.py:894 deploy_error 경로에서 `_problem_id`가 정의되지 않아 NameError 가능 | §2-③ | 없음 — 수정 범위 아님, 확인만 (checkpoint로 명시) |
| A2 | `pytest tests -q`의 23 failed가 pre-existing (이번 변경 무관) | §4 | 낮음 — baseline 대비 diff로 검증 |
| A3 | problem_registry 길이 단언 테스트 존재 가능성 (미확인) | §4 | 중간 — ① 변경 시 해당 단언 실패 → "테스트 수정"이 아닌 "스펙 변경 반영"으로 분류 |

## Environment Availability

Step 2.6: SKIPPED (외부 도구 의존 없음 — 코드 변경만. Python 3.14 + 로컬 파일 수정. 배포/wrangler/DB
변경 없음. 파괴적 작업 프로토콜 불필요)