# Phase 8: Content Cleanup — Delete Published Pollution

## Phase Goal

Clean up already-published problematic posts across 10 CUAP Hugo blogs. Phase 1-2 (keyword/filter refinement) and Phase 3 (Content Validation System) prevent NEW pollution. Phase 8 cleans up OLD pollution that already exists on production blogs.

## Phase Scope

### In Scope
1. **Detection script** — scan all 10 blogs for Chinese titles + off-topic posts
2. **Dry-run catalog** — list all flagged posts without modifying anything
3. **Human review checkpoint** — present catalog for user confirmation
4. **Post deletion** — remove confirmed posts from filesystem
5. **Rebuild + redeploy** — Hugo build and wrangler deploy each blog

### Out of Scope
- Deleting curation.db records (keyword rotation and dedup logic depends on them)
- Modifying post content (only full deletion)
- Changing blog structure or theme
- Cleaning non-CUAP pipelines (gap, travel, etc.)

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Detection method | filesystem scan + CATEGORY_FILTERS blocked keywords | No database queries needed — posts are markdown files on disk |
| Chinese detection | `[\u4E00-\u9FFF\u3400-\u4DBF]` regex + Hangul ratio check | Standard CJK Unicode ranges |
| Off-topic detection | title + tags match against per-blog blocked keyword list | Same logic as pipeline.py `_filter_irrelevant_products()` |
| Deletion approach | `rm -rf` on post directory | Blowfish theme uses directory-per-post format |
| Rollback | `git checkout` per blog repo | Each blog is separate git repo |
| Database preservation | Do NOT touch publish_log | Keyword rotation depends on 30-day TTL |

## Success Criteria

| # | Criterion | Verification Method |
|---|-----------|-------------------|
| SC-01 | Detection script finds all posts with Chinese characters in title | Script output shows Chinese-flagged posts; spot-check 3 |
| SC-02 | Detection script finds all off-topic posts per blog | Script output shows off-topic posts per blog; cross-reference with Phase 1 audit (36.5% rate) |
| SC-03 | Dry-run catalog lists all flagged posts without modifying anything | `flagged_posts.yaml` exists; no filesystem changes during dry-run |
| SC-04 | User reviews and confirms the deletion list | Human checkpoint step passes |
| SC-05 | Confirmed posts are deleted from filesystem | Deleted post directories no longer exist |
| SC-06 | All 10 blogs rebuild without errors | `hugo --gc --minify` succeeds for each blog |
| SC-07 | All 10 blogs deploy without errors | `wrangler deploy` or `wrangler pages deploy` succeeds |
| SC-08 | curation.db publish_log records are NOT modified | `SELECT COUNT(*) FROM publish_log` returns same count before/after |
| SC-09 | Accidentally deleted post can be restored via `git checkout` | Test restore of one post, then restore it back |

## Task Breakdown

---

### Wave 1 — Detection (sequential: 8.1 → 8.2, no side effects)

#### Task 8.1: Create detection script

**File:** `scripts/phase8/detect_problematic_posts.py` (NEW)

**Purpose:** Scan all 10 CUAP Hugo blogs and identify posts that should be deleted.

**Detection criteria:**
1. **Chinese title**: `title:` frontmatter contains `[\u4E00-\u9FFF\u3400-\u4DBF]` characters AND Korean character count < 5 (to avoid false positives on pure-Hangul titles)
2. **Off-topic**: Title or tags contain blocked keywords from the blog's `CATEGORY_FILTERS` entry. Use the same blocked list as `pipeline.py:175-299`.

**Algorithm:**
```
for each blog_id in [laptop, appliance, interior, baby, fitness, health, pet, kitchen, beauty, camping]:
  for each post_dir in /Users/twinssn/Projects/CUAP/{blog_id}-hugo/content/posts/*/:
    read index.md frontmatter
    extract title, tags
    if title contains CJK characters and Hangul count < 5:
      flag as CHINESE
    for each blocked_keyword in CATEGORY_FILTERS[blog_id]["blocked"]:
      if blocked_keyword in title.lower() or any(blocked_keyword in tag.lower() for tag in tags):
        flag as OFFTOPIC
        break
```

**Output format:** `scripts/phase8/flagged_posts.yaml`
```yaml
chinese:
  - blog: baby-hugo
    slug: "some-post"
    title: "中文标题示例"
    path: "/Users/twinssn/Projects/CUAP/baby-hugo/content/posts/some-post/index.md"

offtopic:
  - blog: beauty-hugo
    slug: "some-other-post"
    title: "생활용품 추천"
    reason: "생활용품"
    path: "..."

summary:
  total_flagged: N
  chinese: X
  offtopic: Y
  by_blog:
    baby-hugo: 5
    beauty-hugo: 12
    ...
```

**Verification:**
```bash
cd /Users/twinssn/Projects/5000 && python scripts/phase8/detect_problematic_posts.py --dry-run
cat scripts/phase8/flagged_posts.yaml | head -20
```

**Done when:**
- Script runs without errors
- Output shows flagged posts with correct blog, slug, title, reason
- Dry-run flag prevents any deletion
- All 10 blogs are scanned

---

#### Task 8.2: Run dry-run scan

**Purpose:** Execute the detection script to produce the flagged_posts.yaml catalog.

**Execution:**
```bash
cd /Users/twinssn/Projects/5000 && python scripts/phase8/detect_problematic_posts.py --dry-run
```

**Verification:**
```bash
cat scripts/phase8/flagged_posts.yaml
# Should show summary: total_flagged, chinese, offtopic, by_blog breakdown
```

**Done when:**
- `flagged_posts.yaml` is generated
- Summary stats look reasonable (off-topic rate ~30-40% based on Phase 1 audit)
- No filesystem changes occurred during scan

---

### Checkpoint — Human Review

#### Task 8.3: Present catalog for user confirmation

**Type:** `checkpoint:decision`

**Action:**
1. Read `flagged_posts.yaml`
2. Show summary to user: total flagged, breakdown by blog, reasons
3. Ask user: "이 글들을 삭제할까요?" with options:
   - "전체 삭제" — delete all flagged posts
   - "일부만 삭제" — user selects specific blogs or posts to keep
   - "취소" — abort, no deletion

**Gate:** Deletion cannot proceed without user confirmation.

---

### Wave 2 — Cleanup (sequential: delete → rebuild → deploy)

#### Task 8.4: Delete confirmed posts

**Input:** User-confirmed deletion list from Task 8.3

**Script:** `scripts/phase8/delete_posts.py` (NEW)

**Algorithm:**
```
for each post in confirmed_deletion_list:
  post_dir = /Users/twinssn/Projects/CUAP/{blog_id}-hugo/content/posts/{slug}/
  if post_dir exists:
    rm -rf post_dir
    log: deleted {blog_id}/{slug}
  else:
    log: SKIPPED {blog_id}/{slug} — directory not found
```

**Constraint:** Do NOT touch curation.db.

**Pre-flight check:** Before any deletion, verify each blog has a git repo for rollback:
```bash
for blog in laptop-hugo appliance-hugo interior-hugo baby-hugo fitness-hugo health-hugo pet-hugo kitchen-hugo beauty-hugo camping-hugo; do
  if [ -d "/Users/twinssn/Projects/CUAP/$blog/.git" ]; then
    echo "$blog: git repo ✅"
  else
    echo "$blog: NOT a git repo ⚠️ — rollback unavailable"
  fi
done
```

**Verification:**
```bash
# Count remaining posts per blog
for blog in laptop-hugo appliance-hugo interior-hugo baby-hugo fitness-hugo health-hugo pet-hugo kitchen-hugo beauty-hugo camping-hugo; do
  count=$(ls /Users/twinssn/Projects/CUAP/$blog/content/posts/ 2>/dev/null | wc -l)
  echo "$blog: $count posts"
done
```

**Done when:**
- All confirmed posts are deleted
- Deletion log shows what was removed
- No curation.db records modified

---

#### Task 8.5: Rebuild + redeploy all 10 blogs

**Script:** `scripts/phase8/deploy_blog.sh` (NEW)

**Algorithm per blog:**
```bash
BLOG_DIR=/Users/twinssn/Projects/CUAP/{blog_id}-hugo
cd $BLOG_DIR
hugo --gc --minify  # clean old outputs + minify
# Deploy based on blog type:
# Workers blogs: wrangler deploy --config wrangler.toml
# Pages blogs: wrangler pages deploy . --project-name={blog_id}
```

**Deploy method per blog:**
- Workers (6): laptop, appliance, interior, baby, fitness, health
- Pages (4): pet, kitchen, beauty, camping

**Constraints:**
- Sequential deployment (wrangler lock is global)
- Hugo builds are fast (~2-3s each)
- Wrangler deploys take ~5-10s each
- Total estimated time: ~2 minutes

**Verification:**
```bash
# For each blog, verify deploy succeeded
curl -s -o /dev/null -w "%{http_code}" https://{blog_id}.example.com/ | head -1
# Should return 200
```

**Done when:**
- All 10 blogs rebuild without Hugo errors
- All 10 blogs deploy without wrangler errors
- Live sites return 200 status
- Deleted posts are no longer accessible

## Dependency Graph

```
Wave 1                    Checkpoint              Wave 2
┌─────────────────┐      ┌──────────────────┐    ┌─────────────────┐
│ Task 8.1        │      │ Task 8.3         │    │ Task 8.4        │
│ detection script│──────│ human review     │────│ delete posts    │
│ (auto)          │      │ (checkpoint)     │    │ (auto)          │
│                 │      │                  │    │                 │
│ Task 8.2        │      │                  │    │ Task 8.5        │
│ dry-run scan    │──────│                  │────│ rebuild+deploy  │
│ (auto)          │      │                  │    │ (auto)          │
└─────────────────┘      └──────────────────┘    └─────────────────┘
```

- Task 8.1 → 8.2: sequential (scan then catalog)
- Task 8.2 → 8.3: checkpoint gate (human review)
- Task 8.3 → 8.4: sequential (user confirmation required)
- Task 8.4 → 8.5: sequential (delete before rebuild)

## Verification Strategy

| Task | Verification Method |
|------|-------------------|
| 8.1 | Script runs, output shows flagged posts, no errors |
| 8.2 | `flagged_posts.yaml` generated, summary stats reasonable |
| 8.3 | Human checkpoint passes, user confirms list |
| 8.4 | Deleted directories no longer exist; blog post count reduced |
| 8.5 | `hugo --gc --minify` succeeds; `wrangler deploy` succeeds; live site returns 200 |

## Rollback Strategy

| Change | Rollback Action | Impact |
|--------|----------------|--------|
| Posts deleted from filesystem | `git checkout HEAD -- content/posts/{slug}/` in blog repo | Restore individual post |
| curation.db records | NOT MODIFIED — no rollback needed | None |
| Blog redeployed with fewer posts | Rebuild and redeploy again if needed | Low impact — posts can be restored |

**Rollback priority (fastest first):** Blog redeploy → Post restore via git → Full git reset

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Accidentally delete non-off-topic post | Low | Medium | Human review checkpoint; git rollback per post |
| Hugo build fails after deletion | Low | Medium | Posts are self-contained; deletion shouldn't break build. If it does, restore via git |
| Wrangler rate limit (500 builds/month) | Low | Low | 10 builds per cleanup. ~500/month = 41/day available |
| Detection script false positives (Chinese) | Medium | Low | Human review confirms; Hangul ratio check reduces false positives |
| Detection script false positives (off-topic) | Medium | Low | Human review confirms; blocked keyword list is comprehensive |
| Cross-blog duplicate post deletion | Low | Low | Each blog is independent; no cross-blog references |
| Internal links break after deletion | Low | Low | Posts are standalone product recommendations; no internal linking structure |

## Execution Order

```yaml
order:
  - task_8.1: "scripts/phase8/detect_problematic_posts.py — detection script"
  - task_8.2: "Run dry-run scan → flagged_posts.yaml"
  - task_8.3: "Human review checkpoint"
  - task_8.4: "scripts/phase8/delete_posts.py — delete confirmed posts"
  - task_8.5: "scripts/phase8/deploy_blog.sh — rebuild + deploy"

parallel_groups:
  wave_1: [task_8.1, task_8.2]  # NOTE: sequential — 8.2 depends on 8.1's output
  checkpoint: [task_8.3]
  wave_2: [task_8.4, task_8.5]
```

Total tasks: 5 | Waves: 3 (2 auto + 1 checkpoint) | Scripts: 3 | Files modified: 0 (filesystem deletion only)
