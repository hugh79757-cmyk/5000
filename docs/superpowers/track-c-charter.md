---
title: "Track C Charter — Cross-Branch Investigation & Synthesis"
doc_type: CHARTER
status: APPROVED
created: 2026-08-21
branch: track-c-etap-quality-overhaul
part_of: "Roadmap M5 — Cross-Branch Content-Change Discovery"
---

# Track C Charter

## 0. Premise Shift (2026-08-21 — 비용 전제 변경)

- 3개월 침묵은 장애가 아니라 색인 부재에서 유료 API 비용을 태우지 않으려는 의도된 정지였다.
- 현재 무료 LLM 폴백 체인(16 free tiers → DeepSeek V4 유료 최후수단, 최근 511건 중 97.4% gemini-3.5-flash-lite 1티어 성공, `data/llm_trace/*.jsonl`)으로 발행 비용은 사실상 0.
- 따라서 제약 이동: **비용(량) → 색인·품질(통과율)** 병목. 고치는 것보다 다시 쓰는 게 싸다. 수작업 교정은 불가(5,381건), 재생성이 상한도 높다. 단 전량 재생성은 금지 — 색인·노출 없는 글은 재생성해도 노출 0이므로 선별이 핵심. 아래 P0→P1 재생성 전략과 색인 선행 원칙이 이 전제에서 도출된다.

## Purpose
Cross-branch evidence synthesis: ETAP branch 1 done → expand to car/curation/rap/senior/travel/stock.
Single source of truth for branch investigations, gates, and publish targets.

## Scope
- Branch 1 ETAP: 35→34 (airports-hugo paused be52387f8), 36 Hugo builds verified (ETAP outside 5000 .git, snapshot tar /tmp/etap_hyphen_backup_20260821.tgz). GA 12 sites gained fallback G-N4Q99745QT, disclosure+rel moved to rendering layer (Hugo partial+hook, rebuild = backfill, quality_guard disabled), 36/36 hugo build ok.
- Remaining branches: gap/car(5000), CUAP(curation), RAP, SEAP, TAP, STAP — reuse ETAP methodology (live sitemap+robots+3 posts sample, deploy token audit, GA/AdSense audit).

## Gates
- S0: quality_guard 0허위/LaTeX (DONE for ETAP)
- S1: michelin pilot 6 checks — **PASS (2026-08-22)**: build/GA single/AdSense single/wordCount 통과, disclosure·rel은 콘텐츠 기반 N/A (adventure-hugo에서 렌더 검증 완료). GA4 per-blog 전환(34/36 measurement_id 확보 + michelin 템플릿 전환) 완료.
- S2: 34-blog batch rebuild publish (dispatcher per-blog deploy) — **michelin 파일럿 구조 재설계 완료(요약/비교/FAQ)**, 배포 대기 중(사람 승인).
- S3: live verification (curl sitemap lastmod movement + head GA/AdSense single)

## 진행 상태 갱신 (2026-08-22)
- 스키마-as-code: 설계 → **구현 완료** (`schemas/` 8분기, `schema_loader.py`, `validate_schema_pr.py`, `c08_staging.py`). 상세: `specs/2026-08-22-schema-as-code-design.md` §9b.
- GSC gsc_pages: 36도메인 전부 siteOwner 등록 확인 → `collect_gsc()` 확장 → **563행 수집** (ETAP 계열 17개 도메인 색인/노출 데이터 확인).
- GA4: 공유 fallback G-N4Q99745QT → per-blog measurement_id 전환 (michelin 파일럿 PASS). 매핑: `config/ga4_measurement_map.yaml`.
- airports 42건: **데이터 소진으로 재생성 불가 확정** — paused 유지, S3 데이터 확보 후 재개.
- 병렬 실행 상세: `specs/2026-08-22-track-c-execution-report.md`.

## Publish Target
- 34 active ETAP blogs normal publish + 통A batch (S2). deals-hugo 106-day stall flagged for draft_detected/content pipeline diagnosis after S1.

## Links
- Roadmap: `.planning/ROADMAP.md` M5 (IN_PROGRESS — Track C charter linked here)
- Discovery: `docs/superpowers/specs/2026-08-20-track-c-branch-content-change-discovery.md`
- ETAP discovery: `docs/superpowers/specs/2026-08-20-etap-auto-branches-discovery.md` (34 정정)
- Spike: `docs/superpowers/specs/2026-08-20-etap-spike-full.md` + `2026-08-20-etap-spike-phaseA-interim.md`
- Destructive log: `logs/destructive_2026-08-21.log`

## Regeneration Strategy (수작업 금지 — 선별 재생성)

1. writer 고침(P0 원인 해소 후) → 2. 신규 발행 며칠 품질 확인 → 3. 기존 글 선별 덮어쓰기(동일 URL, frontmatter date/lastmod 유지 금지) → 4. 색인 미달은 재생성 대상에서 제외, 색인 경로 따로 처리.
- 우선순위: `GSC 노출/클릭 有 > 색인 有/실적 無 > 색인 無`. 실적 데이터 없으면 확보가 선행 과제.
- "전량 재생성" 금지 — 실행 불능.

## Indexing Precondition
- robots/sitemap은 검증 완료(allow:/, Cloudflare Managed, GSC pages 0행 — 수집 필요). GSC 34도메인 등록 여부·색인율·IndexNow 동작은 별도 규모 파악 단계(금일 보고용 스냅샷 산출, 해결은 후순위).

## Non-Goals
- No DB backfill for disclosure/rel (render layer covers it). No new branches during Track C.

## Update 2026-08-21 — Family Structure & Airport Data Decision

- **13 Families**: 36 blogs → 13 families (F1 Viator 10, F2 Viator 8, F3 Omio 4, F4 Viator+dest 4, F5 Visa 2, F6-13 singletons). Representative max posts e.g. tour-hugo 254, michelin 272. Map: `docs/superpowers/specs/2026-08-21-etap-family-map.md`.

- **Airports Layer Decision**: Layer1 OurAirports (CC0, public domain, daily) = Quick Facts & Overview (factual, assertive allowed). Layer2 OpenFlights (67,663 routes, 2014 snapshot) = Route Snapshot historical only, conditional display: `As of the 2014 OpenFlights snapshot, N airlines ... M destinations ... This snapshot predates recent network changes and is likely lower than current operations.` + footer `Airport data: OurAirports (public domain). Route data: © OpenFlights contributors, ODbL.` Zero → section omitted.

- **ODbL Interpretation (unconfirmed, external verification needed)**: Share-alike applies to derivative DB distribution, not to Produced Work (article). We do not distribute DB, so attribution only required. Documented as "미확정·외부 확인 필요".

- **Unresolved Decisions (3)**:
  1) D group 41 undercount (2→90, 5→206 etc) regeneration scope.
  2) Topic mixing 91/163 airports (and michelin page/28) handling.
  3) GA4 dedicated property per blog.

Status: DESIGN → family map DISCOVERY, airports PoC DESIGN, harness corpus PLAN.

## 결정 로그
- 2026-08-21: noindex 판정 기준을 표현(grep)에서 데이터(`airlines==0 or dests==0`)로 변경 → 15건→31건 (데이터가 사실, 표현은 허위)
- 2026-08-21: Layer1 OurAirports(CC0)=본문 골격(단정 허용) / Layer2 OpenFlights(ODbL 2014)=하단 부록(`As of the 2014 snapshot...`) 결정
- 2026-08-21: 수집 0이면 글 생성 자체를 스킵(`airports_writer.py:53 or`). 0을 사실로 쓰지 않는다
- 2026-08-21: "허위 < 밋밋함" — 사실 확인이 품질보다 선행, 품질은 Phase 2
- 2026-08-21: 공항 글의 가치는 "무엇이고 어디인가", 취항 수는 부가 정보
- 2026-08-21: 라이브 근거는 `curl -sL` 원본 바이트만, 마크다운 변환본 인용 금지

- 2026-08-21: 정직단어수 게이트 도입 — total이 아니라 재서술·보일러플레이트 제외 후 400 판정
- 2026-08-21: airports 발행 중단(자료 한계)
- 2026-08-21: 기준선은 미쉐린 라이브 하한으로 통일 → ROADMAP: docs/superpowers/ROADMAP-2026Q3.md
