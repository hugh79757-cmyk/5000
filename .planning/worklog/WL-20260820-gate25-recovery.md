# Worklog: WL-20260820-gate25-recovery

## Operation
GATE 2.5 MINIMAL RECOVERY — analytics 수집 rc=127 근본원인 해결 + verify_gate25_runtime.sh 거짓 양성 PASS 교정 + 정규 1회 실행 관측.

## Pre-Count
- `com.5000.analytics` (정규 job): UNLOADED, launchctl exit `- 1`
- `com.5000.analytics.watchdog`: LOADED, exit 0, StartInterval=1800 (30분)
- 오늘 실행 6회 (11:40~14:10) 전부 rc=127 실패
- adsense_daily: max_date=2026-08-19, 2521행 (기준선 09:01:14 동일 = 증분 0)
- 중복 unique key: 0건, integrity_check: ok

## Backup
- `logs/launchd_state_20260820_143315.txt` (launchctl list 스냅샷)
- `scripts/collect_analytics.sh.bak_GATE25_20260820_143315`
- `scripts/verify_gate25_runtime.sh.bak_GATE25_20260820_143315`
- `logs/destructive_2026-08-20.log` (프로토콜 로그)

## Root Cause
`com.5000.analytics.watchdog.plist`에 EnvironmentVariables/PATH 미설정 → watchdog 강제수집 시 `/opt/homebrew/bin` 누락 → `collect_analytics.sh:55`의 `timeout`을 `command not found` 처리 → rc=127. (`com.5000.analytics.plist` 자체는 PATH 포함 — 정규 실행은 정상, watchdog 경로만 깨짐.)

## Execution
1. (Step1) launchctl 상태 확인 — analytics unloaded, watchdog loaded.
2. (Step2) 백업 3건 생성 + destructive 로그 초기화.
3. (Step3) `collect_analytics.sh:55` `timeout` → `/opt/homebrew/bin/timeout` (절대경로). `verify_gate25_runtime.sh` ① heartbeat 부재 시 bad, ② rc!=0 시 bad(GATE2_5_RC_FAIL), ③ DB를 yesterday 기준 비교.
4. (Step4) Fixture: `env -i` 최소 PATH에서 상대 timeout→rc=127 재현, 절대→정상, run_source 방식→rc=0. ✓ (실제 수집 없음)
5. (Step1-계속) `launchctl unload com.5000.analytics.watchdog.plist` (exit 0, 리스트에서 소멸 확인).
6. (Step4) 로컬 커밋 1 (collect_analytics.sh + verify_gate25_runtime.sh 3-section 초안).
7. (Step5 관측 중 발견) 첫 verify에서 adsense_daily 2026-08-20 0행으로 DB_FAIL. 조사: `collect_adsense()`가 `end_date=today-1` 사용 → 어제까지 수집. max_date=2026-08-19가 정상(갭 아님). ③ 체크 과도 엄격(거짓 양성) → yesterday 비교로 완화. 재실행 → PASS=7 FAIL=0 (진성 PASS). 커밋 2.
8. (Step5) `launchctl load com.5000.analytics.plist` (spurious I/O error이나 리스트에서 loaded 확인, exit 0). `launchctl start com.5000.analytics` (plist 트리거, 스크립트 직접 호출 아님)로 정규 1회 발화.
9. (Step5 결과) run `20260820_143746_43308`: `=== Analytics 수집 완료 (성공, rc=0) ===`, 4 source ok, last_success_ts=2026-08-20 14:37:46 (heartbeat 세팅), lock 정리, adsense_daily max=2026-08-19 (=yesterday, 기대치). 일부 GSC 403 사이트 스킵(persona-aikorea24 등) — 별개 권한 이슈, 미손대.

## Post-Verification
- rc=127 버그: 해결 ✓ (절대경로로 reproduction 불가)
- verify 거짓 양성: 해결 ✓ (rc!=0/heartbeat부재/yesterday 미증분 시 FAIL)
- 정규 run rc=0 + heartbeat + DB 일관성: ✓
- 백업 접근 가능·완전: YES
- 실발행 행 보존: 해당없음 (content.db 미변경)

## Logs
- `logs/destructive_2026-08-20.log` (5개 엔트리: PROTOCOL_START, UNLOAD, LOAD, START, OBSERVE_RUN)

## ⑥ 금지 준수
- 수동 수집 직접 호출: 안 함 (launchctl start만)
- Task 3 (계정3 추가): 안 함
- backfill (07-29~08-17 갭): 안 함 (Phase 0 Task 7 대상)
- GSC 403 수정: 안 함
- Phase 1 대시보드: 안 함
- git push: 안 함 (로컬 커밋만, branch _rollback_test)

## Residual Risks
- 과거 갭 2026-07-29~08-17 실제 존재 (Phase 0 Task 7 backfill 필요, 금지로 미처리)
- GSC 403 일부 사이트(persona-aikorea24 등) — 별개 권한 이슈
- watchdog unloaded 상태 유지 (정규 job만 가동) — 주기적 미수집 감시 불가. 재가동은 별도 승인.
- 절대경로 하드코딩: PATH 변경 시 깨짐 (ponytail: 단일 경로 가정, /opt/homebrew/bin 이동 시 수정 필요)
