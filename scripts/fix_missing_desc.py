#!/usr/bin/env python3
"""fix_missing_desc.py — description 없는 글에 본문 첫 문단에서 자동 생성.

용법:
  python scripts/fix_missing_desc.py --dry-run --blog travel1-hugo
  python scripts/fix_missing_desc.py
"""
import argparse
import json
import re
import sys
from pathlib import Path


def gen_desc(body: str, title: str = "") -> str:
    """본문 첫 텍스트 문단에서 140자 내외 description 생성."""
    # 마크다운/HTML 제거
    clean = re.sub(r"\{\{<.*?>\}\}", "", body, flags=re.DOTALL)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", clean)
    clean = re.sub(r"[#>*_`|\[\]]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return ""
    # 첫 문장 ~ 140자
    desc = clean[:140].rsplit(" ", 1)[0] if len(clean) > 140 else clean
    return desc.strip()


def fix_file(md_path: Path, dry: bool) -> bool:
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    fm_end = raw.find("---", 3)
    if fm_end == -1:
        return False
    fm = raw[: fm_end + 3]
    body = raw[fm_end + 3 :]

    if re.search(r"^description:\s*['\"]?\S", fm, re.MULTILINE):
        return False

    title_m = re.search(r"title:\s*['\"]?(.+?)['\"]?\s*$", fm, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else ""
    desc = gen_desc(body, title)
    if not desc:
        desc = title[:100] if title else "정보 안내"
    desc = desc.replace("'", "").replace('"', "")
    desc_short = desc[:150]

    if not fm.rstrip().endswith("---"):
        return False
    insert = f"description: '{desc_short}'\n"
    new_fm = fm[:-3] + insert + "---"

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
                if iss["type"] == "S1_no_desc":
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
