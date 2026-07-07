---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: milestone
status: active
last_updated: "2026-07-08T01:20:00.000Z"
progress:
  total_phases: 13
  completed_phases: 10
  total_plans: 48
  completed_plans: 38
  percent: 79
---

# Project State: 5000

**Status:** v1.1 — Phase 13 Wave 1 완료, Phase 13 Wave 2~3 진행 중
**Initialized:** 2026-06-30

## 배포 방식 (CI 없음)
- GitHub으로 push하지 않음. GitHub Actions workflow 불필요.
- 로컬 launchd daemon → run_5000.sh → scheduler.py 실행
- Hugo 사이트는 Cloudflare Pages (무료 플랜, 월 500빌드 제한)에 직접 배포
- Cloudflare Pages ↔ GitHub 연동 해제 상태
- .github/workflows/ 디렉토리는 존재하지 않음 (의도적 제거)

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-30)

**Core value:** Pipelines run reliably with clear errors when they don't
**Current focus:** Phase 13 — Unified Dashboard (Flask + Chart.js)

## Current Phase

**Phase 13 — Unified Dashboard (Flask + Chart.js) — Wave 1 완료, Wave 2 진행 중**

**Phase Goal:** 단일 대시보드에서 5000(Hub: CUAP/TAP/STAP/RAP/SEAP/CAP/CAP/LAP/ETAP/GAP) + SAP(Sports) + aikorea24 + money-aikorea24 = **49개 자동블로그** 통합 모니터링

**Architecture:** Flask + Chart.js (Jinja2 SSR, localhost:5050)
**Total Tasks:** 15 (Wave 1: 7, Wave 2: 5, Wave 3: 4)

---

### Phase 13 — Wave 1 (Data Collection) — **✅ 완료**

| Task | Status | Notes |
|------|--------|-------|
| 1-1: analytics_collector.py | ✅ | GA4(7개 메트릭)/GSC(멀티계정)/AdSense/Bing 수집 |
| 1-2: Flask Dashboard Skeleton | ✅ | app.py + routes/api.py + routes/pages.py + templates |
| 1-3: Postgres/SQLite 스키마 | ✅ | analytics.db + stap_content.db 연동 |
| 1-4: OAuth 토큰 자동 갱신 | ✅ | 3개 계정(GA4+GSC+AdSense) 통합 토큰 발급 |
| 1-5: GSC 멀티 계정 수집 | ✅ | 3개 계정 순차 조회, 63개 사이트 성공 |
| 1-6: AdSense 멀티 계정 수집 | ✅ | 3계정 / 257건 / $10.66 |
| 1-7: SAP + aikorea24 + money 데이터 통합 | ✅ | 2,848건 stap_content.db 직접 삽입 |

---

### Phase 13 — Wave 2 (Dashboard UI) — **🔴 진행 중**

| Task | Status | Notes |
|------|--------|-------|
| 2-1: Overview 페이지 | 🔴 | Stat cards + Trend charts (Chart.js) |
| 2-2: Revenue 페이지 | 🔴 | Daily/RPM/CTR/by-domain |
| 2-3: Traffic 페이지 | 🔴 | Sessions/Users/PV/Bounce/Engagement |
| 2-4: Search 페이지 | 🔴 | GSC/Bing clicks/impressions/position |
| 2-5: Site Health 페이지 | 🔴 | 7×7 그리드 + 필터 |

---

### Wave 3 — External Site Integration + Operations — **🔴 대기 중**

| Task | Status | Notes |
|------|--------|-------|
| 3-1: SAP sync 자동화 | 🟡 | sync_sap.py → launchd 등록 |
| 3-2: aikorea24 sync 자동화 | 🟡 | sync_aikorea24.py → launchd |
| 3-3: money-aikorea24 sync | 🟡 | sync_money_aikorea24.py 보완 |
| 3-3: launchd + Telegram 알림 | 🔴 | 알림 스크립트 구현 후 launchd 등록 |
| 3-4: GSC 누락 사이트 등록 | 🔴 | biz.techpawz.com, issue.techpawz.com GSC 등록 |

---

### Phase 10 — Blowfish Engagement Optimization (Complete ✓)

- ✓ 10-01: P0 Post-processor — lead + figure shortcodes (Wave 1)
- ✓ 10-02: P1 AI Prompt — alert + badge shortcode instructions (Wave 1)
- ✓ 10-02: P2 Gallery + accordion post-processor + prompt (Wave 2)
- ✓ 10-03: P3 Chart shortcode via embedded data comment (Wave 3)
- ✓ 10-03: AdSense 수동광고 RPM 최적화 (Wave 1)
- Note: Implementation uses HTML approach instead of Blowfish shortcodes (shortcodes_enabled: false for travel-hugo)

---

## Progress

| Phase | Status | Plans | Progress |
|-------|--------|-------|----------|
| 1     | ✓      | 2/2   | 100%     |
| 2     | ✓      | 3/3   | 100%     |
| 3     | ✓      | 3/3   | 100%     |
| 4     | ✓      | 2/2   | 100%     |
| 5     | ✓      | 3/3   | 100%     |
| 6     | ✓      | 10/10 | 100%     |
| 7     | ✓      | 9/9   | 100%     |
| 8     | ✓      | 4/4   | 100%     |
| 9     | ✓      | 1/1   | 100%     |
| 10    | ✓      | 5/5   | 100%     |
| 11    | 🔴     | 3/3   | 0%       |
| 12    | ⬜     | 4/4   | 0%       |
| 13    | 🟡     | 15/15 | 33%      |

---

## Quick Tasks Completed

| Date | Task | Commit | Files |
|------|------|--------|-------|
| 2026-07-08 | Phase 13 Wave 1 완료 — Unified Dashboard 통합 | `pending` | analytics_collector.py, app.py, routes/api.py, routes/pages.py, templates/, scripts/, staple_content.db |
| 2026-07-07 | travel-writer-fixes — 마크다운 포맷 오류 이중 방어 (prompt 규칙 강화 + sanitize_markdown) | `3f230f929` | `config/prompts/travel.yaml`, `pipelines/travel/writer.py` |

---
*Last updated: 2026-07-08 after Phase 13 Wave 1 completion*