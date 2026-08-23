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

# ── 1.5. Ops Dashboard 서버 생존 확인 (보조 감시 — E4-d) ──
# launchd KeepAlive로 자동 복구되므로 death 알림은 저우선순위.
# 단, 2회 연속 PID 없음이면 launchd 자체 문제일 수 있어 알림.
OPS_PID=$(pgrep -f "ops_dashboard/app.py" 2>/dev/null | head -1)
if [ -n "$OPS_PID" ]; then
    echo "[$TS] ✅ ops_dashboard 정상 (PID $OPS_PID, 포트 5060)" >> "$LOG_FILE"
else
    # lsof로도 확인 (PID 없어졌을 때 포트 닫혔는지)
    if lsof -i :5060 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "[$TS] ⚠️ ops_dashboard PID 없으나 포트 5060 청취 중 — 재시작 중 추정 (알림 생략)" >> "$LOG_FILE"
    else
        echo "[$TS] ⚠️ ops_dashboard 사망 감지 (PID 없음, 포트 5060 미청취) — launchd 자동 복구 대기" >> "$LOG_FILE"
    fi
fi

# ── 1.6. Auto-triage 마지막 실행 시각 확인 (E4-d) ──
# 매일 1회 실행 가정, 36시간 넘으면 미실행 경고.
TRIAGE_LOG="/Users/twinssn/Projects/5000/logs/auto_triage_summary.log"
TRIAGE_MAX_HOURS=36
if [ -f "$TRIAGE_LOG" ]; then
    TRIAGE_MTIME=$(stat -f %m "$TRIAGE_LOG" 2>/dev/null || echo 0)
    NOW_EPOCH=$(date +%s)
    TRIAGE_AGE_HOURS=$(( (NOW_EPOCH - TRIAGE_MTIME) / 3600 ))
    if [ "$TRIAGE_AGE_HOURS" -gt "$TRIAGE_MAX_HOURS" ]; then
        echo "[$TS] ⚠️ auto_triage 미실행 감지 (마지막 실행 ${TRIAGE_AGE_HOURS}시간 전, 임계 ${TRIAGE_MAX_HOURS}시간) — launchd 스케줄 확인 필요" >> "$LOG_FILE"
    else
        echo "[$TS] ✅ auto_triage 최근 실행 확인 (${TRIAGE_AGE_HOURS}시간 전)" >> "$LOG_FILE"
    fi
else
    echo "[$TS] ⚠️ auto_triage 로그 파일 없음 ($TRIAGE_LOG) — 실행 이력 없음" >> "$LOG_FILE"
fi

# ── 2. Analytics 수집 미실행 감지 (heartbeat/status 파일 기반) ──
# 로그 파일명 의존 폐기: collect/recover 가 공통으로 갱신하는
# data/analytics_status.json 의 last_success_ts / overall_exit_code / lock 기준으로 판단.
source /Users/twinssn/Projects/5000/scripts/analytics_common.sh

ANALYTICS_STALE_HOURS=8
FORCED_RUN=0

# (a) 이미 실행 중이면 중복 실행 0회
if is_locked; then
    echo "[$TS] ⏸️ analytics 실행 중 (lock 존재) — 강제수집 생략 (중복방지)" >> "$LOG_FILE"
else
    # (b) stale / 실패 판단
    STALE_STATE=$(check_stale "$ANALYTICS_STALE_HOURS")
    case "$STALE_STATE" in
        fresh)
            # success timestamp 가 임계 내 → 강제수집 0회
            echo "[$TS] ✅ analytics 최근 성공 (fresh) — 강제수집 생략" >> "$LOG_FILE"
            ;;
        stale|unknown)
            # 8h+ 미실행 또는 성공 이력 없음 → 1회만 강제 실행
            echo "[$TS] ⚠️ analytics 미실행/실패 감지 ($STALE_STATE, 임계 ${ANALYTICS_STALE_HOURS}h) — 강제수집 1회" >> "$LOG_FILE"
            bash /Users/twinssn/Projects/5000/scripts/collect_analytics.sh >> "$LOG_FILE" 2>&1
            FORCED_RUN=1
            echo "[$TS] ✅ Watchdog 강제수집 완료 (forced_run=$FORCED_RUN)" >> "$LOG_FILE"
            ;;
    esac
fi
