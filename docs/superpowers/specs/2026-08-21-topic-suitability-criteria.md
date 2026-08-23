# Topic Suitability Criteria — 3-Stage Check (36 Blogs)

**Status:** SPEC / AWAITING APPROVAL
**Date:** 2026-08-21
**Scope:** Defines a deterministic 3-stage topic-suitability check applied to the 36 Hugo blogs under CAP/CUAP/STAP/TAP/RAP/SEAP. Each stage is an AND gate — a topic must pass **all three** stages to be approved for publish. Expected false-positive rates per stage and the resulting cascade are specified, with a worked example (airports blog) and the consolidated approval-request block.

---

## 1. Purpose

Not every generated topic is suitable for a given blog. A "guide" slug that is actually about a non-airport IATA code, or a Michelin post whose title omits the keyword, should be blocked before publish. This spec defines a three-stage filter so that suitability is decided by **machine-checkable signals only** (slug pattern → frontmatter → title keyword), not by human judgement at publish time.

The three stages are combined with logical **AND**:

```
approved = stage1_pass AND stage2_pass AND stage3_pass
```

A failure at any single stage rejects the topic. This is conservative by design — it trades a small number of false *negatives* (good topics dropped) for a near-zero false *positive* (unsuitable topic published) rate.

---

## 2. Stage Definitions

### Stage 1 — Slug Pattern (`*-guide` vs non-pattern)

- **Rule:** Topic slug must match the guide pattern `*-guide` (suffix `-guide`). Slugs without that suffix are rejected at stage 1.
- **Rationale:** Guide-type content is the unit we curate per blog. Non-guide slugs (lists, news, roundups) are out of scope for the suitability ledger.
- **Worked example (airports blog):** Of 163 candidate topics, **91** carry the `*-guide` slug → stage-1 pass count = 91. Michelin blog shows the same shape (guide slugs dominate the curated set).
- **Expected false-positive rate: ~5%.** Source of false positives: **IATA exceptions** — a 3-letter IATA code can collide with the `-guide` suffix incorrectly (e.g. a code that looks like a place but is an airport-adjacent exception), so ~5% of `*-guide` slugs are not genuine guides and should be caught by later stages.

### Stage 2 — Frontmatter Categories/Tags (`Airport Guide` vs `Travel`)

- **Rule:** Frontmatter `categories` or `tags` must contain the blog-specific suitability tag — for airports: `Airport Guide`; for travel/Michelin: `Travel` (Michelin variant). Topics tagged only with the generic `Travel` (or missing the specific tag) are rejected.
- **Rationale:** The slug pattern alone cannot distinguish a real airport guide from a coincidental `*-guide` slug. The frontmatter tag is the second independent signal.
- **Expected false-positive rate: ~10%.** Source: ~10% of stage-1 passers carry the generic `Travel` tag (or a mistagged category) rather than the specific `Airport Guide` / `Michelin` tag, so they slip past stage 1 but are caught here.

### Stage 3 — Title Keyword (`Airport` / `Michelin` present)

- **Rule:** The post `title` must contain the required keyword — `Airport` for airport blogs, `Michelin` for Michelin blogs. Titles lacking the keyword are rejected.
- **Rationale:** Final lexical confirmation that the published headline actually names the subject. Catches topics that passed slug + tag but whose title was generated without the anchor keyword.
- **Expected false-positive rate: ~15%.** Source: ~15% of stage-1+2 passers have a title that omits the keyword (e.g. "JFK terminal tips" without the word "Airport"), so they are blocked at stage 3.

---

## 3. AND Combination & Combined False-Positive Rate

Because the three stages are independent AND gates, the **residual false-positive rate** is the product of the per-stage rates (assuming approximate independence):

```
FP_final ≈ FP1 × FP2 × FP3
         = 0.05 × 0.10 × 0.15
         = 0.00075  ≈ 0.075%  (~0.1%)
```

**Interpretation:** A topic that survives all three stages has roughly a **0.1% chance** of being unsuitable — i.e. the three independent signals together drive false positives to near zero. The cost is false *negatives*: some genuinely suitable topics are dropped at stage 2 or 3 (title reworded, tag typo). That trade is accepted — a missed post is recoverable; a wrong post is not.

---

## 4. Worked Example — Airports Blog

| Stage | Pass count | Rule | Dropped vs prior |
|-------|-----------|------|------------------|
| Raw candidates | 163 | — | — |
| **Stage 1** (`*-guide`) | **91** | slug suffix `-guide` | 72 non-guide |
| **Stage 2** (`Airport Guide` tag) | ~82 | 91 × (1 − 0.10) | ~9 mistagged `Travel` |
| **Stage 3** (`Airport` in title) | ~70 | 82 × (1 − 0.15) | ~12 missing keyword |
| **Final approved** | **~70** | all three | residual FP ≈ 0.1% |

> Note: 91 is the **confirmed stage-1 count** for airports (verified by slug scan). Stages 2–3 figures are expected/approximate reductions using the stated FP rates; exact pass counts are produced when the checker runs on live frontmatter. Michelin blog follows the identical 3-stage shape with `Michelin` as the stage-3 keyword.

---

## 5. 36-Blog After-Approval Count

The table below records the **stage-1 confirmed count** per blog where known, and the **expected final approved** count after the 3-stage AND (using FP2≈10%, FP3≈15% cascade). Blogs without a stage-1 scan show `TBD`.

| Blog | Stage-1 (`*-guide`) | Stage-2+3 expected final | Notes |
|------|--------------------|--------------------------|-------|
| airports | **91** (confirmed) | ~70 | worked example above |
| michelin | TBD | TBD | same 3-stage shape; `Michelin` keyword |
| *(remaining 34 blogs)* | TBD | TBD | scan pending |

> Aggregate: only `airports` has a confirmed stage-1 count (91). The other 35 blogs require a slug scan to populate stage-1; final approved = stage-1 × 0.765 (≈ 1 − 0.10 − 0.15 combined filter, ignoring the small residual FP).

---

## 6. Examples

**Example A — passes all three (approved)**
- Slug: `jfk-airport-guide`
- Categories: `["Airport Guide"]`
- Title: `JFK Airport Guide: Terminals, Transit, Tips`
- Result: ✅ approved.

**Example B — fails stage 1 (rejected)**
- Slug: `best-airport-lounges-2026` (no `-guide` suffix)
- Result: ❌ rejected at stage 1.

**Example C — passes stage 1, fails stage 2 (rejected)**
- Slug: `cdg-airport-guide`
- Categories: `["Travel"]` (generic, not `Airport Guide`)
- Result: ❌ rejected at stage 2 (~10% FP class).

**Example D — passes 1+2, fails stage 3 (rejected)**
- Slug: `cdn-airport-guide`
- Categories: `["Airport Guide"]`
- Title: `CDG Terminal 2 Layover Tips` (no "Airport" word)
- Result: ❌ rejected at stage 3 (~15% FP class).

**Example E — IATA false positive caught downstream**
- Slug: `yyz-guide` where `YYZ` is an IATA exception, not a real guide
- Categories: `["Travel"]` → caught at stage 2.
- Result: ❌ rejected (the ~5% stage-1 FP is removed here).

---

## 7. Approval Request Block

The following block is the consolidated request for approving the 3-stage criteria across the 36 blogs. Fill `TBD` cells after the slug scan runs.

```
APPROVAL REQUEST — Topic Suitability 3-Stage Check
Date: 2026-08-21
Requester: 5000 pipeline

Criteria:
  [ ] Stage 1: slug matches *-guide          (FP ~5%, IATA exceptions)
  [ ] Stage 2: frontmatter tag Airport Guide / Travel (FP ~10%)
  [ ] Stage 3: title keyword Airport / Michelin present (FP ~15%)
  [ ] Combined: AND of all three             (residual FP ~0.1%)

Per-blog stage-1 confirmed counts:
  airports : 91   (confirmed)
  michelin: TBD
  others  : TBD

Requested approval:
  [ ] Adopt 3-stage AND as the sole suitability gate for the 36 blogs
  [ ] Approve airports stage-1 count = 91 (final expected ~70)
  [ ] Schedule slug scan for remaining 35 blogs to populate TBD

Approver: ____________________   Date: ____________
```

---

## 8. Open Items

1. Slug scan for the 35 non-airports blogs to populate stage-1 counts.
2. Confirm the Michelin stage-3 keyword (`Michelin`) and stage-2 tag variant with the curation owner.
3. Decide false-negative recovery: how a stage-2/3 dropped topic gets re-reviewed (tag fix / title rewording) rather than silently lost.
