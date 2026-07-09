# Roadmap: 5000

**Last updated:** 2026-07-09 (code-audited, not doc-driven)

**Actual phases completed:** 15 phases 완료 (Phase 12 일부 누락)
**현재 대시보드:** http://localhost:5050 (38개 5000 + 7 SAP + 2 aikorea24 = 47개 블로그 통합)

---

## Phase 1: Foundation — Test & Tooling Infrastructure
**Status:** ✅ Complete  
**Commit:** 초기 CI/테스트 인프라

---

## Phase 2: Core Refactoring — Simplify Central Modules
**Status:** ✅ Complete  
**Commit:** dispatcher registry + publisher 분할

---

## Phase 3: Hardening — Stability & Decoupling
**Status:** ✅ Complete  
**Commit:** `139e5fdda`

---

## Phase 4: TAP Publishing Stabilization (Content Validation)
**Status:** ✅ Complete  
**Commit:** `139e5fdda` (Phase 2.1+3 동시)

---

## Phase 5: Post-Stabilization Enhancement
**Status:** ✅ Complete  
**Commits:** Blowfish 테마 업그레이드, 모니터링 시스템

---

## Phase 6+7: Maintenance, Testing, Content Enhancement
**Status:** ✅ Complete  
**Commit:** `def74aeef`
- dispatcher: validate_config() startup check
- scheduler: 3연속 실패 Telegram alert
- publisher: STAP_CONTENT_DB path fix
- hugo_writer: regex fix, CDN block
- humanizer: meta leakage cleanup
- validators: +10 test cases
- log_config, metrics, log_aggregator: monitoring infra

---

## Phase 8: Content Cleanup
**Status:** ✅ Complete  
**Commit:** `7c2c8a701`  
43개 오염 글 삭제, keywords 정리, deploy fallback fix, beauty-hugo 2차 cleanup

---

## Phase 9: AI-Tell Pattern Enrichment (humanizer.py)
**Status:** ✅ Complete  
**Commit:** `0a17cf55b`  
16개 AI 티 패턴 추가

---

## Phase 10: Blowfish Engagement Optimization
**Status:** ✅ Complete  
**Commit:** `ebbfc815b` (shortcode 구현됨, toggle disabled)  
lead/figure/gallery/accordion/chart shortcode 변환기 hugo_writer.py에 구현

---

## Phase 11: AdSense 고효율 광고 구조 개선
**Status:** ✅ **Complete** (문서에는 deferred로 표기돼있으나 실제 코드는 완료)
- 10개 CUAP 블로그 전부 adsense partials 존재
- IntersectionObserver lazy-load 적용
- mobile-sticky / leaderboard / in-article 3종 partial
- ✅ 참고: `a14fc9c08` 커밋의 "Phase 11 coupang import fix"는 별개 작업 (이전 naming)

---

## Phase 12: Body Content Rescan & Keyword Validation Gate
**Status:** 🔴 **Partial — 1개 task 미완료**
- ✅ `detect_problematic_posts.py` — `--scan-body` flag 구현됨
- ✅ `keyword_expander.py` — `validate_keyword()` 호출 코드는 있음 (try/except ImportError로 보호)
- ❌ **`validate_keyword()` 함수가 `keywords.py`에 누락** — ImportError로 무시되므로 기능이 동작하지 않음 (silent failure)
- ❌ 키워드 검증 게이트가 작동하지 않음

---

## Phase 13: Unified Dashboard — Data Collection + Markdown Audit
**Status:** ✅ **Complete**
- **Wave 1:** analytics_collector.py GA4/GSC/AdSense/Bing, Flask skeleton, 6종 API
- **Wave 2:** 5개 Dashboard UI 페이지 (Overview/Revenue/Traffic/Search/Health) + 19개 Chart.js 차트
- 대시보드 http://localhost:5050 운영 중

---

## Phase 14: Cross-Project Dashboard Integration
**Status:** ✅ **Complete** (commit `4335f7a6b`)
- **Wave 2 UI:** Overview/Revenue/Traffic/Search/Health 5페이지 Chart.js 시각화
- **Wave 3 외부통합:** SAP 7개 + aikorea24 2개 = 9개 사이트 통합 (총 47개)
- **Wave 4 운영:** launchd 등록, 로그 로테이션, notify_down.py 텔레그램 알림

---

## Phase 15: Content Quality Pipeline Integration
**Status:** ✅ **Complete** (commit `8b0ecd4aa`)
- 15-01: quality.db 스키마 + quality_recorder.py
- 15-02: curation pipeline post-publish hook (record_quality 호출)
- 15-03: hugo_builder.py (build_site wrapper)
- 15-04: /api/quality/* 5개 API + quality.html UI
- 15-05: daily_quality_aggregate.py + launchd plist

---

## 차기 Phase 후보 (Phase 16+)

### Phase 12 잔여: validate_keyword() 구현
**Priority: 🔴 HIGH** — silent failure 상태, 3분이면 수정 가능

### Phase 16: Production Hardening / Bug Patrol
**Priority: 🟡 MEDIUM** — 현재 발행 에러 0건, 예방 중심

### Phase 17: Content quality 데이터 기반 최적화 (quality.db 활용)
**Priority: 🟢 LOW** — 데이터가 누적되어야 의미 있음 (2주 후)

---

## Configuration

**현재 Phase 체계:** 15 phases (Phase 1-11 원래 roadmap, 6+7 merged, 13-15 추가)
