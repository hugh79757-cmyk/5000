# SSOT V2 — Artifact Forensic Closure

> **Date**: 2026-08-20
> **Status**: LEGACY_QUARANTINED_V1 — forensic investigation complete
> **Scope**: READ-ONLY forensic reconciliation of pilot-001 artifacts (Stage 0–3)
> **No artifacts modified, no DB queries, no commits, no network fetches**

---

## 1. Forensic Axes Investigated

Eleven axes were investigated across all existing pilot-001 artifacts. Each axis is classified as [검증됨], [부분검증], or [검증불가].

### ① snapshot_hash Full-Value Search

| Field | Value |
|-------|-------|
| Full SHA-256 | `021a3b4f8fb7bb14b7977c1fb8c662b95277bcbd80278bc33d870397ace26e43` |
| JSON key path | `$.snapshot_hash` in STAGE2_MANIFEST.json |
| Surrounding fields | `population_query_sha256` (44cbda41...) above; `sampling_seed` (3437411979), `fail_target` (90) below |
| Exact search result | Found ONLY in `STAGE2_MANIFEST.json` (self) and `docs/SSOT_V2_STAGE2_CORRECTED_ALLOCATION.md` (report). No other file. |

**Status**: [검증됨] — value located, context confirmed, no external match found.

### ② STAGE0_MANIFEST DB Hash Fields

STAGE0_MANIFEST contains **zero** DB-related hash fields. Only: `dirty_diff_binary_hash` (476dbc32...), `dirty_status_porcelain_hash` (9dd22eff...), `plan_document_hash` (0c2d6fdb...), `packet_hash` (7a920603...). No `ops_snapshot_hash` or `snapshot_hash` exists.

**Status**: [검증됨] — absence confirmed by field enumeration.

### ③ snapshot_hash Target Domain — 10 Reproduction Attempts

| # | Target | Actual SHA-256 | Match `021a3b4f`? |
|---|--------|----------------|---------------------|
| 1 | ops_snapshot.db file bytes | `8c4fc4adeeaa...` | ✗ |
| 2 | sampling_frame.csv | `1f16e8d225cd...` | ✗ |
| 3 | sample.csv | `b69e29f71643...` | ✗ |
| 4 | check_results CSV (ordered by id) | `73a726c17f55...` | ✗ |
| 5 | STAGE0_MANIFEST.json | `e2eb2c621e90...` | ✗ |
| 6 | STAGE3_MANIFEST.json | `df742823...` | ✗ |
| 7 | Sorted filenames (4 methods) | various | ✗ |
| 8 | Python canonical JSON (2 methods) | various | ✗ |

**Verdict**: **UNRESOLVED_HASH_DOMAIN** — target cannot be identified from existing artifacts.

**Status**: [검증불가] — target unreproducible. **복구 계획**: pilot-v2.2에서 explicit canonical serialization spec으로 재설계.

### ④ Recomputability

No. DB file exists → different hash. CSV exists → different hash. No serialization spec exists. Column order, row order, encoding, newline rules unknown. Original serialization lost.

**Status**: [검증불가] — recomputation impossible without serialization spec.

### ⑤ blind_packets Directory Integrity

- **133 files, all present.** Individual SHA-256 computed for each.
- `blind_packet_manifest_hash` = `21feb11203306c5a522e137b57d0e4429664f7da7c16fe778e514fbe01617457`
- Only in STAGE3_MANIFEST.json (self-reference). Not in any other file.
- **9 reproduction attempts (all failed):** sorted filenames, hash+filename pairs, concatenated contents, JSON arrays, various separators — none match.

**Classification**: **DIRECTORY_INTEGRITY_UNANCHORED** — files exist with verified hashes, but manifest anchoring is self-referential, not externally verifiable.

**Status**: [부분검증] — individual file hashes verified, but manifest anchoring method unknown.

### ⑥ STAGE3_MANIFEST Field-by-Field

| Field | Value | External Target | Match? |
|-------|-------|-----------------|--------|
| `total_packets` | 133 | blind_packets/ file count | ✅ |
| `fail_packets` | 87 | sample.csv fail rows | ✅ |
| `pass_packets` | 46 | sample.csv pass rows | ✅ |
| `blind_packet_manifest_hash` | 21feb112... | No external target found | **UNANCHORED** |
| `pii_findings_count` | 0 | No external verification | UNVERIFIABLE |
| `redacted_count` | 0 | No external verification | UNVERIFIABLE |

**Critical**: STAGE3_MANIFEST has NO `sample_hash` field — sample→packet linkage is only implied by matching row counts, not cryptographic hash.

**Status**: [부분검증] — count fields match, hash fields unanchored.

### ⑦ Manifest Immutability

STAGE2_MANIFEST modified within 74 seconds of creation (created 12:01:02 UTC, modified 12:02:16 UTC). Two hashes preserved as provenance events (neither canonical). Matching child hashes (`sample_hash`, `sampling_frame_hash`) do NOT restore immutability.

**Classification**: **MANIFEST_MODIFICATION_UNDETERMINED** — cause unknown, old content unavailable.

**Status**: [검증불가] — modification cause undetermined. **복구 계획**: pilot-v2.2에서 atomic rename + no-self-hash 규칙 적용.

### ⑧ Full Hash-Domain Comparison Table

| Artifact | Claimed Hash | Actual Hash | Status |
|----------|-------------|-------------|--------|
| sample.csv | b69e29f7... | b69e29f7... | ✅ MATCH |
| sampling_frame.csv | 1f16e8d2... | 1f16e8d2... | ✅ MATCH |
| ops_snapshot.db | 021a3b4f... (snapshot_hash) | 8c4fc4ad... (file) | ⚠️ UNRESOLVED |
| population_query | 44cbda41... | N/A (no file) | UNREPRODUCIBLE |
| blind_packets/ | 21feb112... | no anchoring file | ⚠️ UNANCHORED |
| STAGE0_MANIFEST | e2eb2c62... | e2eb2c62... | ✅ MATCH |
| STAGE2_MANIFEST | a4a8a5be... | a4a8a5be... | ✅ MATCH |
| STAGE3_MANIFEST | df742823... | df742823... | ✅ MATCH |

**Status**: [부분검증] — 5/8 match, 1 unresolved, 1 unanchored, 1 unreproducible.

### ⑨ STAGE2_MANIFEST Provenance Events

| Event | Hash | Source |
|-------|------|--------|
| PROVENANCE_EVENT_1 | `291b485b...` | Earlier session tool output (`tool_01f185bc8001xHaLqx3ip8S4Dp`) |
| PROVENANCE_EVENT_2 | `a4a8a5be3e59c0ec17cb48c556d80e933a4f195e5c6f2c8d8e18808fb9a9d6c1` | Current disk SHA-256 |

**Neither hash is designated canonical.** Both preserved as provenance events. File metadata: 3,257 bytes, created 12:01:02 UTC, modified 12:02:16 UTC, owner twinssn (uid 501), `com.apple.provenance` xattr present but empty.

**Change cause investigation**: Shell history — no entries. Execution logs — no `.log` files. Editor temp files — none. Scripts in pilot dir — 20 scripts, none reference STAGE2_MANIFEST. 5000 project scripts — none reference it. Git reflog — no commits (all untracked).

**Conclusion**: UNDETERMINED. Most likely: manifest generation wrote initial version at 12:01:02, then updated at 12:02:16 (possibly to add `sample_hash` after verifying sample.csv). No persistent script or log records this write.

**Status**: [검증불가] — cause undetermined, old content unavailable.

### ⑩ Stage 1 Snapshot Reuse Assessment

Previous classification: REUSE_APPROVED (based on semantic diff showing no population query / DB copy / snapshot schema changes).

**After forensic investigation**: REUSE_REVOKED. The `snapshot_hash` (021a3b4f...) in STAGE2_MANIFEST does not match the `ops_snapshot.db` file hash (8c4fc4ad...). The target of `snapshot_hash` cannot be identified. This means the hash chain from snapshot → sampling_frame → sample → blind_packets is anchored to an unresolvable hash. Stage 1 artifacts may be physically valid but their cryptographic linkage to Stage 2 is broken.

**Status**: [부분검증] — physical data appears valid (row counts match), but hash linkage broken.

### ⑪ Legal Status of All Artifacts

All 7 artifacts in `/tmp/ssot_v2_pilot/` are designated **LEGACY_QUARANTINED_V1**:

| # | Artifact | Designation |
|---|----------|-------------|
| 1 | STAGE0_MANIFEST.json | LEGACY_QUARANTINED_V1 |
| 2 | STAGE2_MANIFEST.json | LEGACY_QUARANTINED_V1 |
| 3 | STAGE3_MANIFEST.json | LEGACY_QUARANTINED_V1 |
| 4 | sample.csv | LEGACY_QUARANTINED_V1 |
| 5 | sampling_frame.csv | LEGACY_QUARANTINED_V1 |
| 6 | ops_snapshot.db | LEGACY_QUARANTINED_V1 |
| 7 | blind_packets/ (133 files) | LEGACY_QUARANTINED_V1 |

**Quarantine rules (absolute):**
- Do NOT delete, modify, move, copy, or reuse any quarantined artifact
- Do NOT use quarantined artifacts for pilot-v2.2 labeling
- New execution must use a separate versioned output path
- These artifacts serve as forensic reference only

---

## 2. Composite Integrity Assessment

| Axis | Status | Reason |
|------|--------|--------|
| Artifact integrity | **INDETERMINATE** | STAGE2_MANIFEST hash changed during session; cause undetermined |
| Sampling execution integrity | **INDETERMINATE** | Manifest modification raises questions about sampling process provenance |
| Approved-design conformity | **INVALID** | Executed allocation sum=97 ≠ approved target=90 |
| Hash chain linkage | **BROKEN** | snapshot_hash (021a3b4f...) unresolved; blind_packet_manifest_hash unanchored |
| Stage 1 snapshot reuse | **REUSE_REVOKED** | Hash linkage from snapshot → sampling_frame broken |

---

## 3. Disposition

| Item | Disposition |
|------|-------------|
| Stage 1 snapshot reuse | **REUSE_SUSPENDED** — fresh snapshot required for pilot-v2.2 |
| Artifact integrity | **INDETERMINATE** — cannot be restored |
| Sampling execution integrity | **INDETERMINATE** — cannot be restored |
| Approved-design conformity | **INVALID** — corrected allocation exists but artifacts don't match |
| Stage 2–3 | **QUARANTINED_ARTIFACT** — preserved, not used |
| Corrected allocation design | **FINAL_APPROVED** — independent of artifact validity |
| G5 | **PENDING/BLOCKED** — fresh run required |

---

## 4. Corrected Allocation (Independent of Artifact Validity)

The corrected allocation matrix (documented in `docs/SSOT_V2_STAGE2_CORRECTED_ALLOCATION.md`) is mathematically valid and independently approved:

| Field | Value |
|-------|-------|
| Historical requested_n | 97 |
| Census-adjusted actual | 87 |
| Redistribution | +3 (FM-MISSINGKEYS +1, standard_compliance +1, THUMBNAIL-01 +1) |
| Revised final_target | 90 |

This allocation is **design-only** — it has not been executed against any artifact. It will serve as the allocation specification for pilot-v2.2.

---

## 5. pilot-v2.2 Fresh Run Prerequisites

A fresh pilot-v2.2 run requires:

1. New snapshot from live ops.db (no reuse of LEGACY_QUARANTINED artifacts)
2. New artifact chain contract (see `docs/SSOT_V2_STAGE2_CORRECTED_ALLOCATION.md` §14)
3. New identifiers (pilot-v2.2, no reuse of pilot-001 identifiers)
4. Canonical serialization spec (UTF-8, LF, sorted keys, explicit newline)
5. Atomic rename manifest creation (no self-hash, external linking only)
6. Durable local path (not `/tmp`, not git-tracked)

---

## 6. Files Modified by This Closure

**No files modified.** This is a forensic investigation report. All findings are recorded in this document only.

**Referenced artifacts** (quarantined, read-only):
- `/tmp/ssot_v2_pilot/` — 7 artifacts, LEGACY_QUARANTINED_V1

**Referenced docs** (read-only during investigation):
- `docs/DASHBOARD_SSOT_EXPERIMENT_V2_PLAN.md` — 1314 lines
- `docs/SSOT_V2_PILOT_AUTHORIZATION_PACKET.md` — 467 lines
- `docs/SSOT_V2_STAGE2_CORRECTED_ALLOCATION.md` — 368 lines

---

## 7. Residual Risks

| Risk | Status | Mitigation |
|------|--------|------------|
| snapshot_hash target unknown | UNRESOLVED | pilot-v2.2 explicit serialization spec |
| blind_packet_manifest_hash unanchored | UNRESOLVED | pilot-v2.2 external SHA256SUMS file |
| STAGE2_MANIFEST modification cause unknown | UNRESOLVED | pilot-v2.2 atomic rename, no self-hash |
| LEGACY artifacts on volatile /tmp | RISK | Forensic hashes preserved in this doc |
| Corrected allocation not yet executed | PENDING | pilot-v2.2 fresh run |

---

## 8. Decision State

| Item | Status |
|------|--------|
| Forensic closure | **DOCUMENTED** |
| Legacy artifacts | **LEGACY_QUARANTINED_V1** |
| Corrected allocation | **FINAL_APPROVED** (design-only) |
| Stage 1 snapshot reuse | **REUSE_REVOKED** |
| Fresh pilot-v2.2 | **DESIGNED, NOT YET EXECUTED** |
| Docs-only commit | **PENDING** — this doc + updates to other docs |
| Code/DB/sampling/network | **NOT TOUCHED** |
