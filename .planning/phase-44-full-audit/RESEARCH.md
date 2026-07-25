# Phase 44 Research — 6개 블로그 전수조사 및 품질 최종화

**Researched**: 2026-07-25  
**Phase**: 44 — 전수조사 및 전체 수정 (블로거1 + 휴고5)  
**Predecessor**: Phase 43 완료 (4개 블로그 검증 PASS, travel4 재평가 PASS)  
**Confidence**: HIGH

---

## 1. 아키텍처 현황 — 기존 검증 인프라 재사용 가능

### 1.1 Phase 40~43에서 구축된 검증 도구들

| 도구 | 위치 | 용도 | 재사용 가능성 |
|------|------|------|--------------|
| `generate_content()` | `pipelines/travel/writer.py` | 본문 생성 (dry-run) | ✅ 직접 호출 가능 |
| `fetch_*()` | `pipelines/travel/fetcher.py` | 주제별 데이터 수집 | ✅ 4개 주제 완비 |
| 타이틀 생성 | `shared/title_generator.py` → MiMo API | AI 타이틀 (temp=0.6) | ✅ 100% 성공 검증됨 |
| 품질 메트릭 | `shared/quality_recorder.py` | 발행 후 기록 | ⚠️ 발행 후용, dry-run은 별도 |
| 감지 스크립트 | `scripts/detect_problematic_posts.py` | 본문 스캔 (--scan-body) | ✅ 확장 가능 |

### 1.2 데이터 소스 — 기존 발행글 읽기

```python
# Hugo 콘텐츠 디렉토리 구조
CUAP_BASE = "/Users/twinssn/Projects/CUAP"
BLOGS = {
    "travel-hugo": f"{CUAP_BASE}/camping-hugo/content/posts",
    "travel1-hugo": f"{CUAP_BASE}/travel1-hugo/content/posts", 
    "travel2-hugo": f"{CUAP_BASE}/travel2-hugo/content/posts",
    "travel3-hugo": f"{CUAP_BASE}/travel3-hugo/content/posts",
    "travel4-hugo": f"{CUAP_BASE}/travel4-hugo/content/posts",
}
# blogger1은 별도 경로 (확인 필요)
```

- 각 포스트: `index.md` (frontmatter + markdown 본문)
- frontmatter 필드: title, date, keyword, category, tags, description, thumbnail_url 등
- 본문: 마크다운 + Hugo shortcode (article, chart, gallery 등)

---

## 2. 블로거1 파이프라인 — 접근 방식 확인 필요

### 2.1 현재 확인된 사항

- Blogger 플랫폼 (Hugo 아님)
- 별도 파이프라인: `pipelines/blogger/` 또는 유사
- 대표님 5번 항목이 블로거1 품질 기준

### 2.2 필요한 조사

| 항목 | 확인 필요 | 비고 |
|------|-----------|------|
| 발행글 저장 위치 | GCP Blogger API / 로컬 미러 | API로 조회 or 로컬 DB |
| 본문 형식 | HTML vs Markdown | 변환 필요 여부 |
| 품질 기준 문서 | "대표님 5번 항목" 상세 | 별도 수신 필요 |
| 파이프라인 엔트리포인트 | `pipelines/blogger/pipeline.py` 추정 | 소스 확인 후 연결 |

---

## 3. 전수조사 자동화 설계

### 3.1 검증 함수 시그니처 제안

```python
def verify_post_quality(blog_id: str, post_path: Path, criteria: QualityCriteria) -> VerificationResult:
    """
    단일 포스트 품질 검증
    - blog_id: travel-hugo, travel1-hugo, ...
    - post_path: index.md 파일 경로
    - criteria: 블로그별 QualityCriteria (임계값 포함)
    """
```

### 3.2 블로그별 QualityCriteria 매핑

```python
QUALITY_CRITERIA = {
    "travel-hugo": QualityCriteria(
        min_length=2500,
        required_keywords=["텐트","타프","침낭","랜턴","버너","코펠"],  # 캠핑 핵심 6개 중 ≥3
        forbidden_patterns=[],  # 캠핑은 이동시간 규칙 없음
        title_body_consistency=True,
        min_h2=3, max_h2=4,
        min_h3=3,
        min_h3_sentences=6,
    ),
    "travel1-hugo": QualityCriteria(
        min_length=2500,
        required_fields=["start_date","end_date","location"],
        forbidden_patterns=["추천드립니다","인기가 많습니다","방문객"],
        title_body_consistency=True,
        min_h2=3, max_h2=4,
    ),
    "travel2-hugo": QualityCriteria(
        min_length=2500,
        required_context_words=["시대","종목","양식","비교","대조","공통"],
        title_body_consistency=True,
        min_h2=3, max_h2=4,
        min_h3=3,
        min_h3_sentences=6,
    ),
    "travel3-hugo": QualityCriteria(
        min_length=2500,
        forbidden_words=FORBIDDEN_34_WORDS,  # 기존 34개 금지어
        price_format_check=True,  # "~만원대" 금지
        title_body_consistency=True,
    ),
    "travel4-hugo": QualityCriteria(
        min_length=2500,
        forbidden_movement_patterns=[r"도보\s*\d+", r"차로\s*\d+", r"\d+\s*분\s*(걸어|걸리|소요)"],
        course_name_pattern=r"^\d+코스[:：]\s*.+",  # "1코스: xxx"
        min_h3=3,
        min_h3_sentences=6,
        title_body_consistency=True,
    ),
}
```

### 3.3 검증 항목별 구현 방향

| 검증 항목 | 구현 방식 | 난이도 |
|-----------|-----------|--------|
| 본문 길이 | `len(body_text)` | 쉬움 |
| 필수 키워드/필드 | frontmatter + 본문 문자열 매칭 | 쉬움 |
| 금지어/금지패턴 | 정규식 매칭 (`re.search`) | 쉬움 |
| 타이틀-본문 일관성 | 타이틀 숫자 추출 vs H3/H2 섹션 수 카운트 | 중간 |
| 구조 검증 | 마크다운 헤더 파싱 (`## `, `### `) | 중간 |
| H3당 문장 수 | `split('.')` 또는 `kss.split_sentences` | 중간 |
| 이동시간 패턴 | 정규식 (이미 Phase 43에서 검증됨) | 쉬움 |
| 가격 포맷 | `~만원대`, `만원` 패턴 검출 | 쉬움 |
| 환각 탐지 | API 데이터와 본문 교차 검증 (fetch 필요) | 어려움 |

---

## 4. Dry-run 파이프라인 재사용 — Phase 43 검증 코드 확장

### 4.1 Phase 43 검증 스크립트 패턴

```python
# .planning/phase-43-expand-4-blogs/ 내 검증 코드 재사용
from pipelines.travel.fetcher import fetch_festival, fetch_heritage, fetch_food, fetch_course
from pipelines.travel.writer import generate_content

FETCH_MAP = {
    "travel1-hugo": fetch_festival,
    "travel2-hugo": fetch_heritage,
    "travel3-hugo": fetch_food,
    "travel4-hugo": fetch_course,
    "travel-hugo": fetch_camping,  # 기존 camping fetcher
}
```

### 4.2 Blogger1용 — 별도 처리 필요

```python
# blogger1은 fetcher/generator 구조 다를 수 있음
# 옵션 A: 기존 발행글만 검증 (dry-run 생략)
# 옵션 B: blogger pipeline import 후 동일 패턴 적용
```

---

## 5. 리스크 및 완화

| 리스크 | 가능성 | 영향 | 완화 |
|--------|--------|------|------|
| blogger1 파이프라인 미지원 | 높음 | 검증 공백 | 기존 발행글만 전수조사, dry-run 제외 |
| 발행글 수 편차 (10~100개) | 중간 | 통계 왜곡 | 블로그별 개별 리포트 + 가중 평균 |
| 주제적합성 메트릭 모호 | 중간 | 기준 불일치 | Phase 43 travel4 선례 문서화 후 적용 |
| 환각 자동 탐지 난이도 | 높음 | 검증 누락 | 1차: 금지어/패턴 기반, 2차: 샘플 수동 확인 |

---

## 6. 권장 실행 전략

### 6.1 Wave 1: 인프라 준비 (1일)
- 검증 스크립트 `scripts/verify_quality.py` 작성 (확장형)
- 블로그별 QualityCriteria 정의 완료
- blogger1 접근 방식 확정 (대표님 5번 항목 수신)

### 6.2 Wave 2: 전수조사 실행 (1일)
- 6개 블로그 병렬 검증 (각 블로그 독립)
- 결과: `VERIFICATION-PHASE44.md` (raw data)

### 6.3 Wave 3: 미달 항목 수정 및 Dry-run 검증 (1일)
- FAIL/NEEDS_REVIEW 포스트 재생성 (dry-run)
- 신규 생성 3건/블로그 품질 확인
- 결과: `PHASE44-COMPLETION-REPORT.md`

### 6.4 Wave 4: 문서화 및 마감 (0.5일)
- SUMMARY.md, ROADMAP.md 업데이트
- 다음 단계 제안 (Phase 45+ 또는 운영 전환)

---

## 7. 핵심 파일 경로 요약

```
/Users/twinssn/Projects/5000/
├── pipelines/travel/
│   ├── fetcher.py          # fetch_camping, fetch_festival, fetch_heritage, fetch_food, fetch_course
│   ├── writer.py           # generate_content() — dry-run 엔트리포인트
│   └── pipeline.py         # travel pipeline (참조용)
├── shared/
│   ├── title_generator.py  # AI 타이틀 생성 (temp=0.6, no max_tokens)
│   ├── ai_writer.py        # 본문 생성 (temp=0.85, max_tokens=4800)
│   └── quality_recorder.py # 발행 후 메트릭 (dry-run용 아님)
├── config/
│   ├── prompts.yaml        # tour1_camping, travel1_festival, travel2_heritage, tour2_food, tour3_course
│   └── models.yaml         # temperature 설정
├── scripts/
│   └── detect_problematic_posts.py  # --scan-body 확장 가능
└── .planning/phase-44-full-audit/
    ├── CONTEXT.md          # 이 문서
    ├── RESEARCH.md         # (이 문서)
    ├── PLAN.md             # (작성 예정)
    └── VERIFICATION-PHASE44.md (생성 예정)
```

---

## 8. 다음 단계

1. **PLAN.md 작성** — 위 전략을 구체적 Task/Wave로 분해
2. **blogger1 접근 방식 확정** — 대표님 5번 항목 수신 후 결정
3. **검증 스크립트 초안 작성** — `scripts/verify_quality.py` 첫 버전

---

**Research Complete**: Phase 44 실행 준비 완료. 기존 인프라 90% 재사용 가능, blogger1만 별도 처리 필요.