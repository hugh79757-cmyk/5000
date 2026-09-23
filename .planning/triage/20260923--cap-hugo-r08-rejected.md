---
date: 2026-09-23
type: fix
status: resolved
---

# cap-hugo R08 stale canary: rejected (no site path)

## What
- Pending fix cap-hugo R08 (id=111) marked as rejected
- cap-hugo has no blog_lifecycle entry, no site_path, not in config/blogs.d/*.yaml
- All other cap-hugo R08 entries (44) are dummy/canary from Phase 71 testing

## Why
- cap-hugo R08 was approved during GSD Quick task but has no actual site to fix
- Site doesn't exist in codebase — likely renamed or removed
- Safe to reject: canary entry, no production impact

## Files changed
- `ops_dashboard/ops.db` (pending_fixes id=111: approved→rejected — gitignored)

## How
- Identified cap-hugo has no blog_lifecycle entry
- Confirmed not in config/blogs.d/*.yaml
- Marked as rejected per safety protocol

## Verification
- `sqlite3 ops.db "SELECT status FROM pending_fixes WHERE blog_id='cap-hugo' AND action='fix_r08'"`: 44 resolved, 1 rejected, 0 proposed
