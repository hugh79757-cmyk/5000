# Phase 13 — 통합 대시보드: Research

**Date:** 2026-07-07
**Researcher:** Sisyphus (manual research — 25+ files, 5 DB queries, 3 project analyses)

---

## 1. 프로젝트 현황 매트릭스

### Core Publishing Projects

| 프로젝트 | 경로 | 발행 채널 | 글 수 (content.db) | GA4 트래킹 | 애드센스 | 대시보드 존재 |
|----------|------|-----------|--------------------|------------|----------|--------------|
| **5000 (Hub)** | `~/5000/` | 37 Hugo blogs | 3,845건 ✅ | ✅ GA4 33개 블로그 | ✅ 102 도메인 | ❌ 없음 |
| **CUAP** | ← 5000 내부 | car-hugo 외 | ✅ 포함 | ✅ 포함 | ✅ 포함 | — |
| **TAP** | ← 5000 내부 | travel1-4, heritage-hugo | 1,419건 | ✅ 포함 | ✅ 포함 | — |
| **STAP** | ← 5000 내부 | stock, etf, dividend 외 | 338건 | ✅ 포함 | ✅ 포함 | — |
| **RAP** | ← 5000 내부 | rap1-5-hugo | 441건 | ✅ 포함 | ✅ 포함 | — |
| **SEAP** | ← 5000 내부 | senior-hugo 외 | 181건 | ✅ 포함 | ✅ 포함 | — |
| **CAP** | ← 5000 내부 | appliance, baby, fitness 외 | 251건 | ✅ 포함 | ✅ 포함 | — |
| **LAP/ETAP/GAP** | ← 5000 내부 | laptop, ev, guide 외 | 포함 | ✅ 포함 | ✅ 포함 | — |
| **SAP** | `~/SAP/` | 8 Hugo + 2 Blogger | **자체 DB** (publish_log.db) | **일부** | **일부** | ❌ 없음 |
| **aikorea24** | `~/aikorea24/` | Astro SSR (CF Pages) | **D1 별도** | ✅ 7일치 | ❌ 미확인 | ❌ 없음 |
| **money-aikorea24** | `~/money-aikorea24/` | Astro Static (CF Pages) | **MD 파일** | ❌ 미확인 | ❌ 미확인 | ❌ 없음 |

### Existing Data Infrastructure

#### 5000 — data/content.db (articles)
- 37개 블로그, 3,845건 published articles
- Schema: `id, blog_id, title, slug, status, category, tags, data_source, source_id, published_url, published_at, created_at, sigungu`
- All 5000 sub-projects (CUAP/TAP/STAP/RAP/SEAP/CAP/LAP/ETAP/GAP) use this single DB

#### 5000 — data/analytics.db
| 테이블 | 레코드 | 커버리지 |
|--------|--------|---------|
| `ga4_daily` | 115건 | 33개 블로그, 2026-04-03~04-17 |
| `adsense_daily` | 1,317건 | 102개 도메인 (rotcha.kr/techpawz.com/informationhot.kr/aikorea24.kr) |
| `gsc_daily_summary` | — | Google Search Console clicks/impressions/ctr/position |
| `bing_daily_summary` | — | Bing clicks/impressions |
| `blog_efficiency` | — | Composite score + grade per blog per date |
- **GA4 수집 4월 중단됨** — daily_sync.py 또는 blogdex daily_sync가 멈춘 것으로 추정

#### SAP — data/publish_log.db (독립)
- 10개 sports 블로그 발행 이력
- blogdex의 collect 범위에 포함되어 있는지 확인 필요

#### blogdex — Cloudflare D1 + Workers API (기존 인프라)
- **14개 블로그, 5,208개 글** 수집 완료 (v0.1.0)
- GA4 15개 속성 조회 가능 (perf.py)
- GSC, AdSense, Bing 데이터 집계 중
- Workers API: `blogdex-api.hugh79757.workers.dev`
- React 대시보드: Coaching, Revenue, Opportunity, Keyword, Site, Scout, CPC Hint, Senior (8페이지)
- **핵심 인사이트**: blogdex는 GA4/GSC/AdSense/Bing 수집 파이프라인을 이미 완성함
- 4개 루트 도메인(`rotcha.kr`, `techpawz.com`, `informationhot.kr`, `aikorea24.kr`) × 80+ 서브도메인 커버

#### aikorea24 — Cloudflare D1 (독립)
- Astro SSR 사이트, D1 데이터베이스
- 뉴스 수집 파이프라인: news_collector.py → D1 news 테이블
- GA4 트래킹은 blogdex analytics.db에 일부 존재 (7일)
- content.db에는 **미포함**

#### money-aikorea24 — Astro Content Collections
- `src/content/blog/` 마크다운 파일로 발행
- 5000/content.db 미포함
- GA4/AdSense 트래킹 미확인
- deploy.sh로 Cloudflare Pages 배포

---

## 2. 핵심 이슈

### 이슈 1: 발행 이력 분산
- 5000 (CUAP/TAP/STAP/RAP/SEAP/CAP etc.) → content.db ✅ (통합)
- SAP → publish_log.db (별도) ❌
- aikorea24 → D1 (별도) ❌
- money-aikorea24 → MD files only ❌

### 이슈 2: GA4 수집 중단
- analytics.db ga4_daily 마지막 데이터: 2026-04-17
- 일평균 약 10일치만 존재 (블로그당)
- blogdex daily_sync.py가 멈춘 것으로 보임

### 이슈 3: blogdex 인프라 활용 vs 신규 구축
- blogdex에 GA4/GSC/AdSense 수집 파이프라인, Workers API, React 대시보드 모두 존재
- 하지만 사용자 요청: **Flask + Chart.js** 신규 대시보드
- 결정: blogdex 데이터 수집 패턴을 참고하되, Flask 기반 신규 대시보드 구축

### 이슈 4: aikoera24 / money-aikorea24 연결
- 두 사이트 모두 5000 인프라 바깥에 있음
- 발행 이력 수집을 위한 별도 파이프라인 필요
- aikorea24: D1 쿼리 또는 blogdex sync_astro.py 활용 가능
- money-aikorea24: 파일 스캔 기반 수집

---

## 3. 데이터 소스 매핑

| 대시보드 위젯 | 데이터 소스 | 수집 방식 |
|-------------|-----------|---------|
| 전체 발행 현황 (일/주/월) | content.db articles 테이블 | SQLite 직접 쿼리 |
| 블로그별 발행 수 (막대) | content.db + SAP publish_log.db | SQLite UNION |
| GA4 트래픽 (세션/사용자) | analytics.db ga4_daily | SQLite (blogdex perf.py 패턴) |
| 애드센스 수익 (일/주/월) | analytics.db adsense_daily | SQLite (blogdex adsense.py 패턴) |
| GSC 검색 실적 | analytics.db gsc_daily_summary | SQLite (blogdex gsc.py 패턴) |
| Bing 검색 실적 | analytics.db bing_daily_summary | SQLite |
| 블로그 효율 점수 | analytics.db blog_efficiency | SQLite |
| SAP 발행 현황 | SAP data/publish_log.db | SQLite 직접 (또는 통합 수집) |
| aikorea24 발행 현황 | aikorea24 D1 news 테이블 | D1 쿼리 → JSON (Workers 경유) |
| money-aikorea24 발행 현황 | MD 파일 목록 | 파일 스캔 또는 Hugo sitemap |
| 사이트 헬스 체크 | 각 사이트 HTTP 200 확인 | requests (Flask → 각 사이트) |
| 파이프라인 상태 | dispatcher.py / scheduler.log | 로그 파일 파싱 |

---

## 4. 아키텍처 제안

**결정:** Flask + Chart.js (사용자 선택)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Flask Dashboard (5000/data/dashboard/)        │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │ Overview │  │ Revenue  │  │ Traffic  │  │ Site Health   │   │
│  │   Page   │  │   Page   │  │   Page   │  │    Page       │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬────────┘   │
│       └──────────────┴────────────┴────────────────┘            │
│                            │                                     │
│                    ┌───────┴────────┐                            │
│                    │  Chart.js      │                            │
│                    │  visualization │                            │
│                    └───────┬────────┘                            │
│                            │ Flask routes (JSON API)             │
└────────────────────────────┼────────────────────────────────────┘
                             │
         ┌───────────────────┼──────────────────────┐
         ▼                   ▼                      ▼
   ┌────────────┐   ┌──────────────┐   ┌──────────────────────┐
   │ content.db │   │ analytics.db │   │ SAP/publish_log.db  │
   │ (5000 hub) │   │ (5000 hub)   │   │ (직접 연결)          │
   └────────────┘   └──────────────┘   └──────────────────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
              ┌──────────┐   ┌────────────────┐
              │ blogdex  │   │ aikorea24 D1   │
              │ D1 (참고)│   │ (Workers API)   │
              └──────────┘   └────────────────┘
```

### Key Design Decisions

1. **Flask 서버**를 5000 내부에 배치 (기존 Python 인프라와 일관성)
2. **SQLite 직접 연결** — content.db + analytics.db + SAP publish_log.db는 로컬 SQLite
3. **blogdex D1** — GA4/GSC/AdSense 수집 패턴만 참고, data는 5000/analytics.db 직접 사용
4. **aikorea24 D1** — Workers API를 통해 데이터 수집
5. **money-aikorea24** — 파일 기반 수집 또는 Astro sitemap 파싱
6. **Chart.js** — Flask Jinja2 템플릿에 포함 (SPA 아님)

### Data Collection Enhancement

Phase 13의 첫 번째 Wave는 **analytics.db 데이터 수집 재개**여야 함:
- blogdex의 daily_sync.py 패턴을 5000/shared/analytics_collector.py로 포팅
- SAP sport blogs + aikorea24 + money-aikorea24를 GA4/GSC/AdSense 수집 대상에 추가
- 매일 1회 cron으로 analytics.db 업데이트
