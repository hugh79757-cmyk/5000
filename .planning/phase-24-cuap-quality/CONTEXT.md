# Phase 24: CUAP 콘텐츠 품질 고도화

## Problem Statement

beauty.informationhot.kr에서 가구, 가죽소파 등 뷰티와 무관한 콘텐츠가 노출되고 있음.

### Root Cause Analysis

1. **키워드 오염 (Critical)**
   - `keywords.py`의 `beauty-hugo` 키워드 목록에 하드웨어/가구 키워드 혼재
   - `"가죽", "가죽소파", "노트북", "공기청정기", "냉장고", "덤벨", "데스크"` 등
   - 키워드 확장 과정에서 필터링 실패

2. **타이틀 전환율 미흡 (Medium)**
   - 현재: "립밤 추천" 같은 단순 패턴
   - 목표: 네이버 상위 블로그 수준의 클릭 유도 제목
   - 예: "2026년 7월 립밤 추천 미샤 듀이 루즈·헤라 센슈얼 — 실속 라인업 첫인상"

3. **이미지 중복 (Medium)**
   - 동일 제품 이미지가 여러 글에서 반복 사용
   - R2 업로드 시 고유 식별자 없음

---

## Scope

### In Scope
- `keywords.py` beauty-hugo 키워드 정리 (비뷰티 키워드 제거)
- `CATEGORY_FILTERS` beauty-hugo 필터 강화
- `writer.py` 제목 생성 로직 개선 (네이버 벤치마크 참조)
- `pipeline.py` 이미지 해시 기반 중복 방지

### Out of Scope
- 기존 발행된 글 수정 (다음 발행분부터 적용)
- 다른 블로그 키워드 정리 (beauty-hugo만)

---

## Success Criteria

1. beauty-hugo 키워드 목록에서 비뷰티 키워드 0개
2. `_filter_irrelevant_products()`가 가구/가전 상품 차단
3. 제목이 네이버 상위 블로그 스퀄와 유사한 전환율 구조
4. 동일 제품 이미지가 다른 slug로 업로드됨
