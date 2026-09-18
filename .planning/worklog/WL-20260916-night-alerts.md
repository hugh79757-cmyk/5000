# 2026-09-16 Night Alert Exception Report

**Time:** 2026-09-16 14:54 +07
**Constraint:** failures no retry, immediate exception report; KILL-SWITCH not stimulated; quota frames ≤5.

## 1. toss-sl stockout (ids 161372869/162207275)

- Class: EXTERNAL_CRAWL_STOCKOUT — requires live removal + full crawl backfill.
- Action: NONE by pipeline. Live removal/full backfill is manual/scheduled work, not retry here.
- Report only. No catalog write.

## 2. Validate warning — rap3-hugo duplicate Jaccard 0.71

- Class: VALIDATION_WARNING — duplicate Jaccard 0.71 near threshold.
- Evidence: `logs/scheduler.log:252168-252172` — rap3-hugo 발행 성공 2026-09-16 14:49 KST; catchup no_topics symptom close + P34 close + retry reset.
- Action: NONE. rap3 already published after warning. Do not re-run validation/dispatch. Monitor next rap3 cycle.

## 3. beauty-hugo P04 — Hugo build failed

- Class: P04_DEPLOY_ERROR — build failed in CI, site live 200.
- Evidence: `logs/scheduler.log:251815-251883` — beauty-hugo failure 13:14 exception `모든 LLM tier 실패`, best-beauty-hugo collect_error 13:18; latest `curl https://pet.informationhot.kr` → HTTP/2 200.
- P04 while site live → FALSE-POSITIVE class per liveness guard, but build failure logged.
- Action: NONE by pipeline. No retry. Report to ops dashboard as P04 with liveness 200.

## 4. rank-hugo P04 — W5 image gate blocked (R13 body image 0)

- Class: P04_DEPLOY_ERROR — W5 image gate failure; site live 200.
- Evidence: alert report; `curl https://rank.informationhot.kr` → HTTP/2 200; no corresponding failure in `logs/scheduler.log` latest slice.
- P04 while site live → FALSE-POSITIVE class per liveness guard; image-gate defect logged.
- Action: NONE by pipeline. No retry. Report to ops dashboard as P04 with live site 200.

## 5. SAP network failure recovered after 2 tries

- Class: EXTERNAL_NETWORK — SAP data fetch failure, transient recovery.
- Evidence: `logs/scheduler.log:252117-252119` — 2026-09-16 13:51/13:52 SAP network failures; 13:53 scheduler continues; 13:59 last SAP failure; later slots recovered.
- Action: NONE. Transient network failure. Do not retry SAP fetch now.

## 6. ETAP quality issue — nightlife-hugo only 2 H2

- Class: ETAP_QUALITY — content quality warning; scheduler shows nightlife-hugo pipeline returned false at 14:35.
- Evidence: `logs/scheduler.log:252129-252136`; ETAP alert says nightlife-hugo only 2 H2.
- Action: NONE by pipeline. Failure already counted; do not retry. Report as quality defect for ETAP watcher.

## Summary table

| alert | blog | class | live | retry | report |
|-------|------|-------|------|-------|--------|
| toss-sl stockout | toss-sl | external stockout | unknown | no | yes |
| rap3 duplicate Jaccard 0.71 | rap3-hugo | validation warning | published 14:49 | no | yes |
| beauty-hugo P04 Hugo build failed | beauty-hugo | P04 deploy_error | 200 | no | yes |
| rank-hugo P04 W5 image gate | rank-hugo | P04 deploy_error | 200 | no | yes |
| SAP network failure | SAP | external network | recovered | no | yes |
| ETAP nightlife only 2 H2 | nightlife-hugo | ETAP quality | failed 14:35 | no | yes |
