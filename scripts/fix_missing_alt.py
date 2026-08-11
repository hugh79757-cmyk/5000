#!/usr/bin/env python3
"""fix_missing_alt.py — 이미지 alt 누락을 자동 채움.

전략:
  - 이미지 URL 경로에서 파일명(확장자 제외)을 추론해 alt로 사용
  - 파일명이 의미없으면(해시 등) "관련 이미지"로 대체

용법:
  python scripts/fix_missing_alt.py --dry-run --blog travel1-hugo
  python scripts/fix_missing_alt.py
"""
import argparse
import json
import re
import sys
from pathlib import Path


def infer_alt(url: str) -> str:
    # URL에서 파일명 추출 (쿼리 제거)
    base = url.split("?")[0].split("#")[0]
    fname = base.rstrip("/").split("/")[-1]
    name = re.sub(r"\.[a-zA-Z0-9]+$", "", fname)
    # URL 인코딩 디코딩
    try:
        import urllib.parse
        name = urllib.parse.unquote(name)
    except Exception:
        pass
    # 의미있는 이름이면 사용 (해시/숫자만 아니면)
    name = name.replace("-", " ").replace("_", " ").strip()
    if len(name) >= 2 and not re.fullmatch(r"[0-9a-fA-F]{10,}", name.replace(" ", "")):
        return name
    return "관련 이미지"


def fix_file(md_path: Path, dry: bool) -> tuple[int, int]:
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    fm_end = raw.find("---", 3)
    if fm_end == -1:
        return 0, 0
    fm = raw[: fm_end + 3]
    body = raw[fm_end + 3 :]

    total, fixed = 0, 0

    def _repl(m):
        nonlocal total, fixed
        alt, url = m.group(1), m.group(2)
        total += 1
        if alt.strip():
            return m.group(0)
        fixed += 1
        new_alt = infer_alt(url)
        return f"![{new_alt}]({url})"

    new_body = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", _repl, body)

    # HTML img: alt 없는/빈 태그에 alt 추가
    def _repl_html(m):
        nonlocal total, fixed
        tag = m.group(0)
        total += 1
        src_m = re.search(r'src="([^"]+)"', tag)
        if not src_m:
            return tag
        new_alt = infer_alt(src_m.group(1))
        # alt 없거나 빈 alt면 채움
        alt_m = re.search(r'alt="[^"]*"', tag)
        if alt_m:
            if alt_m.group(0) == 'alt=""' or alt_m.group(0) == "alt=''":
                fixed += 1
                return tag.replace(alt_m.group(0), f'alt="{new_alt}"', 1)
            return tag
        fixed += 1
        if 'src=' in tag:
            return tag.replace('src="', f'alt="{new_alt}" src="', 1)
        return tag

    new_body = re.sub(r"<img\b[^>]*>", _repl_html, new_body)

    if not dry and new_body != body:
        md_path.write_text(fm + new_body, encoding="utf-8")
    return total, fixed


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
                if iss["type"] == "S5_no_alt":
                    targets.append((r["blog_id"], Path(f["file"])))
                    break

    total_fixed = 0
    for blog_id, path in targets:
        if not path.exists():
            continue
        total, fixed = fix_file(path, args.dry_run)
        total_fixed += fixed

    mode = "DRY-RUN" if args.dry_run else "적용"
    print(f"\n[{mode}] 대상 {len(targets)}건, alt 수정 {total_fixed}건")


if __name__ == "__main__":
    main()
