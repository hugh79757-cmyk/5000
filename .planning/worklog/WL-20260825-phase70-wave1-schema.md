# WL-20260825-phase70-wave1-schema

> 날짜: 2026-08-25 / 연관: Phase 70 Wave 1 (Quality Gates) / 상태: 완료

## 파괴적 작업 목록
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| - | publish_log 스키마 확장 | `ALTER TABLE publish_log ADD COLUMN unique_data_points INTEGER DEFAULT 0;` | 기존 컬럼 7개 | 없음(추가형) | 컬럼 존재·타입·기본값·FK 보존 확인 | 기존 컬럼·FK 모두 유지 |

## 4단계 프로토콜 이행
1. 사전 카운트: publish_log 기존 컬럼 7개 (log_id, topic_id, blog_id, title, slug, published_at, url) + FK(topic_id→topics)
2. 되돌림 수단: `ALTER TABLE publish_log DROP COLUMN unique_data_points;` (SQLite 3.35+ 지원) — 추가형이라 롤백 단순
3. 실행: ADD COLUMN unique_data_points INTEGER DEFAULT 0
4. 사후 대조: test_schema.py 6건 전부 통과 (컬럼 존재/INTEGER/기본값 0/기존컬럼보존/FK보존/INSERT검증)

## 결과 / 보존 대상 확인
- 기존 컬럼 7개 + FK 제약 모두 그대로 유지됨 (test_schema.py assert)
- unique_data_points 컬럼 추가 후 INSERT/SELECT 정상 (값 5 저장·조회 확인)
- content.db 및 기타 운영 DB는 미변경 (travel-en.db만 대상)

## 잔존 위험
- travel-en.db 외 타 파이프라인 DB(예: stap_content.db, car.db)는 Phase 70 범위에서 아직 미적용 — 해당 파이프라인의 record_publish_with_data 호출은 Wave 2b에서 점선 연결 예정.
- ALTER는 운영 스케줄러 정지 없이 수행됨 (추가형 컬럼이라 락 불필요, 단일 ALTER 문). 락 경합 우려 없음.
