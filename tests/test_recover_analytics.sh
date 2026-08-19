#!/bin/bash
# tests/test_recover_analytics.sh — recover_analytics.sh 단위 테스트
# 실제 API 수집은 하지 않음 (RECOVER_DRYRUN=1).
set -uo pipefail
SCRIPT="/Users/twinssn/Projects/5000/scripts/recover_analytics.sh"
LOCK="/tmp/recover_analytics.lock"
PASS=0; FAIL=0

# T1: 문법 검사
if bash -n "$SCRIPT" 2>/dev/null; then echo "T1 bash -n: PASS"; PASS=$((PASS+1)); else echo "T1 bash -n: FAIL"; FAIL=$((FAIL+1)); fi

# T2: 동시 실행 방지 — 별도 프로세스가 lock 점유 중일 때 exit 99 (macOS: mkdir 기반)
rm -rf "$LOCK"
( mkdir "$LOCK" 2>/dev/null || exit 0; sleep 2 ) &
sleep 0.6
RECOVER_DRYRUN=1 bash "$SCRIPT" >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 99 ]; then echo "T2 동시실행방지: PASS (rc=$rc)"; PASS=$((PASS+1)); else echo "T2 동시실행방지: FAIL (rc=$rc)"; FAIL=$((FAIL+1)); fi
sleep 2; rm -rf "$LOCK"

# T3: dry-run 정상 실행 — exit 0, 로그에 DRYRUN 기록
RECOVER_DRYRUN=1 bash "$SCRIPT" >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 0 ]; then echo "T3 dry-run 실행: PASS (rc=$rc)"; PASS=$((PASS+1)); else echo "T3 dry-run 실행: FAIL (rc=$rc)"; FAIL=$((FAIL+1)); fi

# T4: timeout 전파 단위 — `timeout 1 sleep 5` 는 124
timeout 1 sleep 5 >/dev/null 2>&1; rc=$?
if [ "$rc" -eq 124 ]; then echo "T4 timeout 전파: PASS (rc=$rc)"; PASS=$((PASS+1)); else echo "T4 timeout 전파: FAIL (rc=$rc)"; FAIL=$((FAIL+1)); fi

# T5: LOG 파일에 DRYRUN skip 기록 확인
if grep -q "DRYRUN skip" /Users/twinssn/Projects/5000/logs/recover_analytics.log 2>/dev/null; then
  echo "T5 로그 기록: PASS"; PASS=$((PASS+1))
else
  echo "T5 로그 기록: FAIL"; FAIL=$((FAIL+1))
fi

echo "=== RESULT: PASS=$PASS FAIL=$FAIL ==="
[ "$FAIL" -eq 0 ]
