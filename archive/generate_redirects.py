import os
import re

# ==========================================
# 사용자 설정
# ==========================================
CONTENT_DIR = "content/posts"   # 포스트가 저장된 위치
OUTPUT_FILE = "static/_redirects" # 생성될 리다이렉트 파일
# ==========================================

def generate_redirects():
    redirects = []
    
    # static 폴더가 없으면 생성
    if not os.path.exists("static"):
        os.makedirs("static")

    # content/posts 경로 절대 경로로 확인
    base_dir = os.getcwd()
    abs_content_dir = os.path.join(base_dir, CONTENT_DIR)

    print(f"🔍 '{abs_content_dir}' 폴더를 스캔하여 리다이렉트 규칙을 생성합니다...")

    try:
        files = os.listdir(abs_content_dir)
    except FileNotFoundError:
        print(f"❌ 오류: '{CONTENT_DIR}' 폴더를 찾을 수 없습니다. 현재 위치가 Hugo 프로젝트 루트인지 확인해주세요.")
        return

    count = 0
    for filename in files:
        if filename.endswith(".md") and filename != "_index.md":
            
            # 패턴 매칭: "연도-월-일-나머지주소.md" 형태를 찾음 (예: 2026-01-15-my-post-title.md)
            # 패턴 매칭: "연도-월-일-순번-나머지주소.md" 형태도 고려 (예: 2026-01-15-001-my-post.md)
            
            # 1. 순번이 있는 경우 (2026-01-15-001-...)
            match_with_seq = re.match(r"(\d{4}-\d{2}-\d{2})-\d{3}-(.*)\.md", filename)
            
            # 2. 순번이 없는 경우 (2026-01-15-...)
            match_no_seq = re.match(r"(\d{4}-\d{2}-\d{2})-(.*)\.md", filename)
            
            date_part = ""
            slug_part = ""
            old_path_with_seq = "" # 순번 포함된 옛날 경로

            if match_with_seq:
                date_part = match_with_seq.group(1)
                slug_part = match_with_seq.group(2)
                # 순번까지 포함된 전체 파일명 베이스
                old_path_with_seq = f"/posts/{filename.replace('.md', '')}/"
                
            elif match_no_seq:
                date_part = match_no_seq.group(1)
                slug_part = match_no_seq.group(2)
                old_path_with_seq = f"/posts/{filename.replace('.md', '')}/"

            if date_part and slug_part:
                # [중요] 404가 발생하는 "옛날 주소" 패턴들
                # Case 1: 날짜 + 순번 + 제목 (파일명 그대로)
                redirects.append(f"{old_path_with_seq} /posts/{slug_part}/ 301")
                
                # Case 2: 날짜 + 제목 (순번 제외)
                redirects.append(f"/posts/{date_part}-{slug_part}/ /posts/{slug_part}/ 301")
                
                count += 1

    # 중복 제거
    redirects = list(set(redirects))

    # 파일 저장
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# Auto-generated redirects for Cloudflare Pages\n")
        f.write("# Old Path -> New Path 301\n")
        for rule in redirects:
            f.write(rule + "\n")
            
    print(f"✅ 완료! 총 {len(redirects)}개의 리다이렉트 규칙이 '{OUTPUT_FILE}'에 저장되었습니다.")
    print("👉 이제 다음 명령어로 배포하세요:")
    print("   hugo && git add . && git commit -m 'Fix 404 redirects' && git push")

if __name__ == "__main__":
    generate_redirects()
