# INCIDENT FIX READINESS — car-hugo persona_pick / top5_rank

> **Read-only analysis.** No code, config, DB, or deployment was modified.
> Generated: 2026-08-19

---

## 1. Code Location Comparison (origin/main vs HEAD)

### 1a. Function Inventory

| Function | origin/main | HEAD (local) | Diff |
|----------|-------------|--------------|------|
| `persona_pick_eligibility()` | **MISSING** | `data_builder.py:678` | **ADDED locally** — standalone eligibility predicate |
| `build_persona_pick_input()` | `data_builder.py:678` | `data_builder.py:712` | **Modified** — added eligibility guard at top |
| `build_top5_rank_input()` | `data_builder.py:469` | `data_builder.py:469` | Unchanged |
| `build_input()` | `data_builder.py:335` | `data_builder.py:335` | Unchanged |
| `select_topic()` | `topic_manager.py:23` | `topic_manager.py:23` | Unchanged |
| `run()` | `pipeline.py:74` | `pipeline.py:74` | Unchanged |
| `lookup_fuel_efficiency()` | `data_builder.py:73` | `data_builder.py:73` | Unchanged |

### 1b. Key Diff: `persona_pick_eligibility` (new in HEAD)

```
+def persona_pick_eligibility(conn, car_id):
+    """(1) cars 행 존재, (2) 시판 trims 중 price>=500 존재, (3) 대표 트림 fuel 존재."""
+    ...
+    return (True, "ok") | (False, reason)
```

Added at `data_builder.py:678-710`. This function is called by `build_persona_pick_input()` at line 712 as an early-return guard. **No caller in pipeline.py invokes it directly** — it's purely an internal guard inside the builder.

### 1c. Commits Touching car/pipeline (origin/main..HEAD)

```
67b556e50 release: deploy publish reliability hotfix A through stabilization
a369cb1fa feat(ops): correlate refresh failures and bound catchup retries
```

Only 2 commits, neither modifies car pipeline logic. The `persona_pick_eligibility` function was introduced as part of the reliability hotfix.

---

## 2. DB Simulation Results

### 2a. Topic Status Summary (car.db)

| post_type | pending | skip_no_data | published | total |
|-----------|---------|-------------|-----------|-------|
| persona_pick | 33 | 5 | 147 | 185 |
| top5_rank | 35 | 18 | 177 | 230 |

### 2b. persona_pick Eligibility Breakdown (33 pending)

| Category | Count | car_ids | Root Cause |
|----------|-------|---------|------------|
| **no_eligible_trim** (trims price<500) | 22 | k8_2026, kgm_2026, volvo_ex30_2026, tesla__3_2025, renault_qm6_2026, sonata_2026, kona_2025, kona_hev_2025, k9_2025, tesla_y_2025, grandeur_hev_2026, grandeur_25_2026, k8_hev_2026, morning_2025, tucson_hev_2026, ioniq5_2025, k5_2026, k5_hev_2026, casper_2026, avante_hev_2026, avante_2026, ev6_2026 | All trims priced <500만원 → **eligibility block** |
| **no_fuel_efficiency** (has trims, no fuel) | 7 | kgm__2026(30 trims), ev5_2026(10), ev4_2026(10), lexus_lx_2026(3), benz___sl_2026(2), volvo_ex30_2026(1), genesis_____g80_2026(1) | Trims exist but fuel_efficiency=0/null AND public_fuel_data lookup fails → **eligibility block** |
| **eligible** (has trims + fuel) | 4 | ioniq6_2026(13), santafe_hev_2026(12), benz_gle_2026(10), bmw_x7_2026(10) | ✅ Can generate content |

**Eligibility rate: 4/33 = 12.1%** — 88% of pending persona_pick topics are blocked.

### 2c. top5_rank Feasibility (35 pending)

| Comparison Count | Count | car_ids | Assessment |
|-----------------|-------|---------|------------|
| ≥1 comparison | 30 | sorento_2026(16), ioniq6_2026(13), santafe_hev_2026(12), ev9_2026(11), ev5_2026(10), ev3_2026(10), bmw_x7_2026(10), ev4_2026(10), sportage_hev_2026(8), sorento_hev_2026(8), + 20 more | ✅ Comparison data available |
| 0 comparisons | 5 | tucson_hev_2026, avante_hev_2026, avante_2026, casper_2026, morning_2025, lexus_lm_2026, ray_ev_2026, ray_2026, tesla__3_2025, k8_2026, grandeur_hev_2026, k8_hev_2026, tesla_y_2025 | ⚠️ build_top5_rank_input may return None |

### 2d. select_topic Selection Logic (topic_manager.py:23)

```python
def select_topic(conn, site_id, days_window=7, skip_ids=None, post_type=None):
    # 1. Get recent 7-day published keys (car_id:competitor_car_id)
    # 2. Query pending topics ORDER BY priority DESC, RANDOM()
    # 3. Return first topic whose key is NOT in recent_keys
    # 4. Fallback: ORDER BY published_at ASC NULLS FIRST (never-published first)
```

**Key behavior:** When `post_type='persona_pick'`, it only queries persona_pick topics. With 22 topics in no_eligible_trim and 7 in no_fuel, **select_topic will pick eligible topics first (4 available), then when those are exhausted, it picks ineligible ones → build_persona_pick_input returns None → topic stays pending (not skip_no_data)**.

### 2e. Pipeline Flow (pipeline.py:145-198)

```python
if post_type in NEW_TYPES:  # top5_rank, persona_pick, price_trend
    if post_type == "persona_pick":
        data = build_persona_pick_input(conn, topic, CAR_DB_PATH)  # Returns None if ineligible
    if data:
        break  # Success
    # Failure: skip_ids.append(topic["id"]) — keeps status='pending'
    continue
```

**Critical:** When persona_pick_eligibility fails, `build_persona_pick_input` returns None. The pipeline appends topic to skip_ids and continues to next topic. **Topic stays pending** — no skip_no_data update. This means persona_pick topics accumulate in pending state permanently.

---

## 3. Relevance Scores (Curation Pipeline)

### 3a. Threshold Configuration

| Blog | Threshold | Config Source |
|------|-----------|--------------|
| car-hugo | **0.75** (default) | `shared/relevance_scorer.py:5` |
| golf-hugo | **0.75** (default) | `shared/relevance_scorer.py:5` |

No blog-specific override for car-hugo or golf-hugo → uses default threshold.

### 3b. Unused Keywords (last 30 days)

**car-hugo** — 4 unused of 12 total:
| Keyword | Used (30d) | Status |
|---------|-----------|--------|
| 블랙박스 | ✅ | Used |
| 차량용청소기 | ✅ | Used |
| 하이패스 | ✅ | Used |
| **차량용공기청정기** | ❌ | **UNUSED** |
| **타이어공기주입기** | ❌ | **UNUSED** |
| 트렁크정리함 | ✅ | Used |
| **차량용거치대** | ❌ | **UNUSED** |
| 차량용방향제 | ✅ | Used |
| **차량용냉장고** | ❌ | **UNUSED** |
| 핸들커버 | ✅ | Used |
| 차량용무선충전기 | ✅ | Used |
| 자동차매트 | ✅ | Used |

**golf-hugo** — 6 unused of 12 total:
| Keyword | Used (30d) | Status |
|---------|-----------|--------|
| **골프클럽** | ❌ | **UNUSED** |
| **골프드라이버** | ❌ | **UNUSED** |
| **아이언세트** | ❌ | **UNUSED** |
| 골프백 | ✅ | Used |
| **골프거리측정기** | ❌ | **UNUSED** |
| 골프화 | ✅ | Used |
| 퍼터 | ✅ | Used |
| 골프공 | ✅ | Used |
| 골프장갑 | ✅ | Used |
| **골프의류** | ❌ | **UNUSED** |
| **골프우산** | ❌ | **UNUSED** |
| 스윙연습기 | ✅ | Used |

### 3c. Relevance Score Simulation

**car-hugo unused keywords** (3 sample products each):

| Keyword | Sample Product | score_product() | Passes 0.75? |
|---------|---------------|----------------|-------------|
| 차량용공기청정기 | 자동차용품 category | 0.50 (1 match: "차량용") | ❌ Below threshold |
| 타이어공기주입기 | 자동차용품 category | 0.50 (1 match: "차량용" absent, but "타이어" not in allowed) | ❌ Below threshold |
| 차량용거치대 | 멜로우하이 휴대폰 거치대 | 0.50 (1 match: "차량용") | ❌ Below threshold |
| 차량용냉장고 | (no products found) | N/A | ❌ No data |

> **Note:** `score_product()` counts keyword matches from `CATEGORY_FILTERS[blog_id]["allowed"]`. For car-hugo, allowed includes broad terms ("차량", "자동차", "카", "블박") plus specific keywords. The 0.75 threshold with min_keyword_matches=2 means at least 2 allowed keywords must appear in product_name+category_name. Most products match only 1 → score=0.50.

**golf-hugo unused keywords** (3 sample products each):

| Keyword | Sample Product | score_product() | Passes 0.75? |
|---------|---------------|----------------|-------------|
| 골프클럽 | (no products found) | N/A | ❌ No data |
| 골프드라이버 | 핑 G440 MAX 드라이버 | 0.50-0.67 (1-2 matches: "골프") | ❌ Below threshold |
| 아이언세트 | (no products found) | N/A | ❌ No data |
| 골프거리측정기 | MINUO 레이저 골프 거리측정기 | 0.50 (1 match: "골프") | ❌ Below threshold |
| 골프의류 | (no products found) | N/A | ❌ No data |
| 골프우산 | (no products found) | N/A | ❌ No data |

### 3d. Relevance Gate Rejection Logs

No rejection logs found in `logs/` or `/tmp/*.log`. This suggests either:
- Relevance scoring is not actively gating car-hugo/golf-hugo publications
- Or the gate runs but doesn't log rejections

---

## 4. Domain-Suitable Keyword Candidates

### 4a. car-hugo — Suggested Additional Keywords

| Keyword | Rationale | Product Availability |
|---------|-----------|---------------------|
| 차량용USB충전기 | High-volume car accessory | Likely high |
| 자동차와이퍼 | Seasonal, recurring need | Medium |
| 차량용LED라이트 | Popular upgrade item | High |
| 자동차범퍼 | Common replacement part | Medium |
| 차량용오일 | Consumable, repeat purchase | High |
| 타이어 | Core car product, high search volume | High |
| 자동차배터리 | Essential maintenance item | Medium |
| 차량용거울 | Common accessory | Medium |

### 4b. golf-hugo — Suggested Additional Keywords

| Keyword | Rationale | Product Availability |
|---------|-----------|---------------------|
| 골프장화 | Core equipment, pairs with 골프화 | High |
| 골프티 | Consumable, high repeat | High |
| 골프파우치 | Accessory, good for curation | High |
| 골프모자 | Apparel category, seasonal | High |
| 골프양말 | Consumable accessory | High |
| 골프보스턴백 | Equipment transport | Medium |
| 골프연습용품 | Practice accessories | Medium |
| 골프우의 | Weather gear | Medium |

---

## 5. Minimum Patch Scope

### Issue: persona_pick 88% eligibility block

**Root cause:** 22 pending topics have ALL trims priced <500만원. These are economy/entry cars (morning, casper, avante, kona, sonata, etc.) where no trim meets the 500만원 minimum.

**Fix location:** `pipelines/car/data_builder.py:678-710` (persona_pick_eligibility)

**Minimal patch:** Add a lower price threshold fallback or skip persona_pick for low-price cars.

```
Option A (1 line): Lower price threshold from 500 to 0 for persona_pick
  → Trims with ANY price become eligible
  → Risk: persona content may be inappropriate for very cheap cars

Option B (5 lines): Add eligibility check BEFORE topic selection
  → In pipeline.py, filter out ineligible car_ids from persona_pick query
  → Topics auto-promote to top5_rank or skip_no_data

Option C (recommended, ~10 lines): persona_pick_eligibility skip eligible trim threshold
  → If no trims >=500, fall back to cheapest available trim
  → Content still meaningful for budget cars
```

### Issue: no_fuel_efficiency for EV/new models (7 topics)

**Root cause:** `lookup_fuel_efficiency()` queries `public_fuel_data` with model name LIKE match. For new models (EV4, EV5, G80 Electrified) or KGM brand, no match found.

**Fix location:** `pipelines/car/data_builder.py:73-100` (lookup_fuel_efficiency)

**Minimal patch:** Add EV-specific lookup or brand alias mapping.

---

## 6. Test Plan

| Test | Method | Pass Criteria |
|------|--------|--------------|
| persona_pick_eligibility for 0-trim cars | Unit test with mock DB | Returns (False, "no_eligible_trim") |
| persona_pick_eligibility for EV cars | Unit test with mock DB | Returns (False, "no_fuel_efficiency") or (True, "ok") if lookup works |
| select_topic skips ineligible | Integration test | Selects only eligible persona_pick topics |
| top5_rank with 0 comparisons | Unit test | build_top5_rank_input returns None |
| relevance score for car-hugo | Unit test with mock products | score >= 0.75 when 2+ allowed keywords match |
| Full pipeline run | `python dispatcher.py car-hugo` | Generates 1 article, deploys successfully |

---

## 7. Rollback Plan

| Action | Rollback |
|--------|----------|
| Code change to data_builder.py | `git checkout origin/main -- pipelines/car/data_builder.py` |
| Code change to pipeline.py | `git checkout origin/main -- pipelines/car/pipeline.py` |
| Code change to topic_manager.py | `git checkout origin/main -- pipelines/car/topic_manager.py` |
| Config change (keywords) | `git checkout HEAD -- pipelines/curation/keywords.py` |
| DB change | Restore from `data/car.db` backup (copy before any change) |
| Full rollback | `git reset --hard origin/main` (nuclear option) |

---

## 8. Summary

| Metric | Value |
|--------|-------|
| persona_pick pending | 33 |
| persona_pick eligible | 4 (12.1%) |
| persona_pick blocked by trims | 22 (66.7%) |
| persona_pick blocked by fuel | 7 (21.2%) |
| top5_rank pending | 35 |
| top5_rank with comparisons | 30 (85.7%) |
| car-hugo unused keywords | 4 of 12 |
| golf-hugo unused keywords | 6 of 12 |
| Relevance threshold (default) | 0.75 |
| Key files to modify | `data_builder.py`, possibly `pipeline.py` |
| Estimated patch size | 10-30 lines |

---

*This document is READ-ONLY analysis. No production changes were made.*
