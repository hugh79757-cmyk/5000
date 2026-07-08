# Phase 15 — Content Quality Pipeline Integration

**Phase Goal:** Phase 13 Hugo Markdown 수정 결과 + Phase 14 Unified Dashboard → **콘텐츠 품질 파이프라인 통합** — 발행 글당 품질 메트릭 자동 수집, 대시보드 시각화, 일일 집계

**Architecture:** Post-publish hook + SQLite quality.db + Flask Dashboard API  
**Mode:** mvp (vertical slice — 품질 데이터 수집 → API → UI)  
**Total Tasks:** 5  
**Dependencies:** Phase 13 완료 (Hugo 마크다운 렌더링 수정), Phase 14 Wave 2 완료 (Dashboard UI)

---

## 15-01: quality.db 스키마 + 기록 모듈

**Files:**
- `shared/quality_recorder.py` (new)
- `data/quality.db` (auto-created)

**Schema:**
```sql
CREATE TABLE article_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blog_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    title TEXT,
    published_at TEXT NOT NULL,
    raw_bold_count INTEGER DEFAULT 0,
    raw_italic_count INTEGER DEFAULT 0,
    raw_strike_count INTEGER DEFAULT 0,
    raw_code_count INTEGER DEFAULT 0,
    has_cta INTEGER DEFAULT 0,
    has_og_image INTEGER DEFAULT 0,
    has_map_text INTEGER DEFAULT 0,
    min_length_pass INTEGER DEFAULT 0,
    empty_template_count INTEGER DEFAULT 0,
    readability_score REAL,
    keyword_coverage_ratio REAL,
    content_length INTEGER,
    paragraph_count INTEGER,
    lead_shortcode INTEGER DEFAULT 0,
    figure_shortcode_count INTEGER DEFAULT 0,
    gallery_shortcode_count INTEGER DEFAULT 0,
    accordion_shortcode_count INTEGER DEFAULT 0,
    chart_shortcode_count INTEGER DEFAULT 0,
    build_success INTEGER DEFAULT 1,
    build_warnings INTEGER DEFAULT 0,
    build_errors INTEGER DEFAULT 0,
    build_time_ms INTEGER DEFAULT 0,
    collected_at TEXT DEFAULT (datetime('now')),
    UNIQUE(blog_id, slug)
);

CREATE TABLE daily_quality_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
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
```

**Functions:**
- `record_quality(blog_id, slug, title, published_at, metrics: dict)` — UPSERT article_quality
- `get_quality_summary(blog_id=None, days=30)` — 일일 집계 조회
- `get_blog_quality_scores()` — 블로그별 평균 품질 점수

**Success Criteria:**
- `python3 -c "from shared.quality_recorder import record_quality; print('OK')"` 성공
- `quality.db` 스키마 생성 확인

---

## 15-02: 파이프라인 후크 통합

**Files:**
- `pipelines/curation/pipeline.py` (modify `_run_inner()`)
- `pipelines/travel/pipeline.py` (modify publish logic)
- `shared/post_validator.py` (add `QualityMetrics` dataclass)

**Logic:**
```python
# post_validator.py
@dataclass
class QualityMetrics:
    readability_score: float
    keyword_coverage_ratio: float
    content_length: int
    paragraph_count: int
    has_cta: bool
    has_og_image: bool
    has_map_text: bool
    min_length_pass: bool
    empty_template_count: int

# pipeline.py _run_inner() 성공 시
from shared.quality_recorder import record_quality
from shared.post_validator import QualityMetrics

metrics = QualityMetrics(
    readability_score=result.get("readability", 0),
    keyword_coverage_ratio=result.get("keyword_coverage", 0),
    content_length=len(body),
    paragraph_count=body.count("\n\n") + 1,
    has_cta=result.get("has_cta", False),
    has_og_image=result.get("has_og_image", False),
    has_map_text=result.get("has_map_text", False),
    min_length_pass=result.get("min_length_pass", False),
    empty_template_count=result.get("empty_template_count", 0),
)
record_quality(blog_id, slug, title, published_at, metrics.__dict__)
```

**Success Criteria:**
- curation 파이프라인 발행 후 `quality.db`에 레코드 생성 확인
- travel 파이프라인 발행 후 `quality.db`에 레코드 생성 확인

---

## 15-03: Hugo 빌드 래퍼 + 메트릭 수집

**Files:**
- `shared/hugo_builder.py` (new)
- `shared/publishers/hugo_writer.py` (modify `deploy_site()`)

**Logic:**
```python
# hugo_builder.py
import subprocess
import time

def build_site(site_path: str, timeout: int = 300) -> dict:
    start = time.monotonic()
    result = subprocess.run(
        ["/opt/homebrew/bin/hugo", "--source", site_path],
        capture_output=True, text=True, timeout=timeout
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    
    warnings = result.stderr.count("WARN")
    errors = result.stderr.count("ERROR")
    
    return {
        "build_success": result.returncode == 0,
        "build_warnings": warnings,
        "build_errors": errors,
        "build_time_ms": elapsed_ms,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
```

**Success Criteria:**
- `python3 -c "from shared.hugo_builder import build_site; print('OK')"` 성공
- 실제 Hugo 빌드 테스트 (로컬 사이트) 성공

---

## 15-04: Dashboard API + Quality 페이지 UI

**Files:**
- `data/dashboard/routes/api.py` (add `/api/quality/*` endpoints)
- `data/dashboard/templates/quality.html` (new)
- `data/dashboard/static/js/dashboard.js` (add `loadQualityPage()`)

**API Endpoints:**
```python
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
    """Shortcode 사용률 by type"""

@api_bp.route("/quality/hugo-build")
def api_quality_build():
    """Hugo 빌드 성공률, 평균 빌드 시간, 경고/에러 추이"""
```

**UI Charts:**
| Chart | Type | Spec |
|-------|------|------|
| Quality Overview Cards (4) | Text | Avg Readability, Keyword Coverage, CTA%, og:image% |
| Quality Trend (30d) | Line | readability + keyword_coverage dual axis |
| Markdown Issues (30d) | Stacked Bar | bold/italic/strike/code by day |
| Shortcode Usage | Horizontal Bar | lead/figure/gallery/accordion by blog |
| Build Health | Line + Table | success rate, avg time, warnings/errors |

**Success Criteria:**
- `/quality` 페이지 5개 차트 렌더링
- `/api/quality/summary` JSON 응답 정상

---

## 15-05: 일일 집계 크론 + Phase 13 검증

**Files:**
- `scripts/daily_quality_aggregate.py` (new)
- `~/Library/LaunchAgents/com.5000.quality-aggregate.plist` (new)

**Logic:**
```python
# daily_quality_aggregate.py
def aggregate_daily():
    """article_quality에서 daily_quality_summary 집계"""
    conn = sqlite3.connect("data/quality.db")
    
    conn.execute("""
        INSERT OR REPLACE INTO daily_quality_summary
        (date, blog_id, total_articles, avg_readability, avg_keyword_coverage,
         pct_has_cta, pct_has_og_image, pct_min_length_pass,
         total_raw_md_issues, articles_with_shortcodes, build_success_rate)
        SELECT 
            DATE(published_at) as date,
            blog_id,
            COUNT(*) as total_articles,
            AVG(readability_score) as avg_readability,
            AVG(keyword_coverage_ratio) as avg_keyword_coverage,
            SUM(has_cta) * 100.0 / COUNT(*) as pct_has_cta,
            SUM(has_og_image) * 100.0 / COUNT(*) as pct_has_og_image,
            SUM(min_length_pass) * 100.0 / COUNT(*) as pct_min_length_pass,
            SUM(raw_bold_count + raw_italic_count + raw_strike_count) as total_raw_md_issues,
            SUM(CASE WHEN lead_shortcode + figure_shortcode_count > 0 THEN 1 ELSE 0 END) as articles_with_shortcodes,
            SUM(build_success) * 100.0 / COUNT(*) as build_success_rate
        FROM article_quality
        WHERE DATE(published_at) = DATE('now', '-1 day')
        GROUP BY DATE(published_at), blog_id
    """)
    conn.commit()
    conn.close()
```

**Success Criteria:**
- `python3 scripts/daily_quality_aggregate.py` 실행 후 `daily_quality_summary` 테이블에 레코드 생성
- launchd plist 등록 (매일 03:00 실행)

---

## Dependency Graph

```
15-01: quality.db 스키마 + 기록 모듈 ──┐
                                        │
15-02: 파이프라인 후크 통합 ─────────────┤
                                        │
15-03: Hugo 빌드 래퍼 ──────────────────┤
                                        │
15-04: Dashboard API + UI ──────────────┘
                                        │
15-05: 일일 집계 크론 ───────────────────┘
```

---

## Verification Commands

### 15-01
```bash
python3 -c "from shared.quality_recorder import record_quality; print('OK')"
ls -la data/quality.db
```

### 15-02
```bash
python3 -c "
from shared.quality_recorder import record_quality
record_quality('test-hugo', 'test-slug', 'Test', '2026-01-01', {'readability_score': 0.8})
print('Recorded')
"
```

### 15-03
```bash
python3 -c "from shared.hugo_builder import build_site; print('OK')"
```

### 15-04
```bash
curl -s http://localhost:5050/api/quality/summary | python3 -m json.tool
curl -s http://localhost:5050/quality | grep -c canvas
```

### 15-05
```bash
python3 scripts/daily_quality_aggregate.py
sqlite3 data/quality.db "SELECT COUNT(*) FROM daily_quality_summary"
```
