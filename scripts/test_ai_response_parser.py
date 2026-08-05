#!/usr/bin/env python3
"""
AI 응답 파서 검증 스크립트
오염 방어 로직의 정확성을 검증합니다.
"""

import sys
import os
sys.path.insert(0, '/Users/twinssn/Projects/5000')

from shared.ai_response_parser import parse_ai_response

def test_thinking_leak_detection():
    """사고과정 누수 감지 기능 검증"""
    print("🧪 사고과정 누수 감지 검증...")
    
    # 테스트 케이스 정의
    test_cases = [
        {
            "name": "정상 응답",
            "content": """# 현대 그랜저 HG N 런칭

## 가격 정보
현대 그랜저 HG N의 가격은 3,530만원부터 시작합니다. 이 가격은 경쟁 모델에 비해 합리적인 수준입니다.

## 연비 효율
연비는 복합 기준 12.8km/L로, 연간 주행거리를 고려할 때 연료비 절감 효과가 큽니다. 연비는 전년 모델과 동일 수준을 유지했습니다.""",
            "expected": {"leak": False, "fallback": False}
        },
        {
            "name": "사고과정 누수 패턴 1",
            "content": """# 아반테 뉴라이즈

## 사용자가 제공한 데이터
아반테 뉴라이즈의 가격은 2,800만원입니다. 이 가격은 경쟁 모델 대비 5% 저렴한 수준입니다.

## 가격 정보
가격은 2,800만원부터 시작하며, 할인 조건에 따라 추가 할인 가능합니다. 연간 유지비는 평균 120만원 수준입니다.""",
            "expected": {"leak": True, "fallback": False}
        },
        {
            "name": "사고과정 누수 패턴 2", 
            "content": """# 코나 EV 트림

## 이제 작성 시작
코나 EV의 가격은 4,200만원으로, 전기차 시장에서 강력한 경쟁력을 보유하고 있습니다.

## 가격 정보
가격은 4,200만원이며, 보조금 적용 시 실제 구매가는 3,800만원 수준입니다. 연비는 전기차 특성상 153km/charge 수준입니다.""",
            "expected": {"leak": True, "fallback": False}
        },
        {
            "name": "사고과정 누수 패턴 3",
            "content": """# 제네시스 G80

## H2-1: 가격 분석
제네시스 G80의 가격은 6,500만원부터 시작합니다. 이 가격은 럭셔리 세그먼트에서 중간 위치를 차지합니다.

## H2-2: 연비 정보
연비는 9.6km/L로, V6 엔진의 성능과 연비의 균형이 좋습니다. 3년 후 잔존가치율은 65%로 우수합니다.""",
            "expected": {"leak": True, "fallback": False}
        },
        {
            "name": "사고과정 누수 패턴 4",
            "content": """# 쏘나타 N 라인

## 문장 수: 15
쏘나타 N 라인은 성능과 스타일을 동시에 잡은 모델입니다. 가격은 3,800만원부터 시작합니다.

## 가격 정보
가격은 3,800만원이며, N 라인 전용 옵션으로 200만원 추가 가능합니다. 연비는 복합 기준 10.2km/L 수준입니다.""",
            "expected": {"leak": True, "fallback": False}
        },
        {
            "name": "사고과정 누수 패턴 5",
            "content": """# 싼타페 페이스리프트

## 주의: 시각적 변경점
싼타페 페이스리프트는 디자인 변경에 중점을 두었습니다. 가격은 2,900만원부터 시작합니다.

## 가격 정보
가격은 2,900만원이며, 가족용 SUV로서 공간 활용성이 뛰어납니다. 연비는 복합 기준 10.5km/L 수준입니다.""",
            "expected": {"leak": True, "fallback": False}
        },
        {
            "name": "사고과정 누수 패턴 6",
            "content": """# K8 N-Line

## 규칙: 핵심 스펙만 집중
K8 N-Line은 스포츠 뉘앙스를 강조한 트림입니다. 가격은 2,600만원부터 시작합니다.

## 가격 정보  
가격은 2,600만원이며, N-Line 디자인 요소가 적용되었습니다. 연비는 복합 기준 12.5km/L 수준입니다.""",
            "expected": {"leak": True, "fallback": False}
        },
        {
            "name": "사고과정 누수 패턴 7",
            "content": """# 스포티지 N-Line

## ~해야 합니다. 강조
스포티지 N-Line은 성능과 실용성을 균형 있게 조화했습니다. 가격은 2,500만원부터 시작합니다.

## 가격 정보
가격은 2,500만원이며, SUV의 활용성을 유지한 성능 모델입니다. 연비는 복합 기준 11.8km/L 수준입니다.""",
            "expected": {"leak": True, "fallback": False}
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- 테스트 케이스 {i}: {test_case['name']} ---")
        
        try:
            result = parse_ai_response(test_case['content'])
            
            # 결과 검증
            leak_detected = result['has_thinking_leak']
            fallback_used = result['is_fallback']
            
            expected = test_case['expected']
            
            # 누수 감지 검증
            leak_correct = (leak_detected == expected['leak'])
            fallback_correct = (fallback_used == expected['fallback'])
            
            status = "✅ PASS" if leak_correct and fallback_correct else "❌ FAIL"
            
            print(f"  누수 감지: {leak_detected} (기대: {expected['leak']}) - {'맞음' if leak_correct else '틀림'}")
            print(f"  폴백 사용: {fallback_used} (기대: {expected['fallback']}) - {'맞음' if fallback_correct else '틀림'}")
            print(f"  상태: {status}")
            print(f"  누수 패턴: {result['leak_pattern'] if result['leak_pattern'] else '없음'}")
            print(f"  제목 추출: {'성공' if result['title'] else '실패'}")
            print(f"  본문 길이: {len(result['body'])}자")
            
            results.append({
                'test_case': test_case['name'],
                'status': status,
                'leak_correct': leak_correct,
                'fallback_correct': fallback_correct,
                'details': result
            })
            
        except Exception as e:
            print(f"  ❌ 오류 발생: {e}")
            results.append({
                'test_case': test_case['name'], 
                'status': '❌ ERROR',
                'error': str(e)
            })
    
    # 요약
    print(f"\n📊 검증 결과 요약")
    print(f"전체 테스트: {len(test_cases)}개")
    passed = sum(1 for r in results if r['status'] == "✅ PASS")
    failed = len(results) - passed
    print(f"통과: {passed}개, 실패: {failed}개")
    
    if failed > 0:
        print("\n❌ 실패한 테스트:")
        for result in results:
            if result['status'] != "✅ PASS":
                print(f"  - {result['test_case']}: {result['status']}")
                if 'error' in result:
                    print(f"    오류: {result['error']}")
    
    return passed == len(test_cases)

def test_structured_parsing():
    """명시적 출력 계약 파싱 검증"""
    print("\n🧪 명시적 출력 계약 파싱 검증...")
    
    test_cases = [
        {
            "name": "TITLE:/BODY: 태그 파싱",
            "content": """TITLE: 현대 그랜저 HG N

## 가격 정보
현대 그랜저 HG N의 가격은 3,530만원부터 시작합니다.

## 연비 효율
연비는 복합 기준 12.8km/L로 우수합니다.""",
            "expected_title": "현대 그랜저 HG N"
        },
        {
            "name": "H1 제목 추출", 
            "content": """# 아반테 뉴라이즈

## 가격 정보
아반테 뉴라이즈의 가격은 2,800만원입니다.

## 연비 효율
연비는 11.5km/L 수준입니다.""",
            "expected_title": "아반테 뉴라이즈"
        },
        {
            "name": "H2 기반 폴백 파싱",
            "content": """## 가격 분석
현대 그랜저 HG N의 가격은 3,530만원부터 시작합니다. 이 가격은 경쟁 모델 대비 합리적입니다.

## 연비 효율
연비는 복합 기준 12.8km/L로 우수하며, 고속도로에서는 15.2km/L를 기록합니다.

## 결론
이 차량은 가성비와 연비의 균형이 뛰어납니다.""",
            "expected_title": None  # H2 이전 내용이 3줄 이상이므로 제목 추출 실패
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- 테스트 케이스 {i}: {test_case['name']} ---")
        
        try:
            result = parse_ai_response(test_case['content'])
            
            title_correct = (result['title'] == test_case['expected_title'])
            status = "✅ PASS" if title_correct else "❌ FAIL"
            
            print(f"  제목 추출: '{result['title']}' (기대: '{test_case['expected_title']}')")
            print(f"  상태: {status}")
            print(f"  폴백 사용: {result['is_fallback']}")
            print(f"  누수 감지: {result['has_thinking_leak']}")
            
            results.append({
                'test_case': test_case['name'],
                'status': status,
                'title_correct': title_correct
            })
            
        except Exception as e:
            print(f"  ❌ 오류 발생: {e}")
            results.append({
                'test_case': test_case['name'],
                'status': '❌ ERROR', 
                'error': str(e)
            })
    
    return all(r['status'] == "✅ PASS" for r in results)

def test_content_cleaning():
    """사고과정 내용 정리 기능 검증"""
    print("\n🧪 사고과정 내용 정리 검증...")
    
    test_content = """# 스포티지 N-Line

## 사용자가 제공한 데이터
스포티지 N-Line의 가격은 2,500만원입니다. 가격 분석을 시작합니다.

## 이제 작성 시작
스포티지 N-Line은 성능과 실용성을 균형 있게 조화했습니다. H2-1 가격 정보.

## 가격 정보  
가격은 2,500만원이며, N-Line 딜러에서 구매 시 추가 혜택 있습니다. 문장 수: 10개.
연비는 복합 기준 11.8km/L 수준입니다. ~해야 합니다. 점검 완료.

## 규칙: 스포츠 뉘앙스 강조
스포티지 N-Line은 스포츠 뉘앙스를 강조하며, 가족용 SUV로서 활용성도 뛰어납니다."""
    
    print("원본 내용:")
    print(test_content)
    print("\n" + "="*50)
    
    try:
        result = parse_ai_response(test_content)
        
        print("정리된 내용:")
        print(result['body'])
        print(f"\n정리 결과:")
        print(f"- 제목: {result['title']}")
        print(f"- 누수 감지: {result['has_thinking_leak']}")
        print(f"- 누수 패턴: {result['leak_pattern']}")
        print(f"- 폴백 사용: {result['is_fallback']}")
        print(f"- 발행 차단: {result['should_fail']}")
        
        # 정리 확인
        cleaned_patterns = [
            '사용자가 제공한 데이터' not in result['body'],
            '이제 작성' not in result['body'], 
            'H2-' not in result['body'],
            '문장 수:' not in result['body'],
            '~해야 합니다' not in result['body'],
            '규칙:' not in result['body']
        ]
        
        cleaning_success = all(cleaned_patterns) and result['has_thinking_leak']
        
        print(f"\n📋 정리 성공: {'✅ PASS' if cleaning_success else '❌ FAIL'}")
        print(f"- 패턴 제거 여부: {cleaned_patterns}")
        
        return cleaning_success
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

def main():
    """주요 검증 실행"""
    print("🚀 AI 응답 파서 검증 시작")
    print("=" * 50)
    
    all_passed = True
    
    # 사고과정 누수 감지 검증
    leak_detection_passed = test_thinking_leak_detection()
    all_passed = all_passed and leak_detection_passed
    
    # 명시적 출력 계약 파싱 검증  
    parsing_passed = test_structured_parsing()
    all_passed = all_passed and parsing_passed
    
    # 내용 정리 검증
    cleaning_passed = test_content_cleaning()
    all_passed = all_passed and cleaning_passed
    
    print("\n" + "=" * 50)
    print("📊 최종 검증 결과")
    print(f"사고과정 감지: {'✅ PASS' if leak_detection_passed else '❌ FAIL'}")
    print(f"명시적 파싱: {'✅ PASS' if parsing_passed else '❌ FAIL'}")
    print(f"내용 정리: {'✅ PASS' if cleaning_passed else '❌ FAIL'}")
    print(f"\n전체 결과: {'✅ 모든 테스트 통과' if all_passed else '❌ 일부 테스트 실패'}")
    
    if all_passed:
        print("\n🎉 오염 방어 로직이 정상적으로 작동합니다!")
        print("hotissue-hugo 발행 재개 전제 조건 충족")
    else:
        print("\n⚠️ 오염 방어 로직에 문제가 발견되었습니다.")
        print("추가 디버깅이 필요합니다.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())