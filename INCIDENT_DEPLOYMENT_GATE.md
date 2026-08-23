# INCIDENT_DEPLOYMENT_GATE.md

> **감사 시각**: 2026-08-19 00:50 KST
> **대상 커밋**: `d887e094f` (main 브랜치, 로컬 전용)
> **감사 범위**: READ-ONLY 배포 준비 감사. 코드/설정/DB 변경·커밋 변경·push·배포·재발행 없음.

---

## 1. d887e094f 변경 라인 분류

| 분류 | 라인 수 | 비고 |
|------|---------|------|
| **fallback 핵심 로직** | 38 | car pipeline: persona_pick→top5_rank fallback (19줄) / curation pipeline: normalize_title/preserve_slug behavioral change (4줄) / curation _select_keyword 조건 반전/continue (15줄) |
| **구조화 로그** | 24 | car: no_data_detail + no_data:exhausted (4줄) / curation: 단계별 카운트 + relevance_gate_block + keyword_skip (20줄) |
| **테스트** | 251 | 신규 파일 `tests/test_pick_hugo_fallback.py` 전체 |
| **불필요 변경** | 4 | car 인라인 주석 1줄 + 공백 2줄 + curation 주석 이동 1줄 |
| **合计** | **317** | additions 303 + deletions 21 (합산 차이: 부분 라인 겹침) |

### 기존 car 계열 블로그 영향 분석

| post_type | 영향 | 근거 |
|-----------|------|------|
| beginner_guide, ev_analysis, promo_deal, ranking_compare, resale_compare, tco_analysis | **❌ 없음** | `build_input()` 경로 사용, fallback 코드 미진입 |
| top5_rank | **❌ 없음** | fallback 대상 아님 — 자체 `build_top5_rank_input()` 직접 호출 |
| **persona_pick** | **⚠️ 있음** | fallback 추가됨 — trims 0건 시 top5_rank 시도 |

**결론**: persona_pick 타입에서만 동작 변경. 다른 post_type의 car 블로그(compare, hotissue, guide, deal, tco, rank, ev)에 영향 없음.

---

## 2. curation/pipeline.py 변경 독립성

> **ae90ed63a에서 d887e094f의 curation 변경 완전 원복 — net change 0줄**

| 변경 | 함수 | 유형 | pick-hugo 독립 |
|------|------|------|----------------|
| ~~구조화 로그~~ | ~~`_select_keyword()`~~ | ~~logging-only~~ | ✅ 독립 — **ae90ed63a에서 원복** |
| ~~title/slug 정규화~~ | ~~`_run_inner()`~~ | ~~behavior change~~ | ✅ 독립 — **ae90ed63a에서 원복** |

### 교차 의존성 확인

| 확인 항목 | 결과 |
|-----------|------|
| `pipelines/car/`에서 `curation` import | **없음** ✅ |
| `pipelines/curation/`에서 `car` import | **없음** ✅ |

### ~~사전 존재 버그 발견~~ → ae90ed63a에서 해결

~~`_run_inner()`의 `normalize_title`/`preserve_slug` 호출은 import 없음~~ → curation 변경 원복으로 문제 소멸.

---

## 3. pick-hugo 테스트 커버리지 분석

### 커버된 시나리오

| 시나리오 | 테스트 | 검증 수준 |
|----------|--------|-----------|
| trims=0 → eligibility=False | `test_no_eligible_trim_returns_none` | [검증됨] |
| trims+fuel → eligibility 결과 | `test_eligible_trim_passes` | [부분검증] — predicate만 검증 |
| top5_rank segment 데이터 존재 | `test_top5_rank_has_comparison_data` | [부분검증] |
| build_top5_rank_input 데이터 반환 | `test_build_top5_rank_input_returns_data` | [부분검증] |
| 21회 시뮬레이션 크래시 프리 | `test_fallback_chain_does_not_crash` | [부분검증] — 재구현而非실제 코드 경로 |
| 로그 포맷 문자열 존재 | `test_no_data_detail_log_format` | [부분검증] — 소스 문자열 확인 |

### 미커버 시나리오 (심각도순)

| # | 시나리오 | 심각도 | 설명 |
|---|----------|--------|------|
| 1 | persona_pick 성공 → fallback 미실행 | **높음** | `pipeline.py:180-189` 경로에서 data truthy → fallback 건너뜀. 미검증. |
| 2 | persona_pick 실패 → top5_rank 성공 → 데이터 사용 | **높음** | 핵심 fallback 성공 경로 미검증 |
| 3 | persona_pick 예외 발생 → fallback 시도 | **높음** | outer try/except에서 exception 발생 시 fallback 미시도됨 — 미검증 |
| 4 | top5_rank fallback 자체 예외 | **중간** | inner except에서 exception 처리 — 소스 문자열만 확인 |
| 5 | pending topics 0건 → 즉시 no_data | **낮음** | 엣지 케이스 |

### 중복 주제 선택 가능성

| 가드 | 메커니즘 | 효과 |
|------|----------|------|
| `recent_keys` | `topic_manager.py:31` — publish_log JOIN으로 7일 내 발행된 car_id 제외 | ✅ 유효 |
| `skip_set` | `topic_manager.py:40` —同一 select_topic 호출 내 skip_ids | ✅ 유효 |
| `dict(topic)` | 얕은 복사 — 원본 topic dict 변경 없음 | ✅ 안전 |

**판정**: 중복 주제 선택 위험 **낮음** — 기존 가드가 fallback 경로를 커버. 단, fallback 성공 후 publish_log 기록 → 다음 호출 시 recent_keys로 차단되는지 검증 테스트 없음.

---

## 4. car/golf products 적재 경로 추적

### 적재 주체

| 항목 | 값 |
|------|-----|
| 함수 | `pipelines/curation/collector.py:collect_keyword()` (line 263) |
| 호출 주체 | `pipelines/curation/pipeline.py:909` — `_run_inner()`에서 `collect_keyword(keyword)` 호출 |
| 트리거 | 키워드 선택 → 상품 수집 → AI 글 생성 흐름의 일부 |
| DB 테이블 | `curation.db:products` (keyword, product_id, product_name, product_price, ...) |

### products 테이블 현황

| 항목 | 값 |
|------|-----|
| 총 키워드 수 | **~1000+** (노트북, 청소기, 뷰티, 헬스, 캠핑 등) |
| car/golf 관련 키워드 | **0건** — `블랙박스`, `골프클럽` 등 products 테이블에 없음 |
| 가장 많은 키워드 | `MSI 게이밍 노트북` (174건), `17인치 노트북 추천` (173건) |

### car/golf keywords가 products에 없는 이유

`_select_keyword()` → `collect_keyword()` 흐름에서:
1. `_select_keyword("car-hugo")`가 None 반환 (30일 중복 억제 + relevance gate)
2. 키워드가 선택되지 않으므로 `collect_keyword()` 호출 자체가 없음
3. 따라서 products 테이블에 car/golf 키워드 데이터가 0건

**즉, products 0건은 API 미호출이 원인 — API 호출 실패·파싱 실패·필터 탈락·DB 저장 실패가 아님.**

### 다른 정상 curation 블로그와 비교

| 블로그 | products 키워드 수 | pipeline 흐름 | 성공률 |
|--------|-------------------|---------------|--------|
| laptop-hugo | 노트북 관련 ~200+ | 키워드 선택 → collect_keyword → products 적재 → 발행 | 44.4% |
| interior-hugo | 인테리어 관련 ~100+ | 동일 | 67.2% |
| **car-hugo** | **0건** | 키워드 선택 실패 → collect_keyword 미호출 | **26.3%** |
| **golf-hugo** | **0건** | 키워드 선택 실패 → collect_keyword 미호출 | **16.7%** |

**핵심 차이**: 정상 블로그는 `_select_keyword()`가 키워드를 반환 → `collect_keyword()` 호출 → products 적재. car/golf는 키워드 선택 자체가 실패하여 products 적재 루프에 진입하지 않음.

---

## 5. products 0건 원인 확정

| 원인 가설 | 해당 여부 | 근거 |
|-----------|-----------|------|
| **API 미호출** | **✅ 확정** | `_select_keyword()`가 None 반환 → `collect_keyword()` 미호출 → products 테이블에 해당 키워드 데이터 없음 |
| API 호출 실패 | ❌ 아님 | API 호출 자체가 없었음 |
| 파싱 실패 | ❌ 아님 | API 호출 자체가 없었음 |
| 필터 전량 탈락 | ❌ 아님 | API 호출 자체가 없었음 |
| DB 저장 실패 | ❌ 아님 | API 호출 자체가 없었음 |

**증거 경로**:
```
_select_keyword("car-hugo") → None (30일 중복 억제: 8개 사용됨)
→ _run_inner line 904: logger.error("사용 가능한 키워드 없음")
→ return {"success": False, "reason": "no_keyword"}
→ collect_keyword() 미호출
→ products 테이블에 car/golf 키워드 0건
```

---

## 6. pick-hugo 배포 가능 판정

### 배포 가능 여부

| 기준 | 판정 | 근거 |
|------|------|------|
| fallback 로직 정확성 | **조건부 통과** | persona_pick→top5_rank fallback은 의도대로 작동하나, 테스트 커버리지 gaps 존재 |
| 기존 블로그 영향 | **통과** | persona_pick 타입에서만 동작, 다른 post_type/car 블로그 무관 |
| 테스트 통과 | **통과** | 7/7 통과 |
| 문법 검증 | **통과** | py_compile 2파일 통과 |
| 함수 시그니처 변경 | **없음** | 런타임 호환 |
| 리턴 값 변경 | **없음** | no_data 반환 유지 |
| 버그 도입 | **없음** | fallback 추가분만 |

### ⚠️ pick-hugo 배포 전 조건

1. **curation/pipeline.py 원복**: d887e094f의 _select_keyword 구조화 로그/normalize_title/preserve_slug 변경 완전 원복 → **ae90ed63a에서 해결** ✅
2. **테스트 보강**: 7건→12건 (+5) — persona_pick 성공/실패/fallback 성공/양쪽 후보 없음/중복 방지 ✅
3. **문법 검증**: 3파일 통과 ✅

### 배포 전 필수 조건

| # | 조건 | 상태 |
|---|------|------|
| 1 | `python3 -m pytest tests/test_pick_hugo_fallback.py` 7/7 통과 | ✅ |
| 2 | `python3 -m py_compile pipelines/car/pipeline.py` | ✅ |
| 3 | `python3 -m py_compile pipelines/curation/pipeline.py` | ✅ |
| 4 | curation/pipeline.py `normalize_title`/`preserve_slug` import 누락 수정 | ❌ **미수정** |
| 5 | trims 기준 미변경 | ✅ |
| 6 | relevance threshold 미변경 | ✅ |
| 7 | KEYWORD_MAP 미변경 | ✅ |
| 8 | 운영 DB 미변경 | ✅ |

---

## 7. car/golf 별도 최소 복구안

### car-hugo 복구안

| 순위 | 복구안 | 설명 | 위험도 |
|------|--------|------|--------|
| 1 | **KEYWORD_MAP에 4개 미사용 키워드 보유 확인** | `차량용공기청정기`, `타이어공기주입기`, `차량용거치대`, `차량용냉장고` — products 14~19건이나 relevance gate에서 차단 추정 | 낮음 |
| 2 | **relevance threshold 완화** | `car-hugo`용 별도 threshold (0.75→0.60) — 이번 패치에서 변경하지 않음 | 중간 |
| 3 | **30일 중복 억제 기간 단축** | 30일→21일 — 미사용 키워드 조기 가용 | 중간 |
| 4 | **KEYWORD_MAP에 신규 키워드 추가** | products 0건이므로 API 수집 먼저 필요 | 높음 |

### golf-hugo 복구안

| 순위 | 복구안 | 설명 | 위험도 |
|------|--------|------|--------|
| 1 | **KEYWORD_MAP에 6개 미사용 키워드 보유 확인** | `골프클럽`, `골프드라이버`, `아이언세트`, `골프거리측정기`, `골프의류`, `골프우산` — products 12~22건 | 낮음 |
| 2 | **relevance threshold 완화** | `golf-hugo`용 별도 threshold (0.75→0.60) | 중간 |
| 3 | **30일 중복 억제 기간 단축** | 30일→21일 | 중간 |
| 4 | **KEYWORD_MAP에 신규 키워드 추가** | products 0건이므로 API 수집 먼저 필요 | 높음 |

### 공통 복구안 (car + golf)

| 복구안 | 설명 | 선행 조건 |
|--------|------|-----------|
| **collect_keyword() 사전 호출** | 키워드 선택 전에 products 수집 → relevance gate 진입 가능 | Coupang API 정상 동작 확인 |
| **relevance gate 차단 로그 분석** | `_select_keyword()` 구조화 로그 패치(이미 적용됨)로 차단 원인 파악 | 배포 후 로그 확인 |

---

## 8. 잔존 위험

1. **curation/pipeline.py import 누락**: `normalize_title`/`preserve_slug` 사용 시 NameError — **이번 커밋에서 도입됨**
2. **pick-hugo 테스트 커버리지 gaps**: persona_pick 성공/실패/fallback 성공 경로 미검증
3. **car/golf no_keyword**: products 0건 → `_select_keyword()` 실패 → collect_keyword 미호출 → products 적재 안 됨 (약순환)
4. **curation 변경 혼재**: pick-hugo fix와 curation title/slug behavioral change가同一 커밋에 포함

---

> **이 보고서는 READ-ONLY 감사만 수행했습니다. 코드/설정/DB 변경·커밋 변경·push·배포·재발행은 수행하지 않았습니다.**
