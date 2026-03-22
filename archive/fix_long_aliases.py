#!/usr/bin/env python3
import os
import re
from pathlib import Path

POSTS_DIR = '/Users/twinssn/Desktop/rotcha-hugo/content/posts'
MAX_ALIAS_LEN = 100

for md_file in Path(POSTS_DIR).glob('*.md'):
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # aliases 찾기
    match = re.search(r'aliases:\s*\n\s*-\s*(/entry/[^\n]+)', content)
    if match:
        alias = match.group(1)
        if len(alias) > MAX_ALIAS_LEN:
            # 짧게 자르기
            short_alias = alias[:MAX_ALIAS_LEN].rsplit('-', 1)[0] + '/'
            new_content = content.replace(alias, short_alias)
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✅ 수정: {md_file.name}")

print("완료!")
