# ETAP spike Phase A — 4 우선 블로그 중간 보고 (2026-08-21)

> **상태**: SPIKE INTERIM — 4/35 완료, read-only probe, 1s 간격 순차 크롤
> **범위**: senior 지정 4개 (airlines / visa / visafree / deals) + airports 추가 검증
> **파일수정**: 0건

## 1. Verbatim 검증 — pause 외 5일 공백은 별도 장애

**airports-hugo sitemap 라이브**

- 총 URL: 165 (`<loc>` 165, `<lastmod>` 165)
- earliest: `2026-04-01T20:31:57+07:00`, latest: `2026-08-16T18:39:03+09:00` (lille-airport-lil-guide)
- 08-16 이후 갱신 없음 — 현재 08-21 기준 5일 공백
- 이전 5일간 발행 멈춤은 pause와 무관: scheduler 로그 2026-08-21 07:34~07:45 3회 연속 `CATCHUP: airports-hugo expected=1 actual=0 missed=1 quota=5 attempt=1/3..3/3` → `Publishing: airports-hugo` → `stage=draft_detected` / `dispatcher reported failure or missing JSON` / `consecutive failures=1/3`으로 보충 실패. 즉 live 파일에 draft가 남아 빌드 차단된 별개 장애.
- ⏭ **후속**: draft 파일 해소 + publishing 재시도 필요 (S2 게이트와 별도)

> pause 검증은 sitemap 갱신이 아니라 `active 35→34, paused 1→2, schedulable 34` + `skip: paused` 로 증명 — commit be52387f8 참조. sitemap 08-16 정체는 pause 전 장애의 증거.

## 2. 4 우선 블로그 — 개별 결과 (문장 원문 포함)

### airlines-hugo — [검증됨] 0/허위 노출 CONFIRMED (형상은 테이블 0)

- **sitemap**: 116 urls, earliest `2026-03-31T16:20:47+09:00`, latest `2026-08-17T13:20:49+09:00` (4일 전), 3.5개월 공백 `2026-05-06 → 2026-08-13` 무갱신.
- **robots**: `Allow: /`, AI 크롤러만 Disallow, `Sitemap: https://airlines.techpawz.com/sitemap.xml`, noindex 없음. `<meta name=robots>` 없음.
- **wordCount**: 609 / 540 / 442 (thin, 900 미만)
- **0/no 패턴 — 문장 통째 인용**:
  - `tap-portugal`: `|Route Count|0|` / `|Airports Served|0|` (테이블 행: `|Route Count|0|`) — `Cheapest Direct Route Miami → Lisbon – $494`는 정상이나 두 카운트는 허위 0.
  - `etihad-airways`: `|Route Count|0|` / `|Airports Served|0|` + LaTeX 누수 `$\rightarrow$` (예: `|Boston $\rightarrow$ Bangkok|$762|`)
  - `thai-airways` prose:
    > "Travelers should note that based on the provided data, there are 0 monthly data points regarding pricing trends or seasonal fluctuations."
    > "Because our database contains 0 monthly data points and 0 specific price points, travelers should prioritize checking the airline's official site to confirm that current schedules and costs align with their budget."
    투어 카드: `Exclusive Full-Day Guided Tour of Old and New Delhi Day Trips From $0 Book Now`
- **고지**: 3/3 모두 disclosure 0, `rel=sponsored` 0.
- **판정**: 관측 대상 — **CONFIRMED** (형상은 `Airlines Operating 0`이 아니라 `Route Count 0` 변형, 허위 0 동일)

### visa-hugo — [검증됨] 0/허위 패턴 없음 REFUTED, 고지 없음

- **sitemap**: 252 urls, earliest `2026-04-01T20:30:54+07:00`, latest `2026-08-20T16:45:59+09:00` (당일), 95일 공백 `2026-05-06 → 2026-08-10` 전에는 있음, 현재는 daily 발행 중.
- **robots**: `Allow: /`, noindex 없음. `<meta name=robots>` ABSENT.
- **wordCount**: 1026 / 923 / 810
- **문장 인용** (대표, 0/no 허위 없음 — 정상 수치 서술):
  > "Visitors from a total of 90 nationalities are permitted to enter Serbia without securing an entry permit beforehand..."
  > "Specifically, citizens of 60 nationalities are granted visa-free entry for stays up to 90 days."
  > "In addition to the visa-free group, citizens of 75 nationalities are eligible to receive a visa on arrival when entering the country."
  — `0` 허위 단정 없음, `no ...` 부정도 없음.
- **고지**: 3/3 disclosure 0 (투어/eSIM CTA 있음에도).
- **판정**: **REFUTED** — 0/허위 없음. 고지만 미비.

### visafree-hugo — [검증됨] REFUTED

- **sitemap**: 168 urls (post 166), earliest `2026-04-05T10:13:12+09:00`, latest `2026-08-20T15:20:24+09:00`, 95일 공백 `2026-05-06 → 2026-08-10`.
- **robots**: 동일, noindex 없음, `<meta name=robots>` NONE.
- **wordCount**: 1177 / 1005 / 1142
- **문장**: `<blockquote>` 1건씩 외 extended quotation 0, 0/no 허위 문장 0.
- **고지**: 0.
- **판정**: **REFUTED**

### deals-hugo — [검증됨] REFUTED, 단 장기간 침묵 (사망)

- **sitemap**: 107 urls (post 105), earliest `2026-04-05T10:14:16+09:00`, latest `2026-05-06T11:26:14+09:00` — **106일 무갱신** (스톨), 2026-08-21 기준 3개월 사망.
- **robots**: `Allow: /`, noindex 없음, `<meta name=robots>` NONE.
- **wordCount**: 872 / 946 / 897 — `affiliate|disclos|commission` 0 hits, zero/no sentence 0 hits (6133 chars scan).
- **판정**: **REFUTED** — 0 허위 없음. 단 sitemap 05-06 이후 정체는 별도 장애 (파이프라인 침묵).

## 3. 관측 A~F 대비 (전수 대비 중간 판정 — Phase A만)

| 관측 | Phase A 근거 | 판정 |
|------|--------------|------|
| A airports 0/0 | 스탠스테드 `Airlines Operating 0` + lille 등 0/0 165 URLs, latest 08-16 | **CONFIRMED** (이미 paused) |
| B GA4 중복/미귀속 | live head `G-DEFAULT`+`G-N4Q99745QT` 전 도메인 공통 (airports/lille, michelin/glasgow 동일) | **CONFIRMED** (정정 08-21: 설정 파일 dups 0은 라이브 반박 불가, 라이브 렌더 기준) |
| airlines 계열 | 8 hits, `Route Count 0` 테이블+프롤즈 0 data points | **CONFIRMED 변형** |
| visa/visafree | 정상 수치 90/60/75 등, 0 단정 없음 | **REFUTED** |
| deals | 0 hits, 106일 사망 | **REFUTED** |

## 4. 1s 간격 및 수집 항목 준수

- 요청 간 1s 간격 순차 크롤 유지 (probe 로그: sequential)
- robots.txt / sitemap 총수·earliest/latest / wordCount 전부 수집, 0/no 문장 통째 인용 완료, 숫자만 보고 없음.

## 5. 다음 단계

- Phase B: 나머지 31 블로그 동일 스키마로 순차 probe (rate limit 준수) → 전수 문서 갱신
- B GA4 중복 등 C~F 검증은 Phase B 완료 시 CONFIRMED/REFUTED 확정

*보고 형식: 금지어 미사용, [검증됨] 분류, 원문 인용 병기, 파일 수정 0*
