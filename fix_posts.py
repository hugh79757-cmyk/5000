import os
import re
from pathlib import Path

CONTENT_DIR = "content/posts"

def fix_posts():
    print("🛠 모든 포스트에 slug 및 aliases 자동 추가 중...")
    count = 0
    
    content_path = Path(CONTENT_DIR)
    if not content_path.exists():
        print(f"❌ 오류: '{CONTENT_DIR}' 폴더가 없습니다.")
        return

    for filepath in sorted(content_path.glob("*.md")):
        if filepath.name == "_index.md":
            continue
        
        filename = filepath.stem  # 확장자 제외
        
        # 날짜-제목 패턴에서 slug 추출 (날짜 제거)
        match = re.match(r"\d{4}-\d{2}-\d{2}-(.+)", filename)
        if match:
            file_slug = match.group(1)
        else:
            file_slug = filename
        
        # 기존 URL (파일명 전체)
        old_path = f"/posts/{filename}/"
        
        content = filepath.read_text(encoding="utf-8")
        
        if not content.startswith("---"):
            continue
            
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
            
        front_matter = parts[1]
        body = parts[2]
        
        has_slug = "slug:" in front_matter
        has_aliases = "aliases:" in front_matter
        
        if has_slug and has_aliases:
            continue
        
        lines = front_matter.strip().split("\n")
        modified = False
        
        if not has_slug and file_slug:
            lines.append(f'slug: "{file_slug}"')
            modified = True
        
        if not has_aliases:
            lines.append(f'aliases: ["{old_path}"]')
            modified = True
        
        if modified:
            new_content = "---\n" + "\n".join(lines) + "\n---" + body
            filepath.write_text(new_content, encoding="utf-8")
            count += 1
            if count <= 10:
                print(f"✅ 수정됨: {filepath.name}")
            elif count == 11:
                print("... (계속 진행 중)")

    print(f"\n🎉 총 {count}개의 파일이 수정되었습니다.")
    print("👉 이제 git add . && git commit -m 'Add slug and aliases' && git push 하세요.")

if __name__ == "__main__":
    fix_posts()
