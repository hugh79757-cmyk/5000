#!/usr/bin/env python3
"""fix_dup_images.py — 본문 내 동일 이미지 URL 중복 제거.

같은 이미지 URL이 2회+ 나오면 첫 번째만 유지하고 나머지 제거.
마크다운 이미지와 HTML img 모두 처리.

용법:
  python scripts/fix_dup_images.py --dry-run
  python scripts/fix_dup_images.py
"""
import argparse
import json
import re
import sys
from pathlib import Path

SKIP = ("ads-partners.coupang.com", "link.coupang.com")


def fix_file(md_path: Path, dry: bool) -> int:
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    fm_end = raw.find("---", 3)
    if fm_end == -1:
        return 0
    fm = raw[: fm_end + 3]
    body = raw[fm_end + 3 :]

    # 마크다운 이미지 URL 카운트
    md_imgs = list(re.finditer(r"!\[[^\]]*\]\(([^)\s]+)", body))
    md_counts = {}
    for m in md_imgs:
        url = m.group(1)
        if any(d in url for d in SKIP):
            continue
        md_counts[url] = md_counts.get(url, 0) + 1

    # HTML img URL 카운트
    html_imgs = list(re.finditer(r'<img\b[^>]*src="([^"]+)"', body))
    html_counts = {}
    for m in html_imgs:
        url = m.group(1)
        if any(d in url for d in SKIP):
            continue
        html_counts[url] = html_counts.get(url, 0) + 1

    removed = 0
    new_body = body

    # 마크다운 중복 제거 (첫 번째만 유지)
    seen = set()
    def _md_repl(m):
        nonlocal removed
        alt, url = m.group(1), m.group(2)
        if any(d in url for d in SKIP):
            return m.group(0)
        if md_counts.get(url, 0) >= 2:
            if url in seen:
                removed += 1
                return ""
            seen.add(url)
        return m.group(0)
    new_body = re.sub(r"(!\[[^\]]*\])\(([^)\s]+)\)", lambda m: _md_repl(m), new_body)

    # HTML img 중복 제거
    seen_html = set()
    def _html_repl(m):
        nonlocal removed
        tag = m.group(0)
        url = m.group(1)
        if any(d in url for d in SKIP):
            return tag
        if html_counts.get(url, 0) >= 2:
            if url in seen_html:
                removed += 1
                return ""
            seen_html.add(url)
        return tag
    new_body = re.sub(r"<img\b[^>]*src=\"([^\"]+)\"[^>]*>", lambda m: _html_repl(m), new_body)

    if not dry and removed > 0:
        md_path.write_text(fm + new_body, encoding="utf-8")
    return removed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--blog")
    ap.add_argument("--scan-json", default="/tmp/scan_all_blogs4.json")
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
                if iss["type"] == "I2_dup":
                    targets.append((r["blog_id"], Path(f["file"])))
                    break

    total = 0
    for blog_id, path in targets:
        if not path.exists():
            continue
        n = fix_file(path, args.dry_run)
        if n:
            total += n
            if args.dry_run:
                print(f"[DRY] {blog_id}: {path.name[:40]} — {n}건 제거")

    mode = "DRY-RUN" if args.dry_run else "적용"
    print(f"\n[{mode}] 대상 {len(targets)}건, 중복 이미지 {total}건 제거")


if __name__ == "__main__":
    main()
