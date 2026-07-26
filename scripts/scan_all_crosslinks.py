#!/usr/bin/env python3
"""scan_all_crosslinks.py — 전수 검증: 10개 CUAP 블로그 모든 크로스링크 스캔

Phase 49-B Step 1. Scans ALL content/posts/*/index.md across 10 CUAP blogs,
extracts every crosslink href targeting informationhot.kr subdomains, and
checks whether the target post slug directory exists on local disk (ground truth).

Usage:
    python3 scripts/scan_all_crosslinks.py                      # full scan, print report
    python3 scripts/scan_all_crosslinks.py --json               # output as JSON (for consumers)
    python3 scripts/scan_all_crosslinks.py --blog baby-hugo     # single blog only
"""

import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────
CUAP_ROOT = "/Users/twinssn/Projects/CUAP"

CUAP_BLOGS = [
    "appliance-hugo",
    "baby-hugo",
    "beauty-hugo",
    "camping-hugo",
    "fitness-hugo",
    "health-hugo",
    "interior-hugo",
    "kitchen-hugo",
    "laptop-hugo",
    "pet-hugo",
]

# Subdomain → blog_id mapping
SUBDOMAIN_TO_BLOG = {
    "appliance": "appliance-hugo",
    "baby": "baby-hugo",
    "beauty": "beauty-hugo",
    "camping": "camping-hugo",
    "fitness": "fitness-hugo",
    "health": "health-hugo",
    "interior": "interior-hugo",
    "kitchen": "kitchen-hugo",
    "laptop": "laptop-hugo",
    "pet": "pet-hugo",
}

# Target domains that are NOT CUAP blogs (e.g. stock.informationhot.kr)
# We detect these but report them separately
NON_CUAP_DOMAINS = {"stock", "senior", "car", "travel", "gap", "rap"}

# Regex patterns for crosslink hrefs (regular and escaped quotes)
# Captures: subdomain, slug
HREF_PATTERN = re.compile(
    r'href="https://([\w-]+)\.informationhot\.kr/posts/([^"/]+)/"'
    r'|href=\\"https://([\w-]+)\.informationhot\.kr/posts/([^"\\]+)\\"'
)

# JSON-LD url pattern (self-referencing canonical URL — NOT a crosslink)
JSONLD_URL_PATTERN = re.compile(
    r'"url":\s*"https://[\w-]+\.informationhot\.kr/posts/[^"]+/"'
)

# Link text extraction pattern
LINK_TEXT_PATTERN = re.compile(
    r'href="[^"]*"[^>]*>([^<]+)<'
    r'|href=\\"[^"\\]*\\"[^>]*>([^<]+)<'
)


# ── Helper functions ───────────────────────────────────────────────────────

def get_link_text(content: str, href: str) -> str:
    """Extract visible link text for a given href from the content."""
    escaped_href = re.escape(href)
    for quote_group in [
        (f'href="{escaped_href}"', f'href="{escaped_href}"'),
        (f'href=\\"{escaped_href}\\"', f'href=\\"{escaped_href}\\"'),
    ]:
        pattern = rf'{quote_group[0]}[^>]*>([^<]+)<'
        m = re.search(pattern, content)
        if m:
            text = m.group(1).strip()
            # Strip emoji/icon prefixes
            text = re.sub(r'^[^\w\s]+', '', text).strip()
            return text
    return ""


def slug_exists_on_disk(target_blog: str, slug: str) -> bool:
    """Check if a post slug directory exists on disk for the target blog."""
    posts_dir = os.path.join(CUAP_ROOT, target_blog, "content", "posts")
    if not os.path.isdir(posts_dir):
        return False
    return os.path.isdir(os.path.join(posts_dir, slug))


def extract_crosslinks(content: str, source_file: str, source_blog: str):
    """Extract all crosslink hrefs from content, excluding self-ref canonical URLs."""
    results = []

    # Get self-referencing URLs from JSON-LD to exclude them
    self_ref_urls = set()
    for m in JSONLD_URL_PATTERN.finditer(content):
        url = m.group(0).split('"')[1] if '"' in m.group(0) else ""
        if url:
            self_ref_urls.add(url)

    # Find all href matches
    for m in HREF_PATTERN.finditer(content):
        # Groups: (sub_regular, slug_regular, sub_escaped, slug_escaped)
        sub = m.group(1) or m.group(3)
        slug = m.group(2) or m.group(4)
        # Strip trailing slashes from captured slug (escaped pattern captures trailing /)
        slug = slug.rstrip('/')

        # Reconstruct the full href
        href = f"https://{sub}.informationhot.kr/posts/{slug}/"

        # Skip self-referencing canonical URLs
        if href in self_ref_urls:
            continue

        # Skip the blog's own links (self-link)
        own_sub = source_blog.replace("-hugo", "")
        if sub == own_sub:
            continue

        link_text = get_link_text(content, href)

        results.append({
            "href": href,
            "subdomain": sub,
            "slug": slug,
            "link_text": link_text,
            "source_file": source_file,
        })

    return results


def analyze_crosslink(link: dict):
    """Analyze a single crosslink — determine if valid or broken."""
    target_blog = SUBDOMAIN_TO_BLOG.get(link["subdomain"])

    if target_blog:
        exists = slug_exists_on_disk(target_blog, link["slug"])
        return {
            **link,
            "target_blog": target_blog,
            "exists": exists,
            "status": "OK" if exists else "404",
            "category": "cuap",
        }
    elif link["subdomain"] in NON_CUAP_DOMAINS:
        return {
            **link,
            "target_blog": None,
            "exists": False,
            "status": "NON_CUAP",
            "category": "non_cuap",
        }
    else:
        return {
            **link,
            "target_blog": None,
            "exists": False,
            "status": "UNKNOWN_DOMAIN",
            "category": "unknown",
        }


# ── Main scan ──────────────────────────────────────────────────────────────

def scan_blog(blog_id: str):
    """Scan a single CUAP blog for all crosslinks."""
    posts_glob = os.path.join(CUAP_ROOT, blog_id, "content", "posts", "*", "index.md")
    md_files = sorted(glob.glob(posts_glob))

    blog_links = []
    blog_self_refs = 0

    for md_path in md_files:
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        links = extract_crosslinks(content, md_path, blog_id)
        blog_links.extend(links)

        # Count JSON-LD self-refs
        self_refs = len(JSONLD_URL_PATTERN.findall(content))
        blog_self_refs += self_refs

    return blog_links, len(md_files), blog_self_refs


def main():
    blogs_to_scan = CUAP_BLOGS
    output_json = "--json" in sys.argv

    # Filter by specific blog if requested
    for arg in sys.argv[1:]:
        if arg.startswith("--blog="):
            blog_filter = arg.split("=", 1)[1]
            if blog_filter in CUAP_BLOGS:
                blogs_to_scan = [blog_filter]
            else:
                print(f"Unknown blog: {blog_filter}")
                print(f"Available: {', '.join(CUAP_BLOGS)}")
                sys.exit(1)

    # ── Scan ──
    all_links = []
    blog_stats = {}

    for blog_id in blogs_to_scan:
        links, total_files, self_refs = scan_blog(blog_id)
        all_links.extend(links)

        blog_stats[blog_id] = {
            "total_files": total_files,
            "total_crosslinks": len(links),
            "self_refs": self_refs,
        }

    # ── Analyze ──
    analyzed = [analyze_crosslink(link) for link in all_links]

    cuap_links = [a for a in analyzed if a["category"] == "cuap"]
    ok_links = [a for a in cuap_links if a["status"] == "OK"]
    broken_links = [a for a in cuap_links if a["status"] == "404"]
    non_cuap_links = [a for a in analyzed if a["category"] == "non_cuap"]
    unknown_links = [a for a in analyzed if a["category"] == "unknown"]

    # ── Per-blog breakdown ──
    per_blog = defaultdict(lambda: {"total": 0, "ok": 0, "broken": 0, "non_cuap": 0})
    for a in analyzed:
        src_sub = a["source_file"].replace(CUAP_ROOT + "/", "").split("/")[0]
        per_blog[src_sub]["total"] += 1
        if a["status"] == "OK":
            per_blog[src_sub]["ok"] += 1
        elif a["status"] == "404":
            per_blog[src_sub]["broken"] += 1
        else:
            per_blog[src_sub]["non_cuap"] += 1

    # Breakdown by TARGET blog for broken links
    broken_by_target = defaultdict(list)
    for bl in broken_links:
        broken_by_target[bl["target_blog"]].append(bl)

    # ── Timestamp ──
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Output ──
    if output_json:
        report = {
            "timestamp": ts,
            "total_files": sum(s["total_files"] for s in blog_stats.values()),
            "total_self_refs": sum(s["self_refs"] for s in blog_stats.values()),
            "total_crosslinks": len(analyzed),
            "cuap_crosslinks": len(cuap_links),
            "ok": len(ok_links),
            "broken": len(broken_links),
            "non_cuap": len(non_cuap_links),
            "unknown": len(unknown_links),
            "per_blog": {k: dict(v) for k, v in per_blog.items()},
            "broken_links": [
                {
                    "source_file": b["source_file"],
                    "href": b["href"],
                    "target_blog": b["target_blog"],
                    "slug": b["slug"],
                    "link_text": b["link_text"],
                }
                for b in sorted(broken_links, key=lambda x: x["source_file"])
            ],
            "broken_by_target": {
                blog: [
                    {"source_file": b["source_file"], "href": b["href"], "link_text": b["link_text"]}
                    for b in links
                ]
                for blog, links in sorted(broken_by_target.items())
            },
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report

    # ── Terminal Report ──
    total_files = sum(s["total_files"] for s in blog_stats.values())
    total_self_refs = sum(s["self_refs"] for s in blog_stats.values())

    print("=" * 72)
    print(f"  CUAP 크로스링크 전수 검증 리포트")
    print(f"  스캔 시간: {ts}")
    print(f"  대상: {len(blogs_to_scan)}개 블로그")
    print("=" * 72)
    print()

    # Per-blog scan summary
    print(f"{'블로그':20s} {'포스트':>7s} {'크로스링크':>10s} {'정상':>6s} {'404':>5s} {'기타':>5s}")
    print("-" * 59)
    for blog_id in blogs_to_scan:
        s = blog_stats[blog_id]
        pb = per_blog[blog_id]
        print(f"{blog_id:20s} {s['total_files']:7d} {s['total_crosslinks']:10d} {pb['ok']:6d} {pb['broken']:5d} {pb['non_cuap']:5d}")

    total_crosslinks = sum(pb["total"] for pb in per_blog.values())
    total_ok = sum(pb["ok"] for pb in per_blog.values())
    total_broken = sum(pb["broken"] for pb in per_blog.values())
    total_other = sum(pb["non_cuap"] for pb in per_blog.values())

    print("-" * 59)
    print(f"{'TOTAL':20s} {total_files:7d} {total_crosslinks:10d} {total_ok:6d} {total_broken:5d} {total_other:5d}")
    print()

    # Summary
    print(f"  총 파일 스캔:  {total_files:,}")
    print(f"  JSON-LD self-refs (제외): {total_self_refs}")
    print(f"  총 크로스링크 추출: {total_crosslinks}")
    print(f"  ─ 정상 (OK):   {total_ok}")
    print(f"  ─ 404 (없음):  {total_broken}")
    print(f"  ─ 기타 도메인: {total_other}")
    print()

    if broken_links:
        print("=" * 72)
        print(f"  ⚠️  404 크로스링크 상세 (총 {len(broken_links)}건)")
        print("=" * 72)
        print()

        # Group by target blog
        for target_blog in sorted(broken_by_target.keys()):
            bls = broken_by_target[target_blog]
            print(f"  ▶ 대상: {target_blog} ({len(bls)}건)")
            print()
            for b in bls:
                src_short = b["source_file"].replace(CUAP_ROOT + "/", "")
                print(f"    소스: {src_short}")
                print(f"    링크: {b['href']}")
                if b["link_text"]:
                    print(f"    텍스트: {b['link_text']}")
                print()

    if non_cuap_links:
        print("=" * 72)
        print(f"  ℹ️  기타 도메인 링크 (Non-CUAP, {len(non_cuap_links)}건)")
        print("=" * 72)
        for a in non_cuap_links:
            src_short = a["source_file"].replace(CUAP_ROOT + "/", "")
            print(f"    {src_short}")
            print(f"    {a['href']}")
            print()

    if unknown_links:
        print(f"  ⚠️  알 수 없는 도메인: {len(unknown_links)}건")

    print()
    print("=" * 72)
    print(f"  리포트 완료")
    print("=" * 72)

    return {
        "timestamp": ts,
        "total_files": total_files,
        "total_crosslinks": total_crosslinks,
        "ok": total_ok,
        "broken": total_broken,
        "non_cuap": total_other,
        "per_blog": {k: dict(v) for k, v in per_blog.items()},
        "broken_links": broken_links,
        "broken_by_target": dict(broken_by_target),
    }


if __name__ == "__main__":
    main()
