# Worklog: WL-20260916-g1-cron-activation

## Operation
G1 cron activation commit + push (destructive: git push), run at 21:15-06:00 local only.

## Pre-Count
- Ahead commits behind window start: 0 (`git log origin/main..main --stat` empty at 2026-09-16 12:14 KST)
- Target files staged: `.github/workflows/publish.yml` + this worklog
- publish.yml state at audit: regular `on:` block, 5 active schedule entries (23:30/03:10/06:35/10:30/13:45 UTC), no `#cron:` label, concurrency `publish-lock-car`, workflow_dispatch blog/dry_run, CAP_PAT clone, run_slot dry-run conditional. No diff from repo HEAD.
- Backup: git tag `pre-destructive-20260916-2115` created before push.

## G1 ev-hugo dry-run (2026-09-16 12:27 KST, dispatch-gate evidence)

- Command: `python scripts/run_slot.py ev-hugo --dry-run`
- Cap repo clone check: `git ls-remote https://x-access-token:${GHP_5000_TOKEN}@github.com/hugh79757-cmyk/ev-hugo.git` → HEAD `b7e470ab16b92e37af2ce4099e650690a0f03f2e`, `refs/heads/main` present. **No env variable named `CAP_PAT` exists; it is exposed to the runner as `GHP_5000_TOKEN`.** Site repo reachable; CI `secrets.CAP_PAT` value still needs user confirmation.
- Ev-hugo config: owner=mac, status=active, daily_quota=5, site_path=/Users/twinssn/Projects/cap/ev-hugo, schedule 06:45/10:25/13:50/17:40/21:00 +07, deploy_type=pages. Owner=mac blocks runner dispatch via I1 guard; runner flip deferred to Phase 81.
- Result: exit=0; `get_state` 12/12 md5; `put_state` 12 objects + manifest; ops.db excluded; log `/tmp/ev_dryrun.log`.
- Concurrency: no `publish-lock-car` held by this dry run (dispatcher skipped). Full runner path is validated by the first automatic runner slot; manual `dry_run=false` dispatch remains prohibited.

## Execution
1. `git tag pre-destructive-20260916-2115`
2. `git add .github/workflows/publish.yml .planning/worklog/WL-20260916-g1-cron-activation.md`
3. `git commit -m "chore(ci): G1 cron activation — publish.yml regular on-block verified + worklog"`
4. `git push origin main`
5. `git show origin/main:.github/workflows/publish.yml` verified schedule entries + publish-lock-car.
6. Append destructive log to `logs/destructive_2026-09-16.log`.

## Post-Verification
- Push OK / no conflicts: TBD in 21:15 run
- publish.yml on-block: 5 entries, no #cron label: TBD in 21:15 run
- Unintended files in commit: none (only worklog staged; publish.yml unchanged from HEAD so git add has no effect)
- IndexNow after push: TBD in 21:15 run
- ev dry-run evidence: R2 12/12 md5, put_state 12 objects + manifest, cap repo reachable via GHP_5000_TOKEN

## Logs
- logs/destructive_2026-09-16.log (will be appended at 21:15)
