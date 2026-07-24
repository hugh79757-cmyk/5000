# Phase 43 Plan — 나머지 4개 블로그로 확장

**Phase**: 43 — 확장 대상 블로그: 축제/문화유산/맛집/코스  
**Strategy**: 캠핑에서 검증된 프롬프트·타이틀 패턴을 주제별로 적용 → 리스크 순차 검증

---

## 43-01: 축제 블로그 (travel1-hugo) 프롬프트 검증

**Task**: Phase 40에서 검증된 옵션을 travel1_festival 프롬프트에 적용

### Deliverables:
- [ ] config/prompts.yaml의 travel1_festival 프롬프트에 temperature 0.85, max_tokens 4800 적용
- [ ] 타이틀 프롬프트 확장된 예시 적용 (이미 적용됨)
- [ ] dry-run 검증: 1건 생성 → 본문 길이·제품 일관성 확인
- [ ] 검증 기준: 2,500자 이상, 제목-본문 일관성 OK

**Acceptance Criteria**:
- ✅ 본문 생성 성공 (2,500~3,500자)
- ✅ 타이틀 생성 성공 (25~35자, 지역명 포함)
- ✅ 제목-본문 숫자 일치
- ✅ ANTI-HALLUCINATION 규칙 위반 없음

<verify>
<automated>python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_festival
from pipelines.travel.writer import generate_content
d = fetch_festival()
r = generate_content(d, blog_id='travel1-hugo')
print(f'TITLE: {r.get(\"title\")}')
print(f'BODY_LENGTH: {len(r.get(\"body_md\", \"\"))}')
print(f'ITEMS: {len(r.get(\"items\", []))}')
"</automated>
</verify>

<done>
- ✅ Content length: 2,500-3,500 characters
- ✅ Title generated successfully (25-35 chars)
- ✅ Title-body consistency achieved
- ✅ No ANTI-HALLUCINATION violations
</done>

---

## 43-02: 맛집 블로그 (travel3-hugo) 프롬프트 검증

**Task**: tour2_food 프롬프트에 옵션 적용 + 금지어 처리 검증

### Deliverables:
- [ ] config/prompts.yaml의 tour2_food 프롬프트에 temperature 0.85, max_tokens 4800 적용
- [ ] ABSOLUTE BAN 목록 재검토 (34개 금지어)
- [ ] dry-run 검증: 1건 생성 → 금지어 사용 여부 확인
- [ ] 데이터 필드 매핑 검증 (메뉴명·가격 정확성)

**Acceptance Criteria**:
- ✅ 금지어 사용 0건
- ✅ TITLE-BODY CONSISTENCY (제목 숫자 = 본문 소개 수)
- ✅ 가격 정보 정확성 ( "~만원대" 없음)
- ✅ 메뉴명 데이터 활용 정상

<verify>
<automated>python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_food
from pipelines.travel.writer import generate_content
d = fetch_food()
r = generate_content(d, blog_id='travel3-hugo')
title = r.get('title', '')
body = r.get('body_md', '')
# Check forbidden words
forbidden_words = ['추천드립니다', '인기가 많습니다', '맛있는']
violations = [word for word in forbidden_words if word in body]
print(f'TITLE: {title}')
print(f'BODY_LENGTH: {len(body)}')
print(f'TITLE_BODY_NUMBERS_MATCH: {str(title).split(\" \")[-1] == str(len([h for h in body.split(\"##\") if \"식당\" in h]))}')
print(f'FORBIDDEN_VIOLATIONS: {violations}')
print(f'PRICE_FORMAT_OK: \"만원대\" not in body')
"</automated>
</verify>

<done>
- ✅ Forbidden words violations: 0
- ✅ Title-body consistency achieved
- ✅ Price format correct (no \"만원대\")
- ✅ Menu names accurately used
</done>

---

## 43-03: 여행코스 블로그 (travel4-hugo) 프롬프트 검증

**Task**: tour3_course 프롬프트에 옵션 적용 + 이동시간 정보 부 대처

### Deliverables:
- [ ] config/prompts.yaml의 tour3_course 프롬프트에 temperature 0.85, max_tokens 4800 적용
- [ ] 이동시간 정보 부족 시 대체 전략 검토 (ex: "교통 정보는 공식 사이트 참조")
- [ ] dry-run 검증: 1건 생성 → 코스 설명 연속성 확인
- [ ] 코스명 정제 로직 검증

**Acceptance Criteria**:
- ✅ 이동시간 생성 0건 (규칙 준수)
- ✅ 코스명이 간결한 키워드 형태 (H3)
- ✅ 장소별 최소 6문장 서술
- ✅ 본문 2,500자 이상 충족

<verify>
<automated>python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_course
from pipelines.travel.writer import generate_content
d = fetch_course()
r = generate_content(d, blog_id='travel4-hugo')
title = r.get('title', '')
body = r.get('body_md', '')
# Check for specific movement time violations (not just character presence)
    import re
    movement_patterns = [
        r'도보\s*\d+',      # "도보 15"
        r'차로\s*\d+',      # "차로 30"  
        r'걸어\s*\d+',      # "걸어 20"
        r'\d+\s*분\s*(걸어|걸리|소요)',  # "30분 걸려", "소요 30분"
        r'\d+\s*시간\s*(걸어|걸리|소요)',  # "1시간 걸려"
        r'\d+\s*분',        # "30분" (standalone time expressions)
        r'\d+\s*시간',      # "2시간" (standalone time expressions)
    ]
    
    movement_violations = []
    for pattern in movement_patterns:
        if re.search(pattern, body):
            movement_violations.append(pattern)
h3_count = len([h for h in body.split('###') if len(h.strip()) > 20])
print(f'TITLE: {title}')
print(f'BODY_LENGTH: {len(body)}')
print(f'MOVEMENT_VIOLATIONS: {movement_violations}')
print(f'H3_SECTIONS: {h3_count}')
print(f'H3_MIN_6_SENTENCES: {all(len(h.split(\".\")) >= 6 for h in body.split(\"###\") if len(h.strip()) > 20)}')
"</automated>
</verify>

<done>
- ✅ Movement time violations: 0
- ✅ H3 sections (>=6 sentences): {h3_count}
- ✅ Body length: 2,500+ characters
- ✅ Course names properly simplified
</done>

---

## 43-04: 문화유산 블로그 (travel2-hugo) 프롬프트 검증

**Task**: travel2_heritage 프롬프트에 옵션 적용 + 공통 맥락 연결 검증

### Deliverables:
- [ ] config/prompts.yaml의 travel2_heritage 프롬프트에 temperature 0.85, max_tokens 4800 적용
- [ ] 공통 맥락 연결 로직 검증 (시대·종목·양식 기반)
- [ ] dry-run 검증: 3곳 문화유산의 맥락 연결성 확인
- [ ] H3 구조와 H2 일관성 검증

**Acceptance Criteria**:
- ✅ 3곳의 공통 맥락이 자연스럽게 연결
- ✅ 단순 나열이 아닌 비교·대조 서술
- ✅ H2 3~4개 구조 준수
- ✅ 역사적 사실 정확성 (overview 기반)

<verify>
<automated>python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_heritage
from pipelines.travel.writer import generate_content
d = fetch_heritage()
r = generate_content(d, blog_id='travel2-hugo')
title = r.get('title', '')
body = r.get('body_md', '')
# Check context connections
h2_sections = len([h for h in body.split('##') if len(h.strip()) > 30])
h3_sections = len([h for h in body.split('###') if len(h.strip()) > 20])
connection_words = ['비교', '대조', '동일', '공통', '반면', '하지만']
connection_count = sum(1 for word in connection_words if word in body)
print(f'TITLE: {title}')
print(f'BODY_LENGTH: {len(body)}')
print(f'CONNECTION_WORDS_COUNT: {connection_count}')
print(f'H2_STRUCTURE: {h2_sections} (target: 3-4)')
print(f'H3_STRUCTURE: {h3_sections} (target: 3)')
print(f'CONTEXT_CONNECTION_OK: {connection_count > 0}')
"</automated>
</verify>

<done>
- ✅ Context connections: {connection_count} words
- ✅ H2 structure: {h2_sections} sections (target: 3-4)
- ✅ H3 structure: {h3_sections} sections (target: 3)
- ✅ Historical facts accurate
</done>

---

## 43-05: 전수 검증 및 최적화

**Task**: 4개 블로그 최종 검증 → 문제 발생 시 개선

### Deliverables:
- [ ] 모든 블로그 dry-run 결과 통합 검증
- [ ] 생성된 타이틀 품질 평가 (클릭 유도성)
- [ ] 본문 생성 실패 시 프롬프트 미세 조정
- [ ] 성공률 통계 작성 (성공/실패/개선 필요)

**Acceptance Criteria**:
- ✅ 4개 블로그 모두 dry-run 성공
- ✅ 타이틀 생성 성공률 90% 이상
- ✅ 본문 길이 기준 100% 충족
- ✅ 제목-본문 일관성 100%

<verify>
<automated>python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_festival, fetch_heritage, fetch_food, fetch_course
from pipelines.travel.writer import generate_content

blogs = [
    ('travel1-hugo', fetch_festival()),
    ('travel3-hugo', fetch_food()),
    ('travel4-hugo', fetch_course()),
    ('travel2-hugo', fetch_heritage())
]

results = {}
for blog_id, data in blogs:
    try:
        r = generate_content(data, blog_id=blog_id)
        title_ok = len(r.get('title', '')) >= 20
        body_ok = len(r.get('body_md', '')) >= 2500
        results[blog_id] = {'title': title_ok, 'body': body_ok, 'success': title_ok and body_ok}
    except Exception as e:
        results[blog_id] = {'success': False, 'error': str(e)}

total_success = sum(1 for r in results.values() if r['success'])
success_rate = total_success / len(blogs) * 100

print(f'TOTAL_SUCCESS_RATE: {success_rate}%')
print(f'INDIVIDUAL_RESULTS:')
for blog_id, result in results.items():
    status = 'SUCCESS' if result['success'] else f'FAILED: {result.get(\"error\", \"Unknown\")}'
    print(f'  {blog_id}: {status}')
print(f'TITLE_LENGTHS: {len(r[\"title\"]) for r in [generate_content(data, blog_id=blog_id) for blog_id, data in blogs]}')
print(f'BODY_LENGTHS: {len(r[\"body_md\"]) for r in [generate_content(data, blog_id=blog_id) for blog_id, data in blogs]}')
"</automated>
</verify>

<done>
- ✅ Total success rate: {success_rate}% (target: 90%+)
- ✅ All blogs: individual success checks passed
- ✅ Title lengths: all within acceptable range
- ✅ Body lengths: all 2,500+ characters
</done>

---

## Execution Strategy

**순차 진행**: travel1 → travel3 → travel4 → travel2 (리스크 낮은 순서)  
**API 과금 최소화**: 각 task당 dry-run 1회로 제한  
**변경 관리**: 기존 프롬프트 백업 후 점진적 적용  

---

## Key Links

```yaml
key_links:
  - from: config/prompts.yaml
    to: shared/ai_writer.py
    via: "temperature=0.85, max_tokens=4800 settings for content generation"
  - from: models.yaml  
    to: deepseek title generation
    via: "temperature=0.6, max_tokens=60 settings"
  - from: Phase 40 verified patterns
    to: Phase 43 prompt applications
    via: "ANTI-HALLUCINATION rules, content length validation"
  - from: config/blogs.d/tap.yaml
    to: 4 target blog pipelines
    via: "blog_id → fetch_sources → prompt mappings"
```

## Pattern References

- **Prompt Optimization**: References `shared/prompt_optimizer.py` from Phase 40 for temperature/token settings
- **Content Validation**: References `shared/content_validator.py` pattern for ANTI-HALLUCINATION checks
- **Title Generation**: References `shared/title_generator.py` improvements with deepseek model
- **Blog Pipeline**: References `pipelines/travel/writer.py` for content generation workflow

## Verification

**gsd-plan-checker** 검증 항목:
- [ ] 각 task가 명확한 deliverables와 acceptance criteria를 가짐
- [ ] 프롬프트 수정이 기존 기능을 파괴하지 않음
- [ ] API 과금 비용이 합리적임
- [ ] 실패 시 롤백 가능성이 명확함

---
**Plan 생성**: 2026-07-24  
**상태**: Ready for execution after validation fixes