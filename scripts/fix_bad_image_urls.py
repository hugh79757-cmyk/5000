#!/usr/bin/env python3
"""fix_bad_image_urls.py — 깨진 이미지 URL 전수 수정.

하위 유형별 처리:
  1. placeholder  — "이미지URL"/"URL"/"image" 텍스트 → 본문 첫 실제 이미지 또는 R2 기본
  2. broken_path  — /Users/..., blob:, /images/ 절대경로 → R2 기본 플레이스홀더
  3. assets_rel   — assets/xxx, ../assets/xxx 상대경로 → R2 기본 (Hugo가 못 처리)

용법:
  python scripts/fix_bad_image_urls.py --dry-run --blog appliance-hugo
  python scripts/fix_bad_image_urls.py
"""
import argparse
import json
import re
import sys
from pathlib import Path

SKIP = ("ads-partners.coupang.com", "link.coupang.com")
DEFAULT_IMG = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp"
PLACEHOLDERS = {"이미지URL", "URL", "image", "이미지", "imageURL"}


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


def classify(url: str) -> str:
    if url in PLACEHOLDERS or "이미지URL" in url or "imageURL" in url:
        return "placeholder"
    if url.startswith(("/Users/", "/images/", "blob:", "/var/", "/tmp/")) or url.startswith("file:"):
        return "broken_path"
    if url.startswith("assets/") or url.startswith("../assets/") or url.startswith("./assets/"):
        return "assets_rel"
    return "ok"


def fix_file(md_path: Path, dry: bool) -> tuple[int, list[str]]:
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    fm_end = raw.find("---", 3)
    if fm_end == -1:
        return 0, []
    fm = raw[: fm_end + 3]
    body = raw[fm_end + 3 :]

    real_img = first_real_image(body)
    changed = 0
    details = []

    def _repl_placeholder(m):
        nonlocal changed, details
        alt, url = m.group(1), m.group(2)
        kind = classify(url.strip())
        if kind == "ok":
            return m.group(0)
        changed += 1
        details.append(f"{kind}: {url[:30]} → {real_img or DEFAULT_IMG}")
        return f"![{alt}]({real_img or DEFAULT_IMG})"

    # 마크다운 이미지
    new_body = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)", _repl_placeholder, body)
    # HTML img src
    def _repl_html(m):
        nonlocal changed, details
        url = m.group(1)
        kind = classify(url)
        if kind == "ok":
            return m.group(0)
        changed += 1
        details.append(f"{kind}: {url[:30]} → {real_img or DEFAULT_IMG}")
        return f'<img src="{real_img or DEFAULT_IMG}" alt="" loading="lazy">'

    new_body = re.sub(r'<img[^>]+src="([^"]+)"', _repl_html, new_body)

    # featureimage도 수정
    def _repl_fm(m):
        nonlocal changed, details
        url = m.group(1)
        kind = classify(url)
        if kind == "ok":
            return m.group(0)
        changed += 1
        details.append(f"fm {kind}: {url[:30]} → {real_img or DEFAULT_IMG}")
        return f"featureimage: '{real_img or DEFAULT_IMG}'"

    new_fm = re.sub(r"featureimage:\s*['\"]?(https?://[^'\s]+|이미지URL|URL|image)['\"]?", _repl_fm, fm)

    if not dry and (new_body != body or new_fm != fm):
        md_path.write_text(new_fm + new_body, encoding="utf-8")
    return changed, details


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--blog")
    ap.add_argument("--scan-json", default="/tmp/scan_all_blogs.json")
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
                if iss["type"] == "I1_bad_url":
                    targets.append((r["blog_id"], Path(f["file"])))
                    break

    total_changed = 0
    for blog_id, path in targets:
        if not path.exists():
            continue
        changed, details = fix_file(path, args.dry_run)
        if changed:
            total_changed += changed
            if args.dry_run:
                print(f"[DRY] {blog_id}: {path.name[:35]} — {changed}건")
                for d in details[:2]:
                    print(f"      {d}")

    mode = "DRY-RUN" if args.dry_run else "적용"
    print(f"\n[{mode}] 대상 {len(targets)}건, URL 수정 {total_changed}건")


if __name__ == "__main__":
    main()
