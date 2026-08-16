---
gsd_state_version: 2.0
milestone: v1.1
milestone_name: milestone
status: active
last_updated: "2026-08-15T00:00:00Z"
progress:
  # 코드·아티팩트 기준 실제 상태. "완료"는 커밋/PLAN+VERIFICATION/구현 코드가 존재하는 것.
  # 진행 중/미시작 포함 총 관리 대상 Phase 수(문서상 개별 추적 행 기준).
  total_phases: 32
  completed_phases: 29
  in_progress_phases: 1
  planned_phases: 3
  percent: 91
---

# Project State: 5000

**Status:** v1.1 — **Phase 71 진행 중 (Wave 1·2·3 완료, Wave 4·5 스켈레톤+승인게이트 구현 완료, OQ#1/OQ#2 시니어 결정 대기).** Phase 73 실행 완료 (SC-1/2/3/4/5/7/8 적용; SC-7 investigate-only 이월). Phase 68 완료 (TAP 블로거 본문 레이아웃 보완 + images:// URL 검증). Phase 67 완료 (G3 해소 + Wave 1·2 라이브 청소). Phase 52 Wave 5 진행 중. 미시작: Phase 45·53·54·55.
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
| 52 | Blowfish 블로그 표준화 + 테마 업그레이드 대응 | 🔄 | Wave 5 진행 중 (Wave 1~4 완료, 2026-07-28) |
| 58 | 발행 문제 인벤토리 + 정밀 Telegram 알림 시스템 (PublishMonitor) | ✅ | 8 커밋 (`0e17f9acc`~`3e5aa1cd5`, 2026-08-06) |
| 59 | Ops Dashboard + Blowfish 표준 단일화 + 파이프라인 통합 | ✅ | 10 커밋 (59-02~59-11, 2026-08-06) |
| 61 | Pipeline Standardization & Branch Renewal | ✅ | 9 plans/6 waves 실행 (2026-08-07) |
| 62 | Content Leak Prevention — C01~C08 Rule System | ✅ | 5 plans/5 waves 실행 완료 (2026-08-07): standard_rules INSERT, leak_tracker 훅, preflight 게이트, 대시보드 체크 |
| 63 | Content Integrity Refinement — C07/C09 검증 + 저혈압 글 판정 | ✅ | 1 plan/1 wave 실행 완료 (2026-08-07): C09 check_c09_frontmatter() 추가, 62-01 재검증 (C04 16/16, C07 95/95, C09 27/27, 오탐 0), health 저혈압 글 배포누락 판정 |
| 64 | 규칙 체계 자기진화 + 운영헌장 | ✅ | 설계·문서 완료 (2026-08-07): C05→P 이동, 네임스페이스 분리(RULE-/ISSUE-), S01/S04 severity 확정, 관찰기간 7일+긴급예외, 오탐미탐 자동기록/승격 사람승인, Task 6 프리플라이트 체크리스트 5종 설계, OPERATIONS-CHARTER 갱신 |
| 66 | P09 시나리오 A/B 판별 (조사 전용) | ✅ | 조사 완료 (2026-08-07). A 반증: health-hugo·pet-hugo 이미지 URL 4,776개 전수 스캔 결과 P09 패턴(세그먼트 50% 이상 중복) 0건. B 확정 불가: P09 알림 로그 0건이나, 로그 부재가 "알림 미발생"인지 "로그 유실"인지 구분 불가 → B 성립 여부는 확인 불가. 감지 slug 특정 불가(로그 0건). deploy.log range 오류(178건/70 slug, 전부 pet-hugo tags repr)와 P09는 별개 확정(교차 0건). 66-RESEARCH.md "B 성립" 결론은 지나치게 강함 — A만 반증되고 B는 미확정이 정확. 코드 수정·INSERT·배포 일체 없음. |
| 67 | fix-g3-first — 오토트리아지 무인화 + 라이브 청소 | ✅ | 실행 완료 (2026-08-08). 커밋 `4d78d3f3f`. launchd 등록 2건(ops-dashboard + auto-triage), auto_triage fail-loud 전환, watchdog 3자 감시, dead_links 43건 제거(Wave 1), 8개 블로그 빌드·배포(Wave 2). STATE.md Phase 67 섹션에 상세. |
| 68 | PPM-5 images:// URL 정규식 검증 추가 | ✅ | 실행 완료 (2026-08-09). 커밋 `ceb65a170`. shared/app_images/core.py 신규 생성: IMAGES_URL_PATTERN(^images://), _build_images_asset_path() 정규식 검증, _validate_images_url(), normalize_hugo_asset_url(). baby-hugo 등 HUGO_BASEURL 없는 환경에서 images:// 생성 시 FrontMatter 삭제 방지 안전 가드. |
| 45 | TAP Blog Meta-Response Detection & Prevention | 📋 Planned | 미시작. ROADMAP Phase 45 참조. TAP 블로거 AI 메타 응답 발행 방지. core/validators.py + core/ai_writer.py + app.py. Phase 44 이후 권장. |
| 53 | Complete Phase 52 Wave 6: Build and Deploy | 📋 Planned | 미시작. Phase 52 Wave 5 완료 후 실행. 36개 블로그 Hugo 빌드 + wrangler 배포 + 라이브 검증. ROADMAP Phase 53 참조. |
| 54 | Curation Title Generation Hardening (제목 fallback 제거) | 📋 Planned | 미시작. `.planning/phase-54-title-hardening/PLAN.md` 존재. writer.py:538-539 하드코딩 fallback 제거 + H1 형식 강제 + CoT/프롬프트 누출 차단. "추천 TOP5 (연도년)" 패턴 134건 재발 중 — 시급. |
| 55 | Curation Content Quality Diagnostics | 📋 Planned | 미시작. `.planning/phase-55-curation-quality-diagnostics/CONTEXT.md` 존재. 경험 허위 주장·소 스불명 수치·건강 효능 단정 측정(read-only). Phase 54 이후. |

**참고 — 문서상 미정리 잔여:**
- Phase 44 (전수조사 및 전체 수정): 44-01~03 완료, 44-04~05(프롬프트 보완 + 마무리) 미완료. ROADMAP Phase 44 참조.
- Old `phase*`(1~17 등) 디렉터리: 완료 판정 파일(PLAN/VERIFICATION/COMPLETION) 없음. 과거 유령 디렉터리로 추정 — 정리 후보.
- `.planning/phases/61-pipeline-standardization-branch-renewal/`: PLAN.md만 존재(VERIFICATION.md 없음). STATE.md에는 웨이브 요약 포함 실행 기록으로 기술. VERIFICATION 작성 또는 상태 확정 필요.
- `.planning/phase-54-title-hardening/`, `.planning/phase-55-curation-quality-diagnostics/`: PLAN/CONTEXT만 존재, 실행 아님.

---

## Quick Tasks Completed

| Date | Task | Commit |
|------|------|--------|
| 2026-08-10 | ETAP 발행 회귀 수정 — `_write_hugo_post_etap()`에서 tags list→str 정규화 (AttributeError: 'list' object has no attribute 'split' 해소, luxury/escape/extreme/nightlife/ghost/layover 등 6+블로그) | `본 커밋` |
| 2026-08-06 | Phase 59-01 — Replace per-pipeline _write_hugo_post() in 34 ETAP pipelines with shared import | `b420e69cc`, `4ff78c0e5`, `d0fd9d2a8`, `a64544294`, `21f445b79` |
| 2026-08-06 | Phase 59-07 — hotissue-hugo PaperMod to Blowfish migration (theme field, layouts, hugo.toml, SingleAuthor fix) | `d6ce85165`, `f8c186ed6`, `b3fcdb1`, `e55626b` |
| 2026-08-06 | Phase 59 Execution — Ops Dashboard (Flask UI+JSON API+templates), Blowfish 단일화 (PaperMod/Congo→Blowfish), ETAP _write_hugo_post 35중복 제거, flights-hugo naming fix | 10 커밋 |
| 2026-08-06 | Phase 59 Planning — Ops Dashboard + Blowfish 단일화 + 파이프라인 통합 CONTEXT/RESEARCH/PLAN 작성 | `planned` |
| 2026-08-05 | 전 블로그 KEYWORD_MAP 전수 감사 — low_relevance 위험 키워드 589 고유쌍 → 212 (제거 377쌍: 외국어혼합 256 + 오프토픽 82 + B1검토 39, 유지 KEEP_B1 84 + KEEP_C 126, SKIP_ARTIFACT 2) | `a8ed1ec30`, `bd98db2ef` |
| 2026-08-05 | camping-hugo 일반명 키워드(조명/난로/선풍기) 제거 + 스케줄러 재시작(PID 12380→31420, camping 발행 성공) | `ca9f9e7ad` |
| 2026-08-05 | golf-hugo/bike-hugo no_keyword 발행 실패 해소 — golf/bike 키워드 24개 수동 수집(products ≥3건) + 스케줄러 재시작(PID 54024→12380, auto_collector 2985개 로드) + scheduler.py catchup/register 시각 파싱 방어 가드 (tap-blogger YAML sexagesimal 600/840 크래시 차단) | `2871c889c`, `64a9874a9` |
| 2026-08-05 | cuap 15개 블로그중 오늘 만든 5개 블로그가 클라우드 플레어 설정이 완료가 안됐다. 배포까지 완료해줘. (massage/car/homeappliance/golf/bike-hugo custom domain 바인딩 + 배포, WORKERS_BLOGS 추가) | `633678a40` + CUAP `9712f78`, `59f3647` |
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

## Phase 58: 발행 문제 인벤토리 + 정밀 Telegram 알림 시스템 (2026-08-06)

**목표:** 24개 발행 문제를 `PROBLEM_REGISTRY`에 전부 등록하고, 발행 시 문제 발생 시 문제별
한국어 Telegram 알림(problem_id, 문제명, 감지 단계, 패턴, 연속 횟수, 조치)을 신규
`PublishMonitor` 단일 진입점으로 보내는 시스템 구축 (additive, non-destructive)

**구현 내용 (8 커밋, 5 wave):**
- `shared/problem_registry.py` — ProblemSpec + Detection + PROBLEM_REGISTRY 24건 + unknown_failure,
  lookup_reason/lookup_problem. reason 인벤토리 34건 전수 매핑 (CRITICAL 6 / MAJOR 12 / MINOR 6)
- `shared/problem_detectors.py` — 순수 탐지 5함수 (P07 CJK / P08 CoT / P09 URL 반복 / P23 길이 / P15·P19 검증)
  + post_generate 디스패처. 기존 validators/ai_response_parser 시그니처 재사용, 신규 regex 없음
- `shared/problem_monitor.py` — PublishMonitor + get_monitor 싱글턴. 실 ThresholdChecker API 사용
  (쿨다운 `_in_cooldown`/`_mark_alerted`, MAJOR `check_consecutive_failures`), `PROBLEM_ALERT_DRY_RUN` env,
  phase=spec.hook 강제, 신규 cooldown 코드 0건
- `dispatcher.py` — 실패 분기 reason→problem 매핑, `_build_and_deploy_central` 반환 캡처(False→P04 post_deploy),
  `failure_count.json` `{blog_id}:{problem_id}` 확장 키 + 성공 시 확장 키 삭제. 기존 `_tg_error` 호출 수 불변
- `pipelines/curation/*` + `shared/publisher.py` — run() 실패 블록 monitor 병렬 호출(phase=spec.hook),
  post-generate raw 훅(sanitize 이전), P22 `ai_generate` RuntimeError 캐치(re-raise 유지), P15/P24 분기,
  P06 featureimage 1회 HTTP 확인(post_publish)
- 테스트 4파일 (registry 13 / detectors 36 / monitor 10 / integration 8 = 67 신규)

**검증:**
- baseline 228/22/1 → 최종 295/22/1 (295 = 228 기존 + 67 신규), **신규 실패 0건** (실패 22건은 사전 존재,
  baseline과 byte-identical)
- dry-run 실발송 0건 (T7 patch assert 1차 근거 + dry-run/normal 결과 동일)
- additivity 게이트: `_tg_error(deploy)`=1, `_tg_error(quota)`=0, curation `_tg_error`=4, publisher `_tg_err(validation)`=1
  — 전부 수정 전과 동일. 신규 cooldown 코드 0건
- 커밋 8건 태스크 단위 원자적 분리 (커밋 계획과 정확히 일치)

**잔존 위험 (Phase 59+ 이연):**
- P05(Hugo build) vs P04(wrangler) 구분 미배선 — `_build_and_deploy_central` bool 반환 계약 변경 필요
- `detect_post_generate`가 본문 전체를 P23 검사에 전달 → 500자 초과 본문마다 P23(quiet, 발송 없음) 보고 잡음
- dry-run(24h) 실운영 관찰 후 실발송 전환 검토 (launchd `PROBLEM_ALERT_DRY_RUN=1`)
- `validators.py:744-758` `body_md` NameError — 스코프 밖, 별도 phase

---

## Phase 67: fix-g3-first — 오토트리아지 무인화 + 라이브 청소 (2026-08-08)

**Status:** ✅ Executed (G3 완전 통과 + Wave 1·2 완료)
**백업 태그:** `pre-g3-fix-2026-08-08` @ `e2137bb60233` (push 금지)
**커밋:** `4d78d3f3f` feat(auto_triage): fail-loud 서버장애 사람호출 + commercial 키워드 우선 + watchdog 3자감시

**실행 내용:**
- E4-a: `com.5000.ops-dashboard.plist` launchd 등록 (KeepAlive=true, 포트 5060, `python -m ops_dashboard.app`), kill→자동재기동 테스트 통과
- E4-b: auto_triage fail-loud 전환 — 서버 장애 시 `data_fetch_failure` 사람 호출 (silent_skip 방지)
- E4-c: 겸용 키워드 commercial 우선 — YAML 순서 + 코드 순서 모두 commercial 먼저, 12/12 테스트 통과, 오삼킴 0건
- E4-d: analytics_watchdog.sh 3자 감시 확장 — 스케줄러 + ops_dashboard + auto_triage
- E4-e: `com.5000.auto-triage.plist` launchd 등록 (매일 03:00, DRY_RUN=0, PYTHONPATH), 실모드 1회 실행 통과
- Wave 1: dead_links.json 53건 HTTP 체크 → 404 9건 식별, 소스 파일 34개 dead 링크 43건 제거, 잔존 0건
- Wave 2: 8개 블로그(appliance/baby/beauty/camping/fitness/health/interior/laptop-hugo) Hugo 빌드 0 errors + wrangler deploy 8/8 True

**launchd 등록 (repo 밖, git 대상 아님):**
- `~/Library/LaunchAgents/com.5000.ops-dashboard.plist` — 포트 5060, KeepAlive, 현재 PID 13818
- `~/Library/LaunchAgents/com.5000.auto-triage.plist` — 매일 03:00, PROBLEM_ALERT_DRY_RUN=0

**라이브 청소 참고 (git 대상 아님):**
- CUAP 콘텐츠 파일 34개 수정됨 (`/Users/twinssn/Projects/cuap/*-hugo/content/posts/.../index.md`)
- 백업: `/tmp/cuap_dead_link_fix_backups/` (45개 파일 백업)
- draft: true 6개 포스트는 라이브 미노출 → 배포 대상에서 제외 (랜턴/발육차트 등)
- published 47개 포스트 중 5개 표본 라이브 dead 링크 제거 확인

**검증:**
- E4-a~e 전부 통과
- Wave 1 dead 링크 잔존 0건
- Wave 2 published 포스트 표본 5개 dead 링크 없음 확인

**한 줄 결론:** "G3 해소 — 대시보드 자동재기동 [O], 트리아지 fail-loud [O], 겸용키워드 오삼킴 [0], watchdog 3자감시 [O], 오토트리아지 실모드 [등록]. Wave 1·2 라이브 청소 완료."

---

*Last updated: 2026-08-08 - Phase 67 완료 (G3 해소 + Wave 1·2 라이브 청소). 백업 태그 pre-g3-fix-2026-08-08. push 금지.*

---

## Phase 61: Pipeline Standardization & Branch Renewal (2026-08-07)

**Status:** ✅ Executed (9 plans / 6 waves 완료)
**Context:** `.planning/phases/61-pipeline-standardization-branch-renewal/61-CONTEXT.md`
**목표:** 85개 블로그 7개 파이프라인 분기(car/curation/etap/rap/senior/travel/stock)를 동일 표준 골격으로 재편하는 리뉴얼

**확정 범위 (사용자 5개 목표 전부 선택):**
1. 파이프라인 코드 구조 통일 (pipeline/fetcher/topic_manager/writer/enrich/validator 골격)
2. config 스키마 통일 (blogs.d/*.yaml 표준 스키마 + config_validator 검증)
3. 실행 방식 통일 (STAP/TAP subprocess 러너 → shared/subprocess_runner.py)
4. 외부 프로젝트(TAP/STAP) 표준 계약 정합 (물리적 병합 아님)
5. 새 분기 생성 도구 (scripts/scaffold_branch.py)

**번호 재지정:** phase.add가 Phase 60을 부여했으나 기존 비공식 `phase-60-publish-investigation-and-hardening`과 충돌 → Phase 61로 재지정 (디렉터리 mv + ROADMAP 수정)

**선행 정리 (사용자 승인, 파괴적 작업):**
- `5000/CUAP/health-hugo` 죽은 복사본 제거 (274 files, grep 0건, inode 분리 확인) — 커밋 `55ea89f06`, 백업 `/Users/twinssn/Projects/_5000_backups/CUAP-health-hugo_20260807-162010.tar.gz`, worklog `WL-20260807-health-hugo-dead-copy-removal.md`
- 커밋 전 작업트리 보존: curation pipeline.py draft-skip fix (404 예방) `39f005084`
- 교차검토 `61-REVIEWS.md` (opencode subagent; claude CLI OAuth 만료로 대체) — 전체 파일 대상 경로 진본 확인, ETAP 35쌍 진본 inode 확인

**Wave 실행 결과 (전 Wave 성공):**
| Wave | Plan | 내용 |
|------|------|------|
| 1 | 61-01 | `docs/PIPELINE-STANDARD.md` — 표준 7-section (run(cfg) 계약, 6-모듈 골격, config 스키마, reason 어휘, DB 규칙) |
| 2 | 61-02 | `shared/db.py`, `shared/subprocess_runner.py`, config_validator 확장, problem_registry reason-key 10개 추가 (language_error=P12 기등록 제외, travel DB 미배선) |
| 3 | 61-03 | senior/rap 표준 골격 (pass-through wrapper 6개) + DB 중앙화 |
| 4 | 61-04/05/06 | car/travel/curation 표준 골격 + DB 중앙화 + travel run() None→no_result 정규화 |
| 5 | 61-07 | ETAP 35쌍 run(cfg)→dict 어댑터 (24×run()/10×run(cfg=None)/1×run(cfg)=flight 정규화), dispatcher 브리지 보존, 10개 pipeline 사전 SyntaxError 수정 |
| 6 | 61-08/09 | dispatcher STAP/TAP→run_subprocess 위임(~124줄 중복 제거), `scaffold_branch.py` + .bak/dead-code 보고(삭제 지연) |

**테스트:** 21 failed / 392 passed / 1 skipped (317→392, +75 신규 테스트). 실패 21건은 **사전 baseline** (relevance_scorer/ai_writer/post_validator/curation 키워드·title_hardening·cot·alert·filters) — Phase 61 도입 실패 0건.

**검증:** 9개 SUMMARY (61-01~61-09) 작성. dispatcher 브리지 `git diff` 공백, ETAP 35개 import/AST OK, `data/*.db` tracked 무변경, AdSense ID 불변, 신규 패키지 0.

**잔존 위험 / 후속 작업:**
- **사전 존재 21건 테스트 실패** — Phase 61과 무관. 별도 정리 필요 (relevance_scorer 기대값 불일치 등).
- 61-08: `run_subprocess`가 `project_root/.env`만 로드 (기존 STAP은 STAP_ROOT/.env + PROJECT_DIR/.env 둘 다 로드) — STAP 발행이 5000 env 값 의존 시 차이 가능. 라이브 STAP/TAP 발행은 mock 검증만 (운영 스케줄러 관찰 필요).
- `.bak` 59건 실제 삭제는 별도 승인 후 (파괴적 작업 규칙).
- `get_db_path`가 etap 미커버 (전용 DB 단일 확인 불가) — 61-07에서 이연.
- 신규 scaffold 분기는 import-verifiable, end-to-end 발행은 미검증 (placeholder).

**다음 단계:** 21건 사전 실패 정리 (선택), 운영 스케줄러로 61-08 STAP/TAP 라이브 발행 관찰

---

## Phase 62: Content Leak Prevention — C01~C08 Rule System (2026-08-07)

**Status:** ✅ Executed (5 plans / 5 waves 완료)
**Context:** `.planning/phases/PHASE-62-content-leak-prevention/CONTEXT.md`
**목표:** 콘텐츠 무결성 규칙 C01~C08을 자동 탐지·차단하는 체계 구축

**실행 결과 (전 Wave 성공):**

| Wave | Plan | 내용 |
|------|------|------|
| 2 | 62-02 | C01~C08 standard_rules INSERT (ops_dashboard/db.py) |
| 3 | 62-03 | shared/leak_tracker.py + hugo_writer.py 3개 지점 훅 |
| 4 | 62-04 | dispatcher preflight_check + _build_and_deploy_central 게이트 |
| 5 | 62-05 | ops_dashboard/checks/content_integrity.py + check_results 통합 |

**구현된 구성 요소:**

| 구성 요소 | 파일 | 설명 |
|-----------|------|------|
| 규칙 정의 | ops_dashboard/db.py | SEED_STANDARD_RULES에 C01~C08 추가 (총 20개 규칙) |
| 원인추적 모듈 | shared/leak_tracker.py | C01/C04 검사 + logs/leak-origin.log 기록 |
| 파이프라인 훅 | shared/publishers/hugo_writer.py | (a)생성직후 (b)humanizer후 (c)저장직전 + ETAP |
| 배포 게이트 | dispatcher.py | preflight_check(blog_id) + _build_and_deploy_central 게이트 |
| 대시보드 체크 | ops_dashboard/checks/content_integrity.py | C01~C08 8개 체크, check_results 기록 |

**검증 결과:**

- [x] C01~C08 규칙 definition이 CONTEXT.md와 일치하게 standard_rules에 INSERT됨 (C02/C04/C08 CRITICAL)
- [x] 원인추적 훅 3개 지점이 설계대로 구현됨 (logs/leak-origin.log)
- [x] preflight_check가 dispatcher._build_and_deploy_central 직전에 삽입됨
- [x] 체크리스트 8개 등록, check_results 8건 기록
- [x] CUAP/CAP/STAP/RAP/ETAP/TAP preflight_check 통과 확인
- [x] 기존 R01~R12와 rule_id 충돌 없음

**잔존 위험 / 후속 작업:**

- C08(live-file 불일치)은 라이브 비교 API 연동 시 별도 구현 필요 (현재 placeholder)
- preflight_check C04 패턴과 leak_tracker C04 패턴이 별도 유지 — 향후 리팩터링 검토
- 대시보드 UI에서 C0 체크 결과를 시각적으로 표시는 별도 작업

**다음 단계:** Phase 52 Blowfish 표준화 Wave 5-6 계속 진행

---

## Phase 68: PPM-5 images:// URL 정규식 검증 추가 (2026-08-09)

**Status:** ✅ Executed (1 plan / 1 wave 완료)
**커밋:** `ceb65a170` feat(app_images): add images:// URL generation with regex validation (PPM-5)

**실행 내용:**
- `shared/app_images/core.py` 신규 생성
  - `IMAGES_URL_PATTERN = re.compile(r"^images://")` 상수 정의
  - `_validate_images_url(url)` — images:// URL 유효성 검증 함수
  - `_build_images_asset_path(path, use_images_scheme=True)` — images:// 생성 시 정규식 검증 적용
  - `normalize_hugo_asset_url(url, base_url)` — images:// → 절대 URL 변환, base_url 없으면 None 반환 (FrontMatter 삭제 방지 가드)
- baby-hugo 등 HUGO_BASEURL/ASSET_DOMAIN 없는 환경에서 images:// 생성 시 의도 명확화
- PPM-6(기본 스킴 변경)은 추후 단계로 이월

**검증:**
- [x] IMAGES_URL_PATTERN 패턴: `^images://`
- [x] _build_images_asset_path에서 _validate_images_url 호출 확인
- [x] 무효한 URL(https:// 등) 검증 실패 → False 반환 확인
- [x] 기존 테스트 393 passed (실패 22건은 사전 baseline, Phase 68과 무관)

**잔존 위험 / 후속 작업:**
- PPM-6: 기본 스킴을 https://로 변경하는 작업은 별도 phase로 이관
- 실제 파이프라인에서 _build_images_asset_path 사용 여부는 호출 측에서 결정

**한 줄 결론:** "PPM-5 완료 — images:// URL 생성 시 IMAGES_URL_PATTERN(^images://) 정규식 검증 추가, 무효 URL 생성 거부, base_url 없을 때 None 반환으로 FrontMatter 삭제 방지."

---

## Phase 73: Other-Branch Unattended Application (2026-08-16)

**Status:** ◆ Executed (7/8 SC 적용; SC-7 investigate-only 이월) — 커밋 완료, push 안 함, wrangler deploy 안 함. SC-4는 후속 슬롯값 제공받아 적용 완료.

**실행 파형:** Wave1(SC-1·2) → Wave2(SC-3·5·7) → Wave3(SC-8) → Wave4(검증 스윕). SC-4(CAP ad config)는 slot 값 미확정으로 사용자가 skip 결정.

**커밋:**
- `f7e41ca37` SC-2: G3 refuted 문서화 + TAP N/A 분류 (subprocess_runner.py:99 주석 + SC2-classification.md)
- `de207f90f` SC-3: FM-THUMBNAIL 스캔+정화 (frontmatter.py + autofix + test 4passed)
- `d103016e0` SC-7: RAP C03 leak 감사 + rap_leak detect-only check (CHECK 등록)
- `b547c596d` SC-8: AGENTS.md Workers(11) 정정 + deploy_type 키 80건 (AGENTS.md는 사전 condensation 포함 커밋 주의)
- `8d9190358` (5000) + `781ddf9016` (STAP): SC-1 STAP P04 reroute + SC-3 dispatcher 등록 + SC-8 deploy_type dispatch
- `9602c8534` (5000 rap.yaml) + RAP submodule 5건 (rap-hugo 1e6fff28, rap2 0f4faec3, rap3 a37208fa, rap4 4f628d1a, rap5 e715a855): SC-5 topSlot=3403350155(5건) + force_draft 사이클 제거
- SC-4 (CAP ad config) — 슬롯값 사용자 제공 후 적용: cap 8블로그 13 config 파일(dual-config는 toml+yaml 병기). 커밋: hotissue 5079fdd, tco 61d5cb7, ev d3ad88e, compare 00f2450, deal 00ac319, guide 6128f82, rank 97564a4, pick 87c4101 (각 블로그 nested git repo별 커밋). Publisher-ID 8772(rotcha 6) / 6677(info rank·pick) 매핑 일치.

**검증 (측정):**
- SC-1: `STAP_PIPELINE_BLOGS` 정의(:95)+조건편입(:1331); 실패경로 `deploy_error`→P04 분기(:1385) 존재. STAP publisher.py:295/313 raise→return string. pytest 사전 baseline 27실패 동일(무회귀).
- SC-2: `os.environ.pop('CLOUDFLARE_API_TOKEN'`(:99) 존재; STAP publisher.py:297 env= 없음; TAP app.py:602-720 hugo/wrangler 0건.
- SC-3: `FM-THUMBNAIL` dispatcher 등록(:972,:984); thumbnail 스캔/정화 코드 존재; pytest 4passed.
- SC-5: `force_draft` rap.yaml 0건; 5 RAP hugo.toml에 3403350155(×3 슬롯) 확인; 2195212287 0건; 6677(Publisher-ID) 미변경.
- SC-7: `rap_leak in CHECKS: True`; 유출 샘플 1건(하남시 미사강변) + 근본원인(_parse_article 2nd-block, publisher.py:585 verbatim write) 식별.
- SC-8: `deploy_type` blogs.d 80건; `WORKERS_BLOGS` 11개(:571); AGENTS.md 11 Workers 명시 + 토큰 strip 정정.

**잔존 위험 / 이월:**
- SC-4(CAP ad config) 적용 완료 → blank-ad 갭 해소 (라이브 배포는 별도 dispatcher 배포 필요).
- SC-7 RAP C03 유출 본문 재조합 근본수정 이월(위험등급, 사람 승인 별도 phase).
- STAP_PIPELINE_BLOGS=set(.values())는 pipeline명 보유 → :1331 조건은 STAP blog-id에 no-op, 실제 P04는 실패경로 분기(:1385)가 담당. STAP 실제 deploy는 기존 publisher.py 경유(중앙 deploy 미이전) — plan shape A 준수.
- `pytest` 27실패는 사전 baseline(test_alert_wiring.py 누락 schedule 모듈), Phase 73 무관.
- AGENTS.md 커밋(b547c596d)에 사전 working-tree condensation(1246행 삭제)가 함께 반영됨 — §1 Publisher-ID 매핑은 global `/Users/twinssn/.config/opencode/AGENTS.md`에 위치(본 repo 파일엔 본래 없음), SC-8 영향 없음.

*Last updated: 2026-08-16 - Phase 73 실행 완료 (SC-1/2/3/5/7/8 적용, SC-4 skip, SC-7 이월).*
