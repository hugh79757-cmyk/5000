# Plan 8-4: Verification and Rollback

**Phase:** 8 — Content Cleanup
**Goal:** Verify deletion and provide rollback capability
**Mode:** verify
**Wave:** 2

## Objective

After batch deletion in Plan 8-3, verify that:
1. All flagged posts were deleted correctly
2. Hugo builds succeed for all affected blogs
3. No unintended posts were deleted
4. Rollback capability is available if needed

## Tasks

### 4.1 Post-deletion verification

Create verification script `scripts/phase8/verify_cleanup.py`:
1. Re-run detection script to confirm flagged posts are gone
2. Check that total post count decreased by expected amount
3. Verify no new errors in Hugo build logs
4. Generate verification report

### 4.2 Rollback capability

Add rollback function to deletion script:
1. Read `deletion_log.yaml`
2. Restore posts from backup directory
3. Support `--blog` and `--slug` filters for partial rollback

## Verification

- [ ] `scripts/phase8/verify_cleanup.py` exists
- [ ] Verification script confirms deletion
- [ ] Hugo build succeeds for all affected blogs
- [ ] Rollback script can restore deleted posts
- [ ] Final post counts match expectations
