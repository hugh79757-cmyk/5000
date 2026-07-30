# Phase: AI Marketing Skills — Wave 1  (Table Numbering Validation)

---

## Wave 1-1: 표 번호 연속성 검증 (Reference Block) — ✅ Completed

**Commit:** `4948d751f`  
**Branch:** `fix/table-numbering-validation`  
**Date:** 2026-07-30

### Summary
- `_build_subscription_reference()` in `pipelines/rap/writer.py` now extracts display slice once (`_display = subscriptions[:15]`)
- Header count uses `len(_display)` instead of `len(subscriptions)` — matches actual table rows
- Both table and detail block enumerate `_display` — sequential 1..N guaranteed

### Verification
- 8 dry-run cases (5 regions × 15 rows, plus 0/1/25-edge) all PASS
- Numbers sequential 1..N, header N == row count

---

## Wave 1-2: 결정론적 후처리 교정 (AI-Generated Table) — ✅ Completed

**Commit:** `9fee5a0b3`  
**Branch:** `fix/table-numbering-postprocess`  
**Date:** 2026-07-30

### Summary
- Added `normalize_reference_table()` in `pipelines/rap/pipeline.py`
  - Detects subscription table by header pattern `| 번호 | 공고명 | 유형 | 지역 | 접수기간 | 상태 |`
  - Renumbers all data rows sequentially 1..N (ignores original numbers)
  - Replaces all `총 N건` / `총 N건의 공고가 확인되는데` patterns with actual row count
  - No-op (log + return original) when no matching table
- Hooked at two points:
  - `_post_process()` start → all-strategy safety net
  - Right after `generate_subscription_article()` → subscription-specific 1st-pass fix
- Strengthened AI prompt in `pipelines/rap/writer.py`:
  - Instruct GPT to renumber included rows from 1
  - Require `총 N건` to match actual included rows
  - Note that `normalize_reference_table()` is final deterministic guard

### Verification
- Exact bug reproduction: article `26년-7월-인천부천-든든전세주택-정정공고-청약-안내` (numbers 1,3,4,5 + "총 15건" vs 4 rows) → corrected to 1,2,3,4 + "총 4건"
- Edge cases: non-matching tables unchanged, already-correct tables preserved, multiple count mentions all corrected, empty body safe
- **7-day production scan (RAP blogs):**
  - Scanned: 170 posts
  - Subscription-table posts: 35
  - **Mismatches found: 13 (37%)** — numbering gaps and/or "총 N건" ≠ row count
  - All 13 corrected by `normalize_reference_table()`

---

## Exit Criteria Result (Wave 1)

> **최근 7일간 RAP 청약-표 포맷 글 35건 중 13건(37%)에서 표 번호 불연속 또는 "총 N건" 불일치 발견 → `normalize_reference_table()` 적용 후 결정론적으로 교정됨**

---

## 확산 검토 대상 (Wave 1 — Spread Review)

동일한 GPT 자유생성 표 패턴(`| 번호 | ... |` 헤더 + AI가 부분 선택 후 원본 번호 유지)을 사용하는 다른 파이프라인에도 유사 버그 가능성이 높음. 아래 파이프라인을 **검토 대상으로 등록**함 (실행은 아직 하지 않음):

| 파이프라인 | 의심 블로그 | 표 패턴 유사도 | 비고 |
|------------|-------------|----------------|------|
| **TRAVEL** (pipelines/travel) | travel-hugo, travel1~4-hugo | 높음 — 지역별 명소/숙소 표에서 GPT가 대표 항목만 선택 시 번호 불연속 발생 가능 | 가장 시급 |
| **ETAP** (pipelines/etap) | ETAP 30+ Hugo blogs | 중간 — 여행 상품 카드 표에서 동일 패턴 사용 | ETAP는 별도 repo |
| **CURATION** (pipelines/curation) | curation 계열 | 낮음 — 상품 비교 표 위주, GPT 생성 표 빈도 낮음 | 추후 검토 |
| **CAR** (pipelines/car) | car-hugo | 낮음 — 실거래가 표 위주, GPT 생성 표 적음 | 추후 검토 |

> **액션 필요:** TRAVEL 파이프라인의 실제 발행 글 표본 조사 → 버그 발생률 측정 → 동일 `normalize` 로직 적용 여부 결정