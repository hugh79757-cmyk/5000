#!/bin/bash
# test_analytics_stabilization.sh — Phase 0 Task 2.5 안정화 로직 검증
#
# 검증 대상:
#  - analytics_common.sh: lock 획득/해제/is_locked, update_status 원자성, check_stale
#  - recover_analytics.sh: DRYRUN 모드 (실제 API 호출 없이 status 갱신, rc=0)
#  - watchdog 결정 로직: fresh→강제수집 0회, stale→1회, locked→0회
#
# 주의: 실제 수집(NETWORK API)은 호출하지 않음 (수동 수집 금지 원칙).

set -uo pipefail
PROJECT_ROOT="/Users/twinssn/Projects/5000"
cd "$PROJECT_ROOT"
source scripts/analytics_common.sh

PASS=0
FAIL=0
assert() {
  local desc="$1"; local cond="$2"
  if [ "$cond" = "0" ]; then
    echo "  ✅ $desc"
    PASS=$((PASS+1))
  else
    echo "  ❌ $desc"
    FAIL=$((FAIL+1))
  fi
}

echo "=== [1] lock acquire/release/is_locked ==="
release_lock 2>/dev/null
acquire_lock; assert "acquire_lock 성공(0)" "$?"
acquire_lock; assert "중복 acquire 실패(비0)" "$([ $? -ne 0 ]; echo $?)"
is_locked; assert "is_locked=true(0)" "$?"
release_lock; assert "release_lock(0)" "$?"
is_locked; assert "해제 후 is_locked=false(비0)" "$([ $? -ne 0 ]; echo $?)"

echo "=== [2] update_status 원자성 + check_stale ==="
rm -f "$_ANALYTICS_STATUS_FILE"
update_status "{ 'last_success_ts': '$(date '+%Y-%m-%d %H:%M:%S')', 'overall_exit_code': 0 }"
assert "update_status rc=0" "$?"
"$_ANALYTICS_PY" -c "import json,sys; d=json.load(open('$_ANALYTICS_STATUS_FILE')); sys.exit(0 if d.get('overall_exit_code')==0 else 1)"
assert "status JSON 유효 + 필드 반영" "$?"
[ "$(check_stale 8)" = "fresh" ]; assert "check_stale fresh" "$?"
# stale: 10h 전
"$_ANALYTICS_PY" -c "import json,datetime; d={'last_success_ts':(datetime.datetime.now()-datetime.timedelta(hours=10)).strftime('%Y-%m-%d %H:%M:%S')}; json.dump(d, open('$_ANALYTICS_STATUS_FILE','w'))"
[ "$(check_stale 8)" = "stale" ]; assert "check_stale stale" "$?"
# unknown: 파일 없음
rm -f "$_ANALYTICS_STATUS_FILE"
[ "$(check_stale 8)" = "unknown" ]; assert "check_stale unknown" "$?"

echo "=== [3] recover_analytics.sh DRYRUN (실제 수집 없음) ==="
rm -f "$_ANALYTICS_STATUS_FILE"
RECOVER_DRYRUN=1 bash scripts/recover_analytics.sh
assert "recover DRYRUN rc=0" "$?"
"$_ANALYTICS_PY" -c "import json,sys; d=json.load(open('$_ANALYTICS_STATUS_FILE')); sys.exit(0 if d.get('sources',{}).get('ga4',{}).get('dryrun') is True else 1)"
assert "status에 dryrun 표시됨(수집 안 함)" "$?"

echo "=== [4] watchdog 결정 로직 (collect spy) ==="
COLLECT_CALLS=0
force_collect_spy() { COLLECT_CALLS=$((COLLECT_CALLS+1)); return 0; }

run_watchdog_decision() {
  COLLECT_CALLS=0
  if is_locked; then
    echo "skip(locked)"; return
  fi
  local st; st=$(check_stale 8)
  case "$st" in
    fresh) echo "skip(fresh)";;
    stale|unknown) force_collect_spy;;
  esac
}

# (a) fresh → 0회
"$_ANALYTICS_PY" -c "import json,datetime; json.dump({'last_success_ts':datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, open('$_ANALYTICS_STATUS_FILE','w'))"
run_watchdog_decision; assert "fresh → 강제수집 0회" "$([ $COLLECT_CALLS -eq 0 ]; echo $?)"

# (b) stale → 1회
"$_ANALYTICS_PY" -c "import json,datetime; json.dump({'last_success_ts':(datetime.datetime.now()-datetime.timedelta(hours=10)).strftime('%Y-%m-%d %H:%M:%S')}, open('$_ANALYTICS_STATUS_FILE','w'))"
run_watchdog_decision; assert "stale → 강제수집 1회" "$([ $COLLECT_CALLS -eq 1 ]; echo $?)"

# (c) locked → 0회
"$_ANALYTICS_PY" -c "import json,datetime; json.dump({'last_success_ts':(datetime.datetime.now()-datetime.timedelta(hours=10)).strftime('%Y-%m-%d %H:%M:%S')}, open('$_ANALYTICS_STATUS_FILE','w'))"
acquire_lock
run_watchdog_decision; assert "locked(stale여도) → 강제수집 0회" "$([ $COLLECT_CALLS -eq 0 ]; echo $?)"
release_lock

echo ""
echo "결과: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
