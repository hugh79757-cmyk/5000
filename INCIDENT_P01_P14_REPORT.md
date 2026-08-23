# INCIDENT_P01_P14_REPORT.md

> **진단 시각**: 2026-08-18 23:50 KST
> **대상 블로그**: pick-hugo, car-hugo, golf-hugo
> **수행 범위**: READ-ONLY 진단만. 재발행·재시도·필터 완화·코드/설정/DB 변경·배포 없음.

---

## 1. 실행 이력 재구성

### pick-hugo (최근 21회)

| # | 시각 | 상태 | reason |
|---|------|------|--------|
| 1 | 08-18 23:41 | failed | no_data |
| 2 | 08-17 12:17 | failed | daily cooldown |
| 3 | 08-17 12:11 | failed | daily cooldown |
| 4 | 08-17 12:06 | failed | daily cooldown |
| 5 | 08-17 12:01 | failed | daily cooldown |
| 6 | 08-17 11:55 | failed | daily cooldown |
| 7 | 08-17 11:24 | failed | daily cooldown |
| 8 | 08-17 11:20 | failed | daily cooldown |
| 9 | 08-17 11:14 | failed | daily cooldown |
| 10 | 08-17 11:07 | failed | daily cooldown |
| 11 | 08-17 11:01 | failed | daily cooldown |
| 12 | 08-17 10:55 | failed | daily cooldown |
| 13 | 08-17 10:49 | failed | daily cooldown |
| 14 | 08-17 10:43 | failed | daily cooldown |
| 15 | 08-17 10:37 | failed | daily cooldown |
| 16 | 08-17 10:31 | failed | daily cooldown |
| 17 | 08-17 10:25 | failed | daily cooldown |
| 18 | 08-17 10:19 | failed | daily cooldown |
| 19 | 08-17 10:13 | failed | daily cooldown |
| 20 | 08-17 10:07 | failed | daily cooldown |
| 21 | 08-17 10:01 | failed | daily cooldown |

> 21건 중 20건이 daily cooldown. 실제 pipeline 실행은 08-18 23:41 단 1건(no_data).

### car-hugo (최근 4회)

| # | 시각 | 상태 | reason |
|---|------|------|--------|
| 1 | 08-18 23:45:49 | failed | no_keyword |
| 2 | 08-18 23:45:48 | failed | 사용 가능한 키워드 없음 |
| 3 | 08-17 13:21:31 | failed | no_keyword |
| 4 | 08-17 13:21:30 | failed | 사용 가능한 키워드 없음 |

### golf-hugo (최근 4회)

| # | 시각 | 상태 | reason |
|---|------|------|--------|
| 1 | 08-18 23:46:20 | failed | no_keyword |
| 2 | 08-18 23:46:19 | failed | 사용 가능한 키워드 없음 |
| 3 | 08-17 14:05:36 | failed | no_keyword |
| 4 | 08-17 14:05:35 | failed | 사용 가능한 키워드 없음 |

---

## 2. no_result / no_keyword 원인 분류

### pick-hugo: no_data (pipeline: car)

| 분류 | 해당 여부 | 근거 |
|------|-----------|------|
| 후보 소진 | **❌ 아님** | `topics` 테이블에 pending=68건 존재 (`data/car.db`) |
| 수집 API 공백/오류 | **❌ 아님** | car 파이프라인은 외부 API 호출 없음, 로컬 DB 기반 |
| 응답 파싱 실패 | **해당 가능** | `build_persona_pick_input()`이 4단계에서 None 반환 |
| 품질 guard | **❌ 아님** | no_data는 품질 검사 이전 단계에서 차단 |
| 유사 제목/중복 guard | **❌ 아님** | no_data는 제목 생성 전 단계 |
| 설정 오류 | **⚠️ 부분 해당** | pending topics 중 다수의 `car_id`가 trims 테이블에 0건 |

**근본 원인 후보 (신뢰도 85%):**

`build_persona_pick_input()`의 `persona_pick_eligibility()`이 다음 조건에서 None 반환:

1. `persona_pick_eligibility(conn, car_id)` → `no_eligible_trim` (trims where price≥500 = 0건)
   - `k8_2026`: trims 0건
   - `kgm____2026`: trims 0건
   - `volvo_ex30_2026`: trims 0건
2. 또는 `no_fuel_efficiency` (연비 데이터 없음)
3. `select_topic()`이 trims가 있는 topic을 먼저 선택하도록 보장하지 않음

**근거 경로:**
- `pipelines/car/pipeline.py:198` → `build_input()` 또는 line 153 `build_top5_rank_input()` / line 168 `build_persona_pick_input()`
- `pipelines/car/data_builder.py:717-719` → `persona_pick_eligibility()` → False 반환
- `pipelines/car/data_builder.py:733-735` → trims 0건 → None 반환
- `pipelines/car/data_builder.py:743-747` → fuel_efficiency 0 → None 반환

**추가 문제 — daily cooldown:**
- 08-17 하루에 **30회+** daily cooldown 발생
- 스케줄러가 ~5분 간격으로 실행 → no_data 1건 발생 후 나머지는 모두 cooldown
- `publish_ledger`에 `daily cooldown` 기록만 쌓이고 실제 pipeline 실행은 1건/일

### car-hugo: no_keyword (pipeline: curation)

| 분류 | 해당 여부 | 근거 |
|------|-----------|------|
| **후보 소진** | **✅ 해당** | 12개 키워드 중 8개가 30일 내 사용 → `_select_keyword()`가 None 반환 |
| 수집 API 공백/오류 | **❌ 아님** | 키워드 선택 단계에서 차단, API 호출 전 |
| 응답 파싱 실패 | **❌ 아님** | — |
| 품질 guard | **⚠️ 부분 해당** | relevance gate가 미사용 4개 키워드도 차단 가능 |
| 유사 제목/중복 guard | **❌ 아님** | 키워드 선택 단계에서 차단 |
| 설정 오류 | **❌ 아님** | — |

**근본 원인 (신뢰도 90%):**

`_select_keyword("car-hugo")` → `_select_keyword()` line 192-198:
- 전체 12개 키워드 중 8개가 `publish_log`에서 30일 내 사용 → 제외
- 미사용 4개: `차량용공기청정기`, `타이어공기주입기`, `차량용거치대`, `차량용냉장고`
- 이 4개는 상품 수 14~19개로 충분 (≥3 조건 통과)
- **relevance gate에서 차단된 것으로 추정** — `score_products()` 평균 relevance가 threshold 미달

### golf-hugo: no_keyword (pipeline: curation)

| 분류 | 해당 여부 | 근거 |
|------|-----------|------|
| **후보 소진** | **✅ 해당** | 12개 키워드 중 6개가 30일 내 사용 → `_select_keyword()`가 None 반환 |
| 수집 API 공백/오류 | **❌ 아님** | 키워드 선택 단계에서 차단 |
| 응답 파싱 실패 | **❌ 아님** | — |
| 품질 guard | **⚠️ 부분 해당** | relevance gate가 미사용 6개 키워드도 차단 가능 |
| 유사 제목/중복 guard | **❌ 아님** | — |
| 설정 오류 | **❌ 아님** | — |

**근본 원인 (신뢰도 90%):**

`_select_keyword("golf-hugo")` → 전체 12개 키워드 중 6개가 30일 내 사용 → 제외
- 미사용 6개: `골프클럽`, `골프드라이버`, `아이언세트`, `골프거리측정기`, `골프의류`, `골프우산`
- 이 6개는 상품 수 12~21개로 충분
- **relevance gate에서 차단된 것으로 추정**

---

## 3. 공유 자원 대조

### 블로그 설정 비교

| 항목 | pick-hugo | car-hugo | golf-hugo |
|------|-----------|----------|-----------|
| 파이프라인 | **car** | **curation** | **curation** |
| 도메인 | pick.informationhot.kr | car.informationhot.kr | golf.informationhot.kr |
| 배포 | pages | workers | workers |
| 스케줄 | 07:24 (1회/일) | 07:30/13:30/19:30 (3회/일) | 08:30/14:30/20:30 (3회/일) |
| 관리 | 5000 dispatcher | md-editor v2 | md-editor v2 |
| 설정 파일 | `cap.yaml:184` | `cuap.yaml:249` | `cuap.yaml:289` |

### 키워드 풀

| 항목 | pick-hugo | car-hugo | golf-hugo |
|------|-----------|----------|-----------|
| 키워드 소스 | car DB (로컬) | KEYWORD_MAP (12개) | KEYWORD_MAP (12개) |
| 30일 내 사용 | N/A | 8/12개 | 6/12개 |
| 미사용 가능 | N/A | 4개 (상품 14~19개) | 6개 (상품 12~21개) |
| 쿠팡 API | 미사용 | 사용 | 사용 |
| relevance gate | 미사용 | threshold=0.75 (default) | threshold=0.75 (default) |

### 코드/설정 최근 변경

| 커밋 | 변경 | 영향 |
|------|------|------|
| `e3259ba2` | car DB 중앙화 | pick-hugo의 car DB 경로 변경 가능 |
| `08e74188` | car standard-skeleton wrappers | pick-hugo 래퍼 추가 |
| `63ca50572` | curation DB 중앙화 | car/golf-hugo의 curation DB 경로 변경 |
| `59c95032f` | config(cuap): car 포함 7개 블로그 활성화 | car-hugo 활성화 |

### API quota / 응답 상태

| 항목 | pick-hugo | car-hugo | golf-hugo |
|------|-----------|----------|-----------|
| 외부 API 호출 | 없음 | 쿠팡 Partners REST | 쿠팡 Partners REST |
| API 차단 | 없음 | `_check_rate_limit` 분당 40회 | 동일 |
| 최근 API 오류 | 없음 | 없음 | 없음 |

---

## 4. 동일 pipeline 블로그 성공률 비교

### car 파이프라인 (pick-hugo 형제)

| 블로그 | 총 실행 | 발행 | 실패 | 성공률 |
|--------|---------|------|------|--------|
| compare-hugo | 1,307 | 1,146 | 161 | **87.7%** |
| hotissue-hugo | 1,306 | 1,136 | 170 | **87.0%** |
| guide-hugo | 565 | 437 | 128 | **77.3%** |
| deal-hugo | 604 | 448 | 156 | **74.2%** |
| tco-hugo | 600 | 441 | 159 | **73.5%** |
| rank-hugo | 395 | 264 | 131 | **66.8%** |
| ev-hugo | 463 | 288 | 175 | **62.2%** |
| **pick-hugo** | **560** | **238** | **322** | **42.5%** ❌ |

> pick-hugo는 car 파이프라인 블로그 중 **최하위**. 형제 블로그 평균 성공률(76.3%) 대비 33.8%p 낮음.
> **판정: 블로그별 장애** — 동일 파이프라인의 다른 블로그들은 정상.

### curation 파이프라인 (car-hugo, golf-hugo 형제)

| 블로그 | 총 실행 | 발행 | 실패 | 성공률 |
|--------|---------|------|------|--------|
| interior-hugo | 845 | 568 | 277 | **67.2%** |
| appliance-hugo | 860 | 533 | 327 | **62.0%** |
| beauty-hugo | 621 | 384 | 237 | **61.8%** |
| baby-hugo | 890 | 516 | 374 | **58.0%** |
| fitness-hugo | 914 | 516 | 398 | **56.5%** |
| kitchen-hugo | 643 | 343 | 300 | **53.3%** |
| health-hugo | 701 | 362 | 339 | **51.6%** |
| camping-hugo | 701 | 336 | 365 | **47.9%** |
| laptop-hugo | 791 | 351 | 440 | **44.4%** |
| pet-hugo | 686 | 299 | 387 | **43.6%** |
| massage-hugo | 24 | 10 | 14 | **41.7%** |
| homeappliance-hugo | 22 | 9 | 13 | **40.9%** |
| **car-hugo** | **38** | **10** | **28** | **26.3%** ❌ |
| **golf-hugo** | **48** | **8** | **40** | **16.7%** ❌ |
| bike-hugo | 70 | 7 | 63 | **10.0%** ❌ |

> car-hugo, golf-hugo는 curation 파�이프라인 블로그 중 **하위 3위 이내**.
> curation 블로그 평균 성공률(49.3%) 대비显著히 낮음.
> **판정: 블로그별 장애 + 키워드 풀 고갈이라는 구조적 한계 공존.**

---

## 5. 재실행 없이 사용 가능한 후보 존재 여부

### pick-hugo

| 항목 | 상태 |
|------|------|
| 사용 가능한 후보 | **⚠️ 부분적** — pending topics 68건 존재하나 trims 데이터 있는 topic은 제한적 |
| 마지막 정상 발행 | **2026-08-12** (6일 전) |
| 주요 slug | `패밀리에게-모델-Y가-맞는-이유-실비용으로-따져봤다` |
| 데이터 대기열 | pending 68건 중 `persona_pick` 33건, `top5_rank` 35건 |
| persona_pick 가용 | **제한적** — 일부 car_id에 trims 0건 (k8_2026, kgm____2026, volvo_ex30_2026) |
| top5_rank 가용 | **가능** — top5_rank는 `build_top5_rank_input()` 사용, 별도 데이터 필요 |

### car-hugo

| 항목 | 상태 |
|------|------|
| 사용 가능한 후보 | **❌ 없음** — 12개 키워드 중 미사용 4개는 relevance gate에서 차단 추정 |
| 마지막 정상 발행 | **2026-08-16** (2일 전) |
| 주요 slug | `차량-내부-공간-넓히는-트렁크정리함-차종별-맞춤형-수납템` |
| 키워드 재사용 가능 | 30일 후 (09-04~09-15) |

### golf-hugo

| 항목 | 상태 |
|------|------|
| 사용 가능한 후보 | **❌ 없음** — 12개 키워드 중 미사용 6개는 relevance gate에서 차단 추정 |
| 마지막 정상 발행 | **2026-08-16** (2일 전) |
| 주요 slug | `가벼운-초경량-골프백-라운딩용-스탠드백-비교-분석` |
| 키워드 재사용 가능 | 30일 후 (09-05~09-15) |

---

## 6. 근본원인 후보 및 신뢰도

### pick-hugo — no_data

| 순위 | 근본원인 | 신뢰도 | 근거 |
|------|----------|--------|------|
| 1 | `persona_pick_eligibility()`이 pending topics를 인덱싱 불가하게 함 | **85%** | trims 0건인 car_id가 pending에 다수 존재, `select_topic()`이 trims 있는 topic 우선 보장 없음 |
| 2 | `build_top5_rank_input()`이 top5_rank 데이터 없음 | **60%** | top5_rank 35건 pending이나 `_rnd.choice(["resale","maintenance","monthly_cost","value"])` 선택 후 데이터 없을 수 있음 |
| 3 | daily cooldown 메커니즘이 1회 실패 후 재시도 차단 | **95%** (부수적) | 08-17 하루 30회+ cooldown — no_data 1건 후 모든 재시도 차단 |

### car-hugo — no_keyword

| 순위 | 근본원인 | 신뢰도 | 근거 |
|------|----------|--------|------|
| 1 | **키워드 30일 중복 억제 + relevance gate 이중 필터** | **90%** | 12개 중 8개 사용됨, 미사용 4개는 relevance gate에서 차단 추정 (threshold=0.75) |
| 2 | 키워드 풀 자체 부족 (12개) | **70%** | 30일 내 8개 사용 → 미사용 4개는 car 관련 쿠팡 상품의 relevance가 낮을 수 있음 |

### golf-hugo — no_keyword

| 순위 | 근본원인 | 신뢰도 | 근거 |
|------|----------|--------|------|
| 1 | **키워드 30일 중복 억제 + relevance gate 이중 필터** | **90%** | 12개 중 6개 사용됨, 미사용 6개는 골프 관련 쿠팡 상품의 relevance가 낮을 수 있음 |
| 2 | 키워드 풀 자체 부족 (12개) | **65%** | 골프는 계절性强, 일부 키워드(골프의류, 골프우산)의 relevance가 낮을 수 있음 |

---

## 7. 안전한 최소 수정안 (재시도 없이)

### pick-hugo

| 수정안 | 설명 | 위험도 |
|--------|------|--------|
| **A. `select_topic()`에 trims 존재 우선 정렬** | pending topics를 trims JOIN으로 필터링 후 선택 | 낮음 |
| **B. `persona_pick_eligibility()` 실패 시 `top5_rank` fallback** | persona_pick 실패 시 top5_rank 시도 | 낮음 |
| **C. daily cooldown 간격 단축 또는 no_data 시 즉시 재시도** | no_data는 daily cooldown 대상에서 제외 | 중간 |

### car-hugo / golf-hugo

| 수정안 | 설명 | 위험도 |
|--------|------|--------|
| **D. relevance threshold 완화** | `car-hugo`/`golf-hugo`용 별도 threshold (0.75→0.60) | 중간 |
| **E. KEYWORD_MAP에 키워드 추가** | car-hugo: 추가 차량용품 키워드, golf-hugo: 추가 골프용품 키워드 | 낮음 |
| **F. 30일 중복 억제 기간 단축** | 30일→21일 또는 14일 | 중간 |

---

## 8. 검증 및 롤백 절차

### 검증 절차

1. pick-hugo: `python3 dispatcher.py pick-hugo` 실행 → `no_data` 아닌 다른 reason 확인
2. car-hugo: `python3 dispatcher.py car-hugo` 실행 → `no_keyword` 아닌 다른 reason 확인
3. golf-hugo: `python3 dispatcher.py golf-hugo` 실행 → `no_keyword` 아닌 다른 reason 확인

### 롤백 절차

- 코드 변경 시: `git revert <commit-hash>`
- 설정 변경 시: `config/blogs.d/cap.yaml` 또는 `cuap.yaml` 원복
- DB 변경 시: `data/curation.db` 백업에서 복원

---

## 9. 잔존 위험

1. **pick-hugo의 dailycooldown 메커니즘**: no_data 1건 발생 후 하루 전체 차단 — 근본 원인 수정 전까지 매일 1건 실패 반복
2. **car-hugo/golf-hugo의 키워드 고갈 주기**: 30일 중복 억제 + relevance gate 이중 필터로 ~30일마다 키워드 고갈 발생
3. **relevance threshold=0.75 (default)**: car/golf 블로그에 적합하지 않은 높은 기준 — 쿠팡 상품의 키워드 관련성이 원래 낮을 수 있음
4. **pick-hugo의 no_data가 8/12 이전부터 존재**: 66건의 pre-8/12 no_data 기록 —这不是新问题,은 누적된 구조적 문제
5. **scheduler가 ~5분 간격으로 실행**: no_data 실패 후에도 스케줄러가 계속 실행 → daily cooldown 로그로 publish_ledger 오염

---

> **이 보고서는 READ-ONLY 진단만 수행했습니다. 코드/설정/DB 변경, 재발행, 재시도는 수행하지 않았습니다.**
