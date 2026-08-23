# PICK_RELEASE_CANDIDATE.md

> **작성 시각**: 2026-08-19 01:10 KST
> **대상**: pick-hugo no_data 장애 복구 — persona_pick→top5_rank fallback

---

## 1. 커밋 정보

| 항목 | 값 |
|------|-----|
| **커밋 1** | `d887e094f` — car/pipeline.py fallback 로직 + 테스트 7건 |
| **커밋 2** | `ae90ed63a` — curation/pipeline.py 원복 + 테스트 5건 추가 |
| **합산 net diff** | car/pipeline.py +22줄, tests/test_pick_hugo_fallback.py +408줄, curation/pipeline.py **0줄** |
| **롤백 SHA** | `037404d8aa406cf722c4a02badff26acf3f43a94` (d887e094f^) |

---

## 2. 합산 net diff 상세

### car/pipeline.py (+22줄, -0줄)

| 변경 위치 | 내용 | 라인 수 |
|-----------|------|---------|
| line 180-191 | `persona_pick → top5_rank fallback` — trims 0건 시 top5_rank 자동 시도 | +19 |
| line 193-198 | `no_data_detail` 구조화 로그 — car_id, reason 포함 | +3 |

**변경 범위**: persona_pick 타입에서만 동작. compare/hotissue/guide/deal/tco/rank/ev 블로그 무관.

### tests/test_pick_hugo_fallback.py (+408줄, -0줄)

| 테스트 클래스 | 테스트 수 | 검증 시나리오 |
|---------------|-----------|--------------|
| TestPersonaPickEligibility | 2 | trims 0 차단, trims+fuel 통과 |
| TestTop5RankFallback | 2 | segment 데이터 존재, build_top5_rank_input 반환 |
| TestNoDataRegression21 | 1 | 21회 크래시 프리 |
| TestStructuredLogging | 2 | no_data_detail 포맷, curation 로그 미포함 |
| TestPersonaPickSuccessSkipsFallback | 1 | 성공→fallback 미실행 (SKIPPED: eligible topic 없음) |
| TestPersonaPickFailThenTop5RankSuccess | 1 | 실패→top5_rank 성공 |
| TestBothCandidatesMissing | 2 | pending 0건, 양쪽 후보 모두 실패 |
| TestDuplicateTopicPrevention | 1 | skip_ids 중복 방지 |

**합계**: 12건 수집, 11건 통과, 1건 SKIPPED

### curation/pipeline.py (0줄 — net diff)

커밋 1에서 추가된 `_select_keyword` 구조화 로그 + `_run_inner` title/slug 변경을 커밋 2에서 완전 원복. curation/pipeline.py의 합산 net change는 0줄.

---

## 3. 테스트 결과

```
tests/test_pick_hugo_fallback.py::TestPersonaPickEligibility::test_no_eligible_trim_returns_none PASSED
tests/test_pick_hugo_fallback.py::TestPersonaPickEligibility::test_eligible_trim_passes PASSED
tests/test_pick_hugo_fallback.py::TestTop5RankFallback::test_top5_rank_has_comparison_data PASSED
tests/test_pick_hugo_fallback.py::TestTop5RankFallback::test_build_top5_rank_input_returns_data PASSED
tests/test_pick_hugo_fallback.py::TestNoDataRegression21::test_fallback_chain_does_not_crash PASSED
tests/test_pick_hugo_fallback.py::TestStructuredLogging::test_no_data_detail_log_format PASSED
tests/test_pick_hugo_fallback.py::TestStructuredLogging::test_curation_logs_not_in_car_pipeline PASSED
tests/test_pick_hugo_fallback.py::TestPersonaPickSuccessSkipsFallback::test_persona_pick_success_no_fallback SKIPPED
tests/test_pick_hugo_fallback.py::TestPersonaPickFailThenTop5RankSuccess::test_fallback_to_top5_rank_succeeds PASSED
tests/test_pick_hugo_fallback.py::TestBothCandidatesMissing::test_no_pending_topics_returns_no_data PASSED
tests/test_pick_hugo_fallback.py::TestBothCandidatesMissing::test_persona_pick_and_top5_rank_both_fail PASSED
tests/test_pick_hugo_fallback.py::TestDuplicateTopicPrevention::test_skip_ids_prevents_reslection PASSED

11 passed, 1 skipped, 1 warning in 1.66s
```

**신규 실패**: 0건

---

## 4. 문법 검증

```
python3 -m py_compile pipelines/car/pipeline.py        → OK
python3 -m py_compile pipelines/curation/pipeline.py   → OK
python3 -m py_compile tests/test_pick_hugo_fallback.py → OK
```

---

## 5. 운영 배포 대상

| 대상 | blog_id | 파일 | 배포 방식 |
|------|---------|------|-----------|
| **pick-hugo** | pick-hugo | `pipelines/car/pipeline.py` + `tests/test_pick_hugo_fallback.py` | dispatcher.py (Hugo 빌드 포함) |

**car-hugo, golf-hugo**: 이 커밋의 변경 영향 없음. 별도 복구안 필요 (products 0건 문제).

---

## 6. 영향 없는 블로그

| 블로그 계열 | 근거 |
|-------------|------|
| compare-hugo | compare.py 사용, car/pipeline.py 미사용 |
| hotissue-hugo | hotissue.py 사용, car/pipeline.py 미사용 |
| guide-hugo | guide.py 사용, car/pipeline.py 미사용 |
| deal-hugo | deal.py 사용, car/pipeline.py 미사용 |
| tco-hugo | tco.py 사용, car/pipeline.py 미사용 |
| rank-hugo | rank.py 사용, car/pipeline.py 미사용 |
| ev-hugo | ev.py 사용, car/pipeline.py 미사용 |
| curation 블로그 전체 | curation/pipeline.py net change 0줄 |

---

## 7. 롤백 절차

```bash
# 롤백 SHA: 037404d8aa406cf722c4a02badff26acf3f43a94
git revert --no-commit ae90ed63a d887e094f
git commit -m "revert(pick-hugo): fallback 로직 + 테스트 롤백"
```

---

## 8. 배포 전 조건

| # | 조건 | 상태 |
|---|------|------|
| 1 | pick-hugo 테스트 12건 통과 (1 skipped 제외) | ✅ |
| 2 | 문법 검증 3파일 통과 | ✅ |
| 3 | curation/pipeline.py net change 0줄 | ✅ |
| 4 | trims 기준 미변경 | ✅ |
| 5 | relevance threshold 미변경 | ✅ |
| 6 | KEYWORD_MAP 미변경 | ✅ |
| 7 | 운영 DB 미변경 | ✅ |

---

> **이 보고서는 READ-ONLY 감사만 수행했습니다. push·배포·재발행은 수행하지 않았습니다.**
