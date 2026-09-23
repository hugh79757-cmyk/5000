---
date: 2026-08-28
type: fix
status: resolved
---

# fitness-hugo P02 연속실패 — CONCURRENCY 스킵을 실패로 오집계

## What
scheduler.py의 publish 슬롯 소진(CONCURRENCY skip) 경로가 `return False` 를 반환해, fleet 부하로 인한 일시적 스킵이 5연속실패 스로틀(P02)을 유발. `return None` 으로 변경(호출자가 None을 "스킵=실패 아님"으로 처리).

## Why
fitness-hugo P02 consecutive 5 failures 원인 분석: scheduler.log에서 5회 실패 대부분이 `[CONCURRENCY] publish 슬롯 풀 소진 (MAX_CONCURRENT=5)` 스킵이었음. 실제 콘텐츠 실패는 1건(irrelevant_products P14)뿐이고 이후 발행 성공. `run_publish` 시그니처는 `bool | None` 이며, 두 호출자(_drain_queue, catchup) 모두 `None` 을 실패 미집계(스킵)로 처리함. 단 CONCURRENCY 경로만 `False` 를 반환해 `bool(False)` → `_track_publish_result(blog_id, False)` → consecutive_failures 증가 → 임계값(5) 도달 → P02 오탐. (stock-hugo에서 이미 짐작했던 "CONCURRENCY 스킵이 실패로 집계됨" 2차 이슈의 실증.)

## Files changed
- scheduler.py (`run_publish` CONCURRENCY 스킵 `return False` → `return None`)

## How
슬롯 확보 실패 분기에서 `return False` → `return None` + 로그에 "(실패로 미집계)" 명시. availability_gate 스킵(기존 `return None`)과 동일 계약. 두 호출자 모두 `if _success is not None` / `if success is None: continue` 로 이미 None을 스킵 처리.

## Verification
- py_compile OK
- 로직: CONCURRENCY 스킵 → None → `_track_publish_result` 미호출 → consecutive_failures 미증가. 실제 콘텐츠/LLM 실패(`return False`)는 기존대로 집계 유지.
- 테스트: tests/test_candidate_availability.py 전체 ERROR는 사전 존재하는 autouse fixture(`_guard_prod_ops_db`, 운영 DB 가드) 셋업 실패로 인한 것 — 본 변경과 무관(코드 도달 전 실패). 본 수정은 1라인 계약 정합성 수정.
