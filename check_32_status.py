import sqlite3
from pathlib import Path

ROOT = Path(".").resolve()
ETAP_DIR = ROOT / "pipelines" / "etap"
DATA_DIR = ROOT / "data"

def section(title): print(f"\n{'='*60}\n  {title}\n{'='*60}")
def ok(msg):   print(f"  ✅  {msg}")
def warn(msg): print(f"  ⚠️   {msg}")
def fail(msg): print(f"  ❌  {msg}")
def info(msg): print(f"  ℹ️   {msg}")

section("1. dispatcher.py")
dispatcher_path = None
for p in [ROOT/"shared"/"dispatcher.py", ROOT/"pipelines"/"dispatcher.py", ROOT/"dispatcher.py"]:
    if p.exists():
        ok(f"발견: {p.relative_to(ROOT)}")
        dispatcher_path = p
        break
if not dispatcher_path:
    fail("dispatcher.py 없음 — 신규 생성 필요")

section("2. publish_ledger")
ledger_ok = False
if dispatcher_path:
    src = dispatcher_path.read_text(errors="ignore")
    if "publish_ledger" in src:
        ok("dispatcher.py 내 publish_ledger 있음")
        ledger_ok = True
    else:
        warn("dispatcher.py에 publish_ledger 없음")

db_paths = list(DATA_DIR.glob("*.db")) + list(ROOT.glob("*.db"))
for db_path in db_paths:
    try:
        con = sqlite3.connect(db_path)
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        con.close()
        if "publish_ledger" in tables:
            ok(f"publish_ledger 테이블 존재: {db_path.name}")
        else:
            info(f"{db_path.name} 테이블: {', '.join(tables)}")
    except Exception as e:
        warn(f"DB 오류 {db_path.name}: {e}")

section("3. ETAP writer 파일 목록")
writer_files = sorted(ETAP_DIR.glob("*_writer.py")) + sorted(ETAP_DIR.glob("*_pipeline.py"))
info(f"총 {len(writer_files)}개")
for f in writer_files:
    print(f"    {f.name}")

section("4. dispatcher 경유 여부")
DISPATCH_KW = ["dispatcher", "dispatch(", "dispatch_post", "publish_via"]
DIRECT_KW   = ["wp_client", "wordpress", ".post(", "publish_post", "create_post"]
via, direct, unclear = [], [], []
for f in writer_files:
    src = f.read_text(errors="ignore")
    d = any(k in src for k in DISPATCH_KW)
    p = any(k in src for k in DIRECT_KW)
    if d and not p:
        via.append(f.name)
    elif p and not d:
        direct.append(f.name)
    else:
        unclear.append(f.name + (" (혼재)" if d and p else " (불명)"))

if via:     ok(f"dispatcher 경유 {len(via)}개: " + ", ".join(via))
if direct:  fail(f"직접 publish {len(direct)}개:\n    " + "\n    ".join(direct))
if unclear: warn(f"확인 필요 {len(unclear)}개:\n    " + "\n    ".join(unclear))

section("5. content.db ETAP 집계")
for db_path in db_paths:
    try:
        con = sqlite3.connect(db_path)
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for tbl in tables:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({tbl})").fetchall()]
            target = [c for c in cols if c in ["pipeline","source","blog_id","site"]]
            if not target:
                continue
            rows = con.execute(f"SELECT DISTINCT {target[0]} FROM {tbl} LIMIT 10").fetchall()
            vals = [str(r[0]) for r in rows if r[0]]
            etap = any("etap" in v.lower() for v in vals)
            (ok if etap else warn)(f"{db_path.name}.{tbl} [{target[0]}]: {vals[:5]}")
        con.close()
    except Exception as e:
        warn(f"DB 오류 {db_path.name}: {e}")

section("6. scheduler.py ETAP 호출")
sched = ROOT / "scheduler.py"
if sched.exists():
    lines = sched.read_text(errors="ignore").splitlines()
    etap_lines = [(i+1, l.strip()) for i, l in enumerate(lines) if "etap" in l.lower()]
    info(f"ETAP 관련 라인 {len(etap_lines)}개")
    for no, l in etap_lines[:25]:
        mark = "✅" if any(k in l for k in DISPATCH_KW) else "  "
        print(f"  {mark} L{no:4d}: {l[:85]}")
else:
    fail("scheduler.py 없음")

section("7. blogs.yaml ETAP 블로그")
blogs_yaml = ROOT / "config" / "blogs.yaml"
if blogs_yaml.exists():
    try:
        import yaml
        blogs = yaml.safe_load(open(blogs_yaml))
        if isinstance(blogs, list):
            etap = [b for b in blogs if str(b.get("pipeline","")).lower() == "etap"]
        elif isinstance(blogs, dict):
            etap = [b for v in blogs.values() for b in (v if isinstance(v,list) else [v]) if str(b.get("pipeline","")).lower() == "etap"]
        else:
            etap = []
        ok(f"ETAP 블로그 {len(etap)}개")
        for b in etap[:5]: print(f"    - {b.get('name') or b.get('id','?')}")
        if len(etap) > 5: print(f"    ... 외 {len(etap)-5}개")
    except ImportError:
        count = blogs_yaml.read_text().lower().count("etap")
        info(f"'etap' {count}회 (pip install pyyaml 필요)")
    except Exception as e:
        warn(f"파싱 오류: {e}")
else:
    fail("config/blogs.yaml 없음")

section("요약")
ok("dispatcher.py 존재") if dispatcher_path else fail("dispatcher.py 없음")
ok("publish_ledger 있음") if ledger_ok else fail("publish_ledger 없음")
ok("모든 writer dispatcher 경유") if not direct else fail(f"직접 publish {len(direct)}개 전환 필요")
print(f"\n  전환 대상: {len(direct)}개 / 완료: {len(via)}개 / 불명: {len(unclear)}개\n")
