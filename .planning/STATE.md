---
gsd_state_version: 2.0
milestone: v1.1
milestone_name: milestone
status: active
last_updated: "2026-08-01T19:20:00Z"
progress:
  total_phases: 30
  completed_phases: 29
  percent: 97
---

# Project State: 5000

**Status:** v1.1 — **Phase 50 완료 (CTA Button Center), 운영 안정화 단계**
**Initialized:** 2026-06-30

## 배포 방식 (CI 없음)
- GitHub으로 push하지 않음. GitHub Actions workflow 불필요.
- 로컬 launchd daemon → run_5000.sh → scheduler.py 실행
- Hugo 사이트는 Cloudflare Pages (무료 플랜, 월 500빌드 제한)에 wrangler 직접 배포
- Cloudflare Pages ↔ GitHub 연동 해제 상태 (STB-06 의도적 제외)
- .github/workflows/ 디렉토리는 존재하지 않음 (의도적 제거)

## Deployment
- **Python 3.14** — uv 기반 가상환경, launchd로 상시 가동
- **Cloudflare Pages** — wrangler CLI로 직접 배포 (월 500회 제한)
- **Hugo** — `/opt/homebrew/bin/hugo` (shared.paths.HUGO_PATH로 중앙 관리)

## Architecture
- **Pipeline model:** 각 pipeline(`pipelines/{pipeline}/`)이 독립적으로 publish 함수 노출
- **Config:** `config/blogs.yaml` (master) + `config/blogs.d/*.yaml` (blog 정의) + `config/prompts.yaml` (프롬프트)
- **DB:** SQLite per pipeline (`data/*.db`) + quality.db (Phase 15)
- **Dashboard:** Flask + Chart.js at http://localhost:5050

---

## All Phases Status

| Phase | Description | Status | Commit |
|-------|-------------|--------|--------|
| 1 | Foundation — Test & Tooling Infrastructure | ✅ | 초기 CI/테스트 인프라 |
| 2 | Core Refactoring — Simplify Central Modules | ✅ | dispatcher registry + publisher 분할 |
| 3 | Hardening — Stability & Decoupling | ✅ | `139e5fdda` |
| 4 | TAP Publishing Stabilization | ✅ | `139e5fdda` |
| 5 | Post-Stabilization Enhancement | ✅ | Blowfish 업그레이드 + 모니터링 |
| 6+7 | Maintenance, Testing, Content Enhancement | ✅ | `def74aeef` |
| 8 | Content Cleanup | ✅ | `7c2c8a701` |
| 9 | AI-Tell Pattern Enrichment | ✅ | `0a17cf55b` |
| 10 | Blowfish Engagement Optimization | ✅ | `ebbfc815b` |
| 11 | AdSense 고효율 광고 구조 개선 | ✅ | 코드 완료 (docs에는 deferred로 표기) |
| 12 | Body Content Rescan & Keyword Validation Gate | ✅ | `88d257e9f` |
| 13 | Unified Dashboard — Data Collection + UI | ✅ | `4335f7a6b` |
| 14 | Cross-Project Dashboard Integration | ✅ | `4335f7a6b` |
| 15 | Content Quality Pipeline Integration | ✅ | `8b0ecd4aa` |
| 16 | Production Hardening — 마무리 작업 | ✅ | `8502d232d` |
| 17 | Content Quality Enhancement — 콘텐츠 품질 고도화 | ✅ | 완료 (2026-07-12) |
| 24 | CUAP 콘텐츠 품질 고도화 — 키워드 정리 + 타이틀 최적화 + 이미지 중복 방지 | ✅ | 완료 (2026-07-20) |
| 28 | CUAP Worker 404→500 Fix — 6개 Worker 블로그 missing-asset 500 → 404 | ✅ | 완료 (2026-07-21) |
| 49 | CUAP Cross-link Bugfix — 크로스링크 slug 불일치 근본 수정 + 전수 배치 수정 | ✅ | `4b33b43fd` + `1b249d615` (2026-07-26) |
| 50 | CTA Button Center — CSS 클래스 표준화 + 인라인 스타일 마이그레이션 | ✅ | 완료 (2026-07-26) |
| 52 | Blowfish 블로그 표준화 + 테마 업그레이드 대응 | 🔄 | Wave 1 진행 중 (2026-07-28) |

---

## Quick Tasks Completed

| Date | Task | Commit |
|------|------|--------|
| 2026-07-26 | Fix _validate_frontmatter split("---") regression — description 내 markdown table separator(---)로 YAML 파싱 실패 → regex 기반 분리로 수정 (rap3/4/5 발행 실패 5건 원인 해결) | `4bda255f6` |
| 2026-07-11 | kuta-hugo 썸네일 깨짐 수정 — batch_thumbnails.py 실행, R2 업로드 확인. blogsmith auto-publisher 썸네일 자동 생성 여부 조사 완료 (gradient overlay 방식, 5000 pipeline 발행 글은 수동 필요) | `완료` |
| 2026-07-10 | Phase 17 — senior-hugo 제목 7개 최적화 (17-01), travel-hugo 실시간 정보 20개 추가 (17-02), dividend-hugo 제목+목적박스 (17-03), senior-hugo 출처 394개 표준화 (17-05), travel-hugo 출처 22개+dividend 면책 2개 (17-05) | `진행 중` |
| 2026-07-09 | 미공개 초안 삭제 — senior-hugo 2개 draft 제거 | `완료` |
| 2026-07-09 | Phase 16 complete — Hardcoded paths, config validation, pipeline hooks, body scan | `8502d232d` |
| 2026-07-09 | Phase 12 fix — validate_keyword() 추가, empty_template regex 수정 | `88d257e9f` |
| 2026-07-08 | Phase 15 complete — Content Quality Pipeline Integration | `8b0ecd4aa` |
| 2026-07-08 | Phase 13+14 complete — Dashboard Wave 1-4 | `4335f7a6b` |

---

## Phase 25: CUAP 거미줄 엔티티 시스템 (2026-07-20)

**목표:** CUAP 10개 블로그 간 크로스 링크 시스템으로 사용자 순회 유도 + 광고 노출 기회 2~3x 증대

**구현 내용:**
- `shared/cuap_entity_linker.py` 신규 생성 (ETAP entity_linker.py 패턴 재사용, category 기반)
  - `CROSS_GRAPH` (10개 블로그 고정 퍼널 경로), `BLOG_DOMAINS`, `ICONS`, `THEME_COLORS`
  - `register_cuap_entity()`, `inject_cross_blog_links()`, `build_cross_sell_card()`, `build_funnel_header()`, `init_cuap_tables()`
  - travel-en.db에 `cuap_entities` + `cuap_link_graph` 테이블 추가 (ETAP entity_links는 미수정)
- `pipelines/curation/pipeline.py` 통합
  - import + `init_cuap_tables()` (모듈 로드 시 1회)
  - 발행 직전: `inject_cross_blog_links()` + `build_cross_sell_card()` + `build_funnel_header()` (fail-open)
  - 발행 성공 후: `register_cuap_entity()` (다음 발행분 크로스 링크 대상)
- Hugo 레이아웃 (10개 블로그)
  - `layouts/partials/cuap-spider-links.html` 신규 (fallback: related.html)
  - `layouts/_default/single.html` 라인 85: `related.html` → `cuap-spider-links.html`
- `scripts/init_cuap_link_graph.py`, `scripts/register_sample_cuap_entities.py` (초기 데이터)

**검증:**
- T1 import PASS, T2 table PASS, T3/T4 AST PASS, T5/T6 Hugo partial PASS, T7 link_graph (60 entries/10 blogs) PASS, T8 entities (10/10 blogs) PASS, T9 integration PASS, T10 Hugo build PASS
- appliance-hugo Hugo 빌드 성공 (에러 없음)

**다음 단계:** 실제 CUAP 발행으로 크로스 링크 동작 확인 + 페이지뷰/광고 노출 모니터링

---

## Phase 28: CUAP Worker 404→500 Fix (2026-07-21)

**목표:** CUAP Worker 블로그 6개(health, pet, kitchen, beauty, camping, baby)에서 missing-asset 접근 시 HTTP 500을 반환하는 버그를 수정하여, 정상 404 페이지(`not_found_handling = "404-page"`)가 반환되도록 함.

**근본원인:**
- `kitchen-hugo/src/index.js`(268-byte, md5 `d25a7783bfe509f593ff6e01f3054eab`)의 `catch` 블록이 missing asset을 무조건 `new Response('Error', { status: 500 })`로 변환.
- 나머지 5개(health/pet/beauty/camping/baby)는 142-byte 공유본(md5 `3fece1c5b4b2fd725e8166968e7627df`, try/catch 없음)으로 정상 추정.

**구현 내용:**
- 6개 전체를 canonical worker로 통일(`ASSETS.fetch` 직접 반환 + `catch → 404`, never 500).
- `md5` 일치 확인: 6개 전부 `5667ff889e7f951b5c4f98a94293a6b2` (kitchen의 buggy `d25a...eab` 소멸).
- `deploy_site()`로 6개 Worker 블로그 순차 재배포 (CLOUDFLARE_API_TOKEN 제거 + OAuth profile `hugh79757`). 6/6 `True` 반환.

**검증:**
- 6/6 missing path → **404** (아님 500).
- 6/6 real published post → **200** (regression guard 통과). pet 초기 typo slug로 404 나왔으나 built slug 재검증 200 (테스트 데이터 오류, worker 회귀 아님).
- Cloudflare URL-encoding 307 redirect는 `-L` follow 시 200 정상 종착.

**다음 단계:** 없음. Phase 27(카드 404) + Phase 28(worker 500)로 CUAP 404 계열 버그 클로즈.

---

## Phase 49: CUAP Cross-link Bugfix (2026-07-26, 재검증 2026-08-01)

**목표:** 크로스링크 slug 불일치(404) 근본 수정 + 기존 bake된 잘못된 링크 전수 수정

**근본원인:** `publisher.py`가 `hugo_writer._write_hugo_post()`로 override되며
`_write_hugo_post()`가 `"url"` 키를 반환하지 않아 `pipeline.py:1064`의 `result.get("url")`이
항상 None → `_make_slug(keyword)`의 `20260726-{keyword}` 형식 date-prefixed slug가
fallback으로 사용 → 모든 크로스링크 404.

**Wave 1 (커밋 `4b33b43fd`)** — 근본 수정:
- `hugo_writer.py`: `_write_hugo_post()` return에 `"url"` 키 추가 (`"file"` 보존, additive)
- `pipeline.py`: slug 추출 3-tier fallback (`result["url"]` > `result["file"]` > keyword)
- `cuap_entity_linker.py`: `build_cross_sell_card()` 희소 엔티티 경고 로깅

**Wave 2 (커밋 `1b249d615`)** — 배치 수정:
- `fix_cuap_entity_slugs.py`: date-prefixed 잘못된 slug 엔티티 14건 삭제 (9개 블로그)
- `fix_baked_crosslink_cards.py`: bake된 크로스링크 href 143건 수정 (38개 파일/10개 블로그)

**49-B (커밋 `045ff37d1`)** — 전수 검증 + 잔여 404 수정:
- `scan_all_crosslinks.py`: 3,076개 포스트 / 9,840개 크로스링크 전수 스캔
- `fix_remaining_crosslinks.py`: 잔여 404 85건 수정 (일반 70 + trailing-slash 15)
- 최종 정상률 **9,840/9,840 (0건 404)**, Hugo 빌드 10/10 블로그 0 에러

**2026-08-01 추가 정리:** `published=0` phantom 엔티티 10건(잘못된 date-prefixed slug,
on-disk 불일치) 삭제 — 백업 `/tmp/cuap_stale_rows_backup_20260801-191632.json`.
`cuap_entities` 474→464행, 잘못된 slug 0건.

**검증:** health 콜레스테롤 포스트 4개 크로스링크 on-disk 일치 (fitness/kitchen/baby/beauty).
플랜 산출물: `49-01-SUMMARY.md`, `49-02-SUMMARY.md` (`.planning/phases/49-crosslink-bugfix/`).

---

## Phase 50: CTA Button Center (2026-07-26)

**목표:** 10개 CUAP 블로그 CTA 버튼 중앙 정렬 + cross-sell/funnel/cta-box CSS 클래스 표준화 + 인라인 스타일 마이그레이션

**구현 내용:**
- 10개 CUAP custom.css: btn-price-check 중앙 정렬(display:table + margin:auto) + cross-sell-card/funnel-header/cta-box 클래스 추가 (다크모드 포함)
- cuap_entity_linker.py: build_cross_sell_card() 모든 인라인 스타일 → CSS 클래스, build_funnel_header() color 외 전부 CSS 클래스
- pipeline.py: CTA fallback 인라인 스타일 → .cta-box CSS 클래스 + fix_markdown_cta_links() post-processing 함수
- scripts/fix_cta_links.py: 기존 포스트 markdown CTA 링크 → HTML 버튼 일괄 변환 스크립트 (dry-run, --blog, .bak, SHA256)

**검증:**
- T1 10/10 custom.css: cross-sell-card/funnel-header/cta-box ✅, btn-price-check centered ✅
- T2 AST OK — cuap_entity_linker.py 0 errors ✅
- T3 AST OK — pipeline.py CTA fallback inline-free ✅, fix_markdown_cta_links() ✅
- T4 AST OK — fix_cta_links.py dry-run 검증 (392 files, URL params 보존) ✅
- T5 10/10 Hugo build 0 errors ✅, 10/10 deploy ✅, live URL 200 ✅

---

## Phase 52: Blowfish 블로그 표준화 + 테마 업그레이드 대응 (2026-07-28)

**목표:** 36개 Blowfish 블로그를 techpawz-hugo 표준(v1.1)으로 통일하고, Hugo 테마 업그레이드에 대응 가능한 구조로 전환

**Wave 1 완료:** extend-head.html 단순화 (35개 블로그 수정 완료)
**Wave 2 완료:** extend_head.html 신규 생성 (26개 블로그)
**Wave 3 완료:** (이전 완료)
**Wave 4 완료:** single.html 정비 (22개 블로그)
- 4-1: Description lead 제거 — 11개 블로그 (CUAP 9 + kuta-hugo + biz-techpawz-hugo)
  - pet-hugo는 이미 제거되어 스킵
- 4-2: H2 분할 인젝션 추가 — 11개 블로그 (STAP 5 + TAP 5 + issue-techpawz-hugo)
  - finance-hugo: header in-article 제거 + H2 split 추가
  - dividend/etf/sector/ipo-hugo: header in-article 제거 + H2 split 추가
  - travel/travel1-4-hugo: H2 split 추가 (header in-article 유지)
  - issue-techpawz-hugo: content-div in-article 제거 + H2 split 추가

**다음 단계:** Wave 5

---

*Last updated: 2026-08-01 Phase 49 Cross-link Bugfix 재검증 완료 (SUMMARY + STATE 정리, phantom 10건 정리)*
