#!/usr/bin/env python3
"""분기(pipeline) 단위로 blogs.d YAML의 status를 active <-> paused 전환.
사용법:
  python3 toggle_pipeline.py list
  python3 toggle_pipeline.py pause etap rap stock          # 해당 파이프라인 전부 중단
  python3 toggle_pipeline.py pause --all --except curation # curation 빼고 전부 중단
  python3 toggle_pipeline.py resume curation
주의: scheduler는 실행 중에도 queue_publish에서 status를 실시간 재확인하므로
      YAML만 바꾸면 재시작 없이 반영됩니다. (register_schedules는 재시작 시 반영)
"""
import sys, glob, os, shutil, datetime, yaml

CONF = "config/blogs.d"

def load(fp):
    return yaml.safe_load(open(fp, encoding="utf-8")) or {}

def iter_files():
    return sorted(glob.glob(f"{CONF}/*.yaml"))

def cmd_list():
    for fp in iter_files():
        d = load(fp)
        for b in d.get("blogs", []):
            if isinstance(b, dict):
                print(f"{os.path.basename(fp):20} {b.get('pipeline','?'):10} "
                      f"{b.get('id','?'):18} {b.get('status','?')}")

def apply(target_pipelines, new_status, all_except=None):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    changed = 0
    for fp in iter_files():
        d = load(fp)
        dirty = False
        for b in d.get("blogs", []):
            if not isinstance(b, dict):
                continue
            pl = b.get("pipeline", "")
            hit = (all_except is not None and pl not in all_except) or \
                  (all_except is None and pl in target_pipelines)
            if hit and b.get("status") != new_status:
                b["status"] = new_status
                dirty = True
                changed += 1
                print(f"  {b.get('id')} ({pl}): -> {new_status}")
        if dirty:
            shutil.copy(fp, f"{fp}.bak_{ts}")
            with open(fp, "w", encoding="utf-8") as f:
                yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False)
    print(f"\n변경 {changed}건. 백업 접미사 .bak_{ts}")
    print("원복: for f in config/blogs.d/*.bak_%s; do mv \"$f\" \"${f%%.bak_%s}\"; done" % (ts, ts))

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "list":
        cmd_list(); return
    args = sys.argv[2:]
    new_status = "active" if cmd == "resume" else "paused"
    if "--all" in args:
        exc = []
        if "--except" in args:
            exc = args[args.index("--except")+1:]
        apply(None, new_status, all_except=set(exc))
    else:
        apply(set(args), new_status)

if __name__ == "__main__":
    main()
