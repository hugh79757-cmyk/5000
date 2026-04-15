#!/bin/bash
# 5000 Scheduler Watchdog
# heartbeat 파일이 15분 이상 갱신되지 않으면 텔레그램 알림 + 재시작

HB_FILE="/Users/twinssn/Projects/5000/logs/heartbeat"
LOG_FILE="/Users/twinssn/Projects/5000/logs/watchdog.log"
ENV_FILE="/Users/twinssn/Projects/5000/.env"
PLIST="com.5000.scheduler"
MAX_AGE=900  # 15분 (초)

now=$(date +%s)
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"; }

# .env에서 안전하게 변수 추출 (source 대신 grep)
TELEGRAM_BOT_TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' "$ENV_FILE" | head -1 | cut -d'=' -f2-)
TELEGRAM_CHAT_ID=$(grep '^TELEGRAM_CHAT_ID=' "$ENV_FILE" | head -1 | cut -d'=' -f2-)

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
    MSG="🚨 스케줄러 중단 감지%0Aheartbeat: ${age}초 전%0A재시작 시도 중..."
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}&text=${MSG}&parse_mode=HTML" > /dev/null 2>&1
    else
        log "WARN: 텔레그램 변수 없음 — 알림 스킵"
    fi
    
    # 스케줄러 재시작
    if pgrep -f "5000/scheduler.py" > /dev/null 2>&1; then
        log "WARN: 스케줄러 프로세스 존재하나 heartbeat 갱신 안 됨 — 강제 재시작"
        pkill -f "5000/scheduler.py" 2>/dev/null
        sleep 3
    fi
    launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/${PLIST}.plist 2>/dev/null
    sleep 2
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/${PLIST}.plist
    log "INFO: 스케줄러 재시작 완료"
else
    log "OK: heartbeat ${age}초 전 — 정상"
fi
