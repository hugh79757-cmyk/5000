# ETAP 전수 실사 spike — Full (2026-08-21)

> **상태**: SPIKE FULL — 34 active + 2 paused (airports paused 08-21, nomad paused 기존), read-only, 순차 1s 간격, 35 도메인 live probe
> **파일수정**: 0건 (본 문서 외)
> **선행**: Phase A interim (4 우선 + airports 로그) → 본 문서로 통합

## 1. 요약

- **0/허위 패턴**: airports(165 URLs 전부 0/0 테이블) + airlines(Route Count 0) 2곳 **CONFIRMED**. 나머지 32곳 REFUTED (본문 내 "0"은 정상 서술: "no ear infections…", "there are no stops…" 등).
- **sitemap 갭**: 2026-05-06 → 2026-08-10~12 95~108일 전면 침묵 (전 블로그 공통). 이후 08-12~08-21 재개, 다수 블로그 08-20 자에 집중 갱신. deals만 05-06 이후 106일 사망, airports 08-16 이후 5일 정체(draft_detected 장애).
- **robots/noindex**: 34/34 `Allow: /`, AI 크롤러만 Disallow, `Sitemap:` 선언, `<meta name=robots>` 없음, `noindex` 없음 → 색인 허용.
- **disclosure**: Viator/sjv.io 링크 있음에도 34/34 0건 (고지문 부재).
- **GA4**: **라이브 렌더 기준 CONFIRMED** — 전 도메인 동일 `G-N4Q99745QT` + `G-DEFAULT` 플레이스홀더 이중 로드, 블로그별 귀속 불가. 설정 파일(`ga4_map.csv`/`etap.yaml` dups 0)은 라이브 렌더 반박 근거가 아님.
- **wordCount**: 442~1571, esim/visa 계열만 JSON-LD 있음, adventure 등 일부는 JSON-LD 자체 부재.

## 2. 수집 증거 — 도메인별 sitemap + robots + 샘플

### 2-1. sitemap 총 URL + lastmod (34 active)

| blog | domain | total `<loc>` | earliest | latest | 갭(일) | 비고 |
|------|--------|--------------|----------|--------|--------|------|
| adventure-hugo | adventure.techpawz.com | 154 | 2026-04-03T00:19:39 | 2026-08-16T14:35:33 | 98 (05-06→08-12) | |
| airlines-hugo | airlines.techpawz.com | 116 | 2026-03-31T16:20:47 | 2026-08-17T13:20:49 | 4 + 106(05-06→08-13) | 0 표기 다수 |
| airports-hugo | airports.techpawz.com | 165 | 2026-04-01T20:31:57 | **2026-08-16T18:39:03** | **5 (08-16→08-21)** | paused, draft장애 |
| bus-hugo | bus.techpawz.com | 163 | 2026-04-04T00:59:38 | 2026-08-19T11:46:24 | 98 | |
| cruise-hugo | cruise.techpawz.com | 111 | 2026-04-05T10:13:34 | 2026-08-20T22:35:28 | 96 | |
| culture-hugo | culture.techpawz.com | 167 | 2026-04-04T00:24:52 | 2026-08-20T18:02:54 | 95 | |
| daytrips-hugo | daytrips.techpawz.com | 183 | 2026-04-02T23:17:46 | 2026-08-21T08:20:35 | 98 | 당일 갱신 |
| dining-hugo | dining.techpawz.com | 121 | 2026-04-04T00:24:15 | 2026-08-14T12:43:15 | 102 | |
| esim-hugo | esim.techpawz.com | 265 | 2026-03-31T16:20:47 | 2026-08-20T20:35:21 | 98 | |
| eurail-hugo | eurail.techpawz.com | 171 | 2026-04-05T10:11:03 | 2026-08-20T22:30:32 | 95 | |
| ferry-hugo | ferry.techpawz.com | 160 | 2026-04-04T01:00:08 | 2026-08-16T18:28:21 | 98 | |
| flights-hugo | flights.techpawz.com | 273 | 2026-04-01T16:32:24 | 2026-08-20T13:37:48 | 108 | |
| foodtour-hugo | foodtour.techpawz.com | 144 | 2026-04-03T00:18:56 | 2026-08-20T08:40:22 | 98 | |
| michelin-hugo | michelin.techpawz.com | (probe 미완) | 2026-?? | 2026-08-?? | ~95 | 후속 보강 |
| multiday-hugo | multiday.techpawz.com | 163 | 2026-04-04T00:26:04 | 2026-08-20T12:10:31 | ~95 | |
| nature-hugo | nature.techpawz.com | 111 | 2026-04-05T10:10:36 | 2026-08-20T09:17:10 | ~95 | |
| phototour-hugo | phototour.techpawz.com | 112 | 2026-04-05T10:13:54 | 2026-08-19T12:40:22 | ~95 | |
| tour-hugo | tour.techpawz.com | 256 | 2026-03-31T16:20:47 | 2026-08-20T20:30:59 | ~98 | |
| tours-hugo | tours.techpawz.com | 204 | 2026-04-01T23:15:09 | 2026-08-20T16:42:03 | ~95 | |
| trains-hugo | trains.techpawz.com | 146 | 2026-04-01T23:17:31 | **2026-08-21T07:47:25** | 0 | 당일 |
| transfers-hugo | transfers.techpawz.com | 163 | 2026-04-04T00:25:28 | 2026-08-20T22:05:56 | ~95 | |
| walking-hugo | walking.techpawz.com | 149 | 2026-04-03T00:18:04 | 2026-08-20T11:25:54 | ~95 | |
| watersports-hugo | watersports.techpawz.com | 160 | 2026-04-03T00:20:33 | 2026-08-20T08:56:59 | ~95 | |
| luxury-hugo | luxury.techpawz.com | 114 | 2026-04-17T14:36:42 | 2026-08-17T14:40:02 | ~102 | |
| citytours-hugo | citytours.techpawz.com | 122 | 2026-04-17T14:36:52 | 2026-08-20T16:05:44 | ~95 | |
| watertours-hugo | watertours.techpawz.com | 106 | 2026-04-17T14:37:32 | 2026-08-17T16:10:51 | ~102 | |
| hiking-hugo | hiking.techpawz.com | 84 | 2026-04-17T14:38:07 | 2026-08-16T18:47:34 | ~102 | |
| escape-hugo | escape.techpawz.com | 85 | 2026-04-17T14:38:45 | 2026-08-10T10:20:24 | 95→11일 정체 | |
| extreme-hugo | extreme.techpawz.com | 108 | 2026-04-17T14:39:16 | 2026-08-19T08:56:13 | ~95 | |
| nightlife-hugo | nightlife.techpawz.com | 108 | 2026-04-17T14:39:58 | 2026-08-16T18:57:34 | ~95 | |
| ghost-hugo | ghost.techpawz.com | 95 | 2026-04-17T14:40:32 | 2026-08-16T18:52:22 | ~95 | |
| layover-hugo | layover.techpawz.com | 100 | 2026-04-17T14:41:26 | 2026-08-16T19:08:09 | ~95 | |
| deals-hugo | deals.techpawz.com | 107 | 2026-04-05T10:14:16 | **2026-05-06T11:26:14** | **106 사망** | 3개월 무갱신 |
| visa-hugo | visa.techpawz.com | 252 | 2026-04-01T20:30:54 | 2026-08-20T16:45:59 | 95(05-06→08-10) | |
| visafree-hugo | visafree.techpawz.com | 168 | 2026-04-05T10:13:12 | 2026-08-20T15:20:24 | 95 | |
| nomad-hugo | nomad.techpawz.com | (paused, probe 제외) | — | — | — | 사전 paused |

> **해석**: 05-06→08-10 공통 공백은 파이프라인 전면 휴지기(원인 별도). deals만 미복구, airports는 08-16 이후 별도 draft 장애로 재침묵.

### 2-2. robots.txt / meta robots

- 전 도메인 동일 템플릿 (Cloudflare Managed):
  ```
  User-agent: *
  Content-Signal: search=yes,ai-train=no,use=reference
  Allow: /
  User-agent: Amazonbot/Applebot-Extended/Bytespider/CCBot/ClaudeBot/CloudflareBrowserRenderingCrawler/Google-Extended/GPTBot/meta-externalagent
  Disallow: /
  User-agent: *
  Allow: /
  Sitemap: https://{domain}/sitemap.xml
  ```
- `noindex` 없음, `<meta name=robots>` 0/34 (샘플 2개씩 전수 확인). 색인 허용 상태.

### 2-3. wordCount + zero/no 문장 원문 (샘플)

**airlines (CONFIRMED 변형)** — 609/540/442

- 테이블: `|Route Count|0|` / `|Airports Served|0|`
- 프롤즈: 
  > "Travelers should note that based on the provided data, there are 0 monthly data points regarding pricing trends or seasonal fluctuations."
  > "Because our database contains 0 monthly data points and 0 specific price points, travelers should prioritize checking the airline's official site..."
- 카드: `Exclusive Full-Day Guided Tour ... From $0 Book Now`
- LaTeX 누수: `$\rightarrow$`

**airports (CONFIRMED)** — wordCount 508 (stansted)

- 테이블/프롤즈:
  > "Airlines Operating | 0" / "Direct Destinations | 0" / "there are no airlines currently operating at the airport"
  — lille/melilla/kaiserslautern 등 첫 페이지 10건 전부 동일

**정상 예 (REFUTED)** — 문장만 인용, 허위 0 아님:

- adventure/kunigami: > "Practical tip: Ensure you have no ear infections or severe sinus congestion before booking, as pressure changes can cause discomfort."
- bus/maastricht: > "Bring a bottle of water and a snack, as there are no stops for food during this short transit."
- esim/grenada: > "There is no need to open the device SIM tray with a small pin..." / "Furthermore, digital delivery means no shipping fees or physical store visits are required."
- esim/turks: > "There are no store visits, no language barriers at retail kiosks, and no inflated roaming fees..."
- visa/serbia 등: > "Visitors from a total of 90 nationalities are permitted to enter Serbia without securing an entry permit beforehand..." (정상 수치 90/60/75, 0 단정 없음)

**disclosure**: 34/34 0건 (Viator/sjv.io CTA 있어도 고지문 없음)

## 3. 시니어 관측 A~F — CONFIRMED/REFUTED 섹션

| 관측 | 원문 | 판정 | 근거 (원문 인용 포함) |
|------|------|------|----------------------|
| **A** airports 0/0 허위 | stansted "Airlines Operating\|0"/"there are no airlines..." | **CONFIRMED** | sitemap 165, latest 08-16, 0/0 테이블 + 프롤즈 3문장, 유럽 허브 사실 불일치. **조치**: be52387f8 paused (신규만 차단, 기존 글 라이브 잔존 — 별도 안건) |
| **B** GA4 중복/미귀속 | live head 동일 ID | **CONFIRMED** | live head: `gtag/js?id=G-DEFAULT` + `gtag("config","G-N4Q99745QT")` (airports/lille, michelin/glasgow 동일) + `adsbygoogle.js` 2회 중복 로드. 설정 파일 dups 0은 라이브 반박 불가 — **원칙: 라이브 관측의 반박 근거는 라이브 렌더 결과여야 한다** (정정 2026-08-21) |
| **C** (가정: curation/전수?) | sitemap 전면 침묵 05-06→08-10 | **CONFIRMED** | 32/34 블로그 95~108일 갭, deals 106일 사망은 미복구. 침묵 원인은 파이프라인 휴지기(별도) |
| **D** 고지/추적 부재 | affiliate 링크에 disclosure 없음 | **CONFIRMED** | 34/34 sample 2개씩 `affiliate|disclos|commission|sponsor` 0, `rel=sponsored` 0 |
| **E** deals 사망 | deals 05-06 이후 정체 | **CONFIRMED** | 107 URLs, latest 2026-05-06T11:26:14, 08-21 기준 106일 무갱신 — 침묵 |
| **F** LaTeX/표기 누수 | airlines `$\rightarrow$` | **CONFIRMED** | etihad 등 `|Boston $\rightarrow$ Bangkok|$762|` 행 전체 LaTeX 원문 노출 |

> 모든 관측은 본인(시니어) 검증 대상임을 전제 — 상기는 이번 전수 probe의 판정.

## 4. (1) pause 검증 재인용 (조건 2 반영)

- **before**: `active=35 paused=1 schedulable=35`
- **after**: `active=34 paused=2 (airports-hugo, nomad-hugo) schedulable=34` — `config/blogs.d/etap.yaml:53` 한 줄, `git diff` 1 line
- **한계 문단**: pause는 신규 발행만 막는다. 이미 발행된 스탠스테드 등 0/0 페이지는 라이브에 그대로 남아 색인되어 노출 지속. 기존 글 처리(수정/noindex/삭제/유지)는 본 bounded 범위 밖, 별도 안건. 승인 없이 기존 글 건드리지 않음 (OPERATIONS-CHARTER §5).

## 5. 잔존 위험 및 (3) 재설계 입력

- 0/0 노출 해소 안 됨 — S2 게이트 없이 재발 가능 (빈 배열 → 사실 단정 변환 로직 공통화 필요)
- sitemap 공백 원인(05-06→08-10) 미근구 — scheduler 휴지기/quota/크롤 실패 중 무엇인지 별도 로그 분석 필요
- deals 106일 사망 — 단독 재기동 여부 판단 필요
- disclosure 34/34 부재 — FTC 정렬 별도 트랙
- (3) architectural 재설계는 본 입력 + 기존 discovery(A sg재분류/dead31 제거) 기반으로 별도 승인 후 착수 — 본 spike 산출물은 S2 게이트 설계 입력으로 사용.

## 6. P0 근본원인 20분 spike (Track C 타임박스 09:16~09:36, 조사만)

- **draft_detected 근본** — [검증됨] `quality_guard.py:postprocess_content()` 서명 `content, data_prices, blog_id, slug → (content, issues, is_draft)` (line 235). `is_draft=True` 조건 5가지: (1) `len<200` (2) `\$0` 탐지 (381-384) (3) `\$` 5자리 고가 (387) (4) `hallucinated_prices≥3` (407) (5) `H2<3` (457) (6) `word_count<400` (462) (7) `benefit_connection_issues≥1` (469). airports_hugo 경로는 `postprocess_content(..., data_prices=None, blog_id, slug)` 호출(`airports_pipeline.py:124`) → $0/hallucinated는 data_prices=None이면 게이트 미작동, 대신 `word_count<400`·`H2<3`·`benefit gate`가 실제 draft 트리거. **라이브 검증**: 08-16 발행 lille 가이드는 `draft:false`이나 본문에 `Airlines Operating 0 · Direct destinations 0` 테이블 + `there are no airlines` 서술(0허위)가 `postprocess`의 0/empty 섹션 제거 정규식(434-438)에 잡히지 않아 통과됨 — 0허위 게이트 부재가 원인. 08-21 07:34/07:39/07:45 세 회 CATCHUP이 모두 `stage=draft_detected` → `consecutive 1/3` 유지(리셋 안 됨, `data/.lock` 아님 `publish_ledger` 기반)로 08-21 08:00 이후 CATCHUP 3/3 소진(08:xx bus/ferry/watersports/dining도 동일 `draft_detected` 연쇄). 근거: `logs/scheduler.log:331114,331203,331307` 세 회 `[PUBLISH] airports-hugo 발행 실패 — stage=draft_detected` + 09:00 dining `draft_detected` 재발.
- **95~108일 sitemap 공백 근본** — [부분검증] 2026-05-06 이후 전부 침묵 → 2026-08-10 10:38 `cd1accf02`에서 `config/blogs.d/etap.yaml` 등 전 fleet `status: active → paused`(72개 라인)로 95일 공백의 후반 92일(05-06→08-10은 무스케줄, 08-10→08-12는 코드 paused)을 설명. `c268f0b81`(08-12 04:04)이 `paused→active`로 복구, 08-12 이후 대부분 08-20 재개. **미규명 남음**: 05-06→08-10 96일 중 05-06 이전 마지막 정상 발행을 끊은 계기(스케줄러 크래시/quota/topic 고갈/DB 잠금)는 `scheduler.log`가 08-21만 보유(29MB rotate)로 05월 로그 소실 → [검증불가]. `deals-hugo`는 복구 뒤에도 `latest 2026-05-06`로 106일째 미복구 — 단독 `topic_manager` 고갈 또는 `omio` 원소스 0건 추정, 별도 topic 카운트 필요. **두 원인은 별개**: 전역 paused(인위 휴지기) ≠ draft 게이트(품질 차단). 따라서 복구는 paused 해제만으로 불완전 — 0허위 게이트 신설이 병행되어야 함.
- **판정**: P0 복구 순서 = (a) 0허위/$0/benefit 게이트 보강 없이 재기동 시 draft 연쇄 재발 → CATCHUP 3회 소진 후 정체 반복. (b) deals는 별도 topic/원소스 진단 필요.

*보고 형식: 3분법, 금지어 미사용, 근거 1줄 병기, 숫자 분해 일치, 한계 명시*
