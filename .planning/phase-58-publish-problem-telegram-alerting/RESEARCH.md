# Phase 58: 발행 문제 인벤토리 + 정밀 Telegram 알림 — Research

**Researched:** 2026-08-06
**Domain:** 발행 오류 탐지·분류·경보 (Publish Problem Detection & Telegram Alerting)
**Confidence:** HIGH (전원 코드베이스 직접 검증, `[VERIFIED: codebase]`)

## Summary

현재 5000 파이프라인의 발행 오류 알림은 **구조화되지 않은 상태**다. 모든 알림이
`shared/telegram_notifier.py`의 `send_error(blog_id, stage, error_msg)` **단일 템플릿**
("🚨 발행 오류 / 블로그 / 도메인 / 레포 / 단계 / 오류")으로 나가며, stage 인자에 raw
reason 문자열(`no_result`, `no_content`, `deploy` 등)이 그대로 들어간다. 문제별 전용
알림 문구·발행 시도 횟수 컨텍스트·심각도별 임계값 정책이 전혀 없다.

두 번째 발견: **상당수 문제가 침묵(silent) 상태**다. (1) `similar_title`은 dispatcher의
알림 목록(dispatcher.py:706)과 curation run() 알림 제외 목록(pipeline.py:856)에서
모두 제외되어 **0건 알림**. (2) CJK/CoT 누수는 `ai_writer.py:439`에서 `RuntimeError`로
승격된 뒤 파이프라인에서 `no_content`/`no_result`로 **재분류·흡수**되어 정확한 원인이
사라진다. (3) ETAP/Workers 블로그 배포 실패는 `dispatcher.py:691-692`에서
`_build_and_deploy_central()` 반환값을 **무시**해 침묵한다. (4) 이미지 URL 토큰 반복은
자동 수정(fixer) 후 log만 남긴다(`[URL-REPEAT]`, hugo_writer.py:48). (5)
`broken_featureimage`는 런타임 탐지 자체가 없어 수동 `batch_thumbnails.py`에 의존한다.

세 번째 발견: **알림 경로 중복/사중화**가 있다. 단일 실패가 (a) curation
`_record_failure`의 3연속 알림(pipeline.py:734-739), (b) curation `run()`의 매회
`_tg_error`(pipeline.py:857), (c) dispatcher의 매회 `_tg_error`(dispatcher.py:715),
(d) `ThresholdChecker.maybe_alert`(쿨다운 60분) — 최대 4개 경로로 중복 전송될 수 있다.
또 `shared/notify.py`는 `telegram_notifier`의 **거의 중복** 구현이며
`shared/validators.py:721` 단 1곳에서만 활성 사용 중이다. `send_validation()`과
`send_no_result_alert()`은 정의만 있고 **호출처가 없는 죽은 코드**다.

**Primary recommendation:** `shared/problem_registry.py`(문제 메타데이터 + 탐지 훅 +
알림 템플릿 + 임계값 정책) + `shared/problem_monitor.py`(PublishMonitor —
`report(result)` 단일 진입점, 심각도별 정책, dry-run)를 **추가**(additive)로 도입하고,
dispatcher 결과 파싱부·curation run()·publisher 검증부·post-generate 훅 4곳을
모니터에 연결한다. 기존 `_tg_error` 호출과 `ThresholdChecker`는 보존한다.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 문제 분류·탐지 (result parse) | API/Backend (dispatcher.py) | — | 모든 pipeline 결과가 `dispatch()`에서 정규화됨 (dispatcher.py:672-741) |
| 문제 탐지 (콘텐츠 생성 단계) | API/Backend (ai_writer / curation writer) | — | CJK/CoT/URL 반복은 생성 직후 원본(raw)에서만 탐지 가능 (BUG-54-001 교훈) |
| 문제 탐지 (발행 후 검증) | API/Backend (publisher._run_validation) | — | Hugo 출력 HTML 검증은 publisher.py:836-855 |
| 문제 탐지 (배포 단계) | API/Backend (deploy.py) | — | Hugo 빌드/wrangler 실패는 deploy.py:106-107, 167-168 |
| 알림 전송 | API/Backend (telegram_notifier) | — | Telegram API는 서버 측 1곳에서만 호출 |
| 임계값·쿨다운 | API/Backend (alert_thresholds) | — | ThresholdChecker가 연속 실패/쿨다운 관리 (alert_thresholds.py:31-155) |
| 경보 수신 | — | User (Telegram) | 최종 소비자는 사용자 1인 |

---

## 1. 문제 인벤토리 (Problem Inventory)

> 모든 탐지 위치는 `[VERIFIED: codebase]` — 직접 read/grep으로 확인한 파일:라인.
> 심각도 기준: **CRITICAL** = 단 1회 발생해도 즉시 인지해야 하는 문제(콘텐츠 오염·배포 실패),
> **MAJOR** = 연속/빈도 임계값 초과 시 알림(발행 불가류), **MINOR** = 로그/통계로 충분.

| ID | 문제명 | 심각도 | 탐지 시점 | 현재 탐지 위치 (파일:라인) | 현재 알림 상태 |
|----|--------|--------|-----------|--------------------------|----------------|
| P01 | no_result (발행 데이터 없음) | MAJOR | dispatcher 결과 파싱 | dispatcher.py:675-677 (None→no_result), :662-670 (cooldown), travel/pipeline.py:219-260 (시군구·가게명 가드 → None), travel/pipeline.py:196-200 (단일소스 fetch 실패) | ⚠️ 알림됨 — `_tg_error`에 연속 횟수 포함 (dispatcher.py:714-715), 3회 시 일일 cooldown+escalation (dispatcher.py:716-719) |
| P02 | no_content (콘텐츠 생성 실패) | MAJOR | dispatcher 결과 파싱 | STAP sector/pipeline.py (subprocess, dispatcher.py:325-384 `_run_stap`), stock/pipeline.py:269 (`reason: "no_content"`), senior/pipeline.py, dispatcher.py:706 | ⚠️ 알림됨 — 일반: 연속 횟수 포함 (dispatcher.py:715), IPO: 1회 알림+일일 cooldown (dispatcher.py:708-712) |
| P03 | similar_title (유사 제목 중복) | MAJOR | dispatcher 결과 파싱 / curation | curation/pipeline.py:1104-1128 (fallback 3회 소진 → `similar_title`), :856 (알림 제외 목록), content_store.py:231-260 (SequenceMatcher 80%), travel/pipeline.py:292-294, validators.py:352-361 (Jaccard 0.7) | 🔴 **침묵** — dispatcher.py:706 알림 목록에 없음, curation run()에서도 제외 (pipeline.py:856), ledger에는 기록됨 (dispatcher.py:703-704) |
| P04 | deploy_error (배포 실패) | CRITICAL | post-deploy | dispatcher.py:694-700 (`result.deploy_error` 처리), STAP stock/pipeline.py:427-428 (`tg_error("deploy")`), deploy.py:167-168 (wrangler 3회 실패 raise), dispatcher.py:613-615 (`_build_and_deploy_central` return False) | ⚠️ 부분 — STAP은 알림 (stock/pipeline.py:428), **ETAP/Workers는 `_build_and_deploy_central` 반환값 무시 (dispatcher.py:691-692) → 침묵** |
| P05 | Hugo build failed | CRITICAL | post-deploy | deploy.py:106-107 (`_run_hugo_build` 실패 raise "Hugo build failed"), dispatcher.py:557-559 (central 경로), deploy.log (logs/deploy.log) | 🔴 **침묵** — 예외는 파이프라인에 전파되지만 ETAP/Workers 경로에서는 결과에 반영 안 됨; Pages 경로도 `deploy_error`로만 부분 전달 |
| P06 | broken_featureimage (썸네일 404) | CRITICAL | post-publish 검증 | 런타임 미탐지; 수동 `scripts/batch_thumbnails.py`; post_validator.py:129-131 (og:image 없음 = WARNING에 불과), AGENTS.md incident "kuta-hugo" | 🔴 **침묵** — 런타임 탐지 자체 없음, 사후 수동 대응 |
| P07 | CJK 누수 (제목/본문 중국어·일본어) | CRITICAL | content generation + post-validate | validators.py:20-32 (`has_cjk`), :200-209 (`assert_korean_or_reject`), curation/pipeline.py:1148-1151 (조용히 다음 키워드), ai_response_parser.py:40-43 (CJK_INSTRUCTION_LEAK), scan_multilingual_leak.py:27-30, 62-65 (cjk_leak_keywords, cjk_line_leak), slugify 화이트리스트 (b0bb7dbb6) | 🔴 **침묵/재분류** — curation은 다음 키워드로 진행, ai_writer는 RuntimeError로 승격 후 no_content로 흡수 (ai_writer.py:439) |
| P08 | LLM/CoT 누수 (사고과정·지시문 노출) | CRITICAL | content generation | ai_response_parser.py:15-49 (THINKING_PATTERNS 9종), :65-82 (_check_multilingual_leak), :84-195 (구조 파싱), curation/writer.py:606-648 (_is_cot_body), :600-603 (임계값 상수), curation/pipeline.py:29-43 (WRITING_INSTRUCTION_PATTERNS/COT_BODY_PATTERNS), :761-833 (content_quality_gate), scan_multilingual_leak.py:15-71 | 🔴 **침묵/재분류** — BUG-54-001(호출 시점 버그) 수정됐으나 전용 알림 없음; RuntimeError→no_content 흡수 |
| P09 | 이미지 URL 토큰 반복 (LLM stutter) | CRITICAL | post-generate (writer) | hugo_writer.py:14-55 (`_fix_repeated_image_urls`, 자동 수정+`[URL-REPEAT]` warning), curation/writer.py:169-216, scripts/fix_repeated_image_urls.py:68-83 (`has_repeated_pattern` 4자×5회) | 🔴 **침묵** — 자동 수정 후 log만, 사용자 미통지 |
| P10 | 제목 템플릿 패턴 (title_blocked) | MAJOR | post-generate | curation/pipeline.py:742-758 (`_title_gate`), writer.py:508-517 (`_TITLE_TEMPLATE_PATTERNS`: "추천 TOP N", "(연도년)", "BEST N" 등) | ⚠️ 알림됨 — curation run()에서 raw reason (pipeline.py:857) |
| P11 | title_regenerate_failed | MAJOR | content generation | curation/pipeline.py:751-753 (`_title_gate`에서 2회 소진), writer.py:561-597 (`_regenerate_title`) | ⚠️ 알림됨 — raw reason |
| P12 | content_quality_gate (CoT body 차단) | MAJOR | post-generate | curation/pipeline.py:761-833 (신호 5종 판정), :823-830 (fail-closed) | ⚠️ 알림됨 — raw reason |
| P13 | rate_limited (쿠팡 API 차단) | MAJOR | content collection | curation/pipeline.py:890-894 (`_check_rate_limit`) | ⚠️ 알림됨 — raw reason |
| P14 | 수집/품질 게이트 실패 (no_keyword, collect_error, insufficient_products, irrelevant_products, low_relevance) | MAJOR | content collection | curation/pipeline.py:882-885, :895-897, :901-933, :938-975, :976-1009 | ⚠️ 알림됨 — raw reason |
| P15 | 발행 후 검증 실패 (CTA 누락, og:image 없음, min_length, 빈 템플릿 `{{}}`, keyword_coverage) | MAJOR(ERROR)/MINOR(WARNING) | post-publish 검증 | publisher.py:836-855 (`_run_validation`), post_validator.py:92-180 (validate_post_html), :100-118 (CTA), :119-126 (빈 템플릿), :128-131 (og:image), :138-149 (min_length/readability), :151-175 (keyword_coverage) | ⚠️ 알림됨 — `send_error("validation")` 1건으로 통합 (publisher.py:848-854); **`send_validation()`은 죽은 코드** (telegram_notifier.py:88-104, 호출처 0건) |
| P16 | duplicate_slug / duplicate_source_id | MINOR | publish | publisher.py:877-901 (source_exists, slug 중복), dispatcher.py:720-726 (STAP collect_all 자동 실행+알림) | ⚠️ 알림됨 (dispatcher.py:723-726) |
| P17 | quota_met / daily_quota_exceeded | MINOR | dispatcher | dispatcher.py:655-659, telegram_notifier.py:38-47 (`_SILENT_REASONS`) | 🔇 의도적 침묵 |
| P18 | already_running (동시 실행 방지) | MINOR | pipeline 진입 | curation/pipeline.py:842-845 (락 실패) | 🔇 의도적 침묵 |
| P19 | 오래된/만료 데이터 (event_date 경과) | MINOR | post-generate 검증 | validators.py:363-372 (stale 7일), :521-530 (행사 종료 3일), :576-589 (정책 30일) | 🔴 침묵 — WARNING → draft 전환 (travel/pipeline.py:334-336) |
| P20 | subprocess 타임아웃/에러 (stap_timeout, tap_timeout, stap_subprocess_error) | MAJOR | dispatcher 결과 | dispatcher.py:377-384, :487-492, :366-375 | ⚠️ 알림됨 — raw reason |
| P21 | config_error / unknown_pipeline / unknown blog_id | MAJOR | dispatcher 진입 | dispatcher.py:646-650, :443-445, :433-434 | ⚠️ 알림됨 — raw reason |
| P22 | LLM 폴백 체인 전체 실패 (RuntimeError) | MAJOR | content generation | ai_writer.py:315 (`raise RuntimeError(msg)` — 전 tier 실패), :123-315 (generate, 17-tier 폴백) | 🔴 **침묵/재분류** — 파이프라인 catch 후 no_content/no_result로 흡수; llm_trace JSONL (ddd9d2fb2)에만 기록 |
| P23 | 이미지 URL 길이 초과 (macOS 255자) | MINOR | post-generate | hugo_writer.py:354-366 (`_shorten_long_url` — 200자 초과 R2 업로드), :636-642 (`sanitize_featureimage_url` max_len=200/500) | 🔴 침묵 — 자동 대체, 실패 시 warning만 (AGENTS.md laptop-hugo incident는 해결됨) |
| P24 | 검증 함수 자체 결함 (예: `validate_post_extended`의 `body_md` NameError) | MINOR | — | validators.py:744-758 (senior+coupang 분기에서 `body_md` 미정의 → NameError), :211-232 (죽은 코드) | 🔴 침묵 — try/except로 삼켜짐 |

**합계: 24개 문제** — CRITICAL 6 (P04, P05, P06, P07, P08, P09), MAJOR 13, MINOR 5.

### 침묵 문제 요약 (알림이 없어 정밀 알림이 필요한 핵심 8건)

| 문제 | 현재 상태 |
|------|-----------|
| P03 similar_title | dispatcher 알림 목록·curation 제외 목록 둘 다에서 제외 — 0건 알림 |
| P04/P05 배포 실패 (ETAP/Workers) | `_build_and_deploy_central` 반환값 무시 (dispatcher.py:691-692) |
| P06 broken_featureimage | 런타임 탐지 자체 없음 |
| P07/P08 CJK·CoT 누수 | RuntimeError 승격 → `no_content`로 재분류 (ai_writer.py:439) |
| P09 이미지 URL 반복 | 자동 수정 + log만 |
| P22 LLM 폴백 전체 실패 | llm_trace JSONL 기록만 |

---

## 2. 탐지 매커니즘 분석 (Detection Mechanism Analysis)

### 2.1 문제별 탐지 방법 (현재 코드 기준 → 재사용 가능한 시그니처)

**P01 no_result**
- 탐지: `dispatch()` 결과가 `None` 또는 `{"success": False, "reason": "no_result"}` (dispatcher.py:675-677).
- travel 파이프라인 세부 원인은 `_travel_sigungu_recently_published()` (travel/pipeline.py:99-146, 14일 룩백),
  가게명 중복 (travel/pipeline.py:262-280), 단일소스 fetch 실패 (travel/pipeline.py:196-200).
- **재사용**: 실패 사유가 `no_result`면 원인 카테고리를 구분할 컨텍스트(블로그, fetch 소스, cooldown 여부)를
  dispatcher가 이미 보유 (dispatcher.py:662-670).

**P02 no_content**
- 탐지: `{"success": False, "reason": "no_content"}` — STAP sector/stock/senior에서 반환.
- sector 원인: 토픽 순환 소진 + 제목/업종 중복 가드 (AGENTS.md incident) → STAP subprocess stdout JSON 파싱 (dispatcher.py:370-372).
- **재사용**: `_run_stap`이 JSON을 반환하므로 원인 세부 문자열(`result.get("keyword")` 등)을 결과 dict에서 추출 가능.

**P03 similar_title**
- 탐지: curation/pipeline.py:1108-1128에서 `reason: "similar_title"` 반환; `_title_is_duplicate` (content_store.py:231-260, SequenceMatcher 80%, 14일).
- travel은 자체 `_travel_title_similar_exists` (travel/pipeline.py:69-96) 사용 → `None` 반환 → dispatcher에서 no_result로 재분류되는 점 주의.
- **재사용**: reason만으로 충분. 원인 컨텍스트(키워드, fallback 소진 여부)는 curation 결과 dict에 `keyword` 키로 존재.

**P04/P05 deploy_error / Hugo build failed**
- 탐지: (a) `result.get("deploy_error")` (dispatcher.py:694), (b) `_build_and_deploy_central` return False (dispatcher.py:613-615, 557-559), (c) `deploy.py:106-107` raise, (d) deploy.log (`logs/deploy.log`).
- **재사용**: `_build_and_deploy_central` 반환값이 **현재 무시**되고 있음 — 반환값을 결과에 병합하는 것이 1차 개선점.
  wrangler stderr에서 인증 오류(`Authentication error code: 10000`) 구분 가능 (deploy.py stdout/stderr).

**P06 broken_featureimage**
- 탐지: frontmatter `featureimage:` URL에 대해 HTTP HEAD/GET 200 확인 (scripts/batch_thumbnails.py 패턴, AGENTS.md kuta-hugo incident).
- **재사용**: `batch_thumbnails.py`의 `_read_frontmatter` (line 97) + R2 URL 검증 로직. 발행 직후 1회 HTTP 확인은
  발행 당시에만 수행하도록 제한(사이트 전체 스캔 금지) 필요.

**P07 CJK 누수**
- 탐지: `validators.has_cjk()` (validators.py:20-32, `[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u3040-\u309F\u30A0-\u30FF]`) — **단일 소스**.
  `assert_korean_or_reject` (validators.py:200-209)는 제목 단독 검사 + 본문 한글 비율 0.5.
  확장 시그니처: scan_multilingual_leak.py:27-30 (cjk_leak_keywords), :62-65 (cjk_line_leak 한 줄 3자 이상).
- **주의**: heritage 콘텐츠는 한자 병기가 정상 (travel2_investigation.md — cjk_line_leak 86건 전부 오탐).
  → 본문 한글 비율(0.5) 기반 탐지가 안전, 단순 한자 존재 탐지는 오탐 유발.
- **재사용**: `has_cjk` + `is_korean_content` (validators.py:186-197) + 확장 키워드 목록.

**P08 LLM/CoT 누수**
- 탐지: ai_response_parser.py:15-49 (THINKING_PATTERNS — ko/en thinking, prompt instruction, thinking 태그),
  :40-43 (CJK_INSTRUCTION_LEAK), :46-49 (FORBIDDEN_WORD_REVERSE), curation/writer.py:606-648 (_is_cot_body,
  3조건 중 2개), curation/pipeline.py:761-833 (content_quality_gate 5신호 중 2개).
- **핵심 교훈 (BUG-54-001)**: sanitize **이전** raw 콘텐츠에서 탐지해야 함 (triage/BUG-54-001-cot-body-detection-not-called.md:44-45).
- **재사용**: `_check_multilingual_leak()` (ai_response_parser.py:65-82) — (has_leak, pattern_name, matched) 반환.
  파이프라인별 임계값 차이(단일 신호 vs 2개 이상)는 컨텍스트로 전달.

**P09 이미지 URL 토큰 반복**
- 탐지: `_has_repeated_pattern(url, min_repeat_len=4, min_repeats=5)` (hugo_writer.py:26-39) — 부분 문자열 4자 이상 연속 5회.
- **재사용**: 동일 함수가 hugo_writer.py:14-55, curation/writer.py:169-216, scripts/fix_repeated_image_urls.py:68-83에 **3중 복제**되어 있음.
  감지 로직을 shared로 추출하고 fixer는 유지, 감지 시 알림만 추가하면 됨.

**P10-P14, P20, P21 (이유 문자열 기반)**
- 모두 `reason` 문자열로 이미 구분 가능 (curation/pipeline.py의 `_record_failure` stage 인자, dispatcher.py:702-704).
- **재사용**: dispatcher 결과 dict가 이미 정규화된 `reason`을 가짐 — PROBLEM_REGISTRY의 reason→problem_id 매핑만 추가하면 됨.

**P15 발행 후 검증 실패**
- 탐지: `validate_post_html(html, blog_id)` (post_validator.py:92-180) → `{"passed", "issues[]"}`,
  publisher.py:846-855에서 호출. issues에 `check` 이름(`cta_html`, `empty_template`, `thumbnail`, `min_length`...) 포함.
- **재사용**: issue dict가 이미 구조화됨 → check 이름을 problem_id로 매핑 가능.

**P19 오래된 데이터**
- 탐지: validators.py:363-372, :521-530, :576-589 (event_date/policy_date 경과).
- **재사용**: validate 이슈 목록에서 `[WARNING]` 구분.

**P22 LLM 폴백 전체 실패**
- 탐지: `generate()`가 RuntimeError raise (ai_writer.py:315); `data/llm_trace/*.jsonl`에 폴백 사슬 기록 (ddd9d2fb2).
- **재사용**: llm_trace 로그에 `fallback_count`, `fallbacks` (ai_writer.py:266-267) — 파이프라인 catch 지점에서
  `RuntimeError` 유형을 구분해 `llm_fallback_exhausted` 문제로 매핑 가능.

### 2.2 기존 검증/스캐너 요약

| 도구 | 위치 | 역할 | 재사용 가능한 시그니처 |
|------|------|------|----------------------|
| `validate_post` / `validate_post_extended` | validators.py:313-399 / :692-760 | 발행 전 검증 (제목 길이, 본문 길이, AI 잔여물, 유사 제목, stale, 일일 한도, 네이버지도, 쿠팡, 내부링크, 면책) | 이슈 문자열 접두사 `[CRITICAL]`/`[ERROR]`/`[WARNING]` (validators.py:217, 243, 495, 632...) |
| `has_cjk` / `is_korean_content` / `assert_korean_or_reject` | validators.py:20-32, 186-209 | CJK 단일 소스 | 한글 비율 0.5, 제목 단독 CJK |
| `_check_multilingual_leak` | ai_response_parser.py:65-82 | 다국어 누수 (thinking/지시문/CJK) | THINKING_PATTERNS 9종 + CJK_INSTRUCTION_LEAK |
| `_is_cot_body` | curation/writer.py:606-648 | CoT body 판정 (3조건 중 2) | 영어 비율 0.30, 지시어 3+, 마커 1+ |
| `_content_quality_gate` | curation/pipeline.py:761-833 | 5신호 fail-closed 게이트 | 신호별 `signal_details` |
| `scan_multilingual_leak.py` | scripts/scan_multilingual_leak.py:15-71 | 오염 전수 스캔 (10패턴) | ko/en_thinking, cjk_leak_keywords, prompt_instruction_leak, forbidden_grammar_break, forbidden_word_reverse, test_dummy, raw_slug_title, cjk_line_leak, thinking_tag_remain |
| `phase5_verify.py` | scripts/phase5_verify.py:60-114 | dry-run 검증 (5항목) | scan_content() — 오염 스캔 재사용 가능 |
| `validate_post_html` | post_validator.py:92-180 | 발행 후 HTML 검증 | issue check 이름 (`cta_html`, `empty_template`, `thumbnail`, `min_length`, `readability`, `keyword_coverage`) |
| `_fix_repeated_image_urls` | hugo_writer.py:14-55 | URL 토큰 반복 자동 수정 | `_has_repeated_pattern` (4자×5회) |
| `has_repeated_pattern` | scripts/fix_repeated_image_urls.py:68-83 | 동일 (복제본) | 동일 |

### 2.3 탐지 시점 매핑 (프로세스 흐름)

```
scheduler.py:264 (dispatcher subprocess)
  → dispatcher.py:643 dispatch() 
      → :672 _run_pipeline()  → pipeline.run(cfg)
          ├─ [content generation] ai_writer.generate() / curation writer  ← P07, P08, P22, P09
          ├─ [collection] curation collector                              ← P13, P14
          ├─ [publish] publisher.publish()                                ← P16, P19, P03
          │    └─ publisher._run_validation()  (post-publish HTML 검증)    ← P15, P06
          │         └─ deploy_site() / _build_and_deploy_central()        ← P04, P05
          └─ 결과 dict 반환
      → :687-740 결과 정규화 + _record_failure + _tg_error  ← P01, P02, P03, P20, P21
  → scheduler._track_publish_result() (scheduler.py:734-758)  ← 연속 실패 임계값
```

---

## 3. 알림 아키텍처 분석 (Alert Architecture)

### 3.1 전송 계층

**`shared/telegram_notifier.py`** (113줄) — 사실상 유일한 전송 계층 `[VERIFIED: codebase]`
- `BOT_TOKEN`/`CHAT_ID` — import 시점 `os.getenv` (line 8-9); `API_URL`도 import 시점 고정 (line 10).
  → **dotenv 로드 후 import해야 하며**, dispatcher.py:25-27 / scheduler.py:23-24가 ~/.env.common + .env 로드 후
  import하므로 정상 동작 (dispatcher.py:31).
- `send()` (line 13-33): requests.POST, timeout 10, 실패 시 False.
- `send_error(blog_id, stage, error_msg)` (line 36-81): **단일 템플릿** "🚨 발행 오류\n블로그/도메인/레포/단계/오류".
  - `_SILENT_REASONS` (line 38-43): quota 계열 4종 자동 침묵.
  - blogs.d/*.yaml에서 domain/repo 조회 (line 50-71).
  - error_msg 500자 트렁케이션 (line 80).
- `send_daily_report()` (line 84-85), `send_validation()` (line 88-104) — **죽은 코드, 호출처 0건**,
  `send_no_result_alert()` (line 107-113) — **죽은 코드, 호출처 0건**.

**`shared/notify.py`** (44줄) — **telegram_notifier의 거의 중복, 활성 호출 1곳** `[VERIFIED: codebase]`
- `send_telegram()` (line 19-36): urllib 기반 자체 구현 — BOT_TOKEN/CHAT_ID 동일 env, 4000자 트렁케이션.
- `alert()` (line 39-43): "⚠️ 제목" 형식.
- 호출처: **`shared/validators.py:721` 단 1곳** (`from shared.notify import alert` — validate_post_extended의
  발행 전 검증 알림). dispatcher/scheduler/pipelines는 전부 telegram_notifier 사용.
- **판정: 중복 코드 (duplicate).** 유일 호출처의 메시지가 Telegram에 실제 전송되는 경로이므로 제거는 금지,
  `telegram_notifier.send` 기반으로 교체 권장 (플래그: `[DUPLICATE] shared/notify.py — telegram_notifier와 동일 역할, 활성 호출 validators.py:721 단 1곳`).

**`shared/monitor.py`** (65줄) — telegram_notifier의 하위 호환 래퍼 (send_telegram, send_daily_report), 일일 리포트 + cooldown 현황.

### 3.2 임계값 계층

**`shared/alert_thresholds.py`** (155줄) `[VERIFIED: codebase]`
- `DEFAULT_ALERT_CONFIG` (line 13-20): consecutive_failures=3, daily_failure_rate=0.5, keyword_fail_streak=5,
  cooldown_minutes=60, enabled=True, dry_run=False.
- `BLOG_OVERRIDES` (line 24-28): pet-hugo=2, fitness-hugo=5, health-hugo=5.
- `ThresholdChecker` (line 31-155): `maybe_alert(blog_id, reason, context)` — 연속 횟수 확인(line 118-126) →
  쿨다운 확인(line 128-137) → dry_run이면 log만(line 147-149) → 아니면 `send_error` 호출(line 150-153).
  **메시지는 범용 템플릿 "[임계값 초과] blog: reason (연속 N회) (ctx=...)"** — 문제별 템플릿 없음.
- 사용처: curation/pipeline.py:862-865, scheduler.py:753-757.

**dispatcher 자체 임계값** `[VERIFIED: codebase]`
- `_ESCALATION_THRESHOLD = 3` (dispatcher.py:92), `_COOLDOWN_MINUTES = 30` (line 88), `data/failure_count.json` (line 91).
- no_result/no_content만 연속 카운트 (line 706-719). **similar_title 등 다른 reason은 카운트되지 않음.**

**curation 자체 임계값** `[VERIFIED: codebase]`
- `_consecutive_failures` (pipeline.py:143) + `_alert_checker.maybe_alert` (line 862-865).
- `_record_failure`에서 keyword_health의 `consecutive_failures >= 3` 시 알림 (line 722-739).

### 3.3 현재 흐름 요약 (문제 → 사용자)

```
문제 발생 → pipeline 결과 dict → dispatcher.py:672-741 정규화
  ├─ no_result/no_content/no_data/fetch_error → _tg_error(blog_id, reason, "pipeline {reason}: 발행 가능 데이터 없음 (연속 N회)")   ← 원인 미구분
  ├─ deploy_error (STAP만) → _tg_error(blog_id, "deploy", "...")
  ├─ duplicate_slug/source_id → _tg_error(blog_id, reason, "중복 발행 방지 — ...")
  └─ 그 외 (similar_title, title_blocked 등) → _record_failure만, 알림 없음
  → send_error() 단일 템플릿 → Telegram
```

### 3.4 "정확한 문제 알림"에 누락된 것 (Gap 분석)

| Gap | 현재 상태 | 필요한 것 |
|-----|-----------|-----------|
| G1 구조화된 문제 분류 체계 부재 | raw reason 문자열 (`no_result`, `deploy`...)이 stage로 사용 | `PROBLEM_REGISTRY` (problem_id → 메타데이터) |
| G2 문제별 알림 템플릿 부재 | "🚨 발행 오류" 단일 템플릿 (telegram_notifier.py:73-81) | 문제별 한국어 템플릿 (`send_problem_alert`) |
| G3 발행 시도 횟수 컨텍스트 부재 | no_result만 "(연속 N회)" 포함 (dispatcher.py:715), 나머지 없음 | 실패 카운터(failure_count.json)를 모든 문제에 적용 |
| G4 침묵 문제 다수 | P03, P04(ETAP/Workers), P05, P06, P07, P08, P09, P22 침묵 | 탐지 훅 + 알림 정책 |
| G5 알림 경로 중복 | 단일 실패에 최대 4개 경로 (curation record_failure, curation run, dispatcher, maybe_alert) | 모니터 단일 진입점 + 쿨다운 통합 |
| G6 성공 컨텍스트 부재 | "발행 성공 후 배포 실패" (dispatcher.py:693)는 success=True + deploy_error로 표현 | 결과 dict에 phase 정보 포함 |

---

## 4. 권장 아키텍처 (Recommended Architecture)

### 4.1 구성 요소 (모두 신규 파일 — 기존 코드는 보존, 증분 연결)

```
shared/problem_registry.py    — PROBLEM_REGISTRY: dict[str, ProblemSpec]
shared/problem_detectors.py   — 순수 탐지 함수 (side-effect 없음, 단위 테스트 대상)
shared/problem_monitor.py     — PublishMonitor (report/detect/send_problem_alert, dry-run)
```

**ProblemSpec (dataclass)** — `shared/problem_registry.py`

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ProblemSpec:
    problem_id: str            # e.g. "P01_no_result"
    name_ko: str               # e.g. "발행 데이터 없음 (no_result)"
    severity: str              # "CRITICAL" | "MAJOR" | "MINOR"
    reason_keys: tuple         # 결과 dict reason 매칭 키 ("no_result", ...)
    hook: str                  # "result_parse" | "post_generate" | "post_validate" | "post_publish" | "post_deploy"
    detect_fn: str = ""        # problem_detectors 내 함수명 (옵션)
    alert_template: str        # 한국어 템플릿 (str.format)
    threshold: str             # "always" | "consecutive:3" | "daily_rate:0.5" | "quiet"
    cooldown_minutes: int = 60
```

**`shared/problem_monitor.py` — PublishMonitor**

```python
class PublishMonitor:
    """발행 결과 단일 진입점 — PROBLEM_REGISTRY 기반 탐지 + 임계값 + 알림"""

    def __init__(self, checker: ThresholdChecker | None = None,
                 dry_run: bool | None = None): ...   # dry_run: env PROBLEM_ALERT_DRY_RUN 우선

    def report(self, blog_id: str, result: dict, phase: str = "result_parse",
               extra: dict | None = None) -> list[str]:
        """1) 결과 dict → reason 매핑 → problem_id 후보 탐지
           2) threshold 정책 판정 (CRITICAL=always, MAJOR=consecutive/daily_rate)
           3) 쿨다운 확인 (ThresholdChecker 재사용)
           4) send_problem_alert() 호출
           반환: 발송된 problem_id 목록 (dry-run이면 발송 예정 목록)"""

    def send_problem_alert(self, problem_id: str, blog_id: str,
                           context: dict) -> str | None:
        """템플릿 렌더 + domain/repo/연속횟수 컨텍스트 주입 + telegram_notifier.send()
           반환: 렌더된 메시지 (dry_run이면 log만, 발송 안 함)"""

    def detect(self, hook: str, content: str, blog_id: str) -> list[Detection]:
        """post_generate/post_validate 훅용 — problem_detectors를 순회해
           raw 콘텐츠에서 P07/P08/P09 시그니처 탐지 (sanitize 이전 호출 필수)"""
```

**`shared/problem_detectors.py`** — 순수 함수만 (신규 모듈)

```python
# P07 CJK — validators.has_cjk/is_korean_content 래핑 (오탐 방지: 한글 비율 0.5 기준)
def detect_cjk_leak(title: str, body: str, blog_id: str) -> Detection | None
# P08 CoT/사고과정 — ai_response_parser._check_multilingual_leak 래핑 + curation _is_cot_body 임계값
def detect_cot_leak(raw_body: str, blog_id: str) -> Detection | None
# P09 URL 토큰 반복 — _has_repeated_pattern 로직 단일화 (3중 복제 제거, fixer는 유지)
def detect_image_url_repeat(body_md: str) -> list[Detection]
# P06 featureimage 404 — frontmatter featureimage URL 1회 HTTP HEAD (post-publish 훅, 발행 직후 1회만)
def detect_broken_featureimage(site_path: str, slug: str) -> Detection | None
# P15 검증 이슈 → problem_id 매핑 (post_validator issue dict 기반)
def classify_validation_issue(issue: dict) -> tuple[str, ...]
```

### 4.2 임계값 정책 (심각도별)

| 심각도 | 정책 | 근거 |
|--------|------|------|
| **CRITICAL** (P04, P05, P06, P07, P08, P09) | **always alert** — 쿨다운 60분만 적용 | 콘텐츠 오염(CJK/CoT)과 배포 실패는 1회라도 즉시 인지 필요; 쿨다운으로 반복 스팸만 방지 |
| **MAJOR** (P01, P02, P03, P10-P14, P20-P22) | **consecutive:3** (기존 `_ESCALATION_THRESHOLD`/ThresholdChecker 기본과 일치) + daily_rate:0.5 | 발행 불가는 빈도 기반 판단 — 단발 실패는 로그로 충분, 연속 3회 이상이면 개입 필요 |
| **MINOR** (P16-P19, P23, P24) | **quiet** — 로그/통계만, 알림 없음 | 일상적 제어 흐름(quota, 중복, stale)은 노이즈 |

- 연속 카운터 재사용: `data/failure_count.json` (dispatcher.py:91, :150-164) — **전 reason 공용으로 확장**.
  P03 similar_title도 카운트에 포함 (현재 제외 — dispatcher.py:703-706).
- 쿨다운: `ThresholdChecker._in_cooldown/_mark_alerted` 재사용 (alert_thresholds.py:80-91).
- 발행 성공 시 카운터 리셋: dispatcher.py:690 `_reset_failure_count` 그대로.

### 4.3 알림 템플릿 예시 (`send_problem_alert` 렌더 결과)

```
🚨 [CRITICAL] 콘텐츠 오염 — LLM/CoT 누수 감지
블로그: health-hugo
문제: P08_llm_cot_leak — 사고과정/프롬프트 지시문이 본문에 노출됨
감지 단계: content_generation
감지 패턴: thinking_leak — "Let me re-read"
연속 실패: 1회 (이번 발행 시도)
조치: 생성 직후 raw 콘텐츠 검증 → 재생성. scan_multilingual_leak.py로 확인.
```

```
⚠️ [MAJOR] 발행 불가 — 유사 제목 중복
블로그: appliance-hugo
문제: P03_similar_title — 제목 유사도 80% 초과 (3회 fallback 소진)
감지 단계: result_parse
연속 실패: 3회 (오늘 2번째 발행 시도)
조치: 키워드별 제목 변형 다양화 또는 유사도 임계값 조정 검토.
```

### 4.4 통합 지점 (additive, non-destructive)

| 통합 지점 | 현재 코드 | 변경 (추가만) |
|-----------|-----------|---------------|
| dispatcher 결과 파싱 | dispatcher.py:687-740 (`_tg_error` 블록) | `monitor.report(blog_id, result)` 호출 추가. **기존 `_tg_error` 호출은 유지** (중복 방지를 위해 monitor가 발송 시 기존 블록은 dry-run 환경변수로 off 가능 — 기본은 둘 다 유지, Phase 59에서 단일화) |
| dispatcher 배포 결과 | dispatcher.py:691-692 (`_build_and_deploy_central` 반환 무시) | 반환값 캡처 → False면 `monitor.report(blog_id, {"success": True, "deploy_error": "..."})` → P04/P05 알림 (침묵 해소, **동작 변경 없이 반환값 사용만 추가**) |
| curation run() | pipeline.py:850-865 | `monitor.report(blog_id, result)` 추가. reason 제외 목록(pipeline.py:856)에 P03 추가해 **기존 알림 중복 제거** (또는 monitor가 쿨다운으로 흡수) |
| post-generate 훅 | curation/writer.py `generate_curation_article` / ai_writer.py:433-451 | raw 콘텐츠에서 `monitor.detect("post_generate", raw)` — **sanitize 이전** (BUG-54-001 교훈) → P07/P08/P09 탐지 → CRITICAL 즉시 알림 (파이프라인 흐름은 변경하지 않음 — 탐지+알림만 추가) |
| post-publish 검증 | publisher.py:836-855 `_run_validation` | `classify_validation_issue()` 매핑 → P15/P06 알림. `send_validation()` 죽은 코드 대체 |
| scheduler 연속 실패 | scheduler.py:734-758 `_track_publish_result` | 유지 (이미 임계값+maybe_alert) — monitor와 쿨다운 공유만 확인 |

### 4.5 Don't Hand-Roll / 재사용 원칙

- **이미지 URL 반복 탐지**: `_has_repeated_pattern`을 새로 작성하지 말고 `shared/problem_detectors.py`로
  **단일화** (hugo_writer.py:26-39 / curation/writer.py:181 / fix_repeated_image_urls.py:68-83의 3중 복제 제거).
  단, "기존 기능 보존" 원칙상 기존 3곳의 수정은 Phase 59(리팩터링)로 이연 가능 — 이번 Phase는
  shared 함수 신규 + 호출만 추가.
- **CJK 탐지**: `validators.has_cjk`가 이미 단일 소스 (b0bb7dbb6 커밋으로 정립) — 새 정규식 금지.
- **Telegram 전송**: `telegram_notifier.send` 재사용 — 새 HTTP 클라이언트 금지. `notify.py` 교체는 이연.
- **임계값/쿨다운**: `ThresholdChecker` 재사용 — 새 쿨다운 구현 금지.

---

## 5. 검증 방법 (Verification Approach)

### 5.1 테스트 인프라 (기존) `[VERIFIED: codebase]`

- 프레임워크: **pytest 9.1.1** (`.venv` — Python 3.11.15, launchd 실행 환경과 동일).
- 설정: `pyproject.toml:5-6` — `testpaths=["tests"]`, `python_files=["test_*.py"]`; `addopts`에 coverage
  (`--cov=shared,pipelines/curation`). ruff lint (py314 대상) 포함.
- 기존 테스트 패턴: `tests/curation/test_alert_thresholds.py` (mock patch + caplog로 dry-run 검증),
  `tests/shared/test_telegram_notifier.py` (`patch("shared.telegram_notifier.BOT_TOKEN", "")` 등).
- 실행: `.venv/bin/python -m pytest tests/...` (Python 3.14 시스템 python도 가능 — pycache에 cpython-314 존재).

### 5.2 신규 테스트 계획

| 테스트 파일 | 검증 내용 |
|-------------|-----------|
| `tests/shared/test_problem_registry.py` | (1) reason→problem_id 매핑 완전성: dispatcher가 내보낼 수 있는 모든 reason(`no_result`, `no_content`, `similar_title`, `title_blocked`, `deploy_error`...)이 레지스트리에 존재. (2) 템플릿에 필수 필드(blog_id, 문제명) 포함 |
| `tests/shared/test_problem_detectors.py` | (1) P07: 샘플 중국어 제목/본문 주입 → `has_cjk` 감지; heritage 한자 병기 샘플 → **오탐 없음** (한글 비율 0.5 기준 확인). (2) P08: `_check_multilingual_leak` 패턴별 샘플(ko/en thinking, `<thinking>`, 프롬프트 지시문). (3) P09: `gLozv0gLozv0gLozv0gLozv0...` URL 주입 → 감지, 정상 URL → 미감지. (4) P15: post_validator issue dict → problem_id 분류 |
| `tests/shared/test_problem_monitor.py` | (1) CRITICAL은 항상 알림. (2) MAJOR는 consecutive 3 미만이면 미발송 (mock send). (3) 쿨다운 내 중복 발송 차단 (ThresholdChecker 재사용 확인). (4) dry_run=True면 `send()` 미호출 + 로그 기록 (test_alert_thresholds.py:71-81 패턴). (5) 발송 메시지에 연속 횟수 포함 |
| `tests/curation/test_problem_monitor_integration.py` | curation `run()` 흐름에서 P03(similar_title)이 기존에는 침묵이었으나 monitor 연결 후 알림됨 — mock `send`로 검증. **기존 `_tg_error` 호출도 유지되므로 기존 테스트 `test_pipeline.py` 회귀 없음 확인** |

### 5.3 dry-run 모드

- `PROBLEM_ALERT_DRY_RUN=1` 환경변수 → `PublishMonitor`가 `send()` 대신 `logger.info("[PROBLEM-ALERT DRY-RUN] ...")`.
- `alert_thresholds.DEFAULT_ALERT_CONFIG["dry_run"]`과 정책 분리 (monitor 자체 플래그 우선).

### 5.4 회귀 방지 (기존 기능 보존)

- 기존 `_tg_error` 호출 경로(dispatcher.py:709, 715, 718, 723, 697 / curation pipeline.py:857)는 **변경하지 않음** —
  monitor는 병렬로 추가. 중복 알림은 monitor의 쿨다운(60분)이 흡수.
- 기존 테스트 전부 green 유지가 Phase 게이트: `tests/curation/test_pipeline.py`, `tests/shared/test_telegram_notifier.py`,
  `tests/curation/test_alert_thresholds.py` 회귀 0건.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Telegram 전송 | 새 HTTP 클라이언트 | `shared/telegram_notifier.send()` | 이미 env 로드·에러 처리·500자 제한 구현됨 (telegram_notifier.py:13-33) |
| 연속 실패 임계값/쿨다운 | 새 쿨다운 구현 | `ThresholdChecker` (alert_thresholds.py:31-155) | per-blog override, dry_run, 쿨다운 60분 기존 구현 |
| CJK 탐지 정규식 | 새 정규식 | `validators.has_cjk` (validators.py:20-32) | 단일 소스로 정립됨 (b0bb7dbb6) — 새 패턴은 오탐 유발 |
| 이미지 URL 반복 탐지 | 새 탐지 함수 | `_has_repeated_pattern` 로직 (hugo_writer.py:26-39) 단일화 | 3중 복제 상태 — 4번째 복제 금지, shared로 추출 |
| 발행 후 검증 | 새 검증기 | `validate_post_html` (post_validator.py:92-180) | issue dict 구조화 이미 완료 — 매핑만 추가 |
| no_result 카운터 | 새 카운터 파일 | `data/failure_count.json` (dispatcher.py:91, 150-164) | 기존 파일·함수 재사용, reason 확장만 |

**Key insight:** 이 프로젝트의 탐지 로직은 대부분 **이미 존재**한다 (validators, ai_response_parser,
post_validator, URL-REPEAT, scan_multilingual_leak). 부족한 것은 탐지가 아니라 **분류·템플릿·정책·단일 진입점**이다.
새 탐지기를 만드는 대신 기존 시그니처를 PROBLEM_REGISTRY에 등록하고 모니터에 연결하는 것이 핵심.

---

## Common Pitfalls

### Pitfall 1: 알림 경로 중복 (4중 전송)
**What goes wrong:** 단일 실패가 curation `_record_failure`(pipeline.py:734-739) + curation `run()`(pipeline.py:857) +
dispatcher(pipeline.py:715) + `maybe_alert`(쿨다운 60분)에서 각각 Telegram 전송 → 사용자에게 중복 메시지 4건.
**Why:** 각 계층이 독립적으로 알림 정책을 구현, 공유 쿨다운 없음.
**How to avoid:** PublishMonitor가 단일 진입점 + ThresholdChecker 쿨다운 공유. Phase 59에서 기존 경로 제거.
**Warning signs:** 같은 실패에 Telegram 메시지 2건 이상 수신.

### Pitfall 2: sanitize 이후 탐지 (BUG-54-001 재발)
**What goes wrong:** CoT 마커가 sanitize에서 제거된 뒤 탐지하면 항상 0건 → 오염 콘텐츠 발행.
**Why:** `_sanitize_body()`가 검증 대상 마커를 먼저 삭제 (triage/BUG-54-001-cot-body-detection-not-called.md:44-45).
**How to avoid:** post-generate 훅은 반드시 **raw 콘텐츠**에서 실행 (pipeline.py:761-833의 `_content_quality_gate`도
sanitize 이전 raw 기준으로 동작 중 — 같은 원칙).
**Warning signs:** `has_thinking_leak=False`인데 발행 글에 사고과정 문구 존재.

### Pitfall 3: CJK 오탐 (heritage 한자 병기)
**What goes wrong:** `cjk_line_leak`(한 줄 3자 이상 한자)이 문화유산 블로그에서 86건 전부 오탐
(travel2_investigation.md) → 알림 폭주.
**Why:** 한자 병기("갑사(甲寺)")는 정상 콘텐츠.
**How to avoid:** P07 탐지는 단순 한자 존재가 아닌 **한글 비율 0.5 미만**(validators.py:186-197) + 지시문성
중국어 키워드(ai_response_parser.py:40-43) 기준으로만 알림.
**Warning signs:** 특정 블로그(travel2)에서만 CJK 알림 다발.

### Pitfall 4: import 시점 env 로드
**What goes wrong:** `telegram_notifier.BOT_TOKEN`은 import 시점 `os.getenv` (telegram_notifier.py:8-10) →
env 로드 전 import면 영구 빈 토큰.
**Why:** dotenv 로드 순서와 import 순서 의존.
**How to avoid:** 신규 모듈은 `load_dotenv` 이후 lazy import (기존 dispatcher.py:25-31 패턴 유지).
**Warning signs:** 로그에 "Telegram credentials missing" 반복.

### Pitfall 5: `_build_and_deploy_central` 반환값 무시
**What goes wrong:** ETAP/Workers 블로그 배포 실패가 침묵 (dispatcher.py:691-692).
**Why:** 반환 bool을 result에 병합하지 않음.
**How to avoid:** 반환값 캡처 → False면 `deploy_error` 컨텍스트로 monitor.report — **호출 시그니처 변경 없음**.
**Warning signs:** 발행 성공(success=True)인데 라이브 사이트 미반영.

### Pitfall 6: `notify.py`를 삭제 대상으로 오인
**What goes wrong:** "notify.py 미사용" 판정 후 삭제 → `validate_post_extended`의 발행 전 검증 알림(validators.py:721)이 끊김.
**Why:** grep이 dispatcher/scheduler 중심이라 유일 호출처(validators.py:721)를 놓침.
**How to avoid:** 이 Phase에서 notify.py는 **교체 대상(이연)** 이지 삭제 대상이 아님. telegram_notifier로 경유 교체는 Phase 59.
**Warning signs:** [Validate] 알림 수신 중단.

---

## Code Examples

### 예 1: PublishMonitor.report — 결과 dict 분류 + 정책 판정
```python
# Source: [VERIFIED: codebase 패턴 — dispatcher.py:687-740, alert_thresholds.py:93-155]
# 신규 shared/problem_monitor.py (설계 스케치)
def report(self, blog_id: str, result: dict, phase: str = "result_parse",
           extra: dict | None = None) -> list[str]:
    sent: list[str] = []
    reason = (result or {}).get("reason", "unknown")
    spec = PROBLEM_REGISTRY.lookup(reason) or PROBLEM_REGISTRY.lookup("unknown_failure")
    if spec is None or spec.threshold == "quiet":
        return sent
    consecutive = self._counters.get(blog_id, 0)   # data/failure_count.json 래퍼
    if spec.severity == "CRITICAL":
        pass                                        # always alert
    elif spec.threshold.startswith("consecutive:"):
        n = int(spec.threshold.split(":")[1])
        if consecutive < n:
            return sent
    if self._checker._in_cooldown(blog_id):
        return sent
    self._checker._mark_alerted(blog_id)
    msg = spec.render(blog_id=blog_id, consecutive=consecutive,
                      phase=phase, **extra or {})
    if self.dry_run:
        logger.info(f"[PROBLEM-ALERT DRY-RUN] {blog_id} {spec.problem_id}: {msg[:120]}")
    else:
        from shared.telegram_notifier import send
        send(msg)
    sent.append(spec.problem_id)
    return sent
```

### 예 2: post-generate 훅 — sanitize 이전 raw 탐지
```python
# Source: [VERIFIED: codebase 패턴 — BUG-54-001 교훈, ai_response_parser.py:65-82]
# pipelines/curation/writer.py 내부, generate_curation_article()의 raw 응답 직후 (기존 _is_cot_body 호출 지점)
raw = llm_response          # sanitize 이전 원본
from shared.problem_monitor import get_monitor
detections = get_monitor().detect("post_generate", raw, blog_id)
for d in detections:        # P07/P08/P09 — CRITICAL 즉시 알림
    get_monitor().send_problem_alert(d.problem_id, blog_id,
        {"pattern": d.pattern, "matched": d.matched[:80], "attempt": attempt})
# 이후 기존 _is_cot_body()/_sanitize_body() 흐름은 변경 없음
```

### 예 3: dispatcher 통합 — 배포 실패 반환값 병합 (additive)
```python
# Source: [VERIFIED: codebase — dispatcher.py:691-692 현재 반환값 무시]
if blog_id in ETAP_PIPELINE_BLOGS or blog_id in WORKERS_BLOGS:
    _deploy_ok = _build_and_deploy_central(blog_id)      # ← 기존: 반환값 무시
    if not _deploy_ok:                                   # ← 추가 (동작 보존)
        from shared.problem_monitor import get_monitor
        get_monitor().report(blog_id,
            {"success": True, "deploy_error": "ETAP/Workers 배포 실패",
             "reason": "deploy_error"}, phase="post_deploy")
```

### 예 4: dry-run 테스트 패턴 (기존 test_alert_thresholds.py:71-81 재사용)
```python
# Source: [VERIFIED: codebase — tests/curation/test_alert_thresholds.py]
def test_maybe_alert_returns_message_when_passed_and_not_in_cooldown(caplog):
    checker = ThresholdChecker(blog_config={"blog1": {"dry_run": True}})
    msg = checker.maybe_alert("blog1", "test_reason", {"cnt": 3})
    assert msg is not None
    assert any("DRY-RUN" in rec.message for rec in caplog.records)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| raw reason 문자열 알림 (stage=reason) | 구조화된 문제 분류 + 문제별 템플릿 | Phase 58 (제안) | 사용자가 문제 원인을 즉시 식별 가능 |
| CJK sanitize(치환) 방식 | 감지+플래그(원본 보존), writer 4관문 | b8ff211df (2026-08) | 오염 원본 보존 → 탐지 가능 |
| CoT body 검증이 sanitize 이후 | sanitize 이전 raw 검증 | BUG-54-001 (2026-08-02) | CoT 누수 차단 실효 |
| 이미지 URL 반복: 자동 수정 + log | 자동 수정 + log + CRITICAL 알림 | Phase 58 (제안) | 수익 직결 콘텐츠 오염 인지 |
| `llm_trace` JSONL 기록만 (폴백 실패) | 폴백 전체 실패 시 MAJOR 알림 | Phase 58 (제안) | 무료 모델 체인 전체 실패 감지 |

**Deprecated/outdated:**
- `send_validation()` / `send_no_result_alert()`: 정의만 있고 호출처 0건 — 신규 모니터가 대체하되 삭제는 Phase 59.
- `shared/notify.py`: telegram_notifier와 중복 — 활성 호출 validators.py:721 1곳, 교체는 Phase 59.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `dispatcher.py:715`의 "연속 N회" 카운터(failure_count.json)가 발행 시도 횟수 컨텍스트의 유일 소스로 재사용 가능 | 3.4 / 4.2 | 다른 파이프라인(curation)은 자체 `_consecutive_failures`(pipeline.py:143) 사용 — 두 카운터 불일치 시 "연속 N회"가 블로그별 최신값이 아닐 수 있음. planner는 monitor가 **dispatcher 카운터를 우선** 사용하도록 지정 필요 |
| A2 | `P04/P05`를 ETAP/Workers에서 잡으려면 `_build_and_deploy_central` 반환값 병합이 충분 | 4.4 | Pages 경로(CAP/TAP)는 `publish()` → `deploy_site()` 예외가 파이프라인 결과에 어떻게 반영되는지 아직 미확인 — planner는 Pages 경로 deploy_error 전파 경로를 Phase 58에서 **검증 태스크로 추가**할 것 |
| A3 | heritage 블로그에서 CJK 오탐 방지를 위해 한글 비율 0.5 기준이면 충분 | 2.1 / Pitfall 3 | 0.5 미만이지만 정상인 콘텐츠(영어 travel 블로그 등) 존재 가능 — 블로그 언어별(한글/영문) 비율 기준 분기가 필요할 수 있음 |
| A4 | Python 3.14 시스템 python으로도 테스트 가능 (pycache cpython-314 존재) | 5.1 | 실제 CI/launchd는 .venv(3.11) 사용 — 테스트 명령은 `.venv/bin/python -m pytest` 고정 권장 |
| A5 | `PROBLEM_ALERT_DRY_RUN` env 방식이 alert_thresholds의 dry_run 정책과 충돌하지 않음 | 5.3 | monitor 자체 플래그 우선으로 설계 — 기존 `DEFAULT_ALERT_CONFIG["dry_run"]`과 독립 |

---

## Open Questions

1. **Pages 블로그의 deploy_error 전파 경로**
   - What we know: STAP은 `result["deploy_error"]`로 반환 (stock/pipeline.py:427-428), ETAP/Workers는 반환값 무시 (dispatcher.py:691-692).
   - What's unclear: CAP(compare 등)·TAP(travel 등) Pages 블로그에서 `publisher.publish()` 내부 `deploy_site()` 예외가
     결과 dict의 어느 키로 나가는지 미확인.
   - Recommendation: Phase 58 태스크 1개로 grep(`deploy_error` 발생 지점 전수) 후 레지스트리에 등록.

2. **similar_title 카운터 포함 여부**
   - What we know: dispatcher.py:703-706에서 similar_title은 알림 목록 제외 — 카운터에도 미포함.
   - What's unclear: 연속 similar_title 3회를 MAJOR 알림으로 올릴지, 아니면 1회로도 알림할지(사용자 판단).
   - Recommendation: 기본값 consecutive:3 (다른 MAJOR와 동일) — discuss-phase에서 확정.

3. **CRITICAL 알림의 쿨다운 60분이 적절한가**
   - What we know: ThresholdChecker 쿨다운 기본 60분 (alert_thresholds.py:17).
   - What's unclear: 동일 문제가 30분 주기로 반복(예: travel2 시군구 가드)될 때 60분 쿨다운이면 하루 최대
     수 회만 알림 — 충분한가.
   - Recommendation: 쿨다운 유지, 단 `P08/P09`(콘텐츠 오염)는 쿨다운 없이 **건별 알림** 옵션을 discuss-phase에 상정.

4. **`notify.py` 교체 시점**
   - What we know: 활성 호출 validators.py:721 1곳, telegram_notifier와 중복.
   - What's unclear: 이 Phase에서 교체할지 Phase 59로 이연할지.
   - Recommendation: **이연** (Phase 58은 문제 알림에 집중) — RESEARCH의 Flag로만 기록.

---

## Environment Availability

> Phase 58은 신규 외부 의존성 없음 (전부 기존 코드 + Python 표준 라이브러리). 텔레그램 API만 네트워크 의존.

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| pytest | 단위 테스트 | ✓ | 9.1.1 (`.venv`) | 시스템 python3 (3.14.6) |
| Python | 실행 | ✓ | .venv 3.11.15 (launchd 일치) / 시스템 3.14.6 | — |
| Telegram API | 알림 전송 | ✓ (네트워크) | — | dry_run 모드로 발송 차단 |
| TELEGRAM_BOT_TOKEN / CHAT_ID | 알림 전송 | ✓ | ~/.env.common 2개 항목 확인 | 미설정 시 send()가 False 반환 (telegram_notifier.py:14-16) |
| ~/.env.common | env 로드 | ✓ | — | dispatcher.py:25, scheduler.py:23 |
| data/failure_count.json | 연속 실패 카운터 | ✓ (기존) | — | 없으면 {} (dispatcher.py:142-147) |
| logs/deploy.log | 배포 실패 진단 | ✓ | — | — |

**Missing dependencies with no fallback:** 없음.

---

## Security Domain

> `security_enforcement`이 config.json에 명시되지 않아 활성으로 간주. 이 Phase의 보안 표면은 최소.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (텔레그램 봇 토큰은 서버 env, 코드에 미노출) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | 기존 시그니처 재사용 (`validators.has_cjk`, `ai_response_parser.THINKING_PATTERNS`); **새 정규식은 기존 단일 소스에 통합** — ad-hoc regex 금지 |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 봇 토큰/채팅 ID 누출 (알림 템플릿에 env 노출) | Information Disclosure | 템플릿은 blog_id/문제명/패턴만 렌더, 토큰·full URL 미포함; `send_error`의 500자 트렁케이션 유지 |
| dry_run 미적용으로 테스트 중 실전 발송 | — | `PROBLEM_ALERT_DRY_RUN=1` env 강제 + 테스트는 `patch("shared.telegram_notifier.send")` 필수 (test_telegram_notifier.py 패턴) |
| 알림 폭주 (알림 채널 DoS) | DoS | CRITICAL도 쿨다운 60분, MAJOR는 consecutive 임계값 — ThresholdChecker 재사용 |

---

## Sources

### Primary (HIGH confidence — 코드베이스 직접 검증 `[VERIFIED: codebase]`)
- `dispatcher.py` — 결과 정규화 :672-741, no_result/no_content 알림 :706-719, deploy :691-700, failure_count :91/142-164, _build_and_deploy_central :541-621, _run_stap :325-384
- `shared/telegram_notifier.py` — send :13-33, send_error :36-81 (단일 템플릿, _SILENT_REASONS :38-43), send_validation :88-104 (dead), send_no_result_alert :107-113 (dead)
- `shared/notify.py` — 중복 구현 확인 (활성 호출 validators.py:721 단 1곳)
- `shared/alert_thresholds.py` — ThresholdChecker :31-155, DEFAULT_ALERT_CONFIG :13-20, BLOG_OVERRIDES :24-28
- `shared/validators.py` — has_cjk :20-32, assert_korean_or_reject :200-209, validate_post :313-399, validate_post_extended :692-760 (notify.alert 호출 :721, body_md NameError :744-758, 죽은 코드 :211-232)
- `shared/ai_response_parser.py` — THINKING_PATTERNS :15-49, _check_multilingual_leak :65-82, parse_ai_response :256-319
- `shared/post_validator.py` — validate_post_html :92-180, CTA/빈 템플릿/og:image/min_length/readability/keyword_coverage
- `shared/publishers/hugo_writer.py` — _fix_repeated_image_urls :14-55 (URL-REPEAT :48), IMAGE-GUARD :354-366, sanitize_featureimage_url :636-642
- `shared/publishers/deploy.py` — _run_hugo_build :22-36, deploy 실패 raise :106-107, :167-168, CLOUDFLARE_API_TOKEN 제거 :78
- `shared/publisher.py` — _run_validation :836-855, publish :861+, duplicate_slug/source_id :877-901
- `shared/content_store.py` — title_similar_exists :231-260
- `shared/monitor.py` — telegram_notifier 래퍼 (일일 리포트 + cooldown 현황)
- `shared/ai_writer.py` — generate 폴백 체인 :123-315, RuntimeError :315, leak 승격 :439
- `pipelines/curation/pipeline.py` — 패턴 상수 :29-43, _alert_checker :142-143, _record_failure :707-739, _title_gate :742-758, _content_quality_gate :761-833, run() 알림 :850-865, similar_title :1104-1128
- `pipelines/curation/writer.py` — _TITLE_TEMPLATE_PATTERNS :508-517, _regenerate_title :561-597, _is_cot_body :606-648, _fix_repeated_image_urls :169-216
- `pipelines/travel/pipeline.py` — _travel_sigungu_recently_published :99-146, 가드 체인 :216-283, validate→draft :323-338
- `pipelines/stock/pipeline.py` — no_content :269, deploy tg_error :427-428
- `scheduler.py` — dispatcher subprocess :245-290, _track_publish_result :734-758, env 로드 :23-24
- `scripts/scan_multilingual_leak.py` — 10패턴 :15-71, 스캔 로직 :74-202
- `scripts/phase5_verify.py` — SCAN_PATTERNS :60-85, scan_content :88-114
- `scripts/fix_repeated_image_urls.py` — has_repeated_pattern :68-83
- `scripts/batch_thumbnails.py` — frontmatter 읽기 :97-136
- `tests/curation/test_alert_thresholds.py`, `tests/shared/test_telegram_notifier.py` — 테스트 패턴
- `.planning/triage/BUG-54-001-cot-body-detection-not-called.md` — sanitize 이전 검증 교훈
- `.planning/triage/20260802--bug-title-templates-created-at-missing.md` — title_templates schema 버그 (이연)
- `.planning/triage/20260805--fix-stap-finance-hugo-db-diversity-and-publish.md` — deploy 인증 오류 파생 이슈
- `.planning/quick/20260805-llm-leak-all-blogs/` — PLAN.md (시그니처 확장), audit_reconciliation.md (169건 탐지, CJK 오탐 116), travel2_investigation.md (한자 병기 오탐 86건)
- `AGENTS.md` — Pipeline Error Pattern Reference (5개 incident), CLOUDFLARE_API_TOKEN 규칙, 배포 규칙
- `pyproject.toml` — pytest 설정 :5-6, ruff

### Secondary (MEDIUM confidence)
- Git log `ddd9d2fb2`, `b8ff211df`, `b0bb7dbb6` — llm_trace/ CJK 단일소스/제목 4관문 커밋 메시지로 동작 의도 확인

### Tertiary (LOW confidence)
- 없음 — 본 리서치는 전원 로컬 코드베이스 검증

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 신규 외부 패키지 없음, 전원 기존 shared/ 재사용 (파일:라인 검증)
- Architecture: HIGH — 탐지 로직·알림 경로 전부 코드베이스에서 직접 확인
- Pitfalls: HIGH — incident 문서(AGENTS.md, BUG-54-001, travel2_investigation) 기반

**Research date:** 2026-08-06
**Valid until:** 2026-09-05 (코드베이스 안정, 30일)

---

## 잔존 위험 (Residual Risks)

1. **[검증불가] Pages 블로그(CAP/TAP)의 deploy_error 전파 경로 미확인** — `publisher.publish()` 내부
   `deploy_site()` 예외가 결과 dict의 어느 키로 나가는지 grep으로 확인하지 못함. Phase 58 계획에
   "deploy_error 발생 지점 전수 grep" 태스크를 포함할 것. 복구: 해당 경로가 확인되면 레지스트리에 P04/P05로 등록.

2. **[부분검증] A1 카운터 불일치** — dispatcher(failure_count.json)와 curation(메모리 `_consecutive_failures`)의
   연속 실패 카운터가 별개. "연속 N회" 메시지가 블로그별 최신값을 보장하지 않을 수 있음. 복구:
   monitor가 dispatcher 카운터 우선 사용을 계획에 명시.

3. **[검증불가] `validate_post_extended`의 `body_md` NameError (validators.py:750)** — senior+coupang 분기에서
   `body_md`가 미정의. try/except로 삼켜지지만 해당 검증이 조용히 누락됨. 본 Phase 범위 밖(수정 금지) —
   잔존 위험으로 기록하고 Phase 59 리팩터링 대상으로 이연. 복구: 해당 라인 접근 시 `html_content`로 치환.

4. **[부분검증] `_SILENT_REASONS` 문자열 매칭의 오탐** — `send_error`의 침묵 판정이 substring 매칭
   (telegram_notifier.py:44-45). "quota"가 포함된 다른 에러 메시지도 침묵될 수 있음. 기존 동작이므로
   이 Phase에서 변경하지 않음 — 모니터 도입 후 재검토 대상.

5. **[검증불가] STAP/TAP subprocess 환경에서 알림 누락 가능성** — STAP 파이프라인 자체의 실패(스크립트
   크래시, JSON 미출력)는 dispatcher가 `stap_subprocess_error`/`stap_no_output`으로 잡지만, STAP 내부에서
   자체 발송하는 tg_error와 중복/누락 여부는 STAP repo 확인 필요 (이 Phase는 5000 repo만 스코프).

6. **[검증됨] 기존 알림 경로와 신규 모니터의 일시적 중복** — Phase 58에서 기존 `_tg_error` 호출을 유지하므로
   같은 실패에 알림이 2건 갈 수 있음. 쿨다운 공유로 흡수하되, 완전 단일화는 Phase 59에서 기존 경로 제거로
   확정. (이 Phase가 "중복 없음"을 목표로 하면 스코프 확장 필요 — discuss-phase에서 결정)
