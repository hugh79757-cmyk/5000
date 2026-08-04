---
date: 2026-08-02
type: bug
status: fixed
phase: 54
severity: high
---

# BUG-54-001: _is_cot_body() 호출되지 않는 버그

## 발견 일자
2026-08-02

## 재현 조건
1. `generate_curation_article()` 호출
2. LLM이 CoT 본문 반환 (예: "우선 사용자 요청은... AIDA 모델 적용... H2 섹션...")
3. `_sanitize_body()`가 CoT 마커 제거 ("우선 사용자 요청은..." → 삭제)
4. `_is_cot_body()`가 정화된 본문에 대해 호출됨
5. `cot_matches = 0` (마커가 이미 제거됨), `writing_matches >= 3` (H2, H3, 비교표 등)
6. 1개 조건만 충족 → `False` 반환 (2개 이상 필요)
7. CoT 본문이 재시도 없이 그대로 발행됨

## 영향
- CoT/프롬프트 지시문이 포함된 본문이 블로그에 발행될 수 있음
- health-hugo id=1980에서 실제 발생 (네덜란드 추천 글, draft:true이지만 배포됨)

## 근본 원인
`generate_curation_article()`에서 `_is_cot_body()` 호출 시점이 `_sanitize_body()` **이후**에 배치됨
→ `_sanitize_body()`가 CoT 마커를 제거한 후 `_is_cot_body()`가 호출되어 항상 False 반환

## 수정 내용
1. `_is_cot_body()` 호출 시점을 `_sanitize_body()` **이전**으로 이동
2. `cot_body_detected` 플래그 추가로 재생성 실패 추적
3. `body_regeneration_failed` 로직 수정: `cot_body_detected and not body`일 때 True

## 수정 파일
- `pipelines/curation/writer.py`: `generate_curation_article()` 함수 내 루프 로직

## 검증
- 단위 테스트: CoT 본문 감지 → 재생성 → 정상 본문 반환 시나리오 통과
- 기존 회귀 테스트: 114 passed, 4 pre-existing failed 유지

## 교훈
- sanitize 함수가 검증 대상의 마커를 제거하면 검증이 무의미해짐
- 검증은 sanitization **이전**에 수행해야 함
- 플래그 기반 상태 추적이 부분 실패 감지에 유용
