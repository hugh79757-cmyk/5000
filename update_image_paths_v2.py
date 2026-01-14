import os
import re

BACKUP_DIR = "/Users/twinssn/Desktop/rotcha-hugo/rankingoneto-1-1"
POSTS_DIR = "/Users/twinssn/Desktop/rotcha-hugo/content/posts"
R2_BASE = "https://pub-f13899253b8f4ee58b588f86589bf042.r2.dev"

# 숫자 aliases로 폴더번호 매핑
updated = 0
for md_file in os.listdir(POSTS_DIR):
    if not md_file.endswith('.md'):
        continue
    
    filepath = os.path.join(POSTS_DIR, md_file)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # aliases에서 숫자 찾기 (예: /22/, /83/)
    match = re.search(r'aliases:.*?- /(\d+)/', content, re.DOTALL)
    if not match:
        continue
    
    folder_num = match.group(1)
    original = content
    
    # r2.dev/img 로 시작하는 이미지를 폴더번호_img 로 변경
    content = re.sub(
        rf'({R2_BASE}/)([^/\s")\]]+\.(jpg|jpeg|png|webp|gif))',
        rf'\g<1>{folder_num}_\2',
        content,
        flags=re.IGNORECASE
    )
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        updated += 1
        if updated <= 5:
            print(f"수정: {md_file} (폴더 {folder_num})")

print(f"\n✅ {updated}개 마크다운 파일 수정 완료!")
