# Track B — AdSense Response Self-Improvement Handoff

> Generated: 2026-08-20 | Session: PAUSED_HANDOFF

---

## 1. Track Identity

- **track_id:** TRACK_B_ADSENSE_SELF_IMPROVEMENT
- **status:** PAUSED_HANDOFF
- **objective:** Keyword Revenue Dashboard의 확인된 AdSense/GSC/GA4 데이터를 사용해 개선 가설과 recommendation을 만들고, 사람 승인형 실험과 전후 평가를 설계
- **operating_mode:** RECOMMENDATION_ONLY_SHADOW
- **implementation_authorized:** false
- **execution_authorized:** false
- **autonomous_decision_authorized:** false
- **commit_authorized:** false
- **push_authorized:** false

---

## 2. Repository State

| Field | Value |
|-------|-------|
| repository_root | /Users/twinssn/Projects/5000 |
| HEAD SHA | `cc926d2d1` (`docs: finalize checker trust-gate section 6 fixtures`) |
| current branch | `_rollback_test` |
| worktree status | Clean (no uncommitted changes to tracked files relevant to Track B) |
| untracked files (relevant) | `docs/CHECKER_TRUST_GATE_DESIGN_SECTION6.md` (untracked, Track A — do not touch) |
| modified files (relevant) | None specific to Track B |
| verified_at | 2026-08-20 |

**Note:** Branch `_rollback_test` is active. Track B design exists only in conversation — no spec file created yet.

---

## 3. Existing Authoritative Dependencies

### 3.1 Keyword Revenue Dashboard Spec

| Field | Value |
|-------|-------|
| path | `docs/superpowers/specs/2026-08-20-keyword-revenue-dashboard-design.md` |
| line count | 294 |
| SHA-256 | `b8116d3ab81673f9d7f59f06120182d5ac1629ff646465b493b59a358c19f175` |
| git status | TRACKED (committed) |
| latest commit | `a06e4c162` (`docs: spec rev.2 (metric naming, attribution layer, guardrails, score, P0 gates)`) |
| approval status | Sections 1-5 APPROVED (rev.2) |

**Key facts from this spec:**
- Data sources: adsense_daily (2393 rows, 110 domains, domain+date grain), gsc_keywords (373 rows, 218 keywords, blog_id+date+query grain), gsc_pages (0 rows), ga4_pages (exists)
- Metrics: ① estimated_keyword_revenue(k), ② estimated_revenue_per_organic_click(blog), ③ true EPC (attributed — unavailable)
- Attribution: A0 (blog_id↔domain), A1 (query↔page via gsc_pages — empty), A2 (page↔revenue — UNAVAILABLE), A3 (GA4 ad revenue — UNAVAILABLE)
- Guardrails G1-G9, Quality gates Q1-Q6 all approved
- "Estimated" label mandatory, 28-day trailing window (G3), data delay 1-3 days (G4)
- Phase 0→1→2→3→4 dependency chain

### 3.2 Phase 0 Implementation Plan

| Field | Value |
|-------|-------|
| path | `docs/superpowers/plans/PHASE0_REVENUE_IMPLEMENTATION_PLAN.md` |
| line count | 857 |
| SHA-256 | `35f3015288e8022bc53ba7073cd0bb490333192ee7ffbfb9c5940b0d1b138865` |
| git status | TRACKED (committed) |
| latest commit | `b2ef0585f` (`docs: Phase 0 revenue implementation plan (R1-R8, Q1-Q6)`) |
| approval status | APPROVED |

**Key facts from this plan:**
- 7 Tasks with Human Approval Gates
- Task 5: gsc_pages collection + page mapping (critical for A1 attribution)
- Phase 0 must complete before any threshold calibration

---

## 4. Existing Data Facts

| Fact | Status | Source |
|------|--------|--------|
| adsense_daily grain = domain + date | CONFIRMED | Keyword Revenue Dashboard Spec |
| AdSense revenue NOT usable for content-level attribution | CONFIRMED | Section 1 Amendment A1 |
| gsc_keywords grain = blog_id + date + query | CONFIRMED | Keyword Revenue Dashboard Spec |
| gsc_pages = 0 rows | CONFIRMED | Keyword Revenue Dashboard Spec |
| ga4_pages exists but grain unverified | CONFIRMED | Section 1 Amendment A8 |
| blog_id, slug, domain, canonical URL = existing identity | CONFIRMED | Codebase exploration (content_store.py, publisher.py, problem_detectors.py) |
| stable content_id | PROPOSED_NEW | Section 2 (UUID-based) |
| revision identity | PROPOSED_NEW | Section 2 (content hash + git commit) |
| change_set identity | PROPOSED_NEW | Section 2 |
| deploy identity | PROPOSED_NEW | Section 2 |
| observation snapshot | PROPOSED_NEW | Section 3 |

---

## 5. Approved Design Progress

### Section 1 — Data Sources & Observation Framework

**Status:** APPROVED_WITH_SECTION2_IDENTITY_DEPENDENCY

**Key decisions:**
- Paired pre/post comparison = primary baseline
- Rolling blog/context baseline = secondary
- Pre/post complete 28-day window required for terminal decision
- 14-day partial = diagnostic only
- Domain revenue = contextual evidence only (NOT content-level revenue)
- Content-level revenue claim prohibited
- Reporting completeness: source_name, expected_through_date, actual_complete_through_date, completeness_status, missing_partition_count, zero_value_confirmed, source_delay_policy_version
- Zero-value dates ≠ missing dates
- Allowed states: PENDING_DATA, INSUFFICIENT_DATA, ATTRIBUTION_UNCERTAIN, CONTAMINATED, KEEP, REJECT, ROLLBACK_REQUIRED, ABSTAIN
- Contamination: treatment (paired invalid), contextual (limits interpretation), site-wide (blocks causal)
- IMPARTIAL prohibited, publication age = auxiliary not primary

### Section 2 — Content Identity + ChangeSET Schema

**Status:** CONDITIONALLY_APPROVED_WITH_B1_B13

**Key decisions:**
- content_id = UUID, generated at first publish transaction start (NOT after live)
- Hugo frontmatter = durable identity SSOT
- articles.content_id = lookup mirror
- frontmatter/DB mismatch → IDENTITY_CONFLICT → ABSTAIN
- HTML/page source exposure = MISSING_CONTRACT until template renders content_id
- Revision = git commit + raw full-file SHA-256 (complementary, not alternative)
- Newline/encoding/YAML not normalized for hash
- Dirty baseline → DIRTY_BASELINE_UNTRUSTED → ABSTAIN (no stored hash substitution)
- Rollback requires recoverable bytes/artifact, not just hash
- change_set ↔ deploy via junction table (deploy_change_set), not dual FK
- Deploy identity: source_commit_id, build_artifact_fingerprint, deploy_target, provider_deployment_id, deploy_attempt_no, build_result, publisher_exit_code, evidence_reference
- Live verification separate from deploy success: BUILD_SUCCEEDED, DEPLOY_COMMAND_SUCCEEDED, LIVE_VERIFICATION_PENDING, LIVE_VERIFIED, LIVE_MISMATCH, LIVE_UNAVAILABLE
- Atomic deploy assumption not made without code/contract verification
- Observation snapshot: immutable, superseded_by pointer, snapshot_payload_sha256
- Metric availability: each metric requires actual schema + completeness confirmation
- source_account_ref (not raw account identifier, no secrets)
- Human approval mandatory for all write/publish/rollback
- deploy(blog_id, started_at) UNIQUE removed, deploy_id = primary key
- REDEPLOY (corrected from REDPLOY)
- Merge/split: separate content_ids, content_lineage table, duplicate_of/merged_into/split_into/migrated_from

### Section 3 — Snapshot, Evaluation, and Decision Contract

**Status:** CONDITIONALLY_APPROVED_WITH_C1_C12

**Key decisions:**
- technical_activation_at = live_verified_at
- measurement_window_start = first complete calendar day after live_verified_at in metric timezone
- No fixed washout period
- Source reporting delay = completeness gate, NOT washout
- GSC indexing delay = attribution/indexing readiness state, NOT washout
- Post-window date never moved after GSC observation (prevents selection bias)
- Deploy status: BUILD_SUCCEEDED + DEPLOY_COMMAND_SUCCEEDED + LIVE_VERIFIED
- Contamination eligibility: TREATMENT blocks paired evaluation, SITE_WIDE blocks domain revenue causal, CONTEXTUAL records but doesn't auto-block content-level pair
- Causal language prohibited: "content-associated pre/post change" OK, "causal effect confirmed" NOT OK
- Decision state fields separated: evaluation_state, evidence_classification, system_recommendation, human_decision, remediation_state
- ROLLBACK_REQUIRED = non-terminal (action-required workflow)
- Rollback workflow: ROLLBACK_REQUIRED → verify revision → approval pending → human approves → in progress → restore → deploy → live verify → ROLLED_BACK → new baseline decision
- Performance rollback needs full window; safety rollback is immediate
- Diagnostic snapshot cannot be used for terminal decision
- Guardrails G1-G9: improvement does not override guardrail regression
- Thresholds: all MISSING_DECISION_THRESHOLD (no approved quantitative thresholds exist)
- Context metric availability: domain↔blog_id mapping, pipeline/cohort definition, source completeness, aggregation contract required

### Section 4 — Improvement Hypothesis and Decision Policy

**Status:** APPROVED_FOR_RECOMMENDATION_ONLY_WITH_D1_D15

**Key decisions:**
- observed_signal (fact) and proposed_mechanism (theory) separated
- content-level signal and domain revenue context separated
- Confidence decomposed into 6 axes: attribution_quality, data_completeness, contamination_status, sample_adequacy, effect_uncertainty, metric_contract_compatibility
- gsc_query_demand cannot be sole hypothesis basis (demand context only, NOT content attribution)
- Improvement classes require provenance (source_path, rule/manual ID, version)
- Exact citation required for existing thresholds → THRESHOLD_NOT_FOUND if absent
- system_recommendation (KEEP_CANDIDATE|REJECT_CANDIDATE|ROLLBACK_CANDIDATE|ABSTAIN) ≠ human_decision (KEEP|REJECT|ROLLBACK_APPROVED|DEFER|OVERRIDE)
- decision_authority = HUMAN
- threshold_policy_version = null until approved
- Safety/deterministic guardrail violations → ROLLBACK_CANDIDATE (no 28-day wait)
- Cooldown/experiment limit numbers removed → UNCALIBRATED
- repeated_proposal_escalation = HUMAN_REVIEW_REQUIRED
- Hypothesis: observed_metric_records[], comparison_type, baseline_snapshot_id, evaluation_snapshot_id, computation_reference, evidence_hash, mechanism_status=HYPOTHESIS_NOT_FACT
- Multiple changes → change_isolation_status=MULTI_COMPONENT, effect_component_attribution=UNRESOLVED
- Section 4 = APPROVED_FOR_RECOMMENDATION_ONLY, auto performance decision BLOCKED_PENDING_THRESHOLD_POLICY

### Section 5 — Threshold Calibration & Governance

**Status:** PROMPT_PREPARED / NOT YET SUBMITTED

**Planned subsections:**
5.1 Threshold inventory
5.2 Estimand definition
5.3 Calibration population
5.4 Data partition
5.5 Candidate threshold generation methods
5.6 Sparse-data policy
5.7 Multi-metric policy
5.8 False action costs
5.9 Threshold versioning
5.10 Validation gate
5.11 Shadow mode
5.12 Approval authority
5.13 Drift monitoring
5.14 Implementation dependency
5.15 Acceptance criteria

---

## 6. Current Architecture Boundary

### Permitted Results (当前)

- Directional observation
- Contextual framing
- Hypothesis candidate
- Patch/recommendation proposal
- Uncertainty report
- Human decision request

### Prohibited Results

- Content-level AdSense revenue claim
- Content change causal effect confirmation
- Autonomous KEEP/REJECT without thresholds
- Autonomous content write
- Autonomous publish
- Autonomous rollback
- Ad click/impression manipulation
- Ad placement/policy auto-change

---

## 7. Missing Dependencies

| Dependency | Status | Required For |
|------------|--------|-------------|
| stable content identity (content_id) | PROPOSED, not implemented | All identity resolution |
| gsc_pages collection + page mapping | 0 rows | A1 attribution (content-level GSC) |
| blog identity mapping verification | EXISTS but unverified | Domain context metrics |
| GA4 page/date grain verification | UNKNOWN | A3 content traffic context |
| revision/change_set/deploy ledger | NOT IMPLEMENTED | Change tracking |
| live revision verification | NOT IMPLEMENTED | Deploy verification |
| immutable observation snapshot | NOT IMPLEMENTED | All paired comparisons |
| source completeness contract | NOT IMPLEMENTED | Reporting completeness |
| threshold calibration population | EMPTY | All threshold generation |
| approved threshold policy | NOT EXISTS | Autonomous decisions |
| shadow-mode validation data | NOT EXISTS | Threshold calibration |

---

## 8. Required Next Design

**Next session designs Section 5 only.**

Section 5 covers:
- Threshold inventory (what exists, what's missing)
- Estimand definition (what each metric estimates)
- Calibration population (eligibility criteria, current empty status)
- Data partition (calibration/validation/monitoring, no leakage)
- Sparse-data policy (recommendation-only when data insufficient)
- Candidate threshold generation methods (hybrid recommended)
- Multi-metric policy (hierarchical recommended)
- False-action costs (asymmetric: false KEEP > false REJECT)
- Threshold versioning (versioned policy lifecycle)
- Validation gate (promotion conditions)
- Recommendation-only shadow mode (before approval)
- Approval authority (human-only)
- Drift monitoring (post-approval)
- Implementation dependency (what must exist first)
- Acceptance criteria

**Rules:**
- Do not invent threshold values without approved calibration population
- Do not create autonomous decision capability
- Do not modify code, config, DB, content, or existing plans
- Do not fetch APIs, run tests, collect data, commit, push, deploy, or publish
- Do not read or incorporate Dashboard Checker Trust-Gate documents

---

## 9. Resume Prompt

```
RESUME_TRACK_B

Use the superpowers:brainstorming skill.

Read:
1. docs/handoffs/2026-08-20-track-b-adsense-self-improvement.md
2. docs/superpowers/specs/2026-08-20-keyword-revenue-dashboard-design.md
3. docs/superpowers/plans/PHASE0_REVENUE_IMPLEMENTATION_PLAN.md

Work only on Track B.
Do not read or incorporate Dashboard Checker Trust-Gate documents.

Continue from Section 5 — Threshold Calibration & Governance.
Treat Sections 1-4 according to the exact statuses and amendments recorded in the handoff.
Do not rewrite Sections 1-4.

Design recommendation-only shadow mode.
Do not invent threshold values without an approved calibration population and validation process.
Do not create or modify the final spec yet.
Do not modify code, config, DB, content, or existing plans.
Do not fetch APIs, run tests, collect data, commit, push, deploy, or publish.

Submit Section 5 in chat and ask one clarifying question.
Then stop for approval.
```
