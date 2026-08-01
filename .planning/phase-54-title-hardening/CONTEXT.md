# CONTEXT.md — Phase 54: Curation Title Generation Hardening

## 배경

- 5000 파이프라인이 하루 블로그당 5건 자동 발행 (CUAP 10개 블로그)
- "네덜란드 추천 TOP5 (2026년)" (health-hugo, publish_log id=1980, 2026-08-01) — 하드코딩 fallback이 LLM H1 누락 시 생성
- 최근 30일 게시물 844건 중 111건(13%)이 "추천 TOP 5" 템플릿 패턴
- Phase 43(2026-07-24)이 "Title Generation Fix"로 COMPLETED 표기되었으나 fallback 로직 미수정 → 재발 확인
- 본 phase 목표: fallback 제거 + H1 형식 강제 + CoT 누출 차단 + 회귀 테스트

## 계약 (계획 시 준수할 제약)

1. **호환성**: 기존 반환 형식 `{"success": bool, "reason": str, ...}` dict 유지. 신규 `PublishResult`를 쓰더라도 `dict(result._asdict())`로 하위 호환
2. **fail-open 유지**: 관련성 점수 계산 실패 등 기존 fail-open 동작은 건드리지 않음
3. **hard fallback 금지**: 제목 생성 실패 시 템플릿 문자열 생성이 아니라 발행 중단(TITLE_BLOCKED 상태)으로 전환
4. **스코프 제한**: Hugo 템플릿 방어(Phase 47), 키워드 풀 전면 감사는 별도 phase
5. **검증 스크립트 정확성**: `generate_curation_article`(writer.py:449), `sqlite3 data/curation.db` 사용 — `generate_post`/`psql` 오류 반복 금지

## 확정된 설계 결정 (PLAN.md에 반영할 것)

- **재생성 루프**: H1 누락 시 `ai_generate(..., tier="economy", temperature=0.5, max_tokens=200)` 최대 2회. 성공 조건 = 길이 10~60자 + CoT 패턴 거부 + 템플릿 패턴 거부
- **템플릿 패턴 (2026-08-01 plan-checker 교정)**: `추천\s*TOP\s*\d+`, `BEST\s*\d+`, `\(\d{4}년\)$` (연도-괄호-끝). **`^\d{4}년`(연도-접두)은 거부하지 않음** — 시스템 프롬프트의 제목 규칙 1(`[연도]년 [월]월 [제품명] 추천`, writer.py:286-287)이 연도-접두 제목을 지시하므로 거부하면 프롬프트 준수 제목이 전부 차단됨. 실제 fallback 시그니처(`{keyword} 추천 TOP5 (2026년)`)는 `추천\s*TOP\s*\d+`와 `\(\d{4}년\)$`로 충분히 포착됨. (이전 결정 2의 `^\d{4}년`은 plan-checker MAJOR-1 발견으로 교체)
- **실패 처리**: 2회 실패 시 하드코딩 대신 발행 중단 + `_record_failure(blog_id, "title_regenerate_failed", ...)`
- **프롬프트**: `_build_system_prompt`에 "맨 첫 줄 # H1" 지시 + CoT/프롬프트 누출 금지 + 나열형 제목 금지. 기존 제목 규칙 1~4는 유지 (additive). 프롬프트 내 금지 예시는 반드시 `추천 TOP N (연도년)` 표기 (리터럴 `추천 TOP5` 금지 — SC-1 grep 오염 방지)
- **description**: `_extract_description()` 헬퍼 분리 (CoT 마커 제거 → 첫 의미 문단 → 150자, 최후 fallback 문구)
- **게이트**: pipeline.py 제목 검증부에 thin wrapper 추가 (기존 TITLE_BLOCKED 위). 게이트 패턴은 `_validate_title`과 동일
- **회귀 테스트**: publish_log에서 템플릿 패턴(`추천\s*TOP\s*\d+` 또는 `\(\d{4}년\)$`) 신규 기록 차단 검증 — 필수. 테스트는 **`_title_gate` wrapper 단위 시임**(`_record_failure` 패치) 사용 — 실 HTTP(Coupang/Naver) 경로인 `_run_inner` 전체 mock은 지양 (plan-checker MAJOR-2)

## 성공 기준

1. writer.py:538-539 하드코딩 fallback 코드가 제거됨 (grep 0건)
2. `generate_curation_article("네덜란드", ...)` 호출 시 제목이 `(2026년)`으로 끝나지 않음
3. description에 "우선 사용자 요청" 미포함
4. 회귀 테스트 통과 — 신규 발행의 title에 템플릿 패턴 0건
5. 기존 테스트 스위트 green 유지 (있으면; 없으면 신규 테스트 추가가 커버)
