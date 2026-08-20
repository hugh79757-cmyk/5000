#!/bin/bash
# verify_gate25_runtime.sh — Phase 0 Task 2.5 운영 검증 (READ-ONLY 전용)
#
# ⚠️ 안전성: 이 스크립트는 조회와 판정 출력만 한다. 다음을 절대 하지 않는다:
#   - launchctl load/unload (운영 변경)
#   - 수집 실행 (collect_analytics.sh / recover_analytics.sh)
#   - DB/heartbeat(status.json) 수정 (update_status / INSERT/UPDATE/DELETE)
#   - 장시간 sleep / polling / 백그라운드 작업
#
# 전제: 13:34 정규 실행이 launchd에 의해 이미 완료된 상태에서 실행.
# watchdog 활성화가 필요하면 별도 스크립트 scripts/enable_watchdog_gate25.sh 를
# 명시적으로 실행할 것 (이 스크립트는 호출하지 않음).

set -uo pipefail
cd /Users/twinssn/Projects/5000
source scripts/analytics_common.sh
PY="/opt/homebrew/bin/python3"
LOG="logs/analytics_collect.log"
BASELINE="data/gate25_baseline.json"
STATUS="$_ANALYTICS_STATUS_FILE"

PASS=0; FAIL=0; ISSUES=()
ok()   { echo "  ✅ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $1"; FAIL=$((FAIL+1)); ISSUES+=("$1"); }
note() { echo "  ℹ️  $1"; }

echo "=== ① 신버전 실행 여부 (조회만) ==="
if [ ! -f "$STATUS" ]; then
  bad "status.json 없음 — 13:34 신버전 실행 미발생 가능성"
else
  RID=$( "$PY" -c "import json;print(json.load(open('$STATUS')).get('last_run_id',''))" )
  LST=$( "$PY" -c "import json;print(json.load(open('$STATUS')).get('last_success_ts',''))" )
  note "run_id=$RID  last_success_ts=$LST"
  if [ -z "$LST" ]; then
    bad "heartbeat 부재 (last_success_ts 공백) — 성공 기록 없음"
  else
    ok "heartbeat 존재: $LST"
  fi
  if grep -q "수집 완료 (성공" "$LOG" || grep -q "수집 종료 (rc=" "$LOG"; then
    ok "로그 포맷 = 신버전 (rc 표시됨)"
  else
    bad "로그 포맷 = 구버전 (rc 표시 없음) — 신버전 미적용"
  fi
  if pgrep -f "collect_analytics.sh" >/dev/null 2>&1; then
    note "현재 수집 프로세스 실행 중 (정상 범위 내 — 종료 대기)"
  else
    ok "수집 프로세스 종료됨"
  fi
fi

echo "=== ② source별 rc!=0 → FAIL (조회만) ==="
if [ -f "$STATUS" ]; then
  RC_RES=$( "$PY" - <<'PY'
import json
d = json.load(open("/Users/twinssn/Projects/5000/data/analytics_status.json"))
sources = d.get('sources', {})
fail = False
for s in ('ga4','gsc','adsense','efficiency'):
    st = sources.get(s, {})
    rc = st.get('exit_code') or 0
    print(f"  • {s}: status={st.get('status')} rc={rc} start={st.get('started')} end={st.get('finished')}")
    if rc != 0 or st.get('status') != 'ok':
        fail = True
oc = d.get('overall_exit_code')
print(f"  • OVERALL_RC={oc}")
print("GATE2_5_RC_FAIL" if (fail or (oc is not None and oc != 0)) else "GATE2_5_RC_OK")
PY
)
  echo "$RC_RES"
  if echo "$RC_RES" | grep -q "GATE2_5_RC_FAIL"; then
    bad "rc!=0 또는 source 실패 — 수집 실패 (rc!=0는 FAIL)"
  else
    ok "모든 source ok + OVERALL_RC=0"
  fi
fi

echo "=== ③ DB vs 기준선 + 무증분 → FAIL (SELECT만) ==="
if [ -f "$BASELINE" ]; then
  DBRES=$( "$PY" - <<'PY'
import sqlite3, json
from datetime import date
db = "/Users/twinssn/Projects/5000/data/analytics.db"
base = json.load(open("/Users/twinssn/Projects/5000/data/gate25_baseline.json"))
def q(sql):
    c = sqlite3.connect(db); r = c.execute(sql).fetchone(); c.close(); return r
print(f"  {'table':14} {'기준MAX':12} {'현재MAX':12} {'기준행':7} {'현재행':7}")
for tbl in ('adsense_daily','gsc_keywords','ga4_daily'):
    bmax, brows = base[tbl]['max_date'], base[tbl]['rows']
    cmax = q(f"SELECT MAX(date) FROM {tbl};")[0]
    crows = q(f"SELECT COUNT(*) FROM {tbl};")[0]
    new = crows - brows
    flag = "▲증가" if (cmax != bmax or new > 0) else "─유지"
    print(f"  {tbl:14} {str(bmax):12} {str(cmax):12} {brows:7} {crows:7}  {flag}")
for (tbl, cols) in [("adsense_daily","account,domain,date"),("gsc_keywords","blog_id,date,query"),("ga4_daily","blog_id,date")]:
    dup = q(f"SELECT COUNT(*) FROM (SELECT {cols} FROM {tbl} GROUP BY {cols} HAVING COUNT(*)>1);")[0]
    print(f"  • {tbl} 중복 unique key: {dup}건")
c = sqlite3.connect(db); integ = c.execute("PRAGMA integrity_check;").fetchone(); c.close()
print(f"  • integrity_check: {integ[0]} (read-only)")
today = date.today().isoformat()
amax = q("SELECT MAX(date) FROM adsense_daily;")[0]
print(f"  • TODAY={today} adsense_max={amax}")
print("GATE2_5_DB_FAIL" if (amax is None or amax < today) else "GATE2_5_DB_OK")
PY
)
  echo "$DBRES"
  if echo "$DBRES" | grep -q "GATE2_5_DB_FAIL"; then
    bad "DB 무증분 (adsense_daily에 today 데이터 없음)"
  else
    ok "DB 증분 확인 (adsense_daily에 today 데이터 존재)"
  fi
else
  bad "기준선 파일 없음 — DB 비교 불가"
fi

echo "=== ④ 프로세스·lock 정리 (조회만) ==="
if is_locked; then
  bad "lock 잔존 — 비정상"
else
  ok "lock 정리됨"
fi
if pgrep -f "collect_analytics.sh" >/dev/null 2>&1; then
  bad "수집 프로세스 잔존 (hanging 의심)"
else
  ok "수집 프로세스 없음"
fi

echo ""
echo "=== 결과: PASS=$PASS FAIL=$FAIL ==="
if [ "$FAIL" -eq 0 ]; then
  echo "=== GATE 판정: PASS (운영 검증 성공) — watchdog 활성화는 enable_watchdog_gate25.sh 별도 실행 ==="
else
  echo "=== GATE 판정: FAIL/부분 — watchdog unloaded 유지, Task 3 승인 보류 ==="
  for i in "${ISSUES[@]}"; do echo "    - $i"; done
fi
[ "$FAIL" -eq 0 ]
