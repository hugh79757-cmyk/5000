#!/usr/bin/env python3
import os
import re
from pathlib import Path

BACKUP_DIR = Path("/Users/twinssn/Desktop/rotcha-hugo/rankingoneto-1-1")
POSTS_DIR = Path("/Users/twinssn/Desktop/rotcha-hugo/content/posts")

# 숫자 폴더에서 HTML 파일의 제목 추출
def get_title_from_html(html_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r'<title>([^<]+)</title>', content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

# 제목으로 마크다운 파일 찾기
def find_md_by_title(title):
    title_clean = re.sub(r'[^\w가-힣]', '', title.lower())
    for md_file in POSTS_DIR.glob("*.md"):
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
        if match:
            md_title = re.sub(r'[^\w가-힣]', '', match.group(1).lower())
            if md_title == title_clean or title_clean in md_title or md_title in title_clean:
                return md_file
    return None

# aliases에 숫자 추가
def add_alias_to_md(md_path, number):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_alias = f"/{number}/"
    
    # 이미 있는지 확인
    if new_alias in content:
        return False
    
    # aliases 섹션 찾기
    if re.search(r'^aliases:', content, re.MULTILINE):
        # 기존 aliases에 추가
        content = re.sub(
            r'(aliases:\s*\n(?:\s*-\s*/[^\n]+\n)*)',
            f'\\1  - {new_alias}\n',
            content
        )
    else:
        # aliases 섹션 새로 추가 (draft: 다음에)
        content = re.sub(
            r'(draft:\s*\w+\n)',
            f'\\1aliases:\n  - {new_alias}\n',
            content
        )
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return True

# 메인 실행
updated = 0
not_found = []

for folder in sorted(BACKUP_DIR.iterdir()):
    if folder.is_dir() and folder.name.isdigit():
        number = folder.name
        html_files = list(folder.glob("*.html"))
        
        if html_files:
            title = get_title_from_html(html_files[0])
            if title:
                md_file = find_md_by_title(title)
                if md_file:
                    if add_alias_to_md(md_file, number):
                        print(f"✅ /{number}/ → {md_file.name}")
                        updated += 1
                else:
                    not_found.append((number, title[:30]))

print(f"\n완료: {updated}개 aliases 추가")
print(f"못 찾은 파일: {len(not_found)}개")
if not_found[:5]:
    print("예시:", not_found[:5])
