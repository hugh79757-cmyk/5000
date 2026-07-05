# Phase 3: Content Validation System

## Phase Goal

Build an automated content validation system that prevents future content pollution by scoring each article's relevance before publish and logging audit data after publish. This makes the Phase 1 (CATEGORY_FILTERS) and Phase 2 (keyword pruning + product_name blocking) fixes **sustainable** — if filter gaps emerge, they are caught before reaching production blogs.

## Phase Scope

### In Scope
1. **Relevance scorer module** (`shared/relevance_scorer.py`) — standalone, testable, reusable scoring logic
2. **Pre-publish validation gate** — hooks into `_run_inner()` at line ~601, blocks low-relevance articles
3. **Post-publish audit logger** — extends `publish_log` table, logs scores after successful publish
4. **Weekly alert** — Telegram summary when off-topic rate exceeds 20% over past 7 days
5. **Per-blog threshold configuration** — override-able scoring thresholds per blog_id

### Out of Scope
- Manual review workflow (fully automated gate)
- UI dashboard for scores (Telegram notification only)
- Historical backfill of scores for already-published articles
- Changes to non-curation pipelines (gap, car, travel, senior, stap)
- New external dependencies (sqlite3 + Python stdlib only)
- Reopening Phase 1/2 filter decisions (CATEGORY_FILTERS/TITLE_BLOCKED left as-is)

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scoring basis | allowed keyword match count | Blog's own CATEGORY_FILTERS are the definitive persona definition — no separate config needed |
| Score normalization | `min(count / min_matches, 1.0)` per product | 1 matched keyword = partial relevance, 2+ = full; avoids false negatives for blogs with narrow allowed lists |
| Threshold granularity | Per-blog override dict in relevance_scorer.py | Blogs have different tolerance (health supplements = broader, laptops = stricter) |
| DB storage | New columns in existing `publish_log` | Single-source truth for publish events; no new table needed |
| Alert schedule | Called from scheduler.py alongside existing pipeline runs | No new daemon/cron needed; reuses existing launchd schedule |

## Success Criteria

| # | Criterion | Verification Method |
|---|-----------|-------------------|
| SC-01 | Newly generated article with products matching only 1 allowed keyword per product is blocked with "low_relevance" reason | Pipeline dry-run with deliberately weak keyword returns `low_relevance` |
| SC-02 | Articles with strong allowed keyword matches (3+ per product) pass the gate | Pipeline dry-run with strong keyword publishes normally |
| SC-03 | `publish_log` table has `avg_relevance_score` column populated after successful publish | `SELECT avg_relevance_score FROM publish_log WHERE blog_id='laptop-hugo' LIMIT 1` returns non-NULL float |
| SC-04 | Default threshold = 0.75; per-blog override loads correctly | Unit test confirms `get_threshold("health-hugo")` returns 0.65 |
| SC-05 | Weekly alert fires when off-topic rate > 20% in past 7 days | Unit test triggers alert threshold, confirms Telegram message format |
| SC-06 | Weekly alert does NOT fire when off-topic rate ≤ 20% | Unit test confirms no alert sent below threshold |
| SC-07 | Existing pipeline behavior unchanged for non-curation pipelines | No imports of relevance_scorer in non-curation code |

## Task Breakdown

---

### Wave 1 — Foundation (sequential: 3.1 first, then 3.2)

**Note:** Task 3.1 and 3.2 both write to `shared/relevance_scorer.py` (3.1 creates it, 3.2 appends). They are **sequential** — 3.2 must run after 3.1. Within Wave 2, 3.3 and 3.4 modify `pipeline.py` at different locations and can run in parallel.

#### Task 3.1: Build relevance scorer module (ALL functions)

**File:** `shared/relevance_scorer.py` (NEW)

**Contains ALL functions for:**
- Scoring (`score_product`, `score_products`, `get_threshold`, `passes_gate`)
- DB migration (`migrate_publish_log` — idempotent, catches duplicate column errors)
- Audit logging (`log_publish_audit` — extends publish_log with score columns)
- Weekly alert (`weekly_offtopic_report`, `run_all_weekly_reports`)

**Function-level specification:**

```python
# ── Per-blog scoring configuration ──
RELEVANCE_CONFIG: dict[str, dict] = {
    "default": {
        "threshold": 0.75,          # avg_relevance below this → gate blocks
        "min_keyword_matches": 2,    # allowed keywords matched for score=1.0
    },
    "laptop-hugo": {"threshold": 0.85},
    "health-hugo": {"threshold": 0.65},
    "baby-hugo":   {"threshold": 0.85},
    "beauty-hugo": {"threshold": 0.85},
}

OFFTOPIC_THRESHOLD = 0.20  # 20% — trigger weekly alert if exceeded


def score_product(product_name: str, category_name: str, allowed_keywords: list[str]) -> float:
    """Score a single product's relevance.
    
    Algorithm:
    1. Combine name + category (lowercased)
    2. Count how many allowed_keywords appear in combined string
    3. Return min(count / min_keyword_matches, 1.0)
    """

def score_products(products: list[dict], blog_id: str) -> dict:
    """Score all products for an article and return aggregate.
    
    Returns: {avg, min, scores, blog_id, threshold}
    
    Uses CATEGORY_FILTERS from pipelines.curation.pipeline.CATEGORY_FILTERS
    to get allowed_keywords for the blog_id.
    Imports CATEGORY_FILTERS at call time (not module level) to avoid circular imports.
    """

def get_threshold(blog_id: str) -> float:
    """Return effective threshold (blog-specific or default 0.75)."""

def passes_gate(scores: dict) -> tuple[bool, str]:
    """Check if article passes the relevance gate.
    
    Returns: (True, "") or (False, "low_relevance: avg=0.50 < threshold=0.75")
    """

def migrate_publish_log(db_path: str) -> None:
    """ALTER TABLE publish_log ADD COLUMN IF NOT EXISTS:
    - avg_relevance_score REAL
    - min_relevance_score REAL
    - product_count INTEGER
    - filtered_count INTEGER
    - validation_passed INTEGER DEFAULT 1
    
    Idempotent — catches 'duplicate column' OperationalError.
    Called at module import time (same pattern as _init_db() in pipeline.py).
    """

def log_publish_audit(db_path: str, blog_id: str, keyword: str, title: str, slug: str, scores: dict, passed: bool) -> None:
    """Insert audit row into publish_log with relevance scores.
    
    Extends _record_publish() with score columns.
    Called INSTEAD of _record_publish() when validation gate is active.
    """

def weekly_offtopic_report(db_path: str, blog_id: str) -> str | None:
    """Query publish_log for past 7 days. Calculate off-topic rate.
    
    Off-topic definition: avg_relevance_score < blog threshold.
    
    Returns: None if rate ≤ 20%, formatted Telegram message string if > 20%.
    """

def run_all_weekly_reports(db_path: str) -> str | None:
    """Run weekly_offtopic_report for all 10 curation blogs.
    Returns combined Telegram message or None if no alerts.
    """
```

**Verification:**
```bash
cd /Users/twinssn/Projects/5000 && python -m pytest tests/shared/test_relevance_scorer.py -v
```

**Done when:**
- `score_product()` handles all edge cases (empty name, no keywords matched, 5+ matched)
- `score_products()` correctly imports CATEGORY_FILTERS and computes aggregate
- `get_threshold()` returns blog-specific override for baby/health/beauty, default for others
- `passes_gate()` correctly returns (False, reason) for low scores
- `migrate_publish_log()` is idempotent — safe for repeated runs
- `log_publish_audit()` inserts a row with all score fields populated
- `weekly_offtopic_report()` triggers at >20%, suppresses at ≤20%
- No side effects on any existing module

---

#### Task 3.2: DB migration execution + pipeline import hook

**File:** `pipelines/curation/pipeline.py` (add `migrate_publish_log()` call alongside existing `_init_db()`)

**Change:** Call `migrate_publish_log()` at module load time, alongside the existing `_init_db()` call at line 98.

After:
```python
from shared.relevance_scorer import migrate_publish_log

_init_db()
migrate_publish_log(str(DB_PATH))  # ensures publish_log has score columns
```

**Verification:**
```bash
python -c "from shared.relevance_scorer import migrate_publish_log; migrate_publish_log('data/curation.db')" \
  && sqlite3 data/curation.db ".schema publish_log" | grep -q avg_relevance_score \
  && echo "OK"
```

**Done when:**
- `migrate_publish_log()` runs automatically on pipeline startup (no manual step)
- Pipeline starts successfully even if columns already exist (idempotent)
- `grep` confirms `avg_relevance_score` is in `publish_log` schema

---

### Wave 2 — Integration (depends on Wave 1)

#### Task 3.3: Pre-publish validation gate in `_run_inner()`

**File:** `pipelines/curation/pipeline.py` (line ~601-605)

**Change:** Insert relevance scoring between `_filter_irrelevant_products()` and the `< 3` guard.

Before (current):
```python
products = _filter_irrelevant_products(blog_id, keyword, products)
if len(products) < 3:
    logger.error(...)
    return {"success": False, "reason": "irrelevant_products"}
```

After:
```python
from shared.relevance_scorer import score_products, passes_gate

products = _filter_irrelevant_products(blog_id, keyword, products)
if len(products) < 3:
    ...

# ── Relevance Scoring Gate ──
try:
    scores = score_products(products, blog_id)
    passed, reason = passes_gate(scores)
    if not passed:
        logger.warning(f"[{blog_id}] 관련성 점수 미달: {scores['avg']:.2f} < {scores['threshold']}")
        _record_failure(blog_id, "low_relevance", f"관련성 점수 {scores['avg']:.2f} < 임계값 {scores['threshold']}", keyword)
        return {"success": False, "reason": "low_relevance"}
    logger.info(f"[{blog_id}] 관련성 점수: avg={scores['avg']:.2f}, min={scores['min']:.2f}, 임계값={scores['threshold']}")
except Exception as e:
    # Fail open: scoring exception should not block publication
    logger.warning(f"[{blog_id}] 관련성 점수 계산 실패 (fail-open): {e}")
    scores = {"avg": 1.0, "min": 1.0, "scores": [], "blog_id": blog_id, "threshold": 1.0}

enrich_products(products, blog_id)  # unchanged
```

**Effect:** Articles where products barely match allowed keywords (only 1 match per product on average with default settings) are blocked with `"low_relevance"` reason. Telegram alert is sent via existing `_tg_error` in `run()`.

**Verification:**
```bash
cd /Users/twinssn/Projects/5000 && python -m pytest tests/curation/test_pipeline_relevance.py -v
```

Or manually via dry-run:
1. Add a test keyword that returns products with weak relevance
2. Run pipeline with `--dry-run`
3. Confirm reason = `low_relevance` and article is not published

**Done when:**
- Gate inserted at correct position (after filter, before enrich)
- `_record_failure` called with "low_relevance" reason
- `low_relevance` added to `_SILENT_REASONS` check in `run()`? (No — it should alert per the Phase 3 requirement. Only `quota_met`/`already_running`/`similar_title` stay silent.)
- Pipeline continues normally for products with strong relevance
- Gate handles scoring exceptions gracefully: try/except with fail-open (log warning, pass article)
- No imports of `relevance_scorer` in non-curation pipelines — `grep -r 'relevance_scorer' pipelines/gap/ pipelines/car/ pipelines/travel/ pipelines/senior/ pipelines/stap/` returns empty

---

#### Task 3.4: Post-publish audit logging in `_run_inner()`

**File:** `pipelines/curation/pipeline.py` (line ~687-690)

**Change:** Replace `_record_publish()` with `log_publish_audit()` to capture scores.

Before (current):
```python
_record_publish(blog_id, keyword, title, slug)
_record_products(blog_id, keyword, products[:5])
```

After:
```python
from shared.relevance_scorer import log_publish_audit

# Enrich products happens before article generation — scores already exist from gate
# But scores were computed at gate time; we recompute here for accuracy 
# (enrich_products may have modified product data)
from shared.relevance_scorer import score_products
final_scores = score_products(products, blog_id)

log_publish_audit(
    str(DB_PATH),
    blog_id, keyword, title, slug,
    scores=final_scores,
    passed=True,
)
_record_products(blog_id, keyword, products[:5])
```

**Design choice:** Scores are recomputed after enrichment (not cached from gate) because `enrich_products()` may change product data (brand/maker fields). This also ensures the audit log reflects the exact products that were published.

**Verification:**
```bash
sqlite3 data/curation.db "SELECT blog_id, keyword, avg_relevance_score, min_relevance_score, product_count, validation_passed FROM publish_log ORDER BY id DESC LIMIT 5;"
```

**Done when:**
- After any successful publish, `publish_log` row has non-NULL `avg_relevance_score`
- Scores are readable via SQL query
- `_record_products` still works (no regression)
- `_record_publish()` is NOT called anymore (replaced by `log_publish_audit`)

---

### Wave 3 — Monitoring (depends on Wave 2)

#### Task 3.5: Weekly off-topic rate alert

**File:** `shared/relevance_scorer.py` (append `weekly_offtopic_report` function)  
**File:** `shared/telegram_notifier.py` (add `send_weekly_report` wrapper — optional, reuse `send()` directly)

**Function-level specification:**

```python
OFFTOPIC_THRESHOLD = 0.20  # 20% — trigger alert if exceeded

def weekly_offtopic_report(db_path: str, blog_id: str) -> str | None:
    """
    Query publish_log for past 7 days. Calculate off-topic rate.
    
    Off-topic definition: avg_relevance_score < blog threshold
      (i.e., this article would have been blocked if the gate existed — but might have been 
       published before Phase 3, or passed because product matched exactly 1 keyword)
    
    Returns:
        None if rate ≤ 20% (no alert needed)
        Formatted Telegram message string if rate > 20%:
        
        📊 [주간 리포트] off-topic 비율 경고
        블로그: {blog_id}
        기간: {start_date} ~ {end_date}
        발행: {total}건
        off-topic: {offtopic_count}건 ({rate:.1f}%)
        임계값 초과: {threshold*100:.0f}% > 20%
        
        상세:
        • {keyword} — avg={score:.2f}
        • {keyword} — avg={score:.2f}
        ...
    """

def run_all_weekly_reports(db_path: str) -> str | None:
    """
    Run weekly_offtopic_report for all 10 curation blogs.
    Returns combined Telegram message or None if no alerts.
    """

def get_last_week_range() -> tuple[str, str]:
    """Return (start_date, end_date) ISO strings for past 7 days."""
```

**Integration point:** Add to `scheduler.py` as a weekly job using `schedule.every().monday.at("10:00")`:

```python
# In scheduler.py:
from schedule import every
from shared.relevance_scorer import run_all_weekly_reports
from shared.telegram_notifier import send

every().monday.at("10:00").do(lambda: (
    (report := run_all_weekly_reports("data/curation.db")) and send(report)
))
```

**Dedup guard:** Store `last_weekly_alert_date` in a small DB table or a simple file. Skip if already sent this week. This prevents duplicate alerts if the scheduler restarts mid-week.

**Note:** The `schedule` library does NOT support `.every().week` natively. Use `.every().monday` which achieves the same cadence with clear day-of-week semantics. If the library version doesn't support `.monday`, use `.every(7).days` with a dedup file check.

**Verification:**
```bash
cd /Users/twinssn/Projects/5000 && python -m pytest tests/shared/test_relevance_scorer.py::test_weekly_report -v
```

Unit test creates a temporary DB with:
- 8 articles with avg_relevance_score = 0.90 (> threshold, on-topic)
- 3 articles with avg_relevance_score = 0.30 (< threshold, off-topic)
- Rate = 3/11 = 27.3% > 20% → alert triggered
- Confirm returned message contains "27.3%" and "off-topic: 3건"

Second test: 1 off-topic out of 10 → 10% ≤ 20% → no alert.

**Done when:**
- `weekly_offtopic_report()` queries recent 7 days correctly
- Off-topic rate calculation matches manual computation
- Alert triggers at >20%, suppresses at ≤20%
- Message format is readable Korean Telegram message
- Unit tests pass for both trigger and suppress cases

## Dependency Graph

```
Wave 1                    Wave 2                    Wave 3
┌─────────────────┐      ┌─────────────────┐      ┌──────────────────┐
│ Task 3.1        │      │ Task 3.3        │      │ Task 3.5         │
│ relevance_scorer│──────│ pre-publish     │      │ weekly alert     │
│ (new module)    │      │ gate in         │      │ (depends on      │
│                 │      │ pipeline.py     │      │ scored data in   │
│                 │      │                 │      │ publish_log)     │
│ Task 3.2        │      │ Task 3.4        │      └──────────────────┘
│ DB migration +  │──────│ post-publish    │
│ audit logger    │      │ audit log in    │
│ (schema change) │      │ pipeline.py     │
└─────────────────┘      └─────────────────┘
```

- Task 3.1 must complete before 3.2 (same file: 3.1 creates it, 3.2 adds import hook)
- Task 3.1 must complete before 3.3 and 3.4 (they import from it)
- Task 3.2 must complete before 3.4 (migration ensures DB columns exist; idempotent so safe)
- Task 3.3 and 3.4 are independent of each other but both depend on Task 3.1
- Task 3.5 depends on Wave 2 producing scored rows in publish_log

## Verification Strategy

| Task | Unit Test File | Type | What It Verifies |
|------|---------------|------|------------------|
| 3.1 | `tests/shared/test_relevance_scorer.py` | New | `score_product()`, `score_products()`, `get_threshold()`, `passes_gate()` |
| 3.2 | `tests/shared/test_relevance_scorer.py` | Same file | `migrate_publish_log()` idempotency, `log_publish_audit()` INSERT |
| 3.3 | `tests/curation/test_pipeline_relevance.py` | New | Gate blocks weak articles, passes strong ones; non-curation pipelines unchanged (grep: `grep -r 'relevance_scorer' pipelines/gap/ pipelines/car/ pipelines/travel/ pipelines/senior/ pipelines/stap/` returns empty) |
| 3.4 | SQLite query (manual/automated) | Integration | `publish_log` has score columns populated |
| 3.5 | `tests/shared/test_relevance_scorer.py` | Same file | `weekly_offtopic_report()` trigger/suppress logic |

**Test file structure:**

```
tests/
├── shared/
│   └── test_relevance_scorer.py    # Tests for Tasks 3.1, 3.2, 3.5
│       ├── test_score_product_basic_match
│       ├── test_score_product_multiple_matches
│       ├── test_score_product_no_match
│       ├── test_score_products_aggregate
│       ├── test_get_threshold_default
│       ├── test_get_threshold_blog_override
│       ├── test_passes_gate_above_threshold
│       ├── test_passes_gate_below_threshold
│       ├── test_migrate_publish_log_idempotent
│       ├── test_log_publish_audit_insert
│       ├── test_weekly_report_triggers
│       └── test_weekly_report_suppresses
├── curation/
│   └── test_pipeline_relevance.py  # Tests for Task 3.3
│       ├── test_gate_blocks_weak_relevance
│       └── test_gate_passes_strong_relevance
```

## Rollback Strategy

| Change | Rollback Action | Impact |
|--------|----------------|--------|
| `shared/relevance_scorer.py` | Delete the file. Remove import lines from pipeline.py. | Zero impact — no existing code depends on it. |
| `publish_log` new columns | `ALTER TABLE publish_log DROP COLUMN avg_relevance_score;` etc. | Existing rows lose score data, but `publish_log` works with original schema. |
| Pre-publish gate (line ~601) | Comment out the gate block, restore original code. | Pipeline returns to Phase 2 behavior (filter-only). |
| Post-publish audit (line ~687) | Revert to `_record_publish()`, remove `log_publish_audit()` call. | `publish_log` new columns become NULL for new rows. |
| Weekly alert | Comment out the scheduler integration call. | No monitoring but everything else works. |

**Rollback priority (fastest first):** Weekly alert → Post-publish audit → Pre-publish gate → Scorer module

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| False positives: blocking articles that should publish | Medium | Medium | Blog-specific thresholds per health/laptop/baby/beauty; `min_keyword_matches=2` is lenient (1 match = 0.5, not blocked at 0.75 threshold unless most products score 0.5); Monitor `low_relevance` Telegram alerts in first week |
| False negatives: poor articles passing the gate | Low | Low | Gate is additive — Phase 1/2 filters still active; Weekly off-topic report catches systemic issues |
| DB migration failure on production curation.db | Low | High | `migrate_publish_log()` catches `OperationalError` (duplicate column) and logs warning; Rolling backup in `data/backups/` |
| Circular import: relevance_scorer imports CATEGORY_FILTERS from pipeline.py | Medium | Low | `score_products()` uses lazy import inside function body, not module-level; Test confirms import works |
| Weekly alert floods Telegram | Low | Low | Alert only fires when >20% threshold exceeded; Aggregation is weekly, not daily; Rate limit = 1 message per week per blog |
| Scoring overhead slows down pipeline | Low | Medium | Scoring is O(n*m) where n ≤ 5 products, m ≤ 50 allowed keywords = 250 string operations max — negligible vs AI generation (seconds vs 30s+) |
| `enrich_products()` changes product names affecting recomputed scores | Low | Medium | Scores computed AFTER enrichment for accuracy; Variation is score drift ≤0.05 based on brand/maker field additions |
| Pre-publish gate exception crashes pipeline | Low | High | Gate wrapped in try/except with fail-open — logs warning, passes article through if scoring fails. See Task 3.3 exception handling pattern |
| Weekly alert sends duplicate messages | Low | Medium | Alert scheduled via `schedule.every().monday.at("10:00")` (not every loop iteration); dedup guard stores last-alert-date in DB |
| Substring keyword matching inflates relevance scores (e.g., "운동" matches "운동화") | Medium | Low | Conservative bias: inflated scores cause false negatives (passing borderline articles), not false positives (blocking good articles). Weekly report catches systemic issues |

## Execution Order

```yaml
order:
  - task_3.1: "shared/relevance_scorer.py — scoring functions"
  - task_3.2: "DB migration + log_publish_audit"
  - task_3.3: "Pre-publish gate in pipeline.py"
  - task_3.4: "Post-publish audit in pipeline.py"
  - task_3.5: "Weekly alert system"

parallel_groups:
  wave_1: [task_3.1, task_3.2]
  wave_2: [task_3.3, task_3.4]
  wave_3: [task_3.5]
```

Total tasks: 5 | Waves: 3 | Files modified: 3 (2 new + 1 edit) | DB migration: 1
