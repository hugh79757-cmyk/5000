# 5000 발행 오류 Root Cause Analysis

**Date:** 2026-07-08
**Scope:** curation 파이프라인 (laptop-hugo, health-hugo, interior-hugo, baby-hugo) + STAP ipo pipeline (ipo-hugo)
**Goal:** 오류 원인 파악 및 개선 방안 제시

---

## 1. Executive Summary

최근 target 5개 블로그에서 집중 발생한 오류는 세 가지 근본 원인에서 비롯됨:

| 원인 | 영향 블로그 | 증상 |
|------|------------|------|
| **Keyword pool 오염 (generic keyword)](pipelines/curation/keywords.py)** | health-hugo, interior-hugo, laptop-hugo, baby-hugo | 쿠팡 검색 결과가 블로그 주제와 무관 → `low_relevance` / `irrelevant_products` |
| **Title template 중복 + return dict 버그** | laptop-hugo, baby-hugo, health-hugo, interior-hugo | AI가 생성한 "1위 X vs Y — 2026년 7월 ..." 제목끼리 반복 매칭 → `similar_title`, 알림에서는 `keyword=` 표시 |
| **STAP ipo 데이터 부족 / subprocess 불안정** | ipo-hugo | 공모주 캘린더 기간이 아니거나 STAP ipo pipeline 오류 → `no_content` |

또한 `pipelines/curation/keywords.py`에 **누락된 쉼표(syntax error)**가 여러 곳 있어 의도한 키워드가 먹히거나 병합되는 문제도 확인됨.

---

## 2. 오류별 Root Cause

### 2.1 `similar_title` — laptop-hugo / baby-hugo

**버그 1: return dict에 keyword 누락**

`pipelines/curation/pipeline.py:805`

```python
return {"success": False, "reason": "similar_title"}  # keyword 없음
```

`run()` 내부에서 `_alert_checker.maybe_alert(blog_id, reason, {"keyword": result.get("keyword", "")})`를 호출하므로 `keyword=`가 비어서 전송됨.

**근본 원인: 제목 템플릿 고착화**

실제 실패 제목 예시:

- laptop-hugo: `1위 다용도 휴대용 독서대 vs 아이리버 아크릴 접이식 — 각도조절 독서대 2026 비교`
- baby-hugo: `1위 블루씨티 vs 예스플러스 — 2026년 7월 나시 추천`
- health-hugo: `1위 DK 면장갑 35g vs 삼성 대용량 재생 잉크 — 2026년 7월 가성비 필수템 5선`

중복 체크 로직(`_title_is_duplicate`)은 3일 이내 제목에서 핵심 20자 또는 3단어 이상 겹치면 차단하지만,
"1위", "vs", "2026", "7월", "추천", "비교" 같은 공통 템플릿 단어가 stop_words에서 제거되어도
상품명/브랜드명 부분이 계속 겹쳐서 false positive를 유발함.

특히 baby-hugo에 "나시" 키워드가 들어가 있는데, 이는 블로그 주제(유아용품)와 무관하며
AI가 성인 의류 비교 제목을 생성해 반복 중복 매칭됨.

**레벨:** P0 (버그 fix) + P1 (템플릿 개선)

---

### 2.2 `low_relevance` — health-hugo (keyword=고함량)

`shared/relevance_scorer.py:6-15` 설정:

```python
RELEVANCE_CONFIG = {
    "default": {"threshold": 0.75, "min_keyword_matches": 2},
    "health-hugo": {"threshold": 0.65},
}
```

`score_product()`는 product_name + category_name에서 allowed 키워드가 몇 개 포함되는지 세서
`count / min_keyword_matches`로 평균을 냄.

키워드 `고함량`은 "고함량 비타민C", "고함량 오메가3" 등으로 검색해야 의미 있지만,
현재 pipeline은 키워드를 그대로 쿠팡 검색어로 사용함.
`고함량` 단독 검색 결과는 비타민/영양제 외에도 다양한 상품이 섞여 relevance 점수가 0.65 아래로 떨어짐.

**레벨:** P1 (keyword 선별 및 검색어 보강)

---

### 2.3 `irrelevant_products` — interior-hugo (keyword=가벼운)

`pipelines/curation/pipeline.py:397-446`의 `_filter_irrelevant_products()`는
allowed 키워드 목록과 blocked 키워드 목록을 기반으로 상품명/카테고리를 필터링함.

키워드 `가벼운`은 인테리어(가구)보다는 노트북, 여행용품, 의류 등에 흔히 쓰이는 형용사.
검색 결과 대부분이 allowed 인테리어 키워드(의자, 책상, 소파 등)를 포함하지 않거나
blocked 카테고리에 속해 필터링되어 3개 미만으로 줄어듦.

마찬가지로 laptop-hugo의 `기계식`은 기계식 키보드로 검색되지만,
laptop-hugo allowed에는 "키보드"가 blocked 목록에 들어 있어(주변기기 차단 의도) 필터링 후 상품이 0개가 됨.

**레벨:** P0 (keyword pool 정제)

---

### 2.4 `no_content` — ipo-hugo

`dispatcher.py:77-84`에 ipo-hugo는 STAP의 `ipo` pipeline으로 매핑됨.

최근 7일간 ledger를 보면 `no_content`와 `stap_subprocess_error`가 교차 발생:

- 2026-07-04~07-05: `stap_subprocess_error`가 다수
- 2026-07-08(오늘): `no_content` 1건

`no_content`는 STAP ipo pipeline에서 발행할 공모주 캘린더 데이터가 없을 때 반환하는 상태로 보임.
공모주 일정이 없는 주간에는 당연히 발생할 수 있으나, 알림은 매번 전송되어 noise가 큼.

**레벨:** P1 (no_content는 정상 상황일 수 있음 / subprocess error는 별도 점검 필요)

---

## 3. keyword_health 현황

`data/curation.db`의 `keyword_health` 테이블에서 target 블로그의 상위 실패 키워드:

| blog_id | keyword | consecutive_failures | last_failure_reason |
|---------|---------|---------------------:|---------------------|
| health-hugo | 고함량 | 3 | low_relevance |
| interior-hugo | 국내생산 | 4 | irrelevant_products |
| interior-hugo | 가벼운 | 3 | irrelevant_products |
| laptop-hugo | 기계식 | 4 | irrelevant_products |
| laptop-hugo | 노트북 | 3 | similar_title |
| baby-hugo | 공룡 | 3 | irrelevant_products |
| baby-hugo | 궁중비책 | 2 | similar_title |

→ **동일 키워드가 반복 실패하면서 전체 keyword pool의 20% 상한선(MAX_QUARANTINE_PERCENT=0.20)**까지 격리될 위험이 있음.

---

## 4. 추가 발견 사항: `keywords.py` syntax error

`pipelines/curation/keywords.py`에서 쉼표 누락으로 인한 문자열 자동 병합(concatenation)이 다수 발견:

| line | 현재 코드 | 결과 병합된 키워드 |
|------|----------|-------------------|
| 71-72 | `"도어"` `<newline>` `"그램파우치"` | `"도어그램파우치"` |
| 328-329 | `"놀이"` `<newline>` `"교구"` | `"놀이교구"` |
| 434-435 | `"덴프스"` `<newline>` `"가방"` | `"덴프스가방"` |
| 495-496 | `"먹는"` `<newline>` `"고려은단"` | `"먹는고려은단"` |
| 631-632 | `"멀티"` `<newline>` `"궁중팬"` | `"멀티궁중팬"` |
| 703-704 | `"리포좀"` `<newline>` `"고분자"` | `"리포좀고분자"` |
| 781-782 | `"레토"` `<newline>` `"가방"` | `"레토가방"` |

이로 인해 의도한 키워드 일부가 사라지고, 병합된 문자열이 키워드로 선택되어 검색 품질이 저하됨.

---

## 5. 개선 방안 (Action Plan)

### P0 — 즉시 배포 (오늘)

**5.1 `keywords.py` syntax error 수정**
- 누락된 쉼표 추가하여 키워드 병합 방지
- 잘못된 문자열 병합 복구

**5.2 `similar_title` return dict에 keyword 추가**
```python
return {"success": False, "reason": "similar_title", "keyword": keyword}
```
- Telegram 알림에 실제 키워드가 표시되어 추적 가능

**5.3 Generic single-word keyword 제거/보강**
- `가벼운`, `고함량`, `기능성`, `국내생산`, `기계식`, `나시` 등
  단독으로 쓰이면 블로그 주제와 맞지 않는 키워드 정리
- 원하는 경우 2~3단어 조합으로 교체 (e.g. `가벼운 노트북`, `고함량 오메가3`, `기계식 키보드`는 해당 블로그와 맞지 않으므로 제거 또는 다른 블로그로 이동)

### P1 — 최근 배포 (이번 주)

**5.4 `_select_keyword`에 category-aware 품질 게이트 강화**
- `_select_keyword` 내부의 relevance gate가 이미 존재함 (line 171-178)
- 하지만 keyword_health에 3회 이상 실패한 키워드는 gate가 통과되더라도 계속 시도됨
- 개선: `consecutive_failures >= 2`인 키워드는 선택 단계에서 skip (격리 상한 전에 미리 차단)

**5.5 Title 중복 검증 개선**
- stop_words에 "1위", "vs", "—", "2026", "2027", "추천", "비교", "TOP5" 등 템플릿 토큰 추가
- 또는 제목에서 "A vs B" 구조를 감지해 구조적 중복도 판단
- 3일 window를 1일로 축소하거나, 핵심 상품명 pair(A+B) 기준으로 비교

**5.6 Per-keyword 실패율 기반 자동 purge**
- `keyword_health`에서 최근 7일간 3회 이상 실패한 키워드가 전체의 10%를 넘어가면
  점검 알림 발송 또는 일시적 발행 중단

### P2 — 전략적 개선 (다음 마일스톤)

**5.7 keyword pool 재설계**
- Phase 2.1 cleanup에서 남은 generic keyword들을 category 필터와 교차 검증
- `CATEGORY_FILTERS[blog_id]["allowed"]`에 포함되지 않는 단어는 keyword pool에서 제거

**5.8 STAP ipo pipeline 안정화**
- `no_content` 발생 시 알림 suppress 고려 (공모주 일정이 없는 기간은 정상)
- `stap_subprocess_error`는 STAP 로그 확인 필요 (STAP 프로젝트 직접 점검)

**5.9 curation keyword 입력 자동화**
- Coupang 카테고리 ID 기반 allowed keyword 추출 또는
  LLM을 활용하여 category 필터에 맞는 구체적인 키워드 세트 생성

---

## 6. Verification

P0 적용 후 아래 커맨드로 검증:

```bash
cd /Users/twinssn/Projects/5000

# 1. keywords.py 문법/구조 점검
python3 -c "from pipelines.curation.keywords import KEYWORD_MAP; print({k: len(v) for k, v in KEYWORD_MAP.items()})"

# 2. similar_title 알림 keyword 포함 확인 (dry-run)
python3 -c "
from pipelines.curation.pipeline import _run_inner
# 또는 실제로 health-hugo 한 건 dry-run 후 similar_title 발생 시 keyword가 return dict에 포함되는지 로그 확인
"

# 3. target 블로그 dry-run 1회
python3 dispatcher.py --blog laptop-hugo --dry-run  # dry-run 옵션은 dispatcher에 없을 수 있음
```

---

## 7. Files to Modify

| 파일 | 변경 내용 |
|------|----------|
| `pipelines/curation/keywords.py` | 쉼표 누락 수정, generic keyword 제거 |
| `pipelines/curation/pipeline.py` | similar_title return dict에 `keyword` 추가 |
| `pipelines/curation/keyword_health.py` | optional: consecutive_failures 2회 이상 skip 로직 |
| `shared/relevance_scorer.py` | optional: threshold/allowed 기반 keyword quality helper |

---

## 8. Recommendations

1. **오늘 P0만 적용**해도 알림 noise와 무의미한 반복 실패가 크게 줄어듦.
2. `similar_title`은 단순 버그라 즉시 수정 권장 — keyword가 표시되지 않아 어떤 키워드가 문제인지 파악 불가.
3. `ipo-hugo`는 공모주 시즌에 따라 `no_content`가 정상일 수 있으므로, STAP 쪽 `stap_subprocess_error` 먼저 진단 권장.
