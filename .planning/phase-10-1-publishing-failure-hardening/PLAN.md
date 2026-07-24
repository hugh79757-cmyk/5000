# Phase 10-1 — Publishing Failure Hardening (Multi-Layer Defense)

**Goal:** kitchen-hugo `low_relevance` 반복 오류 + beauty-hugo 배포 실패를 **이중/삼중 방어막**으로 차단
**Mode:** plan-first (execution ready)

---

## Context

Phase 10에서 `low_relevance` 재시도 로직과 임계값 조정, 키워드 격리를 추가했으나 동일 오류가 재발하고 있다.

### 재발 패턴

| 증상 | 블로그 | 단계 | 빈도 |
|------|--------|------|------|
| `[임계값 초과] kitchen-hugo: low_relevance (keyword=가정용)` | kitchen-hugo | low_relevance | 반복 |
| `[curation] 발행 실패: low_relevance` | kitchen-hugo | low_relevance | 반복 |
| `Hugo빌드/Wrangler배포 실패: Wrangler deploy failed: see deploy.log` | beauty-hugo | deploy | 간헌적 |

### 근본 원인 분석

**kitchen-hugo:**
1. Phase 10은 `products` 레벨 격리만 적용. `keyword=가정용` 자체는 여전히 키워드 풀에 남아 있음 (`pipelines/curation/keywords.py:12, 111, ...`)
2. `가정용`은 overly generic 키워드 → 매칭 상품의 관련성 점수가 낮을 수밖에 없음
3. `low_relevance` 3-retry가 있지만, **fallback 키워드 풀에 `가정용` 계열이 다수 포함** → 같은 계열 키워드로 반복 실패
4. `keyword_health` 격리가 있지만, `quarantined_until` 만료 후 자동으로 다시 선택됨

**beauty-hugo:**
1. `deploy.py`는 network error에만 2회 재시도. **Hugo build 실패, Wrangler deploy 실패(비 network)** 는 즉시 예외 발생
2. `deploy.log`만 있고 자동 복구/재시도 로직 없음
3. 일시적 Cloudflare API 오류, theme lock 경합 등 일시적 오류도 영구 실패로 처리

---

## Defense Architecture (3-Layer)

```
Layer 1: Keyword Defense (사전 차단)
    ├── Toxic keyword blacklist per blog
    ├── Keyword-level quarantine (not just product-level)
    └── Pre-collect health gate

Layer 2: Relevance Defense (사후 회복)
    ├── Dynamic threshold calibration
    ├── Category fallback (키워드 → 카테고리 → 브로드)
    └── Product-level quarantine + deduplication

Layer 3: Deploy Defense (배포 신뢰성)
    ├── Hugo build error classification + retry
    ├── Wrangler deploy exponential backoff retry
    └── Pre-deploy validation (shortcode, asset check)
```

---

## Tasks

### Task 1 — Toxic Keyword Blacklist (kitchen-hugo 즉시 차단)

**File:** `pipelines/curation/keywords.py`

- [ ] `kitchen-hugo` 키워드 풀에서 `"가정용"` 계열 generic 키워드 **완전 제거** (품목 지정형으로 대체: `"가정용 러닝머신"`, `"가정용 커피머신"` 등은 유지, `"가정용"` 단독은 제거)
- [ ] `KEYWORD_BLACKLIST` 매커니즘 도입:
  ```python
  KEYWORD_BLACKLIST = {
      "kitchen-hugo": {"가정용", "주방용품"},  # overly generic
      # 필요시 다른 블로그도 추가
  }
  ```
- [ ] `get_keywords()` 또는 `select_next_keyword()` 에서 blacklist 키워드 자동 제외
- [ ] Verification: `grep '"가정용"' pipelines/curation/keywords.py` 결과 kitchen-hugo 섹션에서 0건

**Why:** Phase 10은 product-level 격리만 했고 keyword 자체는 살아있어서 재발. Keyword 자체를 제거해야 근본 해결.

---

### Task 2 — Keyword-Level Quarantine 강화

**File:** `pipelines/curation/keyword_health.py`

현재: `record_failure()` → `quarantined_until` 설정 → 일정 시간 후 자동 해제  
문제: 해제 후 다시 선택되면 같은 실패 반복

- [ ] **Permanent-ish quarantine for toxic keywords:** `consecutive_failures >= 5` 인 키워드는 `quarantined_until` 대신 `PERMANENT_QUARANTINE` 플래그 도입 (30일이 아닌 90일+)
- [ ] **Auto-blacklist promotion:** `consecutive_failures >= 3` + `reason == "low_relevance"` 인 키워드는 자동으로 `KEYWORD_BLACKLIST`에 추가 (파라미터화 가능)
- [ ] **Failure reason weighting:** `low_relevance` 실패는 다른 실패보다 높은 가중치 부여 (consecutive_failures +2)
- [ ] Verification: `keyword_health` 테이블 조회로 kitchen-hugo의 `가정용`이 permanent quarantine 상태인지 확인

**Why:** 현재 백오프(1h→4h→24h→7d→30d)로는 재발 방지 불충분. 3회 실패하면 keyword pool에서 영구 제외.

---

### Task 3 — Pre-Collect Health Gate

**File:** `pipelines/curation/pipeline.py`

현재: 키워드 선택 → 상품 수집 → 관련성 검증 → 실패 시 fallback  
문제: 이미 실패할 키워드를 수집부터 시작함

- [ ] `_pre_collect_gate(blog_id, keyword)` 함수 추가:
  1. `health_store.is_quarantined(blog_id, keyword)` 체크
  2. `keyword`가 `KEYWORD_BLACKLIST`에 있는지 체크
  3. 최근 7일간 `low_relevance` 실패 횟수 확인 → 2회 이상이면 skip
  4. `collect_keyword()` 호출 전 사전 검증 완료된 키워드만 진행
- [ ] `select_next_keyword()` 내에서 health gate 적용:
  ```python
  for kw in candidates:
      if _is_healthy_keyword(blog_id, kw):
          return kw
  ```
- [ ] Verification: kitchen-hugo run 시 `가정용`이 collect 단계 이전에 skip되는지 로그 확인

**Why:** 불필요한 쿠팡 API 호출 방지 + 실패 키워드의 2차 피해 방지.

---

### Task 4 — Dynamic Threshold Calibration

**File:** `shared/relevance_scorer.py`, `pipelines/curation/pipeline.py`

현재: 고정 임계값 (kitchen-hugo=0.65, default=0.75)  
문제: 카테고리/계절에 따라 평균 점수가 변동 → 같은 임계값이 너무 엄격하거나 너무 느슨할 수 있음

- [ ] **Adaptive threshold:** 최근 10개 성공 글의 평균 점수를 기반으로 임계값 조정
  ```python
  def get_adaptive_threshold(blog_id: str, base_threshold: float) -> float:
      recent_avg = _get_recent_avg_score(blog_id, limit=10)
      if recent_avg is None:
          return base_threshold
      # 최근 평균보다 5% 낮게 설정 (너무 엄격하지 않게)
      return min(base_threshold, recent_avg * 0.95)
  ```
- [ ] **Category-level threshold:** 카테고리별 평균 점수를 별도 추적 (주방가전 vs 소형가전)
- [ ] Verification: kitchen-hugo 5회 발행 후 임계값이 동적으로 조정되는지 로그 확인

**Why:** 고정 임계값은 변동하는 상품 품질에 적응 불가. 적응형 임계값이 과도한 탈락 방지.

---

### Task 5 — Category Fallback (키워드 → 카테고리 → 브로드)

**File:** `pipelines/curation/pipeline.py`

현재: `low_relevance` 실패 → 동일 블로그의 다른 키워드 1개만 시도  
문제: fallback 키워드도 같은 계열이면 연속 실패

- [ ] **Category-aware fallback:** 
  1. 1차: 키워드 레벨 fallback (현재 로직 유지)
  2. 2차: 카테고리 레벨 fallback — 실패한 키워드의 카테고리와 **다른** 카테고리에서 키워드 선택
  3. 3차: 브로드 fallback — 전체 풀에서 가장 오래 사용되지 않은 키워드
- [ ] Implementation:
  ```python
  def _category_fallback(blog_id, exclude_keyword):
      failed_cat = _extract_category(exclude_keyword)
      candidates = [k for k in get_keywords(blog_id) 
                    if _extract_category(k) != failed_cat 
                    and not health_store.is_quarantined(blog_id, k)]
      return candidates[0] if candidates else None
  ```
- [ ] Verification: kitchen-hugo에서 `가정용` 실패 시 `가전` → `생활가전` → `주방` 순으로 fallback되는지 로그 확인

**Why:** 단일 키워드 fallback은 동일 계열 실패를 반복. 카테고리 분산이 핵심.

---

### Task 6 — Deploy Error Recovery (beauty-hugo)

**File:** `shared/publishers/deploy.py`

현재: network error만 2회 재시도. Hugo build 실패/Wrangler deploy 실패는 즉시 예외.

- [ ] **Hugo build error classification:**
  ```python
  BUILD_ERROR_PATTERNS = {
      "recoverable": [
          r"template.*not found",
          r"shortcode.*missing",
          r"resource.*not found",
      ],
      "fatal": [
          r"Failed to parse",
          r"build failed",
          r"cannot unmarshal",
      ]
  }
  ```
  - recoverable → 자동 수정 시도 (예: missing shortcode → no-op으로 대체)
  - fatal → 즉시 실패

- [ ] **Wrangler deploy retry (all errors):**
  - network error: 2회 재시도 + 지수 백오프 (10s, 20s)
  - auth error: 1회 재시도 + env 재로드
  - timeout: 3회 재시도 + 지수 백오프 (30s, 60s, 120s)
  - 기타: 1회 재시도

- [ ] **Pre-deploy validation:**
  ```python
  def _pre_deploy_validate(site_path):
      # 1. shortcode syntax check
      # 2. public/index.html exists after build
      # 3. no broken internal links
      # 4. asset files exist
  ```

- [ ] Verification: `deploy.log`에 재시도 기록이 남는지 확인

**Why:** beauty-hugo 배포 실패는 일시적일 가능성이 높으나 현재 복구 불가. 재시도 + 사전 검증으로 신뢰성 향상.

---

### Task 7 — Monitoring & Alerting

**File:** `shared/publishers/deploy.py`, `pipelines/curation/pipeline.py`

- [ ] **Failure pattern detector:** 같은 키워드가 3회 연속 `low_relevance` 실패 시 Telegram 알림
- [ ] **Deploy failure alert:** 배포 실패 시 `_tg_error()` 호출 + `deploy.log` tail 전송
- [ ] **Daily health summary:** `keyword_health.get_health_summary()` 기반 일일 리포트
  - 격리된 키워드 수
  - 가장 실패 많은 키워드 TOP 5
  - 최근 24h 배포 성공률
- [ ] Verification: 테스트 환경에서 Telegram 알림 수신 확인

**Why:** 조용한 실패 방지. Phase 10에서 발견된 동일 오류를 즉시 감지할 수 있어야 함.

---

## Execution Order

```
Task 1 (blacklist) → Task 2 (quarantine 강화) → Task 3 (pre-collect gate)
       ↓
Task 4 (dynamic threshold) → Task 5 (category fallback)
       ↓
Task 6 (deploy recovery) → Task 7 (monitoring)
```

## Verification Criteria

1. `kitchen-hugo`에서 `가정용` 키워드가 키워드 풀에서 완전 제거 → `grep '"가정용"' pipelines/curation/keywords.py` kitchen-hugo 섹션 0건
2. `keyword_health` 테이블에서 kitchen-hugo의 `가정용`이 permanent quarantine 상태
3. `low_relevance` 3-retry fallback이 category-aware로 작동 → 다른 카테고리 키워드로 대체
4. `deploy.py`에 Hugo build/Wrangler deploy 재시도 로직 추가 → `deploy.log`에 재시도 기록
5. 3회 연속 `low_relevance` 실패 시 Telegram 알림 발송
6. Phase 10-1 적용 후 kitchen-hugo 5회 연속 발행 성공
