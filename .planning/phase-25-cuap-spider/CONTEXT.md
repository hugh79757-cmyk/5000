# Phase 25: CUAP 거미줄 엔티티 시스템

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

## Scope

### In Scope
- CUAP 전용 엔티티 링크 시스템 (cuap_entity_linker.py)
- 본문 인라인 크로스 링크 삽입
- 크로스셀 카드 HTML 생성
- 퍼널 헤더 HTML 생성
- 10개 블로그 간 연결 그래프 정의
- Hugo 레이아웃 수정 (single.html, related.html 대체)

### Out of Scope
- ETAP 기존 entity_linker.py 수정 (별도 프로젝트)
- STAP/TAP 외부 프로젝트 연동
- 실시간 사용자 트래킹/분석
- A/B 테스트 프레임워크
- 광고 수익 직접 최적화 (AdSense 설정 변경)

---

## Success Criteria

1. CUAP 10개 블로그 간 크로스 링크 시스템 구축
2. 본문 발행 시 자동으로 타 블로그 링크 삽입
3. 크로스셀 카드가 본문 하단에 표시
4. 퍼널 헤더가 본문 상단에 표시
5. 세션당 평균 페이지뷰 1.2 → 2.5+ 증가
6. 광고 노출 기회 2~3x 증가
