# INCIDENT_GOLF_FLIGHTS.md

> **진단 시각**: 2026-08-19 08:50 KST
> **진단 유형**: READ-ONLY — 코드·설정·DB 수정·재실행·수동 발행 없음

---

## A. golf-hugo 연속 실패 진단

### 실행별 재구성 (최근 7회)

| # | 시각 | reason | keyword 선택 시도 | 30일 중복 차단 | relevance 진입 | products 수집 | 최종 |
|---|------|--------|------------------|---------------|---------------|--------------|------|
| 1 | 08-17 13:18 | no_keyword | _select_keyword → None | 6/12 소진 | 6개 통과 | 6개 전부 3개 이상 | **relevance gate 차단** (0.00~0.50 < 0.75) |
| 2 | 08-17 13:24 | no_keyword | 동일 | 동일 | 동일 | 동일 | 동일 |
| 3 | 08-17 14:05 | no_keyword | 동일 | 동일 | 동일 | 동일 | 동일 |
| 4 | 08-18 23:46 | no_keyword | 동일 | 동일 | 동일 | 동일 | 동일 |
| 5 | 08-19 08:39 | no_keyword | 동일 | 동일 | 동일 | 동일 | 동일 |
| 6 | 08-19 08:42 | no_keyword | 동일 | 동일 | 동일 | 동일 | 동일 |
| 7 | 08-19 08:48 | no_keyword | 동일 | 동일 | 동일 | 동일 | 동일 |

**모든 run이 동일한 원인** — 매번 `_select_keyword()`가 None을 반환.

### 키워드 풀 현황

| 구분 | 키워드 | 수 |
|------|--------|-----|
| 전체 키워드 | 골프클럽, 골프드라이버, 아이언세트, 골프백, 골프거리측정기, 골프화, 퍼터, 골프공, 골프장갑, 골프의류, 골프우산, 스윙연습기 | 12 |
| 30일 내 사용 | 골프백(8/16), 스윙연습기(8/9), 퍼터(8/8), 골프장갑(8/6), 골프공(8/6), 골프화(8/5) | 6 |
| **사용 가능** | 골프클럽, 골프드라이버, 아이언세트, 골프거리측정기, 골프의류, 골프우산 | **6** |

### _select_keyword() 량 분해

```
get_keywords('golf-hugo') = 12개
  → used_set (30일) = 6개 제거 → available = 6개
  → quarantine = 0개 제거
  → low_relevance (14일) = 0개 제거
  → available = 6개 잔존 ← 키워드 고갈 아님!
  → cat_filtered = 6개 통과
  → products ≥3 체크 = 6개 전부 통과 (12~21개)
  → relevance gate = 6개 전부 탈락 (avg 0.00~0.50 < threshold 0.75)
  → return None ← 유일한 차단 지점
```

### 핵심: relevance gate가 유일한 차단 지점

| keyword | products 샘플 스코어 | threshold | 결과 |
|---------|---------------------|-----------|------|
| 골프클럽 | 0.33 | 0.75 | FAIL |
| 골프드라이버 | 0.00 | 0.75 | FAIL |
| 아이언세트 | 0.17 | 0.75 | FAIL |
| 골프거리측정기 | 0.50 | 0.75 | FAIL |
| 골프의류 | 0.50 | 0.75 | FAIL |
| 골프우산 | 0.50 | 0.75 | FAIL |

**왜 score가 낮은가?** `score_product()`가 `product_name + " " + category_name`에서 `allowed` 키워드를 substring 매칭:
- 골프 상품명에 "골프"가 없는 경우 다수 (예: "핑 G440 스틸 아이언", "야마모토 남성용 드라이버")
- category_name은 "스포츠/레저" → "골프" 미포함
- `min_keyword_matches=2`라 1개만 매칭되면 score=0.50으로 0.75 미달

### 기존 진단과 비교

| 기존 진단 | 검증 결과 |
|-----------|-----------|
| "키워드 풀 12개 고갈→_select_keyword() None" | **부분 정확** — 30일 중복으로 6개 소진되지만, 나머지 6개는 products ≥3 통과 → 완전 고갈 아님 |
| "collect_keyword() 미호출" | **정확** — relevance gate에서 전부 탈락하므로 collect_keyword() 호출 없음 |

### car-hugo 및 정상 curation 블로그 비교

| 블로그 | publish_log 수 | 최근 성공 | relevance 설정 | 특이사항 |
|--------|----------------|-----------|---------------|---------|
| laptop-hugo | 178 | 정상 | threshold 0.65 (오버라이드) | "노트북" substring 매칭 용이 |
| interior-hugo | 302 | 정상 | threshold 0.55 (오버라이드) | "인테리어" substring 매칭 용이 |
| **golf-hugo** | **6** | **08-16 이후 0건** | **threshold 0.75 (default)** | **골프 상품 브랜드명 위주** |

**핵심 차이**: laptop/interior는 `RELEVANCE_CONFIG`에 별도 임계값이 있어 relevance gate를 통과하지만, golf-hugo는 default 0.75로 골프 상품 스코어(0.00~0.50)를 통과하지 못함.

### 키워드 풀 확장·중복 기간 재설계·선수집 방식 장단점

| 방안 | 장점 | 단점 | 최소 안전 수정안 |
|------|------|------|----------------|
| **relevance 임계값 완화** | 코드 변경 없음 (config만) | 품질 게이트 완화 | `relevance_scorer.py`에 `"golf-hugo": {"threshold": 0.50}` 한 줄 |
| **키워드 풀 확장** | 더 많은 후보 확보 | 골프 상품 카테고리 제한적 | keywords.py에 4-6개 추가 |
| **30일→14일 중복 기간** | 빠른 키워드 순환 | 콘텐츠 반복 리스크 | pipeline.py에서 days 파라미터 변경 |
| **CATEGORY_FILTERS 확장** | 매칭 스코어 상승 | 허용 키워드 범위 확대 | pipeline.py golf-hugo allowed에 추가 |

### 최소 안전 수정안

**1순위 (config 변경만, 코드 수정 없음)**:
```python
# shared/relevance_scorer.py RELEVANCE_CONFIG에 추가
"golf-hugo": {"threshold": 0.50},
```

**근거**: interior-hugo(0.55), camping-hugo(0.55) 등과 동일 패턴. 골프 상품은 "핑 G440" 같은 브랜드명이 product_name에 있어 "골프" substring 매칭 실패 빈번.

**2순위 (선택적, config 변경)**:
```python
# pipelines/curation/keywords.py에 키워드 추가
"골프티", "골프모자", "골프양말", "골프공주머니"
```
단, relevance gate가 여전히 0.75면 추가해도 탈락 가능 → 1순위 병행 필요.

---

## B. flights-hugo 실패 진단

### 실행별 재구성 (최근 4회 실패 + 1회 성공)

| # | 시각 | slug | route | reason | pipeline_status | 비고 |
|---|------|------|-------|--------|-----------------|------|
| 1 | 08-17 14:17 | cheapest-flights-den-to-sea | den→sea | content_quality_gate | FAILED_TRANSIENT | |
| 2 | 08-17 14:24 | cheapest-flights-dfw-to-atl | dfw→atl | content_quality_gate | FAILED_TRANSIENT | |
| 3 | 08-17 16:37 | cheapest-flights-bos-to-orl | bos→orl | content_quality_gate | FAILED_TRANSIENT | |
| 4 | 08-19 08:40 | cheapest-flights-den-to-tpa | den→tpa | content_quality_gate | FAILED_TRANSIENT | |
| 5 | 08-19 08:42 | cheapest-flights-den-to-tpa | den→tpa | content_quality_gate | FAILED_TRANSIENT | 동일 route 재시도 |
| **6** | **08-19 08:50** | **cheapest-flights-sea-to-slc** | **sea→slc** | **ok** | **SUCCESS** | **새 route로 성공** |

### 실패 분류

| 분류 | 해당 여부 | 근거 |
|------|-----------|------|
| 입력 부족 | ❌ 아님 | route 데이터는 정상 수집됨 |
| LLM 생성 결함 | ❌ 아님 | content이 생성됨 (draft status) |
| 후처리 손상 | ❌ 아님 | Hugo frontmatter 정상 |
| **검사기 오판** | ❌ 아님 | quality gate가 의도대로 동작 |
| **템플릿/데이터 품질** | **✅ 해당** | 특정 route의 항공편 데이터가 품질 기준 미달 |

**근본 원인**: 특정 출발지→도착지 route의 항공편 데이터가 `content_quality_gate` 기준 미달.
- den→sea, dfw→atl, bos→orl, den→tpa: 모두 탈락
- sea→slc: 성공 — 데이터 품질이 route마다 다름

### 마지막 정상 발행

| 항목 | 값 |
|------|-----|
| 시각 | 2026-08-19 08:50:09 |
| slug | cheapest-flights-sea-to-slc |
| title | Planning a Trip? Cheapest Flights from SEA to SLC Compared |
| status | ok |

### 같은 pipeline 블로그와 비교

| 블로그 | 파이프라인 | 최근 실패 패턴 | self-healing |
|--------|-----------|---------------|-------------|
| flights-hugo | etap | route-specific quality gate | ✅ 다른 route 시도 → 성공 |
| foodtour-hugo | etap | pipeline_returned_false | ❌ 지속 실패 |
| tour-hugo | etap | — | 정상 |

**flights-hugo는 self-healing이 작동하는 상태** — 실패 후 다른 route를 시도하여 성공.

---

## C. 근본원인·영향 범위·최소 수정안·테스트·롤백안

### golf-hugo

| 항목 | 값 |
|------|-----|
| **근본원인** | relevance gate 임계값(0.75)이 골프 상품 브랜드명 매칭 스코어(0.00~0.50)보다 높음 |
| **신뢰도** | **높음** — 7회 연속 동일 원인, 키워드 풀 6개 전부 탈락 확인 |
| **영향 범위** | golf-hugo만 해당. 다른 curation 블로그는 별도 임계값 오버라이드 |
| **최소 수정안** | `relevance_scorer.py`에 `"golf-hugo": {"threshold": 0.50}` 추가 (config 변경 1줄) |
| **테스트** | golf-hugo 1회 실행 → `_select_keyword` 반환값 확인 (None이 아닌 keyword) |
| **롤백안** | 추가된 줄 삭제 (config 변경이므로 코드 롤백 불필요) |

### flights-hugo

| 항목 | 값 |
|------|-----|
| **근본원인** | 특정 route의 항공편 데이터가 content_quality_gate 기준 미달 (route별 데이터 품질 차이) |
| **신뢰도** | **높음** — 4회 실패 모두 route-specific, 5th attempt에서 새 route로 성공 |
| **영향 범위** | flights-hugo만 해당. 일시적 실패, self-healing 동작 |
| **최소 수정안** | **불필요** — 파이프라인이 자동으로 다른 route를 시도하여 성공 |
| **테스트** | flights-hugo 정규 스케줄에서 다음 성공 확인 |
| **롤백안** | 불필요 — 현재 상태가 정상 동작 |

### 코드·설정·프롬프트·API 변경 대조

| 변경 | golf-hugo | flights-hugo |
|------|-----------|-------------|
| 최근 코드 변경 | d887e094f — curation/_select_keyword 로그만 변경 (golf-hugo 미영향) | 없음 |
| 최근 설정 변경 | 없음 | 없음 |
| 프롬프트 변경 | 없음 | 없음 |
| API 상태 | Coupang API 정상 (다른 블로그 정상 발행) | 항공편 API 정상 (route별 데이터 품질 차이) |
| quota | 정상 | 정상 (daily_quota=5, 오늘 1건 성공) |

---

## 잔존 위험

1. golf-hugo: relevance gate 임계값 미변경 시 내일도 동일 실패 예상
2. flights-hugo: self-healing이 작동하나, 특정 시간대에 모든 route가 탈락할 가능성 존재
3. 두 장애 모두 **재실행·수동 발행·threshold 변경 없이** 진단 완료 — 수정안은 별도 작업으로 수행 필요

> **이 보고서는 READ-ONLY 진단만 수행했습니다. 코드/설정/DB 변경·재실행·수동 발행·pause·scheduler 재시작은 수행하지 않았습니다.**
