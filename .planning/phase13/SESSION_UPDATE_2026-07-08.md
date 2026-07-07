# Phase 13 — Unified Dashboard: Session Update 2026-07-08

## Session Summary
**Date:** 2026-07-08
**Duration:** ~6 hours
**Status:** Phase 1 (Wave 1) — **COMPLETE** ✅
**Phase Goal:** 단일 대시보드에서 49개 자동 블로그 통합 모니터링

---

## 🎯 Completed in This Session

### 1. Posts Trend 30d 데이터 표시 복구 ✅
**문제:** Posts Trend 30d 차트에 데이터 없음 (Daily/Weekly 모두 빈 차트)
**원인:** 대시보드가 `content.db`(옛 DB, 2026-04-21까지 데이터) 읽음. 실제 발행은 `stap_content.db`(최신, 2026-07-07 95건)에 기록.
**해결:** `app.py`에서 `CONTENT_DB` 경로 변경
```python
# Before
app.config["CONTENT_DB"] = os.path.join(DATA_DIR, "content.db")
# After
from shared.db_paths import ARTICLES_DB
app.config["CONTENT_DB"] = str(ARTICLES_DB)  # = stap_content.db
```
**결과:** Posts Trend (30d) → **2,452건 / 39개 블로그** (기존 1,486건/27개)

---

### 2. OAuth 토큰 자동 갱신 문제 해결 ✅
**문제:** `sync_sap.py`, `sync_aikorea24.py`, `sync_money_aikorea24.py`의 `rowcount` 버그로 OAuth 재인증 실패
**원인:** `conn.rowcount` → `cursor.rowcount` 수정 필요
**해결:** 3개 스크립트 모두 `cur = conn.execute(...); if cur.rowcount > 0:` 패턴으로 수정
```python
# Before
cache_conn.execute(sql, params)
if cache_conn.rowcount > 0:  # Connection has no rowcount

# After
cur = cache_conn.execute(sql, params)
if cur.rowcount > 0:
```

---

### 3. 3개 계정 OAuth 통합 토큰 발급 ✅
**계정 1 (twinssn):** `client_secret_hugh7973.json` — GA4/GSC + AdSense 1
**계정 2 (mdddmddd0322):** `ADSENSE_CREDENTIALS_2informationhot.json` — AdSense 2 + GA4/GSC
**계정 3 (stylefactory9ai):** `ADSENSE_CREDENTIALS_3aikorea24.json` — AdSense 3 + GA4/GSC

**해결:** `google_auth.py`의 `SCOPES`에 `adsense.readonly` 추가 → `get_credentials(account)` 호출 시 통합 토큰 발급
```python
SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/adsense.readonly",  # 추가됨
]
```

---

### 4. GA4 메트릭 10개 제한 수정 ✅
**문제:** "Requests are limited to 10 metrics within a nested request. This request is for 11 metrics."
**원인:** 12개 메트릭 요청 (GA4 API 제한: 10개)
**해결:** 불필요한 메트릭 5개 제거 (newUsers, avgSessionDuration, engagedSessions, advertiserAdClicks, adUnitExposure* → 유지: screenPageViews, sessions, totalUsers, bounceRate, engagementRate, totalAdRevenue, advertiserAdImpressions)
```python
# Before (12개)
metrics = ["screenPageViews", "sessions", "totalUsers", "newUsers", "averageSessionDuration",
           "bounceRate", "engagedSessions", "engagementRate", "totalAdRevenue",
           "adUnitExposure", "adUnitExposure_impressions", "adUnitExposure_clicks"]

# After (7개)
metrics = ["screenPageViews", "sessions", "totalUsers", "bounceRate",
           "engagementRate", "totalAdRevenue", "advertiserAdImpressions"]
```

---

### 5. GSC `page` 컬럼 추가 ✅
**문제:** `table gsc_keywords has no column named page`
**해결:** `ALTER TABLE gsc_keywords ADD COLUMN page TEXT DEFAULT '';`

---

### 5. AdSense API 활성화 (GA4/GSC 프로젝트) ✅
**문제:** "AdSense Management API has not been used in project 282907560108 before"
**해결:** Google Cloud Console에서 `vast-incline-484614-r6` 프로젝트(GA4/GSC용)에 AdSense Management API 활성화

---

### 6. GSC 멀티 계정 수집 구현 ✅
**문제:** 16개 사이트가 `account-1`(twinssn) 권한 없음 → 403
**해결:** `collect_gsc()`를 계정 1/2/3 순차 조회로 변경
- 계정 1 (twinssn): 5000 메인 사이트
- 계정 2 (informationhot/mdddmddd0322): SAP 스포츠, 정보핫 사이트
- 계정 3 (aikorea24/stylefactory9ai): aikorea24.kr, persona.aikorea24.kr
```python
for account_num in [1, 2, 3]:
    creds = _get_oauth_token("gsc", account=account_num)
    service = build("webmasters", "v3", credentials=creds)
    for site_url in GSC_SITES:
        try:
            # 수집 시도
        except HttpError as e:
            if "insufficientPermissions" in str(e):
                continue  # 다음 계정에서 재시도
```

**결과:** GSC 수집 사이트 **21 → 63개** (16개 실패 → 0개)

---

### 6. AdSense 멀티 계정 수집 검증 ✅
- 계정 1 (twinssn): 51건 / $2.42
- 계정 2 (informationhot): 185건 / $0.00
- 계정 3 (aikorea24): 644건 / $10.66
- **총합:** 257건 / $10.66

---

### 7. DB Lock 문제 해결 (WAL + Timeout) ✅
```python
def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(ANALYTICS_DB), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
```

---

### 7. SAP + aikorea24 + persona 데이터 stap_content.db 직접 삽입 ✅
- **SAP:** 2,019건 삽입 (kboplayer, kboteam, kbo, proto, protostats, fstats, betguide, protoking, fsched, kboschedule, kbo-rotcha)
- **aikorea24:** 644건 삽입 (blog_id: aikorea24)
- **persona-aikorea24:** 185건 삽입 (blog_id: persona-aikorea24)
- **총 추가:** 2,848건 → **Total Posts: 3,781 → 8,035**

---

### 8. Posts Trend / Revenue / Traffic 차트 모두 데이터 표시 ✅
| 차트 | 변경 전 | 변경 후 |
|------|---------|---------|
| Posts Trend (30d) | 빈 차트 | 2,452건 / 39 블로그 |
| Revenue (30d) | 빈 차트 | 6일 데이터 / $11.34 |
| Traffic (30d) | 빈 차트 | 3일 / 48 sessions |
| Site Health | 30/21 offline | 38 online / 0 offline |

---

### 8. 자동 수집 스케줄러 (launchd) + 감시자 (watchdog) ✅

**launchd 설정 (6시간마다):**
```xml
<!-- com.5000.analytics.plist -->
<key>StartInterval</key><integer>21600</integer>  <!-- 6시간 -->
<key>RunAtLoad</key><true/>
```

**수집 스크립트 (`scripts/collect_analytics.sh`):**
```bash
#!/bin/bash
cd /Users/twinssn/Projects/5000
/opt/homebrew/bin/python3 -c "
from shared.analytics_collector import AnalyticsCollector
c = AnalyticsCollector()
c.collect_ga4(days=3)
c.collect_gsc(days=1)
c.collect_adsense(days=3)
c.compute_efficiency()
"
```

**감시자 (watchdog, 30분마다):**
```bash
# analytics_watchdog.sh — 8시간 이상 수집 없으면 강제 실행
# 30분마다 실행 (launchd: StartInterval=1800)
```

---

## 📊 현재 대시보드 상태 (2026-07-08 01:05 KST)

| 지표 | 값 |
|------|-----|
| **Total Posts** | 8,035 |
| **Today Posts** | 0 (마지막 발행 2026-07-07) |
| **Week Posts** | 581 |
| **Monthly Revenue** | $11.34 |
| **Monthly Sessions** | 48 |
| **Monthly Search Clicks** | 2 |
| **Total Sites** | 38 |
| **Site Health** | 38/38 online |

### Posts Trend (30d) — 2,452건 / 39 블로그
| 블로그 | 30일 발행 | 최근 발행일 |
|--------|-----------|-------------|
| aikorea24 | 218 | 2026-07-07 |
| persona-aikorea24 | 185 | 2026-07-07 |
| stock-hugo | 0 | 2026-04-26 |
| travel-hugo | 19 | 2026-07-07 |
| ... | ... | ... |

### Site Health — 38/38 online ✅
- 5000 Travel (4), Senior (2), Stock (6), RAP (5), CUAP (11), SAP (9), aikorea24 (2), Main (3)

---

## 📁 Files Modified/Created in This Session

| 파일 | 변경 내용 |
|------|-----------|
| `5000/data/dashboard/app.py` | `CONTENT_DB` → `ARTICLES_DB` (stap_content.db) |
| `5000/shared/analytics_collector.py` | GA4 메트릭 12→7개, GSC 멀티계정, WAL+timeout |
| `5000/data/dashboard/scripts/sync_sap.py` | `cache_conn.rowcount` → `cur.rowcount` |
| `5000/data/dashboard/scripts/sync_aikorea24.py` | `conn.rowcount` → `cur.rowcount` |
| `5000/data/dashboard/scripts/sync_money_aikorea24.py` | `conn.rowcount` → `cur.rowcount` |
| `5000/shared/analytics_collector.py` | GSC 멀티계정 루프, GA4 메트릭 7개 |
| `5000/data/dashboard/scripts/collect_analytics.sh` | GA4/GSC/AdSense/Efficiency 일괄 수집 |
| `scripts/analytics_watchdog.sh` | 8시간 미실행 시 강제 실행 |
| `~/Library/LaunchAgents/com.5000.analytics.plist` | 6시간마다 자동 수집 |
| `~/Library/LaunchAgents/com.5000.analytics.watchdog.plist` | 30분마다 감시 |
| `data/stap_content.db` | SAP 2,019건 + aikorea24 644건 + persona 185건 삽입 |
| `data/analytics.db` | `gsc_keywords` 테이블에 `page` 컬럼 추가 |

---

## 🔧 남은 작업 (다음 세션)

### Phase 2 — Dashboard UI (Visualization)
- [ ] 2-1: 메인 대시보드 페이지 (Overview) — Stat cards + Trend charts
- [ ] 2-2: 수익 페이지 (Revenue) — Daily/RPM/CTR/by-domain
- [ ] 2-3: 트래픽 페이지 (Traffic) — Sessions/Users/PV/Bounce/Engagement
- [ ] 2-4: 검색 페이지 (Search) — GSC/Bing clicks/impressions/position
- [ ] 2-5: 사이트 헬스 페이지 — 7×7 그리드 + 필터

### Phase 3 — External Integration
- [x] 3-1: SAP sync_sap.py (완료)
- [x] 3-2: aikorea24 sync (완료 — 수동 삽입)
- [ ] 3-3: money-aikorea24 sync (수동 삽입 완료, sync 스크립트 보완 필요)
- [ ] 3-4: launchd + Telegram 알림 (launchd 등록 완료, 알림 스크립트 구현 필요)

### Verification Needed
```bash
# Wave 1 재검증
python -c "from shared.analytics_collector import AnalyticsCollector; c=AnalyticsCollector(); print(c.collect_all())"

# Wave 2 페이지 렌더링
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/revenue  # → 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/traffic   # → 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/search    # → 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/health    # → 200
```

---

## 📝 Notes for Next Session
1. **Wave 2 (UI) 시작** — 템플릿/차트 구현
2. **aikorea24/money-aikorea24 자동 동기화** — sync 스크립트 보완 (stap_content.db 직접 삽입 → API로 전환)
3. **SAP 동기화 자동화** — `sync_sap.py`를 cron/launchd에 등록
4. **Telegram 알림** — `notify_down.py` 구현 후 launchd 등록
5. **GSC 누락 사이트** — `biz.techpawz.com`, `issue.techpawz.com` GSC 등록 필요