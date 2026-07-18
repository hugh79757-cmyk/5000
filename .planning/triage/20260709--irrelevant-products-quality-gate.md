---
date: 2026-07-09
type: docs
status: resolved
---

# baby-hugo irrelevant_products 임계값 초과 — 품질 게이트 정상 작동 (코드 버그 아님)

## What
baby-hugo 발행 실패: `[임계값 초과] irrelevant_products (keyword=가벼운)`
제품 필터가 키워드 `가벼운`에 대해 부적합 상품을 감지하여 발행 차단.

## Why
코드 버그가 아님. `_filter_irrelevant_products()`가 정상 작동 중.
"가벼운"이라는 키워드로 생성된 상품들이 baby-hugo(유아용품) 주제와
관련성이 낮다고 판단되어 품질 게이트가 발행을 차단한 것.

## Resolution
- **코드 수정 불필요**: 품질 게이트가 의도대로 작동 중
- **개선 방향**: AI 프롬프트에서 키워드 선정 기준 개선 검토
  ("가벼운" 대신 "가벼운 유아용품" 등 구체적 키워드 사용)

## Files changed
없음 (품질 게이트 정상 작동 확인)

## Verification
테스트 코드 `tests/curation/test_filters_allblogs.py`에서
`_filter_irrelevant_products()` 정상 동작 확인 완료.
