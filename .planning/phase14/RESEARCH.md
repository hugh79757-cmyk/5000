# Phase 14 Research: Cross-Project Content Quality Dashboard (Unified Dashboard Wave 2+3)

**Date:** 2026-07-08
**Researcher:** Manual analysis (subagent unavailable)
**Scope:** Phase 14 — 다음 로드맵 페이즈로, Phase 13(Hugo Markdown Audit) 완료 후 진행. 기존 `.planning/phase13/` Unified Dashboard Wave 1 완료 상태에서 Wave 2(UI), Wave 3(Ops) 실행.

---

## 1. Current State Assessment

### 1.1 What Works (Wave 1 Complete ✅)

| Component | Status | Evidence |
|-----------|--------|----------|
| `analytics_collector.py` | ✅ 완전 구현 | GA4/GSC/AdSense/Bing 4개 API 수집, multi-account OAuth, WAL+timeout, DB 마이그레이션 |
| `data/dashboard/app.py` | ✅ 실행 중 | Flask + Blueprint, localhost:5050 기동 확인 |
| `/api/health` | ✅ 38/38 온라인 | 38개 사이트 HTTP 체크, ThreadPoolExecutor 병렬 처리 |
| `/api/posts/*` | ✅ 작동 | content.db에서 일/주/월/누적 발행 수 조회 |
| `/api/revenue/*` | ✅ 작동 | analytics.db adsense_daily에서 수익/RPM/CTR 조회 |
| `/api/traffic/*` | ✅ 작동 | analytics.db ga4_daily에서 세션/사용자/PV/이탈률/참여율/광고수익 조회 |
| `/api/search/*` | ✅ 작동 | GSC/Bing/효율 점수 조회 |
| `/api/summary` | ✅ 작동 | Overview 카드용 통합 지표 (total_posts=8060, today=25, revenue=$11.34, sessions=48) |
| `SITES` 레지스트리 | ✅ 38개 사이트 | api.py에 하드코딩된 38개 활성 사이트 (SAP/aikorea24 미포함) |
| Sync scripts | ✅ 구현됨 | sync_sap.py, sync_aikorea24.py, sync_money_aikorea24.py 존재 |
| Launchd watchdogs | ✅ 등록됨 | com.5000.analytics.plist (6시간), com.5000.analytics.watchdog.plist (30분) |

### 1.2 What's Missing (Wave 2 — Dashboard UI)

| Page | Template | JS Logic | Status |
|------|----------|----------|--------|
| **Overview** | index.html (스켈레톤) | dashboard.js `loadSummary()`, `loadPostsChart()`, `loadRevenueChart()`, `loadTopPosts()`, `loadHealth()` | **50% — 차트 렌더링 미완성** |
| **Revenue** | revenue.html (스켈레톤) | `loadRevenuePage()` — 차트 생성 로직만 있음, 데이터 fetch 미구현 | **30% — 차트 데이터 바인딩 없음** |
| **Traffic** | traffic.html (스켈레톤) | `loadTrafficPage()` — 동일 | **30%** |
| **Search** | search.html (스켈레톤) | `loadSearchPage()` — 동일 | **30%** |
| **Health** | health.html (완성도 높음) | `loadHealth()` — 테이블 + 그리드 모두 구현 | **90% — 동작 확인 필요** |

**공통 문제:** `dashboard.js`에 차트 생성 함수들이 정의되어 있으나, **API에서 받은 데이터를 Chart.js 인스턴스에 바인딩하는 로직이 빠져 있음**. 템플릿은 `<canvas>`만 있고 JS에서 차트를 그리는 코드가 불완전.

### 1.3 What's Missing (Wave 3 — External Integration + Ops)

| Task | Script | Status | Blocker |
|------|--------|--------|---------|
| SAP publish_log → dashboard DB | sync_sap.py | ✅ 구현됨 (rowcount fix) | SAP DB 경로 확인 필요 |
| aikorea24 D1 → dashboard | sync_aikorea24.py | ✅ 구현됨 (644건 동기화) | Workers API 경유 필요 |
| money-aikorea24 MD → dashboard | sync_money_aikorea24.py | ✅ 구현됨 (185건 동기화) | 파일 스캔 방식 확인 |
| Launchd 대시보드 서버 등록 | com.5000.dashboard.plist | ❌ 미생성 | 앱 경로, venv python 확정 필요 |
| Telegram 다운 알림 | notify_down.py | ✅ 구현됨 | 테스트 필요 |
| GSC 누락 사이트 등록 | — | ❌ 미완료 | GA4_PROPERTIES에 None인 사이트 많음 |

---

## 2. Detailed Task Breakdown

### Wave 2 — Dashboard UI (5 Tasks)

#### Task 14-01: Overview Page Complete (Stat Cards + Charts)
- **Files:** `templates/index.html`, `static/js/dashboard.js` (확장)
- **Charts needed:**
  - Stat Cards: Total Posts, Today Posts, Monthly Revenue, Monthly Sessions (✅ API ready)
  - Posts Trend (Line, 30d) — `/api/posts/daily?days=30`
  - Revenue Trend (Line, 30d) — `/api/revenue/daily?days=30`
  - Top 10 Blogs by Posts (Horizontal Bar) — `/api/posts/total`
  - Site Health Mini Grid — `/api/health` (이미 `loadHealth()`로 구현됨)
- **Acceptance:** `/` 접속 시 4개 카드 + 3개 차트 + 미니 그리드 모두 렌더링, 오류 없음

#### Task 14-02: Revenue Page Complete
- **Files:** `templates/revenue.html`, `static/js/dashboard.js` (`loadRevenuePage`)
- **Charts:**
  - Daily Earnings (Line, 90d) — `/api/revenue/daily?days=90`
  - RPM Trend (Line, 90d) — `/api/revenue/rpm?days=90`
  - CTR Trend (Line, 90d) — 동일 엔드포인트
  - Revenue by Domain (Bar, Top 20) — `/api/revenue/by-domain?days=30`
  - Weekly Comparison (Bar, current vs prev) — 계산 로직 추가 필요
- **Acceptance:** `/revenue` 페이지 5개 차트 렌더링, 호버 툴팁 정상

#### Task 14-03: Traffic Page Complete
- **Files:** `templates/traffic.html`, `static/js/dashboard.js` (`loadTrafficPage`)
- **Charts:**
  - Sessions + Users (Dual Line, 30d) — `/api/traffic/daily?days=30`
  - Page Views (Area, 30d) — 동일
  - Bounce Rate + Engagement Rate (Dual Line, 30d) — 동일
  - Traffic by Blog (Bar, Top 20) — `/api/traffic/by-blog?days=30`
  - Ad Revenue vs Traffic Scatter — 결합 쿼리 또는 클라이언트 병합
- **Acceptance:** `/traffic` 5개 차트 렌더링

#### Task 14-04: Search Page Complete
- **Files:** `templates/search.html`, `static/js/dashboard.js` (`loadSearchPage`)
- **Charts:**
  - GSC Clicks + Impressions (Dual Line, 30d) — `/api/search/gsc/daily?days=30`
  - Avg Position Trend (Inverted Line, 90d) — 동일 엔드포인트
  - CTR Trend (Line, 30d) — 동일
  - Bing Clicks + Impressions (Dual Line, 30d) — `/api/search/bing/daily?days=30`
  - Blog Efficiency Scores (Horizontal Bar, All) — `/api/search/efficiency?days=30`
  - GSC vs Bing Comparison (Grouped Bar) — 클라이언트 병합
- **Acceptance:** `/search` 6개 차트 렌더링, 효율 점수 색상 코딩(녹/황/적) 정상

#### Task 14-05: Health Page Polish + Auto-refresh
- **Files:** `templates/health.html` (이미 90% 완료)
- **Improvements:**
  - 필터 버튼: All / Online / Offline (JS에서 구현 필요)
  - 자동 새로고침 30초 (이미 `setInterval(loadHealth, 30000)` 있음)
  - 응답시간 기준 정렬 옵션
  - 오프라인 사이트 Telegram 알림 연동 (`notify_down.py` 호출)
- **Acceptance:** 필터 작동, 30초 자동 갱신, 오프라인 시 알림 전송

---

### Wave 3 — External Integration + Operations (4 Tasks)

#### Task 14-06: SAP Publish Log Integration
- **Files:** `scripts/sync_sap.py` (이존재), `scripts/sync_sap_to_dashboard.py` (신규 권장)
- **Logic:**
  1. SAP `data/publish_log.db` → `SELECT blog_id, title, created_at, status FROM publish_log`
  2. Dashboard 전용 `data/dashboard/data/sap_posts.db` 캐시 테이블 생성/업데이트
  3. `/api/posts` 엔드포인트에서 UNION으로 SAP 데이터 포함
  4. 매시간 cron 실행 (`launchd` 또는 `crontab`)
- **Acceptance:** SAP 10개 블로그 발행 이력이 `/api/posts/total`에 표시, 대시보드 Overview에 통합

#### Task 14-07: aikorea24 + money-aikorea24 Integration
- **aikorea24:**
  - Option 1: blogdex Workers API (`blogdex-api.hugh79757.workers.dev`) 경유 — 기존 `sync_astro.py` 활용
  - Option 2: Cloudflare D1 직접 쿼리 (`wrangler d1 execute`)
  - Option 3: sitemap.xml 파싱 (`https://aikorea24.kr/sitemap-index.xml`)
- **money-aikorea24:**
  - `~/money-aikorea24/src/content/blog/` MD 파일 스캔 + frontmatter 파싱
  - 또는 `https://persona.aikorea24.kr/sitemap.xml` 파싱
- **Acceptance:** 두 사이트 발행 현황이 `/api/posts` 및 Overview에 표시

#### Task 14-08: Launchd Dashboard Server + Telegram Alerts
- **Files:** `~/Library/LaunchAgents/com.5000.dashboard.plist`, `scripts/notify_down.py`
- **Launchd config:**
  - `ProgramArguments`: [`/Users/twinssn/Projects/5000/venv/bin/python`, `/Users/twinssn/Projects/5000/data/dashboard/app.py`]
  - `RunAtLoad: true`, `KeepAlive: true`, `WorkingDirectory: /Users/twinssn/Projects/5000`
- **Telegram:** `shared/telegram_notifier.py` 재사용 — health check에서 status != 200 사이트 감지 시 알림
- **Logging:** `/Users/twinssn/Projects/5000/logs/dashboard.log` (rotating)
- **Acceptance:** `launchctl list | grep dashboard` PID 표시, 사이트 다운 시 텔레그램 수신, 로그 정상 기록

#### Task 14-09: GSC Missing Sites Registration
- **Issue:** `GA4_PROPERTIES`에 38개 사이트 중 다수가 `None` (GA4 property ID 미등록)
- **Action:** blogdex `analytics.py` 또는 `daily_sync.py` 패턴으로 속성 ID 자동 탐색 후 등록
- **Priority:** Low (데이터 수집 우선순위 낮음)

---

## 3. Dependencies & Sequencing

```
Wave 2 (Parallel per page):
  14-01 Overview ──┐
  14-02 Revenue ───┤
  14-03 Traffic ───┤ (모두 14-01 완료 후 공통 차트 유틸 재사용 가능)
  14-04 Search ────┘
  14-05 Health ──── (독립적, Health page 이미 90%)

Wave 3 (Sequential - 외부 의존성):
  14-06 SAP sync → 14-07 aikorea24/money sync → 14-08 launchd+telegram → 14-09 GSC 등록
```

---

## 4. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Chart.js 버전/문법 불일치 | Medium | High | `dashboard.js`에서 기존 차트 패턴(`charts.posts`, `charts.revenue` 등) 통일, destroy-before-create |
| API 응답 지연으로 페이지 렌더링 차단 | Low | Medium | `Promise.allSettled`로 개별 차트 실패 시 나머지 렌더링, 로딩 스켈레톤 표시 |
| SAP/aikorea24 DB 스키마 변경 | Medium | Medium | sync 스크립트에 스키마 버전 체크, 실패 시 알림 |
| Launchd venv python 경로 문제 | Low | High | `which python3` 확인 후 절대 경로 사용, `PATH` 환경변수 명시 |
| Hugo markdown 렌더링 이슈(Phase 13) 영향 | High | Medium | 콘텐츠 품질 지표(글자 수, 마크다운 잔재)는 별도 검증 파이프라인 필요 |

---

## 5. Recommended Approach

**MVP Vertical Slices:** 각 페이지를 독립적으로 완료하여 즉시 가치를 창출.
1. **14-01 Overview** → 가장 많이 보는 페이지, 임원/운영자 핵심 지표
2. **14-02 Revenue** → 수익 모니터링 직접적 가치
3. **14-03 Traffic** → 트래픽 추이 확인
4. **14-04 Search** → SEO 성과 추적
5. **14-05 Health** → 운영 안정성 (이미 90%)

**공통 유틸리티 먼저 구축:** `dashboard.js`에 `createLineChart()`, `createBarChart()`, `createDualLineChart()` 헬퍼 함수 추출 → 중복 제거, 일관성 확보.

---

## 6. File Inventory

### Existing (Wave 1 완료)
```
/Users/twinssn/Projects/5000/
├── shared/analytics_collector.py          # 1010 lines — 완전 구현
├── data/dashboard/app.py                  # 58 lines — Flask app
├── data/dashboard/routes/api.py           # 439 lines — 6개 API 그룹
├── data/dashboard/routes/pages.py         # 30 lines — 5개 페이지 라우트
├── data/dashboard/templates/base.html     # 50 lines — Bootstrap 5 + Chart.js CDN
├── data/dashboard/templates/index.html    # 32 lines — 스켈레톤
├── data/dashboard/templates/revenue.html  # 30 lines — 스켈레톤
├── data/dashboard/templates/traffic.html  # 30 lines — 스켈레톤
├── data/dashboard/templates/search.html   # 41 lines — 스켈레톤
├── data/dashboard/templates/health.html   # 99 lines — 90% 완료
├── data/dashboard/static/js/dashboard.js  # 800+ lines — 차트 로직 부분 구현
├── data/dashboard/scripts/sync_sap.py     # 128 lines
├── data/dashboard/scripts/sync_aikorea24.py  # 119 lines
├── data/dashboard/scripts/sync_money_aikorea24.py  # 108 lines
├── data/dashboard/scripts/notify_down.py  # 68 lines
├── ~/Library/LaunchAgents/com.5000.analytics.plist
├── ~/Library/LaunchAgents/com.5000.analytics.watchdog.plist
```

### To Create/Complete (Wave 2+3)
```
├── data/dashboard/static/css/dashboard.css     # 커스텀 스타일 (최소)
├── data/dashboard/static/js/chart-helpers.js   # (선택) 차트 팩토리 함수 분리
├── ~/Library/LaunchAgents/com.5000.dashboard.plist  # 신규
├── scripts/sync_sap_to_dashboard.py            # SAP 통합용 신규
├── .planning/phase14/CONTEXT.md                # 본 연구 기반
├── .planning/phase14/PLAN.md                   # 상세 실행 계획
├── .planning/phase14/RESEARCH.md               # 이 파일
```

---

## 7. Success Criteria (Phase 14 Complete)

1. ✅ **Wave 2**: `/`, `/revenue`, `/traffic`, `/search`, `/health` 5개 페이지 모두 차트 정상 렌더링, 오류 없음
2. ✅ **Wave 3**: SAP + aikorea24 + money-aikorea24 발행 현황이 대시보드 API에 통합 표시
3. ✅ **Ops**: `launchctl list | grep dashboard` PID 확인, 사이트 다운 시 텔레그램 알림 수신, `logs/dashboard.log` 정상 기록
4. ✅ **Integration**: Phase 13 Hugo 마크다운 렌더링 수정 후, 새 발행글의 콘텐츠 품질 지표(글자 수, 마크다운 잔재율)가 대시보드에 반영되는 파이프라인 연결

---

## 8. Next Actions

1. `/gsd-plan-phase 14` 실행하여 상세 `PLAN.md` 생성
2. `14-01 Overview`부터 순차 구현 (chart-helpers.js 공통 유틸 먼저)
3. 각 태스크 완료 시 `curl /api/...` + 브라우저 렌더링 검증