# Phase 71: Editorial Synthesis 실발화 연결

## 문제
editorial_synthesis_step이 9개 writer에 통합됐으나 topic dict에 topic_type/topic_id 미전달 → adapter가 빈 배열 → 합성 no-op.

## 목표
writer에서 실제 100-150단어 editorial synthesis 본문 주입.

## Wave
1. topic dict 확장 (5개 분기 dispatcher/topic_manager에 topic_type+topic_id 추가)
2. data_adapters 실데이터 반환 (분기별 DB 조회 → unique_data_points)
3. 합성 품질 검증 (100-150단어, hallucination 방지, cosine < 0.7)
4. freshness 연동 (unique_data_points 업데이트 + dateModified 갱신)

## 성공 기준
- 9개 writer 모두 비어있지 않은 합성 반환 (≥80자)
- unique_data_points ≥3개 저장
- cosine similarity < 0.7 (동일 블로그 최근 10건 대비)

## 예상 소요: ~9h (2일)
