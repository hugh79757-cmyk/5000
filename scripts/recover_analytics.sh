#!/bin/bash
# recover_analytics.sh — Phase 0 Task 2 안전 수집 복구 스크립트
#
# 요구사항 (Phase 0 Implementation Plan Task 2):
#   - 전체 실행과 API 단계별 hard timeout
#   - exit code 전파
#   - stderr 보존
#   - cleanup trap
#   - 동시 실행 방지 (flock)
#
# 범위: 계정 1·2만 (계정3 / 대규모 backfill 금지 — Task 2 Out of Scope)
# 실제 수집은 analytics_collector 를 호출하며 OAuth auto-refresh 는 허용.
# 토큰 값은 출력하지 않음 (로그에는 단계 성공/실패/timeout 만 기록).
set -uo pipefail

# ---------- 동시 실행 방지 (macOS 호환: mkdir 는 atomic) ----------
LOCKDIR="/tmp/recover_analytics.lock"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: 이미 실행 중 — 중단 (exit 99)" >&2
  exit 99
fi

# ---------- 설정 ----------
PROJECT_ROOT="/Users/twinssn/Projects/5000"
cd "$PROJECT_ROOT" || { echo "cd 실패: $PROJECT_ROOT" >&2; exit 1; }
LOG="$PROJECT_ROOT/logs/recover_analytics.log"
PY="/opt/homebrew/bin/python3"
API_TIMEOUT=600          # 각 API 단계 hard timeout (초)
DAYS_GA4=3
DAYS_GSC=1
DAYS_ADSENSE=3

# ---------- cleanup trap (exit code 전파) ----------
RUN_RC=0
cleanup() {
  local rc=${1:-$RUN_RC}
  rmdir "$LOCKDIR" 2>/dev/null
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] cleanup: exit=$rc" >> "$LOG"
  exit "$rc"
}
trap 'cleanup $?' EXIT INT TERM

# ---------- 단계 실행 래퍼 ----------
# 인자: <STEP_NAME> <cmd...>
# DRYRUN=1 이면 실제 수집을 수행하지 않고 단계 성공만 기록 (테스트/검증용)
if [ "${RECOVER_DRYRUN:-0}" = "1" ]; then
  run_step() {
    local name="$1"; shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP[$name] DRYRUN skip (no API call)" >> "$LOG"
    return 0
  }
else
  run_step() {
  local name="$1"; shift
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP[$name] start" >> "$LOG"
  local rc=0
  timeout "$API_TIMEOUT" "$@" >> "$LOG" 2>&1 || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP[$name] OK" >> "$LOG"
  elif [ "$rc" -eq 124 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP[$name] TIMEOUT($API_TIMEOUT) — 강제 종료" >> "$LOG"
    RUN_RC=124
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP[$name] FAIL(rc=$rc)" >> "$LOG"
    RUN_RC=$rc
  fi
  return "$rc"
  }
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ===== recover_analytics start (timeout=${API_TIMEOUT}s/step) =====" >> "$LOG"

# GA4 (계정1·2 루프는 analytics_collector 내부에서 처리)
run_step "GA4" "$PY" -c \
  "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().collect_ga4(days=$DAYS_GA4)"

# GSC (siteUrl 목록은 analytics_collector 가 관리)
run_step "GSC" "$PY" -c \
  "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().collect_gsc(days=$DAYS_GSC)"

# AdSense (account [1,2] 만 — 계정3 금지)
run_step "ADSENSE" "$PY" -c \
  "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().collect_adsense(days=$DAYS_ADSENSE)"

# Efficiency (GSC/GA4 기반 파생 지표)
run_step "EFFICIENCY" "$PY" -c \
  "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().compute_efficiency()"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ===== recover_analytics done (overall_rc=$RUN_RC) =====" >> "$LOG"
exit "$RUN_RC"
