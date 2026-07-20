---
gsd_state_version: 2.0
milestone: v1.1
milestone_name: milestone
status: active
last_updated: "2026-07-20T22:40:00.000Z"
progress:
  total_phases: 25
  completed_phases: 25
  percent: 100
---

# Project State: 5000

**Status:** v1.1 — **Phase 25 완료 (CUAP 거미줄 엔티티 시스템), 운영 안정화 단계**
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

---

## Quick Tasks Completed

| Date | Task | Commit |
|------|------|--------|
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

*Last updated: 2026-07-20 Phase 25 CUAP 거미줄 엔티티 시스템 완료*
