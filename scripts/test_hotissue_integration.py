#!/usr/bin/env python3
"""
hotissue-hugo 파이프라인 통합 검증 스크립트
LLM 오염 방어 로직의 실제 적용을 검증합니다.
"""

import sys
import os
sys.path.insert(0, '/Users/twinssn/Projects/5000')

def test_pipeline_integration():
    """파이프라인 통합 테스트"""
    print("🧪 hotissue-hugo 파이프라인 통합 테스트...")
    
    # 1. 설정 확인
    try:
        # YAML 파일 직접 로드
        import yaml
        with open('/Users/twinssn/Projects/5000/config/blogs.d/cap.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        hotissue_config = None
        for blog in config.get('blogs', []):
            if blog.get('id') == 'hotissue-hugo':
                hotissue_config = blog
                break
        
        if hotissue_config:
            print(f"✅ hotissue-hugo blog ID 확인: {hotissue_config['id']}")
            print(f"   상태: {hotissue_config['status']}")
            print(f"   도메인: {hotissue_config['domain']}")
        else:
            print("❌ hotissue-hugo 설정 찾을 수 없음")
            return False
    except Exception as e:
        print(f"❌ blog 설정 로드 실패: {e}")
        return False
    
    # 2. 파이프라인 임포트 확인
    try:
        from pipelines.car.pipeline import generate_car, validate_body
        print("✅ car pipeline 임포트 성공")
    except ImportError as e:
        print(f"❌ pipeline 임포트 실패: {e}")
        return False
    
    # 3. AI Writer 임포트 확인
    try:
        from shared.ai_writer import generate
        print("✅ ai_writer 임포트 성공")
    except ImportError as e:
        print(f"❌ ai_writer 임포트 실패: {e}")
        return False
    
    # 4. AI Response Parser 임포트 확인
    try:
        from shared.ai_response_parser import parse_ai_response
        print("✅ ai_response_parser 임포트 성공")
    except ImportError as e:
        print(f"❌ ai_response_parser 임포트 실패: {e}")
        return False
    
    return True

def test_contamination_detection():
    """오염 감지 실제 테스트"""
    print("\n🧪 오염 감지 실제 테스트...")
    
    # Import AI response parser for this test
    from shared.ai_response_parser import parse_ai_response
    
    # 실제 오염 샘플 데이터
    contaminated_samples = [
        {
            "name": "실제 오염 샘플 1",
            "content": """# 2024년형 스포티지 N-Line

## 사용자가 제공한 데이터
스포티지 N-Line의 가격은 3,000만원입니다. LLM이 생성한 데이터를 기반으로 분석합니다.

## 가격 정보
가격은 3,000만원부터 시작하며, N-Line 트림이 적용되었습니다. 연비는 복합 기준 11.8km/L 수준입니다.

## 성능 평가
엔진 성능과 주행 안정성이 뛰어나며, 가족용 SUV로서 활용성이 좋습니다.""",
            "should_block": True
        },
        {
            "name": "실제 오염 샘플 2", 
            "content": """# 그랜저 HG N

## 이제 작성 시작
그랜저 HG N의 분석을 시작합니다. LLM이 사고과정을 포함하여 생성합니다.

## 가격 정보
가격은 3,530만원부터 시작하며, 고급 세단 시장에서 강력한 입지를 차지하고 있습니다.

## 연비 효율
연비는 복합 기준 12.8km/L로 경쟁 모델 대비 우수한 수치를 기록하고 있습니다.""",
            "should_block": True
        },
        {
            "name": "정상 콘텐츠 샘플",
            "content": """# 2024년형 그랜저 HG N

## 가격 정보
2024년형 그랜저 HG N의 가격은 3,530만원부터 시작합니다. 이는 고급 세단 시장에서 합리적인 가격대를 형성하고 있습니다.

## 연비 효율
연비는 복합 기준 12.8km/L를 기록하며, V6 엔진의 성능과 연비의 균형이 뛰어납니다. 고속도주행 시 연비는 더욱 개선됩니다.

## 결론
그랜저 HG N은 가성비와 브랜드 가치의 균형이 뛰어난 모델로, 장거리 주행과 도심 주행 모두에 적합합니다.""",
            "should_block": False
        }
    ]
    
    results = []
    
    for sample in contaminated_samples:
        print(f"\n--- 테스트: {sample['name']} ---")
        
        try:
            parse_result = parse_ai_response(sample['content'])
            
            blocked = parse_result['should_fail']
            leak_detected = parse_result['has_thinking_leak']
            
            # 결과 검증
            if blocked == sample['should_block']:
                status = "✅ PASS"
                print(f"  차단 결정: {'차단됨' if blocked else '통과됨'} - 기대와 일치")
            else:
                status = "❌ FAIL"
                expected = "차단됨" if sample['should_block'] else "통과됨"
                actual = "차단됨" if blocked else "통과됨"
                print(f"  차단 결정: {actual} - 기대: {expected} (불일치)")
            
            print(f"  누수 감지: {leak_detected}")
            print(f"  누수 패턴: {parse_result['leak_pattern'] if parse_result['leak_pattern'] else '없음'}")
            print(f"  상태: {status}")
            
            results.append({
                'name': sample['name'],
                'status': status,
                'blocked': blocked,
                'leak_detected': leak_detected
            })
            
        except Exception as e:
            print(f"  ❌ 오류 발생: {e}")
            results.append({
                'name': sample['name'],
                'status': '❌ ERROR',
                'error': str(e)
            })
    
    # 결과 요약
    passed = sum(1 for r in results if r['status'] == "✅ PASS")
    total = len(results)
    
    print(f"\n📊 오염 감지 테스트 결과: {passed}/{total} 통과")
    
    if passed == total:
        print("✅ 모든 오염 감지 테스트 통과")
        return True
    else:
        print("❌ 일부 테스트 실패")
        for result in results:
            if result['status'] != "✅ PASS":
                print(f"  - {result['name']}: {result['status']}")
        return False

def test_writer_integration():
    """AI Writer 통합 테스트"""
    print("\n🧪 AI Writer 통합 테스트...")
    
    try:
        # 간단한 프롬프트로 테스트
        test_prompt = """다음 차량에 대한 분석 글을 작성해주세요:

## 메인 차량 데이터
{
  "model": "아반테 뉴라이즈",
  "brand": "현대", 
  "base_price": 2800,
  "fuel_efficiency": 11.5
}"""
        
        from shared.ai_writer import generate_car
        from pipelines.car.topic_manager import make_slug
        
        # 데이터 준비
        test_data = {
            "model": "아반테 뉴라이즈",
            "brand": "현대",
            "base_price": 2800,
            "fuel_efficiency": 11.5
        }
        
        # 글 생성
        result = generate_car(test_prompt, test_data)
        
        if result:
            print("✅ AI Writer 통합 성공")
            print(f"  생성된 글 길이: {len(result)}자")
            
            # 오염 검사
            from shared.ai_response_parser import parse_ai_response
            parse_result = parse_ai_response(result)
            
            if parse_result['should_fail']:
                print("❌ 생성된 글에 오염 감지 - 차단됨")
                return False
            else:
                print("✅ 생성된 글에 오염 없음 - 통과됨")
                return True
        else:
            print("❌ AI Writer 통합 실패 - 결과 없음")
            return False
            
    except Exception as e:
        print(f"❌ AI Writer 통합 테스트 오류: {e}")
        return False

def main():
    """주요 통합 검증 실행"""
    print("🚀 hotissue-hugo 파이프라인 통합 검증 시작")
    print("=" * 60)
    
    all_passed = True
    
    # 1. 파이프라인 통합 테스트
    integration_passed = test_pipeline_integration()
    all_passed = all_passed and integration_passed
    
    # 2. 오염 감지 테스트
    detection_passed = test_contamination_detection()
    all_passed = all_passed and detection_passed
    
    # 3. AI Writer 통합 테스트
    writer_passed = test_writer_integration()
    all_passed = all_passed and writer_passed
    
    print("\n" + "=" * 60)
    print("📊 최종 통합 검증 결과")
    print(f"파이프라인 통합: {'✅ PASS' if integration_passed else '❌ FAIL'}")
    print(f"오염 감지: {'✅ PASS' if detection_passed else '❌ FAIL'}")
    print(f"AI Writer 통합: {'✅ PASS' if writer_passed else '❌ FAIL'}")
    print(f"\n전체 결과: {'✅ 모든 테스트 통과' if all_passed else '❌ 일부 테스트 실패'}")
    
    if all_passed:
        print("\n🎉 hotissue-hugo 파이프라인 통합 검증 완료!")
        print("✅ 발행 재개 전제 조건 충족")
        print("📋 다음 단계:")
        print("   1. git commit -m 'feat: LLM 오염 방어 로직 구현'")
        print("   2. hotissue-hugo 발행 파이프라인 재개")
        print("   3. 모니터링 및 테스트")
    else:
        print("\n⚠️ 통합 검증에 문제가 발견되었습니다.")
        print("📋 추가 디버깅이 필요합니다.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())