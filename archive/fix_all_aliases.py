#!/usr/bin/env python3
import os
import re
import glob

POSTS_DIR = "/Users/twinssn/Projects/rotcha-hugo/content/posts"
DRY_RUN = True

def extract_slug_from_filename(filename):
    basename = os.path.basename(filename)
    match = re.match(r'\d{4}-\d{2}-\d{2}-(.+)\.md$', basename)
    if match:
        return match.group(1)
    return None

def parse_front_matter(content):
    if not content.startswith('---'):
        return None, None, content
    second_delimiter = content.find('---', 3)
    if second_delimiter == -1:
        return None, None, content
    front_matter = content[3:second_delimiter].strip()
    body = content[second_delimiter + 3:]
    return front_matter, second_delimiter, body

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

def extract_slug_from_front_matter(front_matter):
    for line in front_matter.split('\n'):
        if line.strip().startswith('slug:'):
            slug = line.split(':', 1)[1].strip().strip('"').strip("'")
            return slug
    return None

def generate_needed_aliases(slug, existing_aliases):
    needed = []
    normalized_existing = set()
    for alias in existing_aliases:
        normalized = alias.strip('/').lower()
        normalized_existing.add(normalized)
    patterns = [
        f"/entry/{slug}",
        f"/entry/{slug}/",
    ]
    for pattern in patterns:
        normalized_pattern = pattern.strip('/').lower()
        if normalized_pattern not in normalized_existing:
            if pattern not in existing_aliases:
                needed.append(pattern)
    return needed

def update_front_matter_with_aliases(front_matter, new_aliases):
    lines = front_matter.split('\n')
    result_lines = []
    in_aliases = False
    aliases_added = False
    for i, line in enumerate(lines):
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
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    front_matter, delimiter_pos, body = parse_front_matter(content)
    if front_matter is None:
        return None, "No front matter"
    slug = extract_slug_from_front_matter(front_matter)
    if not slug:
        slug = extract_slug_from_filename(filepath)
    if not slug:
        return None, "No slug found"
    existing_aliases = extract_existing_aliases(front_matter)
    new_aliases = generate_needed_aliases(slug, existing_aliases)
    if not new_aliases:
        return None, "Already complete"
    updated_front_matter = update_front_matter_with_aliases(front_matter, new_aliases)
    new_content = f"---\n{updated_front_matter}\n---{body}"
    return {
        'filepath': filepath,
        'slug': slug,
        'existing_aliases': existing_aliases,
        'new_aliases': new_aliases,
        'new_content': new_content
    }, "Success"

def main():
    print("=" * 60)
    print("rotcha.kr 404 오류 해결 스크립트")
    print("=" * 60)
    print(f"DRY_RUN 모드: {DRY_RUN}")
    print()
    files = glob.glob(os.path.join(POSTS_DIR, "*.md"))
    print(f"총 {len(files)}개 파일 발견")
    print()
    updated_count = 0
    skipped_count = 0
    error_count = 0
    updates = []
    for filepath in sorted(files):
        result, status = process_file(filepath)
        if result is None:
            if status == "Already complete":
                skipped_count += 1
            else:
                error_count += 1
                print(f"[오류] {os.path.basename(filepath)}: {status}")
        else:
            updated_count += 1
            updates.append(result)
    print()
    print("=" * 60)
    print("처리 결과 요약")
    print("=" * 60)
    print(f"업데이트 필요: {updated_count}개")
    print(f"이미 완료됨: {skipped_count}개")
    print(f"오류: {error_count}개")
    print()
    if updates:
        print("=" * 60)
        print("추가될 aliases 미리보기 (처음 10개)")
        print("=" * 60)
        for update in updates[:10]:
            print(f"\n파일: {os.path.basename(update['filepath'])}")
            print(f"   slug: {update['slug']}")
            print(f"   추가할 aliases:")
            for alias in update['new_aliases']:
                print(f"      + {alias}")
        if len(updates) > 10:
            print(f"\n... 외 {len(updates) - 10}개 파일")
    if not DRY_RUN and updates:
        print()
        print("파일 수정 중...")
        for update in updates:
            with open(update['filepath'], 'w', encoding='utf-8') as f:
                f.write(update['new_content'])
        print(f"{len(updates)}개 파일 수정 완료!")
    elif DRY_RUN and updates:
        print()
        print("DRY_RUN 모드입니다. 실제 수정하려면:")
        print("sed -i '' 's/DRY_RUN = True/DRY_RUN = False/' fix_all_aliases.py")
        print("python3 fix_all_aliases.py")

if __name__ == "__main__":
    main()
