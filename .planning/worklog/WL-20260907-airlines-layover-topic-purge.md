# WL-20260907 — airlines/layover 가짜·데이터0 토픽 정화 (P02 연속실패 해결)

**날짜:** 2026-09-07
**작업 유형:** 파괴적 (travel-en.db DELETE/UPDATE/INSERT)
**트리거:** 09-07 오전 alert — airlines-hugo + layover-hugo pipeline_returned_false 연속 실패 (P02)

## 원인 요약

### airlines-hugo
- `airlines_topics` remaining 283개가 전부 synthetic 가짜 항공사 (`Aero {Country} {code} Airways` — ref_airlines의 iata 오인 기반 생성)
- airlines_writer `fetch_airline_data()`가 routes/directs/monthly 합산 < 3건 → `데이터 부족 스킵` → exhausted 처리 → 다음 가짜 → 무한 반복 → CATCHUP 3회 소진 → P02

### layover-hugo
- remaining 150개 중 100개 도시가 viator_tours 데이터 0건 (공항명 junk 33 + 표기 변형 + 데이터 부재)
- layover_writer `fetch_tours()`가 `city = ?` 정확 매칭 (+city_aliases 조인) → 0건 → exhausted → 반복 실패

## 실행 내역 (4단계 프로토콜 준수)

1. **백업:** `data/travel-en.db.bak_airlines_layover_20260907104717`
2. **airlines:** 가짜 296행 DELETE (`airline_name LIKE 'Aero %' AND '% Airways'` — 진짜 Aero Dili/Mongolia 등 6행은 형태 달라 무사) + exhausted+미발행+실데이터 보유 26행 exhausted=0 리셋 (데이터 소스: airline_routes/flight_direct/flight_monthly/flight_calendar/popular_directions 5테이블 EXISTS)
3. **layover:** 데이터 0개 도시 111행 DELETE (공항명/표기 변형 97 + category 불일치 13 + Sete 정크 category 1) + city_aliases 3행 방향 교정 (canonical=토픽명 악센트 표기, alias=viator ASCII명 — 최초 INSERT 방향 반대였어서 교정)
4. **검증:** fetch_tours remaining 39 도시 전부 > 0건 (0건 도시 0개), airlines pick→generate 성공 (Westjet 리뷰 생성), integrity ok 2회

## 결과

| Blog | 사전 remaining | 사후 remaining | 성질 |
|------|--------------|--------------|------|
| airlines | 283 (전부 가짜) | 26 (전부 실데이터) | 발행 재개 |
| layover | 150 (100개 데이터0) | 39 (전부 실데이터) | 발행 재개 |

## 검증 분류

- [검증됨] 가짜 식별 — `Aero %` + `Airways` 패턴 296행 전부 synthetic (iata_code가 DF=Condor 오인 등 실존 코드 재조합). 진짜 Aero 6행(Aero Dili/Aero Mongolia/Aero K 등)은 형태 상이하여 무사 확인
- [검증됨] layover 정화 후 remaining 39도시 fetch_tours 전부 >0건 — writer 실코드 경로 재현 (Belfast 7건 등)
- [검증됨] airlines 리셋 26행 — 5테이블 EXISTS 데이터 보유 확인 후 리셋. pick→generate_airline_review(Westjet) 실코드 성공
- [검증됨] integrity_check ok 2회 (실행 직후 + 최종)
- [부분검증] 다음 스케줄 발행 성공 — remaining 계산·pick·fetch·generate는 검증했으나 실제 발행(_write_hugo_post → 배포)은 미래 이벤트. 제한 사유: 스케줄러가 수행

## 잔존 위험

- airlines remaining 26 (5개/일 → ~5일). 추가 소스: airline_routes 21 항공사 중 미발행 iata는 airlines_topics 재생성 필요 (추후 진짜 ref_airlines 기반 재생성 스크립트 검토)
- layover remaining 39 (~8일). 신규 도시 보충은 topic_expander가 자동 (layover는 city 스키마 — MIN_THRESHOLD=30 미만이면 05:10 자동 채움... 39 > 30이므로 이번엔 자동 안 채움. 소진 시 자동 보충)
- airlines_topics 원래 가짜 생성 경로 (누가 만들었는지) 미추적 — 재발 방지를 위해선 생성 스크립트 원천 확인 필요. ref_airlines 정상 1,150행이므로 topics 생성 시 iata 유효성 검증 부재 추정
- layover 공항명 토픽 생성 경로도 미추적 — 동일 추정

## 후속 작업 (2026-09-07 오후 — 동일 worklog에 추가)

### 가짜 발행기록 publish_log 정화 [DESTRUCTIVE]
- 대상: topic_id 1038-1050 (13행, Aero Korea DF 등 `Aero {Country} {code} Airways` 패턴). 이들 발행기록과 실제 글 content/posts 0개, 라이브 404 — mark_published_by_id() (topic_manager.py:257)가 데이터 부족 exhausted 처리 시에도 publish_log INSERT하는 설계로 인한 **로그 오염** (실발행 아님).
- 사용자 승인 후 DELETE. 사전 14행 → 13행 DELETE (나머지 1행은 패턴 불일치) → 재검색 0건, 총발행 461→448, integrity ok. 백업: bak_airlines_layover_20260907104717.
- 실존 항공사 6건(Flying Safi/Thomson/Jazeera 등 패턴 우연 매칭)은 정상 발행 — 유지.

### 항공권 제휴 CTA 구현 [PRODUCTION CODE]
- 조사 결과: airlines-hugo 기존 글 제휴 링크 0개 — `_add_product_cards`가 `city LIKE '%IATA%'`로 viator 검색 (도시명≠IATA코드라 매칭 불가 설계 버그).
- 수정: `pipelines/etap/airlines_pipeline.py` `_add_product_cards()` 전면 교체. TRAVELPAYOUTS_MARKER(env) 확인 → 허브 탐색(airline_routes→flight_direct→flight_calendar 폴백) → flight_prices 허브 출발 최저가 3노선 → jetradar searches/new 링크(dep_date=오늘+30일) → insert_product_cards(card_title='Flight Deals from {hub}', btn_text='Search Flights').
- `pipelines/etap/post_processor.py` insert_product_cards() additive 파라미터 2개 추가: card_title(기본 'Top Tours & Activities'), btn_text(기본 'Book Now'). 기존 호출자 45곳 전부 위치인자 → 무영향.
- 마커 없으면 카드 생략(fail-safe), 가격은 DB 실존값만.
- 스킬 생성: `/Users/twinssn/.config/opencode/skills/travelpayouts-affiliate-links/SKILL.md` (env 위치 ~/.env.common 78-79행, jetradar/aviasales 링크 포맷, 날짜 규칙, 마크업 표준).
- 검증 [검증됨]: Westjet 실코드 재현 — 카드 3개, 'Flight Deals from Los Angeles' 헤더, jetradar 링크 6회(LAX→LAS $28), marker=513970, 'Search Flights' 버튼, rel="sponsored noopener", From $28 (flight_prices 실존). py_compile etap 37파일 전부 OK. 기존 테스트 2 실패(preflight_c01/skeleton)는 git stash 재현으로 pre-existing 확정 (내 변경 아님).

## 룩북 매뉴얼 없는 신규 실패 클래스 (사용자 별도 보고 요청분)

1. **pipeline_returned_false + 토픽 데이터 오염** (airlines): 토픽 테이블에 가짜 synthetic 행 존재 → writer 데이터 부족 → exhausted 처리 무한 반복. 매뉴얼 부재. 룩북 대응: 토픽 데이터 원천 검증 체커 필요
2. **pipeline_returned_false + 토픽 데이터 부재** (layover): 토픽 도시가 실제 데이터 테이블에 없음 (공항명/표기변형). 매뉴얼 부재. 룩북 대응: pick 전 fetch 사전 검증 로직 필요
3. 공통: dispatcher `pipeline_returned_false`가 `unknown failure reason`으로 Telegram 발송 생략 (dispatcher.py:2091) — 원인 불명 경보가 안 옴
