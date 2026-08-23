# WL-20260822 — Stale-Refresh (Track A Exp1)

## 작업
check_results fail 행 중 소스가 이미 준수한 stale 행을 `pass`로 갱신 (대시보드 정확도 개선).

## 범위
- 대상 체커: FM-DRAFT(30), FM-FEATUREIMAGE(4), THUMBNAIL-01(10) — status='fail'
- 제외: FM-MISSINGKEYS(parser bug), PARSER_BUG_BLOGS(adventure-hugo), GATE_FILTERED(hotel/airport/restaurant)
- 쿼리 스코프: 44행

## 4단계 프로토콜
1. 사전카운트: 44 (max updatable), exclusions 0
2. 백업: ops_dashboard/ops.db.bak_20260822_215601, /tmp/stale_refresh_before.20260822_215601.json (44행 스냅샷)
3. 실행: 라이브 스케줄러 정지(launchd unload + pkill) → 40 stale 행 status='pass' UPDATE
4. 사후대조: 스코프 fail 44→4 (잔여 4 = 실제 FM-FEATUREIMAGE 위반, 정상 보존)

## 재검사 결과
- stale_confirmed=40 (FM-DRAFT 30 전부, THUMBNAIL-01 10 전부)
- still_failing=4 (FM-FEATUREIMAGE: issue-techpawz, sector, stock, techpawz — 실제 broken featureimage, 갱신 안 함)

## 영구 보존
- content.db 실발행 행: 해당없음(대상 DB=ops.db)
- 스케줄러 정지 확인: scheduler.py / ops_dashboard.app / watchdog 모두 STOPPED

## 복구
- 롤백: ops.db.bak_20260822_215601 복원 OR stale_ids를 다시 'fail'로 UPDATE
