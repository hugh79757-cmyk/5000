---
status: complete
date: 2026-08-30
blogs: [travel3-hugo, sector-hugo, tour-hugo, michelin-hugo]
codes: [P01, P02, P25]
commits: []
---

# Summary: P01/P02/P25 fixes

## Fixes
- travel3 P01: pipelines/travel/pipeline.py food sigungu 3->1, skip place-name guard for food (contentid dedup already). Fixes name-collision no_result.
- sector P02: shared/content_store.py title_similar_exists date-aware (strip YYYY년 M월 D일, skip diff-date). Fixes daily date-stamped false duplicate.
- P25 tour+michelin: dispatcher.py Timer dead code -> ThreadPoolExecutor 150s real timeout (returns pipeline_timeout_150s). michelin_pipeline.py body images 8->3.

## Verification
- py_compile OK x4
- date-aware test: 2026-08-29 vs 2026-08-30 same body ratio 1.0 but not flagged (before: flagged)
- dispatcher timeout now real, not dead code

## Remaining
- cooldown daily_travel3/sector until 2026-08-31 auto-expire, next retry should succeed if fix correct
- STAP writer fallback title synthesis not needed (shared fix sufficient)
- tour image count kept 8 (if still slow, cut to 3 next)

