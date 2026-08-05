#!/usr/bin/env python3
"""
오염된 글 전수조사 스크립트
hotissue-hugo 블로그의 모든 .md 파일을 스캔하여 오염 시그니처를 검출합니다.
"""

import os
import re
import glob
from datetime import datetime

def check_corruption_patterns(file_path):
    """파일의 오염 시그니처를 검사합니다."""
    patterns = {
        'llm_thinking_leak': r'사용자가 제공한 데이터|절대 .* 말라고 했습니다|초안:|이제 .* 작성|H2-\d|문장 수:|주의:|규칙|~해야 합니다\.$',
        'test_dummy': r'E2E Test|Test body|Test Title|Test body with image|## Heading \+ More content',
        'broken_title': r'title: [0-9]{4}-[0-9]{2}-[0-9]{2}-|title: rss-|title: ec[0-9a-f]{6}|title: eba[0-9a-f]|title: %',
        'abnormal_start': r'^[^#]*: ㅇㄴ|^[^#]*: ㅁㄴㅇ|^[^#]*: ㅇㅁㄴ',
        'product_mismatch': r'쿠팡|coupang'
    }
    
    corruption_types = []
    severity = '하'
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 제목 추출
            title_match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else 'NO_TITLE'
            
            # 본문 시작 부분 추출 (첫 번째 비주석 라인)
            lines = content.split('\n')
            body_start = None
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('title:') and not line.startswith('date:'):
                    body_start = line
                    break
            
            # 각 패턴 검사
            for pattern_name, pattern in patterns.items():
                if pattern_name == 'broken_title':
                    # title 프론트매터에서 검사
                    if re.search(pattern, f'title: {title}'):
                        corruption_types.append(pattern_name)
                        severity = '상' if severity == '하' else '중'
                elif pattern_name == 'llm_thinking_leak':
                    # 본문 상단에서 검사
                    if body_start and re.search(pattern, body_start[:200]):  # 본문 시작 200자 내 검사
                        corruption_types.append(pattern_name)
                        severity = '상' if severity == '하' else '중'
                elif pattern_name == 'test_dummy':
                    # 전체 본문에서 검사
                    if re.search(pattern, content):
                        corruption_types.append(pattern_name)
                        severity = '중' if severity == '하' else '상'
                elif pattern_name == 'abnormal_start':
                    # 본문 시작에서 검사
                    if body_start and re.search(pattern, body_start[:100]):
                        corruption_types.append(pattern_name)
                        severity = '중' if severity == '하' else '상'
                elif pattern_name == 'product_mismatch':
                    # 상품-주제 불일치 추가 검사
                    if '쿠팡' in content.lower() and not any(keyword in content.lower() for keyword in ['자동차', '차량', '운전', '엔진', '타이어', '세단', 'suv', '트럭']):
                        corruption_types.append(f"{pattern_name}_unrelated")
                        severity = '하'
                    elif '쿠팡' in content.lower():
                        corruption_types.append(pattern_name)
    
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None
    
    return {
        'file_path': file_path,
        'title': title,
        'corruption_types': corruption_types if corruption_types else None,
        'severity': severity if corruption_types else None
    }

def main():
    # hotissue-hugo content/posts 경로
    base_path = "/Users/twinssn/Projects/cap/hotissue-hugo/content/posts"
    
    # 모든 .md 파일 찾기
    md_files = glob.glob(os.path.join(base_path, "**/*.md"), recursive=True)
    
    print(f"총 {len(md_files)}개 파일 검사 중...")
    
    corrupted_files = []
    
    for file_path in md_files:
        result = check_corruption_patterns(file_path)
        if result and result['corruption_types']:
            corrupted_files.append(result)
    
    # 결과 출력
    print("\n" + "="*80)
    print("오염된 글 전수조사 결과")
    print("="*80)
    
    if not corrupted_files:
        print("오염된 글이 없습니다.")
        return
    
    # 심각도별 정렬
    corrupted_files.sort(key=lambda x: (x['severity'], x['file_path']))
    
    print(f"\n총 오염 파일 수: {len(corrupted_files)}")
    print(f"심각도分布: 상 {len([f for f in corrupted_files if f['severity'] == '상'])}개, 중 {len([f for f in corrupted_files if f['severity'] == '중'])}개, 하 {len([f for f in corrupted_files if f['severity'] == '하'])}개")
    
    print("\n" + "="*80)
    print("상세 결과")
    print("="*80)
    
    for i, file_info in enumerate(corrupted_files, 1):
        print(f"{i:3d}. {file_info['file_path']} | {file_info['corruption_types']} | {file_info['severity']}")
        if file_info['title'] != 'NO_TITLE':
            print(f"     제목: {file_info['title'][:50]}...")
    
    # CSV 형식으로 저장
    csv_path = "/Users/twinssn/Projects/5000/corrupted_posts_analysis.csv"
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write("file_path,corruption_types,severity,title\n")
        for file_info in corrupted_files:
            f.write(f"{file_info['file_path']},{','.join(file_info['corruption_types'])},{file_info['severity']},{file_info['title']}\n")
    
    print(f"\n상세 결과를 CSV 파일로 저장했습니다: {csv_path}")

if __name__ == "__main__":
    main()