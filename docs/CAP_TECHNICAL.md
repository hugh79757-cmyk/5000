# CAP (Car Auto Publisher) 기술문서 — 2026-08-09 기준

**최종 업데이트**: 2026-08-09
**프로젝트 루트**: `/Users/twinssn/Projects/5000`
**상태**: 8개 Hugo 블로그 active 운영 중 (CAP 6개 + rank/pick 2개)

> **주의**: 이 문서는 옵시디언 볼트(`/Users/twinssn/Desktop/메모 Hugh-v2/프로젝트/CAP/`)의 구 문서(v1.0, v3.0, V4.0 등)를 대체하는 **현행 기준서**입니다.
> 구 문서들은 2026-04월경 작성되어 rank-hugo/pick-hugo 추가, active 전환, 실제 코드 변경을 반영하지 못했습니다.

---

## 1. 시스템 개요

CAP는 자동차 비교·분석 블로그 8개를 자동 운영하는 파이프라인입니다.

```
launchd (com.5000.scheduler) → scheduler.py (상시 실행)
  └─ dispatcher.dispatch('{blog_id}')  ← dispatcher.py
      └─ pipelines.car.pipeline.run(blog_cfg)  ← car 파이프라인

pipeline.run() 내부:
  1. daily_quota 체크 (publish_log 당일 건수) → 초과 시 skip
  2. topic_manager.select_topic() → topics에서 pending 토픽 선택
  3. data_builder.build_input() → cars + trims + fuel_data 조립
  4. 프롬프트 로드 (config/blogs.d/cap.yaml → prompts/*/*.md)
  5. ai_writer.generate_car() → GPT 본문 생성
  6. publisher.publish() → Hugo 마크다운 + hugo build + wrangler pages deploy
  7. publish_log INSERT + topics.status='published' 업데이트
```

**매일 06:30** `daily_refresh.py`가 자동 실행되어 데이터 갱신 + 토픽 보충을 수행합니다.

---

## 2. 운영 블로그 (2026-08-09 기준 active)

| blog_id | site_id | 도메인 | post_type | 일일 quota | 비고 |
|---|---|---|---|---|---|
| hotissue-hugo | hotissue | hotissue.rotcha.kr | 6종 랜덤 | 5 | landing funnel |
| tco-hugo | tco | tco.rotcha.kr | tco_analysis | 5 | |
| deal-hugo | deal | deal.rotcha.kr | promo_deal | 5 | |
| compare-hugo | compare | compare.rotcha.kr | ranking_compare | 5 | |
| guide-hugo | guide | guide.rotcha.kr | beginner_guide | 5 | |
| ev-hugo | ev | ev.rotcha.kr | ev_analysis | 5 | |
| rank-hugo | rank | rank.informationhot.kr | top5_rank | 1 | informationhot 계열 |
| pick-hugo | pick | pick.informationhot.kr | persona_pick | 1 | informationhot 계열 |

**중요**: hotissue-hugo만 6종 post_type 전체를 사용(랜덤 선택). 나머지 7개 사이트는 전용 post_type 1개만 사용합니다.

**주의**: rank-hugo와 pick-hugo는 `informationhot.kr` 계열 도메인입니다. AdSense Publisher ID는 **ca-pub-6677996696534146** (informationhot 계열)을 사용해야 합니다. 나머지 6개 rotcha.kr 계열은 **ca-pub-8772455780561463** (rotcha 계열).

---

## 3. 데이터 흐름 상세

### 3.1 전체 파이프라인

```
scheduler.py (launchd, 시간표별 실행)
  └─ dispatcher.dispatch('hotissue-hugo') 등
      └─ pipeline.run(blog_cfg)
          ├─ quota 체크: publish_log 오늘 건수 >= daily_quota → skip
          ├─ topic 선택: topic_manager.select_topic(conn, site_id, post_type)
          │   └─ topics WHERE status='pending' AND site_id=? AND post_type=?
          │      ORDER BY priority DESC, RANDOM()
          ├─ 데이터 조립: data_builder.build_input(conn, topic)
          │   ├─ cars + trims 조회 (차종 기본 정보)
          │   ├─ public_fuel_data 조회 (연비/전비)
          │   ├─ price_history 조회 (가격 변동)
          │   ├─ 세금/보험/유류비/잔존가치/감가/총비용 계산
          │   └─ 경쟁 모델 데이터 추가 (competitor_car_id 있는 경우)
          ├─ 프롬프트 로드: prompts/{site_id}/{post_type}.md
          ├─ GPT 생성: ai_writer.generate_car(prompt, data)
          ├─ 검증: validator.validate_body(body, data)
          │   ├─ 모델명/가격/연비 본문 포함 확인
          │   ├─ 금지어 치환 (과연, 놀랍게도 등)
          │   ├─ 글자수 확인 (최소 2000자)
          │   └─ 공식 사이트 섹션 제거
          ├─ Hugo 작성: publisher.publish()
          │   ├─ content/posts/{slug}/index.md 생성
          │   ├─ frontmatter 설정 (title, date, featureimage 등)
          │   ├─ hugo --gc --minify 빌드
          │   └─ wrangler pages deploy
          └─ publish_log INSERT + topics.status='published' 업데이트
```

### 3.2 daily_refresh.py (매일 06:30 자동 실행)

```
run_refresh():
  1. refresh_trims()     — m.carisyou.com에서 124대 차량 트림/가격 업데이트
  2. fill_trim_efficiency() — 트림별 연비 데이터 채우기
  3. refresh_images()    — car_images R2 업로드 + verified 플래그 설정
  4. scan_new_cars()     — 카이즈유에서 신규 차량 탐색 (수동 등록 필요)
  5. detect_price_changes() — price_history에서 2% 이상 변동 감지 → promo_deal 토픽 생성
  6. replenish_topics()  — 사이트별 pending < 50이면 토픽 자동 보충
```

### 3.3 토픽 보충 로직 (replenish_topics)

**핵심 개념**: `popular` 플래그가 붙은 차량 22대만 토픽 생성에 사용됩니다.

```python
SITE_POST_TYPE = {
    "hotissue": "resale_compare",
    "tco": "tco_analysis",
    "rank": "top5_rank",
    "pick": "persona_pick",
    "deal": "promo_deal",
    "compare": "ranking_compare",
    "guide": "beginner_guide",
    "ev": "ev_analysis",
}

인기車 22대: is_popular=1
비인기車: is_popular=0 (롱테일용, 후순위 보충)
```

**토픽 생성 방식**:

| post_type 유형 | 생성 방식 | 상한 |
|---|---|---|
| **단독형** (tco, deal, guide) | 인기차 22대 각각 1 토픽 | 약 22건 (30일 후 재활용) |
| **비교형** (compare, hotissue) | 동일 세그먼트 내 인기차 쌍 | 약 42쌍 (양방향 84건, hotissue+compare 공유) |
| **EV 전용** (ev) | 전기차/하이브리드 인기차 + 비교 조합 | 약 11대 + 쌍 |
| **신규형** (rank, pick) | 인기차 + 세그먼트 경쟁차 쌍 | 인기차 22대 기준 |

**보충 트리거**: pending < 50건일 때 실행. 인기차 먼저 보충하고, 부족 시 비인기차 추가.

**재활용 규칙**:
- 단독형: published 후 30일 경과 시 재생성 가능
- 비교형: published 후 14일 경과 시 재생성 가능 (코드상 다름 — compare는 14일, solo는 30일)

---

## 4. 데이터 현황 및 부족 원인 (2026-08-09)

### 4.1 car.db 주요 테이블 현황

| 테이블 | 건수 | 용도 | 상태 |
|---|---|---|---|
| cars | 124 | 차량 기본 데이터 | ✅ 충분 |
| trims | 705 | 트림 가격/연비 | ✅ 충분 |
| topics | 변동 | 발행 대기 토픽 | ⚠️ 사이트별 편차 |
| car_images | 1,082 | 차량 이미지 (R2) | ✅ 충분 |
| public_fuel_data | 6,672 | 연비/전비 데이터 | ✅ 충분 |
| price_history | 2,628 | 가격 변동 기록 | ✅ 충분 |
| comparisons | 18 | (레거시) 차량 비교 쌍 | ❌ **미사용** |
| promotions | 0 | (설계만 됨) 제조사 프로모션 | ❌ **미구현** |

### 4.2 topics 테이블 현황

```sql
-- deal-hugo (promo_deal)
SELECT site_id, post_type, status, COUNT(*) FROM topics
WHERE site_id IN ('deal', 'compare') GROUP BY 1,2,3;
```

| site_id | post_type | status | 건수 | 비고 |
|---|---|---|---|---|
| deal | promo_deal | pending | 39 | ✅ 발행 가능 |
| deal | promo_deal | published | 233 | |
| deal | promo_deal | skip_no_data | 343 | ⚠️ 비인기차 데이터 부족 |
| compare | ranking_compare | pending | 17 | ⚠️ 약 3.4일치 |
| compare | ranking_compare | published | 599 | |
| compare | ranking_compare | skip_no_data | 116 | ⚠️ |

### 4.3 데이터가 부족한 이유

**① 인기차 22대 상한 **(솔로형: deal, guide, tco)

- `replenish_topics()`는 `cars WHERE is_popular=1` (22대)만 사용
- 각 인기차는 사이트당 1 토픽만 생성 가능 (published 30일 후 재생성)
- deal-hugo의 경우: 22대 × 1 = 최대 약 22건 pending이 정상 범위
- 현재 39건 pending인 이유: 과거 재생성으로 누적 + 비인기차 일부 포함

**② 비교형 상한 **(compare, hotissue)

- 동일 세그먼트 내 인기차 조합만 생성
- 22대 인기차 세그먼트 분포:
  - 준대형세단: 3대 (그랜저HEV, K8HEV, 그랜저2.5)
  - 준중형SUV: 3대 (투싼HEV, 스포티지HEV, ...)
  - 중형SUV: 4대 (쏘렌토HEV, 싼타페HEV, 아이오닉5, EV6, 테슬라Y)
  - 중형세단: 4대 (K5, 쏘나타, K5HEV, 아이오닉6)
  - 준중형세단: 2대 (아반떼, 아반떼HEV)
  - 소형SUV: 2대 (코나, 코나HEV)
  - 대형세단: 1대 (K9) → 쌍 생성 불가
  - 경차: 2대 (캐스퍼, 모닝)
- 이론적 최대 쌍 수: 약 42쌍 (양방향 84건)
- **compare와 hotissue가 이 풀을 공유** → compare 단독 약 20-30건 상한
- 현재 compare pending 17건: 정상 범위 내 (더 늘어나기 어려움)

**③ skip_no_data 343건 **(deal-hugo)

- 비인기차(`is_popular=0`) 토픽이 파이프라인에서 처리 실패
- `build_input()`이 필요한 데이터(competitor 정보, 이미지 등)를 못 찾으면 skip
- 비인기차 보충은 **인기차 소진 후에만** 작동 → 현재 인기차가 아직 남아있어 비인기차 보충 안 됨
- skip_no_data는 정상적 현상이며, 시스템이 "데이터 부족한 차종은 발행하지 않음"을 의미

**④ promotions 테이블 0건**

- **설계만 되고 미구현**: 제조사 공식 홈페이지 프로모션 크롤링(kia_hyundai.py)이 설계되었으나 실행되지 않음
- **현재 파이프라인에서 전혀 사용 안 함** — deal-hugo의 `promo_deal`은 실제 프로모션 데이터가 아니라 차량 가격/할부/구매 타이밍 분석 글
- **문제 아님**

**⑤ comparisons 테이블 18건**

- 과거 수동/레거시로 생성된 차량 비교 쌍 (현대 vs 기아 주요 모델)
- **현재 파이프라인에서 전혀 사용 안 함** — 비교 조합은 `topics` 테이블로 관리
- **레거시 테이블, 삭제해도 무방**

---

## 5. deal-hugo `promo_deal`의 실제 성격

**흔히 오해하는 점**: "deal-hugo는 제조사 프로모션 정보를 다루는 블로그다" — **아님**.

**실제**: deal-hugo의 `promo_deal`은 **차량 가격 적정성/할부 시뮬레이션/구매 타이밍 분석** 블로그입니다.

프롬프트(`prompts/deal/promo_deal.md`) 구조:
- H2-1: `{model} {trim} {price}만원, 지금 사도 될까` — 가격 적정성 판단
- H2-2: 전 트림 가격 비교 (trim_lineup 데이터)
- H2-3: 경쟁 모델 비교 (competitor 데이터)
- H2-4: 할부 시뮬레이션 + **일반적** 구매 타이밍 조언 (분기말 할인 가능성 등)
- H2-5: 3년 총비용 분석

→ 제조사 실제 프로모션 데이터가 없어도 **차량 가격/할부/감가 데이터만으로 글 작성 가능**.

---

## 6.-rank/pick 정보

rank-hugo와 pick-hugo는 2026-04-16에 추가된 informationhot.kr 계열 블로그입니다.

| 구분 | rank-hugo | pick-hugo |
|---|---|---|
| domain | rank.informationhot.kr | pick.informationhot.kr |
| site_id | rank | pick |
| post_type | top5_rank | persona_pick |
| quota | 1회/일 | 1회/일 |
| 스케줄 | 07:22 | 07:24 |
| 계열 | informationhot | informationhot |
| AdSense | ca-pub-6677996696534146 | ca-pub-6677996696534146 |

**rank-hugo** (`top5_rank`): 인기차 순위/랭킹 콘텐츠. `build_top5_rank_input()` 함수로 데이터 조립.

**pick-hugo** (`persona_pick`): 페르소나 기반 차량 추천. `build_persona_pick_input()` 함수로 데이터 조립. 같은 세그먼트 경쟁차 쌍을 함께 표시.

---

## 7. 주요 코드 파일 맵

| 파일 | 역할 |
|---|---|
| `pipelines/car/pipeline.py` | 메인 실행 루프 (run 함수) |
| `pipelines/car/data_builder.py` | DB → 차량 데이터 조립 (build_input, build_top5_rank_input, build_persona_pick_input) |
| `pipelines/car/topic_manager.py` | 토픽 선택/제목 생성/슬러그/본문 검증 |
| `pipelines/car/title_engine.py` | 사이트별 고CTR 제목 템플릿 엔진 |
| `pipelines/car/daily_refresh.py` | 일일 데이터 갱신 + 토픽 보충 (06:30) |
| `pipelines/car/validator.py` | 발행 전 검증 (파이프라인 내 통합됨) |
| `pipelines/car/enrich.py` | 데이터 보강 (향후 확장용) |
| `shared/ai_writer.py` | GPT 호출 (generate_car) |
| `shared/publisher.py` | Hugo 작성 + 배포 |
| `dispatcher.py` | 블로그 ID → 파이프라인 라우팅 |

---

## 8. 핵심 주의사항

### 8.1 topics 부족 시 대응

- **deal-hugo pending 39건**: 충분. 일일 5회 기준 7.8일치. 추가 조치 불필요.
- **compare-hugo pending 17건**: 약 3.4일치. `daily_refresh.py`가 매일 06:30에 자동 보충하나, 인기차 풀 한계로 급증은 어려움. 긴급 시 수동 보충 가능:
  ```python
  # compare-hugo 토픽 수동 보충 예시
  from pipelines.car.daily_refresh import replenish_topics
  import sqlite3
  conn = sqlite3.connect('/Users/twinssn/Projects/5000/data/car.db')
  replenish_topics(conn, min_pending=30)  # threshold 낮춰서 실행
  ```

### 8.2 skip_no_data는 정상

- deal-hugo의 skip_no_data 343건은 **문제 아님**. 비인기차 데이터 부족으로 발행 skipped.
- 비인기차 토픽은 인기차 소진 후에만 생성됨 (후순위).
- skip_no_data를 줄이려면 `build_input()`이 비인기차 데이터도 처리할 수 있도록 보강하거나, 비인기차 데이터 수집 강화 필요.

### 8.3 promotions/comparisons 테이블

- **둘 다 현재 파이프라인에서 사용되지 않음**.
- promotions: 향후 제조사 프로모션 크롤링 구현 시 사용 예정 (중기 TODO).
- comparisons: 레거시 테이블. 마이그레이션 후 삭제 가능.

### 8.4 AdSense Publisher ID

- **rotcha.kr 계열 6개** (hotissue, tco, deal, compare, guide, ev): `ca-pub-8772455780561463`
- **informationhot.kr 계열 2개** (rank, pick): `ca-pub-6677996696534146`
- hugo.toml의 `[params.advertisement]` 설정과 실제 AdSense 계정 일치 확인 필요.

### 8.5 싱크 큐 (funnel 구조)

```
landing (유입)
  ├─ hotissue-hugo (rotcha) → 6종 랜덤
  ├─ rank-hugo (informationhot) → top5_rank
  └─ pick-hugo (informationhot) → persona_pick

bridge (탐색)
  ├─ compare-hugo → "비교 결과 내 조건에 맞는 차 찾기" (→ pick-hugo)
  ├─ tco-hugo → ...
  ├─ deal-hugo → ...
  ├─ guide-hugo → ...
  └─ ev-hugo → ...

monetize (수익)
  └─ pick-hugo (informationhot) — funnel_stage: monetize
```

---

## 9. 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-08-09 | 문서 최초 작성 (옵시디언 구문서 대체). 8개 블로그 active 기준, 실제 코드 상태 반영 |
| 이전 | 옵시디언 v1.0/v3.0/V4.0 문서들 — 구버전, rank/pick 미포함, 실제 코드 불일치 |

---

*이 문서는 CAP 분기 작업 에이전트용 기준서입니다. 코드 변경이 발생하면 이 문서도 함께 업데이트하세요.*
