import os
import re

POSTS_DIR = "/Users/twinssn/Desktop/rotcha-hugo/content/posts"
R2_BASE = "https://pub-f13899253b8f4ee58b588f86589bf042.r2.dev"

fixed = 0
for md_file in os.listdir(POSTS_DIR):
    if not md_file.endswith('.md'):
        continue
    
    filepath = os.path.join(POSTS_DIR, md_file)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 22_9_img.jpg -> 22_img.jpg (이중 번호 제거)
    content = re.sub(
        rf'({R2_BASE}/)(\d+)_\d+_(img[^")\s]*)',
        r'\1\2_\3',
        content
    )
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        fixed += 1

print(f"✅ {fixed}개 파일 수정 완료!")
