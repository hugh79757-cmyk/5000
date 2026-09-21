# Worklog: WL-20260921-O2-fail_checks-forensic

**Date**: 2026-09-21
**Scope**: fail_checks 455 포렌식 (O-2) — 5대 검사기 226건 타임라인 + 이관 이벤트 대조 + pick DB open 결함 근인 분석
**Constraint**: 읽기 전용 분석 (DB mutation 없음) — 파괴적 작업 아님, 프로토콜 1-2단계만 적용

---

## Pre-Count (분석 대상)
- check_results 테이블: status='fail' 총 465건 (2026-09-19~20)
- 5대 검사기: c08_live_file_mismatch(64) + s01_uniqueness_ratio(63) + s02_structural_similarity(47) + s03_unique_data_points(31) + semantic(21) = **226건**
- pick DB open 에러: scheduler.log 5건 (compare/rank/pick/appliance/baby-hugo, 2026-09-20 09:18)

## Backup
- 분석 전 ops_dashboard/ops.db 복사 불필요 (SELECT만 수행)
- 원본 로그 보존: logs/scheduler.log, .planning/forensics/O-2-fail_checks-455-forensic.md

## Execution
1. SQL 쿼리로 5대 검사기 first_seen/last_seen 집계
2. 이관 이벤트 3개(T-커밋 10a13de45, Flip 4697b429b, Pick정지 3f0fa87d5) 시점과 대조
3. pick DB open 에러 코드 경로 추적: shared/candidate_availability.py:113
4. car.db 파일 상태 확인 (존재, 권한, 크기)
5. WAL 락 경합 가설 수립 및 5대 검사기와의 동근 여부 판정

## Post-Verification
- [x] 이관 유발 검사기 결함: **0건** (타임라인 완전 분리 — Flip 12:48 → 첫 fail 15:21, 2.5h 갭)
- [x] 5대 검사기 226건 전량 ETAP runner 정기 체크 라운드(15:21~23:57)와 일치
- [x] pick DB open 결함: car.db WAL 락 경합 (동시 catchup 5개, timeout 5s) — 5대 검사기와 독립적
- [x] 원본 SQL 출력 및 로그 증빙 동봉 (.planning/forensics/O-2-fail_checks-455-forensic.md)

## Logs
- logs/destructive_2026-09-20.log (라인 추가)
- .planning/forensics/O-2-fail_checks-455-forensic.md (전체 리포트)

## 결론
**이관 유발 검사기 결함 0건 확인** — O-2 종결. pick DB open 결함은 별도 인프라 이슈로 분류 (checker timeout/backoff 패치 필요).