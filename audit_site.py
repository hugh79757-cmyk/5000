import os
import re

# 설정
CONTENT_DIR = "content/posts"

def audit_hugo_site():
    print("🏥 Hugo 사이트 건전성 점검 시작...\n")
    
    total_files = 0
    draft_files = []
    hangul_filenames = []
    no_slug_hangul = []
    
    # content/posts 폴더 스캔
    if not os.path.exists(CONTENT_DIR):
        print(f"❌ 오류: '{CONTENT_DIR}' 폴더가 없습니다.")
        return

    for filename in os.listdir(CONTENT_DIR):
        if filename.endswith(".md") and filename != "_index.md":
            total_files += 1
            filepath = os.path.join(CONTENT_DIR, filename)
            
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
                # 1. Front Matter 파싱 (YAML 부분)
                front_matter = {}
                fm_match = re.match(r"^---\s+(.*?)\s+---", content, re.DOTALL)
                if fm_match:
                    fm_text = fm_match.group(1)
                    for line in fm_text.split("\n"):
                        if ":" in line:
                            key, val = line.split(":", 1)
                            front_matter[key.strip()] = val.strip().strip('"').strip("'")
                
                # 2. Draft(초안) 확인
                # draft가 'true'면 배포되지 않음
                if front_matter.get("draft") == "true":
                    draft_files.append(filename)

                # 3. 한글 파일명 체크
                # 파일명에 한글이 포함된 경우 URL 인코딩 문제가 생길 수 있음
                if re.search(r"[가-힣]", filename):
                    hangul_filenames.append(filename)
                    # Slug 설정이 없으면 위험
                    if "slug" not in front_matter:
                        no_slug_hangul.append(filename)

    # === 리포트 출력 ===
    print(f"📄 총 포스트 수: {total_files}개")
    
    print("\nWarning 1: [숨겨진 글] draft: true 설정됨 (배포 안 됨)")
    if draft_files:
        print(f"   👉 총 {len(draft_files)}개 발견")
        for f in draft_files[:5]: # 5개만 예시로 출력
            print(f"      - {f}")
        if len(draft_files) > 5: print(f"      ...외 {len(draft_files)-5}개")
    else:
        print("   ✅ 없음 (모두 배포 가능 상태)")

    print("\nWarning 2: [URL 위험] 한글 파일명인데 'slug' 설정 없음")
    print("   (맥/윈도우 차이로 404 원인이 될 수 있음)")
    if no_slug_hangul:
        print(f"   👉 총 {len(no_slug_hangul)}개 발견 (404 위험군)")
        for f in no_slug_hangul[:5]:
            print(f"      - {f}")
        if len(no_slug_hangul) > 5: print(f"      ...외 {len(no_slug_hangul)-5}개")
    else:
        print("   ✅ 없음 (안전함)")

    print("\n=== 점검 완료 ===")

if __name__ == "__main__":
    audit_hugo_site()
