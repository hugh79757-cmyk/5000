---
phase: 61
reviewers: [opencode-subagent]
reviewed_at: "2026-08-07T16:35:00Z"
plans_reviewed: [61-01-PLAN.md, 61-02-PLAN.md, 61-03-PLAN.md, 61-04-PLAN.md, 61-05-PLAN.md, 61-06-PLAN.md, 61-07-PLAN.md, 61-08-PLAN.md, 61-09-PLAN.md]
note: "claude CLI auth failed (OAuth expired); opencode independent subagent used as cross-reviewer. Source-grounded against /Users/twinssn/Projects/5000."
---

# Cross-AI Plan Review — Phase 61

> Reviewer: independent opencode subagent (claude CLI unavailable due to expired OAuth).
> Context: phase 61, 9 plans, 6 waves.

## Review Summary

The plans form a coherent, additive, low-risk standardization effort (written standard → shared modules
→ pilot → rollout → external-contract alignment → scaffolding/reporting), and the dependency ordering is
sound. All existing-file targets are genuine; all new-artifact targets correctly do not exist. **No plan
targets any dead/mirror path** — the removed `5000/CUAP/health-hugo` is not referenced. The ETAP bridge
(`_ETAP_BLOG_EXCEPTIONS` @ dispatcher.py:444-446, `inspect.signature` @ 463-464) exists as claimed with
35 genuine `*_pipeline.py` + 35 `*_writer.py` pairs. Overall risk: **MEDIUM**.

## Path-Verification Results (user gate)

✅ No plan target points into any dead mirror. `5000/CUAP/` confirmed absent (removed precursor);
genuine `health-hugo` at `/Users/twinssn/Projects/CUAP/health-hugo`.

| Plan | Existing-file targets (genuine) | New-artifact targets (absent — correct) |
|------|--------------------------------|------------------------------------------|
| 61-01 | — | docs/PIPELINE-STANDARD.md |
| 61-02 | config_validator.py, problem_registry.py, test_problem_registry.py | shared/db.py, shared/subprocess_runner.py, test_db.py, test_subprocess_runner.py, test_config_schema.py |
| 61-03 | senior/pipeline.py(L116), rap/pipeline.py(L962) | senior+rap {topic_manager,enrich,validator}.py, test_pipeline_skeleton.py |
| 61-04 | car/pipeline.py(L26,L73) | car {fetcher,writer,enrich,validator}.py, test_skeleton_car.py |
| 61-05 | travel/pipeline.py(L413) | travel {topic_manager,enrich,validator}.py, test_skeleton_travel.py |
| 61-06 | curation/pipeline.py(L95,L836) | curation {fetcher,topic_manager,validator}.py, test_skeleton_curation.py |
| 61-07 | etap/pipeline.py, etap/topic_manager.py, 35× *_pipeline.py | etap/_contract.py, test_pipeline_skeleton.py |
| 61-08 | dispatcher.py(L380-440,L504-566) | tests/integration/test_subprocess_routing.py |
| 61-09 | — | scripts/scaffold_branch.py, test_scaffold_branch.py, 61-F-*-REPORT.md |

## Agreed Strengths

- Additive / non-destructive across all plans; D-08 separate-commit discipline well-specified.
- Dependency graph A→B→C→D1-4→E/F sound; pilot-first rollout correct.
- ETAP bridge preservation (dispatcher.py:444-465) is the most important safeguard and 61-07 handles it.
- `shared/db.py` scoped to path/connection only — no data move/mutation (tests assert `data/*.db` unchanged).
- No new third-party packages; `.bak`/dead-code handled report-only (destructive-ops honored).
- Config schema fields match config_validator.py:14-16 exactly.

## Agreed Concerns (highest priority — MUST correct before/at execution)

1. **travel DB path mis-targeting (61-05, HIGH):** travel/pipeline.py has NO inline DB constant; uses
   content.db (PUBLISH_LEDGER_DB) + stap_content.db (ARTICLES_DB) via shared.db_paths, NOT travel-en.db.
   → Rescope 61-05-2 Part B: do NOT wire `get_db_path('travel')→travel-en.db`. Document real dependency.
2. **flight_pipeline status-dict (61-07, HIGH):** `flight_pipeline.run(cfg)` returns `{"status":...}`
   without `success` key (flight_pipeline.py:139-168). The "leave dict as-is" rule skips it; `dispatch()`
   does `result.get("success")` (dispatcher.py:743) → flight success could be misclassified. → Normalize
   flight to `success/reason` or explicitly carve it out in PIPELINE-STANDARD.
3. **ETAP signature miscount (61-07, MEDIUM):** measured 24× `run()`, 10× `run(cfg=None)`, 1× `run(cfg)`
   (flight), NOT 21/14. Correct counts in plan/verification.
4. **db_paths TRAVEL_DB stale (61-02, MEDIUM):** `shared/db_paths.py:19` has stale `TRAVEL_DB=travel.db`
   (file is travel-en.db); avoid a third conflicting travel path in shared/db.py.
5. **`language_error` already registered (61-01/61-02, LOW):** already at problem_registry.py:272 (P12);
   drop from the "11 unregistered" to-add list.
6. **Indirect bool returns escape verification regex (61-07, MEDIUM):** heuristic `return True|False` misses
   `return result` (bool var). Adapter normalization must cover indirect bool returns.

## Additional Corrections

- Subprocess dedup "~400-line" is overclaimed — `_run_stap` is ~61 lines (dispatcher.py:380-440),
  `_run_tap_subprocess` ~63 (504-566) → ~124 lines. Right-size the claim.
- senior/rap/car/curation wrappers are pass-through placeholders (no existing module to delegate to) —
  document as placeholders, not misleadingly named.
- Dead-code report (61-09) must enumerate ALL inline DB constants per branch (car: CAR_DB_PATH
  pipeline.py:26 + DB_PATH daily_refresh.py:18; curation: 6 constants; rap: RAP_DB_PATH+GAP_DB_PATH).

## Divergent Views / Open Questions

- Normalize flight's `{"status":...}` now vs. document as exception. → Recommend normalize to
  `success/reason` for standard conformance.
- Whether `shared/db.py` should register a `travel` branch at all, given travel owns no dedicated DB file.
- Whether to keep the "~400-line" dedup framing in the phase summary (recommend ~124).

## Overall Risk Assessment

**MEDIUM.** Design is additive, non-destructive, correctly ordered; DB-path centralization will not move or
mutate real data (user's primary worry satisfied). Elevated risk stems from source-grounded accuracy gaps in
plans 61-02/61-05/61-07. None break existing live pipelines (additive, bridge preserved), so execution is
**safe** — but executing subagents MUST receive the corrections above to avoid shipping misleading wiring
and claims.
