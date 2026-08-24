---
phase: "64"
plan: "06"
subsystem: "rule-system-evolution"
tags: ["registration", "reverse-validation", "promote", "self-improve", "charter"]
dependency_graph:
  requires: ["64-04", "64-05"]
  provides: ["RULE_REGISTRATION_RUNBOOK.md", "rule_reverse_validate.py", "rule_promote.py"]
  affects: ["ops_dashboard/db.py:SEED_STANDARD_RULES"]
tech_stack:
  added: ["scripts/rule_reverse_validate.py", "scripts/rule_promote.py"]
  patterns: ["argparse CLI", "regex in-place edit", "human approval gate", "JSONL validation report"]
key_files:
  created:
    - "docs/RULE_REGISTRATION_RUNBOOK.md"
    - "scripts/rule_reverse_validate.py"
    - "scripts/rule_promote.py"
  modified: []
decisions:
  - "Generalized existing c01_c08_reverse_validation.py into rule-agnostic reverse validator with --rule-id --positive-dir --negative-dir interface"
  - "Promote script enforces human approval via mandatory --approve flag (charter §6-2)"
  - "Runbook codifies 5-step pipeline with per-step checklists and artifact paths"
  - "Emergency bypass clause allows skipping 7-day observe for clear-cut critical issues with reverse-validation proof"
metrics:
  duration: "2h"
  completed_date: "2026-08-24"
---

# Phase 64 Plan 06: Rule Registration Runbook + Reverse-Validate + Promote Helper Summary

**One-liner:** 5-step rule registration pipeline (Discover→Observe→Reverse-Validate→Promote→Document) with generalized reverse validator and human-gated promote helper for safe rule severity escalation.

---

## Verification Results

| Verification Step | Command | Result |
|-------------------|---------|--------|
| Runbook has 단계 3 | `grep -c "단계 3" docs/RULE_REGISTRATION_RUNBOOK.md` | 4 ✅ |
| Runbook has 긴급 예외 | `grep -c "긴급 예외" docs/RULE_REGISTRATION_RUNBOOK.md` | 5 ✅ |
| Reverse validate --help has rule-id | `python scripts/rule_reverse_validate.py --help \| grep rule-id` | PASS ✅ |
| Promote without --approve exits 1 | `python scripts/rule_promote.py --rule-id C01 --from WARNING --to CRITICAL` | exit 1, "인간 승인 필요" ✅ |
| Promote with --approve succeeds | `python scripts/rule_promote.py --rule-id C01 --from MAJOR --to CRITICAL --approve` (on copy) | exit 0, severity updated ✅ |
| Demo validation on C01 data | `python scripts/rule_reverse_validate.py --rule-id C01 --positive-dir ... --negative-dir ...` | 3/3 detected, 0/3 false positive, exit 0 ✅ |

---

## Files Created

### 1. `docs/RULE_REGISTRATION_RUNBOOK.md` (12KB)

**5-Stage Registration Pipeline:**

| Stage | Name | Gate | Key Artifact |
|-------|------|------|--------------|
| 1 | **Discover** | `rule_feedback.jsonl` false_negative ≥3 or manual | `docs/candidates/CAND-XXX-spec.md` |
| 2 | **Observe (7d)** | WARNING severity, **no block** | `ops_dashboard/db.py` SEED add, preflight/dash registration |
| 3 | **Reverse-Validate** | **100% detection + 0% false positive** | `rule_reverse_validate.py` exit 0 + report table |
| 4 | **Promote** | **Human approval (`--approve`)** | `rule_promote.py` SEED severity update + checklist |
| 5 | **Document** | Category map + history update | `64-RULE-CATEGORIES.md`, runbook history table |

**Emergency Bypass Clause:** Clear-cut critical live issue + immediate reverse-validation proof (100%/0%) → skip 7-day observe, log reason in history. Max 2 uses/year.

### 2. `scripts/rule_reverse_validate.py` (19KB)

Generalized from `scripts/c01_c08_reverse_validation.py`:

```bash
python scripts/rule_reverse_validate.py \
    --rule-id S01 \
    --positive-dir scripts/validation_data/S01/positive \
    --negative-dir scripts/validation_data/S01/negative
```

- **Rule-agnostic**: `--rule-id` selects checker from registry (C01~C09 built-in, extensible)
- **Directory-based I/O**: `--positive-dir` (violation samples), `--negative-dir` (normal samples)
- **Gate**: `positive_detected == positive_total > 0` AND `negative_false_positives == 0` → exit 0, else exit 1
- **Output**: Console report table + `scripts/validation_data/{RULE_ID}/validation_result.json`
- **Demo**: C01 validation on demo data → 3/3 detected, 0/3 false positive ✅

### 3. `scripts/rule_promote.py` (8KB)

Human-gated SEED severity escalation:

```bash
# Fails without --approve
python scripts/rule_promote.py --rule-id S01 --from WARNING --to CRITICAL
# → exit 1, "human approval required per charter §6-2"

# Succeeds with --approve
python scripts/rule_promote.py --rule-id S01 --from WARNING --to CRITICAL --approve
# → regex replaces severity in ops_dashboard/db.py:SEED_STANDARD_RULES
# → auto-backup (.bak), verification, post-promote checklist
```

- **Mandatory `--approve`**: Enforces charter §6-2 human gate
- **Regex-based in-place edit**: Minimal diff, preserves formatting
- **Auto-backup**: Creates `.py.bak` before modification
- **Post-promote checklist**: Preflight lookup, dashboard display, Telegram alert, deploy gate, category map, runbook history

---

## Integration Points

| Component | Integration |
|-----------|-------------|
| `logs/rule_feedback.jsonl` | Stage 1 source (false_negative → candidate) |
| `ops_dashboard/db.py:SEED_STANDARD_RULES` | Stage 2/4 target (WARNING add / severity promote) |
| `dispatcher.py:preflight_check` | Stage 2 registration (WARNING rules = warn-only) |
| `ops_dashboard/checks/content_integrity.py` | Stage 2 registration (dashboard check function) |
| `64-RULE-CATEGORIES.md` | Stage 5 documentation (category mapping) |
| `scripts/rule_feedback_review.py` | Stage 1 trigger (monthly review → candidates) |

---

## Deviations from Plan

**None** — Plan executed exactly as written in 64-PLAN.md Task 64-06.

All verification criteria met:
- Runbook contains 단계 3 (step 3) and 긴급 예외 (emergency bypass) clauses
- Reverse validator accepts `--rule-id` argument
- Promote script requires `--approve` flag (exits 1 without, succeeds with)
- Demo validation on C01 data passes gate (100% detection, 0% false positive)

---

## Auth Gates

None encountered. All operations local file/script execution.

---

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: config_mutation | `scripts/rule_promote.py` | In-place regex edit of `ops_dashboard/db.py` SEED_STANDARD_RULES; mitigated by mandatory `--approve` flag, auto-backup, post-verification |

---

## Self-Check: PASSED

All created files exist and are executable. Commit 1ea5125ff contains exactly the three new files. Verification criteria from 64-PLAN.md Task 64-06 all pass.