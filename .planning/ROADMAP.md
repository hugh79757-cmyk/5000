# Roadmap: 5000

**Last updated:** 2026-08-06

**Actual phases completed:** 32 phases 완료 (Phase 59 Planned)
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

**현재 Phase 체계:** 37 phases (Phase 32 완료, Phase 40~44 예정)

## Phase 32: TAP Scheduler Unload (Dual Scheduling Risk Removal)
**Status:** ✅ Complete (2026-07-24)
- V-1 dual scheduling risk 해결: `com.tap.scheduler` 언로드 + plist 비활성화
- `tap-blogger` 발행 주체를 5000 dispatcher로 일원화
- 코드/DB/발행 로직 변경 없음, launchd 서비스 상태만 변경
- 백업: `~/Library/LaunchAgents/com.tap.scheduler.plist.bak_20260724`
- 검증: TAP scheduler 목록 제거 확인, 5000 scheduler 생존 확인, 잔여 프로세스 없음

---

## Milestone 2: 콘텐츠 품질 혁신 (Phase 40–44)

**테마:** 6개 블로그(블로거1 + 휴고5) 본문 품질 개선 → 데이터/이미지/타이틀 검증 → 퍼널 연결성 확보 → 4개 블로그 확장 → 전수조사 마감

**전략:** 캠핑 블로그 1개로 완성 → 5개 전체 확장 (리스크 최소화)

---

### Phase 40: 본문 품질 개선 (파일럿: 캠핑 1개)
**Priority:** 🔴 HIGH
**Cycle:** 조사 → 진단 → 수정 → 검증(dry-run)
**Status:** ✅ Complete (2026-07-24)
- **변경 파일:** `config/models.yaml`(default.temperature 0.7→0.85), `pipelines/travel/writer.py`(max_tokens=4800), `config/prompts/travel.yaml`(분량 3,500→3,000자, ANTI-HALLUCINATION 2줄 추가)
- **40-01:** 현재 파라미터 확인 — temperature=0.7(하드코딩), max_tokens 미지정, 공통 모듈(`shared/ai_writer.py`) 통해 API 호출
- **40-02:** A/B dry-run 비교 — A(0.7/4096)=2,675자 vs B(1.0/6000)=3,109자
- **40-03:** 3개 파일 수정 완료 (models.yaml temperature 0.85, writer.py max_tokens=4800, prompts.yaml tour1_camping 개선)
- **40-04:** 최종 dry-run 검증 — 3,228자, 예약처 환각 0건, 문장 온전함
- **40-05:** 문서화 완료 (VERIFICATION.md, SUMMARY.md)
- **핵심 성과:** "네이버 카페"/"전화 예매"/"OO공단 홈페이지" 등 지어낸 예약 창구 완전 제거
- **VERIFICATION.md:** `.planning/phase-40-content-quality-pilot/VERIFICATION.md`

---

### Phase 41: 데이터·이미지·타이틀 로직 검증 (캠핑 1개)
**Priority:** 🔴 HIGH
**Cycle:** 조사 → 진단 → 수정 → 검증(dry-run)
**Status:** ✅ Complete (2026-07-24)
- **결론:** 결함 0건, 수정 불필요. 모든 영역 정상 동작 확인
- **41-01:** 썸네일 — `generate_content()` 미반환, Hugo 기본 fallback 사용 (의도된 설계)
- **41-02:** 본문 이미지 — `_inject_images()` 정상, 중복 이미지 스킵 설계 의도 확인
- **41-03:** 타이틀 — TITLE_TEMPLATES + MiMo API 정상, 제목 숫자(2곳)와 items_count(2) 일치
- **41-04:** 제목-본문 일치 — 지역명·장소명 일치 확인, 코드 검증 미구현 (프롬프트 의존)
- **41-05:** 수정 불필요 — 검증만으로 종료
- **이월 리스크:** 제목-본문 일치 코드 검증 미구현 → 향후 리스크
- **RESEARCH.md:** `.planning/phase-41-data-image-title-validation/RESEARCH.md`
- **VERIFICATION.md:** `.planning/phase-41-data-image-title-validation/VERIFICATION.md`

---

### Phase 42: 퍼널(funnel) 설계 검증 (5개 블로그 연결)
**Priority:** 🔴 HIGH
**Cycle:** 진단 → 검증
**Status:** ✅ Complete (2026-07-24)
- **결론:** 렌더링 결함 0건, 퍼널 단방향 구조는 의도된 설계로 확정
- **42-01:** 크로스링크 3종(shortcode/nearby-card/funnel-card) 전수 검증 → 모두 정상 렌더링
- **42-02:** raw 텍스트 노출 0건 — `{{< article >}}` shortcode 정상, div HTML balance 0
- **42-03:** 퍼널 단방향(4개 landing → 코스) 확인. bridge_to 전부 미설계. Blogger 퍼널 미적용
- **42-04:** "크로스링크 raw 노출" 결함 — 실재하지 않음 확인. 구두로 우려된 내용이었음
- **이월 리스크:** 퍼널 양방향/상호순환 미구현, Blogger 퍼널 미적용 → 트래픽 증가 후 재검토
- **VERIFICATION.md:** `.planning/phase-42-funnel-validation/VERIFICATION.md`

---

### Phase 43: 나머지 4개 블로그로 확장
**Priority:** 🟡 MEDIUM
**Cycle:** 조사 → 수정 → 검증(dry-run)
**Status:** ✅ Complete (2026-07-24)
- **Scope:** Phase 40~41 확정 패턴을 travel1(축제)·travel2(문화유산)·travel3(맛집)·travel4(코스)에 적용
- **Sub-tasks:**
  - 43-01: 각 주제별 데이터 필드 분석 (축제=입장료/기간, 맛집=메뉴/영업시간 등) ✅
  - 43-02: Phase 40 개선 패턴을 주제 특성에 맞게 각 프롬프트에 적용 ✅
  - 43-03: 블로그별 dry-run 검증 ✅
  - 43-04: 문제 발견 시 개별 수정 ✅
- **Results:**
  - travel1-hugo (축제): 2,659자 - 4/4 PASS
  - travel2-hugo (문화유산): 4,202자 - 4/4 PASS
  - travel3-hugo (맛집): 2,212자 - 4/4 PASS
  - travel4-hugo (코스): 2,418자 - 4/4 PASS (주제 적합성 검증 메트릭 이슈 → 재평가 PASS)
- **Acceptance:** 4개 블로그 dry-run 100% PASS (4/4), 주제별 데이터 필드 정상 반영 ✅
- **VERIFICATION.md:** `.planning/phase-43-expand-4-blogs/VERIFICATION-PHASE43.md`
- **COMPLETION-REPORT.md:** `.planning/phase-43-expand-4-blogs/PHASE43-COMPLETION-REPORT.md`

---

### Phase 44: 전수조사 및 전체 수정
**Priority:** 🟡 MEDIUM
**Cycle:** 진단 → 수정 → 검증
**Status:** 🟡 In Progress (44-01~03 완료, 44-04~05 진행 필요)
- **Scope:** 대표님 5번 항목 — 6개 블로그 전체 최종 품질 점검
- **Sub-tasks:**
  - 44-01: 최종 품질 기준 체크리스트 정의 ✅ (`config/quality_checklist.yaml` 생성)
  - 44-02: 6개 블로그(블로거1 + 휴고5) 전체 전수 점검 ✅ (3007개 포스트, 기존글 0.2% PASS — Phase 40~43 이전 발행글이므로 예상됨)
  - 44-03: 신규 발행이 개선 기준을 통과하는지 확인 🟡 (dry-run 1회/블로그 완료, 품질 대부분 통과하나 "좋은" 금지어·H2/H3 구조·브랜드 키워드 등 일부 미달)
  - 44-04: 미달 항목 최종 수정 (프롬프트 보완 후 재검증 필요)
  - 44-05: 마무리 및 커밋
- **Acceptance:** 6개 블로그 전체 품질 기준 충족, 추가 수정 불필요
- **Notes:** 
  - 기존 발행글(3007개)은 Phase 40~43 개선 이전 작성 → 품질 미달 당연
  - 신규 dry-run 생성글은 Phase 40~43 개선사항 반영돼 대부분 통과
  - 남은 이슈: "좋은" 전역 금지어 추가, H2 3-4개/H3 3개 구조 강제, 브랜드 키워드 1개 강제, travel4 코스명 패턴 "N코스:" 강제

---

## Phase 45: TAP Blog Meta-Response Detection & Prevention
**Priority:** 🔴 HIGH
**Cycle:** 조사 → 수정 → 검증
**Status:** 📋 Planned
- **Problem:** TAP 블로거(travel.rotcha.kr)가 AI 메타 응답("죄송합니다. 이미 작성했습니다...")을 실제 여행 콘텐츠 대신 발행
- **Root Cause:** 1) 프롬프트에 대화형 응답 금지 명시 안됨, 2) 검증기가 메타 응답 탐지 못함, 3) 재시도 로직 없음
- **Scope:** TAP core 모듈 (core/validators.py, core/ai_writer.py, app.py)
- **Sub-tasks:**
  - 45-01: core/validators.py에 메타 응답 탐지 패턴 10개+ 추가
  - 45-02: core/ai_writer.py 시스템 프롬프트에 안티-메타 규칙 강화
  - 45-03: ai_writer.generate_full_content()에 재시도 로직 (최대 2회)
  - 45-04: app.py 파이프라인 레벨 재시도 + 텔레그램 알림
  - 45-05: 드라이런 검증 (카테고리별 10회, 총 30회) + 회귀 테스트
- **Acceptance:** 드라이런 30회 중 메타 응답 0건, 검증 통과율 100%, 기존 100개 포스트 false-positive 0건
- **Dependencies:** Phase 44 품질 기준 완료 후 적용 권장

---

## Phase 46: (Reserved)

---

## Phase 49: Cross-link Creation Bug Fundamental Fix
**Priority:** 🔴 HIGH
**Cycle:** fix → batch → verify
**Status:** 📋 Planned

---

## Phase 50: CTA Button Center — CSS 표준화 + 인라인 스타일 마이그레이션
**Priority:** 🟡 MEDIUM
**Cycle:** css → python → batch → build → deploy
**Status:** ✅ Complete
- **Goal:** 10 CUAP 블로그 CTA 버튼 중앙 정렬, cross-sell/funnel/cta-box CSS 클래스 표준화, 인라인 스타일 → CSS 클래스 마이그레이션
- **Scope:** `cuap/*/assets/css/custom.css` (10개), `shared/cuap_entity_linker.py`, `pipelines/curation/pipeline.py`, `scripts/fix_cta_links.py`
- **Sub-tasks:**
  - 50-01: CSS 클래스 정의 (btn-price-check 중앙 정렬 + cross-sell/funnel/cta-box)
  - 50-02: 인라인 스타일 → CSS 클래스 마이그레이션 (cuap_entity_linker.py)
  - 50-03: CTA fallback CSS 클래스 + markdown CTA post-processing (pipeline.py)
  - 50-04: 기존 포스트 CTA 일괄 변환 스크립트 (scripts/fix_cta_links.py)
  - 50-05: Hugo 빌드 + 배포 (10개 블로그 0 에러)
- **Acceptance:** 10/10 CSS 완료, AST 3/3 OK, 10/10 빌드 0 에러, 10/10 배포 성공, 라이브 URL 200
- **Dependencies:** None

---

## Phase 51: Image URL Token Repetition Bug Fix
**Priority:** 🔴 HIGH
**Cycle:** scan → fix → pipeline → script → verify
**Status:** ✅ Complete
- **Goal:** Detect and fix LLM-generated image URLs with token repetition (e.g., `gLozv0gLozv0gLozv0...` x hundreds)
- **Scope:** `shared/publishers/hugo_writer.py`, `pipelines/curation/writer.py`, `scripts/fix_repeated_image_urls.py`
- **Sub-tasks:**
  - 51-01: 25개 Hugo 블로그(6000+ 포스트) 전수 스캔 → 1건 감염(health-hugo, 10888자 URL)
  - 51-02: 감염 파일 수정 (반복 패턴 제거 + HTTP HEAD 200 확인)
  - 51-03: `_fix_repeated_image_urls()` — 4자+ 5회+ 반복 패턴 감지/정리 함수, `_clean_body()` 및 `_sanitize_body()`에 통합
  - 51-04: `scripts/fix_repeated_image_urls.py` — --dry-run/--blogs/--backup-dir 지원
  - 51-05: 63/63 기존 테스트 통과 확인
- **Acceptance:** 전수 스캔 0건, 파이프라인 신규 생성 URL 0건, 63/63 테스트 통과

---

## Phase 52: Blowfish 블로그 표준화 + 테마 업그레이드 대응
**Priority:** 🔴 HIGH
**Cycle:** survey → standardize → build → deploy → verify
**Status:** 🔄 Wave 1 진행 중
- **Goal:** 36개 Blowfish 블로그를 techpawz-hugo 표준(v1.1)으로 통일, Hugo 테마 업그레이드에 대응 가능한 구조로 전환
- **Scope:** CUAP 10개 + CAP 7개 + STAP 5개 + TAP 5개 + RAP 4개 + SEAP 1개 + 개별 4개 = 36개 블로그
- **Sub-tasks:**
  - 52-01: extend-head.html 단순화 — 36개 블로그 adsense only (GA4/lazy-load 제거) ✅ (35개 수정 완료, 1개 스킵)
  - 52-02: extend_head.html 신규 생성 — 26개 블로그 (CUAP 10개 제외)
  - 52-03: baseof.html 삭제 — 30개 블로그 (테마 기본 사용)
  - 52-04: single.html 정비 — Description lead 제거(12개) + H2 분할 인젝션(11개)
  - 52-05: ad partial 정비 — overflow:hidden, push script 위치, 하드코딩→템플릿 변수
  - 52-06: Hugo 빌드 + 배포 — 36개 블로그 0 에러
- **Acceptance:** 36개 블로그 표준화 완료, Hugo 빌드 0 에러, 배포 성공, 라이브 광고 노출 확인
- **Dependencies:** `Blowfish-Hugo-테마-업그레이드-표준-지침서.md` v1.1, `ADSENSE-GUIDE.md`
- **Documents:**
  - `.planning/phase-52-blowfish-standardization/RESEARCH.md` — 전수 조사 분석
  - `.planning/phase-52-blowfish-standardization/PLAN.md` — 6-wave 실행 계획


---

## Phase 53: Complete Phase 52 Wave 6: Build and Deploy
**Status:** 📋 Planned

### 6-1. 그룹별 Hugo 빌드 검증

| 순서 | 그룹 | 수 | 비고 |
|------|------|----|------|
| 1 | CUAP (Workers) | 10 | Start building sites … 
hugo v0.160.1+extended+withdeploy darwin/arm64 BuildDate=2026-04-08T14:02:42Z VendorInfo=Homebrew


                  │  KO  
──────────────────┼──────
 Pages            │ 1111 
 Paginator pages  │    0 
 Non-page files   │   54 
 Static files     │   15 
 Processed images │    0 
 Aliases          │ 5052 
 Cleaned          │    0 

Total in 1087 ms + 
 ⛅️ wrangler 4.110.0
──────────────────── |
| 2 | CAP (Pages) | 7 | Start building sites … 
hugo v0.160.1+extended+withdeploy darwin/arm64 BuildDate=2026-04-08T14:02:42Z VendorInfo=Homebrew


                  │  KO  
──────────────────┼──────
 Pages            │ 1111 
 Paginator pages  │    0 
 Non-page files   │   54 
 Static files     │   15 
 Processed images │    0 
 Aliases          │ 5052 
 Cleaned          │    0 

Total in 870 ms + 
 ⛅️ wrangler 4.110.0
──────────────────── |
| 3 | STAP (Pages) | 5 | Start building sites … 
hugo v0.160.1+extended+withdeploy darwin/arm64 BuildDate=2026-04-08T14:02:42Z VendorInfo=Homebrew


                  │  KO  
──────────────────┼──────
 Pages            │ 1111 
 Paginator pages  │    0 
 Non-page files   │   54 
 Static files     │   15 
 Processed images │    0 
 Aliases          │ 5052 
 Cleaned          │    0 

Total in 866 ms + 
 ⛅️ wrangler 4.110.0
──────────────────── |
| 4 | TAP (Pages) | 5 | Start building sites … 
hugo v0.160.1+extended+withdeploy darwin/arm64 BuildDate=2026-04-08T14:02:42Z VendorInfo=Homebrew


                  │  KO  
──────────────────┼──────
 Pages            │ 1111 
 Paginator pages  │    0 
 Non-page files   │   54 
 Static files     │   15 
 Processed images │    0 
 Aliases          │ 5052 
 Cleaned          │    0 

Total in 848 ms + 
 ⛅️ wrangler 4.110.0
──────────────────── |
| 5 | RAP (Pages) | 4 | Start building sites … 
hugo v0.160.1+extended+withdeploy darwin/arm64 BuildDate=2026-04-08T14:02:42Z VendorInfo=Homebrew


                  │  KO  
──────────────────┼──────
 Pages            │ 1111 
 Paginator pages  │    0 
 Non-page files   │   54 
 Static files     │   15 
 Processed images │    0 
 Aliases          │ 5052 
 Cleaned          │    0 

Total in 913 ms + 
 ⛅️ wrangler 4.110.0
──────────────────── |
| 6 | SEAP + 개별 (Pages) | 5 | Start building sites … 
hugo v0.160.1+extended+withdeploy darwin/arm64 BuildDate=2026-04-08T14:02:42Z VendorInfo=Homebrew


                  │  KO  
──────────────────┼──────
 Pages            │ 1111 
 Paginator pages  │    0 
 Non-page files   │   54 
 Static files     │   15 
 Processed images │    0 
 Aliases          │ 5052 
 Cleaned          │    0 

Total in 898 ms + 
 ⛅️ wrangler 4.110.0
──────────────────── |

### 6-2. 배포 후 검증

- 각 블로그 라이브 URL HTTP 200 확인
- adsbygoogle.js 로드 확인 (개발자 도구 Network 탭)
- top 광고 + in-article 광고 노출 확인
- 모바일 레이아웃 오버플로 확인

---

## Acceptance Criteria

- [ ] 36개 블로그 extend-head.html: adsense 즉시 로드만 (GA4/lazy-load 없음)
- [ ] 36개 블로그 extend_head.html: GA4 + 모바일 보정 CSS 포함
- [ ] 30개 블로그 baseof.html: 삭제 완료 (테마 기본 사용)
- [ ] 12개 블로그 single.html: Description lead 제거
- [ ] 11개 블로그 single.html: H2 분할 인젝션 추가
- [ ] 36개 블로그 ad partials: overflow:hidden;min-height:100px 적용
- [ ] 36개 블로그 Hugo 빌드 0 에러
- [ ] 36개 블로그 배포 성공
- [ ] 라이브 사이트 광고 노출 확인



---

## Phase 54: Curation Title Generation Hardening (제목 생성 하드코딩 fallback 제거)
**Status:** 📋 PLANNED (2026-08-01, 리넘버: 기존 "Phase 49" 표기 — `.planning/phase-49-crosslink-bugfix`와 번호 충돌로 54로 변경. 51/52/53 이미 점유)
**Plan:** `.planning/phase-54-title-hardening/PLAN.md`
**Context:** Phase 43이 "Title Generation Fix"로 COMPLETED 표기되었으나 fallback 로직 미수정 → 재발 (publish_log "추천 TOP5 (연도년)" 패턴 134건 누적, 2026-08-01 발행분 5건 연속)
**Goal:** 하드코딩 fallback(`{keyword} 추천 TOP5 (연도년)`) 제거 + H1 출력 형식 강제 + CoT/프롬프트 누출 차단 + 회귀 테스트 — 신규 발행 제목 템플릿 패턴 0건 (fail-closed)
**Key Tasks:**
- writer.py:538-539 하드코딩 fallback 제거 → H1 누락 시 제목 전용 재생성 루프 (템플릿 패턴 검증 + CoT 거부 + max 2 retry, 실패 시 발행 중단)
- writer.py `_build_system_prompt`에 H1 출력 형식 지시 + CoT/프롬프트 누출 금지 추가
- writer.py description 추출 `_extract_description()` 헬퍼 분리 (CoT 첫 문장 거부)
- pipeline.py 큐레이션 발행 전 제목 게이트 (thin wrapper, 기존 TITLE_BLOCKED 위, dict 반환 하위 호환)
- 회귀 테스트: publish_log 신규 기록에 템플릿 패턴(`추천\s*TOP\s*\d+`, `BEST\s*\d+`, `\(\d{4}년\)$`) 0건 검증
**Follow-up candidate:** keyword metadata enrichment (RESEARCH 4.5) — Phase 54에서 스코프 제외, 별도 phase로 이연

---

## Phase 55: Curation Content Quality Diagnostics (큐레이션 콘텐츠 품질 진단)
**Status:** 📋 PLANNED (2026-08-02, Phase 54 완료 후 잔존 품질 문제 조사)
**Context:** Phase 54로 CoT/프롬프트 노출은 차단되었으나, 경험 허위 주장(30%), 소스 불명 수치(30%), 건강 효능 단정(20%) 등 3가지 잔존 품질 문제 발견. 10개 블로그 표본에서 최소 1개 위반 70%.
**Goal:** 프롬프트 실태 분석 + 품질 문제 측정 + 개선 지렛대 제안 (read-only, 코드/프롬프트 변경 없음)
**Key Tasks:**
- 프롬프트(_build_system_prompt, BLOG_EXTRA_RULES) 품질 관련 지시 분석
- 10개 블로그 발행 글 표본에서 Q1(경험 주장), Q2(소스 불명), Q3(효능 단정), Q4(반복 H2), Q5(CoT) 측정
- 개선 지렛대 5개 제안: A(1인칭 금지), B(효능 금지), C(소스 인용), D(템플릿 다양화), E(후처리 필터)
**Deliverable:** `.planning/phase-55-curation-quality-diagnostics/CONTEXT.md`
**Follow-up candidate:** Phase 56으로 지렛대 B(효능 금지) + A(1인칭 금지) 실제实施 검토

---

## Phase 58: 발행 문제 인벤토리 + 정밀 Telegram 알림 시스템
**Priority:** 🔴 HIGH
**Cycle:** 조사 → 구현(additive) → 검증(dry-run)
**Status:** 📋 Planned (2026-08-06)
**Plan:** `.planning/phase-58-publish-problem-telegram-alerting/PLAN.md` (v2, PLAN-CHECK PASS)
**Context:** 발행 오류 알림이 `send_error` 단일 템플릿(raw reason)이라 문제 원인 식별 불가. similar_title·CJK/CoT 누수·배포 실패(ETAP/Workers)·이미지 URL 반복 등 8건이 침묵 상태.
**Goal:** 24개 발행 문제(P01~P24)를 PROBLEM_REGISTRY에 등록하고, 발행 시 문제 발생 시 **어떤 문제인지 정확한 문제별 한국어 Telegram 알림**을 신규 PublishMonitor 단일 진입점으로 전송 (additive, 기존 `_tg_error` 경로 보존).
**Key Tasks:**
- 신규 모듈 3종: `shared/problem_registry.py`(ProblemSpec+PROBLEM_REGISTRY 24건), `shared/problem_detectors.py`(순수 탐지), `shared/problem_monitor.py`(PublishMonitor+dry-run)
- 통합 지점 6곳: dispatcher 결과 파싱/배포 반환 캡처, curation run(), post-generate raw 훅(sanitize 이전), post-publish 검증, P22 ai_generate RuntimeError 캐치
- 심각도 정책: CRITICAL=always+60분 쿨다운 / MAJOR=consecutive:3 / MINOR=quiet. `PROBLEM_ALERT_DRY_RUN=1` 롤아웃
- CJK 오탐 방지: 한글 비율 0.5 기반 (travel2 heritage 한자 병기 86건 오탐 실측 반영)
- 검증: 신규 테스트 4파일 + 기존 스위트 회귀 0건 게이트
**이연(Phase 59):** `notify.py` 교체, 죽은 코드(`send_validation`/`send_no_result_alert`) 삭제, 기존 `_tg_error` 경로 단일화, `_has_repeated_pattern` 3중 복제 통폐합

---

## Phase 56: CUAP 키워드 정리 + 임계값 완충 → kitchen/beauty 재활성화
**Status:** ✅ Complete (2026-08-03)
**Plan:** `.planning/phase-56-cuap-keyword-threshold/PLAN.md`
**Commits:** `2ca280808` (키워드 정리 + 완충 수정), `daedef5b1` (재활성화)
**Result:** kitchen/beauty [정상화 통과], active 유지
**Key Changes:**
- kitchen-hugo: 중국어/혼합어 키워드 70개 제거 (핵심 62개 유지)
- beauty-hugo: 비주제 키워드 100개 제거 (핵심 42개 유지)
- alert_thresholds.py: maybe_alert()에 연속 횟수 확인 추가
- pipeline.py: consecutive_failures를 maybe_alert()에 전달
- cuap.yaml: kitchen-hugo, beauty-hugo → active + force_draft:true

---

## Phase 59: Ops Dashboard + Blowfish 표준 단일화 + 파이프라인 통합
**Priority:** 🔴 HIGH
**Cycle:** 조사 → 구현(staged rollout) → 검증
**Status:** 📋 Planned (2026-08-06)
**Plan:** `.planning/phase-59-ops-dashboard-and-unification/PLAN.md`
**Context:** 85개 블로그의 운영 상태를 모바일/웹에서 실시간 파악하는 대시보드 구축 + Blowfish 테마 단일 소스 고정 + 7갈래 파이프라인 분기 단일화
**Goal:**
1. Ops Dashboard: "무엇이 왜 고장났고, 언제 멈췄고, 표준에서 얼마나 벗어났는지" 실시간 파악
2. Blowfish: 테마 오버라이드를 단일 소스로 고정, PaperMod/Congo → Blowfish 통일
3. 파이프라인: ETAP `_write_hugo_post()` 35중복 제거, publisher.py 토큰 불일치 해소
**Key Tasks:**
- Wave 1: ops_dashboard Flask UI + 헬스체크 엔진 + JSON API (포트 5060)
- Wave 2: Cloudflare Tunnel 원격 접근 + 텔레그램 알림 통합
- Wave 3: Blowfish 테마 단일화 (hotissue PaperMod→Blowfish, stock Congo→Blowfish)
- Wave 4: ETAP `_write_hugo_post()` 35중복 → shared/hugo_writer.py 수렴 (staged rollout)
- Wave 5: dispatcher flights-hugo 이름 정렬 + publisher.py 토큰 죽은 코드 제거
- Wave 6: 전체 검증 + GSD 문서 업데이트
**Acceptance:**
- ops dashboard에서 CUAP stale + senior 썸네일 + CJK 릭 + 표준 위반 노출
- ETAP `_write_hugo_post()` 중복 0건
- 테마 3종 → Blowfish 1종
**Dependencies:** `ADSENSE-GUIDE.md`, `Blowfish-Hugo-테마-업그레이드-표준-지침서.md v1.2`, `audit_5000.md`
**Documents:**
- `.planning/phase-59-ops-dashboard-and-unification/CONTEXT.md` — 요구사항
- `.planning/phase-59-ops-dashboard-and-unification/RESEARCH.md` — 코드베이스 분석
- `.planning/phase-59-ops-dashboard-and-unification/PLAN.md` — 6-wave 실행 계획
