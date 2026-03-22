import os
import re

POSTS_DIR = "/Users/twinssn/Desktop/rotcha-hugo/content/posts"

count = 0
for filename in os.listdir(POSTS_DIR):
    if not filename.endswith('.md'):
        continue
    
    match = re.match(r'^(\d{4}-\d{2}-\d{2})-(.+)\.md$', filename)
    if not match:
        continue
    
    slug = match.group(2)
    entry_alias = f"/entry/{slug}/"
    
    filepath = os.path.join(POSTS_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 이미 entry alias가 있으면 건너뛰기
    if f"/entry/{slug}" in content:
        continue
    
    # aliases 섹션에 추가
    if "aliases:" in content:
        content = content.replace("aliases:", f"aliases:\n  - {entry_alias}", 1)
    else:
        # aliases 없으면 draft: 다음에 추가
        content = re.sub(r'(draft:\s*\w+)', f'\\1\naliases:\n  - {entry_alias}', content, 1)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    count += 1
    if count % 100 == 0:
        print(f"진행 중... {count}개")

print(f"✅ {count}개 entry aliases 추가 완료!")
