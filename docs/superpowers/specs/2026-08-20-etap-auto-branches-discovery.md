# ETAP 자동 발행 분기 Discovery — 2026-08-20

> **상태**: DISCOVERY ONLY (설계/계획/코드수정/commit 없음 — 승인 대기)
> **작성 근거**: `config/blogs.d/etap.yaml` 정적 파싱 + `pipelines/etap/*_writer.py`·`*_pipeline.py` grep + 라이브 최신글 curl 점검
> **범위 제외**: 코드/DB 실행·수정·git 작업 일절 없음 (읽기/grep/curl 전용)

---

## 0. 신뢰 등급 정의

| 등급 | 의미 |
|---|---|
| **CONFIRMED** | 코드/grep로 직접 확인, 또는 라이브 페이지 curl로 실제 렌더링 확인 |
| **UNVERIFIED** | 정적 증거는 있으나 최종 렌더링·권위 규칙·외부 법규 근거가 부족해 단정 불가 |
| **UNKNOWN** | 해당 사실을 뒷받침할 증거 자체가 없음 |

> ⚠️ 본 문서는 **FTC 규칙·tracking 표준·deploy 변경안을 invent하지 않는다**. 관찰된 사실과 코드 근거만 기록하며, 법규 적합성 판단은 별도 Design 단계에서 수행한다.

---

## 1. 제외 기준 및 자동 발행 35개 정본

### 제외 기준
- **manual 제외**: `managed_by != pipeline` 인 분기 (ETAP 내 해당 없음 — 35개 전부 `managed_by: pipeline`)
- **paused 제외**: `status: paused` 인 분기
- **자동 발행 판정**: `status: active` + `managed_by: pipeline` + `schedule.times` 존재 → dispatcher(`dispatcher.py:465-475`, `flights`만 `flight_pipeline` 예외:460)가 `pipelines.etap.{stem}_pipeline.run` 호출, scheduler가 주기 실행 → **CONFIRMED_AUTO**

### 정본 (35개)
`etap.yaml` 총 36개 중 `nomad-hugo`만 `status: paused` → 제외. 나머지 **35개 = active 자동 발행 정본**.

| # | blog_id | domain | subgroup |
|---|---------|--------|----------|
| 1 | adventure | adventure.techpawz.com | SG-A |
| 2 | airlines | airlines.techpawz.com | SG-A (크로스셀) |
| 3 | airports | airports.techpawz.com | SG-D |
| 4 | bus | bus.techpawz.com | SG-C |
| 5 | cruise | cruise.techpawz.com | SG-A |
| 6 | culture | culture.techpawz.com | SG-A |
| 7 | daytrips | daytrips.techpawz.com | SG-A |
| 8 | deals | deals.techpawz.com | SG-E |
| 9 | dining | dining.techpawz.com | SG-E |
| 10 | esim | esim.techpawz.com | SG-B |
| 11 | eurail | eurail.techpawz.com | SG-C |
| 12 | ferry | ferry.techpawz.com | SG-C |
| 13 | flights | flights.techpawz.com | SG-E |
| 14 | foodtour | foodtour.techpawz.com | SG-A |
| 15 | michelin | michelin.techpawz.com | SG-E |
| 16 | multiday | multiday.techpawz.com | SG-A |
| 17 | nature | nature.techpawz.com | SG-A |
| 18 | phototour | phototour.techpawz.com | SG-A |
| 19 | tour | tour.techpawz.com | SG-A2 (base 폴백) |
| 20 | tours | tours.techpawz.com | SG-A |
| 21 | trains | trains.techpawz.com | SG-C |
| 22 | transfers | transfers.techpawz.com | SG-A |
| 23 | visa | visa.techpawz.com | SG-D |
| 24 | visafree | visafree.techpawz.com | SG-D |
| 25 | walking | walking.techpawz.com | SG-A |
| 26 | watersports | watersports.techpawz.com | SG-A |
| 27 | luxury | luxury.techpawz.com | SG-A2 |
| 28 | citytours | citytours.techpawz.com | SG-A2 |
| 29 | watertours | watertours.techpawz.com | SG-A |
| 30 | hiking | hiking.techpawz.com | SG-A |
| 31 | escape | escape.techpawz.com | SG-A |
| 32 | extreme | extreme.techpawz.com | SG-A2 |
| 33 | nightlife | nightlife.techpawz.com | SG-A |
| 34 | ghost | ghost.techpawz.com | SG-A |
| 35 | layover | layover.techpawz.com | SG-A |

*(제외: nomad-hugo — `status: paused`)*

---

## 2. blog별 증거 (pipeline / DB / prompt / CTA / affiliate / entity / thumbnail / output / deploy)

공통(35개 전체): DB=`data/travel-en.db`, prompt=writer 모듈 내 인라인 f-string 하드코딩, thumbnail=`image_fetcher`(Pexels+Unsplash)→R2 `etap/{slug}/cover.jpg`, FM=Blowfish(`_write_hugo_post_etap`), entity linker=`shared/entity_linker`(`entity_links`, max_links=5), deploy=`subprocess.run([wrangler,"pages","deploy","public","--project-name",blog_id])` 직접(env -u 누락).

| blog | affiliate 공급자 (증거) | DB 입력 | CTA | 추적파라미터 | 고지문 경로 | deploy 증거 |
|---|---|---|---|---|---|---|
| adventure | Viator (`viator_tours`) | viator_tours | Book Now 카드 | raw deep_link, 없음 | 없음 | `*_pipeline.py:61` |
| airlines | Viator(크로스셀) | flight_*, viator_tours | Book Now(매칭시) | raw | 없음 | airline_pipeline.py |
| airports | Airalo+Viator | airalo_esim, viator_tours | eSIM+투어 카드 | raw | 없음 | airport_pipeline.py |
| bus | Omio | omio_routes | 비교표+Omio카드 | link_url 통과 | 없음 | bus_pipeline.py:62 |
| cruise | Viator | viator_tours, viator_destinations | Book Now+비교표 | raw | 없음 | cruise_pipeline.py:63 |
| culture | Viator(+외부링크) | viator_tours | Book Now+한국문화카드 | raw + 하드코딩 링크 | 없음 | culture_pipeline.py |
| daytrips | Viator | viator_tours | Book Now | raw | 없음 | daytrips_pipeline.py |
| deals | **none** | flight_*, popular_directions | 제휴 CTA 없음 | 해당없음 | 없음 | deals_pipeline.py:70 |
| dining | **none**(미추적 URL) | michelin_restaurants | 레스토랑 카드(url) | url 통과, 추적없음 | 없음 | dining_pipeline.py:62 |
| esim | **Airalo** | airalo_esim | Airalo 플랜 카드(max8) | link 통과(collector 주입) | 없음 | esim_pipeline.py:61 |
| eurail | Omio | omio_routes | 비교표+Omio카드 | link_url 통과 | 없음 | eurail_pipeline.py:71 |
| ferry | Omio | omio_routes | 비교표+Omio카드 | link_url 통과 | 없음 | ferry_pipeline.py:63 |
| flights | **none**(명시적 no-affiliate) | flight_* | 없음 | 해당없음 | 없음 | flight_pipeline.py(미호출) |
| foodtour | Viator | viator_tours | Book Now | raw | 없음 | foodtour_pipeline.py |
| michelin | **none**(michelin_restaurants.url) | michelin_restaurants | 레스토랑 카드(url, 추적없음) | url 통과 | 없음 | michelin_pipeline.py:61 |
| multiday | Viator | viator_tours | Book Now+비교표 | raw deep_link | 없음 | multiday_pipeline.py:63 |
| nature | Viator | viator_tours, viator_destinations | Book Now+비교표 | raw | 없음 | nature_pipeline.py:72 |
| phototour | Viator | viator_tours, viator_destinations | Book Now+비교표 | raw | 없음 | phototour_pipeline.py:72 |
| tour | Viator(+tracking) | viator_tours (base 폴백) | Book Now | `_affiliate_link` 주입 | 없음 | pipeline.py:166-167 |
| tours | Viator | viator_tours | Book Now | raw | 없음 | tours_pipeline.py:61 |
| trains | Omio | omio_routes | 비교표+Omio카드 | link_url 통과 | 없음 | trains_pipeline.py:62 |
| transfers | Viator | viator_tours | Book Now | raw(미주입) | 없음 | transfers_pipeline.py:61 |
| visa | Airalo+Viator | airalo_esim, viator_tours | Airalo+Viator 카드 | raw | 없음 | visa_pipeline.py |
| visafree | Airalo+Viator | airalo_esim, viator_tours | Airalo+Viator 카드 | raw | 없음 | visafree_pipeline.py |
| walking | Viator | viator_tours | Book Now+산문CTA | raw | 없음 | walking_pipeline.py |
| watersports | Viator | viator_tours | Book Now+산문CTA | raw | 없음 | watersports_pipeline.py |
| luxury | Viator(+tracking) | viator_tours | Book Now | `_affiliate_link` 주입 | 없음 | luxury_pipeline.py |
| citytours | Viator(+tracking) | viator_tours | Book Now+비교표 | `_affiliate_link` 주입 | 없음 | citytours_pipeline.py:61,69 |
| watertours | Viator | viator_tours | 산문CTA | raw | 없음 | watertours_pipeline.py |
| hiking | Viator | viator_tours | 산문CTA | raw | 없음 | hiking_pipeline.py |
| escape | Viator | viator_tours | 산문CTA | raw | 없음 | escape_pipeline.py |
| extreme | Viator(+tracking) | viator_tours | 산문CTA | `_affiliate_link` 주입 | 없음 | extreme_pipeline.py:69-75 |
| nightlife | Viator | viator_tours | 산문CTA | raw | 없음 | nightlife_pipeline.py |
| ghost | Viator | viator_tours | 산문CTA | raw | 없음 | ghost_pipeline.py |
| layover | Viator | viator_tours | 산문CTA | raw | 없음 | layover_pipeline.py |

> 미확인→확정 정정 내역: michelin(추정 Viator → 실제 `michelin_restaurants`·SG-E), tour(전용 모듈 없음 → base `pipeline.py` 폴백·SG-A2), citytours(추정 Viator → `_affiliate_link` 확인·SG-A2), trains(추정 Omio → 확인·SG-C).

---

## 3. SG-A ~ SG-E 분류와 구현 차이

> ⚠️ **SG-A와 SG-A2는 임의 통합하지 않는다.** 둘은 Viator 공급자는 같으나 **런타임 tracking 주입 유무**로 명확히 구분된다.

| Subgroup | 구성 블로그 | affiliate 공급자 | tracking 주입 | CTA 카드 | 비고 |
|---|---|---|---|---|---|
| **SG-A** (Viator raw) | adventure, cruise, culture, daytrips, foodtour, multiday, nature, phototour, tours, walking, watersports, watertours, hiking, escape, nightlife, ghost, layover, airlines(크로스셀), transfers (19개) | Viator | **없음** (`deep_link` 그대로) | Book Now / 산문 CTA | `_affiliate_link` 함수 부재 |
| **SG-A2** (Viator +tracking) | luxury, extreme, citytours, tour(base 폴백) (4개) | Viator | **있음** (`_affiliate_link`: pid/mcid/medium=link/campaign={BLOG_ID}) | Book Now / 산문 CTA | `pipeline.py:166`, `*_pipeline.py:69-75` |
| **SG-B** (Airalo 단독) | esim (1개) | Airalo | collectors 주입 추정(미확인) | Airalo 플랜 카드 | |
| **SG-C** (Omio) | bus, eurail, ferry, trains (4개) | Omio | link_url 통과(collectors 주입) | 비교표+단일 카드 | 라이브에서 sjv.io 추적 확인 |
| **SG-D** (Airalo+Viator) | airports, visa, visafree (3개) | Airalo+Viator | raw(미주입) | 혼합 카드 | |
| **SG-E** (affiliate 없음) | deals, dining, flights, michelin (4개) | none | 해당없음 | 레스토랑 카드(michelin/dining) 또는 없음 | michelin/dining은 카드 있으나 추적/제휴 링크 아님 |

**구현 차이 요약**
- SG-A vs SG-A2: **유일한 차이 = `_affiliate_link()` 런타임 추적 파라미터 주입 유무**. 그 외 DB·prompt·thumbnail·entity·deploy·FM 전부 동일.
- SG-C(Omio)만 라이브에서 실제 추적 링크(sjv.io) 확인됨.
- SG-B/SG-D(Airalo)는 라이브에서 airalo 링크는 렌더링되나 추적 파라미터 미확인.
- SG-E는 제휴 링크 자체가 없음(deals/flights) 또는 미추적 레스토랑 URL(dining/michelin).

---

## 4. AGENTS.md 배포 규칙 인용 vs ETAP 코드 비교

### AGENTS.md 정확 인용 (권위 규칙)
> - §"배포는 반드시 dispatcher.py 사용" (약 line 497-499):
>   **"절대 수동으로 `wrangler pages deploy`나 `wrangler deploy`를 직접 실행하지 말 것. `dispatcher.py`가 Worker/Pages 구분, `CLOUDFLARE_API_TOKEN` 제거, Hugo 빌드, 직렬화 락을 전부 처리한다."**
> - §"dispatcher.py가 처리하는 작업" (약 line 534):
>   **"2. `CLOUDFLARE_API_TOKEN` env var 제거 — wrangler auth profile(OAuth) 우선 적용"**
> - §"CLOUDFLARE_API_TOKEN 환경변수 문제" (약 line 559):
>   **"1. 절대 수동 wrangler 명령어 금지"**
> - §"Cloudflare Wrangler Auth Profile" (약 line 469):
>   **"1. 절대 `CLOUDFLARE_API_TOKEN`를 wrangler subprocess에 전달하지 말 것 — profile이 무시됨"**

### ETAP 코드 (실제)
- 기본 모듈: `pipelines/etap/pipeline.py:166-167`
  ```python
  deploy = subprocess.run(
      ["/opt/homebrew/bin/wrangler", "pages", "deploy", "public", "--project-name", cf_project],
  ```
- 개별 모듈(예: `multiday_pipeline.py:63`, `nature_pipeline.py:72`, `citytours_pipeline.py:61`, `trains_pipeline.py:62`, `michelin_pipeline.py:61` 등 36개 전체): 동일 패턴 `subprocess.run([wrangler, "pages", "deploy", "public", "--project-name", blog_id])`
- **`env -u CLOUDFLARE_API_TOKEN` 미사용** — subprocess 호출 어디에도 없음.

### 판정
- **[위반 감지]**: ETAP 36개 모듈 전부가 AGENTS.md 배포 규칙(절대 수동 wrangler 금지 + CLOUDFLARE_API_TOKEN 제거 + dispatcher 경유)을 위반. dispatcher/deploy.py(`shared/publishers/deploy.py`)를 거치지 않고 직접 `wrangler pages deploy`를 호출하며, env var 제거도 없음. → 권위 규칙 대비 명확한 위반.

---

## 5. 확인된 사실 / UNVERIFIED / UNKNOWN

### CONFIRMED (확정 사실)
1. 자동 발행 정본 = ETAP 35개 (nomad-hugo paused 제외).
2. Subgroup 분류 SG-A(19)/SG-A2(4)/SG-B(1)/SG-C(4)/SG-D(3)/SG-E(4) = 35.
3. **deploy 위반**: 36개 ETAP 모듈 전부 subprocess 직접 호출 + env -u 누락 (§4).
4. **라이브 렌더링 관찰** (curl, 2026-08-20):
   | subgroup 대표 | 도메인 링크 렌더링 | 추적 파라미터 | 고지문 텍스트 |
   |---|---|---|---|
   | SG-A (adventure/goreme) | viator 15건 | **없음** | 0건 |
   | SG-A2 (luxury/jalisco) | viator 12건 | **없음** | 0건 |
   | SG-A2 (citytours/jaipur) | viator 15건 | **없음** | 0건 |
   | SG-B (esim/tanzania) | airalo 35건 | **없음** | 0건 |
   | SG-D (visa/guyana) | airalo 7건 | **없음** | 0건 |
   | SG-C (bus/manarola) | omio 15건 | **있음** (sjv.io/c/...) | 0건 |
   | SG-C (trains/murcia) | (해당 글 카드 없음) | — | — |
   | SG-E (flights/michelin) | (해당 글 카드 없음) | — | 0건 |
   - **Viator/Airalo 렌더링 링크에는 `pid=/mcid=/campaign=` 추적 파라미터가 전혀 없음.**
   - **Omio(sjv.io)만 실제 추적 링크 확인.**
   - **고지문 텍스트(affiliate/commission/파트너스/수수료/we earn 등)는 점검한 모든 페이지(10+건)에서 0건.**
5. Aviasales: `collectors/aviasales.py` 존재하나 ETAP 35개 블로그 어디에도 호출 0건 → **미사용 CONFIRMED**.

### UNVERIFIED (확정 불가 — 근거 부족)
1. **affiliate 고지문 "법규 위반" 여부**: 라이브에서 고지문 텍스트가 없음은 CONFIRMED이나, "FTC 등 외부 법규상 의무 위반" 판단은 본 Discovery 범위 밖(권위 규칙/최종 렌더 확정은 했으나 법적 효력 평가 근거 없음) → **UNVERIFIED**.
2. **Viator/Airalo 추적 파라미터 부재 원인**: `_affiliate_link`(SG-A2)는 `if pid and link` 조건부 주입, `pid=os.getenv("VIATOR_PID","")` — env 미설정 시 파라미터 미부착. 코드 조건은 CONFIRMED이나 **런타임 env 값(VIATOR_PID 설정 여부)은 미확인** → 부재 원인은 UNVERIFIED.
3. SG-C trains / SG-E flights·michelin의 "최신 글" 샘플에 카드·링크가 없었음 — 해당 글 데이터 부재 가능성. 카드 렌더링 여부는 다른 글로 재확인 필요 → **UNVERIFIED**(해당 샘플 한정).

### UNKNOWN
- 없음 (35개 블로그 전체의 affiliate 공급자·subgroup은 모두 확인 완료).

---

## 6. 다음 Design 후보와 미결정 사항

> ⚠️ 아래는 **Discovery 이후 다음 단계에서 다룰 후보/질문 나열**이며, 본 문서에서 설계·해결책·코드를 invent하지 않는다.

### Design 후보 (추후 단계)
- **D1 — affiliate tracking 표준화**: SG-A(raw)와 SG-A2(tracking)의 분열을 어떻게 조정할지. 단, **SG-A/SG-A2 임의 통합은 하지 않음** — 별도 subgroup 유지 원칙.
- **D2 — affiliate 고지문 삽입 경로 신설**: Viator/Airalo/Omio 전용 고지문이 코드에 없음(라이브 부재 CONFIRMED). 삽입 위치/문구/조건 설계 필요.
- **D3 — deploy 경로 정상화**: ETAP 36모듈의 subprocess 직접 호출을 dispatcher/`shared/publishers/deploy.py` 경유 + `env -u CLOUDFLARE_API_TOKEN` 적용으로 수정. (위반은 §4에서 CONFIRMED.)

### 미결정 사항 (추가 조사 필요)
1. **SG-A raw 블로그의 tracking 부재**: collector 단계 베이킹(`viator_api.py:63` `?pid=`) vs 런타임 env 미설정 중 어느 경로인지 — `VIATOR_PID`/`VIATOR_MCID` 환경변수 실제 값 확인 필요.
2. **michelin/dining의 혼합형 분류**: SG-E(제휴 없음)이나 레스토랑 카드(`url`)는 렌더링됨. "affiliate 없음"과 "카드 있음"의 경계 정의 필요.
3. **tour-hugo 전용 모듈 부재**: `tour_writer.py`/`tour_pipeline.py` 존재하지 않아 base `pipeline.py`로 폴백 — 의도된 설계인지, 누락인지 확인.
4. **Aviasales collectors 미사용**: 제거할지, 활성화할지 결정.
5. **Omio만 추적 링크 존재**: SG-C(Omio)만 sjv.io 추적이 살아있는 이유 — collectors/omio.py의 주입 방식이 Viator/Airalo와 다른지 확인.

---

## 7. 잔존 위험 (이 Discovery 한정)
- 라이브 점검은 각 subgroup 대표 1~2글 샘플에 국한. 전수 렌더링 검증 아님 (특히 trains/flights/michelin 최신 글은 카드 없어 판정 보류).
-deploy 위반은 코드 정적 확인으로 CONFIRMED이나, "실제 배포 실패/오동작" 여부는 런타임 점검 없음 → 영향은 UNVERIFIED.
- 외부 법규(FTC 등) 적합성은 본 문서 범위 밖.
