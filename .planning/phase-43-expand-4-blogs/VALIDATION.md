# Phase 43 Validation Plan

**Phase**: 43 — 나머지 4개 블로그로 확장  
**Validation Strategy**: Automated dry-run testing for each blog type → success rate validation

---

## Validation Architecture

### Automated Verification Commands

#### Title Generation Validation
```bash
# Test title generation for all 4 blog types
python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_festival, fetch_heritage, fetch_food, fetch_course
from pipelines.travel.writer import generate_content

# Test each blog type
test_cases = [
    ('travel1-hugo', fetch_festival(), '축제'),
    ('travel3-hugo', fetch_food(), '맛집'), 
    ('travel4-hugo', fetch_course(), '코스'),
    ('travel2-hugo', fetch_heritage(), '문화유산')
]

results = {}
for blog_id, data, theme in test_cases:
    try:
        r = generate_content(data, blog_id=blog_id)
        title = r.get('title', '')
        title_ok = len(title) >= 20 and len(title) <= 50
        results[blog_id] = {'title': title, 'valid': title_ok, 'theme': theme}
    except Exception as e:
        results[blog_id] = {'error': str(e)}

print('TITLE GENERATION VALIDATION:')
for blog_id, result in results.items():
    status = 'PASS' if 'valid' in result else f'FAIL: {result.get(\"error\", \"Unknown\")}'
    print(f'  {blog_id} ({result.get(\"theme\")}): {status} - {result.get(\"title\", \"N/A\")}')
```

#### Content Generation Validation
```bash
# Test content generation with length and quality checks
python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/projects/5000')
from pipelines.travel.fetcher import fetch_festival, fetch_heritage, fetch_food, fetch_course
from pipelines.travel.writer import generate_content

test_cases = [
    ('travel1-hugo', fetch_festival()),
    ('travel3-hugo', fetch_food()),
    ('travel4-hugo', fetch_course()),
    ('travel2-hugo', fetch_heritage())
]

content_results = {}
for blog_id, data in test_cases:
    try:
        r = generate_content(data, blog_id=blog_id)
        body = r.get('body_md', '')
        length_ok = len(body) >= 2500
        # Check for hallucination violations
        hallucination_keywords = ['바랍니다', '되시길', '있으시', '마무리하며', '만끽해 보세요']
        hallucination_violations = [kw for kw in hallucination_keywords if kw in body]
        
        content_results[blog_id] = {
            'length': len(body),
            'length_ok': length_ok,
            'hallucinations': hallucination_violations,
            'success': length_ok and len(hallucination_violations) == 0
        }
    except Exception as e:
        content_results[blog_id] = {'error': str(e)}

print('CONTENT GENERATION VALIDATION:')
for blog_id, result in content_results.items():
    if 'error' in result:
        print(f'  {blog_id}: FAIL - {result[\"error\"]}')
    else:
        status = 'PASS' if result['success'] else 'FAIL'
        print(f'  {blog_id}: {status} - Length: {result[\"length\"]}, Hallucinations: {len(result[\"hallucinations\"])}')
```

#### Blog-Specific Validation

##### Festival Blog (travel1-hugo)
```bash
# Check festival-specific requirements
python3 -c "
from pipelines.travel.fetcher import fetch_festival
from pipelines.travel.writer import generate_content

d = fetch_festival()
r = generate_content(d, blog_id='travel1-hugo')
body = r.get('body_md', '')

# Check for visitor numbers (forbidden)
visitor_terms = ['만 명', '명이', '명의', '30만', 'N만']
visitor_violations = [term for term in visitor_terms if term in body]

# Check for parking numbers (forbidden)  
parking_terms = ['대 수용', 'N대', '200대']
parking_violations = [term for term in parking_terms if term in body]

print(f'FESTIVAL VALIDATION:')
print(f'  Visitor number violations: {len(visitor_violations)}')
print(f'  Parking number violations: {len(parking_violations)}')
print(f'  H2 sections: {len([h for h in body.split(\"##\") if len(h.strip()) > 20])}')
"
```

##### Food Blog (travel3-hugo)
```bash
# Check food-specific requirements
python3 -c "
from pipelines.travel.fetcher import fetch_food
from pipelines.travel.writer import generate_content

d = fetch_food()
r = generate_content(d, blog_id='travel3-hugo')
title = r.get('title', '')
body = r.get('body_md', '')

# Check forbidden words
forbidden_words = ['추천드립니다', '인기가 많습니다', '맛있는', '사랑해요']
violations = [word for word in forbidden_words if word in body]

# Check price format
price_ok = '만원대' not in body

# Check title-body consistency
title_num = ''.join(filter(str.isdigit, title.split()[-1]))
body_count = len([h for h in body.split('###') if '식당' in h])
consistency_ok = title_num == str(body_count) if title_num else True

print(f'FOOD VALIDATION:')
print(f'  Forbidden words violations: {len(violations)}')
print(f'  Price format OK (no 만원대): {price_ok}')
print(f'  Title-body consistency: {consistency_ok}')
"
```

##### Course Blog (travel4-hugo)
```bash
# Check course-specific requirements
python3 -c "
from pipelines.travel.fetcher import fetch_course
from pipelines.travel.writer import generate_content

d = fetch_course()
r = generate_content(d, blog_id='travel4-hugo')
body = r.get('body_md', '')

# Check for movement time violations
movement_terms = ['차로', '도보', '분', '시간']
movement_violations = [term for term in movement_terms if term in body]

# Check H3 section structure
h3_sections = [h for h in body.split('###') if len(h.strip()) > 20]
h3_min_sentences = all(len(h.split('.')) >= 6 for h in h3_sections)

print(f'COURSE VALIDATION:')
print(f'  Movement time violations: {len(movement_violations)}')
print(f'  H3 sections (>=6 sentences): {len([s for s in h3_sections if len(s.split('.')) >= 6])}/{len(h3_sections)}')
print(f'  Body length: {len(body)} characters')
"
```

##### Heritage Blog (travel2-hugo)
```bash
# Check heritage-specific requirements
python3 -c "
from pipelines.travel.fetcher import fetch_heritage
from pipelines.travel.writer import generate_content

d = fetch_heritage()
r = generate_content(d, blog_id='travel2-hugo')
body = r.get('body_md', '')

# Check context connections
connection_words = ['비교', '대조', '동일', '공통', '반면', '하지만', '또한']
connection_count = sum(1 for word in connection_words if word in body)

# Check structure
h2_sections = len([h for h in body.split('##') if len(h.strip()) > 30])
h3_sections = len([h for h in body.split('###') if len(h.strip()) > 20])

print(f'HERITAGE VALIDATION:')
print(f'  Context connection words: {connection_count}')
print(f'  H2 structure: {h2_sections} sections (target: 3-4)')
print(f'  H3 structure: {h3_sections} sections (target: 3)')
print(f'  Body length: {len(body)} characters')
"
```

### Validation Scripts

#### 1. Consistency Checker
```python
# title_consistency_checker.py
def check_title_body_consistency(title, body, blog_type):
    if blog_type in ['travel3-hugo']:  # Food blog
        title_num = ''.join(filter(str.isdigit, title.split()[-1]))
        body_count = len([h for h in body.split('###') if '식당' in h])
        return str(title_num) == str(body_count)
    return True  # Other blogs don't have strict number matching
```

#### 2. Content Length Validator
```python
# content_length_validator.py
def validate_content_length(body, blog_type):
    min_length = 2500
    max_length = 3500
    actual_length = len(body)
    return min_length <= actual_length <= max_length
```

#### 3. Forbidden Words Detector
```python
# forbidden_words_detector.py
def check_forbidden_words(body, blog_type):
    forbidden_lists = {
        'travel3-hugo': ['추천드립니다', '인기가 많습니다', '맛있는', '사랑해요', '최고의', '강력 추천'],
        'travel1-hugo': ['만 명', '명이', '명의', '30만', 'N만', '200대', '대 수용'],
        'travel4-hugo': ['차로', '도보', '분', '시간', '만원대'],
        'travel2-hugo': ['바랍니다', '되시길', '있으시', '마무리하며', '만끽해 보세요']
    }
    
    forbidden = forbidden_lists.get(blog_type, [])
    violations = [word for word in forbidden if word in body]
    return violations
```

## Success Metrics

### Acceptance Criteria
- **Overall Success Rate**: 90% or higher (4/5 blogs minimum)
- **Title Generation**: All blogs generate titles between 20-50 characters
- **Content Length**: All blogs generate content between 2,500-3,500 characters
- **Consistency**: Title-body consistency for all blogs
- **No Violations**: Zero hallucination or forbidden word violations

### Validation Report Template
```markdown
# Phase 43 Validation Report

## Summary
- **Test Date**: [Date]
- **Total Blogs Tested**: 4
- **Success Rate**: [Percentage]%
- **Status**: [PASS/FAIL]

## Individual Results
### travel1-hugo (Festival)
- **Title Generation**: [PASS/FAIL]
- **Content Length**: [PASS/FAIL] 
- **Violations**: [Count]
- **Notes**: [Any issues]

### travel3-hugo (Food)
- **Title Generation**: [PASS/FAIL]
- **Content Length**: [PASS/FAIL]
- **Violations**: [Count]
- **Consistency**: [PASS/FAIL]
- **Notes**: [Any issues]

### travel4-hugo (Course)
- **Title Generation**: [PASS/FAIL]
- **Content Length**: [PASS/FAIL]
- **Movement Time Violations**: [Count]
- **Notes**: [Any issues]

### travel2-hugo (Heritage)
- **Title Generation**: [PASS/FAIL]
- **Content Length**: [PASS/FAIL]
- **Context Connections**: [Count]
- **Structure**: [PASS/FAIL]
- **Notes**: [Any issues]

## Recommendations
- [List any prompt adjustments needed]
- [Note any recurring issues]
- [Suggest improvements for next phase]
```

## Error Handling

### Common Failure Modes
1. **Content Too Short**: Adjust max_tokens or relax length requirements
2. **Hallucination Violations**: Strengthen ANTI-HALLUCINATION rules
3. **Structure Issues**: Revise prompt template formatting
4. **API Failures**: Implement retry logic with exponential backoff

### Rollback Strategy
- **Failed Prompt Changes**: Revert to previous prompt configuration
- **API Rate Limits**: Switch to offline mode with cached data
- **Persistent Failures**: Fall back to simplified template generation

---
**Validation Plan Created**: 2026-07-24  
**Status**: Ready for Phase 43 execution