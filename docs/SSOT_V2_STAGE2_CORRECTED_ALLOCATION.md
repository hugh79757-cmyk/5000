# SSOT V2 Stage 2 — Corrected Allocation Matrix & Governance Report

> **Date**: 2026-08-20
> **Status**: FINAL_APPROVED (design-only, not yet executed)
> **Supersedes**: V2 Plan合計 row (line 1184) — planned_n=90 is stale
> **Forensic closure**: `docs/SSOT_V2_ARTIFACT_FORENSIC_CLOSURE.md` — LEGACY_QUARANTINED_V1
> **pilot-v2.2 chain contract**: §14–§18 below — new execution design, no reuse of pilot-001 artifacts

---

## 1. Governance Defect: APPROVED_TARGET_90_VS_EXECUTED_ALLOCATION_97

**Classification**: GOVERNANCE_DEFECT (not cosmetic)

**Description**: The V2 Plan document's合計 row (line 1184) reports `planned_n=90`, but the sum of all 21 individual checker planned_n values in the same document's allocation matrix is **97**. The合計 was never updated after the allocation matrix was finalized with c06=8 and c01=8.

**Evidence**:
- V2 Plan line 1163-1183: 21 checkers with planned_n values summing to 97
- V2 Plan line 1184: 合計 row claims planned_n=90
- STAGE0_MANIFEST.json: `fail_target=90` (approved target)
- STAGE2_MANIFEST.json: `fail_allocation` total = 97 (actual execution)

**Impact**: The approved design (target=90) and the executed allocation (sum=97) diverged by 7 rows. The合計 row's `planned_n=90` masked this divergence.

**Root Cause**: c06_mtime_deploy and c01_curve_quote were added to the allocation matrix with planned_n=8 each (total +16 vs. a prior version that presumably had lower values), but the合計 row retained the pre-reconciliation value of 90.

---

## 2. Three Integrity Axes

| Axis | Status | Evidence |
|------|--------|----------|
| **Artifact integrity** | **INDETERMINATE** | STAGE2_MANIFEST hash changed during session (PROVENANCE_EVENT_1 vs PROVENANCE_EVENT_2); cause undetermined. Forensic closure: `docs/SSOT_V2_ARTIFACT_FORENSIC_CLOSURE.md` |
| **Sampling execution integrity** | **INDETERMINATE** | Manifest modification raises questions about sampling process provenance |
| **Approved-design conformity** | **INVALID** | Executed allocation sum=97 ≠ approved target=90; c06/c01 planned_n=8 each but available_N census=2/4;合計 row's planned_n=90 is stale |

---

## 3. Quarantine Designation

All existing Stage 2–3 artifacts are designated **QUARANTINED_ARTIFACT** — immutable preservation, no Pilot labeling.

| Artifact | SHA-256 | Status |
|----------|---------|--------|
| `sample.csv` | `b69e29f71643654404fb79d92396704fe4801be652ae41578791eb12722fe322` | QUARANTINED |
| `STAGE2_MANIFEST.json` | `a4a8a5be3e59c0ec17cb48c556d80e933a4f195e5c6f2c8d8e18808fb9a9d6c1` | QUARANTINED (note: hash differs from earlier session record `291b485b...` — file was modified during session) |
| `STAGE3_MANIFEST.json` | `df74282348fe72f3d5c3628b627260e94daf8ef9ad5f088b71594402196e6533` | QUARANTINED |
| `blind_packets/` (133 files) | directory intact | QUARANTINED |
| `sampling_frame.csv` | `1f16e8d225cd3ebb019233c15cf27d4781bca9b7895c326fce37f5d0fe6bea42` | QUARANTINED (reference) |
| `ops_snapshot.db` | `8c4fc4adeeaa28f3155b6e08a0cca141ddb0175b91f1907b4b46728c4fcc60ac` | QUARANTINED (reference) |
| `STAGE0_MANIFEST.json` | `e2eb2c621e901fc04e21d051d532c9a8f575eaffce07d164e9781296744d9c2c` | QUARANTINED (reference) |

**Quarantine rules**:
- Do NOT modify, delete, or move any quarantined artifact
- Do NOT use quarantined artifacts for Pilot labeling
- New execution must use a separate versioned output path

---

## 4. Separation of Historical vs. Revised

| Metric | Value | Column/Context |
|--------|-------|----------------|
| **Historical requested_n** | **97** | Original allocation matrix sum (c06=8, c01=8) — DO NOT use as denominator or target |
| **Structural shortfall** | **10** | c06: 8−2=6, c01: 8−4=10−6=4 — from available_N census |
| **Quarantined actual** | **87** | Existing sample.csv — artifact integrity VALID, design conformity INVALID |
| **Revised operational final_target** | **90** | Corrected allocation matrix below — to be executed in Stage 2 resampling |

**Rule**: Historical requested_n=97, structural shortfall=10, quarantined actual=87, and revised final_target=90 must never share the same column, denominator, or calculation.

---

## 5. Corrected Frozen Allocation Matrix

**Pilot fail target**: 90 (unchanged)
**c06/c01 treatment**: CENSUS (all available fail rows selected; diagnostic only, operational gate excluded)
**Redistribution rule**: +3 applied to non-c06/c01 checkers per V2 Plan rules (risk_tier desc → planned_n desc → available_N desc tie-break)

| check_name | risk_tier | historical_planned_n | available_N | final_target | redistribution | notes |
|---|---|---|---|---|---|---|
| c08_live_file_mismatch | HIGH | 15 | 85 | **15** | — | cap=15 (at cap) |
| FM-MISSINGKEYS | HIGH | 12 | 71 | **13** | **+1** | HIGH tier, avail_N=71, cap=15 |
| c06_mtime_deploy | HIGH | 8 | 2 | **2** | — | CENSUS; STRUCTURAL_SHORTFALL=6 |
| c01_curve_quote | HIGH | 8 | 4 | **4** | — | CENSUS; STRUCTURAL_SHORTFALL=4 |
| standard_compliance | HIGH | 8 | 40 | **9** | **+1** | HIGH tier, avail_N=40, cap=15 |
| THUMBNAIL-01 | HIGH | 6 | 36 | **7** | **+1** | HIGH tier, avail_N=36, cap=15 |
| FM-DRAFT | MEDIUM | 5 | 30 | **5** | — | cap=15 |
| content_quality | MEDIUM | 5 | 23 | **5** | — | cap=15 |
| semantic | MEDIUM | 5 | 22 | **5** | — | cap=15 |
| c03_fm_key_leak | MEDIUM | 4 | 20 | **4** | — | cap=15 |
| freshness | LOW | 3 | 14 | **3** | — | cap=15 |
| data_stock | LOW | 3 | 14 | **3** | — | cap=15 |
| R2-01 | LOW | 3 | 8 | **3** | — | cap=15 |
| maintenance_checklist | LOW | 2 | 6 | **2** | — | cap=15 |
| c04_prompt_leak | LOW | 2 | 5 | **2** | — | cap=15 |
| FM-FEATUREIMAGE | LOW | 2 | 4 | **2** | — | cap=15 |
| crosslink_consistency | LOW | 2 | 4 | **2** | — | cap=15 |
| rap_leak | LOW | 1 | 2 | **1** | — | cap=15 |
| render_health | LOW | 1 | 2 | **1** | — | cap=15 |
| R01 | LOW | 1 | 1 | **1** | — | cap=15 |
| R06 | LOW | 1 | 1 | **1** | — | cap=15 |
| **합계** | — | **97** | — | **90** | **+3** | historical=97, corrected=90 |

---

## 6. Redistribution Detail: +3

| checker_id | risk_tier | historical_planned_n | available_N | capacity (cap−current) | added | final_target | constraint check |
|---|---|---|---|---|---|---|---|
| FM-MISSINGKEYS | HIGH | 12 | 71 | 3 (cap=15) | +1 | 13 | 13 ≤ 71 ✓, 13 ≤ 15 ✓ |
| standard_compliance | HIGH | 8 | 40 | 7 (cap=15) | +1 | 9 | 9 ≤ 40 ✓, 9 ≤ 15 ✓ |
| THUMBNAIL-01 | HIGH | 6 | 36 | 9 (cap=15) | +1 | 7 | 7 ≤ 36 ✓, 7 ≤ 15 ✓ |

**Tie-break rationale**:
- FM-MISSINGKEYS (rank 2), standard_compliance (rank 3), THUMBNAIL-01 (rank 4) — all HIGH tier
- Sorted by: risk_tier desc → planned_n desc → available_N desc
- FM-MISSINGKEYS: planned_n=12 > standard_compliance=8 > THUMBNAIL-01=6
- c08 (rank 1, cap=15, at cap) excluded — no capacity remaining
- FM-DRAFT (rank 5, MEDIUM tier) excluded — +3 quota exhausted by HIGH tier

---

## 7. Mechanical Arithmetic Verification

```
final_target sum = 15 + 13 + 2 + 4 + 9 + 7 + 5 + 5 + 5 + 4 + 3 + 3 + 3 + 2 + 2 + 2 + 2 + 1 + 1 + 1 + 1
                 = 90 ✓

Constraint: final_target ≤ available_N for all 21 checkers
  c08:           15 ≤ 85  ✓
  FM-MISSINGKEYS: 13 ≤ 71  ✓
  c06:            2 ≤ 2   ✓
  c01:            4 ≤ 4   ✓
  standard_comp:  9 ≤ 40  ✓
  THUMBNAIL-01:   7 ≤ 36  ✓
  FM-DRAFT:       5 ≤ 30  ✓
  content qual:   5 ≤ 23  ✓
  semantic:       5 ≤ 22  ✓
  c03_fm_key_leak: 4 ≤ 20 ✓
  freshness:      3 ≤ 14  ✓
  data_stock:     3 ≤ 14  ✓
  R2-01:          3 ≤ 8   ✓
  maintenance:    2 ≤ 6   ✓
  c04_prompt_leak: 2 ≤ 5  ✓
  FM-FEATUREIMAGE: 2 ≤ 4  ✓
  crosslink:      2 ≤ 4   ✓
  rap_leak:       1 ≤ 2   ✓
  render_health:  1 ≤ 2   ✓
  R01:            1 ≤ 1   ✓
  R06:            1 ≤ 1   ✓

Constraint: final_target ≤ checker cap for all 21 checkers
  c08:           15 ≤ 15  ✓ (at cap)
  FM-MISSINGKEYS: 13 ≤ 15 ✓
  standard_comp:  9 ≤ 15 ✓
  THUMBNAIL-01:   7 ≤ 15 ✓
  FM-DRAFT:       5 ≤ 15 ✓

Total: 90 = 90 ✓
Redistribution: +1 +1 +1 = +3 ✓
Non-c06/c01 sum: 81 + 3 = 84 ✓
c06+c01: 2 + 4 = 6 ✓
84 + 6 = 90 ✓
```

---

## 8. Durability Risk: Untracked Hash Chain

**Status**: CRYPTOGRAPHICALLY_LINKED_BUT_NOT_GIT_ANCHORED

All provenance hashes (STAGE0→STAGE2→STAGE3→sample.csv) are internally consistent and SHA-256 verifiable. However, no artifact or plan document is committed to git.

| Risk | Description |
|------|-------------|
| `/tmp` single-location storage | All artifacts in `/tmp/ssot_v2_pilot/` — volatile filesystem, lost on reboot |
| Deletion risk | No backup; accidental `rm -rf` destroys entire audit trail |
| Independent recovery impossible | No git anchor means no remote backup, no reflog, no clone recovery |
| Hash chain self-referential | plan_document_hash `0c2d6fdb` references a version that was never committed |
| Session modification | STAGE2_MANIFEST.json hash changed during session (`291b485b...` → `a4a8a5be...`) — integrity of quarantined artifact requires investigation |

**Mitigation**: The corrected docs bundle (this file) provides a git-anchorable record of the corrected allocation. Path-scoped commit recommended after user approval.

---

## 9. Plan Document Corrections Required

The following untracked docs require correction to reflect the corrected allocation and quarantine lineage:

| File | Current State | Required Change |
|------|---------------|-----------------|
| `docs/DASHBOARD_SSOT_EXPERIMENT_V2_PLAN.md` (line 1184) | 合計 planned_n=90 | Update to planned_n=97, add note that合計 was stale |
| `docs/DASHBOARD_SSOT_EXPERIMENT_V2_PLAN.md` (lines 1165-1166) | c06/c01 final_n=2/4 with "STRUCTURAL_SHORTFALL" | Retain as historical; add corrected column referencing this document |
| `docs/SSOT_V2_PILOT_AUTHORIZATION_PACKET.md` | References original_plan_hash=0c2d6fdb | Add quarantine lineage and corrected allocation reference |

**These are docs-only changes. No code, no resampling, no DB changes, no commits until approved.**

---

## 10. Execution Plan (NOT YET EXECUTED)

**Stage 2 resampling plan**:
1. Create new versioned output path: `/tmp/ssot_v2_pilot_v2/` (separate from original)
2. Generate new sampling seed derived from corrected allocation + original seed
3. Re-run stratified sampling with corrected final_target values (sum=90)
4. Generate new sample.csv (90 fail rows + pass rows)
5. Generate new blind_packets/
6. Generate new STAGE2_MANIFEST.json with corrected allocation
7. Preserve original `/tmp/ssot_v2_pilot/` untouched

**Prerequisite**: Corrected allocation matrix (this document) approved by user.

---

## 11. Diff Summary (docs-only)

**New file**: `docs/SSOT_V2_STAGE2_CORRECTED_ALLOCATION.md` (this document)

**Files requiring correction** (pending approval):
- `docs/DASHBOARD_SSOT_EXPERIMENT_V2_PLAN.md` — 合計 row update + corrected column
- `docs/SSOT_V2_PILOT_AUTHORIZATION_PACKET.md` — quarantine lineage reference

**No commits, no resampling, no network fetch, no labeling, no DB access/change, no code changes, no push.**

---

## 12. Artifact Forensic Report (READ-ONLY)

### 12.1 STAGE2_MANIFEST.json Hash Provenance Events

| Event | Hash | Source | Status |
|-------|------|--------|--------|
| **First observed** | `291b485b...` | Computed during earlier session (opencode tool output `tool_01f185bc8001xHaLqx3ip8S4Dp`) | PROVENANCE_EVENT_1 |
| **Currently on disk** | `a4a8a5be3e59c0ec17cb48c556d80e933a4f195e5c6f2c8d8e18808fb9a9d6c1` | sha256sum of `/tmp/ssot_v2_pilot/STAGE2_MANIFEST.json` at 2026-08-20 | PROVENANCE_EVENT_2 |

**Neither hash is designated canonical.** Both are preserved as provenance events. The discrepancy indicates the file was modified between the two observation points.

### 12.2 Current STAGE2_MANIFEST.json Metadata

| Field | Value |
|-------|-------|
| Path | `/tmp/ssot_v2_pilot/STAGE2_MANIFEST.json` |
| Size | 3257 bytes |
| Creation time | 2026-08-20 12:01:02 UTC (kMDItemFSCreationDate) |
| Modification time | 2026-08-20 12:02:16 UTC (kMDItemFSContentChangeDate) |
| Elapsed (create→modify) | 74 seconds |
| Owner | twinssn (uid 501) |
| Extended attributes | `com.apple.provenance` (empty) |
| SHA-256 | `a4a8a5be3e59c0ec17cb48c556d80e933a4f195e5c6f2c8d8e18808fb9a9d6c1` |

### 12.3 Change Cause Investigation

| Source | Finding |
|--------|---------|
| Shell history (`~/.zsh_history`) | No entries referencing STAGE2_MANIFEST |
| Execution logs | No `.log` files in `/tmp/ssot_v2_pilot/` |
| Editor temp files | No `.swp`/`.swo`/`~` files found |
| Scripts in pilot dir | 20 scripts present; **none reference STAGE2_MANIFEST** |
| 5000 project scripts | No scripts in 5000 reference STAGE2_MANIFEST |
| Filesystem xattr | `com.apple.provenance` present but empty |
| Git reflog | No commits touching STAGE2_MANIFEST (all untracked) |
| Opencode tool output | One prior session output (`tool_01f185bc8001xHaLqx3ip8S4Dp`) contains manifest content |

**Conclusion**: The modification cause is **UNDETERMINED**. The most likely explanation is that the manifest generation process wrote an initial version at 12:01:02, then updated it at 12:02:16 (possibly to add the `sample_hash` after verifying sample.csv). However, no persistent script or log records this write. The modification was likely performed by an opencode Write tool call during a previous session.

### 12.4 OLD_CONTENT_UNAVAILABLE

The original content of STAGE2_MANIFEST.json (corresponding to hash `291b485b...`) is **not available**. No backup, git object, or log preserves the earlier version. Content diff between the two versions cannot be computed.

### 12.5 Referenced Artifact Hash Verification

| Artifact | Manifest claimed hash | Actual current hash | Match? |
|----------|----------------------|---------------------|--------|
| `sampling_frame.csv` | `1f16e8d225cd3ebb019233c15cf27d4781bca9b7895c326fce37f5d0fe6bea42` | `1f16e8d225cd3ebb019233c15cf27d4781bca9b7895c326fce37f5d0fe6bea42` | ✅ MATCH |
| `sample.csv` | `b69e29f71643654404fb79d92396704fe4801be652ae41578791eb12722fe322` | `b69e29f71643654404fb79d92396704fe4801be652ae41578791eb12722fe322` | ✅ MATCH |
| `ops_snapshot.db` (snapshot_hash) | `021a3b4f8fb7bb14b7977c1fb8c662b95277bcbd80278bc33d870397ace26e43` | `8c4fc4adeeaa28f3155b6e08a0cca141ddb0175b91f1907b4b46728c4fcc60ac` | ❌ MISMATCH |

**Note**: The `snapshot_hash` in the manifest does not match the `ops_snapshot.db` file hash. This may indicate the manifest's `snapshot_hash` is a content hash of the SQL query result (not the file), or the snapshot was modified after manifest creation. This is a separate integrity concern from the manifest's own hash change.

**Critical**: Even though `sample.csv` and `sampling_frame.csv` hashes match the manifest, the manifest's own immutability is NOT restored by this match. A modified manifest that happens to contain correct referenced hashes is still a modified manifest.

### 12.6 Complete Artifact Inventory (7 artifacts)

| # | Path | Type | Size (bytes) | SHA-256 |
|---|------|------|-------------|---------|
| 1 | `/tmp/ssot_v2_pilot/STAGE0_MANIFEST.json` | JSON | 1,033 | `e2eb2c621e901fc04e21d051d532c9a8f575eaffce07d164e9781296744d9c2c` |
| 2 | `/tmp/ssot_v2_pilot/STAGE2_MANIFEST.json` | JSON | 3,257 | `a4a8a5be3e59c0ec17cb48c556d80e933a4f195e5c6f2c8d8e18808fb9a9d6c1` |
| 3 | `/tmp/ssot_v2_pilot/STAGE3_MANIFEST.json` | JSON | 547 | `df74282348fe72f3d5c3628b627260e94daf8ef9ad5f088b71594402196e6533` |
| 4 | `/tmp/ssot_v2_pilot/sample.csv` | CSV | 49,718 | `b69e29f71643654404fb79d92396704fe4801be652ae41578791eb12722fe322` |
| 5 | `/tmp/ssot_v2_pilot/sampling_frame.csv` | CSV | 381,452 | `1f16e8d225cd3ebb019233c15cf27d4781bca9b7895c326fce37f5d0fe6bea42` |
| 6 | `/tmp/ssot_v2_pilot/ops_snapshot.db` | SQLite | 4,247,552 | `8c4fc4adeeaa28f3155b6e08a0cca141ddb0175b91f1907b4b46728c4fcc60ac` |
| 7 | `/tmp/ssot_v2_pilot/blind_packets/` | Directory (133 JSON files) | 532K total | Directory — individual file hashes not enumerated |

### 12.7 Revised Integrity Status

| Axis | Previous Status | Revised Status | Reason |
|------|----------------|----------------|--------|
| Artifact integrity | VALID | **INDETERMINATE** | STAGE2_MANIFEST hash changed during session; cause undetermined (forensic closure: `docs/SSOT_V2_ARTIFACT_FORENSIC_CLOSURE.md`) |
| Sampling execution integrity | VALID | **INDETERMINATE** | Manifest modification raises questions about sampling process provenance |
| Approved-design conformity | INVALID | **INVALID** (unchanged) | fail_allocation sum=97 ≠ approved target=90 |
| Quarantine | ENFORCED | **LEGACY_QUARANTINED_V1** | All 7 artifacts quarantined; no delete/modify/move/copy/reuse |

### 12.8 Redistribution Rule-Ranking Verification

| Rank | checker_id | risk_tier | planned_n | available_N | cap | capacity | Eligible? | Action |
|------|-----------|-----------|-----------|-------------|-----|----------|-----------|--------|
| 1 | c08_live_file_mismatch | HIGH | 15 | 85 | 15 | 0 | ❌ At cap | skip |
| 2 | FM-MISSINGKEYS | HIGH | 12 | 71 | 15 | 3 | ✅ | **+1** |
| 3 | standard_compliance | HIGH | 8 | 40 | 15 | 7 | ✅ | **+1** |
| 4 | THUMBNAIL-01 | HIGH | 6 | 36 | 15 | 9 | ✅ | **+1** |
| 5 | FM-DRAFT | MEDIUM | 5 | 30 | 15 | 10 | ❌ Quota full | skip |
| 6 | content_quality | MEDIUM | 5 | 23 | 15 | 10 | ❌ Quota full | skip |
| 7 | semantic | MEDIUM | 5 | 22 | 15 | 10 | ❌ Quota full | skip |

**排序 기준**: risk_tier desc (HIGH > MEDIUM > LOW) → planned_n desc → available_N desc
**결과**: +3 = FM-MISSINGKEYS(+1) + standard_compliance(+1) + THUMBNAIL-01(+1) — all HIGH tier
**이전 오류**: FM-DRAFT(+1)은 MEDIUM tier라 HIGH tier 3개가 소진된 후 해당되나, +3 할당이 이미 HIGH tier에서 충족되어 FM-DRAFT는 받지 않음

### 12.9 Field Separation (4 distinct fields)

| Field | Value | Source | Do NOT mix with |
|-------|-------|--------|-----------------|
| `historical_requested_n` | **97** | Sum of V2 Plan allocation matrix planned_n | final_target, actual |
| `census_adjusted_actual` | **87** | Quarantined sample.csv fail row count | final_target, historical |
| `redistribution` | **+3** | FM-MISSINGKEYS+1, standard_compliance+1, THUMBNAIL-01+1 | historical, actual |
| `revised_final_target` | **90** | Corrected matrix sum | historical, actual |

**Cross-check**: 87 (actual) + 3 (redistribution) = 90 (final_target) ✓
**Cross-check**: 97 (historical) − 10 (structural shortfall) = 87 (actual) ✓
**Cross-check**: 81 (non-c06/c01 base) + 3 = 84 (non-c06/c01 final) ✓
**Cross-check**: 84 + 6 (c06+c01) = 90 (total) ✓

---

## 13. Docs-Only Commit Candidate (PENDING)

### 13.1 Files in Commit Candidate

| File | Status | Scope |
|------|--------|-------|
| `docs/SSOT_V2_STAGE2_CORRECTED_ALLOCATION.md` | Modified (this doc) | §14–§18 added |
| `docs/SSOT_V2_ARTIFACT_FORENSIC_CLOSURE.md` | New | Full document |
| `docs/SSOT_V2_PILOT_AUTHORIZATION_PACKET.md` | Modified | §0 status update |
| `docs/DASHBOARD_SSOT_EXPERIMENT_V2_PLAN.md` | Modified | §10A status update |

**Excluded from commit** (per §11 rules):
- checker patches (content_integrity.py, content_quality.py, frontmatter.py, standard.py)
- test files (test_checker_patches_20260820.py)
- ops.db or ops_snapshot.db
- `/tmp/ssot_v2_pilot/` artifacts (LEGACY_QUARANTINED_V1)
- CSV/DB/raw evidence/packets

### 13.2 Non-Circular Hash Bundle Structure

```
CORRECTED_ALLOCATION.md
  ├── SHA-256: <to be computed after final edit>
  ├── references: V2_PLAN.md (line 1184 合計 row)
  ├── references: PILOT_AUTHORIZATION_PACKET.md
  ├── references: ARTIFACT_FORENSIC_CLOSURE.md
  └── quarantined_artifacts (LEGACY_QUARANTINED_V1):
      ├── STAGE0_MANIFEST.json  → e2eb2c62...
      ├── STAGE2_MANIFEST.json  → a4a8a5be... (PROVENANCE_EVENT_2)
      ├── STAGE3_MANIFEST.json  → df742823...
      ├── sample.csv            → b69e29f7...
      ├── sampling_frame.csv    → 1f16e8d2...
      ├── ops_snapshot.db       → 8c4fc4ad...
      └── blind_packets/        → 133 files (directory)
```

**Non-circular**: CORRECTED_ALLOCATION.md references quarantined artifacts by SHA-256 but does not embed their content. Quarantined artifacts do not reference CORRECTED_ALLOCATION.md. No cycle.

### 13.3 Commit Message Candidate

```
docs: SSOT V2 forensic closure + corrected allocation + pilot-v2.2 chain contract

- Forensic investigation: 11 axes, 7 artifacts LEGACY_QUARANTINED_V1
- Corrected allocation: historical=97, census=87, redistribution=+3, target=90
- pilot-v2.2 chain contract: new identifiers, atomic rename, external hash linking
- Canonical serialization: UTF-8, LF, sorted keys, explicit newline
- Status sync: QA Plan + Pilot Packet → LEGACY_RUN_INVALID, FRESH_RERUN_REQUIRED
```

**No code, no resampling, no network fetch, no labeling, no DB changes, no push.**

### 13.4 Commit Verification Checklist

Before committing:
- [ ] All 4 docs have consistent status references
- [ ] No artifact validity claims remain (INDETERMINATE throughout)
- [ ] pilot-v2.2 identifiers do NOT reuse pilot-001 identifiers
- [ ] Forensic closure references are correct
- [ ] No code/DB/CSV/packet files staged

---

## 14. pilot-v2.2 Artifact Chain Contract

**Version**: pilot-v2.2 (no reuse of pilot-001 identifiers)
**Status**: DESIGNED, NOT YET EXECUTED
**Prerequisite**: Fresh snapshot from live ops.db

### 14.1 Identifier Namespace

| Identifier | pilot-001 (LEGACY) | pilot-v2.2 (NEW) |
|------------|--------------------|--------------------|
| run_id | `SSOT_V2_PILOT_2026-08-20` | `SSOT_V2_PILOT_v2.2_<YYYYMMDD>` |
| packet_version | v3.0 | v4.0 |
| output path | `/tmp/ssot_v2_pilot/` | `data/ssot_experiment_v2/pilot_v2.2/` |
| plan hash | 0c2d6fdb (original), 18579234 (reconciled) | Fresh SHA-256 of committed plan doc |
| packet hash | 7a920603 | Fresh SHA-256 of committed packet doc |

**Rule**: pilot-001 identifiers are NEVER reused. pilot-v2.2 generates entirely new identifiers.

### 14.2 Stage 1 Manifest Schema

```json
{
  "manifest_version": "1.0",
  "run_id": "SSOT_V2_PILOT_v2.2_<YYYYMMDD>",
  "stage": 1,
  "created_at": "<ISO 8601 UTC>",
  "plan_commit_sha": "<git SHA of committed plan doc>",
  "packet_commit_sha": "<git SHA of committed packet doc>",
  "source_db_identity": "ops_dashboard/ops.db",
  "source_db_size_bytes": "<int>",
  "source_db_mtime": "<ISO 8601 UTC>",
  "copy_started_at": "<ISO 8601 UTC>",
  "copy_completed_at": "<ISO 8601 UTC>",
  "copy_path": "<absolute path>",
  "copy_sha256": "<SHA-256 of DB copy file>",
  "as_of": "<MAX(checked_at) from copy>",
  "snapshot_fail_count": "<int>",
  "snapshot_pass_count": "<int>",
  "snapshot_eligible_count": "<int>",
  "snapshot_total_count": "<int>",
  "population_query": "<SQL text>",
  "population_query_sha256": "<SHA-256 of canonical query>",
  "schema_version": "check_results v1",
  "row_id_null_count": 0,
  "row_id_duplicate_count": 0
}
```

**Excluded**: Self-hash. The manifest does NOT contain its own SHA-256. Hash is computed externally after atomic rename.

### 14.3 Stage 2 Manifest Schema

```json
{
  "manifest_version": "1.0",
  "run_id": "SSOT_V2_PILOT_v2.2_<YYYYMMDD>",
  "stage": 2,
  "created_at": "<ISO 8601 UTC>",
  "parent_manifest_hash": "<SHA-256 of Stage 1 manifest file>",
  "copy_sha256": "<same as Stage 1 — DB copy unchanged>",
  "sampling_seed": "<int — derived per §14.6>",
  "sampling_frame_row_count": "<int>",
  "sampling_frame_sha256": "<SHA-256 of sampling_frame.csv>",
  "corrected_allocation_sha256": "<SHA-256 of CORRECTED_ALLOCATION.md>",
  "fail_target": 90,
  "fail_actual": "<int>",
  "pass_target": 46,
  "pass_actual": "<int>",
  "sample_row_count": "<int>",
  "sample_sha256": "<SHA-256 of sample.csv>",
  "fail_allocation": {"<check_name>": "<int>", "...": "..."},
  "fail_actual_distribution": {"<check_name>": "<int>", "...": "..."}
}
```

### 14.4 Stage 3 Manifest Schema

```json
{
  "manifest_version": "1.0",
  "run_id": "SSOT_V2_PILOT_v2.2_<YYYYMMDD>",
  "stage": 3,
  "created_at": "<ISO 8601 UTC>",
  "parent_manifest_hash": "<SHA-256 of Stage 2 manifest file>",
  "sample_sha256": "<same as Stage 2 — sample unchanged>",
  "packet_bundle_sha256": "<SHA-256 of canonical packet list (§14.5)>",
  "packet_count": "<int>",
  "fail_packet_count": "<int>",
  "pass_packet_count": "<int>",
  "redaction_report_hash": "<SHA-256 of PII redaction report>",
  "pii_findings_count": "<int>",
  "redacted_count": "<int>"
}
```

### 14.5 Canonical Packet Bundle (blind_packets/ anchoring)

The `packet_bundle_sha256` is computed from a canonical serialization of all packet paths and their individual SHA-256 hashes:

```
canonical_input = sorted list of "<relative_path>  <sha256>\n" lines
packet_bundle_sha256 = SHA-256(canonical_input)
```

This is recorded in Stage 3 manifest and also written to an external `SHA256SUMS` file in the output directory.

### 14.6 Seed Derivation

```python
import hashlib

# Deterministic seed from plan commit + copy hash + allocation
seed_input = f"{plan_commit_sha}||{copy_sha256}||{corrected_allocation_sha256}"
sampling_seed = int(hashlib.sha256(seed_input.encode()).hexdigest()[:8], 16)
```

### 14.7 Hash Linking Chain

```
Plan doc (committed) ──SHA-256──> plan_commit_sha
Packet doc (committed) ──SHA-256──> packet_commit_sha
                                      │
Stage 1 manifest ──parent──> plan_commit_sha + packet_commit_sha
Stage 1 manifest ──copy_sha256──> DB copy file
                                      │
Stage 2 manifest ──parent_manifest_hash──> Stage 1 manifest file
Stage 2 manifest ──sample_sha256──> sample.csv
Stage 2 manifest ──sampling_frame_sha256──> sampling_frame.csv
Stage 2 manifest ──corrected_allocation_sha256──> CORRECTED_ALLOCATION.md
                                      │
Stage 3 manifest ──parent_manifest_hash──> Stage 2 manifest file
Stage 3 manifest ──sample_sha256──> sample.csv (unchanged)
Stage 3 manifest ──packet_bundle_sha256──> canonical packet list
                                      │
SHA256SUMS file ──external──> all manifest file hashes
```

**No manifest contains its own hash.** All hash linking is external (parent → child, or SHA256SUMS file).

---

## 15. Canonical Serialization Rules

All artifacts produced by pilot-v2.2 follow these serialization rules:

### 15.1 Text Files (manifests, CSVs, reports)

| Rule | Value |
|------|-------|
| Encoding | UTF-8 (no BOM) |
| Line endings | LF only (no CRLF) |
| JSON key order | Sorted alphabetically (Python `json.dumps(sort_keys=True)`) |
| CSV column order | Explicit per schema (not alphabetical) |
| Relative paths | Sorted alphabetically (for manifest path lists) |
| Trailing whitespace | None |
| Final newline | Exactly one trailing newline (`\n`) |
| Null values | JSON `null`, CSV empty string |
| Boolean values | JSON `true`/`false` (lowercase) |

### 15.2 Binary Files (DB copies)

| Rule | Value |
|------|-------|
| Hash target | Raw file bytes (no encoding transform) |
| Hash algorithm | SHA-256 |
| Hash format | 64-character lowercase hex |

### 15.3 Manifest Construction

1. Build manifest content in memory
2. Serialize with `json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)`
3. Append exactly one `\n` at end
4. Write to temporary file (`.tmp` suffix)
5. Verify temp file content matches expected JSON
6. Compute SHA-256 of temp file
7. Atomic rename temp → final path
8. Record final file SHA-256 in external SHA256SUMS or next stage's parent_manifest_hash

---

## 16. Atomic Rename + External Hash Linking

### 16.1 Manifest Creation Protocol

```python
import json, hashlib, os, tempfile

def write_manifest(manifest: dict, final_path: str) -> str:
    """Write manifest atomically. Returns SHA-256 of final file."""
    content = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    content_bytes = content.encode("utf-8")
    
    # Step 1: Write to temporary file
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(final_path), suffix=".tmp")
    try:
        os.write(fd, content_bytes)
        os.fsync(fd)
        os.close(fd)
        
        # Step 2: Verify written content
        with open(tmp_path, "rb") as f:
            written = f.read()
        assert written == content_bytes, "Written content mismatch"
        
        # Step 3: Compute hash BEFORE rename
        file_hash = hashlib.sha256(written).hexdigest()
        
        # Step 4: Atomic rename
        os.rename(tmp_path, final_path)
        
        return file_hash
    except Exception:
        os.unlink(tmp_path)
        raise
```

### 16.2 No Self-Hash in Manifest

The manifest JSON does NOT contain a field for its own hash. The hash is:
- Computed after the file is written
- Recorded in the next stage's `parent_manifest_hash` field
- AND/OR recorded in an external `SHA256SUMS` file

### 16.3 SHA256SUMS File Format

```
<hash>  <filename>
<hash>  <filename>
...
```

Written after all manifests for a stage are complete. One SHA256SUMS per stage directory.

---

## 17. Durable Local Path

### 17.1 Output Directory

| Item | Path |
|------|------|
| Base directory | `data/ssot_experiment_v2/` |
| pilot-v2.2 output | `data/ssot_experiment_v2/pilot_v2.2/` |
| DB copy | `data/ssot_experiment_v2/pilot_v2.2/ops_snapshot.db` |
| Manifests | `data/ssot_experiment_v2/pilot_v2.2/STAGE{0,1,2,3}_MANIFEST.json` |
| CSVs | `data/ssot_experiment_v2/pilot_v2.2/*.csv` |
| blind_packets | `data/ssot_experiment_v2/pilot_v2.2/blind_packets/` |
| SHA256SUMS | `data/ssot_experiment_v2/pilot_v2.2/SHA256SUMS` |
| Raw evidence | `data/ssot_experiment_v2/pilot_v2.2/raw_evidence/` |

### 17.2 Git Exclusion Rules

| File | Git-tracked? | Reason |
|------|-------------|--------|
| `*.csv` | No | Data artifacts |
| `*.db` | No | Database copies |
| `blind_packets/` | No | Evidence packets |
| `raw_evidence/` | No | Raw HTTP responses |
| `SHA256SUMS` | No | Ephemeral verification |
| `STAGE*_MANIFEST.json` | No | Execution manifests |
| `docs/*.md` | **Yes** | Design + forensic docs |

**Rationale**: Binary/data artifacts are excluded from git. Only docs/ (design, forensic, allocation) are committed.

---

## 18. Decision State Summary

| Item | Status |
|------|--------|
| Forensic closure | **DOCUMENTED** — `docs/SSOT_V2_ARTIFACT_FORENSIC_CLOSURE.md` |
| Legacy artifacts | **LEGACY_QUARANTINED_V1** — 7 artifacts, no delete/modify/move/copy/reuse |
| Corrected allocation | **FINAL_APPROVED** — design-only, not executed |
| Stage 1 snapshot reuse | **REUSE_REVOKED** — fresh snapshot required |
| pilot-v2.2 chain contract | **DESIGNED** — §14–§17 above |
| Docs-only commit | **PENDING** — 4 docs, no code/DB/CSV |
| Fresh pilot-v2.2 | **NOT YET EXECUTED** — requires separate approval |
| Stage 4–5 | **PAUSED** |
| Final / Paired Regression | **NOT_APPROVED** |
| G5 | **PENDING/BLOCKED** |
