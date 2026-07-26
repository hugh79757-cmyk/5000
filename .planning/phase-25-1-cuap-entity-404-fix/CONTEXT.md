# Phase 25.1: CUAP 엔티티 카드 404 수정 — CONTEXT

## 문제 정의

Phase 25 CUAP 거미줄 엔티티 시스템 구현 시, `register_cuap_entity()`가 `_make_slug(keyword)` 기반 slug로 엔티티를 등록했으나, 실제 `publish()` 함수는 `slugify(title)` 기반 slug를 사용해 배포. 결과적으로 **150개 엔티티 중 16개(10.7%)가 잘못된 URL**로 등록되어 cross-sell 카드/퍼널 헤더 클릭 시 404 발생.

## 근본 원인

1. **Phase 25 초기 구현** (`pipelines/curation/pipeline.py`): `register_cuap_entity()` 호출 시 `post_slug=_make_slug(keyword)` 전달
2. **실제 발행** (`shared/publisher.py:876`): `slug = slugify(title)`로 제목 기반 slug 생성
3. **불일치**: keyword "파우더 추천" → `_make_slug` → `헤브블루-vs-미팩토리-파우더-추천-2026` vs 실제 제목 "2026년 7월 파우더 비교 미팩토리 뿌숭뿌숭 vs 헤브블루 메이크업 프로 7100원 vs 15100원 선택 가이드" → `slugify` → `2026년-7월-파우더-비교-미팩토리-뿌숭뿌숭-vs-헤브블루-메이크업-프로-7100원-vs-15100원-선택-가이드`

## 이미 적용된 수정 (신규 발행분 보호)

`pipelines/curation/pipeline.py:1064` (2026-07-22 추가):
```python
_actual_slug = result.get("url", "").rstrip("/").split("/")[-1] if result.get("url") else slug
register_cuap_entity(..., post_slug=_actual_slug, ...)
```
→ `publish()` 반환 URL에서 실제 배포된 slug 추출해 등록. **신규 발행분은 정상 작동**.

## 남은 작업: 기존 16개 오염 데이터 수정

| 구분 | 개수 | 처리 |
|------|------|------|
| 이미 title-based slug로 일치 | 9 | DB slug와 실제 slug 동일 → 수정 불필요 (단, URL 재확인) |
| slug 불일치로 업데이트 필요 | 6 | 실제 콘텐츠 폴더 slug로 `post_slug`, `post_url` UPDATE |
| 미발행 글로 등록됨 | 1 (laptop-hugo) | `published=0`으로 변경 |

## 범위

### In Scope
- `scripts/fix_cuap_entity_urls.py` 신규 생성 및 실행
- `cuap_entities` 테이블 16개 행 UPDATE/UNPUBLISH
- 수정된 엔티티가 포함된 블로그 차기 발행 시 자동 정상화 확인

### Out of Scope
- 기존 배포된 포스트의 HTML 내 cross-sell 카드 URL 교체 (Phase 29 전량 재배포 시 처리)
- ETAP/STAP 외부 프로젝트 엔티티 시스템
- 신규 발행 파이프라인 수정 (이미 완료)

## 성공 기준

1. `cuap_entities` 테이블에서 `published=1`인 모든 엔티티의 `post_url`이 실존하는 Hugo 콘텐츠와 일치
2. `curl -I https://{domain}/posts/{correct_slug}/` → HTTP 200
3. 신규 발행 시 `register_cuap_entity()`가 title-based slug로 등록됨 (회귀 테스트)

## 위험 요소

| 위험 | 확률 | 영향도 | 완화 |
|------|------|--------|------|
| 슬러그 매칭 오류로 잘못된 URL 저장 | 낮 | 중 | 수동 검증된 FIXES 매핑 테이블 사용 |
| 미발행 글 published=0 처리 누락 | 낮 | 중 | laptop-hugo 명시적 처리 |
| DB 락으로 파이프라인 중단 | 극낮 | 낮 | 단일 트랜잭션, 즉시 커밋 |

## 의존성

- Phase 25 완료 (CUAP 거미줄 엔티티 시스템 구축)
- Phase 27 완료 (CUAP Cross-Sell Card 404 Fix — 백필 스크립트 패턴 선행 완료)
- Phase 29 예정 (전량 재배포로 기존 404 링크 완전 해소)

## 참고 문서

- Phase 25 PLAN: `.planning/phase-25-cuap-spider/PLAN.md`
- Phase 27 CONTEXT: `.planning/phase-27-cuap-cross-sell-404-fix/CONTEXT.md`
- Phase 29 CONTEXT: `.planning/phase-29-cuap-content-fix/CONTEXT.md`