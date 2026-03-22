#!/usr/bin/env python3
"""
티스토리 → Hugo 마이그레이션 404 해결
/entry/글제목 패턴을 aliases로 추가
"""
import os
import re
import urllib.parse

POSTS_DIR = "/Users/twinssn/Desktop/rotcha-hugo/content/posts"

def get_title_from_content(content):
    """Front matter에서 title 추출"""
    title_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
    if title_match:
        return title_match.group(1).strip('"\'')
    return None

def title_to_entry_slug(title):
    """티스토리 /entry/ URL 형식으로 변환"""
    # 공백을 -로 변환
    slug = title.replace(' ', '-')
    # URL 인코딩
    return slug

def add_tistory_aliases(filepath, filename):
    """티스토리 구 URL을 aliases로 추가"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    title = get_title_from_content(content)
    if not title:
        return False, []
    
    # 가능한 티스토리 URL 패턴들
    aliases_to_add = []
    
    # 1. /entry/제목 (티스토리 기본)
    entry_slug = title_to_entry_slug(title)
    aliases_to_add.append(f'/entry/{entry_slug}')
    
    # 2. 공백 없는 버전
    aliases_to_add.append(f'/entry/{title.replace(" ", "")}')
    
    # 3. 파일명에서 slug 추출
    name = filename.replace('.md', '')
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.+)$', name)
    if match:
        file_slug = match.group(4)
        aliases_to_add.append(f'/entry/{file_slug}')
        aliases_to_add.append(f'/{file_slug}/')
    
    # 기존 aliases 확인
    existing = set()
    aliases_match = re.search(r'aliases:\s*\n((?:\s*-\s*.+\n)*)', content)
    if aliases_match:
        existing = set(re.findall(r'-\s*(.+)', aliases_match.group(1)))
    
    # 새로 추가할 것만 필터링
    to_add = [a for a in aliases_to_add if a not in existing and len(a) > 3]
    
    # 중복 제거
    to_add = list(dict.fromkeys(to_add))
    
    if not to_add:
        return False, []
    
    # front matter 수정
    parts = content.split('---', 2)
    if len(parts) >= 3:
        front_matter = parts[1]
        body = parts[2]
        
        if 'aliases:' in front_matter:
            for alias in to_add:
                front_matter = re.sub(
                    r'(aliases:\s*\n)',
                    f'\\1  - "{alias}"\n',
                    front_matter
                )
        else:
            alias_section = '\naliases:\n' + '\n'.join(f'  - "{a}"' for a in to_add) + '\n'
            front_matter = front_matter.rstrip() + alias_section
        
        new_content = '---' + front_matter + '---' + body
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True, to_add
    
    return False, []

def main():
    if not os.path.exists(POSTS_DIR):
        print(f"경로 없음: {POSTS_DIR}")
        return
        
    count = 0
    total = 0
    
    files = sorted([f for f in os.listdir(POSTS_DIR) if f.endswith('.md')])
    
    for filename in files:
        filepath = os.path.join(POSTS_DIR, filename)
        success, added = add_tistory_aliases(filepath, filename)
        
        if success:
            print(f"✅ {filename[:45]}...")
            for a in added[:2]:
                print(f"   → {a}")
            if len(added) > 2:
                print(f"   ... 외 {len(added)-2}개")
            count += 1
            total += len(added)
    
    print(f"\n{'='*50}")
    print(f"완료: {count}개 파일, 총 {total}개 aliases 추가")

if __name__ == '__main__':
    main()
