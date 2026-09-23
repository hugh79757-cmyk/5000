---
date: 2026-08-28
type: fix
status: resolved
---

# golf-hugo 키워드 풀 오염 정화

## What
golf-hugo 큐레이션 키워드 풀에서 비골프 시드(맥북/노트북/덤벨/매트/바닥/그릴/갤럭시북/가방/식기 등 195개)를 제거하고 22개 골프 전용 시드로 교체.

## Why
car-hugo와 동일한 오염 패턴. 단, golf는 CATEGORY_FILTERS가 strict 골프 전용(골프클럽/골프공/스윙 등)이라 게이트가 모든 비골프를 차단 → 실제 오프토픽 누수는 없었음(오염 시드는 생성 시도만 낭비). 사용자 확인("골프 수정해줘")으로 풀만 car-hugo와 동일하게 정화.

## Files changed
- pipelines/curation/keywords.py (golf-hugo 블록: 195 → 22개 골프 전용)

## How
car-hugo와 동일 방식으로 블록 전체 교체. keyword_expander.py의 golf(깨끗함)는 그대로.

## Verification
- 블록 재독: 골프/골프클럽/아이언세트/퍼터/골프공/스윙연습기/골프티/골프모자/드라이버/퍼팅/골프장 등 22개만 존재, 맥북/노트북/덤벨/매트 등 오염 0건
- py_compile OK
- 게이트 시뮬: 맥북 슬리브 파우치→0.15 BLOCK, 덤벨→0.00 BLOCK, 골프클럽 세트→1.0 PASS
