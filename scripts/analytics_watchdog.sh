#!/bin/bash
# Analytics Watchdog — 매 30분마다 checks if collection ran in last 8h
# If not, forces a re-run. Adds auto-recovery for token failures.

cd /Users/twinssn/Projects/5000
LOG_FILE="/Users/twinssn/Projects/5000/logs/analytics_watchdog.log"
TS=$(date '+%Y-%m-%d %H:%M:%S')

# Check last successful collection
LAST_LOG=$(tail -50 /Users/twinssn/Projects/5000/logs/analytics_collect.log 2>/dev/null | grep "완료" | tail -1)
if echo "$LAST_LOG" | grep -q "완료"; then
    LAST_TS=$(echo "$LAST_LOG" | awk '{print $1" "$2}')
    NOW_EPOCH=$(date +%s)
    LAST_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST_TS" +%s 2>/dev/null || echo 0)
    DIFF=$(( (NOW_EPOCH - LAST_EPOCH) / 3600 ))
    if [ "$DIFF" -lt 8 ]; then
        exit 0
    fi
    fi

# 8시간 이상 미실행 → 강제 실행
echo "[$TS] ⚠️ 수집 미실행 감지 (8h+), 강제 실행" >> "$LOG_FILE"
bash /Users/twinssn/Projects/5000/scripts/collect_analytics.sh
echo "[$TS] ✅ Watchdog 복구 완료" >> "$LOG_FILE"
