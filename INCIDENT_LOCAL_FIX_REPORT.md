# INCIDENT_LOCAL_FIX_REPORT.md

> **작성 시각**: 2026-08-19 00:35 KST
> **커밋**: `d887e094f` (main 브랜치, 로컬 전용)
> **대상**: pick-hugo no_data + curation 블로그 no_keyword 구조화 로그
> **수행하지 않은 것**: push, merge, 배포, 운영 DB 변경, 재발행, 임계값 변경, 키워드 설정 변경

---

## 1. 커밋 변경사항

### 커밋 SHA
```
d887e094f fix(pick-hugo): persona_pick→top5_rank fallback + structured logging
```

### 변경 파일 (3건)

| 파일 | 변경 내용 | 변경 유형 |
|------|-----------|-----------|
| `pipelines/car/pipeline.py` | persona_pick 실패 시 top5_rank fallback + 구조화 로그 | PRODUCTION CODE |
| `pipelines/curation/pipeline.py` | `_select_keyword()` 단계별 구조화 로그 | PRODUCTION CODE |
| `tests/test_pick_hugo_fallback.py` | 회귀 테스트 7건 (신규 생성) | TEST CODE |

### 변경하지 않은 것
- `trims` 기준 (price≥500) — 완화 없음
- `relevance threshold` (0.75) — 변경 없음
- `KEYWORD_MAP` — 키워드 추가/삭제 없음
- `blogs.d/*.yaml` — 설정 변경 없음
- `data/*.db` — 운영 DB 수정 없음
- 배포 없음

---

## 2. 변경 상세

### A. `pipelines/car/pipeline.py` — top5_rank fallback

**위치**: line 155-198 (persona_pick 블록)

**변경 전**: persona_pick이 None 반환 시 `skip_ids.append()` → 다음 topic으로 이동 → 모두 실패 시 `no_data` 반환

**변경 후**: persona_pick이 None 반환 시 → `build_top5_rank_input()` 시도 → 성공하면 해당 데이터 사용, 실패하면 `no_data_detail` 로그 기록 후 다음 topic으로 이동

**fallback 조건**: persona_pick 후보 0건일 때만 (기존 선택 순서 변경 없음)

**구조화 로그**:
- `no_data_detail: car_id={car_id} reason={reason}` — persona_pick/top5_rank 모두 실패 시
- `no_data: exhausted {N} candidates (last_ids=[...])` — 전체 후보 소진 시

### B. `pipelines/curation/pipeline.py` — 키워드 선택 로그

**위치**: line 155-224 (`_select_keyword()` 함수)

**변경 전**: 최종 "모든 키워드 사용 완료" 또는 "상품 부족" 로그만 출력

**변경 후**: 각 필터 단계별 카운트 + 구조화 로그:
- `no_keyword: total={N} after_30d_dedup={N} after_quarantine={N} after_low_relevance={N} used_30d=[...] quarantined=[...]`
- `relevance_gate_block: {keyword} avg={score} threshold={threshold}` — relevance 미통과 시
- `keyword_skip: {keyword} products={N} < 3 (pool={pool_name})` — 상품 부족 시

**relevance gate 변경 없음**: threshold=0.75 유지, block 로그만 추가 (debug→info 승격)

### C. `tests/test_pick_hugo_fallback.py` — 회귀 테스트

| 테스트 | 검증 내용 | 결과 |
|--------|-----------|------|
| `test_no_eligible_trim_returns_none` | trims 0건 car_id → eligibility=False | ✅ |
| `test_eligible_trim_passes` | trims+fuel 있으면 eligibility=True 또는 no_fuel_efficiency | ✅ |
| `test_top5_rank_has_comparison_data` | top5_rank fallback에 segment 데이터 존재 | ✅ |
| `test_build_top5_rank_input_returns_data` | build_top5_rank_input이 데이터 반환 | ✅ |
| `test_fallback_chain_does_not_crash` | 21회 시뮬레이션 크래시 프리 | ✅ |
| `test_no_data_detail_log_format` | 로그 포맷에 `no_data_detail:` 포함 | ✅ |
| `test_keyword_selection_log_format` | 로그 포맷에 `relevance_gate_block:` 포함 | ✅ |

**테스트 통과율**: 7/7 (100%)

---

## 3. 시뮬레이션 결과

### pick-hugo persona_pick 시뮬레이션

| 항목 | 결과 |
|------|------|
| pending topics | 68건 (persona_pick 33, top5_rank 35) |
| trims 0건 topic | 22건 (67%) → persona_pick_eligibility 차단 |
| trims 있으나 fuel_efficiency 없음 | 7건 (21%) → persona_pick_eligibility 차단 |
| persona_pick 가용 | 4건 (12%) |
| top5_rank fallback 가용 | 30건 (86%) — segment 비교 데이터 보유 |
| 21회 시뮬레이션 | 크래시 0건, fallback 체인 정상 작동 |

### car-hugo/golf-hugo 키워드 시뮬레이션

| 항목 | car-hugo | golf-hugo |
|------|----------|-----------|
| 현재 키워드 | 12개 | 12개 |
| 30일 내 사용 | 8개 | 6개 |
| 미사용 | 4개 | 6개 |
| 미사용 상품 수 | 14~19개 | 12~22개 |
| 추가 후보 평가 | 10개 제안 → **0개 shortlist** (상품 0건) | 10개 제안 → **0개 shortlist** (상품 0건) |
| 추가 후보 blocker | products 테이블에 해당 키워드 0건 | 동일 |

**키워드 추가 불가 사유**: 제안된 후보 키워드(광택제, 에어컨필터, 골프티, 골프모자 등)는 `curation.db` products 테이블에 상품이 0건. Coupang API로 사전 수집 필요.

---

## 4. 배포 전 조건

| # | 조건 | 상태 |
|---|------|------|
| 1 | `python3 -m pytest tests/test_pick_hugo_fallback.py` 7/7 통과 | ✅ 확인 |
| 2 | `python3 -m py_compile pipelines/car/pipeline.py` | ✅ 확인 |
| 3 | `python3 -m py_compile pipelines/curation/pipeline.py` | ✅ 확인 |
| 4 | `112233` 하드코딩 없음 | ✅ 확인 |
| 5 | trims 기준 미변경 확인 | ✅ 확인 (line 161 price≥500 유지) |
| 6 | relevance threshold 미변경 확인 | ✅ 확인 (0.75 유지) |
| 7 | KEYWORD_MAP 미변경 확인 | ✅ 확인 |
| 8 | blogs.d/*.yaml 미변경 확인 | ✅ 확인 |
| 9 | 운영 DB 미변경 확인 | ✅ 확인 |
| 10 | 로컬 커밋 only (push 없음) | ✅ 확인 |

---

## 5. 롤백 절차

```bash
# 방법 1: git revert
git revert d887e094f

# 방법 2: 수동 원복
git checkout HEAD~1 -- pipelines/car/pipeline.py pipelines/curation/pipeline.py
rm tests/test_pick_hugo_fallback.py
git commit -m "revert: pick-hugo fallback patch"
```

**주의**: 롤백해도 기존 기능에 영향 없음 — fallback 추가분만 제거됨.

---

## 6. 잔존 위험

1. **car-hugo/golf-hugo no_keyword**: 이 패치로 해결되지 않음. KEYWORD_MAP에 키워드 추가 또는 Coupang API로 신규 키워드 수집 필요.
2. **relevance gate threshold=0.75**: 미사용 키워드도 차단할 수 있으나, 이번 패치에서 변경하지 않음. gate 진입 전 30일 중복 억제에서 먼저 차단됨.
3. **daily cooldown 메커니즘**: pick-hugo의 no_data 1건 후 하루 전체 차단은 여전히 존재. 이번 패치로 fallback이 성공하면 해결됨.
4. **persona_pick trims 0건**: 근본 원인은 car DB에 trims 데이터 부족. 이 패치는 fallback으로 우회할 뿐, trims 데이터 보강은 별도 작업 필요.

---

> **이 보고서는 로컬 커밋만 수행했습니다. push·merge·배포·운영 DB 변경·재발행은 수행하지 않았습니다.**
