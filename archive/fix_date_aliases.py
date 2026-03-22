#!/usr/bin/env python3
"""
날짜 포함 URL aliases 추가 스크립트
/posts/2024-01-01-slug/ → /posts/slug/ 리디렉션
"""

import os
import re
import glob

POSTS_DIR = "/Users/twinssn/Projects/rotcha-hugo/content/posts"
DRY_RUN = False

def get_date_and_slug_from_filename(filename):
    """파일명에서 날짜와 slug 추출"""
    basename = os.path.basename(filename)
    match = re.match(r'(\d{4}-\d{2}-\d{2})-(.+)\.md$', basename)
    if match:
        return match.group(1), match.group(2)
    return None, None

def parse_front_matter(content):
    if not content.startswith('---'):
        return None, content
    second_delimiter = content.find('---', 3)
    if second_delimiter == -1:
        return None, content
    front_matter = content[3:second_delimiter].strip()
    body = content[second_delimiter + 3:]
    return front_matter, body

def extract_existing_aliases(front_matter):
    aliases = []
    in_aliases = False
    for line in front_matter.split('\n'):
        stripped = line.strip()
        if stripped.startswith('aliases:'):
            in_aliases = True
            if '[' in stripped:
                match = re.findall(r'["\']([^"\']+)["\']', stripped)
                aliases.extend(match)
                in_aliases = False
            continue
        if in_aliases:
            if stripped and not stripped.startswith('-') and not stripped.startswith('#'):
                if ':' in stripped and not stripped.startswith('"') and not stripped.startswith("'"):
                    break
            if stripped.startswith('- '):
                alias = stripped[2:].strip().strip('"').strip("'")
                if alias:
                    aliases.append(alias)
    return aliases

def generate_date_aliases(date_str, slug, existing_aliases):
    """날짜 포함 URL aliases 생성"""
    needed = []
    
    normalized_existing = set()
    for alias in existing_aliases:
        normalized_existing.add(alias.strip('/').lower())
    
    # 날짜 포함 URL 패턴
    patterns = [
        f"/posts/{date_str}-{slug}",
        f"/posts/{date_str}-{slug}/",
    ]
    
    for pattern in patterns:
        normalized = pattern.strip('/').lower()
        if normalized not in normalized_existing and pattern not in existing_aliases:
            needed.append(pattern)
    
    return needed

def update_front_matter_with_aliases(front_matter, new_aliases):
    lines = front_matter.split('\n')
    result_lines = []
    in_aliases = False
    aliases_added = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('aliases:'):
            in_aliases = True
            result_lines.append(line)
            continue
        if in_aliases:
            if stripped.startswith('- '):
                result_lines.append(line)
                continue
            else:
                in_aliases = False
                if not aliases_added:
                    for new_alias in new_aliases:
                        result_lines.append(f'  - "{new_alias}"')
                    aliases_added = True
        result_lines.append(line)
    
    if in_aliases and not aliases_added:
        for new_alias in new_aliases:
            result_lines.append(f'  - "{new_alias}"')
    
    return '\n'.join(result_lines)

def process_file(filepath):
    date_str, slug = get_date_and_slug_from_filename(filepath)
    if not date_str or not slug:
        return None, "No date/slug in filename"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    front_matter, body = parse_front_matter(content)
    if front_matter is None:
        return None, "No front matter"
    
    existing_aliases = extract_existing_aliases(front_matter)
    new_aliases = generate_date_aliases(date_str, slug, existing_aliases)
    
    if not new_aliases:
        return None, "Already complete"
    
    updated_front_matter = update_front_matter_with_aliases(front_matter, new_aliases)
    new_content = f"---\n{updated_front_matter}\n---{body}"
    
    return {
        'filepath': filepath,
        'date': date_str,
        'slug': slug,
        'new_aliases': new_aliases,
        'new_content': new_content
    }, "Success"

def main():
    print("=" * 60)
    print("날짜 포함 URL aliases 추가 스크립트")
    print("=" * 60)
    print(f"DRY_RUN: {DRY_RUN}")
    print()
    
    files = glob.glob(os.path.join(POSTS_DIR, "*.md"))
    print(f"총 {len(files)}개 파일")
    print()
    
    updated_count = 0
    skipped_count = 0
    updates = []
    
    for filepath in sorted(files):
        result, status = process_file(filepath)
        if result is None:
            skipped_count += 1
        else:
            updated_count += 1
            updates.append(result)
    
    print("=" * 60)
    print("결과")
    print("=" * 60)
    print(f"업데이트 필요: {updated_count}개")
    print(f"이미 완료: {skipped_count}개")
    print()
    
    if updates:
        print("미리보기 (처음 10개):")
        print("-" * 40)
        for update in updates[:10]:
            print(f"\n{os.path.basename(update['filepath'])}")
            for alias in update['new_aliases']:
                print(f"  + {alias}")
        if len(updates) > 10:
            print(f"\n... 외 {len(updates) - 10}개")
    
    if not DRY_RUN and updates:
        print()
        print("파일 수정 중...")
        for update in updates:
            with open(update['filepath'], 'w', encoding='utf-8') as f:
                f.write(update['new_content'])
        print(f"{len(updates)}개 파일 수정 완료!")
    elif DRY_RUN and updates:
        print()
        print("=" * 60)
        print("DRY_RUN 모드입니다. 실제 수정하려면:")
        print("sed -i '' 's/DRY_RUN = False/DRY_RUN = False/' fix_date_aliases.py")
        print("python3 fix_date_aliases.py")
        print("=" * 60)

if __name__ == "__main__":
    main()
