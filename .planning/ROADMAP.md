# Roadmap: 5000

**3 phases** | **10 requirements mapped** | All v1 requirements covered ✓

## Phase 1: Foundation — Test & Tooling Infrastructure

**Goal:** Establish test framework, linting, CI pipeline, and verify Python 3.14 compatibility
**Mode:** mvp
**Requirements:** STB-01, STB-04, STB-05, STB-06

**Success Criteria:**
1. `pytest` runs with >70% coverage on shared/ modules
2. `ruff check .` passes with no errors
3. `mypy .` passes for shared/ and pipelines/
4. GitHub Actions runs lint + test on push
5. `check_package_imports()` removed from `dispatcher.py`

**Plans:**
1. Tooling & test infra — pytest, ruff, mypy config, CI workflow
2. Unit tests for shared modules — validators, humanizer, telegram_notifier

---

## Phase 2: Core Refactoring — Simplify Central Modules

**Goal:** Replace brittle routing in dispatcher, split monolith publisher, clean up backup pollution
**Mode:** mvp
**Requirements:** STB-07, STB-08, STB-03

**Success Criteria:**
1. New blogs require config entry only (no elif chain in dispatcher)
2. `shared/publisher.py` split into 3+ focused platform modules
3. Zero `.bak*` files in source directories
4. All existing pipelines still deploy correctly

**Plans:**
1. Dispatcher registry — dynamic pipeline lookup
2. Publisher decomposition — per-platform modules
3. Backup file cleanup

---

## Phase 3: Hardening — Stability & Decoupling

**Goal:** Eliminate hardcoded paths, consistent error handling, isolate external deps
**Mode:** mvp
**Requirements:** STB-02, STB-09, STB-10

**Success Criteria:**
1. Zero hardcoded absolute paths in source code
2. Every `except Exception` block logs actionable context
3. TAP/STAP/ETAP import failures produce clear error messages with upgrade instructions
4. All pipelines run from clean clone with env-only config

**Plans:**
1. Path configuration — env-driven project roots
2. Error handling audit — consistent patterns across all modules
3. External dependency isolation — interface wrappers

---

## Phase 4: TAP Publishing Stabilization — Post-Refactoring Bug Fixes

**Goal:** Fix 5 regressions introduced by Phase 2/3 refactoring that broke TAP travel blog content
**Mode:** fix (sequential — each bug resolved before next)
**지연: t_0 + 14일 (Phase 3 완료 후 즉시)**

**Success Criteria:**
1. Trip.com CTA HTML이 발행된 글에 정상 렌더링됨
2. `{{}}` 빈 템플릿 잔재가 발행된 글에 나타나지 않음
3. "지도에서 보기" 평문이 본문에 노출되지 않음
4. `no_result` 실패 시 backoff가 작동하여 재시도 폭주 방지
5. 썸네일 이미지가 정상 표시됨
6. travel4-hugo 블로그의 `--dry-run` 발행 테스트 통과
7. 기존 travel1/2/3-hugo, travel-hugo 발행에 영향 없음

**Plans:**
1. **Formatting fixes** — CTA HTML 보존 + 썸네일 키 복원
2. **Content & pipeline fixes** — `{{}}` 제거 + 지도보기 regex + no_result backoff

---

## Phase 5: Post-Stabilization Enhancement — 복구 + 테마 + 모니터링

**Goal:** 이미 발행된 손상 글 복구, Blowfish 테마 업그레이드, 모니터링 시스템 구축
**Mode:** hybrid (fix: 05-01/05-02, mvp: 05-03)
**지연: Phase 4 완료 후 즉시**

**Success Criteria:**
1. 7/1일 발행된 2개 손상 글의 CTA/썸네일/`{{}}`가 모두 수정됨
2. Blowfish 테마가 v2.x로 업그레이드되어 `cover.image:` 키 정상 지원
3. `_clean_body()` DOTALL regex가 모든 AI 생성 섹션 변형을 커버
4. 발행 후 HTML 자동 검증이 CTA/썸네일/`{{}}`/지도보기를 감지
5. 검증 실패 시 Telegram 알림 전송
6. 기존 travel1/2/3-hugo, travel-hugo 발행에 영향 없음

**Plans:**
1. **7/1 글 수동 복구** — index.md 패치 + Hugo rebuild + wrangler deploy
2. **Blowfish 테마 업그레이드 + DOTALL 확장** — v2.x 업데이트, regex 패턴 확장
3. **모니터링 & 관측 시스템** — HTML 검증, Telegram 리포트, 품질 통계

---

## Phase 9: AI-Tell Pattern Enrichment — humanizer.py

**Goal:** `_SYSTEM_PROMPT`에 누락된 B/E/H/I/J계열 AI 티 패턴 16개 추가
**Mode:** refactor
**Commit:** `0a17cf55b`

**Success Criteria:**
1. `_SYSTEM_PROMPT` 10대 카테고리(A~J) 전면 커버
2. im-not-ai ai-tell-taxonomy.md v2.0 기준 16개 패턴 추가
3. 기존 테스트 65/65 통과
4. 길이 ±15% 가드, 영문 70% 스킵 등 안전장치 유지

**Plans:**
1. **09-01** — A계열 보강(4) + B/E/H/I/J계열 신규(12) = 16패턴

---

## Phase 10: Blowfish Engagement Optimization — tour1.rotcha.kr

**Goal:** Add Blowfish theme shortcodes (lead, figure, alert, badge, gallery, accordion, chart) to AI-generated camping articles to increase time-on-page and engagement
**Mode:** mvp
**Commit:** (pending)

**Success Criteria:**
1. First paragraph in new articles displays with larger lead styling via `{{< lead >}}`
2. Images display with captions via `{{< figure >}}` (replacing bare `![alt](url)`)
3. Pet policy and facility tips shown in `{{< alert >}}` callout boxes
4. Camping type shown via `{{< badge >}}` inline badge next to camp name
5. Consecutive images grouped into `{{< gallery >}}` shortcode
6. Facility/amenity sections use `{{< accordion >}}` collapsible sections
7. Campsite stats displayed as Chart.js radar/bar chart via `{{< chart >}}`
8. Only new articles affected — existing published articles unchanged
9. Hugo build succeeds without errors for travel-hugo

**Plans:**
1. **10-01** — P0 Post-processor: lead + figure shortcodes (hugo_writer.py)
2. **10-02** — P1 AI Prompt: alert + badge shortcode instructions (travel.yaml)
3. **10-03** — P2 Post-processor + Prompt: gallery + accordion (hugo_writer.py + travel.yaml)
4. **10-04** — P3 Post-processor: chart shortcode via embedded data comment (pipeline + publisher)

---

## Configuration

**Granularity:** Coarse (3 phases) + Fix (1 phase) + Enhancement (2 phases) + Optimization (1 phase)
**Execution:** Parallel within phases
**Mode:** Vertical MVP (each phase delivers end-to-end improvement)
**Research:** Yes (before each phase)
**Plan Check:** Yes
**Verifier:** Yes
