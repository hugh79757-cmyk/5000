---
phase: 8
plan: 1
subsystem: content-cleanup
tags: [detection, script, python, hugo]
dependency_graph:
  requires: []
  provides: [detection-script, flagged-posts-data]
  affects: [scripts/phase8]
tech_stack:
  added: [python, pyyaml]
  patterns: [cli-script, yaml-output]
key_files:
  created:
    - scripts/phase8/detect_problematic_posts.py
    - scripts/phase8/flagged_posts.yaml
  modified: []
decisions:
  - Fixed path construction bug where blog_id already included -hugo suffix
  - Deduplication logic prevents posts flagged as both Chinese and offtopic from being counted twice
metrics:
  duration: 84s
  completed: "2026-07-04T04:36:50Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 8 Plan 1: Content Cleanup Detection Summary

Problematic post detection script for 10 CUAP Hugo blogs — identifies Chinese-titled and off-topic posts via blocked keyword matching.

## What Was Built

`scripts/phase8/detect_problematic_posts.py` — CLI tool that:
- Scans all 10 CUAP Hugo blogs (`laptop-hugo` through `camping-hugo`)
- Detects **Chinese-titled posts**: CJK characters in title with fewer than 5 Korean characters
- Detects **off-topic posts**: title or tags containing blocked keywords per `CATEGORY_FILTERS`
- Outputs results to `scripts/phase8/flagged_posts.yaml` with structured summary
- Supports `--dry-run` flag (default: no filesystem changes)
- Handles missing directories and malformed frontmatter gracefully

## Scan Results

| Metric | Count |
|--------|-------|
| Total posts scanned | 1,074 |
| Chinese-titled | 0 |
| Off-topic | 43 |
| Total flagged | 43 |
| Off-topic rate | 4.0% |

**By blog:**

| Blog | Flagged | Total Posts | Rate |
|------|---------|-------------|------|
| baby-hugo | 15 | 175 | 8.6% |
| laptop-hugo | 12 | 75 | 16.0% |
| appliance-hugo | 8 | 200 | 4.0% |
| health-hugo | 5 | 64 | 7.8% |
| fitness-hugo | 1 | 150 | 0.7% |
| pet-hugo | 1 | 26 | 3.8% |
| camping-hugo | 1 | 46 | 2.2% |
| interior-hugo | 0 | 213 | 0.0% |
| kitchen-hugo | 0 | 61 | 0.0% |
| beauty-hugo | 0 | 64 | 0.0% |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed path construction double-suffix bug**
- **Found during:** Task 8.1
- **Issue:** `blog_id` already included `-hugo` suffix, but path template added another `-hugo`, creating paths like `laptop-hugo-hugo/content/posts/`
- **Fix:** Changed path construction from `f"{blog_id}-hugo"` to `blog_id` in `scan_blog()`
- **Files modified:** `scripts/phase8/detect_problematic_posts.py`
- **Commit:** cf6848098

### Observations

**Off-topic rate lower than Phase 1 audit (4.0% vs ~36.5%)**
- Detection is keyword-specific in titles/tags only
- Phase 1 likely used broader content/category analysis
- The script catches clear-cut violations; a broader pass may be needed in Phase 8 Plan 2

## Known Stubs

None — script is fully functional with no placeholder data.

## Threat Flags

None — script performs local filesystem reads only, no network access, no sensitive data handling.

## Self-Check: PASSED

- [x] `scripts/phase8/detect_problematic_posts.py` exists
- [x] `scripts/phase8/flagged_posts.yaml` exists (232 lines)
- [x] Commit cf6848098 exists (feat)
- [x] Commit ebf9d050b exists (test)
