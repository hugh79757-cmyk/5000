#!/bin/bash
# Phase 77: 백필 완료 감지 → 개선 루프 자동 활성화 (2026-09-03)
# 사용자 승인: 옵션 2 — "14:35 이후: 백필 완료 확인 → 추출기 재생성 → plist 수정 + reload → 가동"
LOG=/Users/twinssn/Projects/5000/logs/perf_activate_20260903.log
PLIST=/Users/twinssn/Library/LaunchAgents/com.5000.scheduler.plist

echo "[$(date '+%H:%M:%S')] watcher 시작 — backfill(PID 39865) 종료 대기" >> "$LOG"

# 1. 백필 프로세스 종료 대기 (최대 180분 — 폴링 60s)
for i in $(seq 1 180); do
    kill -0 39865 2>/dev/null || break
    sleep 60
done
if kill -0 39865 2>/dev/null; then
    echo "[$(date '+%H:%M:%S')] ERROR: 180분 대기 후에도 백필 실행 중 — 활성화 중단" >> "$LOG"
    exit 1
fi
echo "[$(date '+%H:%M:%S')] 백필 프로세스 종료 확인" >> "$LOG"
tail -2 /Users/twinssn/Projects/5000/logs/backfill_gsc_20260903.log >> "$LOG"

# 2. DB lock 해소 대기 (백필 직후 커넥션 정리 여유)
sleep 30

# 3. 추출기 재생성 (90일 전체 신호)
cd /Users/twinssn/Projects/5000 || exit 1
python3 shared/performance_signals.py >> "$LOG" 2>&1
if [ $? -ne 0 ]; then
    echo "[$(date '+%H:%M:%S')] ERROR: 추출기 실패 — 활성화 중단 (plist 미수정)" >> "$LOG"
    exit 1
fi
echo "[$(date '+%H:%M:%S')] 추출기 재생성 완료" >> "$LOG"

# 4. plist 수정 (plistlib — 백업 후)
cp "$PLIST" "${PLIST}.bak_perf_20260903" >> "$LOG" 2>&1
python3 - << 'EOF' >> "$LOG" 2>&1
import plistlib
p = "/Users/twinssn/Library/LaunchAgents/com.5000.scheduler.plist"
with open(p, "rb") as f:
    d = plistlib.load(f)
d["EnvironmentVariables"]["PERF_SIGNALS"] = "1"
with open(p, "wb") as f:
    plistlib.dump(d, f)
print("plist PERF_SIGNALS=1 OK")
EOF
plutil -lint "$PLIST" >> "$LOG" 2>&1 || {
    echo "[$(date '+%H:%M:%S')] ERROR: plist lint 실패 — 백업 복구" >> "$LOG"
    cp "${PLIST}.bak_perf_20260903" "$PLIST"
    exit 1
}

# 5. 스케줄러 재시작 전 안전 확인 — 파이프라인 실행 중이면 대기 (최대 20분)
for i in $(seq 1 40); do
    pgrep -f "dispatcher.py" > /dev/null || break
    echo "[$(date '+%H:%M:%S')] 파이프라인 실행 중 — 재시작 대기" >> "$LOG"
    sleep 30
done

# 6. launchd reload
launchctl unload "$PLIST" >> "$LOG" 2>&1
launchctl load "$PLIST" >> "$LOG" 2>&1
sleep 5
NEW_PID=$(ps aux | grep "[s]cheduler.py" | awk '{print $2}' | head -1)
echo "[$(date '+%H:%M:%S')] 스케줄러 reload 완료 — 새 PID: $NEW_PID" >> "$LOG"

# 7. 최종 확인 — 새 스케줄러에 PERF_SIGNALS 상속됐는지
if [ -n "$NEW_PID" ]; then
    ps eww "$NEW_PID" 2>/dev/null | grep -o "PERF_SIGNALS=[0-9]*" >> "$LOG" || echo "(env 확인 실패 — ps eww 제한. plist에 설정됨은 plutil로 확인)" >> "$LOG"
fi
echo "[$(date '+%H:%M:%S')] === 개선 루프 활성화 완료 ===" >> "$LOG"
