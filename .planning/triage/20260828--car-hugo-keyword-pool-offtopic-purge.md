---
date: 2026-08-28
type: fix
status: resolved
---

# car-hugo 키워드 풀 오염 정화 (오프토픽 발행 차단)

## What
car-hugo 큐레이션 키워드 풀에서 비자동차 시드(맥북/노트북/슬리브/덤벨/밀폐용기/그릴/가방/바닥/매트 등 130+개)를 제거하고 29개 자동차 전용 시드로 교체.

## Why
car-hugo에 비자동차 상품 2건(층간소음 방지 매트, 맥북 에어 슬리브)이 발행됨. 근본 원인은 키워드 풀 자체가 오염돼 있어 Coupang 검색 시 비차량 상품 시드(바닥/슬리브)가 선택됐기 때문. relevance 게이트(CATEGORY_FILTERS)는 b1에서 이미 정화(느슨한 '카' 토큰 제거)됐으나, 시드 단계에서 오염 시드가 빠져나갈 수 있어 풀 정화가 필요.

## Files changed
- pipelines/curation/keywords.py (car-hugo 블록: 130+ → 29개 자동차 전용)

## How
스크립트로 `"car-hugo": [` 이후 첫 `],`까지 블록 전체를 자동차 전용 29개 시드로 교체. CATEGORY_FILTERS는 이미 strict(자동차매트만, 느슨한 매트/카 없음)라 게이트는 통과 못 함.

## Verification
- score_product("층간소음 방지 매트") = 0.00 → BLOCK
- score_product("맥북 에어 슬리브 가죽 파우치") = 0.15 → BLOCK
- score_product("블랙박스 전후방 4K"/"차량용 공기청정기"/"타이어 공기주입기") = 1.00 → PASS
- 풀에 맥북/노트북/슬리브/덤벨/밀폐용기/그릴 등 오염 시드 0건
- py_compile OK
