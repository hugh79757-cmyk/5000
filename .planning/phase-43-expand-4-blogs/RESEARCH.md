# Phase 43 Research — 확장 대상 4개 블로그 현황

**조사일자**: 2026-07-24  
**조사대상**: travel1-hugo(축제), travel2-hugo(문화유산), travel3-hugo(맛집), travel4-hugo(코스)

---

## [1] 블로그-프롬프트 매핑 확인

| 블로그ID | fetch_sources | prompt_map | 프롬프트ID |
|---------|-------------|------------|-----------|
| travel1-hugo | festival | festival: travel1_festival<br>korservice: travel1_festival | travel1_festival |
| travel2-hugo | heritage | heritage: travel2_heritage<br>korservice: travel2_heritage | travel2_heritage |
| travel3-hugo | food | food: tour2_food<br>korservice: tour2_food | tour2_food |
| travel4-hugo | course | course: tour3_course<br>korservice: tour3_course | tour3_course |

**핵심 발견**: 모든 블로그가 별도 프롬프트를 사용하며, korservice 데이터가 있으면 동일 프롬프트 사용

---

## [2] 4개 주제 프롬프트 원문 분석

### travel1_festival (축제)
**system 주요 포인트**:
- "~입니다/~습니다" 체로 정중하게 작성
- 2,500자 이상, H2 4개 구조 엄수
- **강화된 ANTI-HALLUCINATION**: 맛집/가격/방문객 수/주차 수용대수 절대 금지
- **"직접 방문한 것처럼 쓰지 마세요"** 정보 전달 목적 강조

**user 구조**:
1. ## {region} {theme} 개요와 일정 (축제명, 기간, 장소, 입장료)
2. ## 주요 프로그램과 체험
3. ## 교통과 주차 안내
4. ## 방문 전 참고사항

**데이터 활용 방식**: 축제명, 일정, 장소, 입장료, 주최/주관 정보만 사용

### travel2_heritage (문화유산)
**system 주요 포인트**:
- "같은 지역·같은 종목의 문화유산 2~3곳을 맥락 있게 묶어 소개"
- **공통 맥락 강조**: 같은 시대, 같은 종목, 같은 양식, 같은 사찰 등 연결
- 단순 나열 금지 → 비교·대조·흐름으로 서술
- 2,500자 이상 3,500자 이하, H2 3~4개 구조

**user 구조**:
1. ## {region} {theme} 개요 (공통 맥락과 역사적 배경)
2. ## 각 문화유산별 H3 (데이터 수만큼)
3. ## 방문 안내
4. ## 문화유산의 가치

**데이터 활용 방식**: 상세설명(overview)의 연도, 인물명, 크기 정확히 인용

### tour2_food (맛집)
**system 주요 포인트**:
- "독자가 글을 읽고 '이 식당에 가봐야겠다'고 느끼도록 실용적인 정보"
- **ABSOLUTE BAN**: 34개 금지어 목록 (추천드립니다, 인기가 많습니다 등)
- **TITLE-BODY CONSISTENCY**: 제목 숫자와 본문 수량 정확히 일치
- 맛 묘사 절대 금지 ("쫄깃한", "시원한 국물" 등)

**user 구조**:
- 도입부: 지역 음식 문화 특성 소개
- ## {region} {theme} {count}곳 한눈에 비교
- ## 식당별 상세 정보 (H3 {count}개)
- ## 방문 시 참고사항
- 마무리

**데이터 활용 방식**: 메뉴명, 가격, 영업시간, 전화번호만 사용, "~만원대" 금지

### tour3_course (여행코스)
**system 주요 포인트**:
- "수익형 국내여행 블로그 전문 에디터"
- **이동시간 금지**: "차로 N분, 도보 N분" 절대 금지
- **코스명 정제**: 문장형 → 핵심 키워드로 간결화
- **TITLE-BODY CONSISTENCY**: 지역·장소명 일치

**user 구조**:
1. ## {region} 여행코스 요약 (코스 순서, 장소명 bold-list)
2. ## 코스 상세 안내 (H3 {count}개)
3. ## 방문 전 참고사항

**데이터 활용 방식**: 주소, 설명(overview) 활용, 입장료·영업시간·이동시간 데이터 없음 시 생략

---

## [3] _build_data_block 데이터 필드 현황

### 공통 필드
- `display_region`: 지역명 (축제: 미추홀구, 문화유산: 전북 남원시, 맛집: 충남 서산시, 코스: 경북)
- `theme`: 테마명 (축제: 축제, 문화유산: 보물, 맛집: 맛집, 코스: 가족코스)
- `items`: 장소 리스트 (3~4개)
- `source_type`: 데이터 타입 (festival, heritage, food, course)

### 주제별 특화 필드
- **festival**: 주최/주관 정보, 일정, 장소, 입장료
- **heritage**: 상세설명(overview), 시대, 양식, 역사적 의의
- **food**: 메뉴명, 가격, 영업시간, 주차 정보
- **course**: 코스명, 하위장소, 설명(overview)

---

## [4] 주제별 데이터 실측 결과

| 함수명 | region | theme | items | 상태 |
|-------|-------|-------|-------|------|
| fetch_festival | 미추홀구 | 축제 | 3 | ✅ 정상 |
| fetch_heritage | 전북 남원시 | 보물 | 3 | ✅ 정상 |
| fetch_food | 충남 서산시 | 맛집 | 3 | ✅ 정상 (2개 시군구 오류 후 서산시 성공) |
| fetch_course | 경북 | 가족코스 | 4 | ✅ 정상 |

**API 과금 고려**: 각 fetch 1회 호출로 주제별 데이터 수집 확인 완료

---

## [5] Phase 40에서 검증된 공통 적용 사항

### 이미 적용된 개선사항
1. **title 프롬프트**: 40개 예시로 확장 + deepseek 교체 (temperature=0.6, max_tokens=60)
2. **title 검증**: 긴 단어 임계값 8→12자 상향
3. **템플릿 수정**: travel-hugo 비문 어순 교정

### 본문 프롬프트 관찰
- **공통점**: 모두 ANTI-HALLUCINATION 규칙 강화
- **차이점**: 구조와 데이터 활용 방식 주제별 상이
- **필요 검증**: 본문 프롬프트도 40에서 사용한 temperature/length 적용 여부 확인 필요

---

## [6] 검증 필요 사항

### 긴급 검증 항목
1. **본문 프롬프트 파라미터**: 현재 사용 중인 temperature, max_tokens 설정 확인
2. **데이터 필드 활용**: 각 프롬프트가 지원하는 필드 vs 실제 데이터 필드 매칭
3. **title-body 일관성**: 제목-본문 숫자/키워드 일관성 검증 (특히 맛집)
4. **에러 처리**: food fetch 시 일부 시군구 오류 발생 (원인: 데이터 구조 불일치)

### 리스크 요소
- **tour2_food**: 34개 금지어로 인한 생성 실패 가능성
- **tour3_course**: 이동시간 정보 부족으로 인한 콘텐츠 양부족 리스크
- **travel2_heritage**: 공통 맥락 찾기 로직 복잡성 (3곳 묶기 전략)

---

## [7] 다음 단계 제안

### 검증 순서 (리스크 낮은 순서)
1. **travel1_festival** → 구조 단순, ANTI-HALLUCINATION 명확
2. **travel3_food** → 데이터 구조 명확, 금지어만 주의
3. **travel4_course** → 코스 구조 단순, 이동시간 금지 규칙 명확
4. **travel2_heritage** → 맥락 연결 로직 복잡, 가장 마지막 검증

### API 과금 최소화 전략
- 각 주제당 dry-run 1회로 제한
- 본문 생성 전 title 생성만 먼저 테스트
- 실제 발행은 검증 완료 후 Phase 43 실행에서 처리

---

**조사 완료**: 모든 4개 블로그의 프롬프트, 데이터 구조, 실측 데이터 확인 완료  
**다음 단계**: 각 주제별 프롬프트에 Phase 40에서 검증된 옵션 적용 → dry-run 검증 → PLAN.md 작성