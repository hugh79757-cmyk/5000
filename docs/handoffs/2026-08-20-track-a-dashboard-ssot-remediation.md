# Track A — Dashboard SSOT Autonomous Remediation Handoff

> **Generated:** 2026-08-20
> **Status:** PAUSED_HANDOFF
> **Session scope:** Design only — no code, DB, test, deploy, or commit changes

---

## 1. Track Identity

- **track_id:** TRACK_A_DASHBOARD_SSOT_REMEDIATION
- **status:** PAUSED_HANDOFF
- **objective:** Dashboard row를 SSOT로 사용해 evidence, versioned rule 및 remediation manual을 따라 오류를 진단하고, 사람 승인 후 수정·재발행·live recheck까지 완결하는 능력을 검증
- **operating_mode:** RECOMMENDATION_ONLY_SHADOW (until Experiment 0 passes)
- **implementation_authorized:** false
- **execution_authorized:** false
- **autonomous_decision_authorized:** false
- **commit_authorized:** false
- **push_authorized:** false

---

## 2. Repository State

| Field | Value | Source |
|-------|-------|--------|
| repository_root | `/Users/twinssn/Projects/5000` | git rev-parse --show-toplevel |
| HEAD SHA | `cc926d2d1a07d209ef7737b36409bd758b116a24` | git rev-parse HEAD |
| worktree status | detached HEAD on _rollback_test | git status |
| current branch | `_rollback_test` | git branch --show-current |
| tracked modified files | 15 (`.planning/`, `config/`, `ops_dashboard/checks/`, `pipelines/`, `scripts/`, `shared/`) | git status --short |
| untracked files | 90+ (`.omo/`, `.planning/worklog/`, `docs/`, `data/`, `logs/`, `tests/`, incident reports) | git status --short |
| verified_at | 2026-08-20, session m0186 | git commands executed |

### Conflict Notes

- Branch is `_rollback_test`, not `main`. All prior Section 6 work was committed to this branch.
- HEAD = cc926d2d (Section 6 commit) — this is the latest commit.
- No uncommitted changes to Section 6 file.

---

## 3. Authoritative Completed Work

### Section 6: Unit Fixture Architecture

| Field | Value | Verified |
|-------|-------|----------|
| file | `docs/CHECKER_TRUST_GATE_DESIGN_SECTION6.md` | ✅ exists |
| line count | 704 | ✅ `wc -l` |
| SHA-256 | `c5cb0bd8c25dc162652c789f3588422222633c484193d8b4fea5aeadab098c85` | ✅ `shasum -a 256` |
| commit | `cc926d2d1a07d209ef7737b36409bd758b116a24` | ✅ `git show --stat` |
| commit message | `docs: finalize checker trust-gate section 6 fixtures` | ✅ git log |
| parent | `ce973992224e25c565495f1d10b076dd86043cb5` | ✅ git show |
| tree | `b673bff27ffc9b459d70a9302f570e86c46957ed` | ✅ git show |
| files changed | 1 file, 704 insertions | ✅ git show --stat |
| status | COMMITTED/CLOSED | |

### Section 6 Fixture Inventory (reporting basis)

| Category | Count | Note |
|----------|-------|------|
| total fixtures | 53 | |
| assertion_type: VERDICT | 50 | |
| assertion_type: WORKFLOW | 2 | |
| assertion_type: DESIGN | 1 | |
| verdict: FAIL | 19 | |
| verdict: PASS | 26 | |
| verdict: UNC | 3 | |
| verdict: NOT_APPLICABLE | 2 | |
| provenance: TRACEABLE_EXECUTABLE | 44 | |
| provenance: SYNTHETIC_UNIT_ONLY | 8 | |
| provenance: NON_EXECUTABLE_CONTRACT_PENDING | 1 | |

### G5 Status

- **PENDING/BLOCKED** — Section 7 design in progress, no production gate opening authorized

---

## 4. Capability Discovery

Each item verified against actual code paths.

| Capability | Status | Evidence |
|-----------|--------|----------|
| check_results DB exists | **VERIFIED** | `ops_dashboard/db.py:110-122` — schema with 10 columns |
| latest-only UPSERT | **VERIFIED** | `db.py:1106-1108` — DELETE+INSERT per (blog_id, check_name) |
| checker plugin architecture | **VERIFIED** | `ops_dashboard/checks/__init__.py` — CHECKS dict, @register_check |
| 21 checkers registered | **VERIFIED** | standard(12), content_integrity(5), frontmatter(3), content_quality(1 aggregate), semantic(1), freshness(1), render(1), crosslink(1), data_stock(1), maintenance(1), crosscheck(1), indexnow(1), rap_leak(1) |
| SAFE auto-fix 4 exist | **VERIFIED** | `shared/autofix/__init__.py:91-101` — FIXERS dict: fix_draft_true, fix_featureimage_url_sanitize, fix_frontmatter_missing_keys, fix_thumbnail_r2 |
| non-SAFE → pending_fixes | **VERIFIED** | `db.py:162-176` — pending_fixes table, `db.py:2311+` — propose_pending_fix() |
| manual recheck API absent | **VERIFIED** | No `/api/recheck` in `app.py`. Only `scheduler._run_recheck_all()` for ALL blogs |
| rollback mechanism absent | **VERIFIED** | `shared/autofix/core.py` has backup_blog() (git tag/file copy) but no restore function |
| logs directory exists | **VERIFIED** | 49 log files including deploy.log, dashboard.log, destructive_YYYY-MM-DD.log |
| Hugo/wrangler deploy flow | **VERIFIED** | `shared/publishers/deploy.py`, `dispatcher.py:1633 lines` |
| Telegram notifier exists | **VERIFIED** | `shared/telegram_notifier.py` |
| known_issues table exists | **VERIFIED** | `db.py:95-108` — issue_id, blog_ids, symptom, category, gsd_status |
| readiness metrics exist | **VERIFIED** | `ops_dashboard/readiness.py:262 lines` — 3 green lights |
| rule registry exists | **VERIFIED** | `ops_dashboard/registry/rules.py:255 lines` — 18 UnifiedEntry |
| error registry exists | **VERIFIED** | `ops_dashboard/registry/errors.py:43 lines` — mirrors shared/problem_registry.py |
| problem registry exists | **VERIFIED** | `shared/problem_registry.py:751 lines` — P01-P34 + unknown |
| ERROR_PLAYBOOKS exists | **VERIFIED** | `ops_dashboard/docs/agent-reference/ERROR_PLAYBOOKS.md:215 lines` — per-problem playbook table |
| remediation queue exists | **VERIFIED** | `docs/VERIFIED_REMEDIATION_QUEUE.md:218 lines` — 196 FP breakdown |
| patch result exists | **VERIFIED** | `docs/DASHBOARD_CHECKER_PATCH_RESULT.md:125 lines` — before/after confusion matrix |

---

## 5. Purpose Drift

### Discarded Section 7 Direction

The original Section 7 (chat-only, never committed) was written as a "checker pilot" that:

1. Used Section 6 fixtures as remediation samples
2. Counted expected_verdict=FAIL fixtures as pilot failures
3. Redesigned pilot-v2.2 artifact chain (manifest, sampling, blind packets)
4. Proposed scheduler auto-reopening after pilot pass

### Why Discarded

Section 6 is a **checker contract regression** — it validates whether checker assertions mean what they claim. Section 7 must be a **remediation experiment** — it tests whether an agent can resolve real dashboard errors end-to-end. These are independent concerns:

| | Section 6 | Section 7 |
|---|-----------|-----------|
| validates | fixture assertion meaning | agent remediation capability |
| input | 53 frozen fixtures | live dashboard row |
| output | MATCH/MISMATCH/NOT_EXECUTABLE | CONFIRMED or ABSTAINED |
| relation | independent | depends on Section 6 APPROVED |

### Key Terminology Separation

- `expected_verdict`: what a fixture predicts (PASS/FAIL/UNC)
- `assertion_result`: whether checker reproduces the expected verdict (MATCH/MISMATCH/NOT_EXECUTABLE)

---

## 6. Current Section 7 State

| Item | Status |
|------|--------|
| capability matrix | ACCEPTED |
| original Section 7 design | PURPOSE_DRIFT_DETECTED |
| corrected Section 7 Final Amendment | PREPARED, NOT YET SUBMITTED (in chat, m0182) |
| Experiment 0 execution | NOT AUTHORIZED |
| Experiment 1 execution | NOT AUTHORIZED |
| Section 8 | NOT AUTHORIZED |
| G5 | PENDING/BLOCKED |

---

## 7. Required Next Design

The next session designs Section 7 Final Amendment covering:

1. **Dashboard SSOT completeness contract** — 20 fields classified as VERIFIED_EXISTING / DERIVABLE / MISSING_CONTRACT / NOT_IMPLEMENTED
2. **Rule/manual resolution matrix** — checker → rule_id → registry → manual → actionable mapping (9 fixers exist, 3 partial, 10+ MANUAL_MISSING)
3. **Remediation state machine** — 15 progression states + 16 blocker/failure states
4. **Experiment 0: READ_ONLY_RESOLUTION** — diagnosis + patch proposal + rollback plan, zero mutations
5. **Experiment 1: HUMAN_APPROVED_REMEDIATION** — full flow with human gate, NOT executed at this time
6. **Experiment 2: LIMITED_AUTONOMY** — future only, not designed
7. **Targeted recheck** — 3 levels (target / affected-set / full regression)
8. **Immutable before/after sidecar** — compensate for UPSERT history loss
9. **Rollback contract** — 9 requirements, none currently implemented
10. **Success metrics** — resolution_readiness_rate, diagnosis_accuracy, safe_patch_proposal_rate, abstention_rate (MISSING_THRESHOLD)
11. **First 1-row eligibility** — 11 criteria + 10 auto-exclusions

---

## 8. Known Blockers

| # | Blocker | Severity | Blocks |
|---|---------|----------|--------|
| 1 | rule_id → rule_version connection absent in DB | HIGH | Experiment 1 (versioned rule required) |
| 2 | remediation_manual_id/manual_version not versioned | HIGH | Experiment 1 |
| 3 | source mapping completeness unverified | MEDIUM | Experiment 0 (may cause ABSTAIN) |
| 4 | check_results history absent (UPSERT latest-only) | HIGH | Experiment 1 (before/after comparison) |
| 5 | targeted recheck interface absent | HIGH | Experiment 1 |
| 6 | rollback/restore/redeploy/live verification chain absent | HIGH | Experiment 1 |
| 7 | logs lack structured audit ledger format | MEDIUM | Experiment 1 |
| 8 | non-destructive patch verification absent | HIGH | Experiment 1 |
| 9 | G5 = PENDING/BLOCKED | BY DESIGN | Production gate |

---

## 9. Residual Risks

| # | Risk | Mitigation |
|---|------|-----------|
| 1 | SSOT_INCOMPLETE for many rows (source/action unanswerable) | Experiment 0 ABSTAIN is a valid result |
| 2 | 10+ checkers with MANUAL_MISSING — agent must ABSTAIN | Select rows with fixer-existing checkers for first trial |
| 3 | No rule_version — cannot distinguish rule versions | Record "version: absent" explicitly |
| 4 | UPSERT history loss — before state overwritten | Immutable sidecar snapshot (Experiment 1 only) |
| 5 | Rollback unimplemented | Experiment 0 evaluates plan only, not execution |
| 6 | Audit gap in existing logs | Experiment 0 logs to chat; Experiment 1 needs structured audit |

---

## 10. Exact Resume Prompt

RESUME_TRACK_A

```
Read:
1. docs/handoffs/2026-08-20-track-a-dashboard-ssot-remediation.md
2. docs/CHECKER_TRUST_GATE_DESIGN_SECTION6.md

Work only on Track A.
Do not read or incorporate the AdSense self-improvement track.
Do not reopen Section 6.
Do not resume pilot-v2.2.

Using the handoff's Required Next Design, submit the corrected Section 7 Final Amendment in chat only.

The Section 7 question is:
Can an agent take one actual Dashboard row and, using only Dashboard-linked evidence, a versioned rule, and a versioned remediation manual, produce a safe diagnosis and remediation plan without guessing?

Do not create or modify files.
Do not access or modify DB.
Do not run checkers, tests, builds, auto-fixes, deployments, publishing, commits, or pushes.
Stop after submitting Section 7 and request approval.
```
