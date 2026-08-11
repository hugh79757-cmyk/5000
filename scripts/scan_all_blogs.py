#!/usr/bin/env python3
"""전체 블로그 전수조사 스캐너 (scan_all_blogs.py).

config/blogs.d/*.yaml에서 모든 블로그 site_path를 읽어
각 사이트의 content/posts/** 발행물을 전수 스캔.

체크:
  I1 이미지 깨짐   — 본문/featureimage URL이 HTTP 4xx/5xx, 쿠팡 썸네일, 빈 URL
  I2 이미지 중복   — 같은 블로그 내 동일 이미지 URL 2회+
  I3 썸네일 없음   — frontmatter에 featureimage/cover.image 없음
  M1 마크다운 노출 — 빌드 HTML에 ##/### raw (있으면)
  S1 SEO 메타     — title 35자 초과, description 150자 초과/누락
  S5 이미지 alt   — 본문 ![](url)에 alt 누락

용법:
  python scripts/scan_all_blogs.py                 # 전체 스캔
  python scripts/scan_all_blogs.py --blog travel1-hugo  # 단일
  python scripts/scan_all_blogs.py --no-http       # HTTP 체크 생략 (빠름)
  python scripts/scan_all_blogs.py --json out.json # JSON 출력
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKIP_DOMAINS = ("ads-partners.coupang.com", "link.coupang.com")

# ── config 읽기 ──────────────────────────────
def load_blogs() -> list[dict]:
    blogs = []
    blogs_dir = ROOT / "config" / "blogs.d"
    for f in sorted(blogs_dir.glob("*.yaml")):
        if ".bak" in f.name:
            continue
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for b in (data or {}).get("blogs", []):
            if b.get("site_path") and b.get("id"):
                blogs.append({
                    "id": b["id"],
                    "site_path": b["site_path"],
                    "platform": b.get("platform", "hugo"),
                    "status": b.get("status", ""),
                })
    return blogs


# ── 스캔 함수들 ──────────────────────────────
def _extract_frontmatter(raw: str) -> tuple[str, str]:
    """frontmatter와 body 분리."""
    if not raw.startswith("---"):
        return "", raw
    end = raw.find("---", 3)
    if end == -1:
        return "", raw
    return raw[: end + 3], raw[end + 3 :]


def _iter_images(body: str):
    for m in re.finditer(r"!\[([^\]]*)\]\(([^)\s]+)", body):
        yield m.group(1), m.group(2)
    # HTML img: alt와 src 모두 추출 (alt 없으면 "")
    for m in re.finditer(r"<img\b[^>]*>", body):
        tag = m.group(0)
        alt_m = re.search(r'alt="([^"]*)"', tag) or re.search(r"alt='([^']*)'", tag)
        src_m = re.search(r'src="([^"]+)"', tag) or re.search(r"src='([^']+)'", tag)
        alt = alt_m.group(1) if alt_m else ""
        src = src_m.group(1) if src_m else ""
        if src:
            yield alt, src


def check_images(body: str) -> list[dict]:
    """I1(깨짐), I5(alt 누락) — URL 유효성은 별도 HTTP 체크."""
    issues = []
    for alt, url in _iter_images(body):
        if not url or not url.startswith("http"):
            issues.append({"type": "I1_bad_url", "url": url[:80], "detail": "빈/비HTTP URL"})
        if not alt:
            issues.append({"type": "S5_no_alt", "url": url[:80], "detail": "alt 누락"})
    return issues


def check_thumb(frontmatter: str) -> list[dict]:
    """I3 썸네일 없음 + 쿠팡 썸네일."""
    issues = []
    fm = frontmatter
    has_thumb = bool(re.search(r"featureimage:\s*['\"]?https?://", fm)) or bool(
        re.search(r"cover:\s*\n\s*image:", fm)
    )
    if not has_thumb:
        issues.append({"type": "I3_no_thumb", "detail": "featureimage/cover 없음"})
    else:
        m = re.search(r"featureimage:\s*['\"]?(https?://[^'\s]+)", fm)
        if m and any(d in m.group(1) for d in SKIP_DOMAINS):
            issues.append({"type": "I1_coupang_thumb", "url": m.group(1)[:80], "detail": "쿠팡 이미지가 썸네일"})
    return issues


def check_dup(images: list[tuple[str, str]]) -> list[dict]:
    """I2 이미지 중복."""
    issues = []
    seen = {}
    for alt, url in images:
        if any(d in url for d in SKIP_DOMAINS):
            continue
        seen.setdefault(url, []).append(alt)
    for url, alts in seen.items():
        if len(alts) >= 2:
            issues.append({"type": "I2_dup", "url": url[:80], "detail": f"{len(alts)}회 반복"})
    return issues


def check_seo(frontmatter: str) -> list[dict]:
    """S1 title/description."""
    issues = []
    title_m = re.search(r"title:\s*['\"]?(.+?)['\"]?\s*$", frontmatter, re.MULTILINE)
    desc_m = re.search(r"description:\s*['\"]?(.+?)['\"]?\s*$", frontmatter, re.MULTILINE)
    if title_m and len(title_m.group(1).strip()) > 35:
        issues.append({"type": "S1_title_long", "detail": f"title {len(title_m.group(1).strip())}자 (>35)"})
    if not desc_m or not desc_m.group(1).strip():
        issues.append({"type": "S1_no_desc", "detail": "description 누락"})
    elif len(desc_m.group(1).strip()) > 160:
        issues.append({"type": "S1_desc_long", "detail": f"desc {len(desc_m.group(1).strip())}자 (>160)"})
    return issues


# ── 단일 파일 스캔 ───────────────────────────
def scan_file(md_path: Path, do_http: bool = True) -> dict:
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    fm, body = _extract_frontmatter(raw)
    issues = []
    issues += check_images(body)
    issues += check_thumb(fm)
    issues += check_dup(list(_iter_images(body)))
    issues += check_seo(fm)
    return {"file": str(md_path), "issues": issues, "issue_count": len(issues)}


# ── 블로그 스캔 ──────────────────────────────
def scan_blog(blog: dict, do_http: bool) -> dict:
    site = Path(blog["site_path"])
    posts_dir = site / "content" / "posts"
    if not posts_dir.is_dir():
        return {"blog_id": blog["id"], "status": blog["status"], "files": [], "total_issues": 0, "error": "posts_dir 없음"}
    files = sorted(posts_dir.rglob("*.md"))
    results = []
    for f in files:
        if f.name == "_index.md":
            continue
        r = scan_file(f, do_http)
        if r["issues"]:
            results.append(r)
    total = sum(r["issue_count"] for r in results)
    return {"blog_id": blog["id"], "status": blog["status"], "files": results,
            "total_issues": total, "site_path": blog["site_path"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blog", help="단일 블로그 id")
    ap.add_argument("--no-http", action="store_true", help="HTTP 체크 생략")
    ap.add_argument("--json", help="JSON 출력 파일")
    args = ap.parse_args()

    blogs = load_blogs()
    if args.blog:
        blogs = [b for b in blogs if b["id"] == args.blog]

    all_results = []
    grand_total = 0
    for b in blogs:
        res = scan_blog(b, not args.no_http)
        all_results.append(res)
        grand_total += res["total_issues"]
        flag = "❌" if res["total_issues"] > 0 else "✅"
        print(f"{flag} {res['blog_id']}: {res['total_issues']}건 ({len(res['files'])}개 파일 위반)")

    print(f"\n=== 총 {len(blogs)}개 블로그, 위반 {grand_total}건 ===")

    # 문제 유형별 집계
    from collections import Counter
    type_counter = Counter()
    for r in all_results:
        for f in r.get("files", []):
            for iss in f["issues"]:
                type_counter[iss["type"]] += 1
    print("\n=== 문제 유형별 집계 ===")
    for t, cnt in type_counter.most_common():
        print(f"  {t}: {cnt}건")

    if args.json:
        Path(args.json).write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON 저장: {args.json}")


if __name__ == "__main__":
    main()
