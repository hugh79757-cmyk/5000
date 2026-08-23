# WL-20260815-phase71g-dining-city-recovery

- 날짜: 2026-08-15
- 태그: phase-71g-dining-cities-1(작업1 별칭), phase-71g-dining-cities-2(작업1 no_source)
- 성격: 작업0(read-only 분류) + 작업1(코드 additive, no_source 노출) + 작업2(read-only 판정) — DB 무변경
- 로그: logs/destructive_2026-08-15.log 한 줄 append

## 작업0 — dining city 미매칭 분류 (read-only)

- 감사: active dining_topics 83건 중 zero-stock 도시 **49건** (작업 지시 "24건"과
  불일치 — 전량 분류). 4 자동 / 19 소스없어 / 26 사람결정.

## 작업1a — 자동 4건 별칭 정규화 (대표 승인)

- Rīga→Riga(27), Los Angeles County→Los Angeles(87), Merseyside→Liverpool(7),
  Nevşehir Merkez→Nevşehir(9). CITY_ALIAS_FALLBACK 코드 폴백, country 하드 게이트,
  NFD 폴딩. [phase-71g-dining-cities-1]

## 작업1b — no_source 19건 노출 (data_stock, additive, 대표 승인)

- DINING_NO_SOURCE 19건 → depletion_reason=no_source. check_data_stock에
  depletion_reason/depletion_cities + detail 마커 주입 (판정 불변 — dining-hugo pass 유지).
- db.py registry pass/fail evidence에 no_source 블로그 additive 병기.
- 자동 재큐·생성 트리거 없음 (소스 부재). [phase-71g-dining-cities-2]

## 작업2 — 26건 하위 분류 판정 (read-only, 비자동, 임의 매핑 금지)

### 행정코드 10건 — 대표도시 매핑 확정 시 자동복구 가능 여부
- OV/WV(BE): 후보 대표도시(Oostende/Gent/Kortrijk, Brugge…) source 존재 → **매핑 확정 시 자동복구 가능**
- MO/PU/SR/TN/TP(IT): Modena/Pesaro/Sassari/Trento/Trapani 존재 → 가능
- PT(IT): Prato 존재, Pistoia 부재 → 확정 시 가능 (Prato 채택)
- SI(IT): Siena source 부재 → **매핑 확정해도 source 미존재 → 자동복구 불가**
- V(ES): Valencia/Vigo/Valladolid 존재 → 가능
- ※ 행정코드→대표도시 의미 자체는 대표 결정 필요 (임의 매핑 금지)

### 국가내 매칭 미확정 16건 — 국가 michelin 데이터 + 후보 도시
- Greece(전체 Athens 1개뿐): Myrthianos/Nafplio/Nea Smirni/Paleo Faliro/Thronos/
  Tourlos 모두 후보 없음 → **소스 부재, 자동복구 불가** (6건)
- Finland(4개:Helsinki/Porvoo/Tampere/Turku): Levi 후보 없음 → 불가
- Portugal(68개, Lamego 부재): 불가
- Thailand(17개, Krabi 도시명 부재): Mueang Krabi/Thailand(국가명) 후보 없음 → 불가
- Mexico(28개): Nayarit/Quintana Roo 주(州)명 후보 없음 → 불가
- US(244개): Maryland/Maui/Mecklenburg/Waldo County 주단위·군단위 → 카운티 대표
  도시 매칭은 임의성이 높음 → **대표 결정 필요, 자동복구 불가**

## 검증
- 작업1b: 실DB 19/19 no_source 감지, dining-hugo status pass 유지, 회귀 27실패
  동일(신규0) → [검증됨]
- 작업2: read-only 판정만 — 코드 변경 없음, 임의 매핑 미적용 [검증됨]

## 잔존 위험
- 행정코드 10건 매핑(SI 등) 및 16건 국가내 매칭은 대표 결정 대기 — 자동 복구 미적용.
- 작업 지시 "24건" vs 실측 "49건" 갭 — 전량 분류로 해소, 보고로 명시.