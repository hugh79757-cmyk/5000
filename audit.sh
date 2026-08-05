#!/usr/bin/env bash
# 분기별 blog_id / pipeline / status / site_path / 발행량 감사
set -uo pipefail
cd /Users/twinssn/projects/5000
PY="${PWD}/.venv/bin/python3"
[ -x "$PY" ] || PY=python3

sep() { echo; echo "========== $1 =========="; echo; }

sep "blogs.d/ 파일 목록"
ls -la config/blogs.d/

sep "분기별 blog 요약 (id / pipeline / status / site_path)"
"$PY" - << 'PYEOF'
import glob, yaml, os
rows=[]
for fp in sorted(glob.glob("config/blogs.d/*.yaml")) + ["config/blogs.yaml"]:
    try:
        data = yaml.safe_load(open(fp, encoding="utf-8")) or {}
    except Exception as e:
        print(f"[PARSE FAIL] {fp}: {e}"); continue
    for b in data.get("blogs", []):
        if not isinstance(b, dict): continue
        rows.append((os.path.basename(fp), b.get("pipeline","?"),
                     b.get("id","?"), b.get("status","?"),
                     b.get("daily_quota","-"), b.get("site_path","")))
print(f"{'file':22} {'pipeline':10} {'blog_id':18} {'status':9} {'quota':5} site_path")
print("-"*110)
for f,p,i,s,q,sp in sorted(rows):
    mark = "" if s=="active" else "  <-- inactive"
    print(f"{f:22} {p:10} {i:18} {s:9} {str(q):5} {sp}{mark}")
print(f"\n총 {len(rows)}개 블로그, active={sum(1 for r in rows if r[3]=='active')}")
PYEOF

sep "최근 7일 발행 통계 (분기별 성공/실패)"
"$PY" dispatcher.py report --quality

sep "publish_ledger 최근 실패 사유 TOP (오늘)"
sqlite3 data/content.db "SELECT blog_id, stage, COUNT(*) c FROM publish_ledger WHERE status='failed' AND date(created_at)=date('now') GROUP BY blog_id, stage ORDER BY c DESC LIMIT 20;" 2>/dev/null || echo "(sqlite3 없음/조회 실패)"
