# MAN-013 pending_fixes 자동 승인 규칙

- ID: MAN-013
- Created: 2026-08-25
- Scope: `ops_dashboard/ops.db:pending_fixes` 의 `fix_r08`/`fix_r12` 등 반복 패턴 auto_approve 및 신규 fix manual review

## 1. 정의 및 범위
- 대상: `pending_fixes` 테이블 (`status`: proposed/rejected/resolved, 현재 47/1/62)
- 반복 fix: 과거 동일 `problem_id`+`blog_id`+`fix_type` 조합이 3회 이상 `resolved` 된 패턴 (예: `fix_r08` TABLE_QUALITY, `fix_r12` P02 threshold)
- 신규 fix: 최초 등장 `fix_type` 또는 `problem_id` 신규 조합 — 48h 내 manual review 필수

## 2. 탐지 조건
- `SELECT fix_type, COUNT(*) FROM pending_fixes WHERE status='resolved' GROUP BY fix_type HAVING COUNT(*)>=3;` → auto_approve 후보
- `SELECT status, COUNT(*) FROM pending_fixes GROUP BY status;` → proposed 47건 모니터링
- 반복 패턴 판정: `fix_history` 또는 `pending_fixes` 에서 동일 `blog_id`+`problem_id` 3회 연속 `proposed→resolved` 이력

## 3. 자동 조치
- auto_approve 대상: `fix_r08` (TABLE_QUALITY cols>5), `fix_r12` (임계값 조정) 등 — 과거 검증 완료된 기계적 수정은 `approved_at=datetime('now')` 자동 갱신, `auto_approved=1` 플래그 기록
- 자동 승인 시 대시보드 `pending_fixes` 에서 `status='resolved'` 로 즉시 전환, `applied_at` 기록
- 자동 승인 제외: `pipeline_path` 변경, `config/blogs.d/*.yaml` 구조 변경, `standard_rules` severity 변경 등 — 항상 manual

## 4. 수동 조치 (에스컬레이션)
- 신규 fix: `proposed` 생성 후 48h 내 리뷰 — 승인/거절 미결정 시 `rejected` 자동 전환 안 함, 유지 후 재알림
- 리뷰 절차:
  1. `SELECT * FROM pending_fixes WHERE status='proposed' ORDER BY created_at DESC LIMIT 10;`
  2. `ops_dashboard/fix_history.py` 에서 제안 diff 확인
  3. `APPROVE=1` 환경변수로 승인 또는 `REJECT` 사유 기록
- 에스컬레이션: 48h 초과 미검토는 대시보드 WARNING 배지 + Telegram daily digest 에 포함

## 5. 예방 규칙
- 동일 fix 3회 반복 후에도 재발 시 — fix 자체가 임시방편이므로 근본 원인 분석 필수 (ex: TABLE_QUALITY 반복이면 writer 프롬프트 수정)
- `pending_fixes` 에 ` UNKNOWN` 관련 fix 는 생성 금지 — MAN-011 로 즉시 처리, fixes 큐에 넣지 않음
- auto_approve 는 `fix_type` 단위가 아니라 `fix_type`+`blog_id` 단위로 판단 — 블로그별 특성 고려

## 6. 검증 방법
```bash
sqlite3 /Users/twinssn/Projects/5000/ops_dashboard/ops.db \
  "SELECT status, COUNT(*) FROM pending_fixes GROUP BY status;"
# 기대: proposed 47, resolved 62, rejected 1 (auto_approve 후 proposed 감소)

sqlite3 /Users/twinssn/Projects/5000/ops_dashboard/ops.db \
  "SELECT fix_type, status, COUNT(*) FROM pending_fixes GROUP BY fix_type, status ORDER BY fix_type;"

# auto_approve 시뮬레이션 (dry-run)
sqlite3 /Users/twinssn/Projects/5000/ops_dashboard/ops.db \
  "SELECT fix_type FROM pending_fixes WHERE status='resolved' GROUP BY fix_type HAVING COUNT(*)>=3;"
# 후보 fix_type 목록 확인 후 적용
```
