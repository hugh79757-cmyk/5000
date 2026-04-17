#!/usr/bin/env python3
"""cover.image -> featureimage 변환 (Blowfish 테마용)"""
import re, glob, os

CUAP = "/Users/twinssn/Projects/CUAP"
targets = ["baby-hugo", "fitness-hugo", "appliance-hugo", "interior-hugo", "laptop-hugo"]

COVER_BLOCK = re.compile(r'cover:\n  image: "(.*?)"\n')
IMG_PATTERN = re.compile(r'!\[.*?\]\((https?://[^\)]+)\)')

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
    fixed = 0

    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            content = fh.read()

        fm, body = parse_frontmatter(content)
        if fm is None:
            continue

        modified = False
        img_url = None

        # 기존 cover: block에서 URL 추출 후 제거
        match = COVER_BLOCK.search(fm)
        if match:
            img_url = match.group(1)
            fm = COVER_BLOCK.sub("", fm)
            modified = True

        # cover가 없었으면 본문 첫 이미지에서 추출
        if img_url is None:
            img_match = IMG_PATTERN.search(body)
            if img_match:
                img_url = img_match.group(1)

        # featureimage가 아직 없고 URL이 있으면 추가
        if img_url and "featureimage" not in fm:
            fm = fm.rstrip("\n") + "\nfeatureimage: \"" + img_url + "\"\n"
            modified = True

        if modified:
            content = "---" + fm + "---" + body
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(content)
            fixed += 1

    print(f"[{blog}] fixed: {fixed}/{len(files)}")
