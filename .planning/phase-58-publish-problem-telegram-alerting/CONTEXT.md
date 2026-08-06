# CONTEXT.md — Phase 58: 발행 문제 인벤토리 + 정밀 Telegram 알림 시스템

## 배경

- 5000 파이프라인은 블로그당 하루 수 회 자동 발행 (50+ 블로그, CAP/CUAP/TAP/STAP/RAP/SEAP)
- 현재 발행 오류 알림은 `shared/telegram_notifier.py`의 `send_error(blog_id, stage, error_msg)`
  **단일 템플릿**("🚨 발행 오류 / 블로그 / 도메인 / 레포 / 단계 / 오류")에 raw reason 문자열이
  그대로 들어감 — 사용자가 어떤 문제가 발생했는지 원인을 정확히 알 수 없음
- RESEARCH (2026-08-06, `c06a852ec`) 결과 **24개 문제** 확정 (CRITICAL 6 / MAJOR 12 / MINOR 6 —
  목록 기준으로 정정, PLAN-CHECK M-7 반영):
  - CRITICAL 6 (전부 현재 침묵): P04 deploy_error(ETAP/Workers), P05 Hugo build failed,
    P06 broken_featureimage, P07 CJK 누수, P08 LLM/CoT 누수, P09 이미지 URL 토큰 반복
  - MAJOR 12: P01 no_result, P02 no_content, P03 similar_title(현재 침묵), P10 title_blocked,
    P11 title_regenerate_failed, P12 content_quality_gate, P13 rate_limited, P14 수집/품질 게이트,
    P15 발행 후 검증 실패, P20 subprocess 에러, P21 config_error, P22 LLM 폴백 전체 실패(침묵)
  - MINOR 6: P16 duplicate_slug/source_id, P17 quota, P18 already_running, P19 오래된 데이터,
    P23 이미지 URL 길이, P24 검증 함수 결함
- 핵심 발견: 탐지 로직은 대부분 **이미 존재** (validators, ai_response_parser, post_validator,
  URL-REPEAT, scan_multilingual_leak). 부족한 것은 탐지가 아니라 **분류·템플릿·정책·단일 진입점**.
- 본 phase 목표: 문제를 리스트화하고, 요소마다 탐지 방법을 확정하며, 발행 시 문제 발생 시
  **어떤 문제가 발생했는지 정확한 텔레그램 알림**이 오도록 하는 시스템 구축

## 계약 (계획 시 준수할 제약)

1. **additive, non-destructive**: 기존 기능 보존 원칙. 기존 `_tg_error` 호출 경로
   (dispatcher.py:709/715/718/723/697, curation pipeline.py:857, scheduler.py:284-293)는 **변경하지 않음**.
   monitor는 병렬로 추가. 중복 알림은 monitor의 쿨다운이 흡수.
2. **신규 모듈 3종 추가**: `shared/problem_registry.py`(ProblemSpec + PROBLEM_REGISTRY),
   `shared/problem_detectors.py`(순수 탐지 함수), `shared/problem_monitor.py`(PublishMonitor).
   기존 모듈 시그니처 변경 금지.
3. **새 탐지기 금지 → 기존 시그니처 재사용**: `validators.has_cjk`(단일 소스), `ai_response_parser._check_multilingual_leak`,
   `post_validator.validate_post_html`, `_has_repeated_pattern` 로직, `ThresholdChecker`(쿨다운),
   `telegram_notifier.send`. 새 정규식·새 HTTP 클라이언트·새 쿨다운 구현 금지.
4. **CJK 오탐 방지**: 단순 한자 존재 탐지 금지 (travel2 heritage 한자 병기 86건 오탐 실측).
   한글 비율 0.5 기반(`is_korean_content`) + 지시문성 중국어 키워드 기준으로만 알림.
5. **sanitize 이전 raw 탐지**: post-generate 훅은 반드시 raw 콘텐츠에서 실행 (BUG-54-001 교훈).
6. **심각도 정책 기본값**: CRITICAL = always(쿨다운 60분), MAJOR = consecutive:3 + daily_rate:0.5,
   MINOR = quiet(로그만). `PROBLEM_ALERT_DRY_RUN=1` env로 안전 롤아웃.
7. **스코프**: 5000 repo만 (STAP/TAP/ETAP 내부 알림은 스코프 밖, 보고만). `notify.py` 교체·기존 죽은
   코드(`send_validation`, `send_no_result_alert`) 삭제는 Phase 59 이연.
8. **검증 명령**: `.venv/bin/python -m pytest tests/...` 사용 (launchd와 동일 .venv 3.11).
   테스트는 `patch("shared.telegram_notifier.send")` 필수 (실전 발송 금지).

## 확정된 설계 결정 (PLAN.md에 반영할 것)

- **ProblemSpec (dataclass)**: `problem_id`, `name_ko`, `severity`, `reason_keys`, `hook`,
  `detect_fn`, `alert_template`(한국어, str.format), `threshold`, `cooldown_minutes`.
  reason→problem_id 매핑은 `reason_keys`로 수행 (dispatcher 결과 dict의 `reason` 문자열 기반).
- **PublishMonitor**: `report(blog_id, result, phase, extra) -> list[str]` (발송된 problem_id 목록,
  dry-run이면 발송 예정 목록), `send_problem_alert(problem_id, blog_id, context) -> str|None`,
  `detect(hook, content, blog_id) -> list[Detection]`. `get_monitor()` 싱글턴 제공.
  `PROBLEM_ALERT_DRY_RUN` env 우선, ThresholdChecker 쿨다운 재사용.
- **연속 카운터**: `data/failure_count.json` (dispatcher.py:91, 142-164) 재사용, 전 reason 공용으로 확장.
  P03 similar_title도 카운트에 포함. 발행 성공 시 리셋은 기존 `_reset_failure_count` 그대로.
- **통합 지점 6곳 (추가만)**:
  1. dispatcher 결과 파싱 (dispatcher.py:687-740) — `monitor.report(blog_id, result)` 호출 추가
  2. dispatcher 배포 결과 (dispatcher.py:691-692) — `_build_and_deploy_central` 반환값 캡처 → False면
     `monitor.report(..., {"success": True, "deploy_error": "..."})` → P04/P05 침묵 해소
  3. curation run() (pipeline.py:850-865) — `monitor.report` 추가, 기존 알림은 유지
  4. post-generate 훅 — raw 콘텐츠에서 `monitor.detect("post_generate", raw)` (sanitize 이전) → P07/P08/P09
  5. post-publish 검증 (publisher.py:836-855) — `classify_validation_issue()` 매핑 → P15/P06
  6. scheduler `_track_publish_result` (scheduler.py:734-758) — 유지, 쿨다운 공유만 확인
- **알림 템플릿 예시** (모두 한국어, 문제별):
  - CRITICAL: "🚨 [CRITICAL] 콘텐츠 오염 — LLM/CoT 누수 감지\n블로그: {blog_id}\n문제: P08...\n감지 단계: ...\n감지 패턴: ...\n조치: ..."
  - MAJOR: "⚠️ [MAJOR] 발행 불가 — 유사 제목 중복\n블로그: ...\n문제: P03...\n연속 실패: N회\n조치: ..."
  - 템플릿에 토큰·full URL 미포함 (500자 트렁케이션 유지)
- **Pages 블로그 deploy_error 전파 경로 검증 태스크**: RESEARCH Open Q1 — `deploy_error` 발생 지점 전수
  grep 후 P04/P05 레지스트리 등록 (검증 태스크로 계획에 포함)

## 성공 기준

1. PROBLEM_REGISTRY에 24개 문제 전부 등록 — reason→problem_id 매핑 완전성 테스트 통과
   (dispatcher가 내보낼 수 있는 모든 reason이 레지스트리에 존재)
2. `shared/problem_registry.py`, `shared/problem_detectors.py`, `shared/problem_monitor.py` 신규 생성
3. CRITICAL 문제 6건(P04~P09)이 1회 발생 시 즉시 알림 (dry-run으로 검증)
4. P03 similar_title 포함 MAJOR 문제가 연속 3회 시 알림 (mock send로 검증)
5. 기존 테스트 스위트 green 유지 (tests/curation/test_pipeline.py, test_alert_thresholds.py,
   tests/shared/test_telegram_notifier.py 회귀 0건)
6. 신규 테스트: tests/shared/test_problem_registry.py, test_problem_detectors.py,
   test_problem_monitor.py, tests/curation/test_problem_monitor_integration.py
7. `PROBLEM_ALERT_DRY_RUN=1`에서 실제 Telegram 발송 0건 (로그로만) 확인
8. 신규 테스트 전부 통과 + 기존 테스트 회귀 0건 — 숫자 분해 보고 (예: "N = 신규 X + 기존 Y")
