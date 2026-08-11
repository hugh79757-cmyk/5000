#!/usr/bin/env python3
"""fix_coupang_thumbs.py — 쿠팡 광고 URL이 featureimage로 설정된 글을
본문 첫 비쿠팡 이미지로 교체. 없으면 기본 플레이스홀더 사용.

용법:
  python scripts/fix_coupang_thumbs.py --dry-run   # 미리보기
  python scripts/fix_coupang_thumbs.py             # 적용
  python scripts/fix_coupang_thumbs.py --blog travel-hugo  # 단일
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = ("ads-partners.coupang.com", "link.coupang.com")
DEFAULT_IMG = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"


def find_files_with_coupang_thumb(scan_json: Path) -> list[tuple[str, Path]]:
    data = json.loads(scan_json.read_text(encoding="utf-8"))
    out = []
    for r in data:
        for f in r.get("files", []):
            for iss in f["issues"]:
                if iss["type"] == "I1_coupang_thumb":
                    out.append((r["blog_id"], Path(f["file"])))
                    break
    return out


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


def fix_file(md_path: Path, dry: bool) -> bool:
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    fm_end = raw.find("---", 3)
    if fm_end == -1:
        return False
    fm = raw[: fm_end + 3]
    body = raw[fm_end + 3 :]

    new_img = first_real_image(body) or DEFAULT_IMG
    new_fm = re.sub(
        r"(featureimage:\s*['\"]?)(https?://[^'\s]+)(['\"]?\s*$)",
        lambda m: f"{m.group(1)}{new_img}{m.group(3)}",
        fm,
        count=1,
        flags=re.MULTILINE,
    )
    if new_fm == fm:
        # 못 찾으면 featureimage 줄만 교체
        new_fm = re.sub(
            r"featureimage:\s*['\"]?[^'\n]+['\"]?",
            f"featureimage: '{new_img}'",
            fm,
            count=1,
        )
    if new_fm == fm:
        return False

    if not dry:
        md_path.write_text(new_fm + body, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--blog")
    ap.add_argument("--scan-json", default="/tmp/scan_all_blogs.json")
    args = ap.parse_args()

    scan_json = Path(args.scan_json)
    if not scan_json.exists():
        print("스캔 JSON 없음 — 먼저 scan_all_blogs.py --json 실행")
        sys.exit(1)

    targets = find_files_with_coupang_thumb(scan_json)
    if args.blog:
        targets = [t for t in targets if t[0] == args.blog]

    fixed = 0
    for blog_id, path in targets:
        ok = fix_file(path, args.dry_run)
        status = "FIX" if ok else "SKIP"
        if ok or args.dry_run:
            print(f"[{status}] {blog_id}: {path.name[:40]}")
        fixed += 1 if ok else 0

    mode = "DRY-RUN" if args.dry_run else "적용"
    print(f"\n[{mode}] 대상 {len(targets)}건, 수정 {fixed}건")


if __name__ == "__main__":
    main()
