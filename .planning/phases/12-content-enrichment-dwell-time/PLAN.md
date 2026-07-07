# Phase 12: Content Enrichment & Dwell Time Optimization — PLAN

## Phase Goal
Increase travel blog content length by +50% and dwell time by +30% by leveraging unused API fields and adding new content sections.

## Task Breakdown

---

### Wave 1 — API Data Enhancement

#### Task 12.1: Expand camping API field mapping

**File:** `TAP/core/camping_data.py`

**Changes:**
1. Add new fields to the `results` list in `get_camping_data()`:
   ```python
   'operPdCl': item.get('operPdCl', ''),        # 운영기간
   'exprnProgrm': item.get('exprnProgrm', ''),  # 체험프로그램
   'siteBottomCl1': item.get('siteBottomCl1', ''),  # 바닥종류1
   'siteBottomCl2': item.get('siteBottomCl2', ''),  # 바닥종류2
   'eqpmnLendCl': item.get('eqpmnLendCl', ''),  # 장비대여
   'lctCl': item.get('lctCl', ''),              # 입지구분
   'themaEnvrnCl': item.get('themaEnvrnCl', ''),  # 테마환경
   ```

2. Update `_filter_by_theme_config()` FIELD_MAP to include new fields:
   ```python
   FIELD_MAP = {
       # ... existing mappings ...
       'oper_period': 'operPdCl',
       'experience': 'exprnProgrm',
       'site_ground': 'siteBottomCl1',
       'equipment_rental': 'eqpmnLendCl',
       'location_type': 'lctCl',
       'theme_env': 'themaEnvrnCl',
   }
   ```

**Verification:**
```bash
cd /Users/twinssn/Projects/TAP && python -c "
from core.camping_data import get_camping_data
result = get_camping_data(theme='글램핑')
if result and result.get('items'):
    item = result['items'][0]
    print('operPdCl:', item.get('operPdCl'))
    print('exprnProgrm:', item.get('exprnProgrm'))
    print('lctCl:', item.get('lctCl'))
    print('OK')
"
```

**Done when:** New fields are present in camping data output.

---

#### Task 12.2: Expand Durunubi API field mapping

**File:** `TAP/core/content_generator.py`

**Changes:**
1. In `_fetch_durunubi()`, add new fields to the item dict:
   ```python
   {
       # ... existing fields ...
       'crsDistance': item.get('crsDistance', ''),  # 거리
       'crsTime': item.get('crsTime', ''),          # 소요시간
       'crsDifficulty': item.get('crsDifficulty', ''),  # 난이도
       'crsLevel': item.get('crsLevel', ''),        # 난이도 레벨
   }
   ```

**Verification:**
```bash
cd /Users/twinssn/Projects/TAP && python -c "
from core.content_generator import ContentGenerator
gen = ContentGenerator()
# Test with durunubi theme
items, region, theme_data = gen.fetch_items({'source': 'durunubi_walk', 'theme': '두루누비'})
if items:
    item = items[0]
    print('crsDistance:', item.get('crsDistance'))
    print('crsTime:', item.get('crsTime'))
    print('crsDifficulty:', item.get('crsDifficulty'))
    print('OK')
"
```

**Done when:** Durunubi items include distance, time, and difficulty fields.

---

### Wave 2 — AI Prompt Expansion

#### Task 12.3: Update AI writer max_completion_tokens

**File:** `TAP/core/ai_writer.py`

**Changes:**
1. Change `max_tokens=5000` to `max_tokens=7000` in both `generate_full_content()` calls (camping and general sections).

**Verification:**
```bash
cd /Users/twinssn/Projects/TAP && python -c "
from core.ai_writer import AIWriter
import inspect
source = inspect.getsource(AIWriter.generate_full_content)
assert 'max_tokens=7000' in source, 'max_tokens not updated'
print('OK')
"
```

**Done when:** AI writer uses max_tokens=7000.

---

#### Task 12.4: Expand camping AI prompt with new fields

**File:** `TAP/core/ai_writer.py`

**Changes:**
1. In the camping section of `generate_full_content()`, add new fields to `places_info`:
   ```python
   # Add after existing field additions
   oper_period = item.get('operPdCl', '')
   if oper_period:
       info += f"\n   운영기간: {oper_period}"
   
   experience = item.get('exprnProgrm', '')
   if experience:
       info += f"\n   체험프로그램: {experience}"
   
   site_ground = item.get('siteBottomCl1', '')
   if site_ground:
       info += f"\n   사이트 바닥: {site_ground}"
   
   location_type = item.get('lctCl', '')
   if location_type:
       info += f"\n   입지: {location_type}"
   ```

2. Update the camping prompt structure to include new sections:
   ```
   [글 구조]
   h2: {region} {theme} 고르는 기준 (3~4가지 기준, 4~5문장)
   h3: 각 캠핑장명 (8~10문장: 위치·접근성, 시설, 운영기간, 체험프로그램, 애견동반 여부, 이용 팁)
   h2: {region} {theme} 한눈에 비교 (캠핑장명/운영기간/주요시설/입지/애견동반 여부)
   h2: {region} {theme} 방문 팁 (계절별 추천, 준비물, 예약 팁)
   h2: 마무리 (5~6문장, 캠핑장별 추천 여행자 유형)
   ```

**Verification:**
```bash
cd /Users/twinssn/Projects/TAP && python -c "
from core.ai_writer import AIWriter
import inspect
source = inspect.getsource(AIWriter.generate_full_content)
assert '운영기간' in source, 'operPdCl not in prompt'
assert '체험프로그램' in source, 'exprnProgrm not in prompt'
assert '방문 팁' in source, 'seasonal tips section not in prompt'
print('OK')
"
```

**Done when:** AI prompt includes new fields and seasonal tips section.

---

#### Task 12.5: Add general prompt sections (FAQ, linked courses)

**File:** `TAP/core/ai_writer.py`

**Changes:**
1. In the general (non-camping) prompt structure, add new sections:
   ```
   [글 구조]
   h2: {region} {theme} 고르는 기준 (3~4가지 기준, 4~5문장)
   h3: 각 장소별 (8~10문장: 위치 맥락 → 핵심 시설 → 가격대 → 운영시간 → 예약 팁)
   h2: {region} {theme} 한눈에 비교 (장소명/운영시간/가격대/핵심시설/접근성)
   h2: {region} {theme} 방문 팁 (계절별 추천, 준비물, 예약 팁)
   h2: {region} {theme} 자주 묻는 질문 (3~5개 FAQ)
   h2: 마무리 (5~7문장, 핵심 요약 + 추천 여행자 유형)
   ```

2. Add FAQ generation instruction:
   ```
   [FAQ 작성 지침]
   - 독자가 실제로 물어볼 법한 질문 3~5개를 선정하십시오
   - 각 질문은 구체적이어야 합니다 ("주차 공간이 있나요?" vs "편의시설은?")
   - 답변은 데이터에 있는 정보만 사용하십시오
   - 데이터에 없는 정보는 "방문 전 확인이 필요합니다"로 처리
   ```

**Verification:**
```bash
cd /Users/twinssn/Projects/TAP && python -c "
from core.ai_writer import AIWriter
import inspect
source = inspect.getsource(AIWriter.generate_full_content)
assert '자주 묻는 질문' in source, 'FAQ section not in prompt'
assert '방문 팁' in source, 'seasonal tips section not in prompt'
print('OK')
"
```

**Done when:** General prompt includes FAQ and seasonal tips sections.

---

### Wave 3 — Content Post-Processing

#### Task 12.6: Add Schema.org structured data generator

**File:** `TAP/core/schema_generator.py` (NEW)

**Content:**
```python
"""Schema.org structured data generator for travel blog posts"""

import json
from typing import List, Dict


def generate_travel_schema(
    title: str,
    region: str,
    theme: str,
    items: List[Dict],
    url: str = ""
) -> str:
    """Generate TravelAction + Place schema for campground list posts"""
    
    places = []
    for item in items:
        place = {
            "@type": "Place",
            "name": item.get("title", ""),
            "address": {
                "@type": "PostalAddress",
                "streetAddress": item.get("addr", "")
            }
        }
        if item.get("tel"):
            place["telephone"] = item["tel"]
        if item.get("mapx") and item.get("mapy"):
            place["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": item["mapy"],
                "longitude": item["mapx"]
            }
        places.append(place)
    
    schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"{region} {theme} 추천",
        "numberOfItems": len(items),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "item": place
            }
            for i, place in enumerate(places)
        ]
    }
    
    return json.dumps(schema, ensure_ascii=False, indent=2)


def generate_faq_schema(faqs: List[Dict]) -> str:
    """Generate FAQPage schema for FAQ sections"""
    
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": faq["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq["answer"]
                }
            }
            for faq in faqs
        ]
    }
    
    return json.dumps(schema, ensure_ascii=False, indent=2)
```

**Verification:**
```bash
cd /Users/twinssn/Projects/TAP && python -c "
from core.schema_generator import generate_travel_schema, generate_faq_schema
items = [{'title': '테스트', 'addr': '강원도'}]
schema = generate_travel_schema('테스트 글', '강원도', '글램핑', items)
assert '@type' in schema
print('OK')
"
```

**Done when:** Schema generator module exists and produces valid JSON-LD.

---

#### Task 12.7: Integrate schema into content pipeline

**File:** `TAP/core/content_generator.py`

**Changes:**
1. Add schema generation to `process_html()`:
   ```python
   from core.schema_generator import generate_travel_schema
   
   def process_html(self, content, items, theme, region="", url=""):
       # ... existing code ...
       
       # Add Schema.org structured data
       schema = generate_travel_schema(
           title=f"{region} {theme} 추천",
           region=region,
           theme=theme,
           items=items,
           url=url
       )
       schema_tag = f'<script type="application/ld+json">\n{schema}\n</script>'
       
       # Insert before </head>
       content = content.replace('</head>', f'{schema_tag}\n</head>')
       
       return content
   ```

**Verification:**
```bash
cd /Users/twinssn/Projects/TAP && python -c "
from core.content_generator import ContentGenerator
import inspect
source = inspect.getsource(ContentGenerator.process_html)
assert 'generate_travel_schema' in source, 'Schema not integrated'
print('OK')
"
```

**Done when:** Content pipeline includes Schema.org structured data.

---

#### Task 12.8: Add FAQ extraction from AI output

**File:** `TAP/core/ai_writer.py`

**Changes:**
1. Add FAQ extraction function:
   ```python
   def extract_faqs(self, content: str) -> list:
       """Extract FAQ section from generated content"""
       faqs = []
       in_faq = False
       current_q = None
       
       for line in content.split('\n'):
           if '자주 묻는 질문' in line:
               in_faq = True
               continue
           if in_faq:
               if line.startswith('<h3>') or line.startswith('**Q'):
                   # Extract question
                   q = line.replace('<h3>', '').replace('</h3>', '').strip()
                   q = q.replace('**Q', '').replace('**:', '').strip()
                   if q:
                       current_q = {'question': q, 'answer': ''}
               elif current_q and line.startswith('<p>'):
                   # Extract answer
                   a = line.replace('<p>', '').replace('</p>', '').strip()
                   if a:
                       current_q['answer'] = a
                       faqs.append(current_q)
                       current_q = None
       
       return faqs[:5]  # Max 5 FAQs
   ```

2. Use extracted FAQs for Schema.org:
   ```python
   # In generate_full_content()
   content = self._clean_content(response.choices[0].message.content)
   faqs = self.extract_faqs(content)
   return content, faqs  # Return both content and FAQs
   ```

**Verification:**
```bash
cd /Users/twinssn/Projects/TAP && python -c "
from core.ai_writer import AIWriter
writer = AIWriter()
test_content = '''
<h2>자주 묻는 질문</h2>
<h3>Q: 주차 공간이 있나요?</h3>
<p>네, 각 캠핑장마다 주차장이 마련되어 있습니다.</p>
'''
faqs = writer.extract_faqs(test_content)
assert len(faqs) > 0, 'FAQ extraction failed'
print('OK')
"
```

**Done when:** AI writer can extract FAQs from generated content.

---

### Wave 4 — Verification

#### Task 12.9: Build and verify all 5 Hugo blogs

**Action:** Hugo build each blog and check for errors.

```bash
for blog in travel-hugo travel1-hugo travel2-hugo travel3-hugo travel4-hugo; do
  echo "=== $blog ==="
  cd /Users/twinssn/Projects/TAP/$blog && hugo --gc --minify 2>&1 | tail -2
done
```

**Post-build checks:**
1. Open one blog in Hugo server mode
2. Verify content length increased (word count)
3. Verify new sections appear (FAQ, seasonal tips)
4. Verify Schema.org structured data in page source
5. Verify ad markers remain functional

**Done when:** All 5 blogs build successfully, content enrichment verified.

---

#### Task 12.10: Content quality validation

**Action:** Generate sample posts and validate quality.

```bash
cd /Users/twinssn/Projects/TAP && python -c "
from core.camping_data import get_camping_data
from core.ai_writer import load_ai_writer

# Get sample data
data = get_camping_data(theme='글램핑')
if data and data.get('items'):
    writer = load_ai_writer()
    if writer:
        content, faqs = writer.generate_full_content(
            items=data['items'][:3],
            theme=data['theme'],
            region=data['display_region'],
            angle=data.get('angle', ''),
            category='캠핑'
        )
        
        # Check length
        print(f'Content length: {len(content)} chars')
        print(f'FAQs extracted: {len(faqs)}')
        
        # Check sections
        assert '방문 팁' in content or '방문정보' in content, 'Seasonal tips missing'
        print('Quality check passed')
"
```

**Done when:** Sample content meets quality criteria (length, sections, FAQs).

---

## Dependency Graph

```
Wave 1 (API Data)           Wave 2 (AI Prompt)         Wave 3 (Post-Processing)    Wave 4 (Verification)
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ Task 12.1: Camping  │    │ Task 12.3: max_tokens│    │ Task 12.6: Schema   │    │ Task 12.9: Build    │
│ Task 12.2: Durunubi │────│ Task 12.4: Camping   │────│ Task 12.7: Pipeline │────│ Task 12.10: Quality │
└─────────────────────┘    │ Task 12.5: General   │    │ Task 12.8: FAQ      │    └─────────────────────┘
                           └─────────────────────┘    └─────────────────────┘
```

- Wave 1 tasks are parallel (different APIs)
- Wave 2 tasks depend on Wave 1 (need new fields in data)
- Wave 3 tasks depend on Wave 2 (need updated prompts)
- Wave 4 depends on all previous waves

## Verification Strategy

| Task | Verification Method |
|------|-------------------|
| 12.1 | `python -c "from core.camping_data import get_camping_data; ..."` |
| 12.2 | `python -c "from core.content_generator import ContentGenerator; ..."` |
| 12.3 | `grep 'max_tokens=7000' core/ai_writer.py` |
| 12.4 | `grep '운영기간' core/ai_writer.py` |
| 12.5 | `grep '자주 묻는 질문' core/ai_writer.py` |
| 12.6 | `python -c "from core.schema_generator import generate_travel_schema; ..."` |
| 12.7 | `grep 'generate_travel_schema' core/content_generator.py` |
| 12.8 | `python -c "from core.ai_writer import AIWriter; ..."` |
| 12.9 | Hugo build succeeds for all 5 blogs |
| 12.10 | Sample content meets quality criteria |

## Rollback Strategy

| Change | Rollback |
|--------|----------|
| camping_data.py fields | `git checkout HEAD -- core/camping_data.py` |
| content_generator.py fields | `git checkout HEAD -- core/content_generator.py` |
| ai_writer.py max_tokens | `git checkout HEAD -- core/ai_writer.py` |
| ai_writer.py prompts | `git checkout HEAD -- core/ai_writer.py` |
| schema_generator.py | `rm -f core/schema_generator.py` |
| content_generator.py schema | `git checkout HEAD -- core/content_generator.py` |

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| AI output quality degrades with longer content | Medium | High | Limit max_tokens to 7000; add quality checks |
| API field data is sparse/incomplete | High | Medium | Graceful fallback; only include if data exists |
| FAQ section feels repetitive | Medium | Low | Generate unique FAQs per post; avoid generic questions |
| Schema.org validation errors | Low | Medium | Test with Google Rich Results Test |
| Hugo build time increases | Low | Low | Monitor build time; optimize if >10s |
| Content too long for ad placement | Medium | Medium | Verify ad markers remain functional |

## Execution Order

```yaml
order:
  - task_12.1: "Expand camping API field mapping"
  - task_12.2: "Expand Durunubi API field mapping"
  - task_12.3: "Update AI writer max_completion_tokens"
  - task_12.4: "Expand camping AI prompt with new fields"
  - task_12.5: "Add general prompt sections (FAQ, linked courses)"
  - task_12.6: "Add Schema.org structured data generator"
  - task_12.7: "Integrate schema into content pipeline"
  - task_12.8: "Add FAQ extraction from AI output"
  - task_12.9: "Build and verify all 5 Hugo blogs"
  - task_12.10: "Content quality validation"

parallel_groups:
  wave_1: [task_12.1, task_12.2]
  wave_2: [task_12.3, task_12.4, task_12.5]
  wave_3: [task_12.6, task_12.7, task_12.8]
  wave_4: [task_12.9, task_12.10]
```

Total tasks: 10 | Waves: 4 | New files: 1 | Modified files: 4
