#!/bin/bash
# test_verify_gate25_readonly.sh — verify_gate25_runtime.sh 가 read-only 임을 정적 검증
#
# 금지 패턴 (기본 모드에서 절대 없어야 함):
#   launchctl / update_status / recover_analytics / INSERT-UPDATE-DELETE (sqlite write)
# 허용: SELECT, PRAGMA integrity_check, grep, pgrep, check_stale, is_locked, source analytics_common.sh

set -uo pipefail
cd /Users/twinssn/Projects/5000
VERIFY="scripts/verify_gate25_runtime.sh"
ENABLE="scripts/enable_watchdog_gate25.sh"

PASS=0; FAIL=0
assert() { if [ "$2" = "0" ]; then echo "  ✅ $1"; PASS=$((PASS+1)); else echo "  ❌ $1"; FAIL=$((FAIL+1)); fi; }

echo "=== verify_gate25_runtime.sh (기본 모드) 금지 패턴 검사 (주석 제외) ==="
# 주석(#) 라인 제거 후 실제 코드만 검사
CODE=$( grep -vE '^\s*#' "$VERIFY" )
# launchctl 호출 금지
c=$( echo "$CODE" | grep -c "launchctl" ); assert "launchctl 호출 0건 (실제=$c)" "$([ "$c" -eq 0 ]; echo $?)"
# update_status 금지
c=$( echo "$CODE" | grep -c "update_status" ); assert "update_status 호출 0건 (실제=$c)" "$([ "$c" -eq 0 ]; echo $?)"
# recover_analytics 실행 금지
c=$( echo "$CODE" | grep -c "recover_analytics" ); assert "recover_analytics 참조 0건 (실제=$c)" "$([ "$c" -eq 0 ]; echo $?)"
# sqlite 쓰기 금지 (INSERT/UPDATE/DELETE)
c=$( echo "$CODE" | grep -cE "INSERT|UPDATE|DELETE" ); assert "sqlite 쓰기 키워드 0건 (실제=$c)" "$([ "$c" -eq 0 ]; echo $?)"
# enable_watchdog 실행 금지 (echo 안내문 참조는 허용, 실제 실행만 금지)
c=$( echo "$CODE" | grep -cE "(bash|sh|\./|source)[[:space:]]+.*enable_watchdog" ); assert "enable_watchdog 실행 0건 (실제=$c)" "$([ "$c" -eq 0 ]; echo $?)"
# collect_analytics.sh 실행 금지 (pgrep/grep 조회는 허용이나 'bash ... collect_analytics.sh' 실행은 금지)
c=$( echo "$CODE" | grep -cE "(^|[^a-zA-Z])bash .*collect_analytics\.sh|/bin/sh .*collect_analytics\.sh" ); assert "collect_analytics.sh 실행 0건 (실제=$c)" "$([ "$c" -eq 0 ]; echo $?)"

echo "=== enable_watchdog_gate25.sh 분리 검사 (mutating 이 별도에 있어야 함) ==="
c=$( grep -c "launchctl" "$ENABLE" ); assert "enable 스크립트에 launchctl 존재 (실제=$c)" "$([ "$c" -ge 1 ]; echo $?)"
# verify 스크립트는 enable 을 실행하지 않음 (주석 제외, 실행 형태만)
c=$( echo "$CODE" | grep -cE "(bash|sh|\./|source)[[:space:]]+.*enable_watchdog" ); assert "verify→enable 분리 유지 (실제=$c)" "$([ "$c" -eq 0 ]; echo $?)"

echo "=== bash -n ==="
bash -n "$VERIFY" && assert "verify bash -n" "$?" || assert "verify bash -n" "1"
bash -n "$ENABLE" && assert "enable bash -n" "$?" || assert "enable bash -n" "1"

echo ""
echo "결과: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
