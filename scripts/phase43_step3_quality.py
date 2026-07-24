#!/usr/bin/env python3
"""
Phase 43 Step 3 - 4개 블로그 본문 품질 검증
4개 기준으로 채점: 데이터 활용, 환각 없음, 빈/0값 필드 미언급, 주제 적합성
"""

import sys
import os
import re

# Add project root to path
sys.path.insert(0, '/Users/twinssn/Projects/5000')

from pipelines.travel.fetcher import fetch_festival, fetch_heritage, fetch_food, fetch_course
from pipelines.travel.writer import generate_content

def analyze_quality(blog_id, data, body_md, title):
    """Analyze content quality based on 4 criteria"""
    
    print(f"\n=== {blog_id} 품질 분석 ===")
    print(f"제목: {title}")
    print(f"본문 길이: {len(body_md)}자")
    
    results = {}
    
    # Criteria 1: 데이터 활용 (주소/전화/URL/시설 등 제공 데이터 실제 사용)
    print("\n1. 데이터 활용 검증:")
    data_usage_score = 0
    
    # Extract place names from data
    place_names = []
    if 'items' in data:
        for item in data['items']:
            name = item.get('title', item.get('facltNm', ''))
            if name:
                place_names.append(name)
    
    print(f"   제공 데이터 장소: {len(place_names)}개")
    for place in place_names:
        if place in body_md:
            data_usage_score += 1
            print(f"   ✅ {place}: 본문에 사용됨")
        else:
            print(f"   ❌ {place}: 본문에 미사용")
    
    criteria1_pass = data_usage_score >= len(place_names) * 0.7  # 70% 이상 사용
    results['data_usage'] = {
        'score': data_usage_score,
        'total': len(place_names),
        'pass': criteria1_pass,
        'details': f"{data_usage_score}/{len(place_names)} 장소 사용"
    }
    
    # Criteria 2: 환각 없음 (데이터에 없는 예약처·수치·사실 지어내지 않음)
    print(f"\n2. 환각 검증:")
    hallucination_score = 0
    hallucination_checks = [
        ('예약처', ['네이버 예약', '카카오 예약', '공식 홈페이지 예약']),
        ('수치', ['만원대', '천원대', '오만원대']),  # 가격 정보가 구체적이면 환각
        ('사실', ['세계 최초', '한국 최대', '전국 유일'])  # 과장된 주장
    ]
    
    for check_type, patterns in hallucination_checks:
        violations = []
        for pattern in patterns:
            if pattern in body_md:
                violations.append(pattern)
        
        if violations:
            print(f"   ❌ {check_type}: {violations} - 환각 의심")
        else:
            print(f"   ✅ {check_type}: 환각 없음")
            hallucination_score += 1
    
    criteria2_pass = hallucination_score == len(hallucination_checks)
    results['no_hallucination'] = {
        'score': hallucination_score,
        'total': len(hallucination_checks),
        'pass': criteria2_pass,
        'details': f"{hallucination_score}/{len(hallucination_checks)} 항목 통과"
    }
    
    # Criteria 3: 빈/0값 필드 미언급 (값이 0이거나 빈 필드 언급하지 않음)
    print(f"\n3. 빈 필드 미언급 검증:")
    empty_field_score = 0
    empty_patterns = [
        r'가격:.*?무료',
        r'가격:.*?0원',
        r'전화번호:.*?없음',
        r'운영시간:.*?없음',
        r'휴무일:.*?없음'
    ]
    
    field_violations = []
    for pattern in empty_patterns:
        if re.search(pattern, body_md):
            field_violations.append(pattern)
    
    if field_violations:
        print(f"   ❌ 빈 필드 언급: {field_violations}")
    else:
        print(f"   ✅ 빈 필드 언급 없음")
        empty_field_score = 1
    
    criteria3_pass = empty_field_score == 1
    results['no_empty_fields'] = {
        'score': empty_field_score,
        'total': 1,
        'pass': criteria3_pass,
        'details': "빈 필드 언급 없음" if criteria3_pass else "빈 필드 언급 발견"
    }
    
    # Criteria 4: 주제 적합성 (각 주제 특성에 맞고 타 주제 혼입이 없는가)
    print(f"\n4. 주제 적합성 검증:")
    topic_keywords = {
        'travel1-hugo': ['축제', '행사', '문화축제', '축제장', '공연'],
        'travel2-hugo': ['문화유산', '역사', '유적', '국보', '문화재', '전통'],
        'travel3-hugo': ['맛집', '음식점', '메뉴', '맛', '식당', '요리'],
        'travel4-hugo': ['여행코스', '경로', '루트', '코스', '여행지', '추천코스']
    }
    
    blog_topic = topic_keywords.get(blog_id, [])
    off_topic_patterns = [
        ('travel1-hugo', ['맛집', '음식', '식당']),  # 축제 블로그에 맛집 언급
        ('travel2-hugo', ['축제', '행사', '공연']),  # 문화유산 블로그에 축제 언급
        ('travel3-hugo', ['축제', '행사', '유적']),  # 맛집 블로그에 축제/유적 언급
        ('travel4-hugo', ['맛집', '음식점', '메뉴'])  # 코스 블로그에 맛집 언급
    ]
    
    topic_violations = []
    for check_blog, off_topics in off_topic_patterns:
        if check_blog == blog_id:
            for off_topic in off_topics:
                if off_topic in body_md:
                    topic_violations.append(off_topic)
    
    if topic_violations:
        print(f"   ❌ 주제 혼입: {topic_violations}")
    else:
        print(f"   ✅ 주제 일관성: {blog_topic[0] if blog_topic else '일반'} 주제로 일관됨")
        empty_field_score += 1  # Additional score for topic consistency
    
    criteria4_pass = len(topic_violations) == 0
    results['topic_relevance'] = {
        'score': 1 if criteria4_pass else 0,
        'total': 1,
        'pass': criteria4_pass,
        'details': "주제 일관성 유지" if criteria4_pass else f"주제 혼입: {topic_violations}"
    }
    
    # Overall pass/fail
    total_criteria = 4
    pass_criteria = sum(1 for r in results.values() if r['pass'])
    overall_pass = pass_criteria == total_criteria
    
    results['overall'] = {
        'pass': overall_pass,
        'pass_count': pass_criteria,
        'total_count': total_criteria,
        'score': f"{pass_criteria}/{total_criteria}"
    }
    
    print(f"\n종합 결과:")
    print(f"   통과 항목: {pass_criteria}/{total_criteria}")
    print(f"   전체 평가: {'✅ PASS' if overall_pass else '❌ FAIL'}")
    
    return results

def main():
    """Main quality verification for all 4 blogs"""
    
    blog_configs = [
        ('travel1-hugo', fetch_festival, '축제 블로그'),
        ('travel2-hugo', fetch_heritage, '문화유산 블로그'),
        ('travel3-hugo', fetch_food, '맛집 블로그'),
        ('travel4-hugo', fetch_course, '여행코스 블로그')
    ]
    
    all_results = {}
    
    for blog_id, fetch_func, blog_name in blog_configs:
        print(f"\n{'='*60}")
        print(f"🔍 {blog_name} 품질 검증")
        print(f"{'='*60}")
        
        try:
            # Fetch data
            data = fetch_func()
            if not data:
                print(f"❌ 데이터 수집 실패 - SKIP")
                all_results[blog_id] = {'error': 'Data fetch failed'}
                continue
            
            # Generate content
            result = generate_content(data, blog_id=blog_id)
            if not result:
                print(f"❌ 콘텐츠 생성 실패 - SKIP")
                all_results[blog_id] = {'error': 'Content generation failed'}
                continue
            
            body_md = result.get('body_md', '')
            title = result.get('title', '')
            
            # Analyze quality
            quality_results = analyze_quality(blog_id, data, body_md, title)
            all_results[blog_id] = quality_results
            
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)} - SKIP")
            all_results[blog_id] = {'error': str(e)}
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"📊 PHASE 43 STEP 3 최종 요약")
    print(f"{'='*60}")
    
    for blog_id, results in all_results.items():
        if 'error' in results:
            print(f"❌ {blog_id}: 오류 - {results['error']}")
        else:
            overall = results['overall']
            pass_fail = "✅ PASS" if overall['pass'] else "❌ FAIL"
            print(f"{pass_fail} {blog_id}: {overall['score']} ({len(body_md)}자)")
            
            # Show details for failed criteria
            if not overall['pass']:
                print("   실패 항목:")
                for criterion, result in results.items():
                    if criterion != 'overall' and not result['pass']:
                        print(f"     ❌ {criterion}: {result['details']}")
    
    return all_results

if __name__ == "__main__":
    main()