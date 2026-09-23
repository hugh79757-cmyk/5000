---
date: 2026-08-28
type: fix
status: resolved
---

# stock-hugo 공시 duplicate_slug 연속실패 루프 수정

## What
stock-hugo DISCLOSURE 전략에서 매일 동일 슬러그로 새 rcept_no로 재발생하는 공시(웰컴저축은행)가 duplicate_slug를 내고, 기존 코드가 후보 1개만 시도 후 포기 → 5회 연속 실패 → 스케줄러 P02 consecutive_failures 스로틀을 유발. `_run_disclosure`에 후보 순회(candidate rotation) 로직 추가.

## Why
근본 원인: STAP `pipelines/stock/pipeline.py`의 `_filter_unpublished`가 rcept_no 기준만 중복 제거 → 재발생 공시(새 rcept_no, 동일 슬러그)가 빠져나감. LLM 체인 문제 아님(데이터/공시 재발생 이슈).

## Files changed
- /Users/twinssn/Projects/STAP/pipelines/stock/pipeline.py (`_run_disclosure` 후보 순회)

## How
`candidates[chosen_idx:]` 순회. `result.reason in (duplicate_slug, duplicate_title, duplicate_source_id)` → `_record_publish(disc, "duplicate_skipped")` 후 `continue`(다음 corp 시도). 성공 시 반환, 기타 실패 시 해당 result 반환, 소진 시 `fallback_evergreen`(기존 폴백 보존). 재무데이터 없으면 다음 후보로 skip(기존은 정지). E-corp 스킵 유지.

## Verification
- STAP에서 `python3 -m py_compile pipelines/stock/pipeline.py` → OK
- 로직 리뷰: 런 내 순회로 5연속 중단 제거. 일간 재발생은 런당 1회 중복 후 회복 → 스로틀 미발생
- NOTE: 5000/pipelines/stock/pipeline.py는 레거시/미사용(STAP 라우팅), 미변경. 미커밋(사용자 요청 없음)
