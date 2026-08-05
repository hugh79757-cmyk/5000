#!/usr/bin/env python3
"""
오염된 글 draft 전환 스크립트
LLM 사고과정 누수가 검출된 7개 파일을 draft: true로 전환합니다.
"""

import os
import re

def add_draft_to_file(file_path):
    """파일의 프론트매터에 draft: true를 추가합니다."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # draft 속성 찾기 및 수정
        draft_found = False
        for i, line in enumerate(lines):
            if line.strip() == 'draft: false':
                lines[i] = 'draft: true\n'
                draft_found = True
                break
            elif line.strip().startswith('draft:'):
                # 기존 draft 속성이 있으면 값만 변경
                lines[i] = 'draft: true\n'
                draft_found = True
                break
        
        # draft 속성이 없으면 프론트매터 끝에 추가
        if not draft_found:
            # frontmatter 끝 찾기 (---)
            frontmatter_end = -1
            for i, line in enumerate(lines):
                if line.strip() == '---' and i > 0:
                    frontmatter_end = i
                    break
            
            if frontmatter_end > 0:
                lines.insert(frontmatter_end, 'draft: true\n')
                print(f"Added draft: true to {file_path}")
            else:
                print(f"Warning: No frontmatter found in {file_path}")
                return False
        
        # 파일에 쓰기
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        return True
    
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    # 오염된 파일 목록
    corrupted_files = [
        "/Users/twinssn/Projects/cap/hotissue-hugo/content/posts/2026-08-01-k9-감가-3474만원의-현실-3년-보유-후-중고-매각-시-실제-손실-계산.md",
        "/Users/twinssn/Projects/cap/hotissue-hugo/content/posts/2026-08-02-신차-17410만원-m5-3년-뒤-중고값-8949만원-잔존가치-51의-의미.md",
        "/Users/twinssn/Projects/cap/hotissue-hugo/content/posts/2026-08-02-k9-54-vs-8시리즈-53-잔존가치-1p-차이가-실제-얼마인지-계산해봤다.md",
        "/Users/twinssn/Projects/cap/hotissue-hugo/content/posts/2025-05-05-ecb998eba7a4-ec9888ebb0a9-ec839ded999cec8ab5eab480.md",
        "/Users/twinssn/Projects/cap/hotissue-hugo/content/posts/2025-05-04-ec97acec8ba0eab1b0eb9e98-ec9588ec8bacecb0a8eb8ba8-.md",
        "/Users/twinssn/Projects/cap/hotissue-hugo/content/posts/2026-07-16-g70-슈팅-브레이크-3년-총비용-3115만원-vs-c클래스-4525만원-매달-내는-돈으로-환산하면.md",
        "/Users/twinssn/Projects/cap/hotissue-hugo/content/posts/2026-08-01-i5-감가-5385만원-vs-m5-8098만원-어느-쪽이-더-빠지나.md"
    ]
    
    print(f"총 {len(corrupted_files)}개 파일을 draft: true로 전환합니다...")
    
    success_count = 0
    for file_path in corrupted_files:
        if os.path.exists(file_path):
            if add_draft_to_file(file_path):
                success_count += 1
                print(f"✅ {os.path.basename(file_path)}")
            else:
                print(f"❌ {os.path.basename(file_path)}")
        else:
            print(f"⚠️  파일不存在: {file_path}")
    
    print(f"\n=== 결과 요약 ===")
    print(f"성공: {success_count}/{len(corrupted_files)} 파일")
    print(f"실패: {len(corrupted_files) - success_count}/{len(corrupted_files)} 파일")
    
    if success_count == len(corrupted_files):
        print("✅ 모든 오염 파일의 draft 전환이 완료되었습니다.")
        print("Hugo 빌드 시 해당 글은 제외됩니다.")
    else:
        print("⚠️  일부 파일 처리에 실패했습니다. 수동 확인이 필요합니다.")

if __name__ == "__main__":
    main()