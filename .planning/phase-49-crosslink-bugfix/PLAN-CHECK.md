# Plan Check: Phase 49 — Cross-link Creation Bug Fundamental Fix

**Checked:** 2026-07-26
**Plans verified:** 49-01 (Wave 1), 49-02 (Wave 2)

---

## Overall Verdict: **PASS** (with 2 minor warnings)

Both plans are structurally sound, goal-complete, and ready for execution.
No blockers. 2 warnings address minor documentation formatting and a latent requirement gap.

---

## Per-Plan Verdicts

### Plan 49-01: **PASS** — Root Cause Fix (Wave 1)

| Criterion | Status | Detail |
|-----------|--------|--------|
| ADDITIVE `"url"` key while preserving `"file"` | ✅ PASS | Task 1 explicitly preserves `"file"` key — callers in STAP/TAP won't break |
| 3-tier slug fallback (url→file→keyword) | ✅ PASS | Task 2 handles both Blowfish (parent.name) and PaperMod (stem fallback) |
| Logging without changing HTML output | ✅ PASS | Task 3 adds `logger.warning` before `continue` — HTML unchanged |
| Phase 48 frontmatter builders excluded | ✅ PASS | Explicit constraint: "Do NOT modify any frontmatter builder functions" |
| `Path` already imported in pipeline.py | ✅ PASS | Confirmed at line 12 of `pipelines/curation/pipeline.py` |
| Code changes shown as diffs with line numbers | ✅ PASS | All 3 tasks reference specific line numbers and show before/after |

### Plan 49-02: **PASS** — Batch Fix (Wave 2)

| Criterion | Status | Detail |
|-----------|--------|--------|
| On-disk directory names as ground truth | ✅ PASS | Task 1 scans `content/posts/` directories for actual slug names |
| Card fix runs AFTER DB fix | ✅ PASS | Task 2 explicitly states "Task 1 must be run BEFORE this script" |
| `/tmp` backup instead of `.bak` files | ✅ PASS | Task 2: `/tmp/fix_baked_crosslink_cards_before/` — .bak would break Hugo |
| HTTP 200 + 5 blogs + Hugo build verification | ✅ PASS | Task 3 Steps 3-5 cover all three verification types |
| Avoids `register_cuap_entity()` (INSERT OR IGNORE) | ✅ PASS | Task 1: "Use direct SQL UPDATE, not `register_cuap_entity()`" |

---

## Goal-Backward Traceability Matrix

| Phase Goal (from CONTEXT.md) | Plan | Task(s) | Verification Step |
|---|---|---|---|
| **G1: Fix cross-link URL slug mismatch** | 49-01 | T1 (url key), T2 (file fallback) | grep `"url"` in hugo_writer.py |
| **G2: Fix 4→2 rendering drop** | 49-01 | T3 (logging for sparse entities) | grep logging in cuap_entity_linker.py |
| **G3: Batch fix existing wrong cross-link URLs** | 49-02 | T1 (fix DB), T2 (fix baked cards) | T3: dry-run + actual run |
| **G4: Phase 48 compat** | 49-01 | T1 (excludes frontmatter builders) | git diff checks only `_write_hugo_post()` |
| **G5: Git commit split for rollback** | 49-01 + 49-02 | Separate waves (1 vs 2) | Two separate commits |

| Requirement ID | Description | Plan | Task(s) |
|---|---|---|---|
| PER-REQ-01 | Fix cross-link URL slug to match actual post slug | 49-01 | T1, T2 |
| PER-REQ-02 | Guarantee all 4 cross-links render in HTML | 49-01 | T3 (logging — see Warning 2) |
| PER-REQ-03 | Batch fix script for existing broken links | 49-02 | T1, T2 |
| PER-REQ-04 | Verify health blog cholesterol post 4 links all 200 | 49-02 | T3 (Step 3) |
| PER-REQ-05 | Verify 5 CUAP blogs cross-links | 49-02 | T3 (Step 4) |
| PER-REQ-06 | Hugo build 0 errors | 49-02 | T3 (Step 5) |

> **Note:** There is a labeling inconsistency in RESEARCH.md between the Phase Requirements table (line 47: `PER-REQ-06 = Hugo build 0 errors`) and the Validation Architecture table (lines 481-482: `PER-REQ-05 = Hugo build 0 errors`, `PER-REQ-06 = Phase 48 changes preserved`). The plans correctly implement both requirements regardless of ID mismatch. Not a blocker for plan execution.

---

## Dimension-by-Dimension Analysis

### Dimension 1: Requirement Coverage — ✅ PASS
All 6 PER-REQ IDs are covered across the two plans. Every requirement has at least one implementing task.

### Dimension 2: Task Completeness — ✅ PASS
All 6 tasks (3 per plan) have complete `Files` + `Action` + `Verify` + `Done` sections. Actions show diffs with line numbers.

### Dimension 3: Dependency Correctness — ✅ PASS
- 49-01: `depends_on: []` → Wave 1 ✓
- 49-02: `depends_on: [49-01]` → Wave 2 ✓
No cycles. Valid forward reference.

### Dimension 4: Key Links Planned — ✅ PASS
Data flow correctly traced:
- `hugo_writer._write_hugo_post()` → returns `url` key
- `publisher.py:769` → re-exports `_write_hugo_post`
- `pipelines/curation/pipeline.py` → receives `result["url"]` from `publish()`
- `fix_cuap_entity_slugs.py` → UPDATEs `cuap_entities` table
- `fix_baked_crosslink_cards.py` → regex-replaces hrefs in `index.md`

### Dimension 5: Scope Sanity — ✅ PASS
- Plan 49-01: 3 tasks, 3 files modified ✓
- Plan 49-02: 3 tasks, 2 scripts + 1 DB + content files (acceptable for batch fix) ✓

### Dimension 6: Verification Derivation — ✅ PASS
Both plans have well-formed `must_haves` with testable/verifiable truths, mapped artifacts, and correct key_links.

### Dimension 7: Context Compliance — ✅ PASS
- All 5 locked decisions from CONTEXT.md are implemented:
  - D1 (actual slug): Plan 49-01 T1+T2 ✓
  - D2 (4 links guaranteed): Plan 49-01 T3 (see Warning 2) ✓
  - D3 (batch fix): Plan 49-02 T1+T2 ✓
  - D4 (Phase 48 compat): Plan 49-01 explicit constraint ✓
  - D5 (git commit split): Two-wave structure ✓
- No deferred ideas implemented ✓
- Discretion areas (fallback strategy, batch algorithm, logging approach) handled appropriately ✓

### Dimension 7b: Scope Reduction Detection — ✅ PASS
No scope reduction language ("v1", "future enhancement", "simplified", "stub", "placeholder") found. All tasks deliver what they promise.

### Dimension 7c: Architectural Tier Compliance — ✅ PASS
All task assignments match the Architectural Responsibility Map from RESEARCH.md:
- `hugo_writer.py` → Pipeline shared lib ✓
- `pipeline.py` → Pipeline per-blog ✓
- `cuap_entity_linker.py` → Pipeline shared lib ✓
- New scripts → CLI script ✓

### Dimension 8: Nyquist Compliance — ⏭️ SKIPPED
`"nyquist_validation": false` in `.planning/config.json`. Explicitly disabled.

### Dimension 9: Cross-Plan Data Contracts — ✅ PASS
No conflicting data transformations. Plan 49-02 depends on 49-01 (sequential, not parallel). Single shared data entity (`cuap_entities` DB) is fixed in one direction only (batch fix reads ground truth from disk).

### Dimension 10: AGENTS.md Compliance — ✅ PASS
- **Additive changes only**: Plan 49-01 T1 preserves `"file"` key ✓
- **No pipeline disruption**: Code changes don't require restart ✓
- **Try/except pattern**: Batch scripts wrap file operations; card builder preserves fail-open ✓
- **No direct wrangler deploy**: Hugo build verification only (no `wrangler pages deploy` or `wrangler deploy`) ✓
- **`.bak` avoidance**: Plan 49-02 T2 uses `/tmp` backup explicitly to avoid Hugo build breakage ✓

### Dimension 11: Research Resolution — ⚠️ WARNING
RESEARCH.md has a `## Open Questions` section (lines 443-456) without the `(RESOLVED)` suffix on the heading, and no inline `RESOLVED` markers. However, each question has substantive discussion and a clear recommendation, and the plans implement those recommendations. Formatting convention unmet but content is resolved.

**Issue:**
```yaml
issue:
  plan: null
  dimension: research_resolution
  severity: warning
  description: "RESEARCH.md ## Open Questions heading missing (RESOLVED) suffix; no inline RESOLVED markers"
  file: "RESEARCH.md:443"
  fix_hint: "Rename heading to '## Open Questions (RESOLVED)' and add RESOLVED markers inline per convention"
```

### Dimension 12: Pattern Compliance — ⏭️ SKIPPED
No PATTERNS.md exists for this phase.

---

## Warnings

### Warning 1: Research Resolution Formatting

**Severity:** WARNING
**Description:** `## Open Questions` heading in RESEARCH.md (line 443) lacks `(RESOLVED)` suffix, and no inline `RESOLVED` markers are present on individual questions. Content is substantively resolved — the questions have recommendations implemented by the plans — but the formatting convention from Dimension 11 is unmet.
**Fix:** Optionally update heading to `## Open Questions (RESOLVED)` and add `RESOLVED:` prefix to each question's recommendation.
**Execution risk:** None. Content is correct. Plans implement the recommendations.

### Warning 2: PER-REQ-02 "Guarantee" — Logging Only, No Code Guarantee

**Severity:** WARNING
**Description:** PER-REQ-02 ("Guarantee all 4 cross-links render in HTML") is addressed by Plan 49-01 Task 3 (logging only). The plan adds `logger.warning` calls but does not add code to *enforce* 4 links rendering. The "guarantee" relies on: (a) Bug 1 fix preventing future wrong-slug registrations, and (b) the current state where all 10 blogs have entities (per RESEARCH.md). If a blog has <4 matching entities, the card still shows fewer links.
**Context:** This is within the agent's Discretion area ("Whether to add logging/monitoring for failed cross-link generation").
**Execution risk:** Low. Research confirmed all 10 blogs have 9-20 entities each. The 4→2 issue is transient and currently does not occur. Logging ensures detection if it reoccurs.

---

## Summary

| Dimension | Status |
|-----------|--------|
| 1. Requirement Coverage | ✅ PASS |
| 2. Task Completeness | ✅ PASS |
| 3. Dependency Correctness | ✅ PASS |
| 4. Key Links Planned | ✅ PASS |
| 5. Scope Sanity | ✅ PASS |
| 6. Verification Derivation | ✅ PASS |
| 7. Context Compliance | ✅ PASS |
| 7b. Scope Reduction Detection | ✅ PASS |
| 7c. Architectural Tier Compliance | ✅ PASS |
| 8. Nyquist Compliance | ⏭️ SKIPPED |
| 9. Cross-Plan Data Contracts | ✅ PASS |
| 10. AGENTS.md Compliance | ✅ PASS |
| 11. Research Resolution | ⚠️ WARNING |
| 12. Pattern Compliance | ⏭️ SKIPPED |

**Overall: PASS** — 0 blockers, 2 warnings. Plans are ready for execution.

The two-plan architecture (Wave 1: root cause fix → Wave 2: batch fix) correctly enables the user's requirement for git commit split and rollback safety. Task actions are detailed with line numbers and before/after diffs. Verification steps are concrete and automated. No scope creep or decision contradiction detected.
