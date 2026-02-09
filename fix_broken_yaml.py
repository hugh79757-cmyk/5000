#!/usr/bin/env python3
"""
깨진 YAML front matter 수정 스크립트
aliases에서 줄바꿈이 잘못된 파일들을 찾아 수정
"""

import os
import re
import glob

POSTS_DIR = "/Users/twinssn/Projects/rotcha-hugo/content/posts"

def check_and_fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # front matter 찾기
    if not content.startswith('---'):
        return False, "No front matter"
    
    second_delim = content.find('---', 3)
    if second_delim == -1:
        return False, "No closing ---"
    
    front_matter = content[3:second_delim]
    body = content[second_delim+3:]
    
    # ---가 3개 이상 있으면 깨진 파일
    if content.count('---') > 2:
        return True, filepath
    
    # aliases 안에 줄바꿈 없이 닫히지 않은 따옴표가 있는지 확인
    lines = front_matter.split('\n')
    in_aliases = False
    for i, line in enumerate(lines):
        if 'aliases:' in line:
            in_aliases = True
            continue
        if in_aliases:
            stripped = line.strip()
            if stripped.startswith('- "') and not stripped.endswith('"'):
                return True, filepath
            if stripped.startswith("- '") and not stripped.endswith("'"):
                return True, filepath
            if stripped and not stripped.startswith('-') and not stripped.startswith('#'):
                if ':' in stripped:
                    in_aliases = False
    
    return False, None

def main():
    files = glob.glob(os.path.join(POSTS_DIR, "*.md"))
    broken_files = []
    
    for filepath in sorted(files):
        is_broken, info = check_and_fix_file(filepath)
        if is_broken:
            broken_files.append(filepath)
    
    print(f"깨진 파일 {len(broken_files)}개 발견:")
    print()
    for f in broken_files:
        print(os.path.basename(f))

if __name__ == "__main__":
    main()
