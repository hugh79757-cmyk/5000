import os
import shutil
import re

BACKUP_DIR = "/Users/twinssn/Desktop/rotcha-hugo/rankingoneto-1-1"
POSTS_DIR = "/Users/twinssn/Desktop/rotcha-hugo/content/posts"
OUTPUT_DIR = "/Users/twinssn/Desktop/rotcha-hugo/static/images/renamed"
R2_BASE = "https://pub-f13899253b8f4ee58b588f86589bf042.r2.dev"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 이미지 복사 및 이름 변경
renamed_count = 0
md_updated = 0

for folder in os.listdir(BACKUP_DIR):
    folder_path = os.path.join(BACKUP_DIR, folder)
    if not os.path.isdir(folder_path):
        continue
    
    img_dir = os.path.join(folder_path, "img")
    if not os.path.exists(img_dir):
        continue
    
    for img_file in os.listdir(img_dir):
        if not img_file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
            continue
        
        # 새 파일명: 폴더번호_원본파일명
        new_name = f"{folder}_{img_file}"
        src = os.path.join(img_dir, img_file)
        dst = os.path.join(OUTPUT_DIR, new_name)
        
        shutil.copy2(src, dst)
        renamed_count += 1

print(f"✅ {renamed_count}개 이미지 복사 완료!")
print(f"📁 저장 위치: {OUTPUT_DIR}")
print(f"\n다음 단계:")
print(f"1. {OUTPUT_DIR} 폴더를 R2에 업로드")
print(f"2. 마크다운 파일에서 이미지 경로 수정")
