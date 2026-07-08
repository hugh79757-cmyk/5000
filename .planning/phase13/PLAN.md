# Phase 13 — Unified Dashboard (Flask + Chart.js)

**Phase Goal:** 단일 대시보드에서 5000(Hub: CUAP/TAP/STAP/RAP/SEAP/CAP/LAP/ETAP/GAP) + SAP(Sports) + aikorea24 + money-aikorea24 = **49개 자동블로그** 통합 모니터링

**Architecture:** Flask + Chart.js (Jinja2 SSR, localhost:5050)
**Total Tasks:** 15 (Wave 1: 6, Wave 2: 5, Wave 3: 4)

---

## Wave 1 — Data Collection Restoration + Core APIs

### 1-1: analytics_collector.py — GA4/GSC/AdSense/Bing 수집 재개

**File:** `5000/shared/analytics_collector.py`

**Goal:** blogdex의 `daily_sync.py`/`perf.py`/`adsense.py`/`gsc.py` 패턴을 5000/shared/로 포팅. SAP 10개 + aikorea24 + money-aikorea24 사이트를 GA4/GSC/AdSense 수집 대상에 추가.

**Implementation:**
```python
class AnalyticsCollector:
    def collect_ga4(self, blog_ids: list[str]) -> dict
        # Google Analytics Data API v1
        # blogdex perf.py → ga4_daily INSERT OR REPLACE
    def collect_adsense(self, domains: list[str]) -> dict
        # Google AdSense API → adsense_daily INSERT
    def collect_gsc(self, blog_ids: list[str]) -> dict
        # Google Search Console API → gsc_daily_summary INSERT
    def collect_bing(self, blog_ids: list[str]) -> dict
        # Bing Webmaster API → bing_daily_summary INSERT
    def collect_all(self) -> dict
        # Run all collectors, return summary
```

**Dependencies:** `google-auth-oauthlib`, `google-api-python-client`, `requests` (already in 5000 venv?)
**Success Criteria:**
- `python -c "from shared.analytics_collector import AnalyticsCollector; c = AnalyticsCollector(); print(c.collect_all())"` runs without error
- analytics.db ga4_daily gets new data (post-Apr-17)
- SAP blog IDs included in GA4 query list

---

### 1-2: Flask 대시보드 스켈레톤

**Files:**
- `5000/data/dashboard/app.py` — Flask 앱 메인
- `5000/data/dashboard/requirements.txt` — flask, chart.js CDN (via Jinja2)
- `5000/data/dashboard/routes/__init__.py`
- `5000/data/dashboard/routes/api.py` — JSON API endpoints
- `5000/data/dashboard/routes/pages.py` — HTML page routes
- `5000/data/dashboard/templates/base.html` — Jinja2 base template

**Goal:** Flask 앱 기동. `localhost:5050` 접속 시 기본 페이지 렌더링.

**Success Criteria:**
- `cd 5000/data/dashboard && python app.py` → `* Running on http://127.0.0.1:5050`
- `curl http://localhost:5050/api/health` → `{"status": "ok"}`

---

### 1-3: /api/posts — 발행 현황 API

**File:** `5000/data/dashboard/routes/api.py` (extend)

**Endpoints:**
- `GET /api/posts/daily?days=30` — content.db (blog_id별 일간 발행 수)
- `GET /api/posts/weekly?weeks=12` — 주간 집계
- `GET /api/posts/monthly?months=6` — 월간 집계
- `GET /api/posts/total` — 블로그별 누적 발행 수 (막대차트용)

**Data source:** `5000/data/content.db` — `SELECT blog_id, date(created_at) as dt, COUNT(*) FROM articles WHERE status='published' GROUP BY blog_id, dt`

**Success Criteria:** 각 엔드포인트가 JSON 배열 반환. 프론트에서 Chart.js로 바로 소비 가능한 형태.

---

### 1-4: /api/revenue — 광고 수익 API

**File:** `5000/data/dashboard/routes/api.py` (extend)

**Endpoints:**
- `GET /api/revenue/daily?days=30` — 일간 AdSense 수익 (analytics.db adsense_daily)
- `GET /api/revenue/weekly?weeks=12`
- `GET /api/revenue/monthly?months=6`
- `GET /api/revenue/by-domain` — 도메인별 누적 수익 순위
- `GET /api/revenue/rpm` — RPM/CTR 추이

**Data source:** `5000/data/analytics.db` — `adsense_daily` 테이블

**Success Criteria:** JSON API 정상 응답. Chart.js line/bar 차트 호환.

---

### 1-5: /api/traffic + /api/search — 트래픽 & 검색 API

**File:** `5000/data/dashboard/routes/api.py` (extend)

**Endpoints:**
- `GET /api/traffic/daily?days=30` — GA4 sessions/users/page_views (analytics.db ga4_daily)
- `GET /api/traffic/by-blog` — 블로그별 트래픽 순위
- `GET /api/traffic/engagement` — 이탈률/참여율 추이
- `GET /api/search/gsc/daily?days=30` — GSC clicks/impressions/ctr/position
- `GET /api/search/bing/daily?days=30` — Bing clicks/impressions
- `GET /api/search/efficiency` — blog_efficiency 점수

**Data source:** `5000/data/analytics.db` — `ga4_daily`, `gsc_daily_summary`, `bing_daily_summary`, `blog_efficiency`

**Success Criteria:** 모든 엔드포인트 정상 응답.

---

### 1-6: /api/health — 사이트 헬스 체크 API

**File:** `5000/data/dashboard/routes/api.py` (extend)

**Endpoint:** `GET /api/health`

**Implementation:** requests.get()으로 49개 사이트 HTTP HEAD/GET → 상태 코드 + 응답 시간 기록

**Target list (49 sites):**
- 5000 travel1-4, travel, heritage (6)
- 5000 senior, senior-blogger (2)
- 5000 stock, etf, dividend, sector, ipo, finance (6)
- 5000 rap1-5 (5)
- 5000 appliance, baby, fitness, interior, laptop (5)
- 5000 ev, compare, deal, guide, tco (5)
- 5000 hotissue, info, rank, pick (4)
- 5000 kuta-wordpress, gap-kuta, gap-hugo, tvshow-blogger, ud-blogger (5)
- SAP kboplayer, kboteam, kboschedule, proto, protostats, fstats, fsched, betguide, protoking (9)
- SAP sports.rotcha.kr (Blogger), kbo.rotcha.kr (Blogger) (2)
- aikorea24.kr (1)
- persona.aikorea24.kr (1)

**Data source:** 각 사이트 도메인 매핑 필요 (blogdex에 등록된 정보 활용)

**Success Criteria:**
```json
[
  {"blog_id": "travel3-hugo", "url": "https://travel.rotcha.kr", "status": 200, "response_ms": 342},
  {"blog_id": "kboplayer", "url": "https://kboplayer.informationhot.kr", "status": 200, "response_ms": 156},
  ...
]
```

---

## Wave 2 — Dashboard UI (Visualization)

### 2-1: 메인 대시보드 페이지 (Overview)

**Files:**
- `5000/data/dashboard/templates/index.html`
- `5000/data/dashboard/static/js/dashboard.js`

**Layout (Bootstrap 5):**
```
┌─────────────────────────────────────────────┐
│  🔵 Dashboard — 49 sites    [auto-refresh]  │
├──────────┬──────────┬──────────┬────────────┤
│  Total   │  Today   │  Weekly  │   Monthly  │
│  Posts   │  Posts   │ Revenue  │  Traffic   │
│  3,845   │    12    │  $42.50  │  18,230    │
├──────────┴──────────┴──────────┴────────────┤
│  발행 추이 (Line chart, 30일)                │
├─────────────────────────────────────────────┤
│  수익 추이 (Line chart, 30일)               │
├─────────────────────────────────────────────┤
│  사이트 헬스 (Status grid, 7×7)             │
└─────────────────────────────────────────────┘
```

**Charts:** Chart.js line, bar, doughnut
- Stat cards (total posts, today's posts, weekly revenue, monthly traffic)
- Posts trend (line chart, 30d)
- Revenue trend (line chart, 30d)
- Top 10 blogs by posts (horizontal bar)
- Site health grid (color-coded: green/red/gray)

---

### 2-2: 수익 페이지 (Revenue)

**File:** `5000/data/dashboard/templates/revenue.html`

**Charts:**
- Daily earnings (line, 90d)
- RPM trend (line, 90d)
- CTR trend (line, 90d)
- Revenue by domain (bar, top 20)
- Weekly comparison (bar, current vs previous)

---

### 2-3: 트래픽 페이지 (Traffic)

**File:** `5000/data/dashboard/templates/traffic.html`

**Charts:**
- Sessions + Users (dual line, 30d)
- Page views (area, 30d)
- Bounce rate + Engagement rate (dual line, 30d)
- Traffic by blog (bar, top 20)
- Ad revenue vs traffic scatter plot

---

### 2-4: 검색 페이지 (Search)

**File:** `5000/data/dashboard/templates/search.html`

**Charts:**
- GSC clicks + impressions (dual line, 30d)
- Avg position trend (inverted line, 90d)
- CTR trend (line, 90d)
- Bing clicks + impressions (dual line, 30d)
- Blog efficiency scores (bar, all blogs)
- GSC vs Bing comparison (grouped bar)

---

### 2-5: 사이트 헬스 페이지

**File:** `5000/data/dashboard/templates/health.html`

**Features:**
- 전체 현황 요약 (Online/Offline/Unknown 카운트)
- 49개 사이트 그리드 (7×7)
- 각 사이트: blog_id, 도메인, 상태코드, 응답시간, 마지막 체크 시간
- 필터: All / Online / Offline
- 자동 새로고침 30초

---

## Wave 3 — External Site Integration + Operations

### 3-1: SAP publish_log.db 통합

**File:** `5000/data/dashboard/scripts/sync_sap.py`

**Goal:** SAP publish_log.db 데이터를 주기적으로 읽어서 dashboard 전용 집계 테이블에 저장.

**Implementation:**
- SAP `data/publish_log.db` → `SELECT blog_id, title, created_at, status FROM publish_log`
- 5000 `data/dashboard/data/sap_posts.db`에 캐시
- 매시간 sync (cron)

**Success Criteria:** SAP 10개 블로그 발행 이력이 /api/posts에 통합되어 표시됨.

---

### 3-2: aikorea24 통합

**File:** `5000/data/dashboard/scripts/sync_aikorea24.py`

**Goal:** aikorea24 D1 DB (Cloudflare) → dashboard 데이터 수집.

**Options (in order of preference):**
1. blogdex Workers API (`blogdex-api.hugh79757.workers.dev`) 경유 — 이미 sync_astro.py 존재
2. aikorea24 D1 직접 쿼리 (wrangler d1 execute)
3. aikorea24 sitemap.xml 파싱 (https://aikorea24.kr/sitemap-index.xml)

**Success Criteria:** aikorea24 발행 현황이 대시보드에 표시됨.

---

### 3-3: money-aikorea24 통합

**File:** `5000/data/dashboard/scripts/sync_money_aikorea24.py`

**Goal:** money-aikorea24 MD 파일 목록 → dashboard 데이터 수집.

**Implementation:**
- `~/money-aikorea24/src/content/blog/` 디렉토리 스캔
- MD 파일 frontmatter 파싱 (title, date, tags)
- 또는 Hugo sitemap 파싱 (`https://persona.aikorea24.kr/sitemap.xml`)

**Success Criteria:** money-aikorea24 발행 현황이 대시보드에 표시됨.

---

### 3-4: 운영 — launchd 등록 + 텔레그램 알림

**Files:**
- `~/Library/LaunchAgents/com.5000.dashboard.plist`
- `5000/data/dashboard/scripts/notify_down.py`

**launchd config:**
```xml
<dict>
    <key>Label</key>
    <string>com.5000.dashboard</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/twinssn/Projects/5000/venv/bin/python</string>
        <string>/Users/twinssn/Projects/5000/data/dashboard/app.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/Users/twinssn/Projects/5000</string>
</dict>
```

**Telegram alerts:** shared/telegram_notifier.py 활용 — 사이트 503/타임아웃 시 알림

**Logging:** `5000/logs/dashboard.log` (Python logging rotate)

**Success Criteria:**
- `launchctl list | grep dashboard` → PID 표시
- 사이트 다운 시 텔레그램 알림 수신
- `logs/dashboard.log`에 정상 로그 기록

---

## Dependency Graph

```
Wave 1:                     Wave 2:           Wave 3:
1-1 analytics_collector     (parallel)
1-2 Flask skeleton ──────► 2-1 Overview ──► 3-1 SAP sync
1-3 /api/posts       ──────► 2-2 Revenue      3-2 aikorea24 sync
1-4 /api/revenue     ──────► 2-3 Traffic      3-3 money-aikorea24 sync
1-5 /api/traffic+search ──► 2-4 Search        3-4 launchd+telegram
1-6 /api/health      ──────► 2-5 Health
                            (all 2-x depend on 1-2)
```

---

## Verification

### Wave 1 Verification
```bash
# 1-1
python -c "from shared.analytics_collector import AnalyticsCollector; c=AnalyticsCollector(); r=c.collect_all(); print(r)"

# 1-2
curl -s http://localhost:5050/api/health | python -m json.tool

# 1-3
curl -s http://localhost:5050/api/posts/daily?days=7 | python -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} days, {sum(len(v) for v in d.values())} blog-entries')"

# 1-4
curl -s http://localhost:5050/api/revenue/daily?days=30 | python -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} days, total=${sum(r[\"estimated_earnings\"] for r in d):.2f}')"

# 1-5
curl -s http://localhost:5050/api/traffic/daily?days=7 | python -m json.tool | head -5

# 1-6
curl -s http://localhost:5050/api/health | python -c "import sys,json; d=json.load(sys.stdin); online=sum(1 for s in d if s['status']==200); print(f'{online}/{len(d)} sites online')"
```

### Wave 2 Verification
```bash
# Page loads
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/       # → 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/revenue # → 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/traffic # → 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/search  # → 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/health  # → 200
```

### Wave 3 Verification
```bash
# SAP sync
python 5000/data/dashboard/scripts/sync_sap.py
curl -s http://localhost:5050/api/posts/total | python -c "import sys,json; d=json.load(sys.stdin); sap_blogs=[b for b in d if 'kbo' in b or 'proto' in b]; print(f'SAP blogs in dashboard: {len(sap_blogs)}')"

# launchd
launchctl list | grep dashboard

# Telegram
# Manually stop one site → check Telegram
```

---

## Files Created (Summary)

| # | File | Purpose |
|---|------|---------|
| 1 | `5000/shared/analytics_collector.py` | GA4/GSC/AdSense/Bing 수집기 |
| 2 | `5000/data/dashboard/app.py` | Flask 앱 메인 |
| 3 | `5000/data/dashboard/requirements.txt` | 의존성 |
| 4 | `5000/data/dashboard/routes/__init__.py` | 패키지 |
| 5 | `5000/data/dashboard/routes/api.py` | JSON API 6종 |
| 6 | `5000/data/dashboard/routes/pages.py` | 페이지 라우트 |
| 7 | `5000/data/dashboard/templates/base.html` | 베이스 템플릿 |
| 8 | `5000/data/dashboard/templates/index.html` | 메인 대시보드 |
| 9 | `5000/data/dashboard/templates/revenue.html` | 수익 페이지 |
| 10 | `5000/data/dashboard/templates/traffic.html` | 트래픽 페이지 |
| 11 | `5000/data/dashboard/templates/search.html` | 검색 페이지 |
| 12 | `5000/data/dashboard/templates/health.html` | 헬스 페이지 |
| 13 | `5000/data/dashboard/static/js/dashboard.js` | Chart.js 차트 |
| 14 | `5000/data/dashboard/static/css/dashboard.css` | 커스텀 스타일 |
| 15 | `5000/data/dashboard/scripts/sync_sap.py` | SAP 동기화 |
| 16 | `5000/data/dashboard/scripts/sync_aikorea24.py` | aikorea24 동기화 |
| 17 | `5000/data/dashboard/scripts/sync_money_aikorea24.py` | money-aikorea24 동기화 |
| 18 | `5000/data/dashboard/scripts/notify_down.py` | 텔레그램 다운 알림 |
| 19 | `~/Library/LaunchAgents/com.5000.dashboard.plist` | launchd 자동 실행 |
| 20 | `logs/dashboard.log` | (로그 파일) |
