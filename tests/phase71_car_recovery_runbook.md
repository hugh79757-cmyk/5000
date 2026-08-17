# CAP Car `no_topics` 복구 Runbook (Phase 71 / Critical Path M2)

> 운영 절차 문서. 실제 실행은 `APPROVE_PHASE71_CAR_RECOVERY` 승인 후 1회만.
> 범위: PLAN-CAR-RECOVERY.md Task 3 (runbook 작성만). Task 1·2는 이미 구현·검증됨.

## 대상 증상
- `deal` / `ev` / `guide` (car pipeline)가 `no_topics` 반환, 발행 0건
- `car.db` `topics` `status='pending'` = 0
- `daily_refresh` 정상 완료 기록 없음 (2026-08-06 이후)
- `catchup_missed`가 `no_topics` blog를 반복 재디스패치 → `failure_count` 증폭

## 원인 (확정)
- 후보 토픽 고갈 (`pending=0`) → 정상 **WAITING** 상태 (cooldown 아님)
- `daily_refresh`가 carisyou.com 신규/가격 데이터를 갱신하지 못해 `pending` 보충 안 됨

## 진단 (읽기 전용)
1. `sqlite3 data/car.db "SELECT count(*) FROM topics WHERE status='pending';"` → 0 이면 고갈
2. `sqlite3 ops_dashboard/ops.db "SELECT resource_id,last_at,state FROM resource_heartbeats WHERE resource_id LIKE 'car%' ORDER BY last_at DESC LIMIT 5;"`
3. `grep -E 'deal-hugo|ev-hugo|guide-hugo' data/failure_count.json` → catchup 재시도 누적 확인

## 복구 절차 (승인 후 1회만)
1. `python3 pipelines/car/daily_refresh.py` 수동 1회 실행 (timeout 3600s, heartbeat 자동)
2. 실행 후 `pending` 카운트 재확인 → `>0` 이면 정상
3. `pending>0` 이면 다음 스케줄러 디스패치가 자동 재개 (`no_topics` blog는 catchup에서 제외됨)
4. `pending` 여전히 0 → 데이터 소스(carisyou 스크레이프) 장애 → 별도 조사 (이 runbook 범위 밖)

## 가드레일 (이미 구현·검증됨)
- `scheduler._run_car_refresh`: timeout(3600s) + 30s heartbeat + `returncode!=0`/timeout 시 `SIGTERM`→`SIGKILL` child 정리
- `scheduler._catchup_missed`: `no_topics`/`no_topic` blog는 catchup에서 제외, 재시작 후에도 `ops.db`(`catchup_attempts`)로 억제 상태 영속 → 폭주 없음
- 위 진단만으로 판단, 운영 DB/외부 API/실제 발행 접근 없음

## 금지
- PLAN.md W1~W5 실행 금지
- Phase 69 incident/taxonomy/Dashboard 수정 금지
- 자동수선/자동재배포 금지
- Git push 금지
