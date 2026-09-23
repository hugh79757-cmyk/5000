---
date: 2026-09-02
type: fix
status: resolved
---

# best fleet 3일 주기 + 랭크 셔플 + 썸네일 반복 수정

## What
best-* 9블로그 매일 발행 → 3일 1회로 전환. EarPods 썸네일 반복 3연속 발생 조사 및 수정. quota 2→5 변경 후 3일 gate로 재조정.

## Why
- CUAP bestcategories 1016 등 풀 17~25개, limit 10 고정 + rank ASC → 매일 동일 Top5 선택. _filter_used_products fallback이 products[:5] 원본 리턴이라 중복 차단 무효
- Coupang 랭크 하루 단위 변동 적음 — 매일 발행 비효율
- BEST_CACHE_DAYS=1 인데 하루마다 같은 10개 셔플 없으니 썸네일(products[0]) 고정

## Files changed
- pipelines/curation/pipeline.py — _run_inner 3일 interval gate 추가 (publish_log + content.db fallback), best branch limit 10→20, 일자기반 deterministic shuffle (hash(blog_id:today)), interval_skip을 telegram/consecutive_failures 제외
- config/blogs.d/cuap.yaml — 9 best daily_quota 2→5 (일시, 이후 gate로 3일 1회 제한)

## How
- _run_inner 맨 앞 quota 체크 직후 best-*만 3일 게이트: publish_log→published_products→publish_ledger 순으로 last 조회, fromisoformat + timezone 처리, now-last <3d이면 interval_skip 반환
- get_best_products limit 20으로 전체 풀 확보 후 _filter_used_products + _filter_cross_fleet_products 후 hash seed로 shuffle → 랭크 고정 해제, 일자마다 다른 순서
- fallback limit 20 동일, fallback 시에도 shuffle 유지
- interval_skip은 _tg_error / _consecutive_failures / monitor 미집계로 조용한 스킵

## Follow-up fix (2026-09-03): scheduler.py consecutive_failures

pipeline.py에서 interval_skip을 조용히 스킵하도록 했지만, **scheduler.py `_track_publish_result()`는 dispatcher의 non-success를 모두 실패로 집계** → 5회 연속 catchup 시도 후 P02 Telegram alert 발생.

**Scheduler fix**: `_SILENT_SKIP_REASONS` frozenset + `_track_publish_result(reason=None)` optional param. interval_skip/quota_met/similar_title/already_running은 consecutive_failures에서 제외.
- Triaged: `.planning/worklog/WL-20260903-scheduler-interval-skip-fix.md`
- verified: 4 unit tests pass, scheduler restarted, PID 45719

## Verification
- py_compile pipeline.py OK
- gate test: best-electronics last 2026-09-01T04:05 → now 09-02 → 1.1d 경과 → skip True 확인 (09-04 재발행 예상)
- shuffle deterministic 확인: hash seed 동일 시 같은 순서, 일자 바뀌면 다른 순서
- best_products counts: 1016 19, 1013 23, 1021 18 등 확인, API 200 유지
