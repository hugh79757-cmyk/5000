# Phase 43 Context — 확장 대상 4개 블로그 현황

**Project**: 5000 — 중앙 컨트롤 파이프라인  
**Phase**: 43 — 나머지 4개 블로그로 확장 (축제/문화유산/맛집/코스)  
**Precondition**: 캠핑(travel-hugo)에서 검증된 패턴 수평 전개

## 기존 검증된 패턴 (Phase 40 완료)
1. **본문 프롬프트**: temperature 0.85, max_tokens 4800, ANTI-HALLUCINATION 강화
2. **타이틀 생성**: deepseek 모델로 교체 + temperature 0.6, max_tokens 60
3. **타이틀 예시**: 40개 확장 + travel2 문화유산 10개 확장
4. **템플릿 수정**: travel-hugo 비문 어순 교정, 긴 단어 임계값 12자로 상향

## 대상 블로그별 매핑

| 블로그ID | 주제 | 프롬프트ID | fetch_sources | 검증 우선순위 |
|---------|------|-----------|-------------|-------------|
| travel1-hugo | 축제 | travel1_festival | festival | 1순위 (리스크 낮음) |
| travel3-hugo | 맛집 | tour2_food | food | 2순위 (금지어 주의) |
| travel4-hugo | 코스 | tour3_course | course | 3순위 (단순 구조) |
| travel2-hugo | 문화유산 | travel2_heritage | heritage | 4순위 (복잡성 높음) |

## 검증 필요 항목

### 공통 검증
- [ ] 각 프롬프트에 temperature 0.85, max_tokens 4800 적용
- [ ] 타이틀 프롬프트 확장된 예시 적용 검증
- [ ] 본문-제목 일관성 검증 (특히 숫자 일치)

### 주제별 특화 검증
- **축제**: ANTI-HALLUCINATION 규칙 적용, 방문객 수/주차 정보 금지 확인
- **맛집**: 34개 금지어 적용, 메뉴명·가격 정확성 검증
- **코스**: 이동시간 정보 부 대체 전략 검토
- **문화유산**: 공통 맥락 연결 로직 검증

## 성공 기준
- 각 블로그당 dry-run 1회 성공
- title 생성률 90% 이상 (fallback 템플릿 활용 가능)
- 본문 생성 2,500자 이상 충족
- 제목-본문 숫자/키워드 일관성 100%

## 제약 조건
- Phase 40에서 변경된 본문/타이틀 로직 유지
- 발행/배포 호출 금지 (dry-run만)
- API 과금 최소화 (주제당 fetch 1회, 본문 생성은 검증 후에만)
- 기존 발행물 수정 금지