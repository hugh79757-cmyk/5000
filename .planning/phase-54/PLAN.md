# Phase 54: CUAP 블로그 제목 생성 로직 개선

## 목표
CUAP 블로그 제목의 검색 유입·클릭률(CTR)을 높이기 위해 제목 생성 로직을 개선한다.
발행 파이프라인을 깨지 않고 제목 품질만 끌어올린다.

## 성공 기준
- massage-hugo, kitchen-hugo 등에서 생성한 제목이 다음 조건을 모두 만족:
  (a) 괄호 () 없음 (하이픈 - 사용)
  (b) 검색니즈 키워드 포함 (사람들이 실제 검색하는 구체어)
  (c) 뻔한 어미 없음 ("추천 가이드", "선택지 5종", "총정리", "고르는 법" 금지)
  (d) 서로 중복 없음
- 문법 검증 통과: `python3 -c "import ast; ast.parse(open('파일').read())"`
- 제목 생성 테스트 통과: `force_draft=True`로 3~5개 제목 생성 성공

---

## 현황 진단

### 현재 제목이 밋밋한 이유

| 문제점 | 현재 코드 위치 | 상태 |
|--------|---------------|------|
| 추상적·감성적 수식어 허용 | `_build_system_prompt` (writer.py:288) | "요리 즐거움을 더하는" 같은 표현 가능 |
| 뻔한 어미 차단 안 됨 | `_TITLE_TEMPLATE_PATTERNS` (writer.py:502) | "추천 가이드", "총정리", "고르는 법" 허용 |
| 괄호 () 검증 없음 | `_validate_title` (writer.py:509) | `()` 사용 가능 |
| 길이 기준 느슨 | `_validate_title` (writer.py:509) | 10~60자 (RAP은 32자 이내) |
| 검색니즈 키워드 미강제 | `_build_system_prompt` (writer.py:288) | "제품명 포함"만 요구 |
| 템플릿 자체가 뻔한 어미 | `TITLE_TEMPLATES` (title_templates.py:17) | "고르는 법", "총정리" 사용 |

### RAP의 _SUB_TITLE_RULES (이식 대상)

RAP는 이미 개선된 제목 로직 보유:
- **32자 이내** (35자 초과 금지)
- **4요소 조합 필수**: 지역, 유형, 검색니즈(필수), 후킹
- **괄호 () 절대 금지** → 하이fern - 사용
- **"정보/안내/공고/총정리/확인" 어미 금지**
- **매 글마다 어미·앵글 변경**으로 중복 방지

---

## 작업 단계

### Step 1: 제목 규칙 강화 (pipelines/curation/writer.py)

**1.1 `_build_system_prompt` 수정 (288행~)**

기존:
```python
return f"""당신은 10년 경력의 상품 큐레이션 전문 블로거입니다...
[제목 규칙 — 가장 중요]
제목은 반드시 아래 패턴 중 하나를 따라야 합니다:
1. [연도]년 [월]월 [제품명] 추천 — [구체적 혜택/특징]
2. [제품A] vs [제품B] — [비교 포인트]
3. [대상]을 위한 [제품 유형] 총정리 — [가격대/혜택]
```

변경:
```python
return f"""당신은 10년 경력의 상품 큐레이션 전문 블로거입니다...
[제목 규칙 — 가장 중요, 반드시 준수]
제목은 반드시 아래 조건을 모두 만족해야 합니다:

1. 길이: 35자 이내 (공백 포함, 40자 절대 초과 금지)
2. 괄호 () 사용 절대 금지 — 구분이 필요하면 하이픈(-) 사용
3. 검색니즈 키워드 필수: 사람들이 실제 검색하는 구체적 표현 1개 이상 포함
   - 좋음: "인덕션 프라이팬 추천", "코팅 오래가는", "무선 청소기 흡입력"
   - 나쁨: "요리 즐거움을 더하는", "만족스러운 선택"
4. 뻔한 어미 금지: "추천 가이드", "선택지 5종", "총정리", "고르는 법"으로 끝나면 안 됨
   - 어미를 매번 다르게 작성 (예: "~실속 비교", "~가격대별 정리", "~신혼부부 취향별")
5. 필수 요소 2개 이상 조합: 제품명, 브랜드, 가격대, 대상 중 택 2
6. 중복 방지: 최근 발행 제목과 구조·표현·어조가 완전히 다르게 작성

[제목 패턴 예시 — 참고용, 반드시 이 구조를 따를 필요는 없음]
- "인덕션 냄비 세트 3만원대 - 쿠쿠·르쿠르제 내구성 비교"
- "무선 청소기 흡입력 2026년 8월 - 삼성·LG 150W급 실사용"
- "신혼부부 주방 필수 - 인덕션 프라이팬 5종 가격대별"
```

**1.2 `_validate_title` 수정 (509행~)**

기존:
```python
def _validate_title(title):
    """제목 수용 조건 검증 — False면 재생성/차단 대상.
    - 길이 10~60자
    - CoT 마커 미포함: "우선", "사용자 요청"
    - 템플릿 패턴 미포함: 추천 TOP N / (연도년)$ / BEST N
    """
    if not title:
        return False
    title = title.strip()
    if not (10 <= len(title) <= 60):
        return False
    if "우선" in title or "사용자 요청" in title:
        return False
    for pat in _TITLE_TEMPLATE_PATTERNS:
        if pat.search(title):
            return False
    return True
```

변경:
```python
# 뻔한 어미 패턴 (하드코딩 후처리 sanitize)
_BANNED_TITLE_ENDINGS = [
    re.compile(r"추천\s*가이드$"),
    re.compile(r"선택지\s*\d+종$"),
    re.compile(r"총정리$"),
    re.compile(r"고르는\s*법$"),
    re.compile(r"가이드$"),
    re.compile(r"정리$"),
]

def _validate_title(title):
    """제목 수용 조건 검증 — False면 재생성/차단 대상.

    - 길이 10~32자 (35자 초과 절대 금지)
    - 괄호 () 미포함 (하이픈 - 허용)
    - CoT 마커 미포함: "우선", "사용자 요청"
    - 템플릿 패턴 미포함: 추천 TOP N / (연도년)$ / BEST N
    - 뻔한 어미 미포함: 추천 가이드, 총정리, 고르는 법 등
    """
    if not title:
        return False
    title = title.strip()
    # 35자 이내 (40자 초과 절대 금지)
    if not (10 <= len(title) <= 35):
        return False
    # 괄호 () 사용 금지
    if "(" in title or ")" in title or "（" in title or "）" in title:
        return False
    if "우선" in title or "사용자 요청" in title:
        return False
    for pat in _TITLE_TEMPLATE_PATTERNS:
        if pat.search(title):
            return False
    # 뻔한 어미 차단
    for pat in _BANNED_TITLE_ENDINGS:
        if pat.search(title):
            return False
    return True
```

**1.3 `_TITLE_TEMPLATE_PATTERNS` 확장 (502행~)**

기존:
```python
_TITLE_TEMPLATE_PATTERNS = [
    re.compile(r"추천\s*TOP\s*\d+", re.I),
    re.compile(r"\(\d{4}년\)$"),
    re.compile(r"BEST\s*\d+", re.I),
]
```

변경:
```python
_TITLE_TEMPLATE_PATTERNS = [
    re.compile(r"추천\s*TOP\s*\d+", re.I),
    re.compile(r"\(\d{4}년\)$"),
    re.compile(r"BEST\s*\d+", re.I),
    re.compile(r"추천\s*가이드$"),
    re.compile(r"선택지\s*\d+종$"),
    re.compile(r"총정리$"),
    re.compile(r"고르는\s*법$"),
]
```

**1.4 `_regenerate_title` 프롬프트 강화 (530행~)**

기존:
```python
system_prompt = (
    "당신은 상품 큐레이션 블로그 제목 작성 전문가입니다. 반드시 한국어로 작성하세요.\n"
    "아래 키워드에 대한 블로그 글 제목을 한 줄만 출력하세요.\n"
    "제목 앞에 '# ' 마크다운 H1 마커를 붙이세요.\n"
    "검토 문구, 사고 과정, 설명은 출력하지 마세요.\n"
    '나열형 템플릿 제목("{keyword} 추천 TOP N (연도년)" 형태)은 금지합니다.\n'
    "제목 길이는 10~60자로 작성하세요."
)
```

변경:
```python
system_prompt = (
    "당신은 상품 큐레이션 블로그 제목 작성 전문가입니다. 반드시 한국어로 작성하세요.\n"
    "아래 키워드에 대한 블로그 글 제목을 한 줄만 출력하세요.\n"
    "제목 앞에 '# ' 마크다운 H1 마커를 붙이세요.\n"
    "검토 문구, 사고 과정, 설명은 출력하지 마세요.\n"
    '나열형 템플릿 제목("{keyword} 추천 TOP N (연도년)" 형태)은 금지합니다.\n'
    "괄호 () 사용 절대 금지 — 구분이 필요하면 하이픈(-) 사용.\n"
    "제목 길이는 10~32자로 작성하세요.\n"
    "검색니즈 키워드: 사람들이 실제 검색하는 구체적 표현(예: '인덕션 프라이팬 추천', '코팅 오래가는')을 반드시 1개 이상 포함.\n"
    "뻔한 어미 금지: '추천 가이드', '선택지 5종', '총정리', '고르는 법'으로 끝나면 안 됨.\n"
    "제목에 제품명, 브랜드, 가격대, 대상 중 최소 2개 이상 포함하세요."
)
```

---

### Step 2: TitleTemplatePicker 개선 (shared/title_templates.py)

**2.1 템플릿에서 뻔한 어미 제거**

기존:
```python
TITLE_TEMPLATES: dict[str, str] = {
    "comparison": "{brand1} vs {brand2} — {keyword} 어떤 게 나을까?",
    "ranking": "{keyword} BEST 5 — {year}년 {month}월 엄선",
    "toplist": "TOP 5 {keyword} — 선택한 이유와 특징",
    "buying_guide": "{keyword} 고르는 법: {year}년 최신 가이드",
    "budget": "{keyword} 추천: {price_range}만원 이하 합격점 TOP 5",
    "review_style": "상품 데이터로 비교하는 {keyword} TOP 5",
    "question_style": "{keyword} 고민된다면? 지금 사야 하는 이유",
    "spec_style": "{year}년 {month}월 스펙 비교: {brand1} vs {brand2} vs {brand3}",
    "myth_busting": "{keyword} 흔한 오해 3가지 — {year}년 기준 바로잡기",
    "new_release": "최근 출시 {keyword} {brand1} — 첫인상과 주요 특징",
    "situation_based": "{keyword} 어떤 걸 골라야 할까? 상황별 추천",
}
```

변경:
```python
TITLE_TEMPLATES: dict[str, str] = {
    "comparison": "{brand1} vs {brand2} — {keyword} 실사용 비교",
    "ranking": "{keyword} {year}년 {month}월 실속 5선",
    "toplist": "{keyword} 가격대별 - {brand1} 포함 인기 5종",
    "budget": "{keyword} {price_range}만원 이하 - 합격점 5종",
    "review_style": "{keyword} 실제 리뷰로 본 - {brand1} 주목",
    "question_style": "{keyword} 어떤 걸 살까 - 상황별 3선",
    "spec_style": "{year}년 {month}월 스펙으로 보는 {brand1} vs {brand2}",
    "myth_busting": "{keyword} 흔한 오해 - {year}년 기준 바로잡기",
    "new_release": "최근 출시 {keyword} {brand1} - 첫인상과 특징",
    "situation_based": "{keyword} 상황별 추천 - 어떤 게 맞을까",
}
```

**2.2 블로그별 오버라이드에서 금지 템플릿 업데이트**

`buying_guide` 템플릿이 "고르는 법"을 사용하므로, `avoid_templates`에 추가 검토 필요.

---

### Step 3: 검증 및 테스트

**3.1 문법 검증**

```bash
python3 -c "import ast; ast.parse(open('/Users/twinssn/Projects/5000/pipelines/curation/writer.py').read())"
python3 -c "import ast; ast.parse(open('/Users/twinssn/Projects/5000/shared/title_templates.py').read())"
```

**3.2 제목 생성 테스트**

`force_draft=True`로 CUAP 블로그 제목 3~5개 생성:

```bash
cd /Users/twinssn/Projects/5000
python3 -c "
from pipelines.curation.writer import generate_curation_article
from pipelines.curation.collector import get_products

# 테스트용 키워드
test_keywords = ['인덕션 프라이팬', '무선 청소기', '에어프라이어']
for kw in test_keywords:
    products = get_products(kw, limit=3)
    if products:
        article = generate_curation_article(kw, products, blog_id='massage-hugo', force_draft=True)
        if article:
            print(f'[{kw}] 제목: {article.get(\"title\", \"N/A\")}')
"
```

**3.3 게이트 검증**

생성된 제목이 `_title_gate`와 `_content_quality_gate`를 통과하는지 확인.

---

### Step 4: 발행 파이프라인 안전성 확인

- `pipelines/curation/pipeline.py`의 `_title_gate` (742행)가 새 제목을 차단하지 않는지 확인
- `_content_quality_gate` (761행)가 새 제목 패턴을 허용하는지 확인
- 기존 `_TITLE_TEMPLATE_PATTERNS` 확장이 정상 동작하는지 확인

---

## 수정 대상 파일

| 파일 | 수정 내용 | 영향 범위 |
|------|----------|----------|
| `pipelines/curation/writer.py` | `_build_system_prompt`, `_validate_title`, `_TITLE_TEMPLATE_PATTERNS`, `_regenerate_title` | 제목 생성/검증 로직 |
| `shared/title_templates.py` | `TITLE_TEMPLATES` 값 변경 | 템플릿 선택기 |

## 수정하지 않는 파일

| 파일 | 이유 |
|------|------|
| `pipelines/curation/pipeline.py` | `_title_gate`, `_content_quality_gate` 로직은 유지 |
| `shared/publishers/hugo_writer.py` | 발행 로직 |
| `pipelines/curation/collector.py` | 상품 수집 로직 |
| `pipelines/curation/enricher.py` | 상품 보강 로직 |

---

## 리스크 및 완화

| 리스크 | 확률 | 완화 |
|--------|------|------|
| 새 제목 규칙이 기존 게이트에서 차단 | 중 | `_validate_title`과 `_title_gate`를 함께 수정 |
| LLM이 새 규칙을 따르지 않음 | 중 | 하드코딩 후처리 sanitize (`_BANNED_TITLE_ENDINGS`)로 강제 |
| 제목이 너무 짧아져 SEO 불리 | 낮 | 10자 최소 길이 유지 |
| 템플릿 변경으로 기존 동작 회귀 | 낮 | 기존 템플릿 구조 유지, 값만 변경 |

---

## 검증 체크리스트

- [ ] `writer.py` 문법 검증 통과
- [ ] `title_templates.py` 문법 검증 통과
- [ ] massage-hugo에서 제목 3개 생성 성공
- [ ] kitchen-hugo에서 제목 3개 생성 성공
- [ ] 생성된 제목에 괄호 () 없음
- [ ] 생성된 제목에 검색니즈 키워드 포함
- [ ] 생성된 제목에 뻔한 어미 없음
- [ ] 생성된 제목 간 중복 없음
- [ ] `_title_gate` 통과
- [ ] `_content_quality_gate` 통과
