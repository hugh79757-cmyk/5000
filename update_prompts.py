import yaml

with open('/Users/twinssn/Projects/5000/config/prompts/travel.yaml', 'r') as f:
    data = yaml.safe_load(f)

# 1. Update tour1_camping (camping blog)
camping = data['tour1_camping']
system = camping['system']

# 1a. Add "좋은" to ABSOLUTE BAN
if '"좋은"' not in system:
    system = system.replace(
        '- "접수", "안전교육" (캠핑장에는 해당 없음)',
        '- "접수", "안전교육" (캠핑장에는 해당 없음)\n\n    - "좋은"'
    )

# 1b. Add structure enforcement after length rules
if '[구조 강제' not in system:
    system = system.replace(
        '- 마무리: 3문장 이상',
        '''- 마무리: 3문장 이상


    [구조 강제 - 위반 시 불합격]
    - H2 정확히 3~4개만 사용 (H1 금지)
    - H3 정확히 3개만 사용 (캠핑장 수와 일치)
    - 캠핑 핵심 키워드(텐트, 타프, 침낭, 랜턴, 버너, 코펠) 중 3개 이상 본문 포함
    - 브랜드 키워드(스노우피크, 콜맨, 코베아, 블랙야크, 노스페이스) 중 1개 이상 본문 포함
    - 타이틀에 숫자 명시 시 본문 H2/H3 개수와 일치'''
    )

camping['system'] = system

# 1c. Update user prompt for camping
user = camping['user']
if 'H2는 정확히 4개만 사용' not in user:
    user = user.replace(
        "- 네이버 지도 링크를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)\n\n    '",
        '''- 네이버 지도 링크를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)

    - H2는 정확히 4개만 사용 (비교, 상세, 체크포인트, 준비사항). 그 외 H2 절대 금지.

    - H3는 데이터 수만큼 (보통 3개). 타이틀에 숫자(3곳 등) 명시 시 본문 H3 개수와 일치.

    - 브랜드 키워드(스노우피크, 콜맨, 코베아, 블랙야크, 노스페이스) 중 1개 이상 본문에 포함.
  user: '아래 데이터를 바탕으로 캠핑·글램핑 블로그 글을 작성하세요.'''
    )
camping['user'] = user
data['tour1_camping'] = camping

# 2. Update travel1_festival (festival blog)
festival = data['travel1_festival']
system = festival['system']

# 2a. Add "좋은" to absolute ban
if '"좋은"' not in system:
    system = system.replace(
        '- H1(#) 사용 금지. H2(##)만 사용. H2는 정확히 4개.',
        '- H1(#) 사용 금지. H2(##)만 사용. H2는 정확히 4개.\n- "좋은", "훌륭한", "최고의" (금지어)'
    )

# 2b. Add structure enforcement
if '[구조 강제' not in system:
    system = system.replace(
        '- 절대 2,200자 미만으로 끝내지 마세요. 부족하면 교통, 주차, 방문 팁을 더 자세히 쓰세요',
        '''- 절대 2,200자 미만으로 끝내지 마세요. 부족하면 교통, 주차, 방문 팁을 더 자세히 쓰세요

    [구조 강제 - 위반 시 불합격]
    - H2 정확히 4개만 사용 (개요, 프로그램, 교통주차, 방문참고)
    - 본문에 반드시 포함: "운영시간", "위치", "기간" (데이터 기반)
    - 타이틀에 숫자 명시 시 본문 H2/H3 개수와 일치'''
    )

festival['system'] = system
data['travel1_festival'] = festival

# 3. Update travel2_heritage (heritage blog)
heritage = data['travel2_heritage']
system = heritage['system']

# 3a. Add "좋은" to absolute ban
if '"좋은"' not in system:
    system = system.replace(
        '절대 금지: "바랍니다", "되시길", "있으시", "마무리하며", "마치며", "즐겨보세요", "만끽", 취소선(~~), 이모지, 이미지 마크다운 ![]()',
        '절대 금지: "바랍니다", "되시길", "있으시", "마무리하며", "마치며", "즐겨보세요", "만끽", 취소선(~~), 이모지, 이미지 마크다운 ![]()\n- "좋은"'
    )

# 3b. Add structure enforcement
if '[구조 강제' not in system:
    system = system.replace(
        '- 짧은 글은 허용되지 않습니다',
        '''- 짧은 글은 허용되지 않습니다

    [구조 강제 - 위반 시 불합격]
    - H2 3~4개, H3 3개 이상 (데이터 수만큼)
    - 본문 컨텍스트 단어 2개 이상 포함: "시대", "종목", "양식", "비교", "대조", "공통", "반면"
    - 타이틀에 숫자 명시 시 본문 H2/H3 개수와 일치'''
    )

heritage['system'] = system
data['travel2_heritage'] = heritage

# 4. Update tour2_food (food blog)
food = data['tour2_food']
system = food['system']

# 4a. Add "좋은" to absolute ban
if '"좋은"' not in system:
    system = system.replace(
        '- 직접 방문 체험형 서술 ("맛이 일품이다", "추천이 과장이 아니었다")\n\n\n    [ANTI-HALLUCINATION',
        '- 직접 방문 체험형 서술 ("맛이 일품이다", "추천이 과장이 아니었다")\n\n    - "좋은", "훌륭한", "최고의"\n\n\n    [ANTI-HALLUCINATION'
    )

# 4b. Add structure enforcement
if '[구조 강제' not in system:
    system = system.replace(
        '- 마무리: 3문장 이상',
        '''- 마무리: 3문장 이상

    [구조 강제 - 위반 시 불합격]
    - H2 3~4개, H3 3개 이상 (데이터 수만큼)
    - 본문에 반드시 포함: "메뉴", "가격" (데이터 기반)
    - 가격 표현 "~만원대", "만원대" 절대 금지
    - 타이틀에 숫자 명시 시 본문 H3 개수와 일치'''
    )

food['system'] = system
data['tour2_food'] = food

# 5. Update tour3_course (course blog)
course = data['tour3_course']
system = course['system']

# 5a. Add "좋은" to absolute ban
if '"좋은"' not in system:
    system = system.replace(
        '절대 금지: "바랍니다", "되시길", "있으시", "마무리하며", "마치며", "즐거운 시간이 되길", "만끽해 보세요", "느껴보세요", 취소선(~~), 이모지, 경어체("~세요", "~까요")',
        '절대 금지: "바랍니다", "되시길", "있으시", "마무리하며", "마치며", "즐거운 시간이 되길", "만끽해 보세요", "느껴보세요", 취소선(~~), 이모지, 경어체("~세요", "~까요"), "좋은", "훌륭한", "최고의"'
    )

# 5b. Add structure enforcement
if '[구조 강제' not in system:
    system = system.replace(
        '- 마지막 섹션도 3문장 이상으로 마무리하십시오.',
        '''- 마지막 섹션도 3문장 이상으로 마무리하십시오.

    [구조 강제 - 위반 시 불합격]
    - H2 정확히 3개, H3 3개 이상
    - H3 제목 패턴: "N코스: 장소명" 또는 "N일차: 장소명" 강제
    - 이동시간 표현 절대 금지: "도보 N분", "차로 N분", "N분 소요", "N시간 소요"
    - 타이틀에 숫자 명시 시 본문 H3 개수와 일치'''
    )

course['system'] = system
data['tour3_course'] = course

# Save
with open('/Users/twinssn/Projects/5000/config/prompts/travel.yaml', 'w') as f:
    yaml.dump(data, f, allow_unicode=True, sort_keys=False)

print("Updated all 5 prompts in travel.yaml")