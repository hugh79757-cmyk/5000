# G1_READINESS — pick-hugo 감사 (배치 3 선행 필수)

**작성일**: 2026-09-18  
**대상**: pick-hugo (car 파이프라인, daily_quota=1, owner=mac→runner 이관 예정)  
**상태**: 읽기 전용 감사 — flip/커밋 금지  

---

## 1. 가드 시뮬레이션 (14/30/90일) — 실측값 반영

### 1.1 가드 계층 요약 (파이프라인 코드 기준)

| 가드 | 윈도우 | 코드 위치 | 동작 |
|------|--------|-----------|------|
| **recent_keys** (14일) | 14일 | `pipeline.py:128` `days_window=14` | 동일 car_id:competitor 조합 14일 내 발행 시 선택 제외 |
| **중복 사전체크** (30일) | 30일 | `pipeline.py:147-157` | 30일 내 발행된 car_id → skip_duplicate 마킹 + 회전 |
| **콤보 차단** (90일) | 90일 | `topic_manager.py:45-59` | stap_content.db articles 90일 내 (blog_id, car_id, post_type) 조합 사전 제외 |
| **콤보 차단** (30일 무조건) | 30일 | `topic_manager.py:53-57` | post_type 무관, 30일 내 발행된 car_id 전면 제외 (publisher 가드#2 정합) |

### 1.2 시뮬레이션 결과 (2026-09-18 기준, pick-hugo) — **실측**

```sql
-- car.db topics 상태 (site_id='pick')
persona_pick: pending=39, published=157, skip_duplicate=13, skip_no_data=23  (총 232)

-- car.db publish_log (site='pick') 총 166건, 최근 30일 내 ~30건 (일 1건 페이스)
```

| 윈도우 | 실측 차단 car_id 수 | 비고 |
|--------|-------------------|------|
| **14일** | **6개** | recent_keys (car_id:competitor 조합 기준) |
| **30일** | **21개** | combo 30일 무조건 차단 (publisher 가드#2 정합) |
| **90일** | **33개** | combo 90일 차단 (stap_content.db articles 기준) |

**합산 차단 car_id**: 33개 (중복 제거 후)  
**전체 토픽 car_id**: 135개  
**유효 풀 (차단 후)**: **102개** car_id  
**usable_pending (시판 trim + 30/90일 가드 후)**: **20개** — `daily_refresh.py:468` 기준  

> **핵심 수정**: 기존 추정(~10-15건) → **실측 20개 usable_pending**. quota=1로 일 1건 소진 시 **20일분 커버리지**. 여전히 여유분 부족(≥30 필요) → 토픽 보충 필수.

### 1.3 풀 고갈 완화 현황

- `topic_manager.py:67-73` — 미사용 콤보(pending + 30일+ 경과 published) **우선 선택**, 소진 후 재사용 폴백
- `pipeline.py:230-233` — 신규 타입(persona_pick) 실패 시 `skip_no_data`로 마킹 **않고** pending 유지 → 재시도 가능
- `pipeline.py:154-157` — 30일 중복 감지 시 `skip_duplicate` 마킹 + `status` 업데이트 (영구 차단 아님, 풀 순환용)
- `daily_refresh.py:389-488` `replenish_topics()` — min_pending=50 미만 시 자동 보충 (pick은 usable=20 → 보충 대상)

---

## 2. 토픽 풀 현황 (pick-hugo 전용) — 7블로그 교차표 포함

### 2.1 pick-hugo 단일

| 지표 | 값 | 비고 |
|------|-----|------|
| 전체 토픽 수 | 232 | car.db topics site_id='pick' |
| post_type | persona_pick 단일 | cap.yaml post_type: "persona_pick" |
| pending (raw) | 39 | 즉시 선택 가능 후보 |
| **usable_pending (시판 trim + 가드 후)** | **20** | daily_refresh.py:468 기준 — **min_pending=50 미달** |
| published | 157 | 30/90일 가드에서 재사용 폴백 대상 |
| skip_duplicate | 13 | 30일 중복 차단 이력 |
| skip_no_data | 23 | 과거 기존 타입 누적분 (신규 타입은 pending 유지) |

### 2.2 7블로그 post_type별 usable_pending 교차표 (보완 3 반영)

| 블로그 (site_id) | post_type | raw_pending | usable_pending | published | min_pending 미달 여부 |
|------------------|-----------|-------------|----------------|-----------|----------------------|
| hotissue | resale_compare | 48 | **28** | 427 | ✅ 미달 (보충 대상) |
| tco | tco_analysis | 129 | **129** | 300 | ❌ 충족 |
| rank | top5_rank | 63 | **38** | 201 | ✅ 미달 (보충 대상) |
| **pick** | **persona_pick** | **39** | **20** | **157** | **✅ 미달 (보충 대상)** |
| deal | promo_deal | 112 | **112** | 303 | ❌ 충족 |
| compare | ranking_compare | 55 | **26** | 606 | ✅ 미달 (보충 대상) |
| guide | beginner_guide | 79 | **79** | 297 | ❌ 충족 |
| ev | ev_analysis | 56 | **12** | 193 | ✅ 미달 (보충 대상) |

> **보완 3 결론**: `replenish_topics()` 세그먼트(`SITE_POST_TYPE` 매핑)는 8개 블로그 전 post_type을 커버. **pick-hugo persona_pick 포함**. 단, usable_pending 20개로 min_pending=50 미달 → daily_refresh가 자동 보충 예정. **수동 30건 주입은 폴백으로 강등**, 세그먼트 보충이 주 대응.

---

## Appendix B. Per-post_type 연비 게이트 파일·라인 인용 (E-1 정정 2 반영)

**G1_READINESS 고정용** — E-1 표의 연비게이트 칼럼 근거 코드 증거.

| post_type | 대상 블로그 | 빌드 함수 | 연비 게이트 | 파일·라인 | 동작 |
|-----------|------------|-----------|------------|-----------|------|
| ranking_compare | compare-hugo | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| promo_deal | deal-hugo | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| ev_analysis | ev-hugo | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| beginner_guide | guide-hugo | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| resale_compare | hotissue-hugo | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| tco_analysis | tco-hugo, hotissue-hugo | build_input | **차단 (Y)** | data_builder.py:396-401 | fuel_eff 없으면 return None |
| persona_pick | pick-hugo | build_persona_pick_input → persona_pick_eligibility | **차단 (Y)** | data_builder.py:739-743 | fuel_eff 없으면 return False, "no_fuel_efficiency" |
| top5_rank | rank-hugo, ev-hugo | build_top5_rank_input | **폴백 (N)** | data_builder.py:543-550 | 연료타입별 기본값 사용 (전기 4.5, 하이브리드 16, 디젤 14, 가솔린 12) |

> **핵심**: `promo_deal`·`beginner_guide`의 연비 요구는 `build_input` 경로(data_builder.py:396-401)로 인해 실제 적용됨 — 라이브 no_data와 정합. `top5_rank`만 폴백으로 차단 회피.

---

## 3. W5 이미지 커버리지 (pipeline.py:39 `verified=1` 기준) — **보완 1 완료**

### 3.1 quality.db article_quality 현황

```sql
SELECT * FROM article_quality WHERE blog_id='pick-hugo';  -- 0건
```

**결과**: **W5 이미지 커버리지 데이터 없음** (quality.db에 pick-hugo 레코드 0건)  
**코드 확인**: `pipelines/car/pipeline.py:39,53` — `_select_car_image`가 `car_images.verified=1`만 사용. **quality.db를 읽지 않음**. → quality.db 0건은 **비이슈**로 기록.

### 3.2 유효 풀 car_id별 car_images verified=1 실측 (보완 1-1~3)

> **게이트 기준**: **유효 풀 car_id 100%가 verified=1 이미지 1개 이상 보유** (pipeline이 `verified=1` 필터로만 이미지 선택하므로)

| 구분 | car_id 수 | 비율 |
|------|-----------|------|
| 전체 토픽 car_id | 135 | - |
| 차단 후 유효 풀 | 102 | - |
| **유효 풀 중 verified=1 보유** | **95** | **93.1%** |
| 미보유 (verified=0) | 7 | 6.9% |

**미보유 car_id (7개)**: `audi_a3_2026`, `genesis_____gv70_2027`, `k8_2027`, `kona_2027`, `renault___2027`, `renault______2027`, `volvo_ex90_2026`

> **W5 게이트 상태**: ❌ **미충족** (100% 미달). 7개 car_id 이미지 검증 필요 → `verify_car_images` 실행 후 보충.

---

## 4. 발행 이력 + daily_quota=1 슬롯 커버리지 — **보완 2 재검증 완료**

### 4.1 발행 이력 — **articles 테이블 위치 정정**

| 소스 | 테이블 | 건수 | 기간 | 비고 |
|------|--------|------|------|------|
| car.db | publish_log (site='pick') | 166 | 2026-04-16 ~ 2026-09-10 | 매일 1건 페이스 확인 |
| content.db | publish_ledger (blog_id='pick-hugo') | 596 | 2026-04-16 ~ 2026-09-10 | source=cap 135건(~8/5), source='' 452건 |
| **stap_content.db** | **articles (blog_id='pick-hugo')** | **125** | **2026-04-25 ~ 2026-09-10** | **data_source=car_db 125건, 최신 9/10** |

> **보완 2 판정**: **허위경보 해소**. `content.db`의 `articles` 테이블이 아니라 **`stap_content.db`**의 `articles` 테이블이 실발행 원장 (shared/db_paths.py:14 `ARTICLES_DB = stap_content.db`). publisher.py `insert_article()`이 stap_content.db에 기록함 (content_store.py:62). 9월 발행분 정상 반영됨.  
> **작성 주체**: `shared/publisher.py:960` `insert_article(article)` → `shared/content_store.py:62` `insert_article()` → `stap_content.db`. `ledger_sync.py`는 별도 경로로 `content.db` `publish_ledger` 동기화 (source=cap 마지막 8/5 정지 → 별도 이슈).

### 4.2 슬롯 구조 (daily_quota=1) — **보완 4-3 확인**

| 항목 | 값 | 검증 |
|------|-----|------|
| 일일 슬롯 수 | 1 | cap.yaml 확인 |
| 슬롯 시각 | 06:55 +07 (23:55 UTC) | cap.yaml `times: ['06:55']` |
| cron | `55 23 * * *` (UTC) | kst_to_cron 변환 |
| tco 23:30 UTC 이격 | **25분** | ≥10분 **충족** |
| daily_refresh 00:00 UTC 인접 | **5분** | 직렬화 수용 (순서: pick 발행 → daily_refresh 보충) |
| 클러스터 위험 | 1 | 단일 슬롯 |

### 4.3 슬롯당 발행 상한/커버리지 분석

```
일일 발행 상한 = daily_quota = 1건
주간 발행 상한 = 7건
월간 발행 상한 = 30건
```

**현재 페이스**: 일 1건 유지 (publish_log 166건 / 5개월 ≈ 일 1건)  
**usable_pending 20개** → **20일분 커버리지** (기존 추정 10-15일보다 양호하나 여전히 ≥30 필요)  
**batch 3 flip 후**: 동일 구조 유지 (quota 변경 없음)

---

## 5. skip_no_data / duplicate 이력

### 5.1 skip_no_data (23건)

| 구분 | 건수 | 추정 원인 |
|------|------|-----------|
| persona_pick | 23 | `build_persona_pick_input` 데이터 없음 (페르소나 매칭 실패 또는 가격 조회 실패) |

**현황**: `pipeline.py:199-216` — persona_pick 실패 시 `top5_rank` 폴백 시도. 폴백도 실패 시에만 `skip_ids` 추가 후 continue (pending 유지). **실제 skip_no_data 마킹은 기존 타입에서만 발생**.  
**결론**: 현재 23건은 과거 기존 타입 시절 누적분. 신규 타입 전환 후 `skip_no_data` 신규 발생 **감소 추세**.

### 5.2 duplicate 이력

| 소스 | 구분 | 건수 | 기간 |
|------|------|------|------|
| car.db topics | skip_duplicate | 13 | 30일 중복 차단 마킹 |
| content.db publish_ledger | duplicate_source_id | 8+ | 2026-08-22 ~ 2026-08-25 집중 |
| content.db publish_ledger | deploy (실발행 아님) | 6+ | 2026-08-23 ~ 2026-08-26 |

**분석**: 8월 22-25일경 `duplicate_source_id` 다발 → **publisher 가드(30일/90일) 작동 확인**. 이후 9월 들어 duplicate_source_id 0건 → **가드 정합성 확보**.  
**runner 이관 후 영향**: owner=runner 전환 시 동일 가드 적용 (stap_content.db articles 조회 기준 동일). 중복 차단 로직 변경 불필요.

---

## 6. 종합 리스크 평가 (갱신)

| 리스크 영역 | 등급 | 내용 | 완화 방안 |
|------------|------|------|-----------|
| **풀 고갈 (usable_pending 20 < 30)** | 🔴 **높음** | quota=1, usable_pending=20 → 20일 고갈 | `replenish_topics()` 자동 보충 작동 확인, 필요 시 수동 보충 |
| **이미지 커버리지 93.1% (<100%)** | 🟡 **중간** | 유효 풀 7개 car_id 미검증 | `verify_car_images` 실행, 7개 car_id 이미지 보강 |
| **articles 동기화** | 🟢 **해소** | stap_content.db articles 최신 반영 확인 (허위경보) | ledger_sync(content.db publish_ledger) 별도 점검 |
| **duplicate 가드 과민** | 🟢 **낮음** | 9월 이후 duplicate_source_id 0건, 가드 정상 | 현행 유지 |
| **runner 이관 호환성** | 🟢 **낮음** | 가드 로직 stap_content.db 기준 동일 적용 | 검증 후 flip 진행 |

---

## 7. 배치 3 Flip 전 선행 조치 (필수) — 갱신

| 순서 | 작업 | 담당 | 비고 |
|------|------|------|------|
| 1 | `verify_car_images` 실행 → 7개 미검증 car_id 이미지 검증/보충 | 자동 | W5 게이트 100% 통과용 |
| 2 | 토픽 풀 보강: `replenish_topics()` 자동 보충 작동 확인 (pick usable_pending ≥30 달성 시까지) | 자동/관측 | 30일 커버리지 확보 — 수동 주입은 폴백 |
| 3 | `ledger_sync.py` 실행 → content.db publish_ledger 동기화 복구 (source=cap 8/5 정지) | 자동 | 9월 발행분 반영 |
| 4 | 가드 시뮬레이션 재실행 (보강 후) → usable_pending ≥30 확인 | 자동 | flip 승인 게이트 |
| 5 | batch 2 (ev/guide/hotissue) 4/4 실증 완료 확인 | 관측 | 선행 배치 검증 |

---

## 8. 승인 게이트 (Flip 실행 조건) — **보완 4 확정본**

```
[ ] W5: 유효 풀 car_id 100% verified=1 (실측 93.1% → 7개 보충 후 100%)
[ ] 토픽 풀: usable_pending ≥30 '자가 유지' 확인 (replenish_topics 세그먼트 보충 시뮬 증빙)
[ ] articles 동기화: stap_content.db 최신 반영 확인 완료 (허위경보 해소)
[ ] content.db publish_ledger 동기화 복구 (ledger_sync 실행)
[ ] batch 2 4/4 발행 레그 실증 완료
[ ] 사용자 승인 (AA-3 probe 초록 + 사용자 진행 신호 + 배치 2 실증 보고 수신 후)
```

---

## Appendix A. 기록 정합 확인 (보완 4)

| 항목 | 상태 | 비고 |
|------|------|------|
| 배치 구성 | **확정** | G1-DESIGN.md 배치표 기준: batch1=compare/deal, batch2=ev/guide/hotissue, batch3=rank/pick |
| 게이트 기준 | **통일** | W5 100%(유효 풀), usable_pending ≥30, articles stap_content.db 최신 |
| pick 슬롯 | **확인** | 06:55 +07 (23:55 UTC), tco 23:30 UTC와 25분 이격(≥10분 충족), daily_refresh 00:00 UTC와 5분 인접(직렬화 수용) |

---

*본 문서는 읽기 전용 감사 산출물. Flip/커밋 작업 금지. 배치 3 flip 직전 재실행하여 최신 상태 반영 필요.*
---

## 9. G4 READINESS — Senior (stock + senior 그룹) 이관 전제 갱신 (2026-09-19)

### 9.1 Senior 파이프라인 신규 데이터 소스 (복지로 전환)

| 항목 | 상세 | file:line |
|------|------|-----------|
| **데이터 소스** | gov24 혜택 API (유지) + 복지로 지자체/중앙 API (신규) | pipelines/senior/fetcher.py:15-18, 20-21 |
| **지자체 API** | `http://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations/LcgvWelfarelist` | fetcher.py:20 |
| **중앙 API** | `http://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001` (srchKeyCode=003, callTp=L) | fetcher.py:21 |
| **인증** | DATA_GO_KR_API_KEY (Header/Query param) | fetcher.py:14 |
| **데이터 포맷** | XML (ElementTree 파싱) | fetcher.py:142-143, 180-181 |
| **수집 결과** | 지자체 426건 + 중앙 16건 = **442건** 시니어 전용 서비스 | fetcher.py:227-228 |
| **노인일자리 API** | `sjfd100` 폐기 → `fetch_senior_jobs()` 빈 리스트 반환 | fetcher.py:230-233 |

### 9.2 필터링 로직 — `is_senior_service()` 5단계 판별 (fetcher.py:26-120)

| 단계 | 판별 기준 | 우선순위 |
|------|-----------|----------|
| 1 | 서비스명에 명시적 시니어 키워드 (`노인`, `어르신`, `경로`, `장수수당`, `기초연금`, `장기요양`, `틀니`, `임플란트` 등) | 최우선 |
| 2 | 대상자(trgterIndvdlNmArray)에 명시적 시니어 조건 (`노인`, `어르신`, `65세`, `70세`, `기초연금수급`, `경로우대`, `만 65세 이상`) | 높음 |
| 3 | lifeNmArray가 "노년"/"고령" 단독이거나 마지막에 오는 경우 + 서비스명/대상에 시니어 키워드 | 중간 |
| 4 | intrsThemaArray가 명시적 시니어 테마 (`노인복지`, `노인일자리`, `경로당`, `장기요양`, `치매관리`, `기초연금`, `노인돌봄`, `노인맞춤돌봄`) + 서비스명/대상 키워드 | 중간 |
| 5 | servDgst에 명시적 시니어 표현 + 서비스명/대상 키워드 보조 | 보조 |

**수집 실적**: 지자체 10페이지(500건씩) 중 426건 + 중앙 1페이지(461건) 중 16건 = **442건** 정밀 필터링

### 9.3 수집 DB & Round-trip 대상

| DB | 경로 | 용도 |
|----|------|------|
| **senior.db** | `shared/db.py:get_db_path("senior")` → `data/senior.db` | 서비스 원장 (services 테이블) |
| **content.db** | `shared/db.py:ARTICLES_DB` → `data/stap_content.db` | 발행 원장 (articles 테이블, source=gov24_api) |
| **car.db** | 미사용 (시니어 파이프라인 독립) | — |

**Round-trip 경로**: R2 `5000-state` 버킷 → 로컬 `data/` 복원 → fetcher 수집 → senior.db 저장 → 발행 시 senior.db 조회 → content_store.insert_article() → stap_content.db articles 기록

### 9.4 러너 환경 호환성

| 의존성 | 버전/비고 | 비고 |
|--------|-----------|------|
| **requests** | 2.31+ | gov24/복지로 API HTTP 호출 |
| **xml.etree.ElementTree** | 표준 라이브러리 | 복지로 XML 파싱 |
| **requests/urllib** | 표준/서드파티 | gov24 API 호출 (ODCloud) |
| **sqlite3** | 표준 라이브러리 | senior.db CRUD |
| **lxml** | 불필요 | ElementTree 사용 |

**러너 도커/환경**: 별도 시스템 패키지 불필요 (Python 표준 라이브러리 + requests만 필요). 기존 5000 러너 환경과 100% 호환.

### 9.5 키/인증 요구사항

| 키 | 용도 | 필수 여부 |
|----|------|-----------|
| **DATA_GO_KR_API_KEY** | gov24(혜택) + 복지로(지자체/중앙) API | **필수** |
| NAVER_CLIENT_ID/SECRET | 네이버 블로그 보강 (선택) | 선택 |

### 9.6 G4 이관 게이트 반영

> Senior 파이프라인은 G4(stock + senior) 그룹에 속하며, M-2 READINESS에서 "이관이 신규 소스(복지로/혜택)를 정확히 재현하는지"가 게이트 기준.

| 게이트 항목 | 상태 | 비고 |
|------------|------|------|
| 신규 엔드포인트 재현 | ✅ 완료 | fetcher.py:20-21, 140-230 |
| 키/인증 정확히 적용 | ✅ 완료 | DATA_GO_KR_API_KEY 단일 키로 3개 API 커버 |
| 수집 DB round-trip | ✅ 호환 | senior.db + stap_content.db 경로 공유 |
| 러너 호환성 | ✅ 확인 | requests + ElementTree만 사용, 추가 의존성 없음 |
| 신규 키 적용 | ✅ 적용됨 | 1a7bd07dda3f66dcfdc0101f19cebda907cf5a3aecae7f6dc43cd89d4c3912d9 |

---

### 10. STAP 배포 경로 통합 — 인라인 wrangler 금지 (ST-3, 2026-09-21)

> STAP(shared/publisher.py)는 5000의 dispatcher.py/deploy.py와 별도 경로로 wrangler를 호출했으나,
> CLOUDFLARE_API_TOKEN 환경변수 충돌(STRUCT-02)로 인해 인증 실패가 반복됨. ST-1 수정으로
> 동일 패턴(env strip + --profile hugh79757)을 적용했으나, 근본 해결은 **단일 배포 경로** 원칙.

| 게이트 항목 | 상태 | 비고 |
|------------|------|------|
| STAP wrangler 인증 수정 | ✅ 완료 | `d1a89aaf` — env strip + --profile + commit-dirty 제거 |
| CLOUDFLARE_API_TOKEN 무발견 확인 | ✅ 확인 | grep 0건 (ST-2) |
| **인라인 wrangler 금지 규칙** | ⚠️ 규칙 등재 | STAP의 모든 배포는 5000 dispatcher.py 또는 shared/publishers/deploy.py 경유. 인라인 subprocess wrangler 호출 금지. |
| **단일 소스 원칙** | ⚠️ 규칙 등재 | wrangler 인증·토큰 strip·profile 관리는 shared/publishers/deploy.py의 build_wrangler_env()가 유일한 소스. |

**규칙:** STAP/ETAP/TAP 등 외부 프로젝트는 자체 wrangler deploy를 수행하지 않는다. 5000의 dispatcher.py 또는 deploy.py를 경유한다. 인라인 wrangler 호출 시 STRUCT-02(CLOUDFLARE_API_TOKEN 충돌) 재발 위험.

---

*G4 READINESS 반영 완료 — M-2 READINESS 문서에서 참조*
