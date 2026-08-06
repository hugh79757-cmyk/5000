# Phase 58 — 발행 문제 인벤토리 + 정밀 Telegram 알림 시스템 실행 계획

> 상태: 계획 수립 (2026-08-06) → **v2 (PLAN-CHECK FAIL 반영 — MAJOR 3건 수정: T4 실 ThresholdChecker
> API 기반 발송 메커니즘, P07 테스트 기대치 정정, P22 탐지 경로 배선 + MINOR W-1/W-3/W-4/M-7/M-11/M-12)
> 근거: `RESEARCH.md`(24개 문제 인벤토리, file:line 검증 완료) + `CONTEXT.md`(계약/확정 설계 결정)
> 작업 규칙: **additive, non-destructive** (AGENTS.md 코드 수정 원칙). 기존 `_tg_error` 호출 경로
> (dispatcher.py:709/715/718/723/697, curation pipeline.py:857, scheduler.py:284-293)는 **변경하지 않음**.
> 검증 명령: `.venv/bin/python -m pytest tests/...` (launchd와 동일 .venv 3.11). 테스트는
> `patch("shared.telegram_notifier.send")` 필수 (실전 발송 금지).

---

## 플랜 스코프 요약

### 목표 (Goal, 1문장)

24개 발행 문제를 `PROBLEM_REGISTRY`에 전부 등록하고, 발행 시 문제 발생 시 **어떤 문제인지 정확히
알 수 있는 문제별 한국어 Telegram 알림**(problem_id, 한국어 문제명, 감지 단계, 패턴, 연속 횟수, 조치)을
신규 `PublishMonitor` 단일 진입점으로 보내는 시스템을 **additive**로 구축한다.

### 스코프 (이 Phase가 하는 것)

1. 신규 모듈 3종: `shared/problem_registry.py`(ProblemSpec + PROBLEM_REGISTRY + Detection),
   `shared/problem_detectors.py`(순수 탐지 함수), `shared/problem_monitor.py`(PublishMonitor + get_monitor 싱글턴).
2. 통합 지점 6곳 코드 추가 (dispatcher 결과 파싱, dispatcher 배포 반환 캡처, curation run(),
   post-generate raw 훅, post-publish 검증, **P22 ai_generate RuntimeError 캐치**) + scheduler 지점은 "유지 확인"만.
3. 연속 카운터 `data/failure_count.json`을 전 reason 공용으로 확장 (P03 similar_title 포함).
4. `PROBLEM_ALERT_DRY_RUN=1` env 기반 안전 롤아웃 + 신규 테스트 4파일 + 기존 스위트 회귀 0건 게이트.

### 비목표 (Non-Goals — 전부 Phase 59 또는 스코프 밖)

- `shared/notify.py` 교체, `send_validation()`/`send_no_result_alert()` 죽은 코드 삭제 → **이연**.
- 기존 `_tg_error` 호출 경로 제거·단일화 → **이연** (본 phase는 병렬 추가, 중복은 monitor 쿨다운이 흡수).
- STAP/TAP/ETAP repo 내부 알림 수정 → 스코프 밖 (5000 repo만, 보고만).
- `_has_repeated_pattern` 3중 복제(hugo_writer/curation_writer/fix_repeated_image_urls) 통폐합 →
  **이연** (본 phase는 `shared/problem_detectors.py`에 단일 소스로 신규 생성 + 신규 호출만, 기존 3곳 수정 없음).
- `daily_failure_rate` 실강제, 일별 분해 카운터 → **이연** (기존 `DEFAULT_ALERT_CONFIG.daily_failure_rate`도
  미강제 선례 — spec 메타데이터로만 등록).
- P06 featureimage 사이트 전체 스캔 → 금지 (발행 직후 1회 HTTP 확인만).
- `validators.py:744-758` `body_md` NameError 수정 → 범위 밖 (잔존 위험으로 기록).
- ai_writer 기반 **타 파이프라인**(car/senior/gap/rap/travel/etap)의 콘텐츠 누수 raw 감지·P22 배선 →
  **이번 phase 스코프 밖** (curation 경로만 배선, W-2 문서화). 후속 phase에서 공용 확장 검토.

---

## 개요 (Wave / Task 분해)

### Dependency Graph

```
Wave 1: Task 1 [조사] deploy_error 전수 grep (Open Q1)  ──┐  (P04/P05 reason_keys 확정용)
                                                          ▼
Wave 2: Task 2 (problem_registry.py)  ◀── Task 1 이유 인벤토리 소비
        Task 3 (problem_detectors.py)     [Task 2와 병렬 가능 — 독립 모듈]
                                                          ▼
Wave 3: Task 4 (problem_monitor.py — registry + detectors 소비)
                                                          ▼
Wave 4: Task 5 (dispatcher.py 통합)  ──┐
        Task 6 (curation+publisher 통합) ──┴─  (둘 다 monitor 소비, 파일 무충돌 → 병렬 가능)
                                                          ▼
Wave 5: Task 7 (tests/shared 3파일)  ──┐
        Task 8 (integration 테스트 + 회귀 게이트 + dry-run 실발송 0건) ──┘
```

- **블로킹 관계**: T1 → T2 (P04/P05 reason_keys), T2+T3 → T4, T4 → T5/T6, T2~T6 → T7, T7+T5+T6 → T8.
- **병렬 가능**: T2∥T3 (신규 파일, 무충돌), T5∥T6 (dispatcher.py vs curation/publisher 파일군 분리).
- **파일 소유권** (파동 간 충돌 없음):
  - Wave 2: `shared/problem_registry.py`(T2), `shared/problem_detectors.py`(T3)
  - Wave 3: `shared/problem_monitor.py`(T4)
  - Wave 4: `dispatcher.py`(T5) / `pipelines/curation/pipeline.py`+`writer.py`+`shared/publisher.py`(T6)
  - Wave 5: `tests/shared/*`(T7) / `tests/curation/test_problem_monitor_integration.py`(T8)

### Task 요약표

| Wave | Task | 유형 | 파일 | 산출 |
|------|------|------|------|------|
| 1 | T1 | [검증/조사] | read-only | `DEPLOY-PATHS.md` (이유 인벤토리) |
| 2 | T2 | [PRODUCTION] | `shared/problem_registry.py` | ProblemSpec + PROBLEM_REGISTRY 24건 |
| 2 | T3 | [PRODUCTION] | `shared/problem_detectors.py` | 순수 탐지 5함수 + post_generate 디스패처 |
| 3 | T4 | [PRODUCTION] | `shared/problem_monitor.py` | PublishMonitor + 싱글턴 |
| 4 | T5 | [PRODUCTION] | `dispatcher.py` | 결과 파싱 + 배포 캡처 + 카운터 확장 |
| 4 | T6 | [PRODUCTION] | curation pipeline.py, writer.py, shared/publisher.py | run() + raw 훅 + post-validate |
| 5 | T7 | [TEST CODE] | tests/shared 3파일 | registry/detectors/monitor 단위 테스트 |
| 5 | T8 | [TEST CODE] | tests/curation/test_problem_monitor_integration.py | 통합 테스트 + 회귀 게이트 + dry-run 실발송 0건 |

---

## 실행 태스크

> 구분 표기: **[PRODUCTION CODE]** = 검증 대상 코드 수정, **[TEST CODE]** = 검증 수단 추가.

### Task 1 [검증/조사] — deploy_error 전수 grep (RESEARCH Open Q1 해소) — read-only

- **파일**: 변경 없음. 산출물 `.planning/phase-58-publish-problem-telegram-alerting/DEPLOY-PATHS.md` 신규.
- **동작** (추측 금지, 전부 grep/코드 인용으로 확정):
  1. `deploy_error` 발생·소비 지점 전수:
     ```bash
     grep -rn "deploy_error" --include="*.py" dispatcher.py shared/ pipelines/ scripts/ 2>/dev/null
     grep -rn "deploy" --include="*.py" shared/publisher.py shared/publishers/deploy.py | grep -i "return\|raise\|except\|error" | head -30
     ```
  2. **Pages 블로그(CAP/TAP) 경로 확정**: `shared/publisher.py` `publish()` 내부에서 `deploy_site()` 호출
     부근(read) — 예외가 (a) 상위로 전파되는지 (b) try/except로 삼켜지는지 (c) 결과 dict에 `deploy_error`
     키로 병합되는지. `grep -n "deploy_site\|except\|deploy_error" shared/publisher.py` 후 해당 구간 read.
  3. **ETAP/Workers 경로 확정**: `dispatcher.py:691-692`가 `_build_and_deploy_central()` 반환값을 무시하는지
     read 확인 (RESEARCH 확정 사항 재확인), `_build_and_deploy_central` 내부 실패 원인 구분 가능성
     (Hugo 빌드 실패 vs wrangler 실패) — 각 `return False` 지점과 로그 문구를 표로 정리.
  4. **STAP 경로**: `pipelines/stock/pipeline.py:427-428` `tg_error("deploy")` 확인.
  5. **dispatcher가 내보낼 수 있는 모든 reason 문자열 전수 인벤토리**: `dispatcher.py` 전체에서
     `reason: "..."` 리터럴 + 문자열-정규화 목록(:678) + curation `_record_failure` stage + STAP reason
     을 한 표로 수집 → Task 2의 reason→problem_id 완전성 테스트 입력값으로 사용.
  6. `DEPLOY-PATHS.md`에 (1) deploy_error 전파 경로 4종 표 (경로 | 결과 반영 키 | 침묵 여부),
     (2) dispatcher-exportable reason 전수 목록을 기록.
- **검증**:
  - `grep -rn "deploy_error" --include="*.py" dispatcher.py shared/ pipelines/ scripts/ | wc -l` → 수치를
    DEPLOY-PATHS.md의 표와 대조 (파일 수와 줄 수 일치)
  - `grep -rn 'reason: "' dispatcher.py pipelines/curation/pipeline.py | wc -l` → 인벤토리 항목 수와 대조
  - `test -s .planning/phase-58-publish-problem-telegram-alerting/DEPLOY-PATHS.md` → 산출물 존재
- **완료 기준**: DEPLOY-PATHS.md에 deploy_error 전파 경로 표 + reason 전수 목록이 채워지고, 명령이
  수치를 재현함. Pages 경로가 미확정이면 "미확정 — 잔존 위험 1"로 명시 (추측 금지).
- **예상 소요**: 약 0.5h

---

### Task 2 [PRODUCTION CODE] — `shared/problem_registry.py`: ProblemSpec + Detection + PROBLEM_REGISTRY 24건

- **파일**: `shared/problem_registry.py` (신규)
- **동작** (CONTEXT 확정 설계 결정 — ProblemSpec 필드 전부 구현):
  1. **ProblemSpec (frozen dataclass)**:
     `problem_id`, `name_ko`, `severity`("CRITICAL"|"MAJOR"|"MINOR"), `reason_keys: tuple`,
     `hook`("result_parse"|"post_generate"|"post_validate"|"post_publish"|"post_deploy"),
     `alert_template`(한국어, `str.format`), `threshold`("always"|"consecutive:N"|"quiet"),
     `cooldown_minutes=60`, `action`(한국어 조치 가이드), `detect_fn=""`(problem_detectors 내 함수명, 옵션).
  2. **Detection (frozen dataclass)**: `problem_id`, `pattern`, `matched=""`, `hook=""` — post_generate/
     post_validate 탐지 결과 타입 (detectors/monitor 공용).
  3. **PROBLEM_REGISTRY**: `dict[str, ProblemSpec]` (problem_id 키) — CONTEXT 계약 유지 + 모듈 레벨
     헬퍼 `lookup_reason(reason) -> ProblemSpec | None` (reason_keys 역방향 탐색)와
     `lookup_problem(problem_id) -> ProblemSpec | None` 제공. 미등록 reason용 `unknown_failure`
     (threshold="quiet" — 신규 미지 reason은 로그만) spec 포함.
  4. **24개 문제 전부 등록** (심각도/임계값은 CONTEXT §심각도 정책 기본값 준수,
     reason_keys는 Task 1 인벤토리에서 확정 — 아래는 기본값):

     | ID | name_ko | 심각도 | hook | threshold | reason_keys (기본) |
     |----|---------|--------|------|-----------|--------------------|
     | P01 | 발행 데이터 없음 (no_result) | MAJOR | result_parse | consecutive:3 | no_result, no_data, fetch_error |
     | P02 | 콘텐츠 생성 실패 (no_content) | MAJOR | result_parse | consecutive:3 | no_content, write_error, publish_error |
     | P03 | 유사 제목 중복 (similar_title) | MAJOR | result_parse | consecutive:3 | similar_title |
     | P04 | 배포 실패 (deploy_error) | CRITICAL | post_deploy | always | deploy_error, deploy (Task 1 확정분 병합) |
     | P05 | Hugo 빌드 실패 | CRITICAL | post_deploy | always | hugo_build_failed, build_failed (Task 1 확정분 병합) |
     | P06 | 썸네일 404 (broken_featureimage) | CRITICAL | post_publish | always | broken_featureimage |
     | P07 | CJK 누수 | CRITICAL | post_generate | always | cjk_leak |
     | P08 | LLM/CoT 누수 | CRITICAL | post_generate | always | llm_cot_leak, cot_leak |
     | P09 | 이미지 URL 토큰 반복 | CRITICAL | post_generate | always | image_url_repeat |
     | P10 | 제목 템플릿 패턴 (title_blocked) | MAJOR | result_parse | consecutive:3 | title_blocked |
     | P11 | 제목 재생성 실패 | MAJOR | result_parse | consecutive:3 | title_regenerate_failed |
     | P12 | 콘텐츠 품질 게이트 차단 | MAJOR | result_parse | consecutive:3 | content_quality_gate |
     | P13 | API 차단 (rate_limited) | MAJOR | result_parse | consecutive:3 | rate_limited |
     | P14 | 수집/품질 게이트 실패 | MAJOR | result_parse | consecutive:3 | no_keyword, collect_error, insufficient_products, irrelevant_products, low_relevance |
     | P15 | 발행 후 검증 실패 | MAJOR | post_validate | consecutive:3 | validation, validation_failed |
     | P16 | 중복 slug/source_id | MINOR | result_parse | quiet | duplicate_slug, duplicate_source_id |
     | P17 | 일일 할당량 도달 | MINOR | result_parse | quiet | quota_met, quota_exceeded, daily_quota_exceeded, daily_quota, duplicate_title |
     | P18 | 동시 실행 방지 | MINOR | result_parse | quiet | already_running |
     | P19 | 오래된/만료 데이터 | MINOR | post_validate | quiet | stale, stale_data, event_expired |
     | P20 | subprocess 에러 | MAJOR | result_parse | consecutive:3 | stap_timeout, tap_timeout, stap_subprocess_error, stap_no_output |
     | P21 | 설정 오류 (config_error) | MAJOR | result_parse | consecutive:3 | config_error, unknown_pipeline, unknown_blog_id, inactive |
     | P22 | LLM 폴백 체인 전체 실패 | MAJOR | result_parse | consecutive:3 | llm_fallback_exhausted |
     | P23 | 이미지 URL 길이 초과 | MINOR | post_generate | quiet | image_url_length |
     | P24 | 검증 함수 자체 결함 | MINOR | post_validate | quiet | validation_defect |

     - **주의 (수치 불일치 명시)**: CONTEXT/RESEARCH 헤더는 "MAJOR 13 / MINOR 5"이나 목록 자체는
       MAJOR 12 / MINOR 6 — **목록 기준으로 등록** (총 24 유지). Task 7 테스트에서 총 24개 +
       CRITICAL 6 / MAJOR 12 / MINOR 6을 목록 기준으로 고정 assert.
  5. **alert_template 한국어 템플릿** (문제별 — `str.format` 변수: `{blog_id}`, `{problem_id}`,
     `{name_ko}`, `{severity}`, `{phase}`, `{pattern}`, `{matched}`, `{consecutive}`, `{action}`):
     - CRITICAL 예 (P08): `"🚨 [CRITICAL] 콘텐츠 오염 — LLM/CoT 누수 감지\n블로그: {blog_id}\n문제: {problem_id} — {name_ko}\n감지 단계: {phase}\n감지 패턴: {pattern}\n연속 실패: {consecutive}회\n조치: {action}"`
     - MAJOR 예 (P03): `"⚠️ [MAJOR] 발행 불가 — 유사 제목 중복\n블로그: {blog_id}\n문제: {problem_id} — {name_ko}\n감지 단계: {phase}\n연속 실패: {consecutive}회\n조치: {action}"`
     - **금지**: 템플릿에 토큰(full URL, API 키) 미포함. `action`에는 URL 없이 행동 지시만
       (예: "scan_multilingual_leak.py로 확인 후 재생성", "Hugo 테마/themesDir 점검",
       "키워드별 제목 변형 다양화 검토"). 렌더 결과 500자 트렁케이션은 monitor(Task 4)가 수행.
  6. **기존 모듈 수정 금지**: `shared/` 내 다른 파일은 건드리지 않음.
- **검증**:
  ```bash
  cd /Users/twinssn/Projects/5000
  .venv/bin/python -c "
  from shared.problem_registry import PROBLEM_REGISTRY, lookup_reason, lookup_problem
  assert len(PROBLEM_REGISTRY) == 25, len(PROBLEM_REGISTRY)  # 24 + unknown_failure
  sev = {}
  for s in PROBLEM_REGISTRY.values():
      sev[s.severity] = sev.get(s.severity, 0) + 1
  assert sev['CRITICAL'] == 6, sev
  # Task 1 인벤토리 reason 전수 커버 확인 (인벤토리 확정 후 갱신)
  for r in ['no_result','no_content','similar_title','deploy_error','deploy','validation',
            'title_blocked','rate_limited','stap_timeout','config_error','quota_met','already_running']:
      assert lookup_reason(r) is not None, r
  assert lookup_reason('no_such_reason') is None
  print('registry OK:', sev)
  "
  ```
  `.venv/bin/python -m py_compile shared/problem_registry.py`
- **완료 기준**: 24개 문제 + unknown_failure 등록, reason 역방향 탐색 동작, 심각도 수치 목록 기준
  (6/12/6), Task 1 인벤토리의 reason 전수가 lookup_reason으로 해석됨.
- **예상 소요**: 약 1.5h

### Task 3 [PRODUCTION CODE] — `shared/problem_detectors.py`: 순수 탐지 함수 5종 + post_generate 디스패처

- **파일**: `shared/problem_detectors.py` (신규)
- **동작** (CONTEXT 확정 — 기존 시그니처 재사용, 신규 regex/HTTP/쿨다운 금지):
  1. **`detect_cjk_leak(text) -> Detection | None`** — P07 (2단 분기 — CONTEXT 계약 4 "한글 비율 0.5 + 지시문성 중국어 키워드"):
     - (a) `shared.validators.has_cjk(text)`(기존 regex) True **AND** `is_korean_content(text, min_hangul_ratio=0.5)` False → P07 **검출** (일본어/중국어 문장 = 실제 누수. PLAN-CHECK MAJOR-2: ratio < 0.5이면 검출이 맞음).
     - (b) `_check_multilingual_leak(text)` 반환 `(has_leak, pattern_name, matched)`의 `pattern_name == "cjk_instruction_leak"` (ai_response_parser.py:76-80, CJK_INSTRUCTION_LEAK) → P07 **검출** (지시문성 중국어 키워드 — W-6, P08로 오분류 금지).
     - (c) 그 외 — 한자 병기 한국어 등 ratio ≥ 0.5 → **None** (오탐 방지, travel2 heritage 86건 교훈).
     - `Detection(problem_id="P07", pattern=<트리거 근거: "ratio<0.5"|"cjk_instruction_leak">, matched=<매칭 문자열 1개>, hook="post_generate")`
  2. **`detect_cot_leak(text) -> Detection | None`** — P08:
     - `_check_multilingual_leak(text)` 반환 `pattern_name == "thinking_leak"` (THINKING_PATTERNS 매치, ai_response_parser.py:71-74) → P08. has_leak=False면 None.
     - **주의**: `cjk_instruction_leak`은 여기서 P07로 분기(위 detect_cjk_leak (b)) — P08로 보고 금지.
     - `Detection(problem_id="P08", pattern="thinking_leak", matched=<매칭 문자열 1개>, hook="post_generate")`
  3. **`detect_repeated_image_url(url) -> Detection | None`** — P09.
     - `url.count("/")`, `url.count(".")`, 세그먼트 수, 전체 길이를 수집 후 `len(set(url.split("/")))`가 전체 세그먼트 수의 절반 미만이면 반복 의심 + 전체 길이 > 400자면 확정.
     - `Detection(problem_id="P09", pattern=f"repeated segments ({dup} of {total})", matched=url, hook="post_generate")`
     - False면 None.
  4. **`detect_image_url_length(url) -> Detection | None`** — P23.
     - `len(url) > 500` (hugo_writer `sanitize_featureimage_url` 500자 제한과 동일 기준) → `Detection(problem_id="P23", pattern="url length", matched=str(len(url)), hook="post_generate")`
  5. **`detect_validation_issue(check_result, blog_id) -> Detection | None`** — P15 (+P19 로그 지원):
     - `shared.post_validator.validate_post_html` 반환 dict(keys: issues, warnings, ...)를 받아 `issues`에 P15 관련 항목(cta_html:105, curation_cta:116, empty_template:125, thumbnail:130, map_text:135, min_length:142, readability:148, keyword_coverage:173) 존재 시 P15 Detection 반환.
     - `stale`/`event_expired`류 키가 `issues`에 있으면 **P19(quiet)** Detection 반환 — 발송은 안 되고 로그만 (M-8 보강).
     - False면 None.
  6. **`detect_post_generate(content, blog_id) -> list[Detection]`** — post_generate raw 디스패처 (`monitor.detect("post_generate", ...)`가 호출):
     - P07 → P08 → P09 → P23 순으로 각 detector 실행, **감지된 전건 리스트 반환** (첫 감지만 반환하지 않음 — monitor가 발송 정책 결정).
     - 감지 0건이면 `[]`.
     - `blog_id` 인자는 블로그 컨텍스트(레지스트리 참조 등) — 순수 함수 유지 (state 없음).
  7. **주의사항**:
     - 함수는 **순수**해야 함 — state 없음, 외부 I/O 없음 (HTTP 금지, 파일 금지). 전부 동기 단일 스레드에서 deterministic.
     - `import shared.validators`, `from shared.ai_response_parser import THINKING_PATTERNS, _check_multilingual_leak`, `from shared.post_validator import validate_post_html`(lazy import — post_validator는 Pillow 등 무거운 import가 있어 모듈 로드 시점이 아닌 함수 내부에서 import).
     - 기존 모듈 수정 금지: `validators.py`, `ai_response_parser.py`, `post_validator.py`, `hugo_writer.py` 건드리지 않음.
- **검증**:
  ```bash
  cd /Users/twinssn/Projects/5000
  .venv/bin/python -c "
  from shared.problem_detectors import detect_cot_leak, detect_cjk_leak, detect_repeated_image_url, detect_image_url_length, detect_post_generate
  # P08: THINKING_PATTERNS 실매치 텍스트 (ai_response_parser.py:15-37 — 실측 확인됨)
  leak = detect_cot_leak('이제 글을 작성하겠습니다.\n본문 시작')
  assert leak is not None and leak.problem_id == 'P08', leak
  leak2 = detect_cot_leak('<thinking>\n1. 계획\n2. 실행\n</thinking>\n본문')
  assert leak2 is not None and leak2.problem_id == 'P08', leak2
  # P07 (a): 비한글 CJK (일본어 문장) → 검출 (기대치 정정 — PLAN-CHECK MAJOR-2)
  cjk = detect_cjk_leak('この記事は日本語で書かれています。今日は良い天気です。' * 3)
  assert cjk is not None and cjk.problem_id == 'P07', cjk
  # P07 오탐 방지: 한자 병기 한국어 (ratio >= 0.5) → None
  hanja = detect_cjk_leak('갑사(甲寺)는 충청남도 공주시에 위치한 유서 깊은 사찰입니다. 사찰 내부에는 보물로 지정된 불상이 있습니다.')
  assert hanja is None, hanja
  # P07 (b): 지시문성 중국어 키워드 → 검출 (W-6, 실측: _check_multilingual_leak = (True, 'cjk_instruction_leak', ...))
  cn = detect_cjk_leak('根据要求，请按照规则如下格式输出内容。正文입니다.')
  assert cn is not None and cn.problem_id == 'P07', cn
  # P09: 반복 세그먼트 URL
  img = detect_repeated_image_url('https://img.example.com/a/a/a/a/a/a/a/a/thumb.jpg')
  assert img is not None and img.problem_id == 'P09', img
  # P23: 500자 초과
  long_url = detect_image_url_length('https://example.com/' + 'x' * 520)
  assert long_url is not None and long_url.problem_id == 'P23', long_url
  # post_generate 디스패처 — 리스트 반환 (정상 본문 → [])
  dets = detect_post_generate('정상적인 한국어 본문입니다.', 'any-blog')
  assert isinstance(dets, list) and dets == [], dets
  print('detectors OK')
  "
  ```
  `.venv/bin/python -m py_compile shared/problem_detectors.py`
- **완료 기준**: 5개 순수 함수 + post_generate 디스패처 동작, P08(P08 실패턴) / P09 / P23 감지,
  P07이 ratio<0.5와 cjk_instruction_leak에서 **검출**되고 한자 병기 한국어에서 **None**(오탐 방지),
  기존 모듈 수정 0건 (`git diff --stat shared/`에 problem_detectors.py만 추가).
- **예상 소요**: 약 1.5h

---

### Task 4 [PRODUCTION CODE] — `shared/problem_monitor.py`: PublishMonitor + get_monitor 싱글턴

- **파일**: `shared/problem_monitor.py` (신규)
- **동작** (CONTEXT 확정 설계 API 복귀 — W-3, **실 ThresholdChecker API 준수** — MAJOR-1):
  1. **`PublishMonitor.__init__(self, checker=None, dry_run=None)`**:
     - `checker` 기본값 = **`ThresholdChecker()` 실인스턴스** — 테스트도 실인스턴스 사용, fake 주입 금지 (MAJOR-1).
     - `dry_run` 기본값 = `int(os.environ.get("PROBLEM_ALERT_DRY_RUN", "0")) == 1` (env 우선, 명시 인자가 최우선).
  2. **`report(blog_id, result: dict, phase, extra: dict) -> list[str]`** — 단일 진입점 (CONTEXT API):
     - `result` dict 규약: `{"detection": Detection}` 우선 (post_generate/post_validate/post_publish/post_deploy),
       없으면 `{"reason": str}` (result_parse) → `lookup_reason(reason)`. 둘 다 없으면 None → `logger.warning`(unknown).
     - **phase 전달 규칙 (강제 — MAJOR-1 #5)**: phase 인자는 **매핑된 spec.hook과 반드시 일치**해야 한다.
       불일치 시 `logger.error`(blog_id + problem_id + 기대 phase 명시) 후 **발송 차단**. 각 호출부는
        `spec.hook` 값을 그대로 phase로 전달한다 — 예: curation run()의 `deploy_error`는 P04
        (hook="post_deploy")이므로 **phase="post_deploy"** 로 보고 (Task 6 step 1 — phase="result_parse"
        하드코딩 금지).
     - **threshold 분기 (실 API 기반, maybe_alert 미사용 — MAJOR-1)**:
       - `"always"` (CRITICAL): 연속 임계값 **우회** — `checker._in_cooldown(blog_id)`이면 쿨다운 스킵(로그),
         아니면 `send_problem_alert(...)` 호출 → `checker._mark_alerted(blog_id)`. **`check_consecutive_failures`
         사용 금지** — 실 API는 2인자 `(blog_id, consecutive_count)`로 `count >= 3`을 검사(alert_thresholds.py:68-72)라
         1회차 CRITICAL을 막음.
       - `"consecutive:N"` (MAJOR): `consecutive = extra.get("consecutive_failures", 1)` →
         `checker.check_consecutive_failures(blog_id, consecutive)` True면 쿨다운 체크 후
         `send_problem_alert(...)` + `_mark_alerted(blog_id)`. **`maybe_alert` 사용 금지** — 자체적으로
         `send_error`(구형 단일 템플릿)로 발송(alert_thresholds.py:150-153)해 문제별 템플릿이 무시·중복됨.
       - `"quiet"` (MINOR): `logger.info`만, 발송 안 함.
     - 반환: 발송된(또는 dry-run 발송 예정) problem_id 목록 `list[str]`.
  3. **`detect(hook, content, blog_id) -> list[Detection]`** (CONTEXT API):
     - `hook == "post_generate"` → `detect_post_generate(content, blog_id)` (P07/P08/P09/P23 전건).
     - `hook == "post_validate"` → `detect_validation_issue(content, blog_id)` 결과를 리스트로 래핑 (없으면 `[]`).
     - 미지원 hook → `logger.warning` + `[]`.
  4. **`send_problem_alert(problem_id, blog_id, context: dict) -> str | None`** (CONTEXT API):
     - `spec.alert_template.format(...)` 렌더 (context: pattern/matched/consecutive/phase/action 등) →
       500자 트렁케이션 → dry_run이면 로그만, 아니면 `telegram_notifier.send(message)` → 렌더된 문자열 반환
       (억제/실패 시 None, 예외는 catch → `logger.error` — 파이프라인 중단 금지).
  5. **`get_monitor() -> PublishMonitor`** 모듈 싱글턴 (lazy init).
  6. **연속 카운터 규칙 (단일화 — W-1, CONTEXT A1 "dispatcher 카운터 우선")**:
     - **result_parse 카운터 소유자 = dispatcher** (`data/failure_count.json`, Task 5에서 확장):
       monitor는 **카운트하지 않고** `extra["consecutive_failures"]` 값만 소비. 성공 리셋도 dispatcher가 수행
       (`{blog_id}:{problem_id}` 키 삭제 + 기존 `_reset_failure_count` 불변).
     - **비-dispatcher 훅(post_generate/post_validate/post_publish/post_deploy)**: monitor 인메모리
       `self._consecutive: dict[(blog_id, problem_id), int]` — report() 시 1 증분. CRITICAL(always)은
       카운트 불필요(우회). **리셋 규칙**: 발행 성공 경로(Task 6)에서 `reset(blog_id, problem_id=None)` 호출 시
       해당 키 삭제 (problem_id=None이면 해당 blog 전체 삭제). 인메모리 특성(프로세스 재시작 시 초기화)은
       문서화 — MAJOR post_validate 연속 3회는 단일 실행 내 연속 실패 의미.
     - 쿨다운은 `checker._in_cooldown(blog_id)` / `checker._mark_alerted(blog_id)`(alert_thresholds.py:80-91)
       **기존 메서드만 재사용** — **신규 cooldown 구현 금지**. `ThresholdChecker`에는 reset 메서드가 없음
       (PLAN-CHECK W-1) — 모니터 자체 리셋은 위 규칙으로 처리, checker에 reset 추가 금지.
  7. **주의사항**:
     - `shared.telegram_notifier.send` import + 테스트는 `patch("shared.problem_monitor.telegram_notifier.send")`로 가로채기.
     - 조용한 실패 금지 — 모든 예외 경로에 `logger.error` (재시도 없음, 파이프라인 중단 금지 — 기존 graceful degradation 원칙).
- **검증**:
  ```bash
  cd /Users/twinssn/Projects/5000
  .venv/bin/python -c "
  import os
  from unittest.mock import patch
  from shared.problem_monitor import get_monitor
  from shared.problem_registry import lookup_reason
  os.environ['PROBLEM_ALERT_DRY_RUN'] = '1'
  m = get_monitor()
  assert m.dry_run is True
  # dry_run: 발송 0건 + 발송 예정 목록 반환
  with patch('shared.problem_monitor.telegram_notifier.send') as fake:
      sent = m.report('test-hugo', {'reason': 'llm_cot_leak'}, 'post_generate', {})
      assert fake.call_count == 0 and sent == ['P08'], (fake.call_count, sent)
  # quiet(MINOR) / hook 불일치 / unknown → 발송 0건
  with patch('shared.problem_monitor.telegram_notifier.send') as fake:
      m.report('test-hugo', {'reason': 'quota_met'}, 'result_parse', {'consecutive_failures': 1})
      assert fake.call_count == 0
  with patch('shared.problem_monitor.telegram_notifier.send') as fake:
      m.report('test-hugo', {'reason': 'llm_cot_leak'}, 'result_parse', {})  # P08 hook=post_generate 불일치
      assert fake.call_count == 0
  with patch('shared.problem_monitor.telegram_notifier.send') as fake:
      m.report('test-hugo', {'reason': 'no_such_reason'}, 'result_parse', {})
      assert fake.call_count == 0
  print('monitor dry-run OK')
  "
  ```
  ```bash
  # MAJOR-1: 실 ThresholdChecker 동작 검증 (dry_run 해제, send는 patch — 실전 발송 없음)
  cd /Users/twinssn/Projects/5000
  PROBLEM_ALERT_DRY_RUN=0 .venv/bin/python -c "
  from unittest.mock import patch
  from shared.problem_monitor import get_monitor
  m = get_monitor()
  # CRITICAL 1회차 즉시 발송 → 연속 재호출은 60분 쿨다운 스킵 (별도 blog_id 사용)
  with patch('shared.problem_monitor.telegram_notifier.send') as fake:
      m.report('crit-hugo', {'reason': 'llm_cot_leak'}, 'post_generate', {})
      assert fake.call_count == 1, fake.call_count
  with patch('shared.problem_monitor.telegram_notifier.send') as fake:
      m.report('crit-hugo', {'reason': 'llm_cot_leak'}, 'post_generate', {})
      assert fake.call_count == 0, fake.call_count  # _in_cooldown 스킵
  # MAJOR: 연속 2회 미만 발송 없음 / 3회째 발송 (check_consecutive_failures 실 API)
  with patch('shared.problem_monitor.telegram_notifier.send') as fake:
      m.report('maj-hugo', {'reason': 'no_result'}, 'result_parse', {'consecutive_failures': 2})
      assert fake.call_count == 0, fake.call_count
  with patch('shared.problem_monitor.telegram_notifier.send') as fake:
      m.report('maj-hugo', {'reason': 'no_result'}, 'result_parse', {'consecutive_failures': 3})
      assert fake.call_count == 1, fake.call_count
  print('monitor real-checker OK')
  "
  ```
  `.venv/bin/python -m py_compile shared/problem_monitor.py`
- **완료 기준**: `report()/detect()/send_problem_alert()/get_monitor()` 동작, dry-run 발송 0건,
  CRITICAL 1회차 즉시 발송 + 쿨다운 스킵 (실 ThresholdChecker), MAJOR 3회째 발송, quiet/unknown/hook 불일치
  모두 발송 안 함, 신규 cooldown 코드 없음 (`grep -n "time.time\|cooldown_seconds" shared/problem_monitor.py`
  결과 0건 — `_in_cooldown`/`_mark_alerted` 호출만).
- **예상 소요**: 약 1.5h

### Task 5 [PRODUCTION CODE] — `dispatcher.py` 통합: 결과 파싱 + 배포 캡처 + 카운터 확장

- **파일**: `dispatcher.py` (기존 — **additive만**, 기존 `_tg_error` 호출은 건드리지 않음)
- **동작** (RESEARCH file:line 기준, 추측 금지 — 각 위치는 읽고 확정):
  1. **사전 읽기 (필수)**: `dispatcher.py`의 (a) dispatch 결과 정규화 구간 (:672-740), (b) `_build_and_deploy_central()` 호출부 (:691-692), (c) `_increment_failure_count`/`_reset_failure_count` 정의(:91 근방), (d) `data/failure_count.json` 로드/저장 경로. 읽기 전에 변경 금지.
  2. **baseline 기록 (W-4 — AGENTS.md 수정 전 기준선 필수)**: 어떤 수정도 하기 전에
     `.venv/bin/python -m pytest tests/ -q` 실행 → pass/fail 수치를 실행 리포트(SUMMARY.md)에 기록
     (예: "baseline: X passed, Y failed"). Task 8 회귀 게이트의 대조 기준으로 사용.
  3. **결과 파싱 훅 추가 (실패 분기 내부 — M-11)**: dispatcher.py:701 이하의 **실패 분기**
     (`result.get("success")`가 False일 때) 내부에 배치 — 성공 결과에는 `reason` 키가 없어
     "unknown failure reason" 노이즈가 발생하므로 normalize 직후(:674-686)에는 **배치하지 않음**.
     - `result.get("reason")` 문자열을 `lookup_reason(reason)`으로 매핑.
     - 매핑 결과 None이면 `logger.warning("unknown failure reason: %s", reason)`만 기록(발송 안 함).
     - 매핑 성공 시 `get_monitor().report(blog_id, {"reason": reason}, phase=spec.hook, extra={"consecutive_failures": <현재 카운트>})` 호출 — **phase는 spec.hook 값을 그대로 사용** (Task 4 phase 전달 규칙).
     - `consecutive` 값: 기존 `_increment_failure_count`가 반환하는 카운터 값 재사용.
  4. **배포 반환 캡처** (:691-692): `_build_and_deploy_central()` 반환값을 받아 False일 때:
     - 반환값이 False이고 별도 reason 문구가 없으면 `P04 deploy_error`(또는 Task 1에서 확정한 구분 로직)로 `report(blog_id, {"reason": "deploy_error"}, phase="post_deploy", extra={})` — **P04 hook=post_deploy라 phase="post_deploy"** (result_parse 아님).
     - **기존 `_tg_error(blog_id, "deploy", ...)` 호출은 유지** (이연 — 병렬 발송, 중복은 쿨다운 흡수).
     - dispatcher 내부에서 성공 시 `_reset_failure_count`가 이미 호출되면 그대로 두고, **`{blog_id}:{problem_id}` 확장 키 삭제 경로(W-1)를 성공 분기(:688-690)에 추가** — 성공 시 `data/failure_count.json`에서 해당 blog_id의 모든 확장 키를 삭제 (연속 카운터가 성공 후 누적되지 않도록).
  5. **카운터 공용화** (P03 similar_title 포함, 증분 주체 단일화 — W-1):
     - `data/failure_count.json` 구조: 기존 `{blog_id: int}`를 **호환 유지**(읽기 시 int면 그대로 사용)하면서 reason별 분리 키 `{blog_id}:{problem_id}` 지원 — **기존 키를 삭제하지 않음** (기존 `_increment_failure_count`/`_reset_failure_count`가 쓰는 키 보존).
     - `_increment_failure_count(blog_id)` 기존 함수는 유지 + `problem_id` 인자를 받는 새 경로는 기존 체이닝에 추가(기존 시그니처 변경 금지 — 새 인자는 기본값). 증분: 실패 시 `{blog_id}`(기존)와 `{blog_id}:{problem_id}`(신규) **둘 다 1씩 증분**.
     - 성공 리셋: `_reset_failure_count(blog_id)`(기존, `{blog_id}` 키) 불변 + 위 4번의 확장 키 삭제 경로.
     - P03: curation run()에서 `similar_title`을 reason으로 돌려주는 경로는 이미 존재(:1104-1128) → dispatcher 정규화가 reason을 보존하는지 확인하고 보존되면 그대로. 만약 curation이 `reason: "no_result"`로 일반화하면 Task 6에서 수정(reason 보존은 Task 6 책임, dispatcher는 받은 reason 그대로 사용).
  6. **에러 로그 패턴**: 모든 신규 훅은 `logger.warning/error`에 blog_id + reason + problem_id 명시 — 조용한 실패 금지.
  7. **주의사항**:
     - `import`는 모듈 최상단에 추가 (`from shared.problem_registry import lookup_reason`, `from shared.problem_monitor import get_monitor`).
     - 기존 `_tg_error` 호출, `_increment_failure_count` 호출, `_SILENT_REASONS`/`quota` 분기 로직은 **전부 유지**.
     - dispatcher가 여러 파이프라인(TAP/STAP subprocess)의 결과 dict를 정규화하는 경로(:672-740)에서 reason이 이미 표준화된 값인지 read로 확인하고, subprocess 결과의 raw reason도 보존하는지 확인해 보존.
- **검증**:
  ```bash
  cd /Users/twinssn/Projects/5000
  .venv/bin/python -c "
  import json, os, tempfile
  from unittest.mock import patch
  os.environ['PROBLEM_ALERT_DRY_RUN'] = '1'
  # (1) import 성공
  import dispatcher
  from shared.problem_monitor import get_monitor
  m = get_monitor()
  # (2) 매핑 유닛: reason → spec (샘플)
  from shared.problem_registry import lookup_reason
  assert lookup_reason('no_result').problem_id == 'P01'
  assert lookup_reason('deploy_error').problem_id == 'P04'
  assert lookup_reason('llm_fallback_exhausted').problem_id == 'P22'  # P22 배선 (MAJOR-3)
  print('dispatcher import + mapping OK')
  "
  ```
  ```bash
  # (3) 기존 호출 보존 확인 (additive 게이트)
  cd /Users/twinssn/Projects/5000
  grep -c "_tg_error(blog_id, \"deploy\"" dispatcher.py 2>/dev/null || true
  grep -c "_tg_error(blog_id, \"quota\"" dispatcher.py 2>/dev/null || true
  grep -n "_build_and_deploy_central(" dispatcher.py | head -5
  ```
  ```bash
  # (4) 전체 스위트 회귀 0건 (기존 테스트 유지 확인) — Task 8에서 전량 수행, 여기서는 dispatcher 관련만:
  .venv/bin/python -m pytest tests/test_dispatcher_registry.py -q 2>&1 | tail -3
  ```
- **완료 기준**: baseline 기록(W-4) + reason 매핑(실패 분기 내, M-11) + 배포 실패 캡처(phase="post_deploy") +
  카운터 공용화(증분 주체 단일화 + 성공 시 확장 키 삭제, W-1) 구현, 기존 `_tg_error` 호출 수 불변
  (grep 수치 기록), dispatcher 테스트 통과, dry-run 모드에서 실발송 0건.
- **예상 소요**: 약 2h

---

### Task 6 [PRODUCTION CODE] — curation run() 통합 + post-generate raw 훅 + post-publish 검증

- **파일**: `pipelines/curation/pipeline.py`, `pipelines/curation/writer.py`, `shared/publisher.py` (기존 — **additive만**)
- **동작** (RESEARCH file:line 기준):
  1. **curation run() 실패 블록** (`pipeline.py:850-865`):
     - `_tg_error(blog_id, stage, msg)` 호출 **유지** + 옆에 `get_monitor().report(blog_id, {"reason": stage}, phase=<spec.hook>, extra={"consecutive_failures": _consecutive_failures.get(blog_id,0)+1})` 추가.
     - **phase는 `lookup_reason(stage)`로 매핑된 spec의 hook 값을 그대로 사용** (Task 4 phase 전달 규칙 — MAJOR-1 #3): `stage="deploy_error"` → P04(hook="post_deploy") → **phase="post_deploy"**. phase="result_parse" 하드코딩 금지 (hook 불일치 가드에 차단됨).
     - `stage` 값(`no_result`/`no_content`/`similar_title`/`deploy_error` 등)을 reason으로 매핑. 미등록 stage는 None → 로그만.
     - `_alert_checker.maybe_alert` 기존 호출은 **유지** (병렬 — monitor의 ThresholdChecker 쿨다운이 중복 알림을 흡수).
     - P03 similar_title: reason이 `no_result`로 일반화되지 않도록 **reason 보존 확인** — `run()`이 반환하는 dict의 reason을 `similar_title`로 유지.
  2. **post-generate raw 훅** (`writer.py` — `generate_curation_article` 내부, :681에 `blog_id=None` 파라미터 이미 존재 — PLAN-CHECK 검증):
     - `body = result ...` (또는 `result.get("content","")`) 추출 직후, **`_is_cot_body(body)` 호출 전**(:755 이전)에 raw 상태로 `get_monitor().detect("post_generate", body, blog_id)` 호출:
       - 감지된 각 `Detection`에 대해 `get_monitor().report(blog_id, {"detection": det}, phase=spec.hook, extra={})` — phase는 det.problem_id로 lookup한 spec.hook 값 (전부 "post_generate").
       - **기존 `_sanitize_body`/`_is_cot_body` 흐름은 수정하지 않음** (감지만 추가 — raw 전 검사가 BUG-54-001 교훈).
     - title 템플릿 블록(`_tt_picker` 사용부)에서 title 실패 시 reason `title_blocked`가 run()까지 전달되는 경로 확인 — 보존.
  3. **P22 LLM 폴백 전체 실패 배선 (MAJOR-3 #2)** — `writer.py:745` 본문 `ai_generate(system_prompt, user_prompt, ...)` 호출부:
     - 해당 호출을 `try/except RuntimeError`로 **additive 감싸기**: `except RuntimeError as _re:`에서
       `get_monitor().report(blog_id, {"reason": "llm_fallback_exhausted"}, phase="result_parse", extra={})` 호출
       (P22 hook="result_parse" — enum 내 값 정정, MAJOR-3 #1) 후 **re-raise** (기존 전파/흡수 흐름 불변).
     - 근거: ai_writer.py:315 `raise RuntimeError(msg)`(전 tier 실패)가 기존 흐름에서 no_content로 흡수되어
       P02로 오분류됨 — P22 정확 원인 알림을 추가하고 기존 catch/흡수는 유지.
     - **주의**: writer.py:584의 `except RuntimeError`(title 재생성, 별도 호출부)는 건드리지 않음 — 본문 생성 호출부(:745)만.
  4. **post-publish 검증 훅** (`shared/publisher.py` `_run_validation` :836-855):
     - `_run_validation` 내부에서 `validate_post_html` 결과 dict를 받아 `get_monitor().detect("post_validate", check_result, blog_id)` 호출 → 감지 시 `get_monitor().report(blog_id, {"detection": det}, phase="post_validate", extra={})`.
     - **주의**: P15(MAJOR)와 P24(검증 함수 자체 결함) 분기 — `check_result` 산출 중 예외 발생 시 P24, 정상 issues면 P15. P19(stale/event_expired, quiet)는 로그만 — 발송 없음 (M-8).
     - 기존 `_tg_err(blog_id, "validation", msg)` 호출 유지.
  5. **P06 썸네일 404 확인** (`post_publish` hook — post_validate와 동일 위치 또는 `hugo_writer` frontmatter update 직후):
     - featureimage가 설정된 경우에만 1회 HTTP HEAD/GET(시간 초과 5s, 예외는 None)으로 상태 확인 → 404/500이면 `get_monitor().report(blog_id, {"reason": "broken_featureimage"}, phase="post_publish", extra={})` — P06 hook="post_publish" 일치.
     - **주의**: 이 HTTP 확인은 **발행 직후 1회**만. 배치 스캔 금지. 실패(네트워크 오류)는 문제로 판정하지 않음.
  6. **주의사항**:
     - 파일 3개 수정이지만 공통 패턴(모니터 호출 추가)이라 1 태스크로 유지. 변경은 각 함수 끝에 monitor 호출 추가가 전부 — 기존 로직 수정 없음.
     - `shared/publisher.py`는 다른 파이프라인(car/senior/gap/rap)도 공유 → 수정은 `_run_validation` 내부에만, 훅 실패가 발행 흐름을 막지 않도록 try/except로 감싸기 (조용한 실패 금지 — logger.error 필수).
- **검증**:
  ```bash
  cd /Users/twinssn/Projects/5000
  .venv/bin/python -c "
  import os
  from unittest.mock import patch
  os.environ['PROBLEM_ALERT_DRY_RUN'] = '1'
  from shared.problem_detectors import detect_validation_issue, detect_post_generate
  # P15: validator issues dict 입력
  fake_check = {'issues': ['thumbnail missing'], 'warnings': []}
  det = detect_validation_issue(fake_check, 'test-hugo')
  assert det is not None and det.problem_id == 'P15', det
  # P24: 예외 케이스 — 호출부에서 try/except로 P24 분기되는 구조만 확인
  try:
      detect_validation_issue('not-a-dict', 'test-hugo')
  except Exception:
      pass
  print('pipeline detectors OK')
  "
  ```
  ```bash
  # 파일 3개 수정 여부 + 기존 라인 보존 (git diff 요약)
  git diff --stat pipelines/curation/pipeline.py pipelines/curation/writer.py shared/publisher.py
  # curation 기존 테스트 회귀 (Task 8 전량 게이트 전 선확인)
  .venv/bin/python -m pytest tests/curation/test_alert_thresholds.py -q 2>&1 | tail -3
  ```
- **완료 기준**: run() 실패 블록에 monitor 병렬 호출(phase=spec.hook, deploy_error→post_deploy), raw 훅이
  `_sanitize_body` 이전에 `monitor.detect`로 감지, **P22 ai_generate RuntimeError 캐치 배선(re-raise 유지)**,
  P15/P24 분기 + P19 로그만, P06 1회 확인(phase=post_publish), 기존 `_tg_error`/`_tg_err` 호출 보존,
  curation 테스트 통과.
- **예상 소요**: 약 2h

### Task 7 [TEST CODE] — 단위 테스트: registry / detectors / monitor (3파일)

- **파일**: `tests/shared/test_problem_registry.py`, `tests/shared/test_problem_detectors.py`,
  `tests/shared/test_problem_monitor.py` (신규)
- **동작** (Nyquist 규칙 — `<verify>`의 `<automated>`를 테스트 파일로 대체):
  1. **test_problem_registry.py**:
     - registry 총 25건(24 + unknown_failure), 심각도 수치 목록 기준 **6/12/6** 고정 assert.
     - reason_keys 전수: Task 1 인벤토리 reason 리스트(파일: DEPLOY-PATHS.md)를 fixture로 로드해
       각 reason이 정확히 1개 spec에 매핑됨을 assert (누락/중복 없음).
     - `lookup_reason`/`lookup_problem` None 케이스, 각 spec의 `alert_template.format()` 렌더가
       KeyError 없이 동작하고 500자 이하인지 전수 assert.
     - 미등록 reason `unknown_failure` spec 존재 확인.
  2. **test_problem_detectors.py**:
     - P07: **ratio < 0.5 CJK(일본어/중국어 문장, 예: 'この記事は日本語で書かれています...') → P07 검출**,
       **ratio ≥ 0.5 한자 병기 한국어(예: '갑사(甲寺)는 충청남도...') → None(오탐 방지)**,
       `cjk_instruction_leak` 패턴 텍스트(예: '根据要求，请按照规则如下格式输出内容。') → P07 검출 (W-6).
       — 기대치가 설계(ratio<0.5→검출)와 일치하도록 **역전 방지** (PLAN-CHECK MAJOR-2: 기존 계획의
       "ratio<0.5→None"는 오탐 방지 케이스와 실누수 케이스를 뒤바꾼 것 — travel2 오탐 사고 재현 방향).
     - P08: **THINKING_PATTERNS 실패턴 텍스트**로 감지 (예: '이제 글을 작성하겠습니다.', '<thinking>...',
       '\n주의: ...', 'Let me re-read the request', '문장 수: 3') + `_check_multilingual_leak`의
       thinking_leak 반환 → P08 감지, 정상 본문 → None. 'Sure, let me think step by step' 같은
       비매치 문자열 사용 금지 (실측 매치 0건).
     - P09: 반복 세그먼트 URL 감지 / 정상 URL None / 경계(세그먼트 수 1개) None.
     - P23: 500자 초과 감지 / 500자 이하 None.
     - P15: issues 있는 check_result 감지 / issues 없는 것 None / P19 stale 키는 P19 반환.
     - `detect_post_generate` 디스패처: 후보 4문제 감지 전건 리스트 반환, 전부 없으면 [].
     - 테스트 데이터는 실전 코드와 동일한 패턴 문자열 사용 (연구에서 인용한 실제 감지 사례 재현).
  3. **test_problem_monitor.py**:
     - `patch("shared.problem_monitor.telegram_notifier.send")`로 발송 가로채기 — 실전 발송 금지.
     - **실 `ThresholdChecker()` 인스턴스 사용 — fake checker 주입 금지 (MAJOR-1 #4)**. dry_run 동작
       검증: dry_run=1(env)일 때 전 severity 발송 호출 0건 + `report()` 반환 목록에 발송 예정 problem_id 포함.
     - CRITICAL(always): dry_run=0 + 실 checker → **1회차 즉시 발송 1건**, 곧바로 같은 blog 재호출 시
       **쿨다운 스킵 0건** (60분 — 시간 조작 없이 실 `_in_cooldown` 검증).
     - MAJOR: `extra["consecutive_failures"]` 1/2 → 0건, 3 → 1건 (실 `check_consecutive_failures`),
       발송 후 같은 blog 재호출 시 쿨다운 스킵.
     - MINOR(quiet): 발송 0건.
     - hook 불일치 시 발송 0건(에러 로그), unknown_failure 발송 0건.
     - 500자 초과 템플릿이 트렁케이션되는지 확인.
     - 카운터(W-1): 비-dispatcher 훅(post_validate P15) 연속 카운터 증분 + `reset(blog_id, problem_id)` 호출
       시 키 삭제 확인 (인메모리).
  4. **기존 컨벤션**: `tests/shared/conftest.py` 또는 기존 `tests/curation/conftest.py`의 픽스처 패턴
     (프로젝트 루트 sys.path 등)을 확인해 동일 방식 사용. `.venv/bin/python -m pytest`로 실행.
- **검증**:
  ```bash
  cd /Users/twinssn/Projects/5000
  .venv/bin/python -m pytest tests/shared/test_problem_registry.py tests/shared/test_problem_detectors.py tests/shared/test_problem_monitor.py -v 2>&1 | tail -20
  ```
  (기대: 3파일 전부 통과 — 수치는 실행 결과로 기록)
- **완료 기준**: 3개 테스트 파일 전부 green, 실발송 0건(전부 patch), registry 25건/6/12/6 assert,
  reason 커버리지 테스트가 DEPLOY-PATHS.md 인벤토리와 동기화됨.
- **예상 소요**: 약 2h

---

### Task 8 [TEST CODE] — 통합 테스트 + 회귀 게이트 + dry-run 실발송 0건

- **파일**: `tests/curation/test_problem_monitor_integration.py` (신규)
- **동작**:
  1. **통합 시나리오 테스트** (mock 레벨 — 실발송 금지, 외부 API 호출 금지):
     - curation run() 실패 블록이 `reason="no_result"` 반환 시 P01 spec으로 monitor.report가 호출되는지
       (patch로 검증) — **phase=spec.hook("result_parse") 일치 확인**.
     - writer raw 훅: `generate_curation_article`에 CoT 텍스트('이제 글을 작성하겠습니다...') 주입 시
       P08 보고, 정상 본문 시 보고 0건.
     - publisher `_run_validation`: issues 있는 check_result 주입 시 P15 보고.
     - dispatcher 정규화: reason 문자열이 P04/P05로 매핑되어 report 호출되는지 (mock).
     - **P22 (MAJOR-3 #3)**: `patch("pipelines.curation.writer.ai_generate", side_effect=RuntimeError("모든 LLM tier 실패"))`
       상태에서 `generate_curation_article`(또는 run 경로) 실행 → monitor.report에
       `{"reason": "llm_fallback_exhausted"}` → P22 알림 발송 검증 + **RuntimeError가 기존대로
       재전파(re-raise)되어 no_content 흡수 경로 유지** 확인 (기존 흐름 불변).
     - curation `deploy_error` stage가 **phase="post_deploy"**(P04 hook 일치)로 보고되어 hook 가드에
       차단되지 않는지 확인 (MAJOR-1 #3).
  2. **회귀 게이트** (Task 5/6 수정이 기존 기능을 깨지 않았는지 — 기존 스위트 전량):
     ```bash
     cd /Users/twinssn/Projects/5000
     .venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
     ```
     - **기대: 0 failure** (기존 테스트는 green 유지 — AGENTS.md 코드 수정 원칙).
     - Task 5에서 기록한 **baseline 수치(W-4)와 대조** — baseline 대비 신규 실패 0건이어야 함.
       기존 실패가 baseline에 있으면 "기존 실패 그대로"인지 확인하고 리포트에 기록 — 테스트를 고쳐
       통과시키지 말 것.
  3. **dry-run 실발송 0건 확인 (M-12)**:
     ```bash
     cd /Users/twinssn/Projects/5000
     PROBLEM_ALERT_DRY_RUN=1 .venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
     ```
     - **1차 근거**: T7 `test_problem_monitor.py`의 patch 기반 `send() call_count == 0` assert 전건 통과
       (dry_run=1에서 전 severity 발송 0건을 assert로 실증).
     - 2차 근거: dry-run 환경에서 테스트 로그에 monitor 경유 발송 0건 + `logger.info` 기록 수집.
     - **주의**: 로그 grep만으로 "실발송 0건"을 증명하지 못함 (로그는 기록 발생만 증명) — 1차 근거는
       반드시 T7 patch assert.
  4. **선택 확인** (Open Q1 잔여): DEPLOY-PATHS.md 기준 Pages 경로 전파 방식이 확정됐는지 재확인 —
     미확정이면 리포트에 "검증불가 — 잔존 위험 1"로 기록.
- **검증**:
  ```bash
  cd /Users/twinssn/Projects/5000
  .venv/bin/python -m pytest tests/curation/test_problem_monitor_integration.py -v 2>&1 | tail -10
  .venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
  ```
- **완료 기준**: 통합 테스트 green (P01/P08/P15/P04/P05/**P22** + deploy_error phase 일치 포함), 전체
  스위트 baseline 대비 0 신규 failure, dry-run 실발송 0건(T7 patch assert 1차 근거), 수치 기록.
- **예상 소요**: 약 2h

---

## 검증 태스크 (전수 확인 — Task 1 보강분)

> 실행 태스크의 검증과 별개로, Phase 종료 시 아래를 전수 수행한다.

1. **deploy_error 전수 grep** (Open Q1 — Task 1 산출물 확정본):
   ```bash
   cd /Users/twinssn/Projects/5000
   grep -rn "deploy_error" --include="*.py" dispatcher.py shared/ pipelines/ scripts/ 2>/dev/null
   grep -rn "hugo_build_failed\|build_failed" --include="*.py" dispatcher.py shared/ pipelines/ 2>/dev/null
   ```
   → 발생 지점(발신)과 소비 지점(수신·알림) 수가 DEPLOY-PATHS.md와 일치하는지 대조.
2. **reason 전수 매핑 확인**: Task 1 인벤토리의 모든 reason이 registry의 reason_keys에 커버되는지
   스크립트로 assert (registry 테스트 fixture 재사용).
3. **기존 `_tg_error` 경로 불변 확인**:
   ```bash
   grep -rn "_tg_error" dispatcher.py pipelines/curation/pipeline.py | wc -l   # 수치 기록 (변경 없어야 함)
   git diff --stat dispatcher.py pipelines/curation/pipeline.py shared/publisher.py
   ```
4. **monitor 발송 회수 샘플 로그** — 실운영 환경(launchd)에서는 PROBLEM_ALERT_DRY_RUN=1로 24시간
   관찰 후, 로그에 문제 감지가 실제로 쌓이는지 확인 (실발송은 dry-run 해제 후 다음 Phase에서).

---

## 회귀 / 게이트

| 게이트 | 명령 | 통과 조건 |
|--------|------|-----------|
| 단위 테스트 (T7) | `.venv/bin/python -m pytest tests/shared/test_problem_registry.py tests/shared/test_problem_detectors.py tests/shared/test_problem_monitor.py -q` | 0 failure |
| 통합 테스트 (T8) | `.venv/bin/python -m pytest tests/curation/test_problem_monitor_integration.py -q` | 0 failure |
| 기존 스위트 회귀 | `.venv/bin/python -m pytest tests/ -q` | baseline(Task 5 기록) 대비 0 신규 실패 |
| additivity 게이트 | `git diff --stat` + `grep -c "_tg_error"` | 기존 호출 수 불변, 변경은 추가만 |
| 실발송 0건 | T7 patch 기반 `send() call_count==0` assert (1차 근거, M-12) + dry-run 로그 (2차) | telegram send 0회 |
| py_compile | 각 신규 파일 | 오류 0 |

---

## 커밋 계획 (원자적 커밋 — 태스크별 1커밋)

> 실행 중 각 태스크 완료 시점에 커밋. 커밋 메시지는 repo 컨벤션(간결) 유지.

1. `docs(phase-58): deploy_error 전수 grep 인벤토리 (DEPLOY-PATHS.md)` — T1 산출물
2. `feat(shared): problem_registry — 24개 문제 인벤토리 + lookup` — T2
3. `feat(shared): problem_detectors — 순수 탐지 5함수` — T3
4. `feat(shared): problem_monitor — PublishMonitor 싱글턴 + dry-run` — T4
5. `feat(dispatcher): result reason 매핑 + 배포 실패 캡처 + 카운터 확장` — T5
6. `feat(curation): run()/raw 훅/publisher 검증 모니터 통합 + P22 ai_generate 캐치` — T6
7. `test(shared): registry/detectors/monitor 단위 테스트` — T7
8. `test(curation): 통합 테스트 + 회귀 게이트` — T8

---

## Open Questions (RESEARCH에서 이관 — 태스크에서 해소)

| # | 질문 | 해소 방식 | 해소 상태 |
|---|------|-----------|-----------|
| Q1 | deploy_error가 Pages 경로에서 결과 dict에 병합되는지, 예외 전파인지 | Task 1 전수 grep + read로 확정. 미확정 시 잔존 위험 1로 기록 | **T1에서 해소** (실행 시 확정) |
| Q2 | `_build_and_deploy_central` 반환 False의 reason 문구 구분 가능 여부 | Task 1 read로 로그 문구 수집 → P04/P05 reason_keys 확정 | **T1+T5에서 해소** |
| Q3 | curation run()의 reason이 dispatcher 정규화에서 보존되는지 (similar_title) | Task 5/6 read로 경로 확인, 보존 안 되면 Task 6에서 reason 보존 | **T6에서 해소** |
| Q4 | `data/failure_count.json`의 기존 키 호환 | Task 5에서 int 키 호환 유지 + `{blog_id}:{problem_id}` 추가 (W-1). 기존 키 완전 전환·삭제(마이그레이션)는 **Phase 59 이연** | **부분 해소 T5 / 완전 전환 이연 Phase 59** |

---

## 잔존 위험 (REQUIRED)

| # | 위험 | 대응 | 상태 |
|---|------|------|------|
| 1 | Pages 경로의 deploy 실패가 결과 dict에 안 잡히면 P04 알림 누락 가능 | Task 1 확정, 미확정 시 보고 + dispatcher 배포 캡처(:691) 병행 | 대응 중 (Q1/Q2 — Open Questions 참조) |
| 2 | `_check_multilingual_leak` 기반 감지와 기존 `_is_cot_body`/sanitize 이후 탐지의 이중 보고 소음 | **실 ThresholdChecker 쿨다운(MAJOR-1 수정 후 유효)** + dry-run(24h) 관찰 | 부분 대응 |
| 3 | P09 반복 이미지 탐지가 실전 URL에서 오탐할 가능성 (경계 값) | T3 테스트 경계 케이스 추가, dry-run 관찰 24h | 대응 중 |
| 4 | `validators.py:744-758` `body_md` NameError — 스코프 밖 버그로 잔존 | 이번 phase에서 수정하지 않음 (잔존 위험으로 기록, 재발 시 별도 phase) | 이연 |
| 5 | `detect_post_generate`가 P07/P08/P09/P23 **전건 리스트**를 반환해 다건 발송 소음 가능 (CoT 재시도 후 정상 발행에도 누수 보고) | monitor 쿨다운(60분)이 블로그 단위 소음 흡수, dry-run 관찰로 다건 빈도 확인 | 부분 대응 |
| 6 | daily_failure_rate 미강제 (기존 선례 동일) | spec 메타데이터만 등록, 실강제는 Phase 59+ | 이연 |
| 7 | ai_writer 기반 타 파이프라인(car/senior/gap/rap/travel/etap)은 P07/P08/P09/P22 배선 없음 (curation만) | 이번 phase 스코프로 명시(W-2), 후속 phase에서 공용 확장 검토 | 이연 |

> 위험 1, 3, 5는 dry-run(24h) 관찰 후 Phase 59에서 실발송 전환 시 재평가.

---

## 성공 기준 (CONTEXT §성공 기준 8건 → 태스크 매핑)

| # | 성공 기준 | 담당 태스크 |
|---|-----------|------------|
| 1 | 24개 문제가 registry에 전부 등록 (6/12/6) | T2, T7 |
| 2 | 알림이 문제별 한국어 템플릿으로 발송 (problem_id 명시) | T4, T7 |
| 3 | 기존 `_tg_error` 호출 경로 불변 (additive) | T5, T6, T8 게이트 |
| 4 | dry-run 모드로 실발송 없이 관찰 가능 | T4, T8 |
| 5 | dispatcher reason → 문제 매핑 전수 커버 | T1, T2, T5, T7 |
| 6 | 테스트 전량 green (기존 + 신규) | T7, T8 |
| 7 | 커밋이 태스크 단위 원자적 분리 | 커밋 계획 |
| 8 | deploy_error 전수 grep 결과가 DEPLOY-PATHS.md와 일치 | T1, 검증 태스크 |

---

## Task 요약 (실행 순서)

| 순서 | Task | 파일 | wave |
|------|------|------|------|
| 1 | Task 1 deploy_error 전수 grep | DEPLOY-PATHS.md (신규) | 1 |
| 2 | Task 2 problem_registry.py | shared/problem_registry.py (신규) | 2 |
| 3 | Task 3 problem_detectors.py | shared/problem_detectors.py (신규) | 2 |
| 4 | Task 4 problem_monitor.py | shared/problem_monitor.py (신규) | 3 |
| 5 | Task 5 dispatcher 통합 | dispatcher.py | 4 |
| 6 | Task 6 curation/publisher 통합 | pipelines/curation/pipeline.py, writer.py, shared/publisher.py | 4 |
| 7 | Task 7 단위 테스트 | tests/shared/* 3파일 (신규) | 5 |
| 8 | Task 8 통합 테스트 + 회귀 | tests/curation/test_problem_monitor_integration.py (신규) | 5 |

**총 8 태스크 / 5 wave** — 예상 소요: 약 12h (개발 9h + 테스트 2h + 검증 1h).
