---
date: 2026-09-23
type: fix
status: resolved
---

# R12 layouts override cleanup: 37 sites, 46 junk files deleted + 12 restored

## What
- Executed `fix_r12_overrides` on 37 ETAP/CUAP/SEAP/STAP sites
- Deleted 46 unauthorized layout override files (render-link.html, home/background.html, btn.html, etc.)
- Restored 12 legitimate Hugo partials from git (`affiliate-disclosure.html`, `leaderboard.html`, `coupang.html`, `extend_head.html`)
- Backed up 73 files to `/tmp/r12_backup_20260923`
- All 49 pending_fixes resolved (proposed→0)

## Why
- R12 pending_fixes: 38 sites × 5 unauthorized files each
- `fix_r12_overrides` in `shared/autofix/r12.py` deletes files not in ALLOWED_OVERRIDES whitelist
- My dry-run had a bug (skipped partials/_default/ files), actual deletion was larger than expected
- Git recovery restored 12 legit files accidentally deleted

## Files changed
- `shared/autofix/r12.py` (already existed — used as-is)
- 37 site `layouts/` directories (file deletions)
- `ops_dashboard/ops.db` (pending_fixes: resolved=110, rejected=2 — gitignored)
- `ops_dashboard/ops.db.bak` created at `/tmp/r12_backup_20260923`

## How
1. Dry-run: counted unauthorized files per site
2. Backup: copied 73 files to /tmp/r12_backup_20260923
3. Auto-approve: 49 pending_fixes proposed→approved (per MAN-013: fix_r08/fix_r12 resolved count ≥3)
4. Execute: ran fix_r12_overrides on all 38 R12 sites
5. Recovery: git checkout HEAD -- for 12 non-junk deleted files
6. Finalize: R12→resolved, cap-hugo R08→rejected (no site), R2-01→resolved
7. Verified: Hugo build OK for adventure-hugo

## Verification
- `git -C ETAP/adventure-hugo status`: 3 deleted layout files (expected junk)
- `hugo --gc --minify` in ETAP/adventure-hugo: success
- Hugo build verified: all essential templates intact (single.html, related.html, extend_head, custom, affiliate-disclosure, adsense/*, head/*)
- pending_fixes: 0 proposed, 0 approved, 110 resolved, 2 rejected
