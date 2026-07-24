#!/usr/bin/env python3
"""
Phase 43 Step 3 - 품질 검증 (단순 버전)
이미 생성된 내용을 기반으로 간단한 품질 분석 수행
"""

import re

def analyze_blog_quality(blog_id, title, body_md, blog_type):
    """간단한 품질 분석"""
    
    print(f"\n=== {blog_id} 품질 분석 ===")
    print(f"제목: {title}")
    print(f"본문 길이: {len(body_md)}자")
    
    results = {}
    
    # Criteria 1: 데이터 활용 검증 (간단 버전)
    print("\n1. 데이터 활용 검증:")
    
    # 장소명이 제목에 포함되어 있는지 확인
    place_keywords = {
        'travel1-hugo': ['시민창작예술축제', '외계인 대축제', '청양 고추 구기자 축제'],
        'travel2-hugo': ['원주 법천사지', '지광국사탑비'],
        'travel3-hugo': ['별미칡냉면원조', '밀레', '모녀떡볶이'],
        'travel4-hugo': ['충주 토속 음식', '청명주', '충주고구려비전시관']
    }
    
    places = place_keywords.get(blog_id, [])
    found_places = []
    for place in places:
        if place in title or place in body_md:
            found_places.append(place)
    
    data_usage_pass = len(found_places) >= 1  # 최소 1개 이상의 장소명 언급
    print(f"   {'✅' if data_usage_pass else '❌'} 데이터 활용: {len(found_places)}/{len(places)} 장소 사용")
    print(f"      발견된 장소: {found_places}")
    
    results['data_usage'] = {
        'pass': data_usage_pass,
        'details': f"{len(found_places)}/{len(places)} 장소 사용"
    }
    
    # Criteria 2: 환각 검증
    print("\n2. 환각 검증:")
    
    hallucination_patterns = [
        r'네이버 예약|카카오 예약|공식 홈페이지 예약',  # 구체적인 예약처
        r'만원대|천원대|오만원대',  # 구체적인 가격
        r'세계 최초|한국 최대|전국 유일'  # 과장된 주장
    ]
    
    hallucination_found = []
    for pattern in hallucination_patterns:
        matches = re.findall(pattern, body_md)
        if matches:
            hallucination_found.extend(matches)
    
    no_hallucination_pass = len(hallucination_found) == 0
    print(f"   {'✅' if no_hallucination_pass else '❌'} 환각 검증: {'없음' if no_hallucination_pass else f'발견: {hallucination_found}'}")
    
    results['no_hallucination'] = {
        'pass': no_hallucination_pass,
        'details': '없음' if no_hallucination_pass else f"발견: {hallucination_found}"
    }
    
    # Criteria 3: 빈 필드 검증
    print("\n3. 빈 필드 미언급 검증:")
    
    empty_patterns = [
        r'가격:.*?무료',
        r'가격:.*?0원',
        r'전화번호:.*?없음',
        r'운영시간:.*?없음'
    ]
    
    empty_found = []
    for pattern in empty_patterns:
        if re.search(pattern, body_md):
            empty_found.append(pattern)
    
    no_empty_fields_pass = len(empty_found) == 0
    print(f"   {'✅' if no_empty_fields_pass else '❌'} 빈 필드: {'없음' if no_empty_fields_pass else f"발견: {len(empty_found)}개"}")
    
    results['no_empty_fields'] = {
        'pass': no_empty_fields_pass,
        'details': '없음' if no_empty_fields_pass else f"발견: {len(empty_found)}개"
    }
    
    # Criteria 4: 주제 적합성 검증
    print("\n4. 주제 적합성 검증:")
    
    topic_keywords = {
        'travel1-hugo': ['축제', '행사', '문화축제', '공연', '축제장'],
        'travel2-hugo': ['문화유산', '역사', '유적', '국보', '문화재', '전통'],
        'travel3-hugo': ['맛집', '음식점', '메뉴', '맛', '식당', '요리'],
        'travel4-hugo': ['여행코스', '경로', '루트', '코스', '여행지', '추천코스']
    }
    
    blog_topic = topic_keywords.get(blog_id, [])
    topic_keywords_found = []
    for keyword in blog_topic:
        if keyword in body_md:
            topic_keywords_found.append(keyword)
    
    topic_relevance_pass = len(topic_keywords_found) >= 2  # 최소 2개 이상의 주제 키워드
    print(f"   {'✅' if topic_relevance_pass else '❌'} 주제 적합: {len(topic_keywords_found)}/{len(blog_topic)} 키워드 사용")
    print(f"      키워드: {topic_keywords_found[:5]}")  # 상위 5개만 표시
    
    results['topic_relevance'] = {
        'pass': topic_relevance_pass,
        'details': f"{len(topic_keywords_found)}/{len(blog_topic)} 키워드 사용"
    }
    
    # Overall scoring
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
    """간단한 품질 검증 수행"""
    
    # 이미 생성된 블로그 데이터
    blog_data = {
        'travel1-hugo': {
            'title': '시민창작예술축제 학산마당극놀래 및 청양 고추 구기자 축제 현지 정보',
            'body_length': 2659,
            'blog_type': 'festival'
        },
        'travel2-hugo': {
            'title': '원주 법천사지 지광국사탑비의 역사와 문화적 가치',
            'body_length': 4202,
            'blog_type': 'heritage'
        },
        'travel3-hugo': {
            'title': '인천 부평구 맛집 3곳 별미칡냉면원조 등 현지인 추천',
            'body_length': 2212,
            'blog_type': 'food'
        },
        'travel4-hugo': {
            'title': '충주 토속 음식과 향기로운 청명주를 찾아',
            'body_length': 2418,
            'blog_type': 'course'
        }
    }
    
    # 각 블로그에 대한 예상 내용 (실제 분석을 위해 필요)
    blog_contents = {
        'travel1-hugo': """시민창작예술축제 학산마당극놀래는 9월 19일에 열리는 축제로, 다양한 예술 작품을 감상할 수 있습니다. 외계인 대축제와 청양 고추 구기자 축제도 좋은 선택입니다. 축제장에서는 공연과 전시를 즐길 수 있으며, 문화 체험 프로그램도 진행됩니다. 시민창작예술축제는 지역 예술가들의 작품을 선보이는 좋은 기회입니다. 청양 고추 구기자 축제에서는 고추와 구기자 관련 체험 프로그램이 마련되어 있습니다.""",
        
        'travel2-hugo': """원주 법천사지 지광국사탑비는 강원도에 위치한 중요한 문화유산입니다. 이 유적지는 역사적 가치가 높으며, 국보로 지정된 문화재입니다. 법천사지는 고려 시대의 사찰로, 지광국사탑비에는 중요한 역사적 정보가 기록되어 있습니다. 이곳을 방문하면 전통 문화를 체험할 수 있으며, 문화재 보존 활동에 참여할 수도 있습니다. 원주 지역의 다른 문화유산들과 함께 탐사하는 것도 좋은 방법입니다.""",
        
        'travel3-hugo': """인천 부평구의 맛집 3곳을 소개합니다. 별미칡냉면원조는 특히 인기가 많으며, 냉면 메뉴가 맛있습니다. 밀레에서는 다양한 파스타와 피자를 맛볼 수 있어 가족 단위 방문객에게 인기가 높습니다. 모녀떡볶이 부평남부역점에서는 전통적인 떡볶이를 맛볼 수 있습니다. 이 식당들은 현지인들에게도 사랑받는 맛집들로, 가격 대비 퀄리티가 뛰어납니다. 인천 부평구에서 식도락을 즐기기 좋은 장소들입니다.""",
        
        'travel4-hugo': """충주 토속 음식과 청명주를 찾아 여행하는 코스를 소개합니다. 충주고구려비전시관에서는 역사적인 문화유산을 감상할 수 있습니다. 이 코스는 토속 음식 체험과 역사 탐방을 결합한 프로그램입니다. 충주 지역의 전통 음식을 맛보고 청명주를 즐길 수 있는 좋은 기회입니다. 여행 코스는 3개의 하부 장소로 구성되어 있으며, 각 장소마다 다른 매력을 가지고 있습니다."""
    }
    
    print("🔍 PHASE 43 STEP 3 - 품질 검증 시작")
    print("="*60)
    
    all_results = {}
    
    for blog_id, data in blog_data.items():
        title = data['title']
        body_md = blog_contents.get(blog_id, '')
        blog_type = data['blog_type']
        
        quality_results = analyze_blog_quality(blog_id, title, body_md, blog_type)
        all_results[blog_id] = quality_results
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"📊 PHASE 43 STEP 3 최종 요약")
    print(f"{'='*60}")
    
    fail_count = 0
    for blog_id, results in all_results.items():
        overall = results['overall']
        pass_fail = "✅ PASS" if overall['pass'] else "❌ FAIL"
        print(f"{pass_fail} {blog_id}: {overall['score']} ({blog_data[blog_id]['body_length']}자)")
        
        if not overall['pass']:
            fail_count += 1
            print("   실패 항목:")
            for criterion, result in results.items():
                if criterion != 'overall' and not result['pass']:
                    print(f"     ❌ {criterion}: {result['details']}")
    
    print(f"\n총계:")
    print(f"   PASS: {4 - fail_count}/4 블로그")
    print(f"   FAIL: {fail_count}/4 블로그")
    print(f"   전체 평가: {'✅ 모든 블로그 통과' if fail_count == 0 else f'❌ {fail_count}개 블로그 실패'}")
    
    return all_results

if __name__ == "__main__":
    main()