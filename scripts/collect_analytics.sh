#!/bin/bash
# Analytics daily collection (GA4 + GSC + AdSense + Efficiency)
# Runs every 6 hours via launchd (com.5000.analytics.plist)
#
# 안정화 (Phase 0 Task 2.5):
#  - 전체 및 단계별 hard timeout (SSL/DNS 무한 대기 차단)
#  - exit code 전파 (개별 source 실패가 전체 rc에 반영)
#  - stderr 보존 (>> LOG_FILE 2>&1)
#  - mkdir 기반 동시 실행 방지 (analytics_common.sh)
#  - 원자적 heartbeat/status JSON 갱신 (watchdog이 로그파일명 아닌 이걸 기준으로 판단)
#
# 인증/권한 오류(rc=23, stderr 마커 ANALYTICS_AUTH_ERROR)는 재시도하지 않음.
# 일시 네트워크/DNS 오류는 analytics_collector.retry 가 bounded backoff로 처리.

set -uo pipefail
cd /Users/twinssn/Projects/5000
source scripts/analytics_common.sh

TS=$(date '+%Y-%m-%d %H:%M:%S')
RUN_ID=$(date '+%Y%m%d_%H%M%S')_$$
LOG_FILE="logs/analytics_collect.log"
PY="/opt/homebrew/bin/python3"
API_TIMEOUT=600   # 각 source 단계 hard timeout (초)

# ── 동시 실행 방지 ──
if ! acquire_lock; then
  echo "[$TS] SKIP: 이미 실행 중 (lock=$_ANALYTICS_LOCKDIR)" >> "$LOG_FILE"
  exit 99
fi
trap 'release_lock' EXIT INT TERM

echo "[$TS] === Analytics 수집 시작 (run_id=$RUN_ID) ===" >> "$LOG_FILE"

# 시작 상태 초기화 (모든 source running)
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
}" || echo "[$TS] ⚠️ status 갱신 실패 (계속)" >> "$LOG_FILE"

OVERALL_RC=0

# 단계 실행 래퍼: timeout + exit code 수집 + heartbeat 갱신
# $1=source명  $2=python 표현식
run_source() {
  local name="$1"; shift
  local start; start=$(date '+%Y-%m-%d %H:%M:%S')
  local rc=0
  /opt/homebrew/bin/timeout "$API_TIMEOUT" "$PY" -c "$@" >> "$LOG_FILE" 2>&1 || rc=$?
  local end; end=$(date '+%Y-%m-%d %H:%M:%S')
  local st
  if [ "$rc" -eq 0 ]; then
    st="ok"
  elif [ "$rc" -eq 124 ]; then
    st="timeout"
    OVERALL_RC=124
  elif [ "$rc" -eq 23 ]; then
    st="auth_error"   # 재시도하지 않음 (분류만)
    OVERALL_RC=23
  else
    st="fail"
    [ "$OVERALL_RC" -eq 0 ] && OVERALL_RC=$rc
  fi
  update_status "{
    'sources': {
      '$name': {
        'status': '$st',
        'exit_code': $rc,
        'started': '$start',
        'finished': '$end'
      }
    }
  }" || echo "[$TS] ⚠️ $name status 갱신 실패" >> "$LOG_FILE"
  echo "[$TS] $name → $st (rc=$rc)" >> "$LOG_FILE"
  return "$rc"
}

run_source "ga4" "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().collect_ga4(days=3)"
run_source "gsc" "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().collect_gsc(days=1)"
run_source "adsense" "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().collect_adsense(days=3)"
run_source "efficiency" "from shared.analytics_collector import AnalyticsCollector; AnalyticsCollector().compute_efficiency()"

# 성공 시 last_success_ts 갱신
if [ "$OVERALL_RC" -eq 0 ]; then
  update_status "{ 'last_success_ts': '$TS', 'overall_exit_code': 0 }"
  echo "[$TS] === Analytics 수집 완료 (성공, rc=0) ===" >> "$LOG_FILE"
else
  update_status "{ 'overall_exit_code': $OVERALL_RC }"
  echo "[$TS] === Analytics 수집 종료 (rc=$OVERALL_RC) ===" >> "$LOG_FILE"
fi

exit "$OVERALL_RC"
