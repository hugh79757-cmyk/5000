#!/bin/bash
# Analytics + Scheduler Watchdog — 매 30분마다
# 1. scheduler death 감지 (4h 이상 로그 갱신 없음) → 텔레그램 알림 (우선)
# 2. analytics 수집 미실행 감지 (8h+) → 강제 재실행

cd /Users/twinssn/Projects/5000
LOG_FILE="/Users/twinssn/Projects/5000/logs/analytics_watchdog.log"
TS=$(date '+%Y-%m-%d %H:%M:%S')

# ── 1. Scheduler death 감지 (우선순위 a: PID 생존 확인) ──
# scheduler.log mtime은 Bluefin/Pika에서 갱신 안 될 수 있으므로
# 프로세스 테이블(pgrep)에서 scheduler.py 생존 여부를 직접 확인.
SCHED_DEATH_MINUTES=240

SCHED_PID=$(pgrep -f "scheduler.py" 2>/dev/null | head -1)
if [ -n "$SCHED_PID" ]; then
    # PID 생존 확인 → 정상
    echo "[$TS] ✅ 스케줄러 정상 (PID $SCHED_PID 생존)" >> "$LOG_FILE"
else
    # PID 없음 → 차선(b): error.log mtime으로 death 확인
    # PID와 error.log 둘 다 죽음 신호면 확정, error.log만 살아있으면 오탐 가능성
    ERROR_LOG="/tmp/5000-scheduler.error.log"
    if [ -f "$ERROR_LOG" ]; then
        ERROR_MTIME=$(stat -f %m "$ERROR_LOG" 2>/dev/null || echo 0)
        NOW_EPOCH=$(date +%s)
        ERROR_AGE_MINUTES=$(( (NOW_EPOCH - ERROR_MTIME) / 60 ))
        if [ "$ERROR_AGE_MINUTES" -gt "$SCHED_DEATH_MINUTES" ]; then
            # PID도 없고 error.log도 오래됨 → 확정 death
            ALB="$HOME/.env.common"
            if [ -f "$ALB" ]; then
                export $(grep -v '^#' "$ALB" | xargs)
            fi
            if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
                MSG="🚨 [Watchdog] 5000 스케줄러 death 감지\n"
                MSG+="• PID 생존: 없음 (pgrep scheduler.py 결과 없음)\n"
                MSG+="• error.log 최종 갱신: $(date -r $ERROR_MTIME '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo '알 수 없음')\n"
                MSG+="• 경과 시간: ${ERROR_AGE_MINUTES}분 (임계: ${SCHED_DEATH_MINUTES}분)\n"
                MSG+="• 조치: launchctl list | grep scheduler 로 상태 확인 후 launchctl load ~/Library/LaunchAgents/com.5000.scheduler.plist"
                curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
                    -d "chat_id=$TELEGRAM_CHAT_ID" \
                    -d "text=$(echo -e "$MSG" | sed 's/"/\\"/g')" \
                    -d "parse_mode=Markdown" > /dev/null 2>&1
                echo "[$TS] 🚨 스케줄러 death 알림 발송 (PID 없음, error.log ${ERROR_AGE_MINUTES}분 경과)" >> "$LOG_FILE"
            else
                echo "[$TS] ⚠️ TELEGRAM_BOT_TOKEN/CHAT_ID 미설정 — death 알림 생략" >> "$LOG_FILE"
            fi
        else
            # PID는 없지만 error.log는 최근 갱신 → launchd 재시작 중 or 일시적 소실
            echo "[$TS] ⚠️ 스케줄러 PID 없음, error.log는 최근 갱신 (${ERROR_AGE_MINUTES}분 전) — 재시작 추정 (알림 생략)" >> "$LOG_FILE"
        fi
    else
        # PID 없고 error.log도 없음 → 부정할 수 없는 death
        ALB="$HOME/.env.common"
        if [ -f "$ALB" ]; then
            export $(grep -v '^#' "$ALB" | xargs)
        fi
        if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
            MSG="🚨 [Watchdog] 5000 스케줄러 death 감지\n"
            MSG+="• PID 생존: 없음\n"
            MSG+="• error.log: 없음 (파일 부재)\n"
            MSG+="• 조치: launchctl list | grep scheduler 로 상태 확인 후 launchctl load ~/Library/LaunchAgents/com.5000.scheduler.plist"
            curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
                -d "chat_id=$TELEGRAM_CHAT_ID" \
                -d "text=$(echo -e "$MSG" | sed 's/"/\\"/g')" \
                -d "parse_mode=Markdown" > /dev/null 2>&1
            echo "[$TS] 🚨 스케줄러 death 알림 발송 (PID 없음, error.log 부재)" >> "$LOG_FILE"
        else
            echo "[$TS] ⚠️ TELEGRAM_BOT_TOKEN/CHAT_ID 미설정 — death 알림 생략" >> "$LOG_FILE"
        fi
    fi
fi

# ── 2. Analytics 수집 미실행 감지 (기존 로직) ──
LAST_LOG=$(tail -50 /Users/twinssn/Projects/5000/logs/analytics_collect.log 2>/dev/null | grep "완료" | tail -1)
if echo "$LAST_LOG" | grep -q "완료"; then
    LAST_TS=$(echo "$LAST_LOG" | awk '{print $1" "$2}')
    NOW_EPOCH=$(date +%s)
    LAST_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST_TS" +%s 2>/dev/null || echo 0)
    DIFF=$(( (NOW_EPOCH - LAST_EPOCH) / 3600 ))
    if [ "$DIFF" -lt 8 ]; then
        : # analytics 정상
    fi
fi

# 8시간 이상 미실행 → 강제 실행
echo "[$TS] ⚠️ 수집 미실행 감지 (8h+), 강제 실행" >> "$LOG_FILE"
bash /Users/twinssn/Projects/5000/scripts/collect_analytics.sh
echo "[$TS] ✅ Watchdog 복구 완료" >> "$LOG_FILE"
