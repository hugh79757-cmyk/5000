#!/bin/bash
# recover_analytics.sh — Phase 0 Task 2 안전 수집 복구 스크립트
#
# 안정화 (Phase 0 Task 2.5): collect_analytics.sh 와 정책 일치
#   - analytics_common.sh 공유 (잠금 + heartbeat/status)
#   - 전체 및 단계별 hard timeout
#   - exit code 전파
#   - stderr 보존
#   - cleanup trap
#   - DRYRUN 모드 (실제 API 호출 없이 단계 성공만 기록)
#
# 범위: 계정 1·2만 (계정3 / 대규모 backfill 금지 — Task 2 Out of Scope)
# 실제 수집은 analytics_collector 를 호출하며 OAuth auto-refresh 는 허용.
# 토큰 값은 출력하지 않음.
set -uo pipefail

source /Users/twinssn/Projects/5000/scripts/analytics_common.sh

PROJECT_ROOT="/Users/twinssn/Projects/5000"
cd "$PROJECT_ROOT" || { echo "cd 실패: $PROJECT_ROOT" >&2; exit 1; }
LOG="$PROJECT_ROOT/logs/recover_analytics.log"
PY="/opt/homebrew/bin/python3"
API_TIMEOUT=600
DAYS_GA4=3
DAYS_GSC=1
DAYS_ADSENSE=3

TS=$(date '+%Y-%m-%d %H:%M:%S')
RUN_ID=$(date '+%Y%m%d_%H%M%S')_recover_$$

if ! acquire_lock; then
  echo "[$TS] ERROR: 이미 실행 중 — 중단 (exit 99)" >&2
  exit 99
fi
trap 'release_lock' EXIT INT TERM

RUN_RC=0

echo "[$TS] ===== recover_analytics start (run_id=$RUN_ID, timeout=${API_TIMEOUT}s/step) =====" >> "$LOG"

update_status "{
  'last_run_id': '$RUN_ID',
  'overall_exit_code': None,
  'run_started': '$TS',
  'sources': {
    'ga4': {'status': 'running'},
    'gsc': {'status': 'running'},
    'adsense': {'status': 'running'},
    'efficiency': {'status': 'running'}
  }
}" || echo "[$TS] ⚠️ status 갱신 실패" >> "$LOG"

run_step() {
  local name="$1"; shift
  local start; start=$(date '+%Y-%m-%d %H:%M:%S')
  local rc=0
  if [ "${RECOVER_DRYRUN:-0}" = "1" ]; then
    echo "[$TS] STEP[$name] DRYRUN skip (no API call)" >> "$LOG"
    update_status "{'sources': {'$name': {'status': 'ok', 'exit_code': 0, 'started': '$start', 'finished': '$start', 'dryrun': True}}}" || true
    return 0
  fi
  timeout "$API_TIMEOUT" "$@" >> "$LOG" 2>&1 || rc=$?
  local end; end=$(date '+%Y-%m-%d %H:%M:%S')
  local st
  if [ "$rc" -eq 0 ]; then st="ok"
  elif [ "$rc" -eq 124 ]; then st="timeout"; RUN_RC=124
  elif [ "$rc" -eq 23 ]; then st="auth_error"; RUN_RC=23
  else st="fail"; [ "$RUN_RC" -eq 0 ] && RUN_RC=$rc
  fi
  update_status "{'sources': {'$name': {'status': '$st', 'exit_code': $rc, 'started': '$start', 'finished': '$end'}}}" || true
  echo "[$TS] STEP[$name] $st (rc=$rc)" >> "$LOG"
  return "$rc"
}

run_step "ga4" "$PY" -c "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().collect_ga4(days=$DAYS_GA4)"
run_step "gsc" "$PY" -c "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().collect_gsc(days=$DAYS_GSC)"
run_step "adsense" "$PY" -c "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().collect_adsense(days=$DAYS_ADSENSE)"
run_step "efficiency" "$PY" -c "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().compute_efficiency()"

if [ "$RUN_RC" -eq 0 ]; then
  update_status "{ 'last_success_ts': '$TS', 'overall_exit_code': 0 }"
else
  update_status "{ 'overall_exit_code': $RUN_RC }"
fi

echo "[$TS] ===== recover_analytics done (overall_rc=$RUN_RC) =====" >> "$LOG"
exit "$RUN_RC"
