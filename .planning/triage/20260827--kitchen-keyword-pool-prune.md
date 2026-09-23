---
date: 2026-08-27
type: fix
status: resolved
---

# kitchen-hugo 키워드 풀 오염 정화 (20 토큰)

## What
kitchen-hugo P14 경보 `가방` — _filter_irrelevant_products가 정상 거부(올바른 동작). 오염은 키워드 풀 자체에 비주방 토큰 혼입.

## Why
`pipelines/curation/keywords.py` KEYWORD_MAP[kitchen-hugo] 블록에 주방 무관 토큰(가방, 노트북, 남성, 덤벨 등) 포함 → P14가 이런 키워드로 쿠팡 상품 조회 시 필터가 매번 거부.

## Files changed
- pipelines/curation/keywords.py (kitchen-hugo 블록에서 20 토큰 정확 삭제)
- 백업: keywords.py.bak_20260827_150500

## How
라인인덱스 시도는 쓰기 전 assert 실패(파일 무변경). 콘텐츠 기반 정규 추출로 20 토큰(pruned) 정확 삭제: 가방,가죽,가죽소파,갤럭시,갤럭시북,게이밍,기숙사,길들이기,남녀공용,남성,남자,노트북,노트북가방,노트북파우치,대학생,대화면,덤벨,데스크,도루코,독일.

## Verification
- py_compile OK. kitchen 블록에 '가방' 더 이상 없음. 나머지 주방 항목 유효.
- P14는 필터 정상동작(버그 아님) → 경보 자체는 올바른 거부.

## Next observation
해당 없음 (resolved). 단 P14 경보 재발 시 다른 블로그 풀도 점검.
