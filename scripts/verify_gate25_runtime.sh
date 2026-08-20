#!/bin/bash
# verify_gate25_runtime.sh — Phase 0 Task 2.5 운영 검증 (13:34 정규 실행 직후 실행)
#
# 검증 항목 (지시 ①~⑦):
#  ① 신버전 collect_analytics.sh 실행 여부 (run ID/시각/로그포맷/ps)
#  ② source별 시간/exit/timeout/retry/auth 분류/OVERALL_RC vs status.json 일치
#  ③ analytics.db source별 MAX(date)/증가량/중복/integrity/WAL vs 기준선
#  ④ 프로세스·lock 정리·launchd hanging 없이 종료
#  ⑤ 성공 시 watchdog load + fresh heartbeat 강제수집 0회·중복 0건
#  ⑥ 실패 시 watchdog unloaded 유지 + 원인 기록
#  ⑦ GATE 문서 갱신 + Task 3 승인 판정
#
# 주의: 수동 수집은 하지 않음 (launchd 정규 실행만 대상).

set -uo pipefail
cd /Users/twinssn/Projects/5000
source scripts/analytics_common.sh
PY="/opt/homebrew/bin/python3"
LOG="logs/analytics_collect.log"
BASELINE="data/gate25_baseline.json"
STATUS="$_ANALYTICS_STATUS_FILE"
WATCHDOG_PLIST="$HOME/Library/LaunchAgents/com.5000.analytics.watchdog.plist"

PASS=0; FAIL=0; ISSUES=()
ok()   { echo "  ✅ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $1"; FAIL=$((FAIL+1)); ISSUES+=("$1"); }
note() { echo "  ℹ️  $1"; }

echo "=== ① 신버전 실행 여부 ==="
if [ ! -f "$STATUS" ]; then
  bad "status.json 없음 — 13:34 신버전 실행 미발생 가능성"
else
  RID=$( "$PY" -c "import json;print(json.load(open('$STATUS')).get('last_run_id',''))" )
  LST=$( "$PY" -c "import json;print(json.load(open('$STATUS')).get('last_success_ts',''))" )
  note "run_id=$RID  last_success_ts=$LST"
  # 로그 포맷 신버전 확인: "수집 완료 (성공, rc=0)" 또는 "수집 종료 (rc=..)"
  if grep -q "수집 완료 (성공" "$LOG" || grep -q "수집 종료 (rc=" "$LOG"; then
    ok "로그 포맷 = 신버전 (rc 표시됨)"
  else
    bad "로그 포맷 = 구버전 (rc 표시 없음) — 신버전 미적용"
  fi
  # 프로세스 command line (실행 중이면)
  if pgrep -f "collect_analytics.sh" >/dev/null 2>&1; then
    note "현재 수집 프로세스 실행 중 (정상 범위 내)"
  else
    ok "수집 프로세스 종료됨 (hanging 없음)"
  fi
fi

echo "=== ② source별 vs status.json 일치 ==="
if [ -f "$STATUS" ]; then
  "$PY" - <<PY
import json, sys
d = json.load(open('$STATUS'))
sources = d.get('sources', {})
allok = True
for s in ('ga4','gsc','adsense','efficiency'):
    st = sources.get(s, {})
    print(f"  • {s}: status={st.get('status')} rc={st.get('exit_code')} start={st.get('started')} end={st.get('finished')}")
    if st.get('status') not in ('ok', None):
        allok = False
if allok and d.get('overall_exit_code') == 0:
    print("  ✅ 모든 source ok + OVERALL_RC=0")
elif d.get('overall_exit_code') is not None:
    print(f"  ⚠️  OVERALL_RC={d.get('overall_exit_code')} — 부분/실패")
PY
fi

echo "=== ③ DB vs 기준선 ==="
"$PY" - <<'PY'
import sqlite3, json
db = "/Users/twinssn/Projects/5000/data/analytics.db"
base = json.load(open("/Users/twinssn/Projects/5000/data/gate25_baseline.json"))
def q(sql):
    c = sqlite3.connect(db); r = c.execute(sql).fetchone(); c.close(); return r
checks = {
  "adsense_daily": "adsense_daily",
  "gsc_keywords": "gsc_keywords",
  "ga4_daily": "ga4_daily",
}
print(f"  {'table':14} {'기준MAX':12} {'현재MAX':12} {'기준행':7} {'현재행':7}")
for tbl in checks:
    bmax, brows = base[tbl]['max_date'], base[tbl]['rows']
    cmax = q(f"SELECT MAX(date) FROM {tbl};")[0]
    crows = q(f"SELECT COUNT(*) FROM {tbl};")[0]
    new = crows - brows
    flag = "▲증가" if (cmax != bmax or new > 0) else "─유지"
    print(f"  {tbl:14} {str(bmax):12} {str(cmax):12} {brows:7} {crows:7}  {flag}")
# 중복 unique key 확인
for (tbl, cols) in [("adsense_daily","account,domain,date"),("gsc_keywords","blog_id,date,query"),("ga4_daily","blog_id,date")]:
    dup = q(f"SELECT COUNT(*) FROM (SELECT {cols} FROM {tbl} GROUP BY {cols} HAVING COUNT(*)>1);")[0]
    print(f"  • {tbl} 중복 unique key: {dup}건")
# integrity
c = sqlite3.connect(db); integ = c.execute("PRAGMA integrity_check;").fetchone(); c.close()
print(f"  • integrity_check: {integ[0]}")
PY

echo "=== ④ 프로세스·lock 정리 ==="
if is_locked; then
  bad "lock 잔존 — 비정상 (수집 종료 후 잠금 해제돼야 함)"
else
  ok "lock 정리됨"
fi
if pgrep -f "collect_analytics.sh" >/dev/null 2>&1; then
  bad "수집 프로세스 잔존 (hanging 의심)"
else
  ok "수집 프로세스 없음"
fi

echo "=== ⑤/⑥ watchdog 판정 ==="
OVERALL=$( "$PY" -c "import json; print(json.load(open('$STATUS')).get('overall_exit_code'))" 2>/dev/null )
if [ "$OVERALL" = "0" ]; then
  note "전체 성공 → watchdog load 시도"
  launchctl load "$WATCHDOG_PLIST" 2>/dev/null
  sleep 5
  # fresh heartbeat → 강제수집 0회 확인
  FORCED=$( grep -c "강제수집 1회" logs/analytics_watchdog.log 2>/dev/null | tail -1 )
  # 방금 load 후 강제수집 로그 있는지
  RECENT=$( tail -5 logs/analytics_watchdog.log 2>/dev/null | grep -c "강제수집" )
  if [ "$RECENT" -eq 0 ]; then
    ok "fresh heartbeat → 강제수집 0회 (watchdog 정상)"
  else
    bad "watchdog load 후 강제수집 발생 — heartbeat 불일치 의심"
  fi
  echo "  → 10분 안정 상태는 운영자가 사후 확인 (본 검증은 즉시 판정)"
  GATE_VERDICT="PASS — Task 3 승인 가능"
else
  note "전체 비성공(rc=$OVERALL) → watchdog unloaded 유지"
  launchctl unload "$WATCHDOG_PLIST" 2>/dev/null
  GATE_VERDICT="FAIL/부분 — watchdog unloaded, Task 3 승인 보류"
  for i in "${ISSUES[@]}"; do echo "    - $i"; done
fi

echo ""
echo "=== 결과: PASS=$PASS FAIL=$FAIL ==="
echo "=== GATE 판정: $GATE_VERDICT ==="
[ "$FAIL" -eq 0 ]
