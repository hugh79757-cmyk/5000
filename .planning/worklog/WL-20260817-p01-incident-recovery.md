# WL-20260817-p01-incident-recovery

> 날짜: 2026-08-17 / 연관: commit 899ef413c (worktree fix/p01-runtime-normalization), 운영 HEAD a369cb1fa / 상태: 완료

## 파괴적 작업 목록
| 시각(+07) | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 00:46 | scheduler 정상 재시작 1회 (PR2 활성화) | kill -15 16974 → launchd KeepAlive 기동 28402 | scheduler 1개 | 해당없음(launchd KeepAlive) | 1개 유지 | heartbeat 정상 |
| 00:48 | ops.db PR2 스키마 마이그레이션 | ensure_schema() 수동 호출 | events 1721행 | /tmp/ops.db.pr2_migration_bak_20260817_004830 | resource_health 생성(0행), PR2 컬럼 6/6, events 1721행 유지 | 행 감소 0 |
| 00:53 | P01 차단 설정 + reason 보정 + P34 open | set_incident_retry_blocked + raw SQL UPDATE(3행) + record_retry_amplification(3건) | open P01 3행, open P34 0건 | /tmp/ops.db.p01_block_bak_20260817_005313 | P01 3행 retry_blocked=1 reason='no_topics', P34 3건 open, events 1721 유지 | 행 감소 0 |
| 01:11 | scheduler 정상 재시작 1회 (hotfix 반영) | kill -15 28402 → launchd KeepAlive 기동 98143 | scheduler 1개 | 해당없음(launchd KeepAlive) | 1개 유지 | heartbeat 정상 |
| 01:11 | 운영 코드 교체 (hotfix 2파일) | worktree 파일 → 운영 복사 | dispatcher.py / publish_error_events.py clean | /tmp/p01_hotfix_bak_20260817_011137, /tmp/p01_hotfix_bak_20260817_011128 | md5 일치 확인(53f356..., 6e624b...) | git diff 없음(복사 후 clean) |

## 4단계 프로토콜 이행
1. 사전 카운트: 각 작업 직전 상태를 위 표 사전카운트에 기록. P01 보정은 open incident 3행만 대상(blog_id 3개 한정).
2. 되돌림 수단: ops.db 2종 백업(004830/005313) + 코드 백업(011137/011128) — rollback 시 백업 복원 또는 UPDATE 역방향.
3. 실행: 승인 범위(사용자 승인 1~8) 내에서만. watch Dog 미건드림(42575 유지), kill -9 미사용, DB 행 삭제 없음, push 없음.
4. 사후 대조: events 총행 1721 유지(증가분: P34 3건 open + P01 3행 UPDATE — 행 삭제 0). content.db 미접촉(source='' 실발행 보존과 무관).

## 결과 / 보존 대상 확인
- publish_error_events 총행: 1721 → 1721 + (신규 기록분은 scheduler 정규 실행 시에만) — 삭제 0.
- P01 3행: retry_blocked=1, reason='no_topics' (차단 SSOT 반영).
- P34 3행: open, retry_blocked=1 (retry_amplification).
- resource_health: 생성(rows 0 — 06:30 daily_refresh부터 기록 예정).
- scheduler: 재시작 후 정확히 1개(98143), heartbeat 정상 갱신, 신규 runtime error 0.

## 잔존 위험
- 기존 incident_key(legacy reason='' 경로)와 신규 키(stage=reason)가 분리되어, 정규 schedule 실패 시 새 unblocked P01 행이 쌓임 — get_catchup_retry_state의 blocked 우선 조회(commit 899ef413c)로 차단은 유지되나, 발생 행 증가는 known ceiling.
- 06:30 daily_refresh / 07:00 catchup / 07:12·07:18 정규 schedule 실패 검증은 시간 대기 항목 (이 세션에서 미확인).
- resource_health rows 0 → P33 root 판정은 daily_refresh 기록 후에만 가능.

## 감사 로그
- logs/destructive_2026-08-17.log에 4건 append (PR2 마이그레이션, P01 차단, 코드 교체 2건).