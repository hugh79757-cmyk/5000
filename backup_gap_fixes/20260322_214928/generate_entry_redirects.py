import os
import re

POSTS_DIR = "/Users/twinssn/Desktop/rotcha-hugo/content/posts"
REDIRECTS_FILE = "/Users/twinssn/Desktop/rotcha-hugo/static/_redirects"

# 기본 리다이렉트 규칙
redirects = [
    "# 모바일",
    "/m/* /:splat 301",
    "/m / 301",
    "",
    "# entry 경로 -> posts로 리다이렉트"
]

count = 0
for filename in os.listdir(POSTS_DIR):
    if not filename.endswith('.md'):
        continue
    
    # 파일명에서 날짜와 슬러그 추출
    # 예: 2021-04-11-파리-바게트-몇시까지....md
    match = re.match(r'^(\d{4}-\d{2}-\d{2})-(.+)\.md$', filename)
    if not match:
        continue
    
    date = match.group(1)
    slug = match.group(2)
    
    # entry URL 생성 (날짜 제외)
    entry_path = f"/entry/{slug}*"
    posts_path = f"/posts/{date}-{slug}/ 301"
    
    redirects.append(f"{entry_path} {posts_path}")
    count += 1

# 파일 저장
with open(REDIRECTS_FILE, 'w', encoding='utf-8') as f:
    f.write('\n'.join(redirects))

print(f"✅ {count}개 entry 리다이렉트 생성 완료!")
print(f"📁 저장: {REDIRECTS_FILE}")
