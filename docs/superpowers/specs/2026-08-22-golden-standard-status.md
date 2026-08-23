# ETAP 13개 패밀리 Golden Standard 현황

생성일: 2026-08-22
기준: 15항목 공통 체크리스트 (본 문서 하단)

## 패밀리 상태 테이블

| Family | 기준 블로그 | 도메인(실측) | 상태 | 통과 |
|--------|------------|------------|------|------|
| F1 | foodtour-hugo | foodtour.techpawz.com | 기존 통과 | ✅ |
| F2 | tour-hugo | tour.techpawz.com | 통과(2026-08-22 배포) | ✅ |
| F3 | eurail-hugo | eurail.techpawz.com (baseURL 누락→수정함) | 통과(2026-08-22 배포) | ✅ |
| F4 | daytrips-hugo | daytrips.techpawz.com | 통과(2026-08-22 배포) | ✅ |
| F5 | visa-hugo | visa.techpawz.com | 통과(2026-08-22 배포, #1/#6 N/A 후보) | ✅ |
| F6 | airlines-hugo | airlines.techpawz.com | 통과(2026-08-22 배포) | ✅ |
| F7 | airports-hugo | airports.techpawz.com (config/_default/hugo.toml 구조 — 유일) | 통과(2026-08-22 배포) | ✅ |
| F8 | deals-hugo | deals.techpawz.com | 통과(2026-08-23 배포, #1/#6 N/A) | ✅ |
| F9 | dining-hugo | dining.techpawz.com | 통과(2026-08-23 배포, #1/#6 N/A) | ✅ |
| F10 | esim-hugo | esim.techpawz.com | 통과(2026-08-23 배포) | ✅ |
| F11 | flights-hugo | flights.techpawz.com | 통과(2026-08-23 배포, #1/#6 N/A 후보) | ✅ |
| F12 | michelin-hugo | michelin.techpawz.com | 통과(2026-08-23 배포, #1/#6 N/A) | ✅ |
| F13 | nomad-hugo | nomad.techpawz.com | 통과(2026-08-23 배포 — family-map으로 식별) | ✅ |

## 블로커 목록

- ~~F13 기준 블로그 미상~~ → 해소(2026-08-23): `2026-08-21-etap-family-map.md` 기준 F13 = nomad-hugo(단일 멤버, paused, 39 posts)로 확정·통과 처리. 13/13 패밀리 전부 통과
- airlines_topics 데이터 공백: 727 잔여 중 681행(94%) 발행 불가 데이터 부족 → exhausted=1 일괄 정리(백업 /tmp/opencode/f6_exhausted_backup.txt), 유효 ~46행. 다른 *_topics 풀도 동일 공백 가능성 — 각 패밀리 진입 시 확인 권장

## 패밀리별 상세 기록

### F6 airlines-hugo — 통과 (2026-08-22)

**기존 포스트(turkish-airlines-airline-review)**: 15항목 라이브 사실상 전부 통과 — 단 LLM이 우연히 문단 시작+링크가 붙은 케이스라 재발 방지 픽스 병행.

**픽스 3건 [PRODUCTION CODE]**:
1. airlines_writer.py 인트로 우선 규칙 추가("Start with a 2-3 sentence introduction paragraph BEFORE any heading")
2. airlines_pipeline.py `_add_product_cards`(:127) 직후 cross-sell 블록(base :333-339 클론; 항공사 리뷰는 도시 컨텍스트 없어 city/country 빈값 전달)
3. airlines_writer.py 단어 규칙 신설(기존 무규칙): "MINIMUM 1,100 words, target 1,200-1,600 … under 1,000 rejected" + 섹션 확장 지시 → 실측 864→1,861단어

**토픽 풀 정리**: 잔여 727개 중 flight_direct 보유 27/route 12뿐 → 파이프라인 동일 기준(iata 미등록 OR 데이터포인트<3) SQL 선별로 681행 exhausted=1. royal-air-maroc는 CRITICAL(empty-data hallucination)→**draft:true 처리로 Hugo 미발행 = quality_guard 게이트 정상 작동 입증**(draft 소비분 publish_log id=208). UA/AA/QR priority=99 부스트 운영. QR(qatar-airways)은 864단어 #15 미달이나 나머지 통과+실발행 유지(잔존 위험 기록).

**검증 포스트: american-airlines-airline-review — 15항목 로컬+라이브 통과**: draft False/H2 10(md)/11(html)/lead/img9·webp8/words 1,861/strong_para 0/bq 2(시스템 카드)/techpawz main 10/card-title 1/viator 3/og:title 클린. 배포 421df11b(cf_project=airlines-hugo).

**버그 기록**: shared.telegram_notifier에 send_critical 없음 → ImportError(비치명, 진행됨). quality_guard의 CRITICAL 알림 경로 누락 — 별도 수정 과제.

**측정 교정안 누적**: #2 og:image webp / #5 `class="?etap-disclaimer-card` strip 후 strong_para / #8 `<main>` greedy 추출+`techpawz\.com` 문자열 카운트(Hugo minify 무따옴표 href 대응) / #14 og:title / #15 로컬 md 기준 / lead=`class="lead` 접두 / curl+UA 필수(python urllib 403) / 움라우트 slug URL 인코딩

### F2 tour-hugo — 통과 (2026-08-22)
- 테스트 발행: `_run_impl()` 직접 호출 (run_batch는 당일 쿼타 5/5 소진 게이트). 토픽 id=88 Manzanillo/Mexico
- 파일: content/posts/manzanillo-mexico-guide/index.md / LLM 성공 / cover+body 8장 R2 webp
- 15항목 **15/15 통과** (affiliate링크 15 / featureimage R2 webp / 본문img 11 / H2 6개 전부 가드 허용패턴·강등 0 / product-cards 1 / disclaimer 1 / cross-sell techpawz 링크 7 / lead 1 / tags 정상 / LLM blockquote 0 / 과장볼드 0 / 투어명 반복 0 / 금지패턴 0 / 1,588단어)
- 참고: hugo_writer 제휴인근 disclaimer 스킵 로그 → quality_guard의 etap-disclaimer-card 삽입으로 #7 충족
- Hugo 빌드 856ms → wrangler pages deploy 완료 → 라이브 curl 5종 통과 (HTTP 200/40,788B, h2 7, img 11, disclaimer·카드 발화, viator 링크, lead 렌더)
- F3 준비 중 발견: eurail-hugo/hugo.toml baseURL 누락(3줄뿐) → `https://eurail.techpawz.com/` 1행 추가함

### F3 eurail-hugo — 통과 (2026-08-22)

**발견된 결함 4종 → 수정 4건**:
1. H2 가드 비매칭: 구 프롬프트 필수 H2 전부 강등(`<p><strong>` 4개)·첫 H2만 생존 → eurail_writer 프롬프트를 가드 허용 패턴 제목으로 재작성(Route Options at a Glance / Train Guide: What to Expect / Tips for Booking Ahead / Money-Saving Tips for This Route / Practical Tips for Travelers 등) + 인트로 문단 우선 규칙(lead 래핑 조건 충족)
2. body 이미지 0장: image_fetcher.fetch_body_images는 관련성 필터 탈락 시 빈 리스트 반환(폴백 부재) → `if not collected:` 무필터 폴백 추가(cover 폴백과 대칭). györ 포스트에서 5장 확보 입증
3. 단어수 미달(779<1000): 프롬프트 "MINIMUM 1,100 words, target 1,200-1,600 … rejected" + "Expand each H2 into 2-3 full paragraphs" (nomad_writer 검증 패턴 차용) → 실측 1,458~1,514
4. cross-sell 0 + 볼드 라벨: (a) 전용 파이프라인은 cross-sell import만 하고 호출 없음(base에만 실동작) → base pipeline.py:333-339 블록을 eurail_pipeline._add_product_cards 이후 복제(dest_country/destination 사용) (b) 시스템 프롬프트에 라벨형 볼드 금지 rule 추가 (c) 제목 금지규칙("A Practical Guide"/"A Comprehensive Guide") 추가

**테스트 발행 2건 모두 15항목 로컬+라이브 통과**:
- saarbrücken-to-berlin-train: 신규 코드로 발행. H2=7/img 7장 webp/og:image R2 webp/lead/disclaimer/strong_para 0/techpawz 고유링크 7/words ~1,381/제목 클린
- györ-to-budapest-train: 픽스 이전 발행분 → 제목 sed 수정 + cross-sell 원샷 주입(build_cross_sell_html Hungary/Budapest) 후 재배포. `<main>` techpawz 링크 1, og:title 클린
- 배포: wrangler pages deploy --project-name=eurail-hugo 3회(882448fb/9104e9a9/2c646c82)

**플랫폼 이슈 기록 (미수정 — 35블로그 영향)**:
- 첫-H2 가드 루프: `_fix_invalid_h2`의 regex `\n##\s+`가 선행 개행 필요 → 본문 첫 H2는 검사 불가(생존), 이후만 강등. 공유 regex `(?:^|\n)` 수정 시 전 블로그 재검증 필요
- lead 스킵 조건: `_apply_lead_shortcode`는 첫 블록이 `#`/`##`/`{{<` 등으로 시작하면 무조건 스킵 — 인트로 없는 포스트는 lead 영구 누락

**측정 교정안 (이후 패밀리 검증 적용)**:
- #2 featureimage: 'featureimage' 문자열 대신 `og:image[^>]+r2\.dev[^>]+\.webp`
- #5 볼드강등: etap-disclaimer-card div(시스템 카드) 제외 후 strong_para 계산
- #8 cross-sell: 페이지 전체 techpawz regex 금지(Hugo nav 절대경로 오염) → `<main>` 영역 또는 로컬 md 기준
- #14 제목: og:title 기준
- URL 인코딩: 움라우트 slug는 %C3%B6/%C3%BC 인코딩 필수

### F4 daytrips-hugo — 통과 (2026-08-22)

**결함 2종 → 수정 2건**:
1. cross-sell 0: daytrips_pipeline도 import-only(F3와 동일) → `_add_product_cards`(:137) 직후 base :333-339 블록 복제(topic city/country 사용)
2. lead 0: 프롬프트가 훅 문장을 `## [Hook…]` H2로 요구 → 본문 첫 블록이 `##`라 lead 스킵(+첫-H2 가드 루프로 검사 회피) → STRUCTURE 교체: "인트로 문단 2-3문장을 헤딩 전에, 훅은 plain text" + 섹션 H2 4개 유지(Best Budget Day Trips 등 — 전부 기존 가드 허용 패턴)

**테스트 발행**: prague-day-trips (`_run_impl()` 직접 호출). 로컬: lead True/H2 3(데이터 부족 OMIT 규칙)/words 1,270/imgs webp 3+tripadvisor 썸네일 5(비교테이블 상품 이미지—기존 설계)/techpawz 링크 6/title 클린. 배포 f48e2e85 → 라이브: og:image R2 webp/techpawz main 10/disclaimer/viator·sjv 12/og:title 클린 → **15항목 통과**

**관찰(미조치)**:
- 비교테이블의 tripadvisor 상품 썸네일 이미지는 외부 CDN — writer 원래 설계, 체크리스트(#3 body img)와 별개 항목
- content/posts에 비라틴 슬러그 포스트 다수 존재(아랍어·태국어 등) — 별도 이슈로 추적 권장

**측정 교정안 추가**:
- lead 렌더 체크: `class="lead` 접두 매칭 (정확매칭은 복수클래스 오탐)
- disclaimer 카드 strip: 무따옴표 속성 대응 `class="?etap-disclaimer-card`
- 라이브 fetch: python urllib → Cloudflare 403. 반드시 curl + User-Agent 헤더

### F5 visa-hugo — 통과 (2026-08-22)

**결함 2종 → 픽스 2건**:
1. cross-sell import-only(visa_pipeline.py :18/:24/:25, eurail/daytrips와 동일 패턴) → :133 _add_product_cards 직후 base :333-339 블록 복제. topic에 city/country 없음(passport 기반 스키마) → `build_cross_sell_html(country=article.get("country",""), city=topic.get("passport",""))`로 적용
2. 인트로 문단 규칙 부재(destination/passport 양쪽 프롬프트 모두) → 본문이 H2로 시작해 lead 스킵. 양쪽 분기 RULES 첫 줄에 "Start with a 2-3 sentence introduction paragraph BEFORE any heading" 추가

**테스트 발행**: visa-policy-solomon-islands (`_run_impl()` 직접호출). 로컬 md: lead True / H2 4(허용패턴) / img 4 전부 webp / bold 0 / techpawz 링크 11(visafree cross-sell 발작) / words 1,080 / 제목 클린
**배포**: Hugo 541ms + wrangler deploy --project-name=visa-hugo (etap.yaml:504; visafree-hugo는 :528 별도) → https://3d369202.visa-hugo.pages.dev
**라이브**: HTTP200/31,769B — #2~#5, #7~#12, #14, #15 전부 PASS

**N/A 후보 — 사용자 확인 필요**: #1 affiliate disclosure / #6 product cards. visa 콘텐츠는 투어 상품 데이터 자체가 없어(viator 링크·카드 원천 부재) 발화 조건이 성립하지 않음. partial의 조건부 미표시 = 설계 정상 동작.

**측정 교정안 추가 3건**: (a)`<main>` 추출은 non-greedy 금지(greedy `(.*)` 사용 — non-greedy면 첫 </main>에서 잘림... 실제로는 minify된 단일행이라 greedy 필요) (b)#8은 quoted-href regex 금지 — Hugo minify가 href 따옴표 제거하므로 `techpawz\.com` 문자열 카운트 기준 (c)#15 단어수는 로컬 md 기준 확정(라이브 main words는 렌더 방식 차이로 과소계산)

### F7 airports-hugo — 통과 (2026-08-22)

**기존 포스트 심각 결핍** (lille-airport-lil-guide, 2026-08-16 — 전 패밀리 최고령): 이미지 완전 부재(img 0), disclaimer 부재, lead 부재, cross-sell 본문 0. 픽스 범위가 타 패밀리보다 넓었음.

**픽스 4건 [PRODUCTION CODE]**:
1. airports_writer.py 인트로 우선 규칙 + MINIMUM 단어 규칙("MINIMUM 1,100 words, target 1,200-1,500 … rejected under 1,000. Expand with general travel advice, NOT invented facts")
2. airports_pipeline.py `_add_product_cards`(:133) 직후 cross-sell 블록(base :333-339 클론)
3. **양방향 destinations 쿼리 버그 픽스**: fetch_airport_data가 `WHERE origin=?`(outbound만) 조회 → OAK 등 인바운드 전용 공항이 "데이터 없음" 오판으로 스킵됨 → `CASE WHEN origin=? THEN destination ELSE origin END WHERE origin=? OR destination=?` 교체
4. 풀 일괄 정리: airline_routes에 origin/destination 매칭 전무한 444행 exhausted=1 처리(백업: /tmp/opencode/f7_exhausted_backup.txt). OAK는 픽스 이전 시도로 소진됨

**테스트 발행**: vancouver-international-airport-yvr-guide (YVR) — 로컬 words 1,353/H2 7/imgs 9(webp 7)/techpawz 13/lead True/draft False
**배포**: Hugo 444ms → wrangler pages deploy --project-name=airports-hugo (etap.yaml:56) → 라이브 15항목 전부 통과(og:image R2 webp, H2(main) 8, strong_paras(카드제외) 0, disclaimer, techpawz(main) 13, lead, og:title 클린)

**특이사항**: 이 블로그만 `config/_default/hugo.toml` 구조(루트 hugo.toml 없음). 잔여 풀 = LYS 1개뿐(LOW TOPICS 경고 지속).

### F8 deals-hugo — 통과 (2026-08-23)

**특이 결함: 3개월+ 발행 중단(팬텀 행)** — publish_log 172행 중 디스크 존재 최신=2026-05-06(cheapest-flights-los-angeles-to-hou). 이후 160여 행은 DB에만 존재(쓰기 실패 후 mark_published 무조건 실행되는 구조 탓, etap-republish 스킬 함정표 케이스). → write-fail 가드(multiday_pipeline.py:136-140 패턴) 복제로 차단: `_write_hugo_post` 결과 None/dict success falsy면 return(write_failed), 통과 시에만 _mark_published. visa 파이프라인도 동일 가드 미보유(잔존 위험 기록).

**writer 결함**: 동적 H2 7종 전부 가드 비매칭(Best Deals from X/Budget Flights Under $200/Long-Haul Deals Over/Direct Flight Options/When to Fly/How to Get Best Price → DEMOTE 실측) + 인트로/단어 규칙 부재. → hugo_writer 가드 181패턴 전수 추출(ast.literal_eval—함수 내 지역변수라 import 불가) 후 통과 제목으로 재타이틀: Quick Facts / Current Flight Prices Under $200 / Current Flight Prices $200-$500 / Current Flight Prices Over $500 / Direct vs. Connecting Flights / Money-Saving Tips for X Travelers / Booking Tips + 인트로 우선 규칙 + MINIMUM 1,100 words 규칙.

**pipeline 픽스**: cross-sell 블록 삽입(build_cross_sell_html country/city)+inject_internal_links.

**테스트 발행**: cheapest-flights-los-angeles-to-indianapolis (publish_log 2026-08-23T01:36). 로컬 md: draft False/lead True/H2 6/img6 webp6/**words 1,714**/strong_para 0/techpawz_abs 14/bq 2(시스템 카드)/title 클린/tags 정상. 빌드 265ms→배포 9f9039e1→라이브(HTTP200/37,320B): og:image R2 webp/H2 6/img12 webp8/strong_para 0/disclaimer/techpawz(main) 14/lead True/title 클린. #1 affiliate·#6 cards는 viator/sjv 링크 원천 부재 구조라 **N/A 확정**(마스터 규정과 일치).

**측정 노트 추가**: og:title은 무따옴표 속성 문제로 regex truncation → `<title>` 태그 또는 `property="?og:title"? content="..."` 사용.

### F9 dining-hugo — 통과 (2026-08-23)

**픽스 3건**: ① writer RULES 인트로 우선 규칙 + MINIMUM 1,100 words(기존 1,200-1,800 불릿 대체) ② pipeline :127 직후 cross-sell 클론(import-only였음; write-fail 가드는 원래 보유—팬텀 위험 없음) ③ 시스템 프롬프트 볼드 금지 rule 5 신규 추가("NEVER bold an entire paragraph or write label-style bold leads…max 10 words")

**경위**: 1차 발행(m-dining)은 라이브에서 `<p><strong>Where to eat tonight:</strong></p>` 라벨형 볼드 1개(#5 미달) → rule 5 추가 후 재발행(me-dining)으로 해소. m-dining은 픽스 이전 발행분이라 라벨형 볼드 잔존(잔존 위험).

**검증(me-dining)**: 로컬 md — draft False/lead True/H2 4/img4 webp4/**words 1,515**/bold_paras 0/techpawz_abs 8/title 'Coastal Refinement: A Dining Strategy for ME' 클린/tags 정상. 빌드 305ms→배포 71fc5973→라이브(HTTP200/34,929B): og:image R2 webp/H2(main) 5/img4 webp4/**strong_para(non-card)=0**/techpawz(main) 8/disclaimer/lead/title 클린. #1·#6 N/A 규정 준수.

### F10 esim-hugo — 통과 (2026-08-23)

**픽스 4건**: ① esim_pipeline.py cross-sell 클론(_add_product_cards 직후, country 기반) ② writer 인트로 우선+MINIMUM 1,100 words 규칙(기존 "1,000-1,500" 대체) ③ 시스템 프롬프트 rule 4 볼드 금지 ④ 제목 규칙 확장: `Title must include "{country}" and "eSIM". Title must NOT contain "A Practical Guide"/"A Comprehensive Guide"` — 신규 발행분이 실제로 "A Practical Guide to Moldova eSIM Connectivity" 제목으로 나와 györ 전례대로 발견→픽스. write-fail 가드는 원래 보유.

**테스트 발행**: esim-moldova(publish_log 최신). 로컬 md: draft False/lead True/H2 6/img10 webp6/**words 1,703**/strong_para 0/bold15w 0/techpawz_abs 8/viator·sjv 28(esim 계열은 airalo.pxf.io 카드 링크—rel=sponsored)/bq 3(시스템 카드). 제목 sed 수정 후('Moldova eSIM: Staying Connected for Less') 빌드 666ms→배포 7c777301.

**라이브**(HTTP200/39,980B): og:image R2 webp/h2 7/webp 8/strong_para(non-card) 0/disclaimer/techpawz(main) 8/lead True/title 클린. **#1 affiliate disclosure 발화 확인**('commission' 문구 존재 — partial findRE의 airalo 조건 매칭) + **#6 product cards 1개**(etap-card-title, airalo.pxf.io sponsored 링크) → **15항목 풀 체크 전부 통과**(#13 투어명반복은 투어 없는 콘텐츠라 해당없음).

### F11 flights-hugo — 통과 (2026-08-23)

**구세대 구조**: 파이프라인 파일명 `flight_pipeline.py`(단수), `_run_impl(cfg)` 시그니처(유일), cross-sell import 자체가 없었음, write-fail 가드 없음(무조건 mark_published — 팬텀 위험 구조).

**픽스 5건 [PRODUCTION CODE]**:
1. import 추가: build_cross_sell_html(entity_linker) + insert_cross_sell_block — 초기에 topic_manager에서 import 시도했다가 ImportError(post_processor.py:151가 정위치) 정정
2. inject_internal_links 직후 cross-sell 블록(country="", city=dest_city)
3. write-fail 가드 신규(multiday :136-140 패턴) — 통과 시에만 mark_published
4. flight_writer: 단어 규칙 "MINIMUM 1,100 words, target 1,200-1,600 … rejected under 1,000" (기존 1,200-1,600 MINIMUM 아님 교체) + 볼드 금지 + 제목 금지 규칙("A Practical Guide"/"A Comprehensive Guide")
5. H2 6종은 기존부터 가드 허용 패턴이라 재타이틀 불필요 확인(Current Flight Prices: X to Y 등)

**테스트 발행**: cheapest-flights-sea-to-ont (제목 "Planning a Trip? Cheapest Flights from SEA to ONT Compared" 클린). 로컬 md: draft False/lead True/H2 6/img6 webp6/words 1,588/strong_para 0/techpawz_abs 6. 빌드 513ms→배포 13935799→라이브(HTTP200/35,044B): og:image webp/h2 6/img6 webp6/strong_para 0/disclaimer/techpawz(main) 6/title 클린.

**#1/#6 N/A 후보**: flights 파이프라인엔 product card 시스템 자체가 없고 노선 콘텐츠는 viator/sjv/airalo 제휴링크 원천 부재 → affiliate disclosure 조건부 미발화=시스템 정상. 사용자 승인 필요(F5/F8 전례와 동일 성격).

### F12 michelin-hugo — 통과 (2026-08-23)

**결함 2종(연쇄) → 픽스 2건 [PRODUCTION CODE]**:
1. H2-GUARD allowlist 비매칭: 신규 strict 4-H2 구조("At a Glance/Where to Eat/Compare/FAQ")가 `_ALLOWED_H2_PATTERNS`에 없어 전부 `<strong>` 강등(manchester/lausanne 실측 H2=0) → hugo_writer.py 가드에 4패턴 추가. 근거: `_clean_body()` 단위 실행 → H2 4 유지, 강등 0
2. 볼드 강등 연쇄로 본문 이미지 삽입(`^## ` 위치 기반)도 0건 → 위 픽스로 해소
3. michelin_writer 프롬프트에 OPENING PARAGRAPH 필수 + description 섹션명 금지 규칙 추가 — 1차 테스트발행(marbella)에서 lead 0 + description='At a Glance' 결함 발견 후 적용, 2차 발행(miami-beach)으로 검증

**수동 복구**: manchester/lausanne(`<strong>`→`##` 복원+이미지 2장 삽입, 백업 /tmp/opencode/{slug}.index.md.bak), marbella(리드 인트로+description 보강)

**테스트 발행 2건**: marbella(topic_id=192), miami-beach — 최종 로컬 15항목 4포스트 전부 통과(유효 13항목+N/A 2)
**배포**: Pages 프로젝트 확인(`wrangler deploy`는 Workers 전용으로 실패 → `wrangler pages deploy ./public --project-name=michelin-hugo`) → 라이브 4포스트 h2≥4/img≥2/lead=1 확인

### F13 nomad-hugo — 통과 (2026-08-23)

**식별**: family-map 기준 F13 = nomad-hugo(paused, 39 posts). canggu 디렉터리 빈 폴더(팬텀 행, F8과 동일 패턴) 발견

**결함 4종 → 픽스 5건 [PRODUCTION CODE]**:
1. nomad 동적 H2 7종 중 4종("Internet SIM Cards and Connectivity"/"Cost of Living for Nomads in {city}"/"Visa and Stay Options"/"Neighborhoods and Where to Stay") 가드 비매칭 강등 → hugo_writer 가드에 4패턴 추가(테스트발행 ubud에서 실측 후 픽스·복구)
2. write-fail 가드 부재(무조건 mark_published — canggu 팬텀 원인) → multiday :136-140 패턴 복제
3. cross-sell import-only(호출 코드 없음, F3/F4/F5와 동일) → `_add_product_cards` 직후 build_cross_sell_html+insert_cross_sell_block 추가(country/city 사용)
4. writer 반환 `"tours": []` 하드코딩 → product cards 구조적 불가. airalo_esim SELECT에 price/sale_price/image_link/currency 추가하고 tours를 eSIM 플랜으로 매핑(esim_pipeline :74-90 카드 스키마 차용)
5. nomad_pipeline `_affiliate_link`가 airalo.pxf.io 링크를 Viator 파라미터로 오염 → `.pxf.io/` 포함 시 원본 유지 가드. 단위검증: fetch_data('Ubud','Indonesia') → 5플랜 → 카드 1블록, pxf 링크 무결성 확인
6. nomad_writer 제목 규칙에 완결성 규칙 추가(vilnius 실측 "…Remote Work Haven with…" 말줄임 제목)

**테스트 발행**: ubud-digital-nomad-guide — 로컬 words 1,878/H2 7/img 8/lead/cards/crosssell 전부 통과. 수동 복구 병행(강등 역방향+이미지 3장)
**최신 포스트 수리**: vilnius(말줄임 제목 교체+'Why Vilnius Is a Hidden Gem for Remote Workers', lead 래핑, eSIM 카드 삽입, 크로스셀 3도메인 — 전부 공유 함수 재사용, H2 7/words 1,593)
**배포**: Hugo 203ms → wrangler pages deploy(nomad-hugo) 2회 → 라이브: ubud(h2 8/webp 4/lead/card/pxf 15/disc) · vilnius(h2 8/r2 이미지 jpg 8장 전부 200/lead/card/pxf 13/title 클린)

**측정 노트**: 구세대 포스트는 R2 이미지가 .webp가 아니라 .jpg — 라이브 img 체크는 확장자 무관 r2\.dev 매칭으로
