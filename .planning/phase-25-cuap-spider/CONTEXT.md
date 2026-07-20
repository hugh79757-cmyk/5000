# Phase 25: CUAP 거미줄 엔티티 시스템 — CONTEXT

## Problem Statement

CUAP 10개 블로그가 독립적으로 운영되어 사용자 이탈률이 높고 광고 노출 기회가 제한적임.

### Root Cause Analysis

1. **크로스링크 부재 (Critical)**
   - 기존 entity_linker.py는 ETAP(여행 블로그) 전용, CUAP 미사용
   - CUAP 블로그 간 자연스러운 연결 경로 없음
   - 사용자가 유입 후单一 블로그에서만 머무름

2. **퍼널 구조 부재 (High)**
   - 관련 글 추천이 같은 블로그 내에서만 발생
   - 카테고리 간 자연스러운 흐름 설계 없음
   - 광고 노출 기회 단일 페이지에 한정

3. **광고 최적화 미흡 (Medium)**
   - 크로스셀 카드 없음
   - 퍼널 헤더 없음
   - 사용자 순회 유도 메커니즘 부재

---

## Implementation Decisions

### Decision 1: CUAP 엔티티 DB 위치
- **선택:** travel-en.db 통합 (권장)
- **이유:** 기존 ETAP entity_linker.py의 travel-en.db에 CUAP 테이블 추가 — 관리 편리, 기존 코드 재사용
- **적용:** `cuap_entities` + `cuap_link_graph` 테이블을 travel-en.db에 추가

### Decision 2: 인라인 링크 삽입 시점
- **선택:** 발행 시 본문 삽입 (권장)
- **이유:** pipeline.py에서 publish() 호출 전 본문에 삽입 — 기존 entity_linker.py 패턴과 동일, 안정적
- **적용:** `inject_cross_blog_links()` 함수를 pipeline.py 발행 흐름에 삽입

### Decision 3: 크로스셀 카드 생성 방식
- **선택:** Python에서 미리 생성 (권장)
- **이유:** pipeline.py에서 HTML 문자열로 생성 후 마크다운에 삽입 — 기존 CTA 패턴과 동일, 안정적
- **적용:** `build_cross_sell_card()` 함수로 HTML 생성 후 body_md에 삽입

### Decision 4: 퍼널 헤더 생성 방식
- **선택:** Python에서 미리 생성 (권장)
- **이유:** pipeline.py에서 HTML 문자열로 생성 후 마크다운에 삽입 — 크로스셀 카드와 동일 패턴
- **적용:** `build_funnel_header()` 함수로 HTML 생성 후 body_md 상단에 삽입

### Decision 5: Hugo 레이아웃 통합 방식
- **선택:** 통일 레이아웃 (권장)
- **이유:** 10개 블로그 전부 동일한 cuap-spider-links.html 사용 — 관리 편리, 일관성
- **적용:** `layouts/partials/cuap-spider-links.html` 신규 생성 후 10개 블로그 전부 적용

### Decision 6: 퍼널 경로 설정 방식
- **선택:** 고정 경로 (권장)
- **이유:** CROSS_GRAPH 딕셔너리로 고정 경로 설정 — 단순하고 안정적, 즉시 적용 가능
- **적용:** `cuap_entity_linker.py`에 CROSS_GRAPH 딕셔너리 정의

---

## Scope

### In Scope
- `shared/cuap_entity_linker.py` 신규 생성
- `pipelines/curation/pipeline.py` 발행 흐름 수정
- `layouts/partials/cuap-spider-links.html` 신규 생성
- `layouts/_default/single.html` 수정 (related.html 대체)
- travel-en.db에 CUAP 테이블 추가

### Out of Scope
- ETAP 기존 `entity_linker.py` 수정
- STAP/TAP 외부 프로젝트 연동
- 실시간 사용자 트래킹/분석
- A/B 테스트 프레임워크
- 광고 수익 직접 최적화 (AdSense 설정 변경)
- 기존 발행된 글 수정 (다음 발행분부터 적용)

---

## Success Criteria

1. CUAP 10개 블로그 간 크로스 링크 시스템 구축
2. 본문 발행 시 자동으로 타 블로그 링크 삽입
3. 크로스셀 카드가 본문 하단에 표시
4. 퍼널 헤더가 본문 상단에 표시
5. 세션당 평균 페이지뷰 1.2 → 2.5+ 증가
6. 광고 노출 기회 2~3x 증가

---

## Risk Mitigation

| 리스크 | 영향도 | 완화 방안 |
|--------|--------|-----------|
| 링크 품질 저하 | 중 | 키워드 매칭 임계값 설정, 수동 검증 |
| 성능 저하 | 하 | DB 인덱싱, 캐싱 전략 |
| Hugo 빌드 실패 | 중 | partial 오류 시 fallback 처리 |
| 광고 정책 위반 | 하 | Google AdSense 가이드라인 준수 |
