---
phase: 62-content-leak-prevention
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/c01_c08_reverse_validation.py
  - scripts/c01_c08_validation_data/
autonomous: true
requirements: []
must_haves:
  truths:
    - "404 6건 + 오염 27건 + 동남냄비받침 44건 = dead links 전량 fail 감지"
    - "ETAP 영문 3551건 오탐 0, 전부 pass"
    - "프롬프트 누수 케이스 오탐 없이 C04로 탐지"
    - "영문 프롬프트 누수 패턴 별도 확인, ETAP 영문 글 통과"
  artifacts:
    - path: "scripts/c01_c08_reverse_validation.py"
      provides: "C01~C08 역검증 스크립트"
      min_lines: 300
    - path: "scripts/c01_c08_validation_data/dead_links.json"
      provides: "dead links 검증 데이터 (404 6건 + 오염 27건 + 동남냄비받침 44건)"
    - path: "scripts/c01_c08_validation_data/etap_english_samples.json"
      provides: "ETAP 영문 3551건 샘플 검증 데이터"
    - path: "scripts/c01_c08_validation_data/cot_leak_samples.json"
      provides: "프롬프트 누수 검증 샘플"
  key_links:
    - from: "c01_c08_reverse_validation.py"
      to: "ops_dashboard/db.py standard_rules"
      via: "규칙 definition 임포트"
      pattern: "from ops_dashboard.db import.*C0[1-8]|STANDARD_RULE_DEFS"
---

<objective>
## 목표

C01~C08 규칙 정의를 실제 사례(역검증 데이터)에 대해 검증하여 **"전건 탐지 + 오탐 0"** 을 확인.

## 배경

CONTEXT.md §역검증 표: 작성한 규칙을 실제 사례에 돌려 검증하지 않으면 안 됨.

| 검증 항목 | 사례 | 기대 결과 |
|-----------|------|-----------|
| (a) 죽은 크로스셀 링크 | 404 6건 + 오염 27건 + 동남냄비받침 44건 | 전부 fail로 잡아야 함 |
| (b) 정상 글 | ETAP 영문 글 3551건 | 오탐 0, 전부 pass |
| (c) C04 패턴 | 프롬프트 누수 케이스 | 오탐 없이 탐지 |
| (d) 영문 글 C04 | ETAP 영문 글 | 영문 프롬프트 누수 패턴 별도 확인, 오탐 없이 통과 |

**실행 게이트**: 역검증에서 "실제 사례 전건 탐지 + 오탐 0" 확인 후 다음 단계 진행.

**오탐 발생 시**: INSERT/삽입을 보류하고 조건만 수정해 재검증.
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@/Users/twinssn/Projects/5000/.planning/phases/phase-62-content-leak-prevention/CONTEXT.md
@/Users/twinssn/Projects/5000/ops_dashboard/db.py
@/Users/twinssn/Projects/5000/ops_dashboard/checks/standard.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: 검증 데이터 준비</name>
  <files>scripts/c01_c08_validation_data/dead_links.json, scripts/c01_c08_validation_data/etap_english_samples.json, scripts/c01_c08_validation_data/cot_leak_samples.json</files>
  <action>
검증에 사용할 데이터를 준비한다:

1. **dead_links.json** (C07 검증용):
   - 404 6건: 라이브에서 HTTP 404 발생하는 크로스셀 카드 URL 목록
   - 오염 27건: DB에 published=0인 slug를 가리키는 크로스셀 카드
   - 동남냄비받침 44건: 크로스셀 로직이 잘못된 slug를 산출한 사례
   - 각 항목: {blog_id, post_slug, cross_sell_target_slug, expected_status}

2. **etap_english_samples.json** (오탐 검증용):
   - ETAP 영문 글 3551건 중 대표 샘플 100건 이상
   - 각 항목: {blog_id, post_slug, body_md, frontmatter}
   - C01/C02/C03/C04 통과해야 하는 정상 글

3. **cot_leak_samples.json** (C04 검증용):
   - "Need think", "We need to write", "Let's think step by step" 등
     프롬프트·CoT 패턴이 포함된 본문 샘플
   - 영문 패턴 별도 수록 (ETAP 영문 글용)
   - 각 항목: {pattern, body_snippet, expected_detected: true}
</action>
  <verify>
<automated>
# dead_links.json 구조 확인
python3 -c "import json; d=json.load(open('scripts/c01_c08_validation_data/dead_links.json')); print(f'dead_links: {len(d)}건')"

# etap 샘플 확인
python3 -c "import json; d=json.load(open('scripts/c01_c08_validation_data/etap_english_samples.json')); print(f'etap_samples: {len(d)}건')"

# cot_leak 샘플 확인
python3 -c "import json; d=json.load(open('scripts/c01_c08_validation_data/cot_leak_samples.json')); print(f'cot_samples: {len(d)}건')"
</automated>
  </verify>
  <done>
검증 데이터 3개 파일이 모두 존재하고 유효 JSON임
  </done>
</task>

<task type="auto">
  <name>Task 2: C01~C08 판정 함수 구현</name>
  <files>scripts/c01_c08_reverse_validation.py</files>
  <action>
C01~C08 각 규칙의 판정 함수를 구현한다.

**C01 — 프론트매터 내 곡선따옴표**
```python
def check_c01(frontmatter: str) -> tuple[bool, str]:
    """frontmatter에 곡선따옴표(' ' " ")가 있으면 fail"""
    # 직선따옴표: ' "
    # 곡선따옴표: ' ' " "
    curved_single = "'"  # U+2018, U+2019
    curved_double = '"'  # U+201C, U+201D
    found = []
    if any(c in frontmatter for c in curved_single):
        found.append("곡선따옴표(' ')")
    if any(c in frontmatter for c in curved_double):
        found.append('곡선따옴표(" ")')
    if found:
        return False, f"C01 위반: {', '.join(found)}"
    return True, "C01 통과"
```

**C02 — 프론트매터 미종료 (중요: 첫--- 이후 두 번째 --- 존재 여부로만 판정)**
```python
def check_c02(full_content: str) -> tuple[bool, str]:
    """첫 --- 이후 두 번째 ---가 없으면 fail. 전체 --- 홀수 카운트 금지."""
    # 첫 --- 위치 찾기 (라인 시작 ---)
    lines = full_content.split('\n')
    first_dash_idx = None
    second_dash_idx = None
    for i, line in enumerate(lines):
        if line.strip() == '---':
            if first_dash_idx is None:
                first_dash_idx = i
            elif second_dash_idx is None and i > first_dash_idx:
                second_dash_idx = i
                break  # 두 번째 찾았으면 중단 (첫 --- 이후만 봄)
    if first_dash_idx is None:
        return False, "C02 위반: 첫 --- 없음"
    if second_dash_idx is None:
        return False, "C02 위반: 첫 --- 이후 두 번째 --- 없음"
    return True, "C02 통과"
```
**주의**: 전체 `---` 홀수 카운트 판정 금지. 본문 내 `---` 수평선과 혼동됨.

**타블로그 변형 실측 (2026-08-14, techpawz-hugo C02 확산 확정)**:
- **원인**: 닫는 `---`가 개행 없이 본문 첫 문단과 같은 줄에 병합된 형태
  (`---2026 근로장려금 ...`). 첫 `---`(라인0)는 정상, 두 번째 독립 `---` 줄이
  없어 `line.strip() == '---'` 매치 실패 → C02 fail + frontmatter 미파싱으로
  **Hugo가 해당 포스트 페이지 HTML을 생성하지 않음**(라이브 404).
- **교정 규칙**: `\n---(?=[^\s\n])` 를 `\n---\n` 로 치환(닫는 `---` 뒤 본문 병합
  분리). 본문 첫 줄 텍스트는 그대로 보존, 최소 변경. hotissue의 여는 쪽
  `^---[^\n]` 유형과는 배열이 다르므로 카드에 이 유형 명시.
- **검증**: 교정 후 frontmatter 재파싱 `^---\n.*?\n---\n` 성공 + Hugo 빌드에서
  해당 포스트 HTML 생성 + title 정상 렌더 + 라이브 HTTP 200 + 대시보드
  `c02_frontmatter_close` pass(791건).

**C03 — 본문에 프론트매터 키 라인 유출**
```python
def check_c03(body_md: str, frontmatter_keys: list[str]) -> tuple[bool, str]:
    """본문에 title:, og_image:, featureimage:, date:, slug: 등 프론트매터 키 라인 존재 시 fail"""
    FM_KEY_PATTERN = re.compile(r'^\s*(title|og_image|featureimage|date|slug|categories|tags|description|draft|image|pubDate|author):')
    leaked = []
    for line in body_md.split('\n'):
        if FM_KEY_PATTERN.match(line):
            leaked.append(line.strip()[:60])
    if leaked:
        return False, f"C03 위반: 프론트매터 키 유출 {len(leaked)}건 — {leaked[0]}"
    return True, "C03 통과"
```

**C04 — 본문 LLM 프롬프트/사고문 누수 (영문 패턴 별도)**
```python
def check_c04(body_md: str, locale: str = 'ko') -> tuple[bool, str]:
    """프롬프트 지시문·CoT 사고문 패턴이 본문에 있으면 fail"""
    KO_PATTERNS = [
        r"먼저\s*생각", r"생각해보자", r"생각해\s*보자",
        r"다음\s*단계", r"단계별로", r"우선\s*",
        r"우리가\s*해야\s*할", r"필요한\s*것",
    ]
    EN_PATTERNS = [
        r"\bNeed\s+think\b", r"\bWe\s+need\s+to\s+write\b",
        r"Let.s\s+think\s+step\s+by\s+step",
        r"think\s+step\s+by\s+step",
        r"let.s\s+break\s+this\s+down",
        r"here.?s\s+the\s+plan",
        r"firstly,?\s", r"secondly,?\s",
        r"in\s+order\s+to\s+achieve",
    ]
    patterns = EN_PATTERNS if locale == 'en' else KO_PATTERNS
    found = []
    for pat in patterns:
        m = re.search(pat, body_md, re.IGNORECASE)
        if m:
            found.append(m.group()[:40])
    if found:
        return False, f"C04 위반: 프롬프트 누수 패턴 {len(found)}건 — {found[0]}"
    return True, "C04 통과"
```

**C05 — draft:true 발행 대상**
```python
def check_c05(frontmatter_dict: dict) -> tuple[bool, str]:
    """frontmatter에 draft: true가 있는데 발행 대상이면 fail"""
    if frontmatter_dict.get('draft') is True:
        return False, "C05 위반: draft:true 발행 대상"
    return True, "C05 통과"
```

**C06 — 로컬 mtime > 배포 시각**
```python
def check_c06(file_path: Path, last_deploy_at: str) -> tuple[bool, str]:
    """로컬 파일 mtime이 마지막 배포 시각보다 최신이면 fail"""
    if not file_path.exists():
        return True, "파일 없음 (skip)"
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    deploy_dt = datetime.fromisoformat(last_deploy_at)
    if mtime > deploy_dt:
        return False, f"C06 위반: 로컬 mtime {mtime.isoformat()} > 배포 {deploy_dt.isoformat()}"
    return True, "C06 통과"
```

**C07 — 죽은 크로스셀 링크**
```python
def check_c07(body_md: str, slug_db: dict[str, bool], live_check_fn: Callable) -> tuple[bool, str]:
    """크로스셀 카드가 가리키는 slug가 published=0이거나 HTTP 404면 fail"""
    # 크로스셀 카드에서 target slug 추출 (data-target-slug 속성 등)
    target_slugs = re.findall(r'data-target-slug=["\']([^"\']+)["\']', body_md)
    dead = []
    for slug in target_slugs:
        # DB 확인
        if slug in slug_db and not slug_db[slug]:
            dead.append(f"{slug}(DB unpublished)")
            continue
        # 라이브 HTTP 확인
        status = live_check_fn(slug)
        if status == 404:
            dead.append(f"{slug}(HTTP 404)")
    if dead:
        return False, f"C07 위반: 죽은 크로스셀 링크 {len(dead)}건 — {dead[0]}"
    return True, "C07 통과"
```

**C08 — 라이브-파일 불일치**
- 구현 보류 (라이브 비교 API 필요 — 추후)
- placeholder 함수 제공
</action>
  <verify>
<automated>
# 각 판정 함수 단위 테스트
python3 scripts/c01_c08_reverse_validation.py --test-functions
</automated>
  </verify>
  <done>
C01~C07 판정 함수 구현 완료, 단위 테스트 통과
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: 역검증 실행</name>
  <files>scripts/c01_c08_reverse_validation.py</files>
  <action>
역검증 스크립트를 실행하여 CONTEXT.md의 검증 기준을 확인한다.

**실행 명령**:
```bash
python3 scripts/c01_c08_reverse_validation.py \
  --dead-links scripts/c01_c08_validation_data/dead_links.json \
  --etap-samples scripts/c01_c08_validation_data/etap_english_samples.json \
  --cot-samples scripts/c01_c08_validation_data/cot_leak_samples.json
```

**검증 기준 (모두 충족해야 다음 단계로 진행)**:
1. dead_links 404 6건 + 오염 27건 + 동남냄비받침 44건 = **77건 전부 C07 fail**
2. ETAP 영문 3551건 샘플 100건 이상 **오탐 0, 전부 pass**
3. 프롬프트 누수 케이스 **오탐 없이 C04로 탐지**
4. ETAP 영문 글 **영문 프롬프트 누수 패턴 별도 확인, 오탐 없이 통과**

**출력 형식**:
```
=== C01~C08 역검증 결과 ===
데드링크 검출: 77/77 (100%)
ETAP 영문 통과: 100/100 (오탐 0)
프롬프트 누수 탐지: 15/15 (오탐 0)
영문 프롬프트 패턴 확인: 별도 검증 완료

결과: ✅ 전건 탐지 + 오탐 0 → 다음 단계 진행 가능
```
</action>
  <verify>
<automated>
python3 scripts/c01_c08_reverse_validation.py \
  --dead-links scripts/c01_c08_validation_data/dead_links.json \
  --etap-samples scripts/c01_c08_validation_data/etap_english_samples.json \
  --cot-samples scripts/c01_c08_validation_data/cot_leak_samples.json \
  2>&1 | tee /tmp/c01_c08_validation_result.txt

# 결과 확인
grep -q "전건 탐지 + 오탐 0" /tmp/c01_c08_validation_result.txt && echo "PASS" || echo "FAIL - 오탐 또는 미탐지 있음"
</automated>
  </verify>
  <done>
dead_links 77건 전부 fail, ETAP 영문 100건 오탐 0, 프롬프트 누수 전건 탐지 확인
  </done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <what-built>C01~C08 역검증 스크립트 및 검증 데이터</what-built>
  <how-to-verify>
scripts/c01_c08_reverse_validation.py 실행 결과를 확인한다.

기대 결과:
- dead_links: 77건 전부 C07 fail
- ETAP 영문: 오탐 0, 전부 pass
- 프롬프트 누수: 오탐 없이 C04 탐지
- 영문 프롬프트 패턴: 별도 확인 완료
  </how-to-verify>
  <resume-signal>
역검증 결과 확인 후:
- ✅ 통과 시: "승인" → 다음 계획(62-02) 진행
- ❌ 오탐/미탐지 시: "오탐 있음: [내용]" → 조건 수정 후 재검증
  </resume-signal>
</task>

</tasks>

<success_criteria>
- [ ] dead_links.json에 404 6건 + 오염 27건 + 동남냄비받침 44건 = 77건 포함
- [ ] etap_english_samples.json에 ETAP 영문 글 대표 샘플 100건 이상 포함
- [ ] cot_leak_samples.json에 프롬프트 누수 패턴 샘플 포함 (영문 패턴 별도)
- [ ] C01~C07 판정 함수 구현 + 단위 테스트 통과
- [ ] C02는 "첫 --- 이후 두 번째 --- 존재 여부"로만 판정 (전체 --- 홀수 카운트 금지)
- [ ] 역검증 결과: dead_links 77건 전부 fail + ETAP 영문 오탐 0 + 프롬프트 누수 전건 탐지
</success_criteria>

<output>
Create `scripts/c01_c08_reverse_validation.py` and `scripts/c01_c08_validation_data/*.json`

커밋 메시지 후보:
- `test(phase-62): add C01~C08 reverse validation script and data`
</output>
