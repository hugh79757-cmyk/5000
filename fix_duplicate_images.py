#!/usr/bin/env python3
import re
from pathlib import Path

POSTS_DIR = Path("/Users/twinssn/Desktop/rotcha-hugo/content/posts")

fixed = 0
for md_file in POSTS_DIR.glob("*.md"):
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 연속된 동일 이미지 제거 (빈 줄 포함)
    content = re.sub(
        r'(!\[image\]\([^)]+\))\s*\n\s*\n\s*\1',
        r'\1',
        content
    )
    
    if content != original:
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ {md_file.name}")
        fixed += 1

print(f"\n완료: {fixed}개 파일 수정")
