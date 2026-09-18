# Night Report — 2026-09-16

**Local time:** 2026-09-16 12:36 +07
**Commit window:** 21:15–next 06:00 KST (not open yet; scheduled tasks deferred)

## 1. Cron activation commit (STEP 1 — deferred to 21:15)

- `git log origin/main..main --stat`: EMPTY — no ahead commits. HEAD=origin/main=c0c5b2e99.
- `.github/workflows/publish.yml`: already regular `on:` block, exactly 5 schedule entries (23:30/03:10/06:35/10:30/13:45 UTC), no `#cron:` label, concurrency `publish-lock-car`, workflow_dispatch blog/dry_run, CAP_PAT clone, run_slot dry-run conditional.
- Working-tree diff for publish.yml vs HEAD: EMPTY after restoring unrelated env-key rename. Only worklog will stage at 21:15.
- Worklog: `.planning/worklog/WL-20260916-g1-cron-activation.md` (pre-count, execution, post-verification, ev dry-run evidence).
- Deferred: tag `pre-destructive-20260916-2115`, stage+commit publish.yml+worklog, push, verify `git show origin/main:.github/workflows/publish.yml`, IndexNow after push.

## 2. ev-hugo dry-run (STEP 2)

- `python scripts/run_slot.py ev-hugo --dry-run` → exit=0.
- R2: get_state 12/12 md5; put_state 12 objects + manifest; ops.db excluded. Log: `/tmp/ev_dryrun.log`.
- Cap repo reachable: `git ls-remote` HEAD `b7e470ab16b92e37af2ce4099e650690a0f03f2e`, main exists. No env var named `CAP_PAT`; exposed as `GHP_5000_TOKEN`. CI secret value still needs user confirmation.
- ev-hugo owner=mac; I1 runner guard blocks runner dispatch until owner flip. Manual `dry_run=false` dispatch remains prohibited.

## 3. G1 readiness audit (STEP 3)

- Artifact: `.planning/phases/phase-81-g1-car-cap-migration/G1_READINESS.md`.
- Blogs audited: compare-hugo, deal-hugo, ev-hugo, guide-hugo, hotissue-hugo, rank-hugo.
- Summary: all 6 have available topics under 14/30/90-day guards; W5 candidate pools adequate (compare/deal/guide/hotissue 15, ev 11, rank 17 verified ≥5 images). Skip_dup low except hotissue (51). Skip_no_data high for ev (272) and guide (350). Latest publish: rank today 06:50; others yesterday.
- Flip order: compare → deal → guide → rank → ev → hotissue.
- B1 monthly estimate: ~2,130 min > 2,000 private limit; public conversion + OAuth rotation prerequisite.

## 4. Phase 81 proposal (STEP 4)

- `.planning/phases/phase-81-g1-car-cap-migration/PLAN.md` updated: G1 cron activation section, ev dry-run section, flip order, per-blog procedure, F-4 timezone normalization, B1 prerequisite. Status remains In Planning until G-C closes.

## 5. IndexNow status

- No push yet → no IndexNow submission this cycle. To be verified after 21:15 commit/push.

## 6. Morning verification (STEP 5 / tomorrow)

- First cron at 23:30 UTC (06:30 +07 next day). Verify 5/5 slots green, quota both frames ≤5, no KILL-SWITCH signals, usage tracking, 06:30 retrospective verification.
