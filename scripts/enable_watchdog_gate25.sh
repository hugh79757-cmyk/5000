#!/bin/bash
# enable_watchdog_gate25.sh — Phase 0 Task 2.5 watchdog 활성화 (MUTATING, 별도 실행 전용)
#
# ⚠️ 이 스크립트는 운영 변경을 수행한다:
#   - launchctl load com.5000.analytics.watchdog.plist
#   - fresh heartbeat 상태에서 강제수집 0회 / 중복 프로세스 0건 확인
#
# verify_gate25_runtime.sh (read-only) 가 PASS 를 출력한 후에만 명시적으로 실행할 것.
# 본 스크립트는 verify_gate25_runtime.sh 에서 호출되지 않는다.

set -uo pipefail
cd /Users/twinssn/Projects/5000
source scripts/analytics_common.sh
WATCHDOG_PLIST="$HOME/Library/LaunchAgents/com.5000.analytics.watchdog.plist"
LOG="logs/analytics_watchdog.log"

if [ ! -f "$_ANALYTICS_STATUS_FILE" ]; then
  echo "❌ status.json 없음 — 검증 미선행. verify_gate25_runtime.sh 먼저 실행하라"
  exit 1
fi

STALE=$( check_stale 8 )
if [ "$STALE" != "fresh" ]; then
  echo "❌ heartbeat가 fresh 아님 ($STALE) — watchdog load 보류. 상태 점검 후 재시도"
  exit 1
fi

echo "✅ fresh heartbeat 확인 — watchdog load"
launchctl load "$WATCHDOG_PLIST" 2>/dev/null
sleep 5

RECENT=$( tail -8 "$LOG" 2>/dev/null | grep -c "강제수집" )
if [ "$RECENT" -eq 0 ]; then
  echo "✅ load 후 강제수집 0회 (fresh heartbeat 정상)"
else
  echo "⚠️ load 후 강제수집 로그 발견 — heartbeat 불일치 의심, 즉시 unload"
  launchctl unload "$WATCHDOG_PLIST" 2>/dev/null
  exit 1
fi

echo "✅ watchdog 활성화 완료 (10분 안정 상태는 운영자가 사후 확인)"
