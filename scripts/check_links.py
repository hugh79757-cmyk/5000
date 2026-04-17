#!/usr/bin/env python3
"""내부링크 전수조사 — 404 찾기"""
import re, glob, os
from urllib.parse import unquote

ALL_PROJECTS = {
    "CUAP": ["baby-hugo", "fitness-hugo", "appliance-hugo", "interior-hugo", "laptop-hugo"],
    "CAP": ["deal-hugo", "compare-hugo", "ev-hugo", "guide-hugo", "hotissue-hugo", "pick-hugo", "rank-hugo", "tco-hugo"],
    "RAP": ["rap-hugo", "rap2-hugo", "rap3-hugo", "rap4-hugo", "rap5-hugo"],
    "ETAP": [],
    "TAP": [],
}

BASE = "/Users/twinssn/Projects"

# ETAP/TAP 동적 탐색
for proj in ["ETAP", "TAP"]:
    proj_dir = os.path.join(BASE, proj)
    if os.path.exists(proj_dir):
        ALL_PROJECTS[proj] = [d for d in os.listdir(proj_dir) if d.endswith("-hugo") and os.path.isdir(os.path.join(proj_dir, d))]

# href= 뒤에 따옴표 있을 수도 없을 수도 있음
HREF_PATTERN = re.compile(r'href=["\']?(/[^\s"\'><]+)')

SKIP_EXT = (".png", ".jpg", ".jpeg", ".webp", ".ico", ".xml", ".json", ".txt",
            ".svg", ".woff", ".woff2", ".css", ".js", ".webmanifest")

for project, blogs in ALL_PROJECTS.items():
    for blog in sorted(blogs):
        public_dir = os.path.join(BASE, project, blog, "public")
        if not os.path.exists(public_dir):
            continue

        html_files = glob.glob(os.path.join(public_dir, "**", "*.html"), recursive=True)
        if not html_files:
            continue

        all_links = set()
        for f in html_files:
            with open(f, "r", encoding="utf-8") as fh:
                content = fh.read()
            for match in HREF_PATTERN.finditer(content):
                href = match.group(1)
                if href == "/" or href.startswith("/#"):
                    continue
                if href.startswith("/css/") or href.startswith("/js/") or href.startswith("/lib/"):
                    continue
                if any(href.lower().endswith(ext) for ext in SKIP_EXT):
                    continue
                all_links.add(href)

        broken = []
        for link in sorted(all_links):
            decoded = unquote(link).rstrip("/")
            check = [
                os.path.join(public_dir, decoded.lstrip("/"), "index.html"),
                os.path.join(public_dir, decoded.lstrip("/")),
                os.path.join(public_dir, decoded.lstrip("/") + ".html"),
                os.path.join(public_dir, decoded.lstrip("/"), "index.xml"),
            ]
            if not any(os.path.exists(p) for p in check):
                broken.append(unquote(link))

        if broken:
            print(f"[{project}/{blog}] {len(broken)} BROKEN / {len(all_links)} total:")
            for b in broken[:15]:
                print(f"  404: {b}")
            if len(broken) > 15:
                print(f"  ... +{len(broken)-15} more")
        else:
            print(f"[{project}/{blog}] OK ({len(all_links)} links)")
