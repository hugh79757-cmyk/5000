# Design: 키워드 수익 분석 대시보드 + 발행 전략 엔진 (rev.2)

- 날짜: 2026-08-20 (rev.2 개정)
- 분류: architectural (다중 서브시스템 — 분석 대시보드 + 발행 전략 엔진으로 분해)
- 목적지: 수익 (AdSense + 제휴 복합)
- 현재 위치 (성숙도 지도): L1 (감시)
- 목표: L4 (수익 최적화)
- 개정 이력: rev.1 (섹션 1~5 승인 완료, 커밋 5fe249da8~2b24838e2, 셀프 리뷰 05f8eb046) → rev.2 (지표 명명 교정, attribution 계층, guardrail, 추천 점수 분리, Phase 0 품질 게이트)

## 배경 요약

- 최종 목표: "사용되는 키워드가 어떤건지, 키워드에 따른 피치 단가가 어땠는지, 그에 따른 수익은 얼마였는지 세세하게 분석할 수 있는 도구" → 이를 기반으로 성과 목표 기준의 신규 발행 전략.
- 결과물 우선순위: **분석 대시보드 먼저** (발행 전략 엔진은 그 다음).
- 피치 단가 정의: **실적 기반 추정 단가**.
- 성숙도 레벨 지도: L0 수동 → L1 감시 → L2 진단+수정지시 → L3 자동 복구 → L4 수익 최적화 → L5 자율 운영. 현재 = L1.

## 섹션 1: 데이터 연결 골격 [승인됨 + rev.2 보강]

### 1-1. 데이터 소스 현황 (검증됨)

| 소스 | DB/테이블 | 단위 | 상태 |
|------|-----------|------|------|
| AdSense | `data/analytics.db` `adsense_daily` | domain (DATE + DOMAIN_NAME dimension) | 2393행 / 110도메인 / 2026-03-19~07-28 (4.3개월, 충분) |
| GSC 키워드 | `gsc_keywords` | **blog_id** (UNIQUE(blog_id,date,query)) | 373행 / 218키워드 / 14일 (얇음) |
| GSC 페이지 | `gsc_pages` | blog_id + page(URL) + date | **0행** |
| GA4 페이지 | `ga4_pages` | blog_id + page_path | 존재 |

- `gsc_keywords`, `gsc_pages`, `ga4_pages`는 이미 blog_id 단위 → 조인 가능.
- `adsense_daily.domain` → blog_id 매핑만 Phase 0/1에서 필요.

### 1-2. 도메인→blog_id 매핑 (Phase 0에서 생성, Phase 1에서 적용)

- `adsense_daily.domain`을 blog_id로 연결하는 매핑 테이블/로직 생성.
- 주의: `foodwater.tistory.com` (티스토리) 등 5000 인벤토리 밖 도메인 존재 → 매핑에서 제외/분리 표시.

### 1-3. 지표 명명 교정 (rev.2 핵심 변경)

기존 rev.1의 "키워드 EPC" 명칭을 폐기하고 다음 3개 지표로 구분한다:

```
① estimated_keyword_revenue(k)
   = (GSC_clicks(k) ÷ Σ GSC_clicks(blog)) × AdSense_revenue(blog, day)
   → "키워드 추정 수익". 비례배분 추정치일 뿐, 단가 지표가 아님.

② estimated_revenue_per_organic_click(blog)
   = AdSense_revenue(blog, day) ÷ Σ GSC_clicks(blog)
   → "유기 클릭당 추정 수익" (블로그 레벨 단가).

③ true EPC (attributed)
   = attributed_revenue ÷ attributed_clicks
   → 실측 attribution(페이지/URL 단위 수익 + 해당 페이지 클릭)이 존재할 때만 계산.
     rev.2 현재는 attribution 데이터가 없으므로 true EPC는 미표시 (추정 금지).
```

**명칭 규칙**: `estimated_keyword_revenue`는 "추정 수익"으로 표시, "EPC"라는 단어는 true EPC(실측 attribution)에만 사용한다. rev.1의 "키워드 EPC" 표기는 오명칭으로 판정되어 폐기된다.

## 섹션 2: 지표 정의 + attribution 계층 + guardrail [승인됨 + rev.2 보강]

### 2-1. 비례배분의 한계: 단위 클릭가치 동일화 (rev.2 명시)

**수식 전개**: ①에서 파생되는 키워드 단위 클릭가치는 블로그 내 상수다.

```
단위 클릭가치(k) = estimated_keyword_revenue(k) ÷ GSC_clicks(k)
               = [(GSC_clicks(k) ÷ ΣGSC_clicks(blog)) × Revenue(blog)] ÷ GSC_clicks(k)
               = Revenue(blog) ÷ ΣGSC_clicks(blog)          ← k와 무관한 상수
               = estimated_revenue_per_organic_click(blog)
```

**예제**:
- 블로그 X: 일일 AdSense $10.00, 일일 GSC 클릭 100 → 단위 클릭가치 = $0.10
- 키워드 A "gr86 유지비" (클릭 45): 추정 수익 $4.50, 단위 클릭가치 $0.10
- 키워드 B "gr86 리뷰" (클릭 10): 추정 수익 $1.00, 단위 클릭가치 $0.10

**결론**: 블로그 내부에서는 모든 키워드의 단위 클릭가치가 동일 → **순위 변별력이 사라진다** (수익순 정렬 = 클릭순 정렬과 동일). 따라서:
- 블로그 내부 순위 비교에는 `estimated_keyword_revenue`를 쓰지 않고, **클릭·CTR·평균순위 자체**를 사용한다.
- 단가 비교는 **블로그 간**에서만 의미가 있다 (블로그마다 단위 클릭가치가 다름).
- 이 한계는 대시보드에 명시 표기한다.

### 2-2. attribution 계층 설계 (rev.2 신설 — 추정 금지 원칙)

가능한 연결만 사용하고, **실제 제공되지 않는 dimension은 추정하지 않는다**.

| 계층 | 연결 | 데이터 출처 | 상태 |
|------|------|-------------|------|
| A0 | blog_id ↔ domain | 매핑 테이블 (1-2) | Phase 0에서 구축 |
| A1 | query ↔ page ↔ date | GSC `gsc_keywords`(query) + `gsc_pages`(page, date) | **gsc_pages 0행 — 수집 필요** |
| A2 | page ↔ revenue | **AdSense Management API v2는 page/URL 단위 수익 dimension을 제공하지 않음** (DATE, DOMAIN_NAME, AD_UNIT, PRODUCT 등만 제공) | **불가 — 추정 금지** |
| A3 | GA4 landing page ↔ ad revenue | GA4에 광고 수익 이벤트가 설정되어 있지 않음 (감사 확인) | **불가 — 추정 금지** |

**결과**:
- 페이지/URL 단위 수익 attribution(A2)은 데이터 소스가 없으므로 **구축하지 않는다**. true EPC(③)는 미표시.
- 실현 가능한 최대 깊이 = **A0 + A1** (쿼리→페이지 연결) + 블로그 레벨 수익.
- 페이지 단위 추정 수익은 "추정"으로만 표시하고 true EPC와 혼동 금지.
- A2가 가능해지는 조건(AdSense URL 채널 API, GA4 ad revenue 이벤트 설정, 제휴 subId reporting)이 갖춰지면 그때 확장한다.

### 2-3. 예상 증분수익 정의 (rev.2 신설)

페이지 레벨 수익이 없으므로, 발행 전략의 기본 단위는 **증분 클릭 × 블로그 단가**로 정의한다.

```
expected_incremental_revenue(후보 키워드)
  = expected_incremental_clicks × estimated_revenue_per_organic_click(blog)

예: 블로그 단위 클릭가치 $0.10, 신규 글 예상 증분 클릭 30/월
    → 예상 증분수익 = 30 × $0.10 = $3.00/월
```

**이중 곱 금지 주의**: `expected_incremental_revenue ≠ 예상 클릭 × estimated_keyword_revenue` — estimated_keyword_revenue는 이미 클릭 수를 포함한 배분치이므로, 이를 단가처럼 곱하면 클릭을 이중으로 곱하는 오류가 된다. 단가로는 반드시 `estimated_revenue_per_organic_click` (②)을 사용한다.

**confidence 표시**: 예상 증분수익은 신뢰도(낮음/중간/높음)와 함께 표시한다. 신뢰도 결정 요인: 데이터 기간(28일 충분 여부), 클릭 수(희소 여부), 계절성, 순위 안정성. 신뢰도가 낮으면 추천에서 제외하거나 하위 정렬한다.

### 2-4. 분석 지표 정의 (3개 레벨)

- **L1 블로그/도메인**: 수익(일/주/월), PV, 클릭, RPM, CTR, `estimated_revenue_per_organic_click`, 7일·30일 추세선(증감율).
- **L2 키워드**: 노출, 클릭, CTR, 평균 순위(포지션), `estimated_keyword_revenue`(추정 수익 — 참고용). 정렬 토글(수익/클릭/CTR/순위), 필터(기간·블로그·최소 클릭). **단위 클릭가치 비교는 블로그 간에서만** (2-1 한계 표시).
- **L3 게시글**: page_path, PV(ga4_pages), 소속 키워드(A1 매핑, gsc_pages 수집 후). 페이지 수익은 표시하지 않음 (A2 불가).

### 2-5. guardrail (rev.2 신설 — 데이터 표시 규칙 포함)

| # | Guardrail | 규칙 |
|---|-----------|------|
| G1 | 최소 노출/클릭 | 클릭 < 3 기본 숨김. 노출 < 100은 CTR 통계 신뢰 불가 → CTR 표시 시 경고 |
| G2 | 희소 데이터 shrinkage | 클릭 적은 키워드(3≤클릭<10)는 추정치를 블로그 평균 방향으로 축소: `shrunk = (clicks × sample + prior_weight × blog_avg) ÷ (clicks + prior_weight)`, prior_weight=10 기본 |
| G3 | 28일 trailing window | 모든 집계는 최근 28일 고정 (GSC 롤링 기준). 기간 변경은 명시적 필터로만 |
| G4 | 데이터 지연 | AdSense/GSC 수집 지연(1~3일) 고려 — 최근 3일은 "지연 가능" 마커 표시, 0건을 즉시 해석 금지 |
| G5 | 계절성 | 전년 동기 또는 직전 동일 기간 대비 비교 병기 (단순 전주 대비 증감만으론 판단 금지) |
| G6 | 검색순위 | 평균 순위(포지션) 변화를 클릭 변화와 함께 표시 — 순위 하락을 수요 감소로 오판 금지 |
| G7 | CTR | CTR은 순위·노출 품질과 함께 해석 (단독 지표로 발행 판단 금지) |
| G8 | 키워드 cannibalization | 추천 전 동일/유사 키워드가 기존 게시글에 이미 커버되었는지 검사 — 커버된 키워드는 "확장" 추천으로만, 신규 추천에서 제외/플래그 |
| G9 | 신규 글 색인 실패 | 발행 후 N일(기본 14일) 내 색인(IndexNow/GSC 포함) 미확인 시 "색인 미확인" 플래그 — 수익 평가에서 제외하고 재색인 조치 안내 |

**데이터 표시 규칙**:
- "추정 수익" 라벨 강제 (실측 아님 명시).
- 클릭 < 3 키워드 기본 숨김 (G1).
- 기간 기본값: 최근 28일 (G3).
- guardrail 위반 시 해당 행에 경고 마커 표시.

### 2-6. 키워드 랭킹 테이블 (예시 — rev.2)

| 키워드 | 클릭 | CTR | 평균순위 | 추정수익* | 단위 클릭가치 | 신뢰도 | 블로그 |
|--------|------|-----|---------|-----------|--------------|--------|-------|
| gr86 유지비 | 45 | 4.2% | 3.1 | $3.87 | $0.086 | 높음 | car.rotcha.kr |
| 스타일런 2026 | 32 | 5.8% | 2.4 | $2.95 | $0.086 | 높음 | car.rotcha.kr |

*추정수익 = 비례배분 추정치 (블로그 내 단위 클릭가치는 동일 — 2-1 참조).

## 섹션 3: 발행 전략 엔진 [승인됨 + rev.2 보강]

### 3-1. 목적
키워드 분석 결과를 다음에 발행할 글을 고르는 입력값으로 전환. "이 키워드는 이미 수익이 나니 비슷한 글을 더 쓰자" 또는 "단가 좋은 키워드의 노출을 늘리자" 같은 의사결정을 자동 제안.

### 3-2. 키워드 4분면 분류 (설명용 — rev.2에서 "설명 도구"로 격하)

4분면은 **직관적 설명용**으로만 유지한다 (실제 추천 우선순위는 3-3 점수 사용):

- **A (단가↑, 클릭↑)**: 현재 수익의 핵심. 유사 키워드로 확장 발행.
- **B (단가↑, 클릭↓)**: 아직 노출 적지만 단가 좋음 → 신규 발행 1순위 후보.
- **C (단가↓, 클릭↑)**: 트래픽은 오는데 단가 낮음 → CTA/제휴/광고 배치 최적화 대상.
- **D (단가↓, 클릭↓)**: 관찰만.

단, rev.2 2-1에 따라 **단가(estimated_revenue_per_organic_click)는 블로그 레벨 상수**이므로, 4분면의 단가 축은 **블로그 간 비교**에서만 유효하다. 블로그 내부 키워드 비교에는 4분면 대신 클릭/CTR/순위와 예상 증분수익(2-3)을 사용한다.

### 3-3. 추천 점수 (rev.2 신설 — 실제 우선순위)

실제 발행 추천 우선순위는 4분면이 아닌 **점수**로 결정한다:

```
recommendation_score = w1 × expected_incremental_revenue
                     − w3 × risk_score
   (신뢰도 낮음이면 score × 0.5 페널티, guardrail G8/G9 위반 시 risk_score 증가)

초기 가중치: w1=1.0, w3=0.2 (config에서 조정 가능)
content_cost_estimate: Phase 2 전까지 추천 점수에서 제외.
  Phase 2 구현 시점에 조사·작성·검수 비용 기반 1~3등급 rubric을 정의한 뒤 점수에 추가한다.
```

- `expected_incremental_revenue`: 2-3 정의 (증분 클릭 × 블로그 단가 — 이중 곱 금지).
- `risk_score`: cannibalization 위험(G8), 색인 위험(G9), 경쟁 강도(기존 상위 순위 글 존재 여부).
- 점수는 **대시보드 추천 카드에 표시**하고, 근거(각 구성요소 값)를 함께 노출한다.

### 3-4. 발행 추천 생성 (Phase 2 — 수동 제안)

출력 형식: 대시보드 "발행 추천" 카드 목록 (키워드, score, 예상 증분수익, 신뢰도, 제안 제목, 근거).

예상 증분 클릭 산출: 동일 키워드 최근 28일 평균 클릭을 기본값 (데이터 없으면 유사 키워드 평균 보정, 신뢰도 낮음 표시).

**Phase 2는 제안만** (에이전트가 직접 발행하지 않음 — human_approval 경계 유지). 사용자 승인 시 기존 체인 발행 파이프라인에 주제로 전달.

### 3-5. 피드백 루프 (발행 후 측정)
- 발행된 글의 키워드가 새 데이터 주기에 나타나면 → 예상 증분수익 vs 실제 증분수익 비교 (G9 색인 확인 선행).
- "추천 → 발행 → 28일 후 재평가" 주기 폐쇄 (성숙도 L4의 핵심 루프).

### 3-6. 한계 (명시적)
- GSC 데이터가 14일분(얇음) → 초기 점수 신뢰도 낮음 → Phase 0 수집 복구가 전체의 전제 조건.
- 2-1 비례배분 한계로 인해 키워드 단위 단가 변별 불가 — 점수는 클릭/CTR/순위 기반 예상 증분수익이 주축.
- true EPC(실측 attribution)는 데이터 소스 부재로 미제공 (2-2) — 추정치와 혼동 금지.

## 섹션 4: AdSense 수집 복구 + Phase 0 품질 게이트 [승인됨 + rev.2 보강]

### 4-1. 문제 요약 (감사에서 검증됨)
- 데이터 공백 3주: `adsense_daily` 최신 데이터 2026-07-28.
- 원인 판정: OAuth 만료 아님 (토큰 8/18~8/19 갱신 중). GA4 토큰 갱신 시 `oauth2.googleapis.com DNS 해석 실패` 반복 + 8/11 이후 launchd 프로세스 hang (PID 746 등 5개 프로세스 8/11 상태로 생존).
- 계정 누락: `analytics_collector.py:644` `for account_num in [1, 2]:` — 계정3(aikorea24) 수집 안 됨.
- 매핑 부재: `adsense_daily.domain` → blog_id 매핑 없음.
- grain 문제: `gsc_pages` 0행 (A1 연결 불가).

### 4-2. 복구 작업 정의

| # | 작업 | 설명 | 위험 |
|---|------|------|------|
| R1 | hang 프로세스 정리 | 8/11 hang된 PID 746/738/948/859/950 kill + watchdog/launchd 재시작 | 낮음 |
| R2 | DNS/네트워크 확인 | oauth2.googleapis.com 해석 실패 원인 확인 (네트워크/프록시) | 정보 수집 |
| R3 | 수집 복구 | `collect_analytics.sh` 수동 1회 실행 → 성공/실패 확인 | 낮음 — GET 전용 |
| R4 | 계정3 추가 | collector loop에 account 3 (aikorea24) 포함 | 중간 — 토큰/시크릿 이미 존재 |
| R5 | 도메인→blog_id 매핑 | `adsense_daily.domain` ↔ `blog_lifecycle` 매핑 테이블/로직 생성 (config/blogs.d 기반) | 중간 — 인벤토리 밖 도메인 분리 필요 |
| R6 | 소급 데이터 | GSC 16개월 조회 API로 부분 복구. AdSense는 API 조회 기간 제한 확인 후 가능 범위만 | 정보 수집 |
| R7 | gsc_pages 수집 (rev.2 추가) | A1(query↔page) 연결용 gsc_pages 채움 (페이지 dimension 수집) | 중간 — GSC API page dimension 포함 |
| R8 | grain·중복 검증 (rev.2 추가) | gsc_keywords/gsc_pages/ga4_pages/adsense_daily 중복·결측 스캔 | 낮음 |

### 4-3. 실행 경계
- R1~R3: full_auto 가능 (수집 파이프라인 복구, 낮은 위험)
- R4~R8: human_approval (계정 추가·매핑·수집 로직은 코드 변경)

### 4-4. Phase 0 완료 조건 + 품질 게이트 (rev.2 확장)

| # | 게이트 | 통과 기준 |
|---|--------|-----------|
| Q1 | AdSense 최신성 | 수집 실행 후 `adsense_daily`에 최근 3일 이내 date 행 존재 (연속 일자 확인) |
| Q2 | 계정3 수집 | `adsense_daily`에 aikorea24 도메인 행 존재 (계정3 경유) |
| Q3 | domain/blog 매핑 | 매핑 커버리지 = (인벤토리 내 매핑된 도메인 ÷ 인벤토리 전체 도메인) ≥ 95%. 미매핑 목록 출력 (인벤토리 밖 도메인은 별도 분리 표시) |
| Q4 | GA4/GSC grain | `gsc_pages` 행 > 0 (A1 연결 가능), `ga4_pages` 커버리지 = blog_lifecycle 대비 ≥ 90%, `gsc_keywords` 28일 연속 존재 |
| Q5 | 중복/결측 | (blog_id,date,query) 중복 0건, adsense_daily UNIQUE(account,domain,date) 위반 0건, 필수 컬럼 NULL 0건 |
| Q6 | 소급 데이터 | R6 결과 기록 — 복구 가능 기간 문서화, 불가 기간 명시 |

### 4-5. 완료 정의 (Phase 0)
- Q1~Q6 전부 통과 시 Phase 0 완료. 하나라도 실패 시 해당 항목만 재수행.

## 섹션 5: 구현 범위/우선순위 [승인됨 + rev.2 보강]

### 5-1. 구현 순서

| Phase | 범위 | 내용 |
|-------|------|------|
| Phase 0 | 수집 복구 + 품질 게이트 | 섹션 4 R1~R8 + Q1~Q6 (AdSense 복구, 계정3, 매핑, gsc_pages, 중복·결측 검증) |
| Phase 1 | 분석 대시보드 | R5 매핑 적용, L1~L3 지표 API·화면, 2-1 한계 표시, guardrail G1~G9, "추정" 라벨 |
| Phase 2 | 발행 전략 엔진 | 2-3 예상 증분수익 + 3-3 추천 점수, 추천 카드 (제안만, human_approval) |
| Phase 3 | 피드백 루프 | 추천→발행→28일 재평가 + G9 색인 모니터 (L4 수익 최적화) |
| Phase 4 | (후속) | 제휴 subId+reporting (true EPC 실측화), A/B 실험 |

### 5-2. 중복 개발 금지
- AdSense 수집 파이프라인 (기존 `com.5000.analytics` + `analytics_collector.py` 재사용)
- data/dashboard revenue API·화면 (기존 5050 대시보드 확장 — 신규 대시보드 아님)
- coupang_* 링크 생성 (기존 재사용, subId만 추가)
- funnel_tracking 스키마 (기존 재사용)
- blog_efficiency (기존 재사용)
- scheduler/dispatcher/플레이북 구조 (기존 재사용)

### 5-3. 완료 기준 (전체)
- 대시보드에 키워드별 추정 수익·클릭·CTR·평균순위 표시 + 단위 클릭가치 한계 표기
- 발행 추천 카드가 3-3 점수 기반으로 생성 (예상 증분수익·신뢰도·근거 포함)
- 추천→발행→28일 재평가 루프가 동작, G9 색인 미확인 플래그 포함

## 공식 예제 모음 (rev.2 — acceptance test 입력값)

**E1. 비례배분 (2-1)**: 블로그 일일 AdSense $10, 일일 GSC 클릭 100.
- 키워드 A 클릭 45 → estimated_keyword_revenue = 45/100 × $10 = **$4.50**
- 키워드 B 클릭 10 → estimated_keyword_revenue = 10/100 × $10 = **$1.00**
- 단위 클릭가치 A = 4.50/45 = **$0.10**, B = 1.00/10 = **$0.10** (동일 — 상수 검증)

**E2. 증분수익 (2-3)**: 블로그 단위 클릭가치 $0.10, 신규 글 예상 증분 클릭 30/월.
- expected_incremental_revenue = 30 × $0.10 = **$3.00/월**
- 오검증: 30 × estimated_keyword_revenue($4.50) = $135 — **이중 곱 (금지 케이스)**

**E3. shrinkage (G2)**: 블로그 평균 단가 $0.10, 키워드 샘플 단가 $0.20, 클릭 5, prior_weight 10.
- shrunk = (5×0.20 + 10×0.10) ÷ (5+10) = (1.0+1.0)/15 = **$0.133**

## Acceptance Criteria (rev.2)

| AC | 검증 항목 | 기준 | 검증 수단 |
|----|-----------|------|-----------|
| AC-1 | estimated_keyword_revenue 계산 | E1 수치와 일치 (A=$4.50, B=$1.00) | 단위 테스트 |
| AC-2 | 단위 클릭가치 상수성 | 블로그 내 모든 키워드의 단위 클릭가치 = Revenue÷ΣClicks (E1: $0.10) | 단위 테스트 |
| AC-3 | 이중 곱 금지 | expected_incremental_revenue 계산이 E2 규칙 준수 (단가=②, 클릭 1회만) | 코드 리뷰 + 테스트 |
| AC-4 | shrinkage | E3 수치와 일치 ($0.133) | 단위 테스트 |
| AC-5 | 명칭 규칙 | UI/API에 "키워드 EPC" 표현 0건, "추정 수익"/"유기 클릭당 추정 수익" 사용 | grep |
| AC-6 | guardrail 적용 | G1(클릭<3 숨김), G3(28일), G4(지연 마커), G8(cannibalization), G9(색인 플래그) 동작 | 통합 테스트 |
| AC-7 | true EPC 미표시 | attribution 데이터 부재 상태에서 true EPC 필드 미노출 (추정 금지) | 대시보드 스모크 테스트 |
| AC-8 | Phase 0 게이트 | Q1~Q6 전부 통과 로그 기록 (부분 통과 시 실패 항목 명시) | 실행 로그 |
| AC-9 | 추천 점수 | 3-3 점수식 구성요소(증분수익, 리스크, 신뢰도) 모두 표시, content_cost_estimate는 Phase 2 전까지 점수에 미포함 | API 응답 검사 |

## 참조 문서

- `REVENUE_CAPABILITY_AUDIT.md` (2026-08-20, READ-ONLY 감사)
- `REVENUE_MATURITY_ROADMAP.md` (2026-08-20)