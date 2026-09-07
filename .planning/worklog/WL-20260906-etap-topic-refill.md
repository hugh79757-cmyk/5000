# WL-20260906 — ETAP 토픽 리필 (토픽 부족 전수조사 후속)

**날짜:** 2026-09-06
**작업 유형:** 파괴적 (travel-en.db 대량 INSERT + 정크 DELETE)
**승인:** 사용자 m0271 — "권장안 실행" (flights 200 / dining 200 / esim 11 / near-low 7종)

## 배경

ETAP 토픽 부족 전수조사(census)에서 LOW(≤10) 4종 + Near-low(≤75) 7종 식별.
`visafree-hugo`는 소스 소진(visa_requirements 199 passport 전부 사용)으로 refill 불가 → 제외.

## 사전 상태 (remaining, get_remaining_count 공식 기준)

| Blog | 사전 remaining | 사후 remaining | 추가 |
|------|--------------|--------------|------|
| flights | **0 (발행 중지)** | 200 | +200 |
| dining | 9 | 97 | +88 |
| esim | 6 | 8 | +2 (신규 소스 한계) |
| citytours | 39 | 126 | +87 |
| nomad | 35 | 115 | +80 |
| multiday | 50 | 98 | +48 |
| nightlife | 49 | 50 | +1 |
| cruise | 57 | 66 | +9 |
| watersports | 68 | 160 | +92 |
| extreme | 73 | 167 | +94 |

INSERT 760행 → 정크 47행 DELETE + esim 중복slug 9행 DELETE → **순증 +704행.**

## 실행 내역

1. **백업:** `data/travel-en.db.bak_topic_refill_20260906211044` (169MB, integrity ok)
2. **INSERT (760행):** `scripts/tmp_topic_refill.py` (실행 후 삭제)
   - flights: flight_prices에서 price≥5건 노선 200개. IATA→도시명은 airports_topics + 수동 hub 매핑(NYC/LON/WAS/YTO/YEA/YMQ/REK/PHX/RIC/SHV). title 6패턴 순환, slug `cheapest-flights-{city}-to-{city}`, priority=50, exhausted=0, unique_data_points='[]'
   - dining: michelin_restaurants 식당≥10 도시 88개(≥10 소스 한계). title `Best Michelin Restaurants in {city}, {country}: Fine Dining Guide`, slug `michelin-{city}-{country}`, priority=min(100, cnt/5)
   - esim: 11 신규 국가. region 수동 매핑(카리브=latin america, MENA=arabia & africa, global=global). priority=min(95, plan_count*5+30)
   - near-low 7종: Viator cats = topic_expander BLOG_CATEGORIES와 동일. ASCII-clean 도시만. title/slug 기존 행 패턴 준수(예: `Best Shore Excursions in {city}: ...`/`{city}-shore-excursions`). priority=50, tour_count=실제 투어수
3. **정크 제거 (47행):** admin code(전대문자 1-3자: NA/RM/B/FI/SA/VE/ME/GR/SS/OT/VV/CRD/GC/HU/SO/TF/BA/PM/BI/A/V/SS 등), Krung Thep Maha Nakhon, El Sayeda Zeinab, Amman Governorate, Improvement District No. 9. County/District/Amphoe는 기존 테이블 관례상 존재(Maui County 18개 등) → 유지
4. **esim 중복slug 9행 DELETE (id 213,215-222):** 기존행(id 62-177, Title Case 표기)과 slug가 대소문자 정규화 후 동일. 기존행은 전부 exhausted=1 발행완료 → 새 행 발행 시 duplicate_slug 위험 → 삭제. 214(Côte d'Ivoire), 223(global international)은 유지
5. **검증:** pick_topic_by_id 실제 호출 10블로그 전부 선택 성공, PRAGMA integrity_check ok, slug 중복 0 (flight/dining/citytours/nightlife/extreme/multiday/cruise/watersports/esim), nomad 기존 중복 43건은 전부 refill 이전 것(97/122/139 id 대역) → 원복 불필요

## 검증 분류

- [검증됨] INSERT 수/remaining 재계산 — `get_remaining_count` 공식(똑같은 SQL)으로 사전/사후 대조. 산출 근거: 760 = flights 200 + dining 88 + esim 11 + citytours 100 + nomad 100 + multiday 50 + nightlife 1 + cruise 10 + watersports 100 + extreme 100. 704 = 760 − 47(정크) − 9(esim 중복)
- [검증됨] pick_topic_by_id 10블로그 실제 선택 성공 — flights "Planning a Trip? Cheapest Flights from New York to Orlando", dining "Best Michelin Restaurants in Oakland, USA", esim "Best eSIM Plans for Bosnia and Herzegovina", citytours "Calcasieu Parish City Tours", nomad "Digital Nomad Guide to Valletta", multiday "Best Multi-Day Tours From Cat Hai", nightlife "Evening Entertainment Guide to Koh Samui", cruise "Best Shore Excursions in Cyclades", watersports "Water Sports and Boat Tours in Cozumel", extreme "Outdoor Activities in La Fortuna"
- [검증됨] 무결성 — PRAGMA integrity_check = ok (refill 전후 + DELETE 후 3회)
- [검증됨] slug 중복 0 — 9개 테이블 GROUP BY slug HAVING COUNT(*)>1 = 0 (nomad 기존 중복은 refill 이전 존재분)
- [부분검증] 다음 스케줄 발행 성공 여부 — remaining 계산·토픽 선택은 검증했으나 실제 발행(5개/일/블로그)은 미래 이벤트. 제한 사유: 발행은 스케줄러가 수행
- [부분검증] flights 토픽 품질 — flight_prices에 price 데이터 존재 확인했으나 price 데이터가 발행 시점에 유효한지(expires_at)는 미검증. flight_writer가 'Do NOT invent prices' rule 준수 가정

## 잔존 위험

- **nomad 기존 slug 중복 43건** (tbilisi-digital-nomad-guide 4개 등): refill 이전부터 존재. exhausted 되지 않은 중복이 있으면 duplicate_slug 에러 가능 → 모니터링 필요. 원복 불필요(내 작업 아님)
- **nightlife 거의 소진 (50)**: Viator 후보가 District of Columbia 1개뿐 — 다음 refill 시점에 재소진 예상. 대응: nightlife BLOG_CATEGORIES cats 확장 필요(예: Dinner Cruises, Live Music 등)
- **cruise 후보 부족 (+9)**: Viator cats 한계. cruise cats 확장 필요
- **esim 신규 소스 한계 (+2)**: airalo_esim 외 신규 국가 소스 부재. global/combo 상품군 카테고리 신설 필요
- **flights 노선 확장**: flight_prices 716 노선 중 493이 price≥5건 — 200만 사용. 잔여 293개는 추후 추가 가능
- **dining ≥10 도시 소진 (+88)**: 식당 5-9개 도시 253개가 잔여 소스. 추후 threshold 완화 필요
- **visafree refill 불가**: 소스 자체 소진. 근본 대응은 visa 데이터 수집기 신설 필요

## 스크립트 폐기

`scripts/tmp_refill_precount.py`, `scripts/tmp_topic_refill.py`, `scripts/tmp_junk_cleanup.py` — 검증 완료 후 삭제. 재필요시 이 worklog + 백업으로 재현 가능.
