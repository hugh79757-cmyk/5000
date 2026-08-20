#!/bin/bash
# analytics_common.sh — collect_analytics.sh / recover_analytics.sh / analytics_watchdog.sh 공유
#
# 책임:
#  - mkdir 기반 동시 실행 방지 잠금 (macOS에 flock 없음)
#  - 원자적 heartbeat / status JSON 갱신 (temp + os.replace)
#  - success timestamp / run ID / exit code / source별 상태 보존
#  - stale 여부 판단 (last_success_ts 기준)
#
# 이 파일은 `source` 되어 사용됨 (실행 권한 불필요).

_ANALYTICS_LOCKDIR="/tmp/analytics_collect.lock"
_ANALYTICS_STATUS_FILE="/Users/twinssn/Projects/5000/data/analytics_status.json"
_ANALYTICS_PY="/opt/homebrew/bin/python3"

# ── 동시 실행 방지 ──
# 획득 성공 시 0, 실패(이미 실행 중) 시 1 반환
acquire_lock() {
  mkdir "$_ANALYTICS_LOCKDIR" 2>/dev/null
}

release_lock() {
  rmdir "$_ANALYTICS_LOCKDIR" 2>/dev/null
}

is_locked() {
  [ -d "$_ANALYTICS_LOCKDIR" ]
}

# ── status JSON 갱신 (원자적) ──
# $1 = python dict literal (병합할 필드). 실패 시 1 반환.
update_status() {
  "$_ANALYTICS_PY" - "$_ANALYTICS_STATUS_FILE" "$1" <<'PY' || return 1
import sys, json, os, datetime
path, frag = sys.argv[1], eval(sys.argv[2])

def deep_merge(a, b):
    for k, v in b.items():
        if k in a and isinstance(a[k], dict) and isinstance(v, dict):
            deep_merge(a[k], v)
        else:
            a[k] = v

d = {}
if os.path.exists(path):
    try:
        d = json.load(open(path))
    except Exception:
        d = {}
deep_merge(d, frag)
d["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
tmp = path + ".tmp." + str(os.getpid())
with open(tmp, "w") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
os.replace(tmp, path)
PY
}

# ── stale 판단 ──
# $1 = threshold_hours (float). stdout: fresh / stale / unknown
check_stale() {
  "$_ANALYTICS_PY" - "$_ANALYTICS_STATUS_FILE" "$1" <<'PY'
import sys, json, os, datetime
path, th = sys.argv[1], float(sys.argv[2])
if not os.path.exists(path):
    print("unknown"); sys.exit(0)
try:
    d = json.load(open(path))
except Exception:
    print("unknown"); sys.exit(0)
ts = d.get("last_success_ts")
if not ts:
    # 성공 이력 없음 → 최초 1회는 stale로 간주하여 수집 허용
    print("stale"); sys.exit(0)
try:
    last = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
except Exception:
    print("unknown"); sys.exit(0)
age_h = (datetime.datetime.now() - last).total_seconds() / 3600
print("fresh" if age_h < th else "stale")
PY
}

# heartbeat 파일 경로 노출 (watchdog이 참조)
analytics_status_file() {
  echo "$_ANALYTICS_STATUS_FILE"
}
