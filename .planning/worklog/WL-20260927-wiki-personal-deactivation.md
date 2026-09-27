# WL-20260927 — wiki-personal 비활성화 (Worker 100K 한도 대응)

## 원인
- aikeep24-web 64,942/75,018 invocations (86%). 드라이버 = wiki-personal 연속 임베딩 루프.
- 메커니즘: ingest.py 상시 기동 → wiki/*.md mtime 갱신 → 120초 루프가 50~75파일/배치 재임베딩 → 배치당 52+ Worker POST, embedded=0.
- 증폭: SKIP_D1_CACHE=1, Cache HIT도 invocation 카운트.

## 조치
- launchd bootout 8 job (embed-continuous, ingest-continuous, dashboard, recoveries 등). plist 파일은 삭제 안 함.
- ingest PID 1051은 bootout TERM으로 종료 확인 (kill 불필요).
- 로그: logs/destructive_2026-09-27.log

## 사후
- 잔여 프로세스 0, loaded job 0, plist 파일 보존.
- Worker 호출 감소는 내일 GraphQL workersInvocationsAdaptive로 확인 필요.

## 재활성화
- launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<plist> (필요 시점에만).
- 권장: 재활성화 전 SKIP_D1_CACHE 제거 + sleep 상향 먼저 적용.
