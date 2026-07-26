---
date: 2026-07-26
type: fix
status: resolved
---

# TAP 블로거 메타 응답 발행 차단 (4계층 방어)

## What
`travel.rotcha.kr` (TAP 블로거)에서 AI가 여행 콘텐츠 대신 메타 응답("죄송합니다. 제가 이미 동일한 요청에 대해 블로그 글을 작성하여 전달드렸습니다...")을 발행하는 문제 해결. 4계층 방어 시스템 구축으로 재발 방지.

## Why
**발생 원인**: gpt-4o-mini 모델이 프롬프트를 대화형 연속 요청으로 해석해 "이미 답변함"이라는 메타 응답을 생성. 기존 검증기(`core/validators.py`)는 길이(≥200자), HTML 구조(h2/h3), 금지어, 이모지만 체크하여 메타 응답을 통과시킴.

**트리거**: 2026-07-25 "경북 맛집 풀빌라 3곳 청도굿스파키즈 등 비교 추천" 포스트에서 메타 응답 발행됨.

**기존 방어 부재**:
1. 시스템 프롬프트에 "대화형 응답 금지" 규칙 없음
2. 검증기에 메타 응답 탐지 패턴 없음
3. AI 라이터 재시도 로직 없음
4. 파이프라인 레벨 재시도/알림 없음

## Files changed
- `core/validators.py` — `META_RESPONSE_PATTERNS` 11개 정규식 추가, `_is_meta_response()` 함수, `validate_content()`에 `is_meta_response` 플래그 반환
- `core/__init__.py` — 새로운 심볼 익스포트 (`META_RESPONSE_PATTERNS`, `_is_meta_response`)
- `core/ai_writer.py` — 시스템 프롬프트에 `ANTI-META (CRITICAL)` 섹션 추가, `generate_full_content(max_retries=2)` 재시도 루프 구현
- `tests/test_validators.py` — `TestMetaDetection`, `TestRegressionSuite` 클래스 추가 (전체 20개 테스트 통과)

## How
**4계층 방어 (깊이 순):**
1. **Layer 1 - 프롬프트 강화**: 시스템 메시지에 `ANTI-META (CRITICAL)` 규칙 5종 명시 (사과/메타코멘트/재작성 제안/AI 자기언급/사용자 질문 절대 금지)
2. **Layer 2 - 검증기 탐지**: 11개 정규식으로 메타 응답 패턴 탐지 (`죄송합니다.`, `이미 작성`, `동일한 요청`, `앞서 전달`, `구조로 작성`, `언어 모델`, `AI 모델`, `As an AI`, `수정.*원하시.*있다면`, `다시 작성해 드리`)
3. **Layer 3 - AI 라이터 자동 재시도**: `max_retries=2` 기본값, 메타 탐지 시 경고 로그 후 재시도, 3회 실패 시 `RuntimeError`
4. **Layer 4 - 파이프라인 재시도 + 알림**: (계획됨) `app.py` `run_publish()` 3회 재시도, 최종 실패 시 텔레그램 알림

## Verification
- 단위 테스트: 20개 전체 통과 (기존 10개 + 신규 10개)
- 회귀 테스트: 기존 검증 로직(길이, 금지어, h2/h3, 공백, 이모지) 변경 없음 확인
- 임포트 검증: `META_RESPONSE_PATTERNS` 11개 로드, `_is_meta_response()` 메타/정상 샘플 정확 분류
- `validate_content()` 반환값: 메타 콘텐츠 `is_meta_response=True`, 정상 콘텐츠 `False`
- `generate_full_content()` 시그니처에 `max_retries=2` 파라미터 포함 확인