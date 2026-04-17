#!/usr/bin/env python3
"""기존 글의 본문 첫 이미지를 front matter cover.image로 추가 + AdSense raw HTML 제거"""
import re, glob, os

CUAP = "/Users/twinssn/Projects/CUAP"
targets = ["baby-hugo", "fitness-hugo", "appliance-hugo", "interior-hugo", "laptop-hugo"]

IMG_PATTERN = re.compile(r'!\[.*?\]\((https?://[^\)]+)\)')
AD_PATTERN = re.compile(
    r'\n*<script async src="https://pagead2\.googlesyndication\.com.*?</script>\n*',
    re.DOTALL
)

def parse_frontmatter(content):
    if not content.startswith("---"):
        return None, None
    end = content.find("---", 3)
    if end == -1:
        return None, None
    fm = content[3:end]
    body = content[end + 3:]
    return fm, body

for blog in targets:
    pattern = os.path.join(CUAP, blog, "content", "**", "index.md")
    files = glob.glob(pattern, recursive=True)
    ad_removed = 0
    cover_added = 0

    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            content = fh.read()

        modified = False

        cleaned = AD_PATTERN.sub("", content)
        if cleaned != content:
            content = cleaned
            modified = True
            ad_removed += 1

        fm, body = parse_frontmatter(content)
        if fm is not None and "cover:" not in fm:
            match = IMG_PATTERN.search(body)
            if match:
                img_url = match.group(1)
                fm = fm.rstrip("\n") + "\ncover:\n  image: \"" + img_url + "\"\n"
                content = "---" + fm + "---" + body
                modified = True
                cover_added += 1

        if modified:
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(content)

    print(f"[{blog}] ads removed: {ad_removed}, cover added: {cover_added} / total: {len(files)}")
