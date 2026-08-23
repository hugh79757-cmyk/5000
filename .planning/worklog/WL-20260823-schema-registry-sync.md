# WL-20260823 — schema_registry DB + 대시보드 뷰 + daily sync

**태스크:** SCHEMA_REGISTRY_DB_AND_DASHBOARD_SYNC (CODE_IMPLEMENT, HIGH)
**커밋:** `e1acc419e`(선행 schema-as-code), `7c96e87f2`(본 태스크 +571행 9파일)

## 수행 내용

1. **PART_1** — ops.db에 `schema_registry` 테이블 생성(사용자 DDL), 85블로그 동기화
   (85/85, 분기 분포 fleet 검증 일치). 파괴 프로토콜: 백업 → 실행 → 사후대조 → 로그.
2. **PART_2** — `/schema`, `/schema/<blog_id>` Flask 뷰 + 템플릿 2종 + nav 링크.
   요약은 내구 신호 실시간 계산(64/12/9), 감사 스냅샷(54/22/9)과 차이 문서화.
3. **PART_3** — scheduler.py 09:00 `_run_schema_sync` 훅, 테스트 6건(6/6),
   회귀 대조(HEAD 워크트리: 신규 실패 0), sqlite 커넥션 누수 수정.

## 검증 근거

- sync 85/85: python3 직접 실행 출력 확인
- 분기 분포: etap36/cuap15/cap13/tap8/stap6/rap5/seap2 = 85 (fleet 리포트와 일치)
- 테스트: tests/ops_dashboard/test_schema_registry.py 6/6 (tmp DB, 운영 가드 통과)
- 회귀: HEAD 베이스라인 12실패 ⊃ 작업트리 8실패 — 신규 회귀 없음
- 타 테이블 불변: check_results 2000 / blog_lifecycle 85 / standard_rules 20

## 남긴 것

- 요약 수치 영속 저장(54/22/9 스냅샷) 미구현 — 컬럼 추가 승인 시 별도 작업
- scheduler 재시작 전까지 daily sync 미가동 (수동 재시작 필요)
- validate_schema_pr.py / c08_staging.py 미커밋 (별도 태스크 산출물)

상세: /tmp/schema_registry_implementation_result.md
