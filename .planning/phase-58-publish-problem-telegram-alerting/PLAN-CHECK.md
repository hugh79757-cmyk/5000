# Plan Check: Phase 58 — 발행 문제 인벤토리 + 정밀 Telegram 알림 시스템

**Checked:** 2026-08-06
**Plans verified:** PLAN.md (단일 플랜, Task 1-8 / 5 waves)
**검증 근거:** 실코드 read + `.venv/bin/python` 실측 실행 (아래 각 항목에 표기)

---

## 판정 요약

## **PASS** (재검증 2차 — MAJOR 3건 해소 확인)

> 1차 검증(2026-08-06) 판정: **FAIL** (Score: 58/100, MAJOR 3건 blocking) — 아래 본문은 1차 기록.
> 2차 검증(2026-08-06, 수정본 PLAN.md v2)에서 MAJOR 3건 전부 해소 확인 — 상세는 하단
> "## 재검증 2차 (2026-08-06)" 참조. **실행 가능.**

1차 기록: 계획의 뼈대(24개 문제 등록, additive 원칙, raw 훅 위치, dry-run 롤아웃, 테스트 인프라)는
건실하고 file:line 참조 대부분이 실코드와 일치한다. 그러나 **모니터의 핵심 발송 메커니즘(T4)이
실제 ThresholdChecker API와 불일치**하고, **P07 탐지 테스트 기대치가 설계·목표와 정반대로
뒤집혀** 있으며, **P22가 등록만 되고 탐지 경로가 전무**하다. 이 3건은 실전 파이프라인에서
"CRITICAL 즉시 알림"(성공 기준 #3), "CJK 오탐 방지"(계약 4), "24건 정확 알림"(목표)을
충족하지 못하게 한다. 실행 전 수정 필수.

### 검증 요약

| 항목 | 결과 |
|---|---|
| 코드 사실 검증 (file:line) | 22건 중 20건 ✅, 2건 ⚠️ (아래 표) |
| 24개 문제 등록 | ✅ 24건 (6 CRITICAL / 12 MAJOR / 6 MINOR — 목록 기준 정확) |
| additive 게이트 | ✅ 기존 `_tg_error` 호출 경로 변경 없음 명시 + grep 게이트 |
| raw 훅 위치 (BUG-54-001) | ✅ `writer.py:755` `_is_cot_body` 호출 **이전** (실코드 확인) |
| CJK 오탐 방지 설계 | ✅ ratio 0.5 기반 설계 — **단, 테스트 기대치가 뒤집힘 (MAJOR-2)** |
| 심각도 정책 | ⚠️ CRITICAL 항상발송 메커니즘이 실 API와 불일치 (MAJOR-1) |
| 검증 명령 (`.venv/bin/python -m pytest`, patch send) | ✅ 전 태스크 일관 |
| 잔존 위험 섹션 | ✅ 존재 (6건, REQUIRED 충족) |

---

## 코드 사실 검증표 (PLAN.md 참조 vs 실코드)

| PLAN.md 참조 | 실코드 | 결과 |
|---|---|---|
| dispatcher.py:672-740 결과 정규화 | `dispatch()` :672-741 (normalize :674-686, 실패 처리 :701-741) | ✅ 일치 |
| dispatcher.py:691-692 배포 반환값 무시 | :691-692 `_build_and_deploy_central(blog_id)` 반환 미캡처 | ✅ 일치 — 반환 캡처 계획 타당 |
| dispatcher.py:709/715/718/723/697 `_tg_error` | :697(deploy), :709(ipo), :715(no_result), :718(escalation), :723(duplicate) | ✅ 일치 |
| dispatcher.py:91 failure_count 경로 | :91 `_FAILURE_COUNT_FILE`, 함수 :142-164 | ✅ 일치 |
| dispatcher.py:678 문자열-정규화 목록 | :678-684 `("quota_met","fetch_error","no_data","write_error","no_content","publish_error","config_error")` | ✅ 일치 (1라인 오프셋 무해) |
| curation pipeline.py:850-865 run() 실패 블록 | :850-865 (알림 제외 목록 :856, `_tg_error` :857, maybe_alert :862-865) | ✅ 일치 |
| curation pipeline.py:857 유지 | :857 `_tg_error(blog_id, reason, ...)` | ✅ 일치 |
| curation pipeline.py:1104-1128 similar_title | :1104-1128 fallback 3회 소진 → `reason:"similar_title"` | ✅ 일치 |
| writer.py:606-648 `_is_cot_body` | :606-648 | ✅ 일치 |
| writer.py:755 이전 raw 훅 | :755 `if _is_cot_body(body):`, :762 `_sanitize_body(body)` — **raw 시점 :750-752** | ✅ 일치 — BUG-54-001 교훈 준수 |
| writer.py `generate_curation_article` blog_id | :681 `def generate_curation_article(keyword, products, blog_id=None)` — blog_id 존재 | ✅ (PLAN:386 우회 분기 불필요) |
| publisher.py:836-855 `_run_validation` | :836-855 (`_tg_err(...,"validation",...)` :848-854) | ✅ 일치 |
| publisher.py duplicate_slug/source_id | :877-901 | ✅ 일치 |
| validators.py has_cjk :20-32 | :20-26 `CJK_CHARS` + `has_cjk` | ✅ 일치 |
| validators.py is_korean_content :186-197 | :186-197 `min_hangul_ratio=0.5` 기본 | ✅ 일치 |
| ai_response_parser THINKING_PATTERNS :15-49 | :15-37 (CJK_INSTRUCTION_LEAK :40-43, FORBIDDEN :46-49) | ✅ 일치 |
| ai_response_parser `_check_multilingual_leak` :65-82 | :65-82 | ✅ 일치 |
| post_validator check 이름 8종 | cta_html:105, curation_cta:116, empty_template:125, thumbnail:130, map_text:135, min_length:142, readability:148, keyword_coverage:173 | ✅ 전부 일치 |
| alert_thresholds ThresholdChecker 재사용 | :31-155, `maybe_alert` :93-155 | ⚠️ 시그니처/동작 불일치 (MAJOR-1) |
| scheduler.py:284-293 / :734-758 | :284-293 `_tg_error` 3건, :734-758 `_track_publish_result` | ✅ 일치 (유지 확인만 — CONTEXT 부합) |
| validators.py:744-758 body_md NameError | :692-698 시그니처에 `body_md` 없음, :750 `body_md.split()` 사용 → NameError 실재 | ✅ 일치 (잔존 위험 4 정확) |
| telegram_notifier.send :13-33 | :13-33 `send(message, parse_mode="HTML")` | ✅ 일치 |
| 테스트 파일 존재 | tests/shared/test_telegram_notifier.py, tests/curation/test_alert_thresholds.py, test_pipeline.py | ✅ 존재 |

---

## MAJOR findings (blocking — 실행 전 수정 필수)

### MAJOR-1 [검증됨 — alert_thresholds.py 실독 + PLAN.md 대조]
**Task 4 CRITICAL "always" 발송 메커니즘이 실제 ThresholdChecker API와 불일치 → 성공 기준 #3 실패**

- **증거**:
  - PLAN.md:269: `"always" (CRITICAL) → checker.check_consecutive_failures(blog_id, problem_id, consecutive=1)를 쿨다운 게이트로 사용해 무조건 발송 여부 결정 (60분 쿨다운)`
  - 실 API (alert_thresholds.py:68-72): `check_consecutive_failures(self, blog_id, consecutive_count) -> bool` — **3인자 호출 시 TypeError**, 2인자로 고쳐도 `1 >= 3`(기본 임계값) → **False** → CRITICAL이 1회차에 발송 안 됨 (BLOG_OVERRIDES pet-hugo=2 등은 더 높음). 이 메서드는 **쿨다운과 무관** (쿨다운은 `_in_cooldown`/`_mark_alerted`, :80-91) — "60분 쿨다운 게이트"로 쓸 수 없음.
  - PLAN.md:270: MAJOR 경로 `checker.maybe_alert(...)` 위임 — but `maybe_alert`는 **자체적으로 `send_error`(구형 단일 템플릿)로 발송** (alert_thresholds.py:150-153). 문제별 한국어 템플릿(성공 기준 #2)이 무시되거나, monitor가 자체 템플릿도 발송하면 **중복 발송**.
  - PLAN.md:266: hook 불일치 시 발송 금지 가드 — curation `deploy_error`를 phase="result_parse"로 보고(P6:378)하면 P04(hook=post_deploy)와 불일치 → **합법적 경보가 조용히 차단**.
  - PLAN.md:452-453: T7은 "checker를 fake로 주입" — 실 ThresholdChecker 경로를 테스트가 **우회**해 생산 동작 검증 부재.
- **영향**: CONTEXT 성공 기준 #3 "CRITICAL 6건(P04~P09) 1회 발생 시 즉시 알림" 미달. P04~P09 전부가 실전에서 조용히 누락되거나 중복 발송.
- **수정 방향**: always 경로는 `checker._in_cooldown(blog_id)`/`checker._mark_alerted(blog_id)`(기존 메서드)만 쿨다운 게이트로 재사용하고 연속 임계값은 우회, `send_fn`으로 자체 템플릿 발송. MAJOR 경로는 `maybe_alert`의 **반환값만 게이트로** 사용(발송은 자체 템플릿). T7은 **실 ThresholdChecker**로 1회차 발송 + 60분 쿨다운 스킵을 검증. curation deploy_error는 phase="post_deploy"로 보고.

### MAJOR-2 [검증됨 — `.venv/bin/python` 실측 실행]
**P07(CJK 누수) 테스트 기대치가 설계·목표와 정반대 → T3 verify / T7 테스트가 실패하거나 오탐 체계를 생산**

- **증거**:
  - 설계 (PLAN.md:205-207): `has_cjk` 판별 후 `is_korean_content(min_hangul_ratio=0.5)` **ratio 미달이면 판정** (→ 일본어/중국어 = 누수로 검출).
  - 테스트 (PLAN.md:236-238): `detect_cjk_leak('この記事は日本語で書かれています。...')` → `assert cjk is None` — **일본어(진짜 CJK 누수)가 미검출이어야 한다고 주장**.
  - 실측: 해당 샘플 `has_cjk=True`, `is_korean_content(0.5)=False` → 설계대로면 P07 **검출** → assert `cjk is None` **실패**. 반면 heritage 스타일("갑사(甲寺)...")은 `has_cjk=True`, `is_korean_content=True` → 설계상 미검출(올바른 오탐 방지).
  - T7 스펙 (PLAN.md:442): "한글 비율 0.5 미만 CJK → None(오탐 방지), ratio ≥ 0.5 → 감지" — **완전 역전**: 오탐 케이스(한자 병기 한국어)를 검출하고, 실누수(일본어/중국어)를 놓침 — travel2 한자 병기 86건 오탐 사고(계약 4)를 그대로 재현하는 방향.
  - 부속 결함 [검증됨 — 실측]: P08 verify 샘플 `'Sure, let me think step by step.\n1. 계획\n2. 실행\n글 본문'` (PLAN.md:234-235) — 실측 `_check_multilingual_leak` = `(False, None, None)`, THINKING_PATTERNS 매치 0건 → `detect_cot_leak`이 None 반환 → assert `leak is not None` **실패**.
- **영향**: T3 검증 명령이 실행 시점에 실패(작업 정지), 또는 테스트를 강제 통과시키려다 탐지 로직을 목표와 반대로 구현(오탐 체계 생산). P07은 24건 중 CRITICAL — 목표("CJK 릭 정확 알림") 직접 위반.
- **수정 방향**: 테스트 기대치를 설계에 맞게 교정 — (a) ratio < 0.5 CJK(일본어/중국어 문장) → P07 검출 assert, (b) ratio ≥ 0.5 한자 병기 한국어 → None assert. P08 샘플은 THINKING_PATTERNS 실매치 텍스트(예: `"Let me re-read the request\n"`, `<thinking>`, `"주의: ..."`)로 교체.

### MAJOR-3 [검증됨 — plan 전역 grep]
**P22(LLM 폴백 체인 전체 실패)가 레지스트리에만 등록되고 탐지 경로 0건 → 24건 중 1건이 영원히 발화 불가**

- **증거**:
  - PLAN.md:162: P22 등록 (hook="content_generation", reason_key="llm_fallback_exhausted") — 단독 등장 (grep 결과 PLAN.md 내 유일).
  - PLAN.md:127: hook enum = "result_parse"|"post_generate"|"post_validate"|"post_publish"|"post_deploy" — P22의 "content_generation"은 **enum 밖** → 가드(PLAN.md:266)가 발송을 차단.
  - 통합 지점(PLAN.md:22-27)에 ai_writer RuntimeError 캐치 지점 없음. `llm_fallback_exhausted` reason을 생성하는 코드 경로가 프로젝트 전체에 **0건** (grep 확인). ai_writer.py:315 `raise RuntimeError(msg)`는 파이프라인 catch에서 `no_content`로 흡수(RESEARCH) → 전체 폴백 실패가 **P02로 오분류**되어 사용자에게 정확한 원인 미전달.
  - T8 통합 테스트 범위(PLAN.md:476-481)에 P22 없음.
- **영향**: 목표("24건 중 하나라도 발생하면 어떤 문제인지 정확히 알림")의 1/24 미달 + LLM 폴백 전멸 시 원인 오인식.
- **수정 방향**: ai_writer RuntimeError catch 지점에 additive P22 보고 추가(또는 dispatcher가 fallback 컨텍스트 보유 시 매핑) + T8 통합 테스트 1건 추가. hook을 enum 내 값으로 정정.

---

## MINOR findings (non-blocking)

### W-1 [검증됨] 연속 카운터 공용화: 증감·리셋 주체 미지정, `reset()`은 no-op
- PLAN.md:277 `reset(blog_id)`: "checker.reset_failure_count 또는 동등 메서드 재사용. 존재하지 않으면 logger.debug만 하고 스킵" — **ThresholdChecker에는 reset 메서드가 없음** (alert_thresholds.py 전역 read, 메서드: get_config/check_consecutive_failures/check_keyword_streak/_in_cooldown/_mark_alerted/maybe_alert). 확장 키 `{blog_id}:{problem_id}`(PLAN.md:330)는 **성공 시 리셋 경로가 없음** → 연속 카운터가 성공 후에도 누적 → "연속 3회"가 비연속 누적 실패에도 발화. 누가 증분하는지(monitor vs dispatcher)도 미지정.
- **수정**: Task 5 카운터 확장에 성공 시 `{blog_id}:{problem_id}` 키 삭제 경로 명시 + 증분 주체 단일화 (CONTEXT A1 우선 원칙: dispatcher 카운터 우선).

### W-2 [부분검증] post-generate 훅(P07/P08/P09/P23)이 curation에만 배선
- PLAN.md:382-386 raw 훅은 `pipelines/curation/writer.py`만. CONTEXT 설계 결정 4는 "curation/writer.py generate_curation_article **/ ai_writer.py:433-451**" 병기 — ai_writer 기반 파이프라인(car/senior/gap/rap/travel)은 콘텐츠 누수 감지 0건 (ai_writer.py:439 RuntimeError → no_content 흡수는 RESEARCH 확인, 직접 미실측).
- **수정**: ai_writer 경로 제외 사유를 스코프 명시로 문서화하거나 ai_writer raw 지점 1곳 추가.

### W-3 [검증됨] PublishMonitor API가 CONTEXT 확정 설계와 상이
- CONTEXT: `report(blog_id, result, phase, extra) -> list[str]`, `detect(hook, content, blog_id)`, `send_problem_alert(problem_id, blog_id, context)`, `__init__(checker=None, dry_run=None)`.
- PLAN.md:262-277: `report(blog_id, problem, phase, consecutive, pattern, matched)` — `detect()`/`send_problem_alert()` 메서드 **부재** (Task 6이 standalone `detect_raw_content` 직접 호출), `__init__(checker, send_fn)`.
- **수정**: 사용자 승인을 받거나 CONTEXT API로 복귀 (기능 동등하나 locked API 이탈).

### W-4 [검증됨] 수정 전 baseline 미실행 (Phase 54 W3와 동일 패턴)
- PLAN.md:482-489 T8 회귀 게이트가 "수정 전 baseline과 대조"를 요구하나 baseline 기록 태스크 없음. AGENTS.md 코드 수정 원칙은 수정 전 기준선 실행을 필수로 규정.
- **수정**: Task 5 시작 전 `pytest tests/ -q` baseline 수치를 PLAN.md 또는 리포트에 기록하는 단계 추가.

### W-5 [부분검증] 단일 플랜 8 태스크 / 11 파일 — 스코프 초과 경계
- 파일: 신규 7(shared 3 + DEPLOY-PATHS + tests 4) + 수정 4(dispatcher.py, curation pipeline.py, writer.py, shared/publisher.py). 태스크당 파일 소유권 분리·소태스크(0.5-2h)라 실행 리스크는 낮으나 2-3 태스크/플랜 기준을 초과. Phase 54(5 태스크) PASS 선례보다 큼.
- **수정**: 선택 — T1~T4(모듈) / T5~T8(통합+테스트) 2-플랜 분할 권장.

### W-6 [부분검증] 지시문성 중국어 키워드 기준이 P07에 미구현 + CJK_INSTRUCTION_LEAK가 P08로 오분류
- CONTEXT 결정 4: "한글 비율 0.5 + **지시문성 중국어 키워드 기준으로만** 알림". PLAN P07(PLAN.md:205-207)은 ratio만. `_check_multilingual_leak`의 `cjk_instruction_leak`(ai_response_parser.py:76-80) 매치는 PLAN.md:209에서 **P08**(LLM/CoT 누수)로 보고 → 중국어 지시문 누수가 P08로 오분류. 실측: cjk_instruction_leak 패턴 존재 확인 (직접 발화 미실측).
- **수정**: `cjk_instruction_leak` 패턴 매치를 P07로 분기.

### M-7 [검증됨] 심각도 수치 헤더 불일치 — PLAN은 목록 기준(6/12/6) 채택, 문서화됨
- CONTEXT/RESEARCH 헤더 "MAJOR 13 / MINOR 5" vs 인벤토리 목록 실수 12/6 (P15 MAJOR 1건, P23/P24 MINOR). PLAN.md:166-168이 불일치를 명시하고 목록 기준 6/12/6 등록 — **목록 기준이 정확**하나 CONTEXT 헤더와의 불일치는 사용자 확인 필요 (레지스트리 검증 assert가 6/12/6 고정이라 CONTEXT 수정도 함께).

### M-8 [검증됨] P19(오래된/만료 데이터) 등록만 되고 탐지 경로 없음
- PLAN.md:159 P19(hook=post_validate, quiet) — detect_validation_issue(PLAN.md:218-220)는 P15 check 8종만 매핑, validators.py stale 검사(:363-372) 연결 지점 없음. quiet(로그만)라 실발송 영향은 없으나 로그조차 발생하지 않음.

### M-9 [검증됨] ROADMAP.md에 Phase 57/58 항목 부재
- ROADMAP.md(575줄)는 Phase 56까지만 존재. 추적성 갭 (plan 자체 결함 아님 — 프로세스 산출물 누락).

### M-10 [검증됨] RESEARCH "## Open Questions" 미해소 표기 (Dimension 11)
- RESEARCH.md:596-618 Q1~Q4에 (RESOLVED) 마커 없음. PLAN.md:562-569가 Q1~Q4를 태스크(T1/T5/T6)로 이관해 해소 경로를 갖는 것은 타당하나, Q1/Q2가 실행 중 미확정이면 P04/P05 reason_keys·P03 보존 배선이 위험 (잔존 위험 #1로 완화됨).

### M-11 [검증됨] Task 5 result_parse 훅 위치가 성공 케이스에 노이즈 유발 가능
- PLAN.md:321 "normalize 직후" 무조건 훅: success=True 결과는 `reason` 키 부재 → `lookup_reason(None)` → None → **모든 성공 발행마다** "unknown failure reason" warning. dispatcher.py:687-741 실패 분기(:701 이하) 내로 배치 필요.

### M-12 [부분검증] Task 8 "dry-run 실발송 0건" 확인이 부분 순환
- PLAN.md:490-496 로그 grep("PROBLEM_ALERT_DRY_RUN")은 로깅 발생만 증명, `send()` 미호출은 증명 못함. 실증은 T4/T7의 patch 기반 `call_count==0` assert. dry-run 0건 게이트는 T7 assert를 1차 근거로 명시할 것.

---

## Dimension-by-Dimension 요약

| Dimension | Status |
|---|---|
| 1. Requirement Coverage (성공 기준 8건 매핑) | ✅ PASS (매핑표 존재, P22 배선 누락은 MAJOR-3) |
| 2. Task Completeness (Files/Action/Verify/Done) | ⚠️ FAIL — T3/T7 검증 기대치 역전 (MAJOR-2) |
| 3. Dependency Correctness | ✅ PASS (T1→T2→T4→T5/T6→T7/T8, 사이클 없음, 파일 소유권 분리) |
| 4. Key Links Planned | ⚠️ PASS — P22/P19 미배선 (MAJOR-3, M-8) |
| 5. Scope Sanity | ⚠️ WARNING — 8 태스크/11 파일 (W-5) |
| 6. Verification Derivation | ⚠️ FAIL — CRITICAL 경로 검증이 실 API 우회 (MAJOR-1) |
| 7. Context Compliance | ⚠️ FAIL — API 이탈(W-3), P07 테스트 역전(MAJOR-2), daily_rate 이연(M-7 참조) |
| 7b. Scope Reduction Detection | ✅ PASS — "v1/stub/future" 축소 표현 없음, 이연 항목 전부 문서화 |
| 7c. Architectural Tier Compliance | ✅ PASS — 전부 API/Backend 계층 (RESEARCH 맵 부합) |
| 8. Nyquist Compliance | ⏭️ SKIPPED — config.json `nyquist_validation: false` |
| 9. Cross-Plan Data Contracts | ✅ PASS — 단일 플랜, failure_count.json 하위 호환·템플릿 str.format 계약 명시 |
| 10. AGENTS.md Compliance | ⚠️ WARNING — additive 원칙 준수, baseline 누락 (W-4) |
| 11. Research Resolution | ⚠️ WARNING — Open Questions 태스크 이관 처리, 실행 중 해소 (M-10) |
| 12. Pattern Compliance | ⏭️ SKIPPED — PATTERNS.md 없음 |

---

## 잔존 위험 (checker 추가)

- [검증불가] gates.md 필수 리딩 파일이 참조 경로에 없음 (`get-shit-done/references/`에 ui-brand.md·questioning.md만 존재) — 게이트 기준은 내장 프로세스로 검증 수행.
- [부분검증] 잔존 위험 #2/#5 (raw 시점 감지와 기존 `_is_cot_body`/sanitize 이후 탐지의 이중 보고) — monitor 쿨다운 흡수 전제가 MAJOR-1 수정(실 쿨다운 사용) 후에만 유효.
- [부분검증] T1(전수 grep) 산출 전에는 P04/P05 reason_keys·P03 reason 보존이 미확정 — Q1/Q2 미해소 시 잔존 위험 #1로 명시된 대로 보고.

---

## 결론

**Verdict: FAIL (1차)** — MAJOR 3건 / MINOR 12건.

구조·사실 검증은 대체로 정확하나, **3건의 MAJOR blocking**(T4 CRITICAL 발송 메커니즘 API 불일치, P07 테스트 기대치 역전, P22 탐지 경로 부재)이 실전 파이프라인에서 성공 기준 #2/#3과 목표("24건 정확 알림")를 직접 위반한다. 실행 전 3건 수정 → 재검증 후 실행을 권장한다.

---

## 재검증 2차 (2026-08-06)

**Verdict: PASS** — MAJOR 3건 전부 RESOLVED (실코드 대조 + `dispatcher.py`/`hugo_writer.py` read 확인).
spot-check MINOR 6건(W-1/W-3/W-4/M-7/M-11/M-12) 수정 반영 확인.

### MAJOR-1 [RESOLVED — 실 ThresholdChecker API 준수]

| 요구사항 | 수정 반영 위치 |
|---|---|
| CRITICAL(always): `checker._in_cooldown(blog_id)`/`_mark_alerted(blog_id)`만 쿨다운 게이트로 사용, `check_consecutive_failures` **사용 금지** (실 API 2인자 `(blog_id, consecutive_count)`, `count>=3` 검사 — alert_thresholds.py:68-72 — 1회차 CRITICAL을 막음) | PLAN.md:288-292 |
| MAJOR: `check_consecutive_failures(blog_id, consecutive_count)` 2인자 호출 + 자체 템플릿 발송, `maybe_alert` **사용 금지** (자체적으로 `send_error` 구형 템플릿 발송 — alert_thresholds.py:150-153) | PLAN.md:293-296 |
| curation `deploy_error` → `phase="post_deploy"` (P04 hook 일치) — "result_parse" 하드코딩 금지 | PLAN.md:285-287, 454, 581-582 |
| T7은 **실 ThresholdChecker() 인스턴스** 사용 — fake 주입 금지 | PLAN.md:541 |
| phase 전달 규칙 문서화 + 강제 (불일치 시 logger.error + 발송 차단 가드) | PLAN.md:283-287 |
| 실 checker 검증 명령: CRITICAL 1회차 즉시 발송/60분 쿨다운 스킵, MAJOR 2회 미만 0건/3회째 1건 | PLAN.md:352-374 |

### MAJOR-2 [RESOLVED — P07/P08 기대치 정정, 실측 기반 샘플 교체]

- ratio < 0.5 CJK(일본어/중국어 문장) → P07 **검출** — 기대치 정정 명시 ("ratio<0.5이면 검출이 맞음") — PLAN.md:208, 244-246, 525-529
- ratio ≥ 0.5 한자 병기 한국어 → **None** (오탐 방지, travel2 heritage 86건 교훈) — PLAN.md:210, 247-249, 526
- `cjk_instruction_leak` 패턴 → **P07** 분기 (P08 오분류 금지, W-6 해소) — PLAN.md:209, 214, 250-252, 527
- P08 샘플 = THINKING_PATTERNS **실매치** 5종 ('이제 글을 작성하겠습니다', '<thinking>', '\n주의:', 'Let me re-read the request', '문장 수: 3') — PLAN.md:240-243, 530-533. 'Sure, let me think step by step' 등 비매치 샘플 사용 금지 명시 (실측 매치 0건).

### MAJOR-3 [RESOLVED — P22 탐지 경로 배선]

- P22 hook 정정: "content_generation"(enum 밖) → **"result_parse"** — PLAN.md:165
- `writer.py:745` `ai_generate` 호출부 **additive** try/except RuntimeError → `get_monitor().report(blog_id, {"reason": "llm_fallback_exhausted"}, phase="result_parse", extra={})` + **re-raise** (기존 no_content 흡수 경로 불변). writer.py:584(title 재생성 except) 미변경 명시 — PLAN.md:463-469. 근거: ai_writer.py:315 RuntimeError가 P02로 오분류되던 경로 해소.
- P22 배선 검증: registry 매핑 assert (PLAN.md:426) + **T8 통합 테스트** — `patch("pipelines.curation.writer.ai_generate", side_effect=RuntimeError)` → P22 알림 + re-raise 확인 — PLAN.md:577-580

### Spot-check MINOR (수정 반영 확인)

- **W-1** RESOLVED — 카운터 소유자 단일화: result_parse = dispatcher(`failure_count.json` 확장 키 `{blog_id}:{problem_id}`, 성공 시 확장 키 삭제 경로 + 기존 `_reset_failure_count` 불변) / 비-dispatcher 훅 = monitor 인메모리 `self._consecutive` + `reset(blog_id, problem_id)`. ThresholdChecker에 reset 추가 금지 명시 — PLAN.md:308-319, 400-404, 550-551
- **W-3** RESOLVED — CONTEXT API 복귀: `__init__(checker=None, dry_run=None)` / `report(blog_id, result, phase, extra) -> list[str]` / `detect(hook, content, blog_id)` / `send_problem_alert(problem_id, blog_id, context)` / `get_monitor()` — PLAN.md:277-307
- **W-4** RESOLVED — Task 5 수정 **전** baseline 기록 단계 추가 (수정 전 `pytest tests/ -q`) — PLAN.md:387-389
- **M-7** RESOLVED — CONTEXT.md 헤더 "MAJOR 13/MINOR 5" → **"6/12/6 (목록 기준 정정, M-7 반영)"** + registry assert 6/12/6 고정 — CONTEXT.md, PLAN.md:169-171, 518
- **M-11** RESOLVED — Task 5 result_parse 훅을 **실패 분기(:701 이하) 내부**로 배치, normalize 직후(:674-686) 배치 금지 (성공 시 reason 부재 "unknown failure reason" 노이즈 차단) — PLAN.md:390-395
- **M-12** RESOLVED — dry-run 실발송 0건의 **1차 근거를 T7 patch 기반 `send() call_count==0` assert**로 명시 (로그 grep만으로 증명 금지 명시) — PLAN.md:592-601, 647
- 추가 확인: M-8(P19 stale → quiet 로그만), W-2(curation 전용 스코프 명시), W-5/W-6 문서화 — PLAN.md:224, 41-42, 472, 688

### 재확인 사항

- **additive 게이트**: 기존 `_tg_error` 경로(dispatcher:697/709/715/718/723, curation:857, scheduler:284-293) 불변 명시 + grep 게이트 — PLAN.md:6-7, 384, 409, 456, 473, 646
- **잔존 위험 7건** (REQUIRED) — PLAN.md:678-690
- **24개 문제 전부 등록** (6/12/6) + `unknown_failure` — PLAN.md:142-167, 185
- **성공 기준 8건 → 태스크 매핑표** — PLAN.md:694-705
- **실발송 0건 게이트**: `PROBLEM_ALERT_DRY_RUN` env + `patch("shared.telegram_notifier.send")` — PLAN.md:647
- **사실 재확인 (read)**: `_increment_failure_count(blog_id) -> int` 반환값 존재 (dispatcher.py:150-156) — Task 5 카운터 재사용 계획 유효 / P23 500자 기준 = `sanitize_featureimage_url` 호출부 `max_len=500` (hugo_writer.py:772, 932) — PLAN.md:221 일치

### INFO (비차단 관찰)

- Task 7 "심각도 6/12/6 고정 assert" (PLAN.md:518)은 registry 25건(24 + unknown_failure)에서 `unknown_failure`를 제외하고 P01~P24만 집계해야 함 — unknown_failure severity 미지정이라 테스트 작성 시 주의 (실행 시 결정 가능).

**재검증 결론:** MAJOR 3건 RESOLVED, spot-check MINOR 전부 반영, 실코드 대조 사실 오류 없음. 1차 검증의 blocking 사유 소멸 — **`/gsd-execute-phase 58` 진행 가능.**
