#!/usr/bin/env python3
"""fix_missing_thumbs.py — featureimage 없는 글에 본문 첫 비쿠팡 이미지를 추가.

본문에 이미지가 있으면 그 첫 이미지를 featureimage로 채우고,
없으면 R2 기본 플레이스홀더를 사용.

용법:
  python scripts/fix_missing_thumbs.py --dry-run
  python scripts/fix_missing_thumbs.py --blog travel1-hugo
  python scripts/fix_missing_thumbs.py --scan-json /tmp/scan_all_blogs.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

SKIP = ("ads-partners.coupang.com", "link.coupang.com")
DEFAULT_IMG = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"


def first_real_image(body: str) -> str:
    for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)", body):
        url = m.group(1)
        if url.startswith("http") and not any(d in url for d in SKIP):
            return url
    for m in re.finditer(r'<img[^>]+src="(https?://[^"]+)"', body):
        url = m.group(1)
        if not any(d in url for d in SKIP):
            return url
    return ""


def fix_file(md_path: Path, dry: bool, force_default: bool = False) -> bool:
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    fm_end = raw.find("---", 3)
    if fm_end == -1:
        return False
    fm = raw[: fm_end + 3]
    body = raw[fm_end + 3 :]

    # 이미 featureimage/cover 있으면 skip
    if re.search(r"featureimage:\s*['\"]?https?://", fm) or re.search(r"cover:\s*\n\s*image:", fm):
        return False

    img = first_real_image(body)
    if not img and not force_default:
        return False  # 본문 이미지 없으면 기본값 없이는 스킵
    img = img or DEFAULT_IMG
    # frontmatter 끝(---) 앞에 featureimage 추가
    if not fm.rstrip().endswith("---"):
        return False
    insert = f"featureimage: '{img}'\n"
    new_fm = fm[:-3] + insert + "---"

    if not dry:
        md_path.write_text(new_fm + body, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--blog")
    ap.add_argument("--force-default", action="store_true", help="본문 이미지 없어도 R2 기본 썸네일 채움")
    ap.add_argument("--scan-json", default="/tmp/scan_all_blogs3.json")
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
                if iss["type"] == "I3_no_thumb":
                    targets.append((r["blog_id"], Path(f["file"])))
                    break

    fixed = 0
    for blog_id, path in targets:
        if not path.exists():
            continue
        ok = fix_file(path, args.dry_run, force_default=args.force_default)
        if ok:
            fixed += 1
            if args.dry_run:
                print(f"[DRY] {blog_id}: {path.name[:40]}")

    mode = "DRY-RUN" if args.dry_run else "적용"
    print(f"\n[{mode}] 대상 {len(targets)}건, 수정 {fixed}건")


if __name__ == "__main__":
    main()
