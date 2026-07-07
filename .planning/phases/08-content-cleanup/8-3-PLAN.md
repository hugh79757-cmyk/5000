# Plan 8-3: Batch Deletion of Flagged Posts

**Phase:** 8 — Content Cleanup
**Goal:** Delete off-topic posts identified by detection script
**Mode:** execute
**Wave:** 1

## Objective

Based on the detection results in `scripts/phase8/flagged_posts.yaml`, delete 43 off-topic posts from CUAP Hugo blogs. The posts are flagged as `body_offtopic` - their body content contains keywords outside the blog's category scope.

## Tasks

### 3.1 Create batch deletion script

**File:** `scripts/phase8/delete_flagged_posts.py`

Create a script that:
1. Reads `flagged_posts.yaml`
2. For each post in `body_offtopic` list:
   - Moves the post directory to a backup location (`scripts/phase8/deleted/`)
   - Records the deletion in a log file
3. Supports `--dry-run` flag (default: true)
4. Supports `--blog` filter to delete only from specific blog
5. Creates backup with timestamp: `deleted/{blog}/{slug}_{timestamp}/`

### 3.2 Execute deletion with confirmation

Run the deletion script with user confirmation:
1. Show summary of posts to be deleted
2. Ask for confirmation
3. Execute deletion
4. Save deletion log to `scripts/phase8/deletion_log.yaml`

## Verification

- [ ] `scripts/phase8/delete_flagged_posts.py` exists
- [ ] Script runs with `--dry-run` without errors
- [ ] Backup directory structure is correct
- [ ] Deletion log is created with timestamp
- [ ] Hugo build succeeds after deletion
