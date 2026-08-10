# WL-20260808-triage-classification-run-isolation

> 날짜: 2026-08-08 / 연관: Phase 69 W4.5 보정 / 상태: 완료

## 배경

W4(Phase 69)에서 auto_triage 분류 결과를 `triage_classifications` 테이블에 기록하도록
추가했다. W4 계획은 "dry-run 시 DB 쓰기 생략"을 명시했으나, 구현은
"dry-run에서도 DB 기록 동작을 확인할 수 있어야 한다"는 사용자 요구를 지키기 위해
dry-run 여부와 무관하게 항상 쓰도록 했다. 결과적으로 auto_triage가 반복 실행되면
분류 행이 반복 누적되는 잠재 오염이 있었다.

목표: dry-run 검증 동작은 유지하되 프로덕션 DB 오염을 차단. 프로덕션
`triage_classifications`에는 항상 "최신 run의 1회분"만 존재하도록 한다.

## 진단 (변경 전)

- 현재 237건 전부 `classified_at = 2026-08-08 11:21:40` 단일 타임스탬프 → **순수 1회분**.
- 반복 실행으로 인한 교차 run 중복은 아직 발생 전. 다만 (problem_id, target) 내부 중복
  (예: P14/car-hugo 9건)은 동일 run 내 서로 다른 알림 이벤트로 **정당한 중복**.
- 결론: 237건 = 정상 1회분 → 별도 정리 불필요. 이후 재실행 시 누적만 차단하면 됨.

## 파괴적 작업 목록

| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 18:34 | ops.db 스키마 마이그레이션 (ADD COLUMN run_id + idx_triage_run) | `db.init_db(ops.db)` | 237 | ops.db.bak_20260808_183421 | 237 유지, run_id 컬럼 추가 | 행수 237 보존 |
| 18:35~51 | auto_triage dry-run 2회 → replace_triage_classifications (DELETE 전행 → INSERT 현재 run) | `python3 scripts/auto_triage.py` | 237 | tag pre-w45-triagefix-2026-08-08 | run1 237 → run2 237 (증가 없음) | 최신 run_id 1종만, 구 run 0행 |

## 4단계 프로토콜 이행

1. 사전 카운트: triage_classifications 237건 (distinct classified_at 1종 = 단일 run).
2. 되돌림 수단: `ops_dashboard/ops.db.bak_20260808_183421` + git tag `pre-w45-triagefix-2026-08-08`.
3. 실행: db.py 스키마 마이그레이션 → auto_triage dry-run 2회 (replace 경로).
4. 사후 대조: 건수 237 유지 (증가 0), run_id = 최신 run 1종, 분류 분포 baseline 일치.

## 변경 사항

- `ops_dashboard/db.py`
  - `triage_classifications`에 `run_id TEXT DEFAULT ''` 컬럼 추가 (CREATE + `_alter_columns`).
  - `idx_triage_run` 인덱스 추가 (기존 DB는 `_alter_columns` 후 생성 — 컬럼 부재 실패 방지).
  - 신규 `replace_triage_classifications(conn, run_id, rows)`: 기존 전행 DELETE 후 현재 run 행만
    INSERT (원자적, 최신 1회분만 유지). `record_triage_classification` 시그니처·동작은 변경 안 함.
- `scripts/auto_triage.py`
  - `_record_classifications_db`: run_id(시각) 생성 후 `replace_triage_classifications` 호출로 교체.
    기존 텔레그램·summary·JSON 경로는 무변경.

## 검증 (모두 통과)

- dry-run 연속 2회 → 건수 237 → 237 (누적 0, 구 run 행 0).
- problem_id별 건수 W4 baseline과 정확히 일치 (excluded 69, P02 36, P14 26, leak_detected 26,
  known_issue 25, standard_compliance 21, P17 12, P15 6, unknown_failure 5, P18 4,
  dead_entity_link 3, P01 2, P06 1, P10 1).
- auto_triage dry-run exit 0 (2회).
- 텔레그램(dry-run 미발송)·summary.log·JSON 경로 무변경 (기존 코드 경로 유지).
- git diff --stat: `ops_dashboard/db.py` + `scripts/auto_triage.py` 만. 언스테이지 트랙 파일 집합 불변.

## 잔존 위험

- `record_triage_classification`(단건 raw INSERT, run 관리 없음)이 남아 있음. 현재 호출부가
  없지만, 미래에 이 함수를 그대로 쓰면 run 관리를 우회해 누적이 재발할 수 있음.
  W5에서 이 함수를 제거하거나 run_id 필수화로 정리 권장.
- auto_triage가 스케줄(launchd/cron)로 매 실행마다 테이블을 교체하므로, 과거 run 이력은
  DB에 남지 않음 (오직 logs/triage_classifications_YYYYMMDD.json으로만 보존). 의도된 "최신
  1회분만" 의미론이며, 이력 감사가 필요하면 JSON 덤프를 원천으로 사용.
