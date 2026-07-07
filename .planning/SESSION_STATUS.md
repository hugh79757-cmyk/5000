## CUAP 프로젝트 현황

### ✅ 완료
| 작업 | 상태 | 비고 |
|------|------|------|
| Phase 1: Audit | ✅ | 36.5% 오염률 확인, AUDIT_REPORT.md |
| Phase 2: Keyword/Filter Refinement | ✅ | 438개 키워드 제거, CATEGORY_FILTERS 강화 |
| baby-hugo P0 fix | ✅ | 골지/긴팔/나시 + 패션의류 차단 |
| beauty-hugo P0 fix (1차) | ✅ | 13개 생활용품 키워드 제거 |
| Phase 3: Content Validation System | ✅ | relevance_scorer, pre-publish gate, audit log, weekly alert |
| Phase 8: Content Cleanup | ✅ | 43개 오염 글 삭제, 10/10 블로그 배포 완료 |
| Deploy fallback fix | ✅ | deploy.py + deploy_blog.sh + baby-hugo wrangler.toml |
| **Phase 8.5: beauty-hugo 2차 클린업** | ✅ | **9개 generic 키워드 제거 (85→76)** |
| **Phase 13 Wave 1 — Unified Dashboard** | ✅ | **49개 블로그 통합 모니터링 완료** |

---

### 🔴 해결해야 할 것

#### 1. Phase 11 PLAN.md 수정 (blocker 3개)
**파일:** `.planning/phase11/PLAN.md`
**blocker:**
- AD3가 세 번째 `<h2` 앞이 아니라 AD2랑 같은 위치에 붙음 (replace 로직 오류)
- `cp custom.css`가 kitchen-hugo 등 기존 커스텀 CSS 덮어씀
- Task 11.3 CSS 명세가 너무 추상적 (구체적 CSS 코드 없음)
**필요:** PLAN.md 수정 → 재검증 → 실행

#### 2. Phase 11 실행 (AdSense 최적화)
**작업:** adsense 파셜 3종 + single.html 재작성 + baseof.html override + custom.css + config
**범위:** 블로그 10개
**의존:** PLAN.md blocker 해결 후

#### 3. Phase 11 검증
**작업:** Hugo 빌드 + DevTools 체크리스트 12항목 (SC-01~SC-12)
**의존:** Phase 11 실행 후

---

### 📋 우선순위
1. ✅ beauty-hugo irrelevant_products — **완료** (9개 키워드 제거, 발행 확인 대기)
2. 🔴 Phase 11 PLAN.md blocker 3개 수정 (다음 세션)
3. 🔴 Phase 11 실행
4. 🔴 Phase 11 검증

---

## 📋 Phase 13 — Unified Dashboard 현황

### ✅ Wave 1 (Data Collection) — **완료**
| Task | 상태 | 비고 |
|------|------|------|
| 1-1: analytics_collector.py | ✅ | GA4(7개 메트릭)/GSC(멀티계정)/AdSense/Bing 수집 |
| 1-2: Flask Dashboard Skeleton | ✅ | app.py + routes/api.py + routes/pages.py + templates |
| 1-3: Postgres/SQLite 스키마 | ✅ | analytics.db + stap_content.db 연동 |
| 1-4: OAuth 토큰 자동 갱신 | ✅ | 3개 계정(GA4+GSC+AdSense) 통합 토큰 발급 |
| 1-5: GSC 멀티 계정 수집 | ✅ | 3개 계정 순차 조회, 63개 사이트 성공 |
| 1-6: AdSense 멀티 계정 수집 | ✅ | 3계정 / 257건 / $10.66 |
| 1-7: SAP + aikorea24 + money 데이터 통합 | ✅ | 2,848건 stap_content.db 직접 삽입 |

---

### 📊 현재 대시보드 상태 (2026-07-08 01:05 KST)

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

### Posts Trend (30d) — **2,452건 / 39 블로그**
| 블로그 | 30일 발행 | 최근 발행일 |
|--------|-----------|-------------|
| aikorea24 | 218 | 2026-07-07 |
| persona-aikorea24 | 185 | 2026-07-07 |
| fstats | 145 | 2026-07-07 |
| compare-hugo | 115 | 2026-07-07 |
| kbo | 105 | 2026-07-07 |
| kboteam | 58 | 2026-07-07 |
| kboplayer | 58 | 2026-07-07 |
| betguide | 58 | 2026-07-07 |
| travel-hugo | 19 | 2026-07-07 |
| ... | ... | ... |

### Site Health — **38/38 online** ✅
- 5000 Travel (4), Senior (2), Stock (6), RAP (5), CUAP (11), SAP (9), aikorea24 (2), Main (3)

---

### ⏳ 남은 작업 (Phase 13)

| Phase | Task | 상태 |
|-------|------|------|
| **Wave 2 — Dashboard UI** | | |
| 2-1: Overview 페이지 | 🔴 | Stat cards + Trend charts (Chart.js) |
| 2-2: Revenue 페이지 | 🔴 | Daily/RPM/CTR/by-domain |
| 2-3: Traffic 페이지 | 🔴 | Sessions/Users/PV/Bounce/Engagement |
| 2-4: Search 페이지 | 🔴 | GSC/Bing clicks/impressions/position |
| 2-5: Site Health 페이지 | 🔴 | 7×7 그리드 + 필터 |
| **Wave 3 — Integration** | | |
| 3-1: SAP sync 자동화 | 🟡 | sync_sap.py → launchd 등록 |
| 3-2: aikorea24 sync 자동화 | 🟡 | sync_aikorea24.py → launchd |
| 3-3: money-aikorea24 sync | 🟡 | sync_money_aikorea24.py 보완 |
| 3-4: launchd + Telegram 알림 | 🔴 | 알림 스크립트 구현 후 launchd 등록 |
| 3-5: GSC 누락 사이트 등록 | 🔴 | biz.techpawz.com, issue.techpawz.com GSC 등록 |

---

### 🎯 다음 세션 우선순위
1. **Phase 13 Wave 2-1**: Overview 페이지 구현 (Stat cards + Chart.js 트렌드 차트)
2. **Phase 11 PLAN.md blocker 수정** (Phase 11 진행을 위해)
3. **자동화 등록**: sync_sap.py, sync_aikorea24.py, sync_money_aikorea24.py → launchd 등록

---

*Last updated: 2026-07-08 01:20 KST*