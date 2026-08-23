---
title: "Track C Session State — 2026-08-22 (코드 중심 갱신)"
status: IN_PROGRESS
---

# Track C Session State — 2026-08-22 23:30 +09:00

> **갱신 기준:** 코드 변경 실측 기준. 토큰 만료로 세션 교체됐으나 코드 상태는
> `git status` + 파일 실측으로 동기화함.

## [완료 — 코드로 확정된 것]

### 스키마-as-code (설계 → 구현 완료)

| 항목 | 코드 경로 | 상태 |
|---|---|---|
| 스키마 YAML 8분기 | `schemas/_base/default.yaml` + `schemas/{etap,cap,cuap,manual,tap,stap,rap,seap}/schema.yaml` | ✅ 구현 |
| 로더 | `ops_dashboard/schema_loader.py` — `load_schema()` TTL 300초 캐시, `_resolve_branch` blogs.d 기반, deep-merge | ✅ 구현 |
| CI 정합성 게이트 | `scripts/validate_schema_pr.py` — 정방향(구조변경→스키마 동반), 역방향(드라이런) | ✅ 구현 |
| c08 2단계 판정 | `ops_dashboard/checks/c08_staging.py` — Stage 1(로컬) / Stage 2(라이브), 기존 content_integrity.py 무수정 | ✅ 구현 |

- 설계 문서: `docs/superpowers/specs/2026-08-22-schema-as-code-design.md` (READY_FOR_IMPLEMENTATION)
- c08 staging 검증: 표본 5건 — tour/trains=LOCAL_VIOLATION(말줄임표), ferry=LIVE_DRIFT(og:image),
  pick/hotissue=FALSE_POSITIVE(contains 규칙 dismiss)

### GA4 per-blog 전환 (Task 6)

| 항목 | 코드 경로 | 상태 |
|---|---|---|
| measurement_id 조회 | Admin API `list_data_streams` → `web_stream_data.measurement_id` | ✅ 34/36 확보 |
| 매핑 파일 | `config/ga4_measurement_map.yaml` — 34 confirmed / 2 미해결(eurail·phototour PermissionDenied) | ✅ 생성 |
| 템플릿 전환 | `ETAP/michelin-hugo/layouts/partials/extend-head.html` — 하드코딩 G-N4Q99745QT 제거, `site.Params.ga4_measurement_id` 사용, 미설정 시 warnf | ✅ michelin 파일럿 PASS |
| michelin 주입 | `ETAP/michelin-hugo/hugo.toml` `[params] ga4_measurement_id = "G-73WF2WRN9H"` | ✅ 빌드 검증 (G-N4Q99745QT 0회) |

- 36개 전체 적용: 각 블로그 hugo.toml에 measurement_id 주입만 남음 (Task 8 확산 시 일괄).

### GSC gsc_pages 수집 (Task 5)

| 항목 | 코드 경로 | 상태 |
|---|---|---|
| 도메인 등록 확인 | Search Console `sites().list()` — ETAP 36개 전부 **siteOwner 등록됨** (DNS 인증 불필요) | ✅ 확인 |
| GSC_SITES 확장 | `shared/analytics_collector.py` — ETAP 36도메인 추가 | ✅ |
| URL_TO_BLOG_ID 확장 | `shared/analytics_collector.py` — ETAP 36 매핑 추가 | ✅ |
| gsc_pages INSERT | `shared/analytics_collector.py:collect_gsc()` — `dimensions:["page"]` 추가 쿼리 + INSERT | ✅ |
| 초기 수집 | `data/analytics.db` gsc_pages — **563행** (22개 도메인, ETAP 계열 17개) | ✅ |

- 계획 문서: `docs/TRACKC_GSC_COLLECTION_PLAN.md`
- ETAP 데이터 있는 블로그: travel1(52p/66imp), travel3(40p/103imp), escape(15p/47imp), nomad(14p), bus(6p), cruise(5p) 등.
- 데이터 0 도메인(michelin/tour/adventure 등) = GSC 등록만 되고 아직 색인/노출 미발생.

### S2 michelin 파일럿 (Stream 1)

| 항목 | 코드 경로 | 상태 |
|---|---|---|
| writer 프롬프트 개선 | `pipelines/etap/michelin_writer.py` — STRICT STRUCTURE(At a Glance→Where to Eat→Compare→FAQ), 내부링크 ≤3/500w | ✅ |
| 파일럿 생성 검증 | Tokyo 971단어, Paris 1053단어 — H2 4개 정확, FAQ/테이블 존재, Stage 1 PASS | ✅ |

- 배포: 미배포 (사람 승인 후 dispatcher로 배포 예정).

### airports 42건 — 데이터 소진으로 재생성 불가 확정

- `airports_topics exhausted=0` 60개 ∩ `airline_routes origin`(103개) = **0개**.
- `generate_airport_guide` 가드(airlines=0 or destinations=0 → None)로 STN/KDL/LIL 차단 확인.
- **결론:** airports paused 유지. 재생성은 S3 데이터 확보(OurAirports/OpenFlights 재수집) 후.

## [진행 중 / 남은 것]

1. **michelin 파일럿 배포** — 사람 승인 → dispatcher 배포 → 라이브 6 checks.
2. **GA4 36개 전체 주입** — 각 hugo.toml measurement_id (34개 confirmed 값).
3. **Task 7: 대상 선정 로직** — gsc_pages 데이터 기반 Tier 1/2/3 (노출/클릭 > 색인 > 무색인).
4. **Task 8: 전 분기 확산** — michelin 검증 구조를 선정 대상에 적용 + 스키마 Stage 1 연동.
5. **Task 9: GA4 효과 측정 대시보드** — per-blog engagement_rate (GA4 분리 후).
6. **Cross-Branch Synthesis** — TAP travel1/4 정독 + 종합 문서 (우선순위 낮음).
7. **Phase 2 자동 피드백 루프** — 설계 문서 §10 placeholder, 별도 설계.

## [열려 있는 결정 — 대표 승인 필요]

- michelin 파일럿 배포 승인
- GA4 eurail·phototour 2건 권한 문제 해결 (다른 계정 소유 추정)
- airports S3 데이터 확보 시점 (OurAirports/OpenFlights 재수집)
- 주제 혼입 91건 / D그룹 41건 / ODbL 해석 (기존 미결 유지)

## [다음 세션 첫 명령]

"docs/superpowers/specs/2026-08-21-track-c-session-state.md 를 읽고, michelin 파일럿 배포 승인 요청부터. 이후 GA4 36개 전체 measurement_id 주입 + Task 7 대상 선정 로직 구현."
