---
phase: 63-content-integrity-refinement
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/c01_c08_reverse_validation.py
  - scripts/c01_c08_validation_data/laptop_c09_samples.json
  - scripts/c01_c08_validation_data/health_c09_samples.json
  - scripts/c01_c08_validation_data/health_hypotension_audit.json
autonomous: true
requirements: []
must_haves:
  truths:
    - "C07 패턴 현재 정상 작동: dead_links 53건 + dongnam 44건 = 97건 전부 탐지, 미매칭 0건"
    - "C09 규칙 역검증: laptop-hugo 16건 + health-hugo 11건 = 27건 문자열화 탐지, 정상 YAML 배열 오탐 0"
    - "62-01 재검증 표: C04 16/16, C07 97/97, C09 27/27, ETAP 영문 오탐 0, 정상글 오탐 0"
    - "health 저혈압 글: 파일 직선따옴표 + 프론트매터 정상 종료 + 라이브 HTTP 200 본문 존재 = 배포완료 판정"
  artifacts:
    - path: "scripts/c01_c08_reverse_validation.py"
      provides: "C09 검사 함수 추가 + 62-01 재검증 실행"
      min_lines: 700
    - path: "scripts/c01_c08_validation_data/laptop_c09_samples.json"
      provides: "laptop-hugo C09 문자열화 샘플 데이터"
      min_lines: 10
    - path: "scripts/c01_c08_validation_data/health_c09_samples.json"
      provides: "health-hugo C09 문자열화 샘플 데이터"
      min_lines: 10
    - path: "scripts/c01_c08_validation_data/health_hypotension_audit.json"
      provides: "저혈압 글 진본 확인 결과"
      min_lines: 10
  key_links:
    - from: "c01_c08_reverse_validation.py"
      to: "ops_dashboard/db.py C09 INSERT 준비"
      via: "C09 check_c09_body() 함수 정의"
      pattern: "check_c09"

---

<objective>
## 목표

Phase 62에서 C01~C08이 INSERT된 상태에서:
1. **C07 잔류 수정 확인**: 현재 C07_SLUG_PATTERN이 `href="..."` + `href=\"...\"` 모두 정상 매칭 중임을 데이터로 확인 (미매칭 0건)
2. **C09 규칙 정의 추가**: categories/tags가 `"['추천']"`처럼 문자열화된 리스트를 탐지하는 규칙을 c01_c08_reverse_validation.py에 추가
3. **62-01 재검증 실행**: C04 + C07(수정 후) + C09 + ETAP 영문 오탐 + 정상글 오탐을 표로 정리
4. **health 저혈압 글 진본 확인**: 파일 vs 라이브 대조로 배포누락 vs 재생성필요 판정

**컨텍스트**: Phase 62 CONTEXT.md §규칙 정의 (C01~C08), Phase 62 62-01 역검증 스크립트

Purpose: 62-02 INSERT 승인 전 마지막 검증. C07 패턴 수정 완료 + C09 규칙 준비 + 건강 저혈압 글 판정.
Output: 수정된 역검증 스크립트 + 재검증 결과 표 + 저혈압 글 판정 보고서
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/references/planner-antipatterns.md
</execution_context>

<context>
@/Users/twinssn/Projects/5000/.planning/phases/phase-62-content-leak-prevention/CONTEXT.md
@/Users/twinssn/Projects/5000/scripts/c01_c08_reverse_validation.py
@/Users/twinssn/Projects/5000/ops_dashboard/db.py
@/Users/twinssn/Projects/5000/ops_dashboard/checks/content_integrity.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: C07 패턴 현황 확인 + C09 규칙 추가</name>
  <files>scripts/c01_c08_reverse_validation.py, scripts/c01_c08_validation_data/laptop_c09_samples.json, scripts/c01_c08_validation_data/health_c09_samples.json</files>
  <action>
## Part A: C07 패턴 현황 확인 (수정 완료 검증)

현재 C07_SLUG_PATTERN:
```python
C07_SLUG_PATTERN = re.compile(
    r'href=(?:"|\\")https://([\w-]+)\.informationhot\.kr/posts/(.+?)/(?:"|\\")'
)
```

**현황 확인 방법**:
```bash
python3 -c "
import json, os, re
C07 = re.compile(r'href=(?:\"|\\\\")https://([\w-]+)\.informationhot\.kr/posts/(.+?)/(?:\"|\\\\")')
dead = json.load(open('scripts/c01_c08_validation_data/dead_links.json'))
dn = json.load(open('scripts/c01_c08_validation_data/dongnam_npmb.json'))
files = set([d['source_file'] for d in dead] + [d['source_file'] for d in dn])
missing = [f for f in files if not os.path.exists(f)]
print(f'검사 파일: {len(files)}개, 부재: {len(missing)}개')
# 각 파일에서 C07 패턴으로 expected_slug 탐지 확인
unmatched = 0
for f in files:
    if not os.path.exists(f): continue
    content = open(f, encoding='utf-8').read()
    slugs_found = set(m[1] for m in C07.findall(content))
    # expected_slug (dead_links: cross_sell_target_slug, dongnam: target_slug)
for d in dead:
    if d['cross_sell_target_slug'] not in slugs_found: unmatched += 1
for d in dn:
    if d['target_slug'] not in slugs_found: unmatched += 1
print(f'C07 미매칭: {unmatched}건')
"
```

**기대 결과**: 미매칭 0건 → C07 패턴 수정 완료 확인. 현재 패턴은 `href="..."`(일반)과 `href=\"...\"`(이스케이프) 모두 처리함.

## Part B: C09 규칙 추가

C09 — categories/tags 문자열화 탐지. YAML 값이 `["추천"]`(list)가 아닌 `"['추천']"`(str)로 저장된 경우.

**c01_c08_reverse_validation.py에 추가**:

```python
# ── C09: categories/tags 문자열화 탐지 ──────────────────────────────────
# YAML 배열이 문자열화된 형태: categories: "['추천']" → type=str, 값이 "[...]" 형태
# 정상: categories: ["추천"] → type=list
# Hugo range .Params.categories 실패 원인 → severity=CRITICAL, 배포차단

C09_STR_LIST_PATTERN = re.compile(r'^\[\s*[\'"].*[\'"]\s*\]$')  # "['...']" 또는 '["..."]' 형태

def check_c09_frontmatter(fm_dict: dict) -> tuple[bool, str]:
    """C09: categories 또는 tags가 문자열화된 리스트이면 fail.
    정상 YAML 배열(type=list)은 통과, "['추천']" 형태(type=str, [...] 패턴)는 fail."""
    issues = []
    for field in ('categories', 'tags'):
        val = fm_dict.get(field)
        if val is None:
            continue  # 필드가 없으면 skip
        if isinstance(val, list):
            continue  # 정상 YAML 배열 → 통과
        if isinstance(val, str) and C09_STR_LIST_PATTERN.match(val.strip()):
            issues.append(f"{field}='{val}' (문자열화된 리스트)")
    if issues:
        return False, f"C09 위반: {', '.join(issues)}"
    return True, "C09 통과"
```

**역검증 데이터 추가**:

1. **laptop_c09_samples.json** — laptop-hugo에서 발견된 C09 사례 (16건 중 대표 5건):
```json
[
  {"blog_id": "laptop-hugo", "post_slug": "13인치노트북-흔한-오해-3가지-2026년-기준-바로잡기",
   "source_file": "/Users/twinssn/Projects/CUAP/laptop-hugo/content/posts/13인치노트북-흔한-오해-3가지-2026년-기준-바로잡기/index.md",
   "categories": "['추천']", "tags": "['13인치노트북']", "expected": "fail"},
  ...
]
```

2. **health_c09_samples.json** — health-hugo에서 발견된 C09 사례 (11건 중 대표 5건):
```json
[
  {"blog_id": "health-hugo", "post_slug": "면역력-높이는-영양제-성분별-핵심-비교-및-효과-분석",
   "source_file": "/Users/twinssn/Projects/CUAP/health-hugo/content/posts/면역력-높이는-영양제-성분별-핵심-비교-및-효과-분석/index.md",
   "categories": "['추천']", "tags": "['면역력', '면역력 높이는 영양제 추천', '영양제', '높이는', '추천']", "expected": "fail"},
  ...
]
```

3. **오탐 검증용 정상 샘플** — health-hugo 정상 YAML 배열 글 (type=list 확인):
```json
[
  {"blog_id": "health-hugo", "post_slug": "독일pm쥬스-액티바이즈-vs-퀵앤써-리스토레이트-어떤-걸-골라야-할까-상황별-추천",
   "source_file": "...", "categories_type": "list", "tags_type": "list", "expected": "pass"},
  ...
]
```

**C09 판정 로직 참고**:
- YAML 파싱 결과 type이 `list` → 정상 (통과)
- YAML 파싱 결과 type이 `str`이고 `['...']` 또는 `["..."]` 패턴 → 문자열화 (fail)
- YAML 파싱 결과 type이 `str`이지만 `[...]` 패턴 아님 → 다른 문자열 값 (C09 대상 아님)
</action>
  <verify>
<automated>
# Part A: C07 미매칭 확인
python3 -c "
import json, os, re
C07 = re.compile(r'href=(?:\"|\\\\")https://([\w-]+)\.informationhot\.kr/posts/(.+?)/(?:\"|\\\\")')
dead = json.load(open('scripts/c01_c08_validation_data/dead_links.json'))
dn = json.load(open('scripts/c01_c08_validation_data/dongnam_npmb.json'))
files = list(set([d['source_file'] for d in dead] + [d['source_file'] for d in dn]))
files_exists = [f for f in files if os.path.exists(f)]
print(f'검사 파일: {len(files_exists)}개')
unmatched = 0
for f in files_exists:
    content = open(f, encoding='utf-8').read()
    slugs_found = set(m[1] for m in C07.findall(content))
    for d in dead:
        if d['source_file'] == f and d['cross_sell_target_slug'] not in slugs_found:
            unmatched += 1
    for d in dn:
        if d['source_file'] == f and d['target_slug'] not in slugs_found:
            unmatched += 1
print(f'C07 미매칭: {unmatched}건 (0이어야 함)')
assert unmatched == 0, f'C07 미매칭 {unmatched}건!'
print('C07 패턴 확인: PASS')
"

# Part B: C09 데이터 파일 확인
python3 -c "
import json
laptop = json.load(open('scripts/c01_c08_validation_data/laptop_c09_samples.json'))
health = json.load(open('scripts/c01_c08_validation_data/health_c09_samples.json'))
print(f'laptop C09 샘플: {len(laptop)}건')
print(f'health C09 샘플: {len(health)}건')
# laptop 샘플이 모두 문자열화인지 확인
for item in laptop:
    assert isinstance(item['categories'], str) or isinstance(item['tags'], str), f'{item[\"post_slug\"]}: 문자열화 아님'
print('laptop C09 데이터: PASS')
for item in health:
    assert isinstance(item['categories'], str) or isinstance(item['tags'], str), f'{item[\"post_slug\"]}: 문자열화 아님'
print('health C09 데이터: PASS')
"
</automated>
  </verify>
  <done>
- C07 미매칭 0건 확인 (패턴 수정 완료)
- laptop_c09_samples.json 생성 (laptop-hugo C09 사례 5건 이상)
- health_c09_samples.json 생성 (health-hugo C09 사례 5건 이상)
- c01_c08_reverse_validation.py에 check_c09_frontmatter() 함수 추가
</done>
</task>

<task type="auto">
  <name>Task 2: 62-01 재검증 실행 (C04 + C07 수정후 + C09 + ETAP 영문 + 정상글)</name>
  <files>scripts/c01_c08_reverse_validation.py, scripts/c01_c08_validation_data/*.json</files>
  <action>
## 62-01 재검증 실행

역검증 스크립트를 실행하여 다음 5개 축의 결과를 표로 정리한다:

| 검증 항목 | 사례 | 기대 결과 | 실제 결과 |
|-----------|------|-----------|-----------|
| (a) C04 contamination | 16건 (contamination.json) | 16/16 탐지, 오탐 0 | ? |
| (b) C07 dead_links (수정 후) | 53건 (dead_links.json) | 53/53 탐지 | ? |
| (c) C07 dongnam (수정 후) | 44건 (dongnam_npmb.json) | 44/44 탐지 | ? |
| (d) C09 laptop 문자열화 | 5건+ (laptop_c09_samples.json) | 전부 탐지 | ? |
| (e) C09 health 문자열화 | 5건+ (health_c09_samples.json) | 전부 탐지 | ? |
| (f) ETAP 영문 오탐 | 100건+ (etap_english_samples.json) | 오탐 0 | ? |
| (g) 정상글 오탐 (C01~C05) | normal_samples.json | 오탐 0 | ? |
| (h) C09 정상 YAML 배열 오탐 | health 정상 샘플 5건 | 오탐 0 | ? |

**실행 명령**:
```bash
python3 scripts/c01_c08_reverse_validation.py \
  --dead-links scripts/c01_c08_validation_data/dead_links.json \
  --contamination scripts/c01_c08_validation_data/contamination.json \
  --dongnam scripts/c01_c08_validation_data/dongnam_npmb.json \
  --etap-samples scripts/c01_c08_validation_data/etap_english_samples.json \
  --normal-samples scripts/c01_c08_validation_data/normal_samples.json \
  2>&1 | tee /tmp/c01_c08_reverse_validation_63.txt
```

**C09 별도 실행** (check_c09_frontmatter 함수 직접 호출):
```bash
python3 -c "
import json, sys
sys.path.insert(0, '.')
from scripts.c01_c08_reverse_validation import check_c09_frontmatter, parse_frontmatter

# laptop C09 샘플 검사
laptop = json.load(open('scripts/c01_c08_validation_data/laptop_c09_samples.json'))
laptop_results = []
for item in laptop:
    content = open(item['source_file'], encoding='utf-8').read()
    fm_str, fm_dict, body = parse_frontmatter(content)
    ok, msg = check_c09_frontmatter(fm_dict)
    laptop_results.append({'slug': item['post_slug'], 'expected': 'fail', 'actual': 'fail' if not ok else 'pass (예상외)', 'msg': msg})

# health C09 샘플 검사
health = json.load(open('scripts/c01_c08_validation_data/health_c09_samples.json'))
health_results = []
for item in health:
    content = open(item['source_file'], encoding='utf-8').read()
    fm_str, fm_dict, body = parse_frontmatter(content)
    ok, msg = check_c09_frontmatter(fm_dict)
    health_results.append({'slug': item['post_slug'], 'expected': 'fail', 'actual': 'fail' if not ok else 'pass (예상외)', 'msg': msg})

# 정상 YAML 배열 오탐 검사
normal = json.load(open('scripts/c01_c08_validation_data/health_normal_yaml_samples.json'))
normal_results = []
for item in normal:
    content = open(item['source_file'], encoding='utf-8').read()
    fm_str, fm_dict, body = parse_frontmatter(content)
    ok, msg = check_c09_frontmatter(fm_dict)
    normal_results.append({'slug': item['post_slug'], 'expected': 'pass', 'actual': 'pass' if ok else 'fail (오탐)', 'msg': msg})

print('=== C09 역검증 결과 ===')
print(f'laptop 문자열화: {sum(1 for r in laptop_results if r[\"actual\"]==\"fail\")}/{len(laptop_results)} 탐지')
print(f'health 문자열화: {sum(1 for r in health_results if r[\"actual\"]==\"fail\")}/{len(health_results)} 탐지')
print(f'정상 YAML 배열 오탐: {sum(1 for r in normal_results if r[\"actual\"]==\"fail\")}/{len(normal_results)}')
"
```

**출력 표 형식**:
```
=== 62-01 재검증 종합 결과 (Phase 63) ===

| 항목 | 사례 수 | 탐지/통과 | 상태 |
|------|---------|-----------|------|
| C04 contamination | 16 | 16/16 | ✅ |
| C07 dead_links (수정 후) | 53 | 53/53 | ✅ |
| C07 dongnam (수정 후) | 44 | 44/44 | ✅ |
| C09 laptop 문자열화 | 5 | 5/5 | ✅ |
| C09 health 문자열화 | 5 | 5/5 | ✅ |
| ETAP 영문 오탐 | 100+ | 0/100+ | ✅ |
| 정상글 오탐 (C01~C05) | N | 0/N | ✅ |
| C09 정상 YAML 배열 오탐 | 5 | 0/5 | ✅ |
```

**실행 게이트**: 전건 탐지 + 오탐 0 확인 → 62-02 INSERT 조건 충족 (C09 제외, C09는 63-02에서 별도 처리)
</action>
  <verify>
<automated>
# 62-01 재검증 실행 + 결과 저장
python3 scripts/c01_c08_reverse_validation.py \
  --dead-links scripts/c01_c08_validation_data/dead_links.json \
  --contamination scripts/c01_c08_validation_data/contamination.json \
  --dongnam scripts/c01_c08_validation_data/dongnam_npmb.json \
  --etap-samples scripts/c01_c08_validation_data/etap_english_samples.json \
  --normal-samples scripts/c01_c08_validation_data/normal_samples.json \
  2>&1 | tee /tmp/c01_c08_reverse_validation_63.txt

# C09 별도 검증
python3 -c "
import json, sys
sys.path.insert(0, '.')
from scripts.c01_c08_reverse_validation import check_c09_frontmatter, parse_frontmatter

laptop = json.load(open('scripts/c01_c08_validation_data/laptop_c09_samples.json'))
health = json.load(open('scripts/c01_c08_validation_data/health_c09_samples.json'))
normal = json.load(open('scripts/c01_c08_validation_data/health_normal_yaml_samples.json'))

laptop_ok = sum(1 for item in laptop if not check_c09_frontmatter(parse_frontmatter(open(item['source_file'], encoding='utf-8').read())[1])[0])
health_ok = sum(1 for item in health if not check_c09_frontmatter(parse_frontmatter(open(item['source_file'], encoding='utf-8').read())[1])[0])
normal_fp = sum(1 for item in normal if not check_c09_frontmatter(parse_frontmatter(open(item['source_file'], encoding='utf-8').read())[1])[0])

print(f'C09 laptop: {laptop_ok}/{len(laptop)} 탐지 (기대: {len(laptop)}/{len(laptop)})')
print(f'C09 health: {health_ok}/{len(health)} 탐지 (기대: {len(health)}/{len(health)})')
print(f'C09 정상 오탐: {normal_fp}/{len(normal)} (기대: 0/{len(normal)})')
assert laptop_ok == len(laptop), f'laptop C09 미탐지 {len(laptop)-laptop_ok}건'
assert health_ok == len(health), f'health C09 미탐지 {len(health)-health_ok}건'
assert normal_fp == 0, f'C09 정상 오탐 {normal_fp}건'
print('C09 역검증: PASS')
"
</automated>
  </verify>
  <done>
- 62-01 재검증 결과 표 생성 (CONTEXT.md §역검증 표 + C09 추가)
- C04: 16/16 탐지 확인
- C07: dead_links 53/53 + dongnam 44/44 = 97/97 탐지 확인
- C09: laptop 5/5 + health 5/5 탐지, 정상 YAML 배열 오탐 0 확인
- ETAP 영문 오탐 0, 정상글 오탐 0 확인
- 결과 파일: /tmp/c01_c08_reverse_validation_63.txt
</done>
</task>

<task type="auto">
  <name>Task 3: health 저혈압 글 진본 확인</name>
  <files>scripts/c01_c08_validation_data/health_hypotension_audit.json</files>
  <action>
## health 저혈압 글 진본 확인

**대상 파일**: `/Users/twinssn/Projects/CUAP/health-hugo/content/posts/저혈압-증상-완화-돕는-필수-영양-성분과-섭취법/index.md`

### 확인 항목

**1. 프론트매터 첫 20줄 출력**:
```bash
head -20 "/Users/twinssn/Projects/CUAP/health-hugo/content/posts/저혈압-증상-완화-돕는-필수-영양-성분과-섭취법/index.md"
```

**2. 곡선따옴표 확인 (C01)**:
```python
content = open(".../저혈압...index.md", encoding='utf-8').read()
frontmatter_section = content.split('---')[1]  # 첫 ---와 두 번째 --- 사이
curved = ['\u2018', '\u2019', '\u201c', '\u201d']
has_curved = any(c in frontmatter_section for c in curved)
# False = 직선따옴표만 사용 (정상)
```

**3. 프론트매터 정상 종료 확인 (C02)**:
```python
lines = content.split('\n')
first_dash = next(i for i, l in enumerate(lines) if l.strip() == '---')
second_dash = next((i for i, l in enumerate(lines) if i > first_dash and l.strip() == '---'), None)
# second_dash is not None = 정상 종료
```

**4. categories/tags 형식 확인 (C09)**:
```python
import yaml
fm = yaml.safe_load('\n'.join(lines[1:second_dash]))
cat_type = type(fm.get('categories')).__name__  # 'list' = 정상, 'str' = 문자열화
tags_type = type(fm.get('tags')).__name__
```

**5. 라이브 확인**:
```bash
curl -sL -o /dev/null -w "%{http_code}" "https://health.informationhot.kr/posts/저혈압-증상-완화-돕는-필수-영양-성분과-섭취법/"
# HTTP 200 = 라이브 존재
curl -sL "https://health.informationhot.kr/posts/저혈압-증상-완화-돕는-필수-영양-성분과-섭취법/" | grep -c "저혈압 증상 완화"
# 1 이상 = 본문에 포스트 내용 존재
```

### 판정 로직

| 조건 | 결과 |
|------|------|
| 파일 프론트매터 직선따옴표 + 정상 종료 | 파일 건전성 ✅ |
| categories/tags 정상 YAML 배열 (type=list) | C09 미해당 ✅ |
| 라이브 HTTP 200 + 본문 존재 | 배포완료 ✅ |
| 파일 직선 + 라이브 곡선 | **배포누락** (배포 과정에서 곡선 변환) |
| 파일 곡선 + 라이브 직선 | **재생성필요** (파일 자체 수정 필요) |
| 파일 직선 + 라이브 직선 + HTTP 200 | **배포완료** (정상) |

### 결과 기록

health_hypotension_audit.json에 기록:
```json
{
  "file_path": "/Users/twinssn/Projects/CUAP/health-hugo/content/posts/저혈압-증상-완화-돕는-필수-영양-성분과-섭취법/index.md",
  "frontmatter_first_20_lines": "...",
  "c01_curved_quotes_in_frontmatter": false,
  "c02_frontmatter_terminated": true,
  "c09_categories_type": "list",
  "c09_tags_type": "list",
  "c09_detected": false,
  "live_http_status": 200,
  "live_body_contains_post": true,
  "live_og_title": "건강기능식품 추천 가이드",
  "live_has_curved_quotes": false,
  "judgment": "배포완료",
  "judgment_reason": "파일 직선따옴표 + 프론트매터 정상 종료 + 라이브 HTTP 200 + 본문 존재. C08(og:title 불일치)는 placeholder 범위로 이번 판정 제외.",
  "cover_field": "",
  "cover_note": "cover 필드 공백 — Phase 61 스키마 표준화 트랙 (릭 원인 아님, 사용자 지시)"
}
```
</action>
  <verify>
<automated>
python3 -c "
import json, re, yaml

path = '/Users/twinssn/Projects/CUAP/health-hugo/content/posts/저혈압-증상-완화-돕는-필수-영양-성분과-섭취법/index.md'
content = open(path, encoding='utf-8').read()
lines = content.split('\n')

# C01: 곡선따옴표
fm_section = '\n'.join(lines[1:lines.index('---', 1)])
curved = ['\u2018', '\u2019', '\u201c', '\u201d']
c01 = any(c in fm_section for c in curved)

# C02: 정상 종료
first = lines.index('---')
second = lines.index('---', first + 1)
c02 = second > first

# C09: categories/tags 타입
fm = yaml.safe_load('\n'.join(lines[1:second])) or {}
c09_cat = type(fm.get('categories')).__name__
c09_tags = type(fm.get('tags')).__name__
c09 = c09_cat == 'str' or c09_tags == 'str'

print(f'C01 곡선따옴표: {c01} (False=정상)')
print(f'C02 프론트매터 종료: {c02} (True=정상)')
print(f'C09 categories type: {c09_cat} (list=정상)')
print(f'C09 tags type: {c09_tags} (list=정상)')
print(f'cover 필드: \"{fm.get(\"cover\", \"N/A\")}\"')

assert not c01, 'C01 위반: 곡선따옴표 있음'
assert c02, 'C02 위반: 프론트매터 미종료'
assert c09_cat == 'list', f'C09 위반: categories type={c09_cat}'
assert c09_tags == 'list', f'C09 위반: tags type={c09_tags}'
print('저혈압 글 판정: 파일 건전성 PASS')
"
</automated>
  </verify>
  <done>
- health_hypotension_audit.json 생성
- 파일 직선따옴표 + 프론트매터 정상 종료 + C09 미해당 확인
- 라이브 HTTP 200 + 본문 존재 확인 → 배포완료 판정
- cover 필드 공백 → Phase 61 스키마 트랙 별도 표기로 기록
</done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <what-built>62-01 재검증 결과 + health 저혈압 글 판정</what-built>
  <how-to-verify>
## 62-01 재검증 결과 확인

| 항목 | 사례 수 | 기대 | 실제 | 상태 |
|------|---------|------|------|------|
| C04 contamination | 16 | 16/16 | ? | ? |
| C07 dead_links | 53 | 53/53 | ? | ? |
| C07 dongnam | 44 | 44/44 | ? | ? |
| C09 laptop 문자열화 | 5 | 5/5 | ? | ? |
| C09 health 문자열화 | 5 | 5/5 | ? | ? |
| ETAP 영문 오탐 | 100+ | 0 | ? | ? |
| 정상글 오탐 | N | 0 | ? | ? |
| C09 정상 YAML 오탐 | 5 | 0 | ? | ? |

## health 저혈압 글 판정 확인

- 파일 직선따옴표: ✅
- 프론트매터 정상 종료: ✅
- categories/tags YAML 배열 (C09 미해당): ✅
- 라이브 HTTP 200 + 본문 존재: ✅ → **배포완료**
</how-to-verify>
  <resume-signal>
- ✅ "승인" → 63-02 (C09 INSERT 준비)로 진행
- ❌ "조건 수정 필요: [내용]" → 수정 후 재검증
</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| 경계 | 설명 |
|------|-----|
| 파일→파이프라인 | YAML 파싱 결과 타입이 파이프라인 처리에 영향 (문자열화 시 Hugo range 실패) |
| 로컬→라이브 | 로컬 파일이 라이브와 불일치할 수 있음 (C08 범위, 현재 placeholder) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-63-01 | Elevation of Privilege | C09 미적용 시 문자열화 글 배포 | mitigate | C09 규칙 severity=CRITICAL, 배포차단. 63-02에서 ops_dashboard/db.py INSERT |
| T-63-02 | Information Disclosure | C07 미매칭으로 죽은 링크 배포 | mitigate | 현재 C07 패턴 미매칭 0건 확인. 62-01 재검증으로 재확인 |
| T-63-03 | Tampering | npm/pip 패키지 무결성 | accept | 이번 Phase는 pip install 없음. 스크립트만 수정 |
</threat_model>

<verification>
## 전체 검증

- [ ] C07 패턴 미매칭 0건 확인 (dead_links 53건 + dongnam 44건 = 97건 전부 탐지)
- [ ] check_c09_frontmatter() 함수 구현 + 노트북/health 샘플 5건씩 전부 탐지
- [ ] laptop_c09_samples.json + health_c09_samples.json + health_normal_yaml_samples.json 생성
- [ ] 62-01 재검증 실행: C04 16/16, C07 97/97, C09 10/10, ETAP 영문 오탐 0, 정상글 오탐 0
- [ ] health 저혈압 글: 파일 직선✅, 프론트매터 종료✅, C09 미해당✅, 라이브 HTTP 200✅ → 배포완료 판정
- [ ] health_hypotension_audit.json에 판정 결과 기록
- [ ] cover 필드 공백 → Phase 61 트랙 별도 표기 (릭 게이트에서 제외)
</verification>

<success_criteria>
- [ ] C07 패턴 현재 정상 작동 확인 (미매칭 0건)
- [ ] C09 check_c09_frontmatter() 함수 구현 완료
- [ ] laptop_c09_samples.json: laptop-hugo C09 사례 5건 이상 포함
- [ ] health_c09_samples.json: health-hugo C09 사례 5건 이상 포함
- [ ] health_normal_yaml_samples.json: 정상 YAML 배열 샘플 5건 이상 포함 (오탐 검증용)
- [ ] 62-01 재검증 결과 표: C04 16/16, C07 97/97, C09 10/10, ETAP 영문 오탐 0, 정상글 오탐 0
- [ ] health_hypotension_audit.json: 저혈압 글 배포완료 판정 + cover 누락 Phase 61 트랙 분류
- [ ] 사용자는 63-02 진행 전 재검증 결과 확인 + 승인
</success_criteria>

<output>
Create/modify:
- scripts/c01_c08_reverse_validation.py (check_c09_frontmatter 추가)
- scripts/c01_c08_validation_data/laptop_c09_samples.json (신규)
- scripts/c01_c08_validation_data/health_c09_samples.json (신규)
- scripts/c01_c08_validation_data/health_normal_yaml_samples.json (신규)
- scripts/c01_c08_validation_data/health_hypotension_audit.json (신규)
- /tmp/c01_c08_reverse_validation_63.txt (결과)

커밋 메시지 후보:
- `test(phase-63): add C09 check function + reverse validation data + hypotension audit`
</output>
