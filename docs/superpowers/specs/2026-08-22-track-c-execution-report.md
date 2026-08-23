---
title: "Track C Execution — GA4 per-blog + GSC gsc_pages + michelin pilot (2026-08-22)"
doc_type: EXECUTION_REPORT
status: COMPLETED
created: 2026-08-23
branch: track-c-etap-quality-overhaul
part_of: "Track C — 병렬 그룹 A/B 실행 결과"
---

# Track C 병렬 실행 보고 (2026-08-22 ~ 08-23)

> 토큰 만료로 세션 교체됐으나, 코드 변경 실측 기준으로 문서화.

## 1. michelin pilot 6 checks — S1 게이트 PASS

**검증:** michelin-hugo 최신 포스트(reykjavik-iceland) 기준, 로컬 Hugo 빌드 후 public HTML 검사.

| 체크 | 결과 | 비고 |
|---|---|---|
| Hugo build | ✅ PASS | 0 에러 |
| GA single | ✅ PASS | G-N4Q99745QT 1종 (단일). per-blog 전환은 아래 GA4 작업 |
| AdSense single | ✅ PASS | adsbygoogle.js 1회 |
| Disclosure | ⚠️ N/A | michelin 콘텐츠 affiliate 링크 0건 (조건부 렌더). adventure-hugo에서 렌더 검증(17건) |
| rel=sponsored | ⚠️ N/A | 동일 — adventure-hugo에서 15건 검증 |
| wordCount | ✅ PASS | 1193 ≥ 706 baseline |

**결론:** S1 게이트 PASS. disclosure/rel은 콘텐츠 기반 N/A — 렌더 레이어 자체는 타 블로그에서 검증 완료.

## 2. GA4 per-blog 전환 (Task 6)

### measurement_id 조회 (Admin API)

- **메서드:** `AnalyticsAdminServiceClient.list_data_streams()` → `stream.web_stream_data.measurement_id`
  (초기 `stream.measurement_id` 직접 접근은 AttributeError — `web_stream_data` 중첩 필드).
- **결과:** 34/36 확보. eurail-hugo, phototour-hugo만 PermissionDenied (다른 계정 소유 추정).

### 매핑 파일

`config/ga4_measurement_map.yaml` — 36개 blog_id → ga4_property(기존) + measurement_id(신규 확보).
34 confirmed / 2 planned.

### 템플릿 전환

- **수정:** `ETAP/michelin-hugo/layouts/partials/extend-head.html`
  - 기존: `{{ if not $gid }}{{ $gid = "G-N4Q99745QT" }}{{ end }}` (하드코딩 폴백)
  - 변경: `site.Params.ga4_measurement_id` 읽기, 미설정 시 `warnf` + 태그 미삽입 (무음 실패 금지)
- **주입:** `ETAP/michelin-hugo/hugo.toml` `[params] ga4_measurement_id = "G-73WF2WRN9H"`
- **검증:** hugo build → public/index.html에서 G-73WF2WRN9H 2회, G-N4Q99745QT 0회. **파일럿 PASS.**

### 남은 것

- 36개 전체: 각 블로그 hugo.toml에 measurement_id 주입 (Task 8 확산 시 일괄).

## 3. GSC gsc_pages 수집 (Task 5)

### 도메인 등록 확인

- Search Console `sites().list()` — **ETAP 36개 전부 siteOwner 등록됨** (DNS 인증 불필요).
  이전에 "GSC_SITES 상수에 ETAP 미등록"으로 파악됐던 것은 **코드 상수 문제**였고 실제 GSC엔 등록돼 있었음.

### collect_gsc 확장

`shared/analytics_collector.py`:
- `GSC_SITES`에 ETAP 36도메인 추가.
- `URL_TO_BLOG_ID`에 ETAP 36 매핑 추가.
- `collect_gsc()`에 gsc_pages INSERT 추가 — `dimensions:["page"]` 별도 쿼리 (rowLimit 1000).

### 초기 수집 결과 (7일치, 2026-08-19~25 기준)

- **gsc_pages 총 563행**, 22개 도메인 데이터.
- ETAP 계열: travel1(52p/66imp), travel3(40p/103imp), escape(15p/47imp), nomad(14p), bus(6p/13imp), cruise(5p/10imp), multiday(5p), watersports(3p), nightlife(2p), foodtour/luxury/trains/transfers/walking/ipo(각 1p) 등 17개.
- **데이터 0 도메인** (michelin/tour/adventure 등): GSC 등록만 되고 아직 색인/노출 미발생 → 색인 후 자동 수집.

**핵심 인사이트:** GSC 색인/노출 데이터가 이미 있는 ETAP 도메인 17개는 Task 7(대상 선정)의 즉시 입력이 됨.

## 4. S2 michelin 파일럿 본문 재설계 (Task 2 / Stream 1)

### 기존 구조 (reykjavik-iceland)

1113단어, H2 5개(Why Visit/Best Time/Where to Stay/Things to Do/Food), 내부링크 1개(0.4/500w), CTA 0, FAQ 0.

### writer 프롬프트 개선

`pipelines/etap/michelin_writer.py` — STRICT STRUCTURE 도입:

```text
1. ## At a Glance — 요약 TABLE (Restaurant | Award | Cuisine | Price), 3-7행
2. ## Where to Eat — H3 상세 (120-180단어, 시그니처/가격/선택 근거)
3. ## Compare — 비교 TABLE (+ Best For 열) — 체류 유도
4. ## FAQ — 3문항 — 롱테일 키워드
- 내부링크 ≤ 3/500w, 최대 6개
```

### 파일럿 생성 검증

- Tokyo: 971단어, H2 정확히 [At a Glance, Where to Eat, Compare, FAQ], 테이블 88 pipe, FAQ O, 외부링크 0, **Stage 1 PASS**.
- Paris: 1053단어, 동일 구조 (재현성 확인).
- **배포: 미배포** — 사람 승인 후 dispatcher로 배포 → 라이브 6 checks 재검증.

## 5. airports 42건 — 재생성 불가 확정

- `airports_topics exhausted=0` 60개 ∩ `airline_routes origin`(103개) = **0개**.
- STN/KDL/LIL 가드 차단 확인 (`airlines=0 or destinations=0 → None`).
- **결론:** airports paused 유지. 재생성은 S3 데이터 확보(OurAirports/OpenFlights 재수집) 후.
- 기존 완료 22건이 데이터 있는 전부였음.

## 6. 남은 작업

| 우선순위 | 작업 | 선행 조건 |
|---|---|---|
| 1 | michelin 파일럿 배포 + 라이브 검증 | 사람 승인 |
| 2 | GA4 36개 전체 measurement_id 주입 | 34개 값 확보됨 |
| 3 | Task 7: 대상 선정 로직 (Tier 1/2/3) | gsc_pages 데이터 (완료) + topic-suitability 승인 |
| 4 | Task 8: 전 분기 확산 | michelin 검증 |
| 5 | Task 9: GA4 효과 측정 대시보드 | GA4 분리 완료 |
| 6 | Cross-Branch Synthesis | 우선순위 낮음 |

## 7. 승인 대기

- michelin 파일럿 배포 승인
- GA4 eurail·phototour 권한 문제 (다른 계정 확인)
- airports S3 데이터 확보 시점
