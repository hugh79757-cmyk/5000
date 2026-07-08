# Phase 14 — Cross-Project Content Quality Dashboard (Unified Dashboard Wave 2+3)

**Phase Goal:** Flask + Chart.js 기반 단일 대시보드에서 5000(38개) + SAP(10개) + aikorea24 + money-aikorea24 = **50개 자동 블로그**의 발행/수익/트래픽/검색/헬스 통합 모니터링 완성

**Architecture:** Flask + Chart.js (Jinja2 SSR, localhost:5050)  
**Mode:** mvp (vertical slices — 각 페이지가 독립적 완전 기능)  
**Total Tasks:** 9 (Wave 2: 5 UI 페이지, Wave 3: 3 Integration + 1 Ops)  
**Dependencies:** Phase 13 완료 후 (Hugo 마크다운 렌더링 수정 → 콘텐츠 품질 지표 파이프라인 연결)

---

## Wave 2 — Dashboard UI Completion (5 Tasks)

### 14-01: Overview Page Complete — Stat Cards + Core Charts

**Files:**
- `data/dashboard/templates/index.html` (extend)
- `data/dashboard/static/js/dashboard.js` (extend `loadSummary`, `loadPostsChart`, `loadRevenueChart`, `loadTopPosts`, `loadHealth`)

**Charts Required:**
| Chart | API Endpoint | Type | Spec |
|-------|-------------|------|------|
| Stat Cards (4) | `/api/summary` | Text | Total Posts, Today Posts, Monthly Revenue, Monthly Sessions |
| Posts Trend (30d) | `/api/posts/daily?days=30` | Line | Aggregated across all blogs, toggle daily/weekly |
| Revenue Trend (30d) | `/api/revenue/daily?days=30` | Dual Line | Revenue($) left axis, RPM($) right axis |
| Top 10 Blogs by Posts | `/api/posts/total` | Horizontal Bar | Bottom-up, max 15 blogs |
| Site Health Mini Grid | `/api/health` | Color Grid | 38 sites, green/red/gray dots |

**Implementation Notes:**
- `dashboard.js`에 `createLineChart(ctx, labels, datasets, options)`, `createBarChart(ctx, labels, datasets, options)` 헬퍼 함수 추가하여 중복 제거
- 차트별 `charts.{name}` 변수로 인스턴스 관리, `destroy()` 후 재생성
- 에러 시 캔버스에 "Failed to load" 표시, 콘솔 로그

**Success Criteria:**
- `curl -s http://localhost:5050/ | grep -c canvas` → 4개 이상
- 브라우저에서 `/` 접속 시 4개 카드 + 3개 차트 + 미니 그리드 3초 내 렌더링
- JS 콘솔 에러 없음

---

### 14-02: Revenue Page Complete

**Files:**
- `data/dashboard/templates/revenue.html` (extend)
- `data/dashboard/static/js/dashboard.js` (extend `loadRevenuePage`, `loadRevenueByDomain`, `loadRpmTrend`)

**Charts Required:**
| Chart | API Endpoint | Type | Spec |
|-------|-------------|------|------|
| Daily Earnings (90d) | `/api/revenue/daily?days=90` | Line | Fill area, currency format |
| RPM Trend (90d) | `/api/revenue/rpm?days=90` | Line | RPM($) primary, CTR(%) secondary axis |
| CTR Trend (90d) | 동일 | Line | 동일 차트에 CTR 라인 추가 |
| Revenue by Domain (30d) | `/api/revenue/by-domain?days=30` | Horizontal Bar | Top 20, currency format |
| Weekly Comparison | 계산 로직 JS에서 | Grouped Bar | This week vs Last week, revenue & RPM |

**Implementation Notes:**
- Weekly comparison은 `/api/revenue/daily?days=14` 받아서 주간 집계 후 계산
- RPM/CTR 듀얼 축 차트는 `yAxisID: 'y' / 'y1'` 패턴 재사용 (Overview Revenue Trend와 동일)

**Success Criteria:**
- `/revenue` 5개 차트 렌더링, 호버 툴팁에 `$`/`%` 단위 표시
- Weekly comparison 바 차트 정상 (이번 주/지난 주 구분 색상)

---

### 14-03: Traffic Page Complete

**Files:**
- `data/dashboard/templates/traffic.html` (extend)
- `data/dashboard/static/js/dashboard.js` (extend `loadTrafficPage`, `loadTrafficChart`, `loadTrafficByBlog`)

**Charts Required:**
| Chart | API Endpoint | Type | Spec |
|-------|-------------|------|------|
| Sessions + Users (30d) | `/api/traffic/daily?days=30` | Dual Line | Sessions(파랑), Users(초록) |
| Page Views (30d) | 동일 | Area Chart | Yellow, fill true |
| Bounce Rate + Engagement (30d) | 동일 | Dual Line | Bounce(빨강), Engagement(파랑), % 축 |
| Traffic by Blog (30d) | `/api/traffic/by-blog?days=30` | Horizontal Bar | Top 20, sessions 기준 |
| Ad Revenue vs Traffic | JS에서 `/traffic/daily` + `/revenue/daily` 병합 | Scatter | X: Sessions, Y: Ad Revenue, 점 크기=PV |

**Implementation Notes:**
- Scatter chart는 Chart.js `type: 'scatter'` 사용, `data: [{x, y, r}]` 포맷
- 데이터 병합은 날짜 기준 `Map`으로 조인

**Success Criteria:**
- `/traffic` 5개 차트 렌더링, Scatter 차트 점 호버 시 날짜/세션/수익 표시

---

### 14-04: Search Page Complete

**Files:**
- `data/dashboard/templates/search.html` (extend)
- `data/dashboard/static/js/dashboard.js` (extend `loadSearchPage`, `loadGscChart`, `loadBingChart`, `loadEfficiencyChart`)

**Charts Required:**
| Chart | API Endpoint | Type | Spec |
|-------|-------------|------|------|
| GSC Clicks + Impressions (30d) | `/api/search/gsc/daily?days=30` | Dual Line | Clicks(초록), Impressions(파랑), 듀얼 축 |
| Avg Position Trend (90d) | 동일 | Inverted Line | Position 낮을수록 좋음 → 11 - position 변환 |
| CTR Trend (30d) | 동일 | Line | % 축, 0~10% 범위 |
| Bing Clicks + Impressions (30d) | `/api/search/bing/daily?days=30` | Dual Line | 동일 패턴 |
| Blog Efficiency Scores (30d) | `/api/search/efficiency?days=30` | Horizontal Bar | All blogs, 색상: >80 녹, 50-80 황, <50 적 |
| GSC vs Bing Comparison | 두 엔드포인트 병합 | Grouped Bar | 날짜별 클릭수 비교 (GSC 파랑, Bing 보라) |

**Implementation Notes:**
- Efficiency bar 색상: `backgroundColor: score > 80 ? 'rgba(25,135,84,0.7)' : score > 50 ? 'rgba(255,193,7,0.7)' : 'rgba(220,53,69,0.7)'`
- Grouped bar는 Chart.js `labels: dates, datasets: [{label:'GSC', data:[...]}, {label:'Bing', data:[...]}]`

**Success Criteria:**
- `/search` 6개 차트 렌더링, 효율 점수 색상 코딩 정상, Position 역축 표시

---

### 14-05: Health Page Polish + Auto-refresh

**Files:**
- `data/dashboard/templates/health.html` (already 90% complete)
- `data/dashboard/static/js/dashboard.js` (add filter logic to `loadHealth`)

**Improvements:**
1. **Filter Buttons**: All / Online / Offline (버튼 그룹, 클릭 시 그리드/테이블 필터링)
2. **Auto-refresh**: 기존 `setInterval(loadHealth, 30000)` 유지
3. **Sort Options**: Status / Response Time / Blog ID 정렬 드롭다운
4. **Telegram Alert Integration**: `loadHealth()`에서 offline 감지 시 `notify_down.py` 호출 (중복 방지 cooldown 30분)
5. **Response Time Histogram**: 하단에 응답시간 분포 바 차트 추가 (선택)

**Implementation Notes:**
- Filter 상태를 `localStorage`에 저장하여 새로고침 시 복원
- Telegram 알림은 `fetch('/api/notify-down', {method:'POST', body:JSON.stringify({site})})` 엔드포인트 신규 추가 권장

**Success Criteria:**
- 필터 버튼 작동 (All=38, Online=38, Offline=0 기본)
- 30인터미널에서 사이트 하나 중단 후 30초 내 그리드 빨간 점 변경, 텔레그램 수신
- 응답시간 기준 정렬 작동

---

## Wave 3 — External Site Integration (3 Tasks)

### 14-06: SAP Publish Log Integration

**Files:**
- `data/dashboard/scripts/sync_sap_to_dashboard.py` (new)
- `data/dashboard/scripts/sync_sap.py` (reuse logic)
- `data/dashboard/routes/api.py` (extend `/api/posts` for SAP UNION)

**Logic:**
```python
# 1. SAP DB 읽기
sap_db = Path("/Users/twinssn/Projects/SAP/data/publish_log.db")
conn = sqlite3.connect(sap_db)
rows = conn.execute("""
    SELECT blog_id, title, created_at, status 
    FROM publish_log 
    WHERE created_at > datetime('now', '-90 days')
""").fetchall()

# 2. Dashboard 전용 캐시 DB
cache_db = Path("data/dashboard/data/sap_posts.db")
# Table: sap_posts(blog_id, title, created_at, status, synced_at)

# 3. UPSERT
for row in rows:
    cache_conn.execute("""
        INSERT OR REPLACE INTO sap_posts (blog_id, title, created_at, status, synced_at)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, row)

# 4. /api/posts/total에서 UNION
SELECT blog_id, COUNT(*) FROM articles WHERE status='published' GROUP BY blog_id
UNION ALL
SELECT blog_id, COUNT(*) FROM sap_posts WHERE status='published' GROUP BY blog_id
```

**Schedule:** 매시간 cron (`launchd` 별도 plist 또는 기존 analytics watchdog에 추가)

**Success Criteria:**
- `/api/posts/total` 응답에 `kboplayer`, `kboteam`, `kboschedule`, `proto`, `protostats`, `fstats`, `fsched`, `betguide`, `protoking` 9개 + `sports` blogger 1개 = 10개 SAP 블로그 표시
- Overview Posts Trend 차트에 SAP 데이터 반영

---

### 14-07: aikorea24 + money-aikorea24 Integration

#### aikorea24
**Options (preference order):**
1. **blogdex Workers API** — `blogdex-api.hugh79757.workers.dev` 경유 (기존 `sync_astro.py` 재사용)
2. **Cloudflare D1 직접 쿼리** — `wrangler d1 execute aikorea24 --command="SELECT ..."`
3. **Sitemap 파싱** — `https://aikorea24.kr/sitemap-index.xml`

**Recommended:** Option 1 (blogdex Workers API) — 이미 인증/인프라 갖춰짐

#### money-aikorea24
**Options:**
1. **MD 파일 스캔** — `~/money-aikorea24/src/content/blog/` frontmatter 파싱
2. **Hugo Sitemap** — `https://persona.aikorea24.kr/sitemap.xml` 파싱

**Recommended:** Option 2 (Sitemap) — 배포 후 즉시 반영, 파일시스템 의존성 없음

**Files:**
- `data/dashboard/scripts/sync_aikorea24.py` (extend to write to dashboard cache DB)
- `data/dashboard/scripts/sync_money_aikorea24.py` (extend)
- `data/dashboard/routes/api.py` (extend `/api/posts` UNION)

**Schedule:** 매 30분 cron

**Success Criteria:**
- `/api/posts/total`에 `aikorea24` (1개), `persona-aikorea24` (1개) 표시
- Overview Top Blogs 차트에 두 사이트 포함

---

### 14-08: GSC Missing Sites Registration

**Issue:** `shared/analytics_collector.py:GA4_PROPERTIES`에 38개 사이트 중 다수 `None`

**Action:**
1. blogdex `analytics.py`의 GA4 property 자동 탐색 로직 포팅
2. `GA4_ADMIN` API로 계정 하위 속성 목록 조회 → 도메인 매핑
3. 수동 보정: `rotcha.kr` 서브도메인 공통 property, `techpawz.com` 서브도메인 공통 property 등

**Files:** `shared/analytics_collector.py` (GA4_PROPERTIES dict 업데이트)

**Schedule:** 1회 실행, 이후 월간 검증

**Success Criteria:** GA4_PROPERTIES `None` 개수 0개 (또는 의도적으로 미등록 사이트만 제외)

---

## Wave 4 — Operations (1 Task)

### 14-09: Launchd Dashboard Server + Telegram Alerts + Logging

**Files:**
- `~/Library/LaunchAgents/com.5000.dashboard.plist` (new)
- `data/dashboard/scripts/notify_down.py` (extend for health check integration)
- `data/dashboard/routes/api.py` (add `/api/notify-down` POST endpoint)

**Launchd Config:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
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
    <key>StandardOutPath</key>
    <string>/Users/twinssn/Projects/5000/logs/dashboard.out.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/twinssn/Projects/5000/logs/dashboard.err.log</string>
</dict>
</plist>
```

**Telegram Alert Flow:**
1. `loadHealth()` (30초마다) → offline 사이트 감지
2. `notify_down.py`의 `check_and_alert()` 호출 (cooldown 30분, `data/dashboard/data/alert_cooldown.json` 관리)
3. `shared.telegram_notifier.send_error()`로 전송

**Logging:** Python `logging.handlers.RotatingFileHandler` (10MB, backup 5) → `/Users/twinssn/Projects/5000/logs/dashboard.log`

**Success Criteria:**
- `launchctl list | grep dashboard` → PID 표시
- 사이트 하나 수동 중단 → 30초 내 대시보드 Health 페이지 빨간 점, 텔레그램 알림 수신
- `logs/dashboard.log`에 `INFO` 레벨 로그 정상 기록 (요청, 응답시간, 에러)

---

## Dependency Graph

```
Wave 2 (UI - Parallel per page):
  14-01 Overview ──┐
  14-02 Revenue ───┤ (공통: chart-helpers.js 선행 권장)
  14-03 Traffic ───┤
  14-04 Search ────┘
  14-05 Health ──── (독립적)

Wave 3 (Sequential - 외부 의존성):
  14-06 SAP sync ──► 14-07 aikorea24/money sync ──► 14-08 GSC 등록 ──► 14-09 Launchd+Telegram
```

---

## Verification Commands

### Wave 2 — UI Pages
```bash
# 14-01 Overview
curl -s http://localhost:5050/ | grep -c 'id="stat'  # 4 stat cards
curl -s http://localhost:5050/ | grep -c '<canvas'  # 4+ charts

# 14-02 Revenue
curl -s http://localhost:5050/revenue | grep -c '<canvas'  # 5 charts

# 14-03 Traffic
curl -s http://localhost:5050/traffic | grep -c '<canvas'  # 5 charts

# 14-04 Search
curl -s http://localhost:5050/search | grep -c '<canvas'  # 6 charts

# 14-05 Health
curl -s http://localhost:5050/health | grep -c 'healthGrid'  # 1
curl -s http://localhost:5050/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{d[\"online\"]}/{d[\"total\"]} online')"
```

### Wave 2 — API Data
```bash
curl -s http://localhost:5050/api/summary | python3 -m json.tool
curl -s http://localhost:5050/api/posts/daily?days=7 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} days')"
curl -s http://localhost:5050/api/revenue/daily?days=30 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} days, total=${sum(r[\"revenue\"] for r in d):.2f}')"
curl -s http://localhost:5050/api/traffic/daily?days=7 | python3 -m json.tool | head -10
curl -s http://localhost:5050/api/search/gsc/daily?days=7 | python3 -m json.tool | head -10
```

### Wave 3 — Integration
```bash
# 14-06 SAP
python3 data/dashboard/scripts/sync_sap_to_dashboard.py
curl -s http://localhost:5050/api/posts/total | python3 -c "import sys,json; d=json.load(sys.stdin); sap=[b for b in d if 'kbo' in b['blog_id'] or 'proto' in b['blog_id']]; print(f'SAP blogs: {len(sap)}')"

# 14-07 aikorea24
python3 data/dashboard/scripts/sync_aikorea24.py
curl -s http://localhost:5050/api/posts/total | python3 -c "import sys,json; d=json.load(sys.stdin); ai=[b for b in d if 'aikorea24' in b['blog_id']]; print(f'aikorea24 blogs: {len(ai)}')"

# 14-08 GSC registration
python3 -c "from shared.analytics_collector import AnalyticsCollector; c=AnalyticsCollector(); print([k for k,v in c.GA4_PROPERTIES.items() if v is None])"
```

### Wave 4 — Ops
```bash
# Launchd
launchctl load ~/Library/LaunchAgents/com.5000.dashboard.plist
launchctl list | grep dashboard

# Logs
tail -f /Users/twinssn/Projects/5000/logs/dashboard.log

# Telegram test
python3 -c "
from shared.telegram_notifier import send_error
send_error('test-site', 'test', 'Phase 14 dashboard test alert')
"
```

---

## File Inventory

### Existing (Wave 1 완료, 수정 필요)
| File | Lines | Status |
|------|-------|--------|
| `shared/analytics_collector.py` | 1010 | ✅ Complete |
| `data/dashboard/app.py` | 58 | ✅ Complete |
| `data/dashboard/routes/api.py` | 439 | ✅ API Complete, need UNION for SAP/aikorea24 |
| `data/dashboard/routes/pages.py` | 30 | ✅ Complete |
| `data/dashboard/templates/base.html` | 50 | ✅ Complete |
| `data/dashboard/templates/index.html` | 87 | 🔄 Extend (charts wiring) |
| `data/dashboard/templates/revenue.html` | 30 | 🔄 Extend (charts wiring) |
| `data/dashboard/templates/traffic.html` | 30 | 🔄 Extend (charts wiring) |
| `data/dashboard/templates/search.html` | 41 | 🔄 Extend (charts wiring) |
| `data/dashboard/templates/health.html` | 99 | 🔄 Polish (filters, sort, alert) |
| `data/dashboard/static/js/dashboard.js` | 800+ | 🔄 Extend (chart helpers, all pages) |
| `data/dashboard/scripts/sync_sap.py` | 128 | 🔄 Reuse for sync_sap_to_dashboard.py |
| `data/dashboard/scripts/sync_aikorea24.py` | 119 | 🔄 Extend (cache DB write) |
| `data/dashboard/scripts/sync_money_aikorea24.py` | 108 | 🔄 Extend (cache DB write) |
| `data/dashboard/scripts/notify_down.py` | 68 | 🔄 Extend (cooldown, health integration) |

### To Create
| File | Purpose |
|------|---------|
| `data/dashboard/static/js/chart-helpers.js` | Chart factory functions (createLineChart, createBarChart, createDualLineChart, destroyChart) |
| `data/dashboard/static/css/dashboard.css` | Custom styles (chart containers, health grid, badges) |
| `data/dashboard/scripts/sync_sap_to_dashboard.py` | SAP publish_log → dashboard cache DB + cron |
| `data/dashboard/data/sap_posts.db` | SQLite cache (auto-created by sync script) |
| `data/dashboard/data/aikorea24_posts.db` | SQLite cache (auto-created) |
| `data/dashboard/data/alert_cooldown.json` | Telegram alert cooldown tracking |
| `~/Library/LaunchAgents/com.5000.dashboard.plist` | Dashboard server launchd |
| `/Users/twinssn/Projects/5000/logs/dashboard.log` | Rotating log file |

---

## Exit Criteria (Phase 14 Complete)

- [ ] **14-01** `/` Overview: 4 stat cards + 3 charts + mini health grid 렌더링, JS 에러 없음
- [ ] **14-02** `/revenue`: 5 charts 렌더링, 호버 툴팁 단위($, %) 표시
- [ ] **14-03** `/traffic`: 5 charts 렌더링, scatter 차트 작동
- [ ] **14-04** `/search`: 6 charts 렌더링, 효율 점수 색상(녹/황/적) 정상
- [ ] **14-05** `/health`: 필터(All/Online/Offline) 작동, 30초 자동 갱신, offline 시 텔레그램 수신
- [ ] **14-06** SAP 10개 블로그 `/api/posts/total` 표시, Overview Posts Trend 반영
- [ ] **14-07** aikorea24 + money-aikorea24 2개 블로그 `/api/posts/total` 표시
- [ ] **14-08** GA4_PROPERTIES `None` 0개 (의도적 제외 제외)
- [ ] **14-09** `launchctl list | grep dashboard` PID, 사이트 다운 시 텔레그램, 로그 정상
- [ ] **Integration** Phase 13 Hugo 마크다운 수정 후 새 발행글 콘텐츠 품질 지표(글자수, 마크다운 잔재율) 대시보드 반영 파이프라인 설계 완료 (Phase 15에서 구현)

---

## Next Phase (Phase 15)

**Phase 15: Content Quality Pipeline Integration** — Phase 13 Hugo 마크다운 렌더링 수정 결과(콘텐츠 길이, 마크다운 잔재율, CTA/썸네일/지도보기 검증)를 대시보드에 실시간 반영하는 파이프라인 구축. `hugo_writer.py` 검증 결과 → `analytics.db` 또는 별도 `quality.db` 저장 → `/api/quality` 엔드포인트 신설 → Overview에 "Content Quality" 카드/차트 추가.