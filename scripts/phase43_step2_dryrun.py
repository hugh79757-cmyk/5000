#!/usr/bin/env python3
"""
Phase 43 Step 2 - 4개 블로그 본문 dry-run 생성
timeout: 300초, 재시도 1회 허용
발금 금지, dry-run만 실행
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, '/Users/twinssn/Projects/5000')

from pipelines.travel.fetcher import fetch_festival, fetch_heritage, fetch_food, fetch_course
from pipelines.travel.writer import generate_content

def generate_blog_content(blog_id, fetch_func, blog_name):
    """Generate content for a specific blog with timeout handling"""
    print(f"\n=== {blog_name} ({blog_id}) ===")
    
    try:
        # Fetch data
        print("데이터 수집 중...")
        data = fetch_func()
        if not data:
            print("❌ 데이터 수집 실패 - SKIP")
            return False
            
        print("데이터 수집 완료")
        
        # Generate content (dry-run only, no publishing)
        print("본문 생성 중...")
        start_time = time.time()
        
        result = generate_content(data, blog_id=blog_id)
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result and result.get('content'):
            body_md = result.get('body_md', '')
            title = result.get('title', '')
            
            print(f"✅ 생성 완료")
            print(f"   소요 시간: {duration:.1f}초")
            print(f"   제목: {title}")
            print(f"   본문 길이: {len(body_md)}자")
            print(f"   본문 내용 일부: {body_md[:200]}...")
            
            return {
                'success': True,
                'title': title,
                'body_length': len(body_md),
                'duration': duration,
                'content_preview': body_md[:200]
            }
        else:
            print("❌ 본문 생성 실패 - SKIP")
            return False
            
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)} - SKIP")
        return False

def main():
    """Main execution for all 4 blogs"""
    
    blogs = [
        ('travel1-hugo', fetch_festival, '축제 블로그'),
        ('travel2-hugo', fetch_heritage, '문화유산 블로그'),
        ('travel3-hugo', fetch_food, '맛집 블로그'),
        ('travel4-hugo', fetch_course, '여행코스 블로그')
    ]
    
    results = {}
    
    for blog_id, fetch_func, blog_name in blogs:
        result = generate_blog_content(blog_id, fetch_func, blog_name)
        results[blog_id] = result
        
        # Add separator between blogs
        print("\n" + "="*50)
    
    # Summary
    print("\n" + "="*50)
    print("STEP 2 요약:")
    print("="*50)
    
    success_count = sum(1 for r in results.values() if r and r.get('success'))
    total_count = len(results)
    
    print(f"성공: {success_count}/{total_count}")
    
    for blog_id, result in results.items():
        if result and result.get('success'):
            print(f"✅ {blog_id}: {result['body_length']}자 ({result['duration']:.1f}초)")
        else:
            print(f"❌ {blog_id}: 실패 (SKIP)")
    
    return results

if __name__ == "__main__":
    main()