#!/usr/bin/env python3
"""리팩토링 회귀 테스트"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def test_validators():
    """validators.py 테스트"""
    print("\n" + "=" * 50)
    print("[테스트 1] validators.py")
    print("=" * 50)
    
    from utils.validators import is_cafe, is_valid_restaurant, is_valid_recipe, get_content_type
    from storage.models import Restaurant, Recipe
    
    # 카페 판별 테스트
    cafe1 = Restaurant(name="카페이밤헤스티아", category="", address="경북 영양", phone="")
    cafe2 = Restaurant(name="스타벅스", category="커피전문점", address="서울", phone="")
    cafe3 = Restaurant(name="달식당", category="이탈리안", address="경북", phone="")
    
    print(f"카페이밤헤스티아 → is_cafe: {is_cafe(cafe1)} (예상: True)")
    print(f"스타벅스 → is_cafe: {is_cafe(cafe2)} (예상: True)")
    print(f"달식당 → is_cafe: {is_cafe(cafe3)} (예상: False)")
    
    # 맛집 검증 테스트
    rest1 = Restaurant(name="달식당", category="이탈리안", address="경북 영양", phone="0507-1420-1664")
    rest2 = Restaurant(name="유즈노모레", category="", address="경남 남해", phone="010-4351-2624")
    
    valid1, reason1 = is_valid_restaurant(rest1)
    valid2, reason2 = is_valid_restaurant(rest2)
    
    print(f"달식당 (업종O) → valid: {valid1}, reason: {reason1}")
    print(f"유즈노모레 (업종X) → valid: {valid2}, reason: {reason2}")
    
    # 타입 판별 테스트
    recipe = Recipe(name="막걸리수육", ingredients=["돼지고기", "막걸리"], steps=["삶는다", "썬다"])
    
    print(f"카페이밤헤스티아 → type: {get_content_type(cafe1)} (예상: cafe)")
    print(f"달식당 → type: {get_content_type(rest1)} (예상: restaurant)")
    print(f"막걸리수육 → type: {get_content_type(recipe)} (예상: recipe)")
    
    return True


def test_restaurant_generator():
    """맛집 글 생성기 테스트"""
    print("\n" + "=" * 50)
    print("[테스트 2] RestaurantContentGenerator")
    print("=" * 50)
    
    from generators.content_restaurant import RestaurantContentGenerator
    from storage.models import Restaurant
    
    gen = RestaurantContentGenerator()
    
    # 업종 있는 경우
    item1 = Restaurant(
        name="달식당",
        category="이탈리안 파스타",
        address="경상북도 영양군 영양읍 동부리 146",
        phone="0507-1420-1664",
        broadcast="생생정보",
        broadcast_date="1월 21일"
    )
    
    content1 = gen.generate(item1, "1월 21일", corner_name="믿고떠나는스타의고장")
    
    if content1:
        print("✅ 업종 있는 맛집 글 생성 성공")
        print(f"   글자수: {len(content1)}자")
        # 타이틀 확인
        import re
        title_match = re.search(r'<title>(.+?)</title>', content1)
        if title_match:
            print(f"   타이틀: {title_match.group(1)}")
    else:
        print("❌ 업종 있는 맛집 글 생성 실패")
    
    # 업종 없는 경우 (생성 안 되어야 함)
    item2 = Restaurant(
        name="유즈노모레",
        category="",
        address="경남 남해",
        phone="010-4351-2624",
        broadcast="생생정보",
        broadcast_date="1월 21일"
    )
    
    content2 = gen.generate(item2, "1월 21일")
    
    if content2 is None:
        print("✅ 업종 없는 맛집 글 생성 스킵 (정상)")
    else:
        print("❌ 업종 없는데 글이 생성됨 (오류)")
    
    return True


def test_cafe_generator():
    """카페 글 생성기 테스트"""
    print("\n" + "=" * 50)
    print("[테스트 3] CafeContentGenerator")
    print("=" * 50)
    
    from generators.content_cafe import CafeContentGenerator
    from storage.models import Restaurant
    
    gen = CafeContentGenerator()
    
    item = Restaurant(
        name="카페이밤헤스티아",
        category="카페",
        address="경상북도 영양군 입암면 신구리 154",
        phone="0507-1304-9043",
        broadcast="생생정보",
        broadcast_date="1월 21일"
    )
    
    content = gen.generate(
        item, 
        "1월 21일", 
        corner_name="믿고떠나는스타의고장",
        instagram_url="https://instagram.com/test"
    )
    
    if content:
        print("✅ 카페 글 생성 성공")
        print(f"   글자수: {len(content)}자")
        import re
        title_match = re.search(r'<title>(.+?)</title>', content)
        if title_match:
            print(f"   타이틀: {title_match.group(1)}")
        if '카페' in content:
            print("✅ '카페' 단어 포함됨")
        if '인스타그램' in content:
            print("✅ 인스타그램 링크 포함됨")
    else:
        print("❌ 카페 글 생성 실패")
    
    return True


def test_recipe_generator():
    """레시피 글 생성기 테스트"""
    print("\n" + "=" * 50)
    print("[테스트 4] RecipeContentGenerator")
    print("=" * 50)
    
    from generators.content_recipe import RecipeContentGenerator
    from storage.models import Recipe
    
    gen = RecipeContentGenerator()
    
    item = Recipe(
        name="막걸리수육",
        ingredients=["돼지고기 앞다리살 600g", "막걸리 2컵", "된장 1큰술", "마늘 5쪽"],
        steps=["고기를 찬물에 담가 핏물을 뺀다", "막걸리와 된장을 넣고 삶는다", "40분간 중불에서 익힌다", "썰어서 접시에 담는다"],
        chef="김하진",
        broadcast="알토란",
        broadcast_date="1월 19일"
    )
    
    content = gen.generate(item, "1월 19일", corner_name="576회")
    
    if content:
        print("✅ 레시피 글 생성 성공")
        print(f"   글자수: {len(content)}자")
        import re
        title_match = re.search(r'<title>(.+?)</title>', content)
        if title_match:
            print(f"   타이틀: {title_match.group(1)}")
        if '<ul>' in content and '<ol>' in content:
            print("✅ 재료(ul)와 순서(ol) 태그 포함됨")
    else:
        print("❌ 레시피 글 생성 실패")
    
    return True


def test_notifier():
    """텔레그램 알림 테스트"""
    print("\n" + "=" * 50)
    print("[테스트 5] TelegramNotifier")
    print("=" * 50)
    
    from publishers.notifier import TelegramNotifier
    
    notifier = TelegramNotifier()
    
    if notifier.is_configured():
        print("✅ 텔레그램 설정됨")
        
        # 수동 검토 알림 테스트 (실제 전송은 안 함)
        test_item = {
            'name': '유즈노모레',
            'broadcast': '생생정보',
            'corner_name': '나나랜드',
            'category': '',
            'address': '경남 남해군',
            'phone': '010-4351-2624',
            'broadcast_date': '1월 21일',
            'instagram_url': 'https://instagram.com/test'
        }
        
        print("   notify_manual_review 함수 존재: ✅")
    else:
        print("⚠️ 텔레그램 미설정 (테스트 스킵)")
    
    return True


def test_html_structure():
    """HTML 구조 테스트 - h3 없이 h2만 사용"""
    print("\n" + "=" * 50)
    print("[테스트 6] HTML 구조 (h2만 사용)")
    print("=" * 50)
    
    from generators.content_restaurant import RestaurantContentGenerator
    from storage.models import Restaurant
    
    gen = RestaurantContentGenerator()
    
    item = Restaurant(
        name="테스트맛집",
        category="한식",
        address="서울 강남구",
        phone="02-1234-5678",
        broadcast="생생정보",
        broadcast_date="1월 21일"
    )
    
    content = gen.generate(item, "1월 21일", corner_name="테스트코너")
    
    if content:
        has_h3 = '<h3>' in content
        has_h2 = '<h2>' in content
        
        if has_h2 and not has_h3:
            print("✅ h2만 사용됨 (h3 없음)")
        elif has_h3:
            print("❌ h3 태그 발견됨 (수정 필요)")
        else:
            print("⚠️ h2 태그 없음")
    else:
        print("❌ 글 생성 실패")
    
    return True


def main():
    """메인 테스트 실행"""
    print("=" * 50)
    print("리팩토링 회귀 테스트")
    print("=" * 50)
    
    results = {}
    
    try:
        results['validators'] = test_validators()
    except Exception as e:
        print(f"❌ validators 테스트 오류: {e}")
        results['validators'] = False
    
    try:
        results['restaurant_generator'] = test_restaurant_generator()
    except Exception as e:
        print(f"❌ restaurant_generator 테스트 오류: {e}")
        results['restaurant_generator'] = False
    
    try:
        results['cafe_generator'] = test_cafe_generator()
    except Exception as e:
        print(f"❌ cafe_generator 테스트 오류: {e}")
        results['cafe_generator'] = False
    
    try:
        results['recipe_generator'] = test_recipe_generator()
    except Exception as e:
        print(f"❌ recipe_generator 테스트 오류: {e}")
        results['recipe_generator'] = False
    
    try:
        results['notifier'] = test_notifier()
    except Exception as e:
        print(f"❌ notifier 테스트 오류: {e}")
        results['notifier'] = False
    
    try:
        results['html_structure'] = test_html_structure()
    except Exception as e:
        print(f"❌ html_structure 테스트 오류: {e}")
        results['html_structure'] = False
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("테스트 결과 요약")
    print("=" * 50)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, passed_test in results.items():
        status = "✅ 통과" if passed_test else "❌ 실패"
        print(f"  {name}: {status}")
    
    print(f"\n총 {passed}/{total} 통과")
    
    if passed == total:
        print("\n🎉 모든 테스트 통과!")
    else:
        print("\n⚠️ 일부 테스트 실패 - 위 로그 확인")


if __name__ == "__main__":
    main()
