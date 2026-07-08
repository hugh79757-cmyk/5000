# Phase 15 Research: Content Quality Pipeline Integration

**Date:** 2026-07-08
**Scope:** Phase 13 Hugo Markdown 수정 결과 + Phase 14 Unified Dashboard → **Phase 15: 콘텐츠 품질 파이프라인 통합**

---

## 1. Current State Assessment

### Phase 13 (Hugo Markdown Audit) — 완료된 베이스라인
- **36개 사이트** 스캔 완료 (STAP 6, RAP 5, CUAP 9, Travel 5, Car 4, Senior 1, 기타 6)
- **총 2,394개 이슈** 발견 (bold 108, italic 96)
- **파이프라인별 분포:** unknown 1,242 (주로 ETAP/techpawz 사이트), curation 400, stock 370, rap 228, car 83, senior 71, travel 0
- **데이터:** `baseline-findings.json` (1,531줄), `baseline-findings.csv`, `inventory.json` (36개 사이트)

### Phase 14 (Unified Dashboard) — Wave 1 완료, Wave 2/3 계획됨
- **Flask + Chart.js** localhost:5050 실행 중
- **APIs:** `/api/health`, `/api/posts/*`, `/api/revenue/*`, `/api/traffic/*`, `/api/search/*`, `/api/summary`
- **38개 사이트** 레지스트리 (SAP/aikorea24 미포함)
- **analytics_collector.py:** GA4/GSC/AdSense/Bing 수집 완전 구현

### 품질 검증 현황 (`shared/post_validator.py`)
| 검증 항목 | 대상 | 상태 |
|----------|------|------|
| CTA HTML | Travel blogs | ✅ 구현 |
| `{{}}` 빈 템플릿 | 전체 | ✅ 구현 |
| og:image 썸네일 | 전체 | ✅ 구현 |
| "지도에서 보기" 평문 | 전체 | ✅ 구현 |
| 최소 본문 500자 | 전체 | ✅ 구현 |
| 가독성 점수 | 전체 | ✅ 구현 |
| **키워드 커버리지** | 전체 | ✅ 구현 (기술 식별자 제외 로직 추가됨) |

### Hugo Writer Shortcode 변환 (`shared/publishers/hugo_writer.py`)
- `_convert_inline_md_to_html()` — **bold, strike, italic, inline code**를 HTML 태그로 변환
- **적용 범위:** frontmatter 필드(title, description, category, tags) + lead paragraph + body 전체
- **보호:** 코드 블록(` ``` `) 내부 제외
- **한계:** 이미 발행된 `content/posts/**/index.md` 레거시 파일은 변환되지 않음 (Phase 13에서 리메디에이션 예정)

---

## 2. Data Sources & Metrics Schema

### 2.1 품질 메트릭 분류

| 카테고리 | 메트릭 | 수집 소스 | 수집 시점 |
|----------|--------|-----------|-----------|
| **마크다운 렌더링** | raw_bold_count, raw_italic_count, raw_strike_count, raw_code_count | Phase 13 baseline + Hugo build scan | 발행 시 + 일일 스캔 |
| **구조적 완전성** | has_cta, has_og_image, has_map_text, min_length_pass, empty_template_count | `post_validator.py` | 발행 후 즉시 |
| **콘텐츠 품질** | readability_score, keyword_coverage_ratio, content_length, paragraph_count | `post_validator.py` | 발행 후 즉시 |
| **Shortcode 변환** | shortcode_conversion_rate (lead, figure, gallery, accordion, chart) | `hugo_writer.py` 호출 로그 | 발행 시 |
| **Hugo 빌드** | build_success, build_warnings, build_errors, build_time_ms | Hugo CLI stdout/stderr | 배포 시 |

### 2.2 제안 스키마: `quality.db` (SQLite)

```sql
CREATE TABLE article_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blog_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    title TEXT,
    published_at TEXT NOT NULL,
    -- 마크다운 렌더링
    raw_bold_count INTEGER DEFAULT 0,
    raw_italic_count INTEGER DEFAULT 0,
    raw_strike_count INTEGER DEFAULT 0,
    raw_code_count INTEGER DEFAULT 0,
    -- 구조적 완전성
    has_cta INTEGER DEFAULT 0,
    has_og_image INTEGER DEFAULT 0,
    has_map_text INTEGER DEFAULT 0,
    min_length_pass INTEGER DEFAULT 0,
    empty_template_count INTEGER DEFAULT 0,
    -- 콘텐츠 품질
    readability_score REAL,
    keyword_coverage_ratio REAL,
    content_length INTEGER,
    paragraph_count INTEGER,
    -- Shortcode
    lead_shortcode INTEGER DEFAULT 0,
    figure_shortcode_count INTEGER DEFAULT 0,
    gallery_shortcode_count INTEGER DEFAULT 0,
    accordion_shortcode_count INTEGER DEFAULT 0,
    chart_shortcode_count INTEGER DEFAULT 0,
    -- Hugo 빌드
    build_success INTEGER DEFAULT 1,
    build_warnings INTEGER DEFAULT 0,
    build_errors INTEGER DEFAULT 0,
    build_time_ms INTEGER DEFAULT 0,
    -- 메타
    collected_at TEXT DEFAULT (datetime('now')),
    UNIQUE(blog_id, slug)
);

CREATE INDEX idx_quality_blog_date ON article_quality(blog_id, published_at);
CREATE INDEX idx_quality_collected ON article_quality(collected_at);
```

### 2.3 일일 집계 테이블: `daily_quality_summary`

```sql
CREATE TABLE daily_quality_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,  -- YYYY-MM-DD
    blog_id TEXT NOT NULL,
    total_articles INTEGER DEFAULT 0,
    avg_readability REAL,
    avg_keyword_coverage REAL,
    pct_has_cta REAL,
    pct_has_og_image REAL,
    pct_min_length_pass REAL,
    total_raw_md_issues INTEGER DEFAULT 0,
    articles_with_shortcodes INTEGER DEFAULT 0,
    build_success_rate REAL,
    UNIQUE(date, blog_id)
);

CREATE INDEX idx_dqs_date ON daily_quality_summary(date);
```

---

## 3. Pipeline Architecture Options

### Option A: Post-Publish Hook (Recommended — MVP)
```
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐
│  Pipeline   │───►│ validate_post()  │───►│ quality.db  │
│  (curation  │    │ + hugo_writer    │    │ (INSERT)    │
│   travel,   │    │ log metrics      │    └──────┬──────┘
│   stock...) │    └────────┬─────────┘           │
└─────────────┘             │                     │
                            ▼                     ▼
                   ┌──────────────────┐    ┌─────────────┐
                   │  Hugo Build      │    │  analytics  │
                   │  (capture stdout)│    │  _collector │
                   └────────┬─────────┘    │  (daily)    │
                            ▼              └─────────────┘
                   ┌──────────────────┐
                   │ quality.db       │
                   │ (UPDATE build_*) │
                   └──────────────────┘
```
**장점:** 실시간 품질 데이터, 파이프라인 수정 최소, 즉시 피드백
**단점:** Hugo 빌드 시간 측정 위해 subprocess 래퍼 필요

### Option B: Daily Batch Scan (Phase 13 스타일)
```
매일 03:00 cron ► scan_all_sites() ► quality.db (INSERT/UPDATE)
```
**장점:** 구현 단순, 기존 Phase 13 스캐너 재사용
**단점:** 실시간성 없음, 발행 시점과 수집 시점 차이

### Option C: Hybrid (Recommended for Phase 15+)
- **Phase 15 (MVP):** Option A — Post-publish hook으로 즉시 수집
- **Phase 16+:** Option B 추가 — 과거 콘텐츠 일일 재스캔으로 드리프트 감지

---

## 4. Integration Points

### 4.1 Pipeline 수정 필요 파일

| 파일 | 수정 내용 |
|------|----------|
| `pipelines/curation/pipeline.py` | `_run_inner()` 성공 시 `record_quality(blog_id, slug, metrics)` 호출 |
| `pipelines/travel/pipeline.py` | 동일 |
| `pipelines/stock/pipeline.py` (STAP) | subprocess 내부에서 품질 데이터 반환하도록 JSON 확장 |
| `shared/post_validator.py` | `validate_post_html()` → dict 반환 외에 `QualityMetrics` dataclass 추가 |
| `shared/publishers/hugo_writer.py` | shortcode 사용 여부 플래그 반환 (`used_shortcodes: set[str]`) |

### 4.2 Dashboard API 확장 (`data/dashboard/routes/api.py`)

```python
# 새로운 엔드포인트
@api_bp.route("/quality/summary")
def api_quality_summary():
    """Overview용 품질 카드: 전체 사이트 평균 readability, 커버리지, CTA 비율"""
    
@api_bp.route("/quality/by-blog")
def api_quality_by_blog():
    """블로그별 품질 점수 테이블"""
    
@api_bp.route("/quality/markdown-issues")
def api_quality_markdown():
    """마크다운 렌더링 이슈 트렌드 (30일)"""
    
@api_bp.route("/quality/shortcodes")
def api_quality_shortcodes():
    """Shortcode 사용률 by type (lead, figure, gallery...)"""
    
@api_bp.route("/quality/hugo-build")
def api_quality_build():
    """Hugo 빌드 성공률, 평균 빌드 시간, 경고/에러 추이"""
```

### 4.3 Dashboard UI 추가 (Phase 14 Wave 2 연계)

| 페이지 | 차트 | 설명 |
|--------|------|------|
| **Quality Overview** | Stat Cards + Trend | 평균 readability, keyword coverage, CTA%, og:image% |
| **Markdown Health** | Line + Bar | 일별 raw markdown 이슈 수 (bold/italic/strike/code별) |
| **Content Quality** | Scatter + Bar | 길이 vs readability, keyword coverage 분포 |
| **Shortcode Adoption** | Stacked Bar | 블로그별 shortcode 타입 사용률 |
| **Build Health** | Line + Table | 빌드 성공률, 평균 시간, 상위 경고/에러 |

---

## 5. Dependencies & Sequencing

```
Phase 13 (Hugo Markdown Fix)
    │
    ├─► baseline-findings.json → quality.db 초기 데이터 시드
    │
    ▼
Phase 14 Wave 2 (Dashboard UI) ◄── 공통: chart-helpers.js, API 패턴
    │
    ├─► /api/quality/* 엔드포인트 추가
    │
    ▼
Phase 15 (Content Quality Pipeline) — 본 페이즈
    │
    ├─► 15-01: quality.db 스키마 + 기록 모듈 (shared/quality_recorder.py)
    ├─► 15-02: 파이프라인 후크 통합 (curation, travel, stock)
    ├─► 15-03: Hugo 빌드 래퍼 + 메트릭 수집
    ├─► 15-04: Dashboard API + Quality 페이지 UI
    └─► 15-05: 일일 집계 크론 + Phase 13 리메디에이션 후 재스캔 검증
```

---

## 6. Risk Mitigation

| 리스크 | 가능성 | 영향 | 완화 |
|--------|--------|------|------|
| 파이프라인별 품질 데이터 포맷 불일치 | High | Medium | 공통 `QualityMetrics` dataclass 정의, 파이프라인별 adapter 패턴 |
| Hugo 빌드 시간 측정 오차 | Medium | Low | subprocess `time.monotonic()` 래퍼, 타임아웃 300초 |
| 레거시 콘텐츠 재스캔 시 DB 중복 | Medium | Medium | UNIQUE(blog_id, slug) + UPSERT 패턴 |
| 품질 데이터로 인한 analytics.db 비대 | Low | Medium | 별도 `quality.db` 분리, 일일 집계 후 상세 데이터 90일 후 아카이브 |
| Shortcode 변환 실패 미감지 | Medium | High | `hugo_writer.py`에서 사용된 shortcode 타입 명시적 반환 |

---

## 7. Success Criteria (Phase 15 Complete)

1. **품질 DB 운영:** `quality.db`에 발행 글당 품질 메트릭 자동 기록 (99%+ 성공률)
2. **API 완성:** `/api/quality/*` 5개 엔드포인트 정상 응답, 대시보드 차트 렌더링
3. **파이프라인 통합:** curation, travel, stock 3개 파이프라인에서 품질 데이터 자동 수집
4. **Hugo 빌드 메트릭:** 빌드 성공률, 평균 시간, 경고/에러 추이 대시보드 표시
5. **Phase 13 검증:** 리메디에이션 후 재스캔 시 raw markdown 이슈 0개 확인
6. **알림 연동:** readability < 0.3 또는 CTA 누락 시 텔레그램 알림 (기존 `notify_down.py` 확장)

---

## 8. Next Actions

1. `/gsd-plan-phase 15 --skip-research` 실행하여 상세 PLAN.md 생성
2. `shared/quality_recorder.py` 모듈 신규 작성 (공통 스키마, 기록 함수)
3. `pipelines/curation/pipeline.py` 첫 번째 통합 테스트
4. `data/dashboard/routes/api.py`에 `/api/quality/*` 엔드포인트 추가