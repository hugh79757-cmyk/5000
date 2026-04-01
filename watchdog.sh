#!/bin/bash
# 5000 Scheduler Watchdog
# heartbeat 파일이 15분 이상 갱신되지 않으면 텔레그램 알림 + 재시작

HB_FILE="/Users/twinssn/Projects/5000/logs/heartbeat"
LOG_FILE="/Users/twinssn/Projects/5000/logs/watchdog.log"
PLIST="com.5000.scheduler"
MAX_AGE=900  # 15분 (초)

now=$(date +%s)
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"; }

# heartbeat 파일 존재 확인
if [ ! -f "$HB_FILE" ]; then
    log "WARN: heartbeat 파일 없음 — 스케줄러 미시작 또는 첫 실행"
    exit 0
fi

last_hb=$(cat "$HB_FILE" 2>/dev/null || echo "0")
age=$((now - last_hb))

if [ "$age" -gt "$MAX_AGE" ]; then
    log "ALERT: heartbeat ${age}초 전 — 스케줄러 중단 감지"
    
    # 텔레그램 알림
    source /Users/twinssn/Projects/5000/.env
    MSG="🚨 스케줄러 중단 감지%0Aheartbeat: ${age}초 전%0A재시작 시도 중..."
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}&text=${MSG}&parse_mode=HTML" > /dev/null 2>&1
    
    # 스케줄러 재시작
    launchctl unload ~/Library/LaunchAgents/${PLIST}.plist 2>/dev/null
    sleep 2
    launchctl load ~/Library/LaunchAgents/${PLIST}.plist
    log "INFO: 스케줄러 재시작 완료"
else
    log "OK: heartbeat ${age}초 전 — 정상"
fi
