import os
import re

BACKUP_DIR = "/Users/twinssn/Desktop/rotcha-hugo/rankingoneto-1-1"
POSTS_DIR = "/Users/twinssn/Desktop/rotcha-hugo/content/posts"
R2_BASE = "https://pub-f13899253b8f4ee58b588f86589bf042.r2.dev"

# 폴더번호 -> 마크다운 파일 매핑 생성
folder_to_md = {}
for folder in os.listdir(BACKUP_DIR):
    folder_path = os.path.join(BACKUP_DIR, folder)
    if not os.path.isdir(folder_path):
        continue
    
    # HTML 파일에서 제목 추출
    for f in os.listdir(folder_path):
        if f.endswith('.html'):
            # 파일명에서 제목 추출 (번호- 제거)
            title_part = re.sub(r'^\d+-', '', f).replace('.html', '')
            folder_to_md[folder] = title_part
            break

updated = 0
for md_file in os.listdir(POSTS_DIR):
    if not md_file.endswith('.md'):
        continue
    
    filepath = os.path.join(POSTS_DIR, md_file)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 각 폴더에 대해 이미지 경로 수정
    for folder, title in folder_to_md.items():
        # 마크다운 파일명에 제목이 포함되어 있는지 확인
        if title[:10] in md_file:  # 제목 앞 10자로 매칭
            # img.jpg -> 폴더번호_img.jpg
            content = re.sub(
                rf'{R2_BASE}/(img[^")]*\.(jpg|jpeg|png|webp|gif))',
                rf'{R2_BASE}/{folder}_\1',
                content,
                flags=re.IGNORECASE
            )
            break
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        updated += 1

print(f"✅ {updated}개 마크다운 파일 수정 완료!")
