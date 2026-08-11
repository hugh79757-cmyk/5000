#!/usr/bin/env python3
"""fix_long_titles.py — 35자 초과 title을 word boundary에서 축약.

용법:
  python scripts/fix_long_titles.py --dry-run --blog cap  # 미리보기
  python scripts/fix_long_titles.py                       # 전체 적용
"""
import argparse
import json
import re
import sys
from pathlib import Path


def shorten_title(title: str, limit: int = 35) -> str:
    t = title.strip().rstrip("…")
    if len(t) <= limit:
        return title
    truncated = t[:limit].rsplit(" ", 1)
    return truncated[0] + "…" if len(truncated) > 1 else t[:limit] + "…"


def fix_file(md_path: Path, dry: bool) -> bool:
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    fm_end = raw.find("---", 3)
    if fm_end == -1:
        return False
    fm = raw[: fm_end + 3]
    body = raw[fm_end + 3 :]

    m = re.search(r"^(title:\s*['\"]?)(.+?)(['\"]?\s*)$", fm, re.MULTILINE)
    if not m:
        return False
    title = m.group(2).strip()
    if len(title) <= 35:
        return False
    new_title = shorten_title(title)
    new_fm = fm[: m.start()] + m.group(1) + new_title + m.group(3) + fm[m.end() :]

    if not dry:
        md_path.write_text(new_fm + body, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--blog")
    ap.add_argument("--scan-json", default="/tmp/scan_all_blogs2.json")
    args = ap.parse_args()

    scan_json = Path(args.scan_json)
    if not scan_json.exists():
        print("스캔 JSON 없음")
        sys.exit(1)

    data = json.loads(scan_json.read_text(encoding="utf-8"))
    targets = []
    for r in data:
        if args.blog and r["blog_id"] != args.blog:
            continue
        for f in r.get("files", []):
            for iss in f["issues"]:
                if iss["type"] == "S1_title_long":
                    targets.append((r["blog_id"], Path(f["file"])))
                    break

    fixed = 0
    for blog_id, path in targets:
        if not path.exists():
            continue
        ok = fix_file(path, args.dry_run)
        if ok:
            fixed += 1
            if args.dry_run and fixed <= 5:
                print(f"[DRY] {blog_id}: {path.name[:40]}")

    mode = "DRY-RUN" if args.dry_run else "적용"
    print(f"\n[{mode}] 대상 {len(targets)}건, 수정 {fixed}건")


if __name__ == "__main__":
    main()
