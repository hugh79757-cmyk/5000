---
type: quick
slug: publish-errors-p01-p02-p25
created: 2026-08-30
severity: major
blogs: [travel3-hugo, sector-hugo, tour-hugo, michelin-hugo]
codes: [P01, P02, P25]
---

# Quick: P01/P02/P25 publish errors (travel3, sector, tour, michelin)

## Context
4 publish errors from scheduler/dashboard:
- travel3-hugo P01 no_result 4회 연속 (candidate exhaustion, name-based dedup)
- sector-hugo P02 no_content 9회 연속 (title_similar date-blind + LLM marker missing)
- tour-hugo P25 timeout 600s (dispatcher dead timer + heavy etap batch)
- michelin-hugo P25 timeout 600s (8 body images heavy)

## Plan
1. travel3 P01: pipelines/travel/pipeline.py _run_single place dedup relax (food source: skip is_place_used or threshold 2) + sigungu guard days 3->1 for food if trivial. Clear cooldown if needed. [P01]
2. sector P02: shared/content_store.py title_similar_exists date-strip before ratio + STAP writer fallback title synthesis (or keep minimal fix in shared only, STAP separate repo). Prioritize shared fix. [P02]
3. P25: dispatcher.py fix Timer dead code -> ThreadPoolExecutor 150s guard (real timeout). michelin_pipeline.py count 8->3. [P25 x2]
4. Verify: compile check, small unit demo for title dedup, scheduler timeout simulation.
5. Commit + update STATE.md quick table, keep destructive log.

## Verification
- travel3: place guard no longer blocks name collision when contentid fresh
- sector: "2026년 8월 29일 ..." vs "2026년 8월 30일 ..." not flagged duplicate
- dispatcher: pipeline >150s returns pipeline_timeout_150s not 600s kill
- michelin: image count 3

## Out of scope
- Full STAP pipeline refactor, full LLM chain tuning (separate)
