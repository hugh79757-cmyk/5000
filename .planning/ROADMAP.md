# Roadmap: 5000

**Last updated:** 2026-07-21

**Actual phases completed:** 28 phases 완료
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
**Status:** ✅ **Complete** (commit `88d257e9f`)
- ✅ `detect_problematic_posts.py` — `--scan-body` flag 구현됨
- ✅ `keyword_expander.py` — `validate_keyword()` 호출 코드 있음
- ✅ `validate_keyword()` 함수 `keywords.py`에 추가 (circular import 방어 lazy import)
- ✅ 키워드 검증 게이트 정상 작동

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

## Phase 16: Production Hardening — 마무리 작업
**Status:** ✅ **Complete** (commit `8502d232d`)
- **16-01:** keywords.py circular import 확인 — lazy import 검증 통과
- **16-02:** STB-02 Hardcoded `/Users/twinssn/...` paths 제거 — `shared/paths.py`로 중앙화
- **16-03:** STB-13 Config schema validation — `shared/config_validator.py` 생성
- **16-04:** Blowfish shortcode toggle — 이미 활성화됨 (default True) 확인
- **16-05:** Pipeline hook travel/stock 확장 — quality_recorder.record_quality() 연결
- **16-06:** `detect_problematic_posts.py --scan-body` 실행 (101건 탐지)
- **16-07:** empty_template regex fix 검증 — `r"\{\}"`→`r"\{\{[\s]*\}\}"` PASS
- **16-08:** Uncommitted changes 정리 — 2개 커밋 (Phase 16 + session artifacts)

---

## Phase 17: Content Quality Enhancement — 콘텐츠 품질 고도화
**Status:** ✅ **Complete** (2026-07-12)

### Phase 17 작업
| 번호 | 작업 | 상태 |
|------|------|------|
| 17-01 | senior-hugo 제목 CTR 최적화 | ⚪ 보류 (기존발행글은 수정 안함) |
| 17-02 | travel-hugo 실시간 정보 섹션 추가 | ✅ 완료 |
| 17-03 | dividend-hugo 유사 글 차별화 | ✅ 완료 |
| 17-04 | dividend-hugo 기초재무분석 추가 | ✅ 완료 |
| 17-05 | 전체 블로그 출처 명시 강화 | ✅ 완료 |

### 상세 내용
**17-01 senior-hugo 제목 개선** (CTR 3/10 → 8/10 목표)
- Before: "60세 이상 고령자 고용지원금, 분기당 30만원 지원조건은?"
- After: "고령자 고용지원금으로 인건비 30만원 절약하는 법 (신청서류·조건 총정리)"
- 원칙: 관료적 표현 제거, 혜택 중심, 초보자 친화적

**17-02 travel-hugo 실시간 정보 섹션**
- 모든 기사 끝에 표준화된 블록 추가:
  - 날씨 확인 링크 (기상청, 네이버 날씨)
  - 예약 가능 여부 확인 (네이버 지도)
  - 공지사항 확인 (해당 시설 공식 홈페이지)

**17-03 dividend-hugo 글 차별화**
- 유사한 top 10 글들을 목적별로 재분류:
  - 고수익 추구형 (월배당 가능 고배당주)
  - 안정성 우선형 (배당성향 30-70% 우량주)
  - 성장 배당주 (배당 증가율 10% 이상)

**17-04 dividend-hugo 기초재무분석**
- 배당률·배당성향·부채비율·유비율·ROE 등 종합 진단표 추가
- 출처: DART 전자공시, 한국거래소

**17-05 출처 명시 강화**
- 모든 지원금·혜택 관련 글에 공식 출처 링크 추가
- 정부24, 한국거래소, 도로교통공단 등 신뢰할 수 있는 출처 명시
- 할루시네이션 방지를 위한 팩트체크 원칙 적용

---

## Next (Phase 18+)

### Phase 18: Content quality 데이터 기반 최적화 (quality.db 활용)
**Priority: 🟢 LOW** — 데이터가 누적되어야 의미 있음 (2주 후)

### Phase 19: AdSense Publisher ID Standardization + Sticky Ad Removal
**Priority: 🟡 MEDIUM** — 앵커광고 정상화, 도메인별 pub ID 최종 검증, mobile-sticky 제거

### Phase 20: Hugo Build 안정화 (`--minify` 호환성 + badge shortcode)
**Priority: 🟡 MEDIUM** — CUAP/TAP baseof.html dead code 제거, badge shortcode 호환성 수정

### Phase 21: Funnel Automation — 퍼널 구조 자동화
**Priority: 🔴 HIGH** — 블로그 간 퍼널 관계 정의, 퍼널 링크 자동 삽입, STAP entity_linker 버그 수정

### Phase 27: CUAP Cross-Sell Card 404 Fix
**Priority: 🔴 HIGH** — baby 블로그 하단 크로스셀 카드 `-rec` 404 (Phase 25 샘플 데이터 오염)
**Status:** ✅ Complete (2026-07-21)
- 근본원인: `cuap_entities`(travel-en.db) 29건 전부 Phase 25 테스트 데이터, 실제 발행 slug 0건. `register_cuap_entity()` 미호출.
- 16개 발행 포스트에 `-rec` 404 URL 베이크됨. 실제 발행 글은 블로그별 68~260개 존재.
- 수정: DB purge → filesystem 백필 → 16파일 URL 교체 → 재배포 → 라이브 200 검증.

---

### Phase 28: CUAP Worker 404→500 Fix
**Priority: 🔴 HIGH** — 6개 Worker 블로그(kitchen 포함)에서 missing-asset 접근 시 HTTP 500 반환 버그
**Status:** ✅ Complete (2026-07-21)
- 근본원인: `kitchen-hugo/src/index.js`(268-byte)의 `catch`가 missing asset을 무조건 500 "Error"로 변환. 나머지 5개는 142-byte 공유본(try/catch 없음, 정상).
- 수정: 6개 전체를 canonical worker(`ASSETS.fetch` 직접 반환 + `catch → 404`, never 500)로 통일. md5 `5667ff889e7f951b5c4f98a94293a6b2` 일치.
- 배포: `deploy_site()`로 6개 Worker 블로그 순차 재배포 (EXIT=0).
- 검증: 6/6 missing path → 404 (아님 500), 6/6 real post → 200 (regression guard 통과).

### Phase 29: CUAP 콘텐츠 오염 + 퍼널 카드 404 + 광고 공백 수정
**Priority: 🔴 HIGH** — pet-hugo에 뷰티 글 발행, cuap_entities URL 불일치로 크로스셀 404, beauty-hugo 미배포로 광고 공백
**Status:** ✅ Complete (2026-07-22)
- **29-01:** `keywords.py` pet-hugo 키워드에서 `"관리"` 제거 + 문법 오류 수정 (콤마 누락 8건)
- **29-02:** `cuap_entities` DB 오염 URL 27건 정리 (4건 삭제 + 23건 slug 업데이트)
- **29-03:** beauty-hugo 재배포 → 라이브 200 확인
- **29-04:** 광고 partial 검증 — `ca-pub-6677996696534146` + ad-slot `2195212287` 정상 로드 확인

## Configuration

**현재 Phase 체계:** 29 phases (Phase 29 진행 중)
