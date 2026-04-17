#!/usr/bin/env python3
"""본문 첫 이미지를 featureimage로 추가 (리사이즈 스킵 오버라이드 전제)"""
import re, glob, os

CUAP = "/Users/twinssn/Projects/CUAP"
targets = ["baby-hugo", "fitness-hugo", "appliance-hugo", "interior-hugo", "laptop-hugo"]
IMG_PATTERN = re.compile(r'!\[.*?\]\((https?://[^\)]+)\)')

def parse_frontmatter(content):
    if not content.startswith("---"):
        return None, None
    end = content.find("---", 3)
    if end == -1:
        return None, None
    return content[3:end], content[end+3:]

for blog in targets:
    pattern = os.path.join(CUAP, blog, "content", "**", "index.md")
    files = glob.glob(pattern, recursive=True)
    added = 0
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            content = fh.read()
        fm, body = parse_frontmatter(content)
        if fm is None or "featureimage" in fm:
            continue
        match = IMG_PATTERN.search(body)
        if not match:
            continue
        img_url = match.group(1)
        fm = fm.rstrip("\n") + '\nfeatureimage: "' + img_url + '"\n'
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("---" + fm + "---" + body)
        added += 1
    print(f"[{blog}] featureimage added: {added}/{len(files)}")
