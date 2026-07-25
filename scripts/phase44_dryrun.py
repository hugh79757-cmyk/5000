#!/usr/bin/env python3
"""
Phase 44 Dry-run — 6개 블로그 신규 발행 품질 검증
Phase 40~43 개선사항이 적용된 새 콘텐츠가 품질 기준 100% 통과하는지 확인

Usage:
    python3 scripts/phase44_dryrun.py
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, '/Users/twinssn/Projects/5000')

from pipelines.travel.fetcher import (
    fetch_camping, fetch_festival, fetch_heritage, fetch_food, fetch_course
)
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
        
        if result and result.get('body_md'):
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
                'content_preview': body_md[:200],
                'body_md': body_md,
                'title': title,
            }
        else:
            print("❌ 본문 생성 실패 - SKIP")
            return False
            
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)} - SKIP")
        return False


def verify_quality(blog_id, result):
    """Verify generated content against Phase 40-43 quality criteria"""
    if not result or not result.get('success'):
        return False, ['본문 생성 실패']
    
    body = result.get('body_md', '')
    title = result.get('title', '')
    errors = []
    
    # 1. 본문 길이 ≥ 2500자
    if len(body) < 2500:
        errors.append(f'본문 길이 미달: {len(body)} < 2500')
    
    # 2. 타이틀 존재
    if not title:
        errors.append('타이틀 없음')
    
    # 3. 금지어 검사 (공통 + 블로그별)
    # 공통 금지어
    forbidden_common = [
        "추천드립니다", "인기가 많습니다", "맛있는", "좋은", "훌륭한", "최고의"
    ]
    
    # 블로그별 추가 금지어
    forbidden_by_blog = {
        'travel-hugo': [],  # 캠핑은 공통만
        'travel1-hugo': ["방문객", "주차장", "주차장보유", "주차가능"],
        'travel2-hugo': [],  # 문화유산은 공통만
        'travel3-hugo': [
            "강추", "강력추천", "무조건", "필수코스", "인생맛집", "찐맛집",
            "대박", "진심", "진짜", "완전", "진짜로", "절대", "무조건가야함",
            "후회없음", "인생메뉴", "찐", "갓성비", "혜자", "가성비끝판왕",
            "가성비최고", "줄서서먹는", "웨이팅", "대기필수", "예약필수", "품절대란"
        ],
        'travel4-hugo': [],  # 코스는 공통만
    }
    
    all_forbidden = set(forbidden_common)
    if blog_id in forbidden_by_blog:
        all_forbidden.update(forbidden_by_blog[blog_id])
    
    found_forbidden = [w for w in all_forbidden if w in body]
    if found_forbidden:
        errors.append(f'금지어 발견: {found_forbidden}')
    
    # 4. 이동시간 패턴 검사 (코스 블로그만)
    if blog_id == 'travel4-hugo':
        movement_patterns = [
            r"도보\s*\d+",
            r"차로\s*\d+",
            r"걸어\s*\d+",
            r"\d+\s*분\s*(걸어|걸리|소요)",
            r"\d+\s*시간\s*(걸어|걸리|소요)",
            r"\b\d+\s*분\b",
            r"\b\d+\s*시간\b",
        ]
        violations = []
        for pattern in movement_patterns:
            if __import__('re').search(pattern, body, __import__('re').IGNORECASE):
                violations.append(pattern)
        if violations:
            errors.append(f'이동시간 패턴 위반: {violations[:3]}')
    
    # 5. 가격 포맷 검사 (맛집 블로그만)
    if blog_id == 'travel3-hugo':
        price_violations = []
        for pattern in ["~만원대", "만원대", "만 원대"]:
            if pattern in body:
                price_violations.append(pattern)
        if price_violations:
            errors.append(f'가격 포맷 위반: {price_violations}')
    
    # 6. 필수 키워드 검사 (캠핑 블로그만)
    if blog_id == 'travel-hugo':
        required_keywords = ["텐트", "타프", "침낭", "랜턴", "버너", "코펠"]
        found = [kw for kw in required_keywords if kw in body]
        if len(found) < 3:
            errors.append(f'캠핑 필수 키워드 부족: {len(found)}/3 (발견: {found})')
        
        # 브랜드 키워드
        brand_keywords = ["스노우피크", "콜맨", "코베아", "블랙야크", "노스페이스"]
        found_brands = [kw for kw in brand_keywords if kw in body]
        if len(found_brands) < 1:
            errors.append(f'브랜드 키워드 부족: 0/1')
    
    # 7. 축제 블로그 필수 요소
    if blog_id == 'travel1-hugo':
        required_elements = ["운영시간", "위치", "기간"]
        missing = [e for e in required_elements if e not in body]
        if missing:
            errors.append(f'축제 필수 요소 누락: {missing}')
    
    # 8. 문화유산 컨텍스트 단어
    if blog_id == 'travel2-hugo':
        context_words = ["시대", "종목", "양식", "비교", "대조", "공통", "반면"]
        found = [w for w in context_words if w in body]
        if len(found) < 2:
            errors.append(f'문화유산 컨텍스트 단어 부족: {len(found)}/2')
    
    # 9. 코스명 패턴 (코스 블로그)
    if blog_id == 'travel4-hugo':
        import re
        h3_sections = [h.strip() for h in body.split('###') if h.strip() and len(h.strip()) > 10]
        course_sections = [h for h in h3_sections if re.match(r'^\d+[코스일차][:：]\s*.+', h.split('\n')[0])]
        if len(course_sections) < 3:
            errors.append(f'코스 섹션 부족: {len(course_sections)}/3 (패턴: N코스: xxx)')
    
    return len(errors) == 0, errors


def main():
    """Main execution for all 6 blogs"""
    
    blogs = [
        ('travel-hugo', fetch_camping, '캠핑 블로그'),
        ('travel1-hugo', fetch_festival, '축제 블로그'),
        ('travel2-hugo', fetch_heritage, '문화유산 블로그'),
        ('travel3-hugo', fetch_food, '맛집 블로그'),
        ('travel4-hugo', fetch_course, '여행코스 블로그'),
        # blogger1은 Blogger 플랫폼이라 별도 처리 필요 - skip for now
    ]
    
    results = {}
    quality_results = {}
    
    for blog_id, fetch_func, blog_name in blogs:
        result = generate_blog_content(blog_id, fetch_func, blog_name)
        results[blog_id] = result
        
        # 품질 검증
        if result and result.get('success'):
            passed, errors = verify_quality(blog_id, result)
            quality_results[blog_id] = {'passed': passed, 'errors': errors}
            if passed:
                print(f"🟢 품질 검증: PASS")
            else:
                print(f"🔴 품질 검증: FAIL")
                for err in errors:
                    print(f"   - {err}")
        else:
            quality_results[blog_id] = {'passed': False, 'errors': ['본문 생성 실패']}
        
        # Add separator between blogs
        print("\n" + "="*50)
    
    # Summary
    print("\n" + "="*50)
    print("Phase 44 Dry-run 요약:")
    print("="*50)
    
    success_count = sum(1 for r in results.values() if r and r.get('success'))
    total_count = len(results)
    
    quality_pass = sum(1 for q in quality_results.values() if q['passed'])
    quality_total = len(quality_results)
    
    print(f"본문 생성: {success_count}/{total_count}")
    print(f"품질 검증: {quality_pass}/{quality_total}")
    
    for blog_id in results:
        r = results[blog_id]
        q = quality_results[blog_id]
        if r and r.get('success'):
            status = "✅" if q['passed'] else "❌"
            print(f"  {status} {blog_id}: {r['body_length']}자 ({r['duration']:.1f}초) - 품질: {'PASS' if q['passed'] else 'FAIL'}")
            if not q['passed']:
                for err in q['errors']:
                    print(f"      - {err}")
        else:
            print(f"  ❌ {blog_id}: 생성 실패")
    
    # Overall result
    overall = quality_pass == quality_total
    print(f"\n{'='*50}")
    if overall:
        print("🎉 Phase 44 Dry-run: 전체 PASS (100% 품질 기준 통과)")
    else:
        print(f"⚠️  Phase 44 Dry-run: {quality_pass}/{quality_total} PASS - 품질 기준 미달")
    print(f"{'='*50}")
    
    return overall


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)