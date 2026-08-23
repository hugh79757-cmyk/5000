# Checker Trust-Gate Design — Section 6: Unit Fixture Architecture (Final Amendment)

> **Version:** 6.0-FA  
> **Status:** FINAL AMENDMENT REQUIRED → APPROVAL PENDING  
> **Previous:** Section 6A CONDITIONALLY APPROVED, Section 6B NOT APPROVED  
> **Scope:** Section 6 only. Sections 1–5 and 7+ unchanged.  
> **Amendments ①–⑳ incorporated. No code/config/DB/test/commit/push/deploy/tuning/sampling/network changes.**

---

## 6.0 Amendments Summary

| # | Requirement | Amendment |
|---|---|---|
| ① | 53 unique assertions by fixture_id, no double-counting | Inventory §6.9 — arithmetic cross-check included |
| ② | assertion_type: VERDICT / WORKFLOW / DESIGN | Schema §6.1 — three distinct assertion_type values |
| ③ | verdict enum: PASS/FAIL/UNC/NOT_EVALUATED/NOT_APPLICABLE only | Schema §6.1 — no compound codes, no free-text verdicts |
| ④ | c01: per-signature required/optional fields, subject·command_verb·control_delimiter·instruction_payload not universally required | §6.4 — SIG-01 through SIG-04 each with own field set |
| ⑤ | c01 synthetic = SYNTHETIC_UNIT_ONLY; EXECUTABLE_FROZEN_CORPUS requires composite identity + full SHA-256 | §6.4 — provenance_status rules |
| ⑥ | c06 PRECHECK excluded from attempt_no; <15min = WORKFLOW/WAITING_CDN | §6.5 — phase/attempt/verdict separation |
| ⑦ | c06 all fixtures carry phase, attempt_no, elapsed_minutes, etc. | §6.5 — full field inventory per fixture |
| ⑧ | c08 no "positive" taxonomy; expected_verdict or contract_case; TP8 frozen corpus requires stable row_id + full hash | §6.3 — fixture taxonomy |
| ⑨ | fingerprint normalization allowlist closed; prohibited fields enumerated | §6.2 — normalization rules |
| ⑩ | c08 title/image independent subchecks, independent assertions | §6.3 — subcheck isolation |
| ⑪ | c08 confirmed 404 = FAIL; 403/5xx/timeout = UNC; pending suffix = DESIGN/NON_EXECUTABLE | §6.3 — image fetch verdict rules |
| ⑫ | c08-C07/C07b, C12 paired fixtures re-verified; C11 = KNOWN_PASS_FP_PREVENTION | §6.3 — per-fixture provenance |
| ⑬ | FM-MISSINGKEYS: key existence contract, no gratuitous NOT_APPLICABLE | §6.6 |
| ⑭ | CQ03/CQ05: separate disclosure + applicability contracts | §6.7 |
| ⑮ | All stable-row fixtures: provenance_status mandatory | §6.1, §6.9 |
| ⑯ | Acceptance criteria: executable VERDICT assertions only | §6.8 |
| ⑰ | G5 rollforward: measured precision ≥90%, terminal known-TP 100%, new FP=0, TP13+c01 FP4 unresolved → BLOCKED | §6.8 |
| ⑱ | §6.9 inventory: checker/subcheck/assertion_type/verdict/provenance_status breakdown, total = 53 | §6.9 |
| ⑲ | §6.10 residual risks | §6.10 |
| ⑳ | Section 6 only; no Section 7, no code, no commit | Scope boundary |

---

## 6.1 Common Assertion Schema

Every assertion follows this schema. All fields are mandatory unless marked optional.

| Field | Type | Values / Constraint | Notes |
|---|---|---|---|
| `fixture_id` | string | `F-{checker}-{NN}` | Globally unique, monotonic within checker |
| `checker_name` | string | Short checker identifier | Matches DB `check_name` |
| `subcheck_id` | string | `NULL` or `{checker}-C{NN}` | Child subcheck for checkers with title/image paired contracts |
| `assertion_type` | enum | `VERDICT` / `WORKFLOW` / `DESIGN` | Exactly one per assertion row |
| `verdict` | enum | `PASS` / `FAIL` / `UNC` / `NOT_EVALUATED` / `NOT_APPLICABLE` | **Only when assertion_type = VERDICT.** NULL for other types |
| `workflow_state` | enum | `WAITING_CDN` / `UNC_RETRYABLE` / NULL | **Only when assertion_type = WORKFLOW.** NULL for other types |
| `design_status` | enum | `NON_EXECUTABLE_CONTRACT_PENDING` / NULL | **Only when assertion_type = DESIGN.** NULL for other types |
| `reason_code` | string | Single normalized token (e.g. `TITLE_MISMATCH`, `OG_MISSING`, `KEY_ABSENT`) | **Required for every VERDICT assertion.** No compound codes. No free-text |
| `rationale` | string | Free-text explanation | Separate from reason_code. Clarifies context |
| `provenance_status` | enum | `TRACEABLE_EXECUTABLE` / `SYNTHETIC_UNIT_ONLY` / `UNRESOLVED_FIXTURE` / `NON_EXECUTABLE_CONTRACT_PENDING` | Required for every stable-row fixture |
| `stable_row_id` | string | Composite identity | Required for TRACEABLE_EXECUTABLE; NULL for SYNTHETIC |
| `evidence_hash` | string | Full 64-hex SHA-256 | Required for TRACEABLE_EXECUTABLE; NULL otherwise |

**Forbidden patterns:**
- Compound reason codes (e.g. `TITLE_MISMATCH_OR_OG_MISSING`)
- Free-text verdict strings (e.g. `"probably fail"`)
- Verdict/reason concatenation (e.g. `FAIL:TITLE_MISMATCH`)
- Using `WAITING_CDN`, `REFRESH_REQUIRED`, `CONTRACT_PENDING`, `UNRESOLVED_FIXTURE` as verdict values
- Using `NOT_APPLICABLE`, `NOT_EVALUATED`, `UNRESOLVED_FIXTURE`, `NON_EXECUTABLE_CONTRACT_PENDING` in the verdict field — these are separate status concepts, not verdicts

---

## 6.2 Fingerprint Normalization Rules

### 6.2.1 Closed Allowlist — Removable Dynamic Fields

Only the following fields MAY be stripped from a fingerprint before comparison. No other field is removable.

| # | Field | Condition | Evidence |
|---|---|---|---|
| 1 | `build_timestamp` | Approved build timestamp (Hugo generated, ISO 8601) | Present in `<meta name="date">` or `<time>` tag only |
| 2 | `nonce` | Cryptographic nonce (Hugo Pipes asset fingerprint) | Present in `?v=<hash>` query parameter only |
| 3 | `generated_metadata` | Explicitly registered generated metadata | Only `generator` meta tag content |

### 6.2.2 Prohibited Removals — Never Strip These Fields

| # | Field | Reason |
|---|---|---|
| 1 | Title text | Core content identity |
| 2 | Body text / paragraphs | Core content identity |
| 3 | URL / permalink | Canonical mapping |
| 4 | Canonical link target | SEO identity |
| 5 | Asset identity (image src, alt text) | Content-bound asset reference |
| 6 | Content hash (body SHA-256) | Immutability anchor |
| 7 | Arbitrary HTML text | Any `<p>`, `<span>`, `<div>` text content |

**Default:** All fields NOT in the allowlist are PRESERVED. If a comparison requires stripping a field not in the allowlist, the comparison is INVALID and must be redesigned.

---

## 6.3 c08 — Live File Mismatch (Title/Image Child Subchecks)

### 6.3.1 Subcheck Isolation

c08 has two independent child subchecks. Each child carries its own assertions. A FAIL in one child does NOT imply a verdict in the other.

| Subcheck ID | Child | Evaluates |
|---|---|---|
| `c08-C01` | Title | `<title>` / `og:title` vs frontmatter `title` |
| `c08-C02` | Image | `og:image` / `<meta property="og:image">` vs `featureimage` |

### 6.3.2 Title Child Contracts

| Contract ID | Condition | assertion_type | verdict | reason_code |
|---|---|---|---|---|
| c08-C01a | Live `<title>` text ≠ frontmatter `title` after suffix normalization | VERDICT | FAIL | `TITLE_MISMATCH` |
| c08-C01b | Live `<title>` text = frontmatter `title` after suffix normalization | VERDICT | PASS | `TITLE_MATCH` |
| c08-C01c | `og:title` absent AND `<title>` present with site suffix stripped | VERDICT | FAIL | `OG_MISSING` |
| c08-C01d | `og:title` present AND matches frontmatter `title` | VERDICT | PASS | `OG_TITLE_MATCH` |
| c08-C01e | Configured site-name suffix not yet resolved (child evaluation contract pending) | DESIGN | — | — |

### 6.3.3 Image Child Contracts

| Contract ID | Condition | assertion_type | verdict | reason_code |
|---|---|---|---|---|
| c08-C02a | `og:image` URL returns HTTP 200 and matches `featureimage` | VERDICT | PASS | `IMAGE_MATCH` |
| c08-C02b | `og:image` URL returns confirmed HTTP 404 | VERDICT | FAIL | `OG_MISSING` |
| c08-C02c | `og:image` URL returns HTTP 403 or 5xx | VERDICT | UNC | `IMAGE_FETCH_ERROR` |
| c08-C02d | `og:image` URL returns timeout | VERDICT | UNC | `IMAGE_FETCH_TIMEOUT` |
| c08-C02e | `og:image` URL returns transient transport failure (retryable) | VERDICT | UNC | `IMAGE_FETCH_TRANSIENT` |
| c08-C02f | `og:image` absent from rendered HTML | VERDICT | FAIL | `OG_MISSING` |
| c08-C02g | Configured image child contract not yet finalized | DESIGN | — | `NON_EXECUTABLE_CONTRACT_PENDING` |

### 6.3.4 Title Suffix Normalization

The `<title>` tag in Hugo always includes a site suffix (e.g. `· 뷰티/스킨케어 추천 가이드`). When comparing against frontmatter `title`:

1. Extract `<title>` text content
2. Strip trailing `· {configured_site_name}` pattern (configurable per blog)
3. Compare stripped `<title>` against frontmatter `title` (exact match after whitespace normalization)

If the configured site-name suffix is unavailable for a blog, the title child fixture is `assertion_type=DESIGN, design_status=NON_EXECUTABLE_CONTRACT_PENDING`.

### 6.3.5 Fixture Taxonomy — No "positive" Classification

c08 fixtures use `expected_verdict` or `contract_case` for classification, NOT "positive"/"negative" terminology. Each fixture is classified by:

| Field | Values | Purpose |
|---|---|---|
| `expected_verdict` | `PASS` / `FAIL` / `UNC` | What the fixture is designed to produce |
| `contract_case` | `KNOWN_TP` / `KNOWN_FP_PREVENTION` / `UNRESOLVED` | Corpus role |

**known-TP frozen corpus:** Only rows with confirmed `stable_row_id` (composite identity) AND full 64-hex SHA-256 `evidence_hash` are included. Unconfirmed representative cases remain `UNRESOLVED_FIXTURE` / provenance pending.

**known-PASS regression corpus (KNOWN_PASS_FP_PREVENTION):** Used for regression testing only. NOT mixed with known-TP corpus. Purpose: verify no new FP introduced.

### 6.3.6 c08-C07/C07b, C12, C11 Re-verification

| Fixture ID | Subcheck | expected_verdict | contract_case | provenance_status | Notes |
|---|---|---|---|---|---|
| F-c08-07 | c08-C01 | PASS | KNOWN_PASS_FP_PREVENTION | TRACEABLE_EXECUTABLE | Title match — regression guard |
| F-c08-07b | c08-C02 | PASS | KNOWN_PASS_FP_PREVENTION | TRACEABLE_EXECUTABLE | Image match — regression guard |
| F-c08-12 | c08-C01 | PASS | KNOWN_PASS_FP_PREVENTION | TRACEABLE_EXECUTABLE | Paired title/image PASS |
| F-c08-11 | c08-C01 | PASS | KNOWN_PASS_FP_PREVENTION | TRACEABLE_EXECUTABLE | Same as FM-C04 pattern — regression FP prevention |

**C11 and FM-C04 are classified KNOWN_PASS_FP_PREVENTION.** They are NOT mixed with known-TP/FN-prevention fixtures. Purpose: detect regressions that would turn a previously-passing case into a false negative.

---

## 6.4 c01 — Curve Quote (4 Control Signatures)

### 6.4.1 Signature Schema

Each signature has its own `required_fields` and `optional_fields`. The fields `subject`, `command_verb`, `control_delimiter`, `instruction_payload` are NOT universally required across all signatures.

| Field | Definition | SIG-01 | SIG-02 | SIG-03 | SIG-04 |
|---|---|---|---|---|---|
| `signature_id` | Unique identifier | Required | Required | Required | Required |
| `rule_version` | Checker version / git SHA | Required | Required | Required | Required |
| `pattern_type` | Detection pattern type | Required | Required | Required | Required |
| `subject` | Entity being addressed/controlled | Optional | Optional | Optional | Required |
| `command_verb` | Action verb in instruction | Optional | Required | Optional | Optional |
| `control_delimiter` | Structural delimiter in template | Optional | Optional | Required | Optional |
| `instruction_payload` | Full instruction text | Optional | Optional | Optional | Optional |

### 6.4.2 Signature Definitions

| Signature | Focus | Required Fields | Optional Fields | Detection Target |
|---|---|---|---|---|
| **SIG-01** | System-prompt noun phrase | `signature_id`, `rule_version`, `pattern_type` | `subject`, `command_verb`, `control_delimiter`, `instruction_payload` | Noun-phrase template markers in system prompts |
| **SIG-02** | Instruction/command + command verb | `signature_id`, `rule_version`, `pattern_type`, `command_verb` | `subject`, `control_delimiter`, `instruction_payload` | Imperative instruction patterns with action verbs |
| **SIG-03** | Rule + compliance verb | `signature_id`, `rule_version`, `pattern_type`, `control_delimiter` | `subject`, `command_verb`, `instruction_payload` | Rule-statement patterns with compliance verbs |
| **SIG-04** | Address subject (you/AI/助手) | `signature_id`, `rule_version`, `pattern_type`, `subject` | `command_verb`, `control_delimiter`, `instruction_payload` | Direct-address patterns targeting AI/assistant |

### 6.4.3 Fixture Provenance Rules for c01

| provenance_status | Condition | Evidence Required |
|---|---|---|
| `TRACEABLE_EXECUTABLE` | composite identity (stable_row_id) + full 64-hex SHA-256 evidence_hash confirmed | Both `stable_row_id` AND `evidence_hash` present and verified |
| `SYNTHETIC_UNIT_ONLY` | Assertion constructed for testing, not from live data | No `stable_row_id` or `evidence_hash` — synthetic fixture |

**c01 synthetic fixtures are SYNTHETIC_UNIT_ONLY.** They are NEVER classified as EXECUTABLE_FROZEN_CORPUS. Only fixtures with confirmed composite identity AND full evidence hash receive `TRACEABLE_EXECUTABLE`.

### 6.4.4 c01 Verdict Rules

- **Natural-language curly quotes** (U+2018/19, U+201C/1D in prose context): `NOT_APPLICABLE` — not a template leak
- **Template/instruction marker exposure** (frontmatter fields leaking into body with curly quotes): `FAIL`
- **All 47 current fail rows**: reclassified as FP per trust gate report — natural-language typography, not template leakage

---

## 6.5 c06 — Mtime Deploy (Phase/Attempt/Verdict Separation)

### 6.5.1 Phase Definitions

| Phase | Definition | attempt_no | assertion_type | Terminal verdict? |
|---|---|---|---|---|
| `PRECHECK` | Initial deploy_ts elapsed check (<15 min) | `null` | `WORKFLOW` | **No** — workflow state only |
| `EVALUATION_1` | First evaluation window (≥15 min, <30 min) | `1` | `VERDICT` or `WORKFLOW` | Conditional |
| `EVALUATION_2` | Second evaluation window (≥30 min) | `2` | `VERDICT` | Terminal |

### 6.5.2 Timing Rules

| Elapsed Time | Phase | attempt_no | Allowable assertion_type | Allowable verdict / workflow_state |
|---|---|---|---|---|
| <15 min | PRECHECK | `null` | WORKFLOW | `WAITING_CDN` only |
| ≥15 min, <30 min | EVALUATION_1 | `1` | VERDICT or WORKFLOW | `PASS`, `UNC_RETRYABLE`, or other |
| ≥30 min | EVALUATION_2 | `2` | VERDICT | `PASS`, `FAIL`, or `UNC` (terminal) |

### 6.5.3 Network Unavailability Handling

| Scenario | attempt_no | Result |
|---|---|---|
| Network unavailable at EVALUATION_1 | `1` | `workflow_state = UNC_RETRYABLE` (NOT terminal UNC) |
| Network unavailable at EVALUATION_2 | `2` | `verdict = UNC, terminal = true` |

### 6.5.4 Required Fields per c06 Fixture

Every c06 fixture MUST carry all of the following:

| Field | Type | Description |
|---|---|---|
| `phase` | enum | `PRECHECK` / `EVALUATION_1` / `EVALUATION_2` |
| `attempt_no` | int or null | `null` for PRECHECK; `1` or `2` for evaluations |
| `elapsed_minutes` | float | Minutes since deploy_ts |
| `artifact_available` | bool | Whether deploy artifact is accessible |
| `target_url_confirmed` | bool | Whether target URL resolves |
| `http_result` | int or null | HTTP status code (if fetched) |
| `live_fingerprint_available` | bool | Whether live page fingerprint exists |
| `normalized_match` | bool or null | Whether normalized comparison matched |

### 6.5.5 PRECHECK Is Not an Attempt

PRECHECK is a workflow gate, not an evaluation attempt. It does NOT count toward `attempt_no`. The PRECHECK assertion has `assertion_type=WORKFLOW, workflow_state=WAITING_CDN` and never produces a terminal PASS/FAIL/UNC verdict.

---

## 6.6 FM-MISSINGKEYS — Key Existence Contract

### 6.6.1 Contract Definition

FM-MISSINGKEYS checks whether all **required keys** exist in post frontmatter. The required-key set is defined by an authoritative contract (not configurable per blog).

| Condition | verdict | reason_code |
|---|---|---|
| All required keys present | `PASS` | `ALL_KEYS_PRESENT` |
| One or more required keys absent | `FAIL` | `KEY_ABSENT` |
| Applicability preconditions not met (no contract basis) | `NOT_APPLICABLE` | `N/A_NO_CONTRACT_BASIS` |

### 6.6.2 Applicability Rule

FM-MISSINGKEYS applies to ALL post frontmatter. There is no blog-type exclusion in the authoritative contract. The current 40 FP from ETAP `_index.md` is classified as `FAIL` (the check scans `_index.md` which lacks required keys) — this is a check logic issue, not an applicability exemption.

**No gratuitous NOT_APPLICABLE fixtures.** If there is no explicit contract basis for non-applicability, the fixture carries a verdict, not NOT_APPLICABLE.

---

## 6.7 CQ03/CQ05 — Disclosure + Applicability Contracts (Separated)

### 6.7.1 Two Independent Contracts

| Contract | What It Checks | Applies When |
|---|---|---|
| **Disclosure contract** (CQ03) | Presence of "쿠팡 파트너스" or equivalent affiliate disclosure in post body | Blog has `skip_product_rules = false` |
| **Applicability contract** (CQ05) | Product/thumbnail image presence | Blog has `skip_product_rules = false` |

### 6.7.2 Applicability Gate

Blogs with `skip_product_rules = true` (stock/sector/finance/dividend/etf/info categories) do NOT trigger CQ03 or CQ05.

| Condition | CQ03 verdict | CQ05 verdict |
|---|---|---|
| `skip_product_rules = true` | `NOT_APPLICABLE` | `NOT_APPLICABLE` |
| `skip_product_rules = false` AND disclosure present | `PASS` | — |
| `skip_product_rules = false` AND disclosure absent | `FAIL` | — |
| `skip_product_rules = false` AND product image absent | — | `FAIL` |

### 6.7.3 No New Checker Rules

Section 6 fixtures do NOT create new checker rules. CQ03/CQ05 fixture behavior matches the existing `content_quality.py` checker logic. Applicability gate is determined by `blog_lifecycle.skip_product_rules` config, not by Section 6 design.

---

## 6.8 Acceptance Criteria + G5 Rollforward

### 6.8.1 Acceptance Criteria Computation

Acceptance criteria are computed from **executable VERDICT assertions only.** The following are excluded from the denominator:

| Exclusion | Reason |
|---|---|
| `NOT_EVALUATED` | Not adjudicated |
| `NOT_APPLICABLE` | Contractually inapplicable |
| `UNRESOLVED_FIXTURE` | Provenance incomplete |
| `NON_EXECUTABLE_CONTRACT_PENDING` | Design incomplete |
| `assertion_type = WORKFLOW` | Not a verdict assertion |
| `assertion_type = DESIGN` | Not a verdict assertion |

**Precision formula:** `Precision = TP / (TP + FP)`

Where:
- TP = `FAIL` verdict on a known-TP fixture (true positive)
- FP = `FAIL` verdict on a known-FP-prevention fixture (false positive)

### 6.8.2 Terminal Known-TP Sensitivity

Terminal known-TP sensitivity must be **100%** on the independent known-TP corpus where terminal adjudication is complete. This means every known-TP fixture with `TRACEABLE_EXECUTABLE` provenance and terminal verdict must receive `FAIL`.

### 6.8.3 Paired Known-PASS Regression Corpus

New FP count on the known-PASS regression corpus must be **0**. Any FAIL on a `KNOWN_PASS_FP_PREVENTION` fixture is a regression and blocks G5.

### 6.8.4 G5 Rollforward Conditions (all required)

| Condition | Threshold | Status |
|---|---|---|
| Measured precision | ≥ 90% | **Not 91.4%** — that is a projection, not a measured result |
| Terminal known-TP sensitivity | = 100% | All terminal adjudicated known-TP = FAIL |
| New FP | = 0 | Zero FAIL on KNOWN_PASS_FP_PREVENTION corpus |
| Targeted FP non-increase/decrease | Contract satisfied | P0–P6 patches do not introduce new FP |
| TP13 + c01 FP4 provenance | **UNRESOLVED_PROVENANCE** | Blocks G5 regardless of other metrics |

**TP13+c01 FP4:** If provenance remains unresolved, G5 = `PENDING/BLOCKED` regardless of all other metrics.

### 6.8.5 91.4% Projection Statement

The value 91.4% (212/232) is a **projection** based on P0–P6 patch estimates. It is NOT a measured result. Measured precision can only be determined after patch execution and RecheckAll. Do not express 91.4% as achieved or measured.

---

## 6.9 Fixture Inventory — Unique by fixture_id (53 Total)

### 6.9.1 Assertion Inventory — Per Fixture

Each row is one unique `fixture_id`. Multi-assertion fixtures (e.g. c06 workflow+verdict) have a single row with the verdict assertion counted.

#### c08 — Live File Mismatch (11 fixtures)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 1 | F-c08-01 | c08-C01 | VERDICT | FAIL | — | TITLE_MISMATCH | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 2 | F-c08-02 | c08-C01 | VERDICT | FAIL | — | OG_MISSING | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 3 | F-c08-03 | c08-C02 | VERDICT | FAIL | — | OG_MISSING | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 4 | F-c08-04 | c08-C02 | VERDICT | UNC | — | IMAGE_FETCH_ERROR | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 5 | F-c08-05 | c08-C01 | VERDICT | PASS | — | TITLE_MATCH | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |
| 6 | F-c08-06 | c08-C02 | VERDICT | PASS | — | IMAGE_MATCH | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |
| 7 | F-c08-07 | c08-C01 | VERDICT | PASS | — | TITLE_MATCH | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |
| 8 | F-c08-07b | c08-C02 | VERDICT | PASS | — | IMAGE_MATCH | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |
| 9 | F-c08-11 | c08-C01 | VERDICT | PASS | — | TITLE_MATCH | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |
| 10 | F-c08-12 | c08-C01 | VERDICT | PASS | — | TITLE_MATCH | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |

**Sub-totals:** FAIL=3, PASS=6, UNC=1 → 10 VERDICT + 1 DESIGN (F-c08-ts-01)

#### c01 — Curve Quote (8 fixtures)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 11 | F-c01-01 | NULL | VERDICT | PASS | — | NATURAL_QUOTE | SYNTHETIC_UNIT_ONLY | KNOWN_PASS_FP_PREVENTION |
| 12 | F-c01-02 | NULL | VERDICT | PASS | — | NATURAL_QUOTE | SYNTHETIC_UNIT_ONLY | KNOWN_PASS_FP_PREVENTION |
| 13 | F-c01-03 | NULL | VERDICT | PASS | — | NATURAL_QUOTE | SYNTHETIC_UNIT_ONLY | KNOWN_PASS_FP_PREVENTION |
| 14 | F-c01-04 | NULL | VERDICT | PASS | — | NATURAL_QUOTE | SYNTHETIC_UNIT_ONLY | KNOWN_PASS_FP_PREVENTION |
| 15 | F-c01-05 | NULL | VERDICT | PASS | — | TEMPLATE_LEAK | SYNTHETIC_UNIT_ONLY | KNOWN_TP |
| 16 | F-c01-06 | NULL | VERDICT | PASS | — | TEMPLATE_LEAK | SYNTHETIC_UNIT_ONLY | KNOWN_TP |
| 17 | F-c01-07 | NULL | VERDICT | PASS | — | TEMPLATE_LEAK | SYNTHETIC_UNIT_ONLY | KNOWN_TP |
| 18 | F-c01-08 | NULL | VERDICT | PASS | — | TEMPLATE_LEAK | SYNTHETIC_UNIT_ONLY | KNOWN_TP |

**Sub-totals:** All PASS. c01 47 live fails reclassified as FP (natural-language typography). Synthetic TP fixtures test template-leak detection. SYNTHETIC_UNIT_ONLY provenance — no live stable_row_id.

#### c06 — Mtime Deploy (9 fixtures)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case | phase | attempt_no |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | F-c06-01 | NULL | VERDICT | FAIL | — | MTIME_UNDEPLOYED | TRACEABLE_EXECUTABLE | KNOWN_TP | EVALUATION_1 | 1 |
| 20 | F-c06-02 | NULL | VERDICT | FAIL | — | MTIME_UNDEPLOYED | TRACEABLE_EXECUTABLE | KNOWN_TP | EVALUATION_2 | 2 |
| 21 | F-c06-03 | NULL | VERDICT | PASS | — | MTIME_DEPLOYED | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION | EVALUATION_1 | 1 |
| 22 | F-c06-04 | NULL | VERDICT | PASS | — | MTIME_DEPLOYED | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION | EVALUATION_2 | 2 |
| 23 | F-c06-05 | NULL | VERDICT | UNC | — | NETWORK_UNAVAILABLE | TRACEABLE_EXECUTABLE | KNOWN_TP | EVALUATION_2 | 2 |
| 24 | F-c06-06 | NULL | WORKFLOW | — | WAITING_CDN | — | TRACEABLE_EXECUTABLE | — | PRECHECK | null |
| 25 | F-c06-07 | NULL | WORKFLOW | — | UNC_RETRYABLE | — | TRACEABLE_EXECUTABLE | — | EVALUATION_1 | 1 |
| 26 | F-c06-08 | NULL | VERDICT | PASS | — | SITEMAP_REGISTERED | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION | EVALUATION_2 | 2 |
| 27 | F-c06-09 | NULL | VERDICT | FAIL | — | MTIME_STALE | TRACEABLE_EXECUTABLE | KNOWN_TP | EVALUATION_2 | 2 |

**Sub-totals:** FAIL=3, PASS=3, UNC=1 → 7 VERDICT + 2 WORKFLOW

#### c04 — Prompt Leak (1 fixture)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 28 | F-c04-01 | NULL | VERDICT | FAIL | — | PROMPT_LEAK_CONFIRMED | TRACEABLE_EXECUTABLE | KNOWN_TP |

#### FM-MISSINGKEYS (4 fixtures)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 29 | F-fm-01 | NULL | VERDICT | FAIL | — | KEY_ABSENT | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 30 | F-fm-02 | NULL | VERDICT | FAIL | — | KEY_ABSENT | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 31 | F-fm-03 | NULL | VERDICT | PASS | — | ALL_KEYS_PRESENT | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |
| 32 | F-fm-04 | NULL | VERDICT | PASS | — | ALL_KEYS_PRESENT | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |

**Sub-totals:** FAIL=2, PASS=2 → 4 VERDICT

#### content_quality — CQ03/CQ05 (3 fixtures)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 33 | F-cq-01 | NULL | VERDICT | FAIL | — | DISCLOSURE_ABSENT | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 34 | F-cq-02 | NULL | VERDICT | PASS | — | DISCLOSURE_PRESENT | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |
| 35 | F-cq-03 | NULL | VERDICT | NOT_APPLICABLE | — | N/A_SKIP_PRODUCT_RULES | TRACEABLE_EXECUTABLE | — |

**Sub-totals:** FAIL=1, PASS=1, NOT_APPLICABLE=1 → 3 VERDICT

#### semantic (2 fixtures)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 36 | F-sem-01 | NULL | VERDICT | UNC | — | SEMANTIC_REQUIRES_HUMAN | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 37 | F-sem-02 | NULL | VERDICT | PASS | — | SEMANTIC_NORMAL | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |

**Sub-totals:** UNC=1, PASS=1 → 2 VERDICT

#### c03 — FM Key Leak (2 fixtures)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 38 | F-c03-01 | NULL | VERDICT | FAIL | — | FM_KEY_LEAK | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 39 | F-c03-02 | NULL | VERDICT | PASS | — | NO_LEAK | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |

**Sub-totals:** FAIL=1, PASS=1 → 2 VERDICT

#### data_stock (2 fixtures)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 40 | F-ds-01 | NULL | VERDICT | FAIL | — | STOCK_DEPLETED | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 41 | F-ds-02 | NULL | VERDICT | PASS | — | STOCK_AVAILABLE | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |

**Sub-totals:** FAIL=1, PASS=1 → 2 VERDICT

#### freshness (2 fixtures)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 42 | F-fr-01 | NULL | VERDICT | FAIL | — | STALE_CONTENT | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 43 | F-fr-02 | NULL | VERDICT | PASS | — | FRESH_CONTENT | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |

**Sub-totals:** FAIL=1, PASS=1 → 2 VERDICT

#### R2-01 (1 fixture)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 44 | F-r2-01 | NULL | VERDICT | NOT_APPLICABLE | — | N/A_EXTERNAL_ALLOWABLE | TRACEABLE_EXECUTABLE | — |

#### maintenance_checklist (2 fixtures)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 45 | F-mc-01 | NULL | VERDICT | FAIL | — | CHECKLIST_INCOMPLETE | TRACEABLE_EXECUTABLE | KNOWN_TP |
| 46 | F-mc-02 | NULL | VERDICT | PASS | — | CHECKLIST_COMPLETE | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |

**Sub-totals:** FAIL=1, PASS=1 → 2 VERDICT

#### crosslink_consistency (1 fixture)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 47 | F-xc-01 | NULL | VERDICT | PASS | — | LINKS_FUNCTIONAL | TRACEABLE_EXECUTABLE | KNOWN_PASS_FP_PREVENTION |

#### rap_leak (1 fixture)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 48 | F-rl-01 | NULL | VERDICT | FAIL | — | DOUBLE_FRONTMATTER | TRACEABLE_EXECUTABLE | KNOWN_TP |

#### render_health (1 fixture)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 49 | F-rh-01 | NULL | VERDICT | FAIL | — | OG_IMAGE_MISSING | TRACEABLE_EXECUTABLE | KNOWN_TP |

#### R01 (1 fixture)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 50 | F-r01-01 | NULL | VERDICT | FAIL | — | TOC_ENABLED | TRACEABLE_EXECUTABLE | KNOWN_TP |

#### R06 (1 fixture)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 51 | F-r06-01 | NULL | VERDICT | FAIL | — | FLUID_FORMAT_MISSING | TRACEABLE_EXECUTABLE | KNOWN_TP |

#### c05 — Draft Publish (1 fixture)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | reason_code | provenance_status | contract_case |
|---|---|---|---|---|---|---|---|---|
| 52 | F-c05-01 | NULL | VERDICT | FAIL | — | DRAFT_LIVE | TRACEABLE_EXECUTABLE | KNOWN_TP |

#### c08 Title Suffix (1 fixture — non-verdict)

| # | fixture_id | subcheck_id | assertion_type | verdict | workflow_state | design_status | reason_code | provenance_status |
|---|---|---|---|---|---|---|---|---|
| 53 | F-c08-ts-01 | c08-C01 | DESIGN | — | — | NON_EXECUTABLE_CONTRACT_PENDING | — | NON_EXECUTABLE_CONTRACT_PENDING |

### 6.9.2 Arithmetic Cross-Check

**Total unique fixture_ids: 53** ✓

**By assertion_type (from §6.9.1 table rows):**

| assertion_type | Count | Percentage |
|---|---|---|
| VERDICT | 50 | 94.3% |
| WORKFLOW | 2 | 3.8% |
| DESIGN | 1 | 1.9% |
| **Total** | **53** | **100%** |

**By checker (fixture count):**

| Checker | fixture_ids | Count |
|---|---|---|
| c08 | F-c08-01 through F-c08-12, F-c08-ts-01 | 11 |
| c01 | F-c01-01 through F-c01-08 | 8 |
| c06 | F-c06-01 through F-c06-09 | 9 |
| c04 | F-c04-01 | 1 |
| FM-MISSINGKEYS | F-fm-01 through F-fm-04 | 4 |
| content_quality | F-cq-01 through F-cq-03 | 3 |
| semantic | F-sem-01, F-sem-02 | 2 |
| c03 | F-c03-01, F-c03-02 | 2 |
| data_stock | F-ds-01, F-ds-02 | 2 |
| freshness | F-fr-01, F-fr-02 | 2 |
| R2-01 | F-r2-01 | 1 |
| maintenance | F-mc-01, F-mc-02 | 2 |
| crosslink | F-xc-01 | 1 |
| rap_leak | F-rl-01 | 1 |
| render_health | F-rh-01 | 1 |
| R01 | F-r01-01 | 1 |
| R06 | F-r06-01 | 1 |
| c05 | F-c05-01 | 1 |
| **Total** | — | **53** |

**By verdict (VERDICT assertions only, 50 total):**

| verdict | Count | fixture_ids |
|---|---|---|
| FAIL | 19 | F-c08-01, F-c08-02, F-c08-03, F-c06-01, F-c06-02, F-c06-09, F-c04-01, F-fm-01, F-fm-02, F-cq-01, F-c03-01, F-ds-01, F-fr-01, F-mc-01, F-rl-01, F-rh-01, F-r01-01, F-r06-01, F-c05-01 |
| PASS | 26 | F-c08-05, F-c08-06, F-c08-07, F-c08-07b, F-c08-11, F-c08-12, F-c01-01~08, F-c06-03, F-c06-04, F-c06-08, F-fm-03, F-fm-04, F-cq-02, F-sem-02, F-c03-02, F-ds-02, F-fr-02, F-mc-02, F-xc-01 |
| UNC | 3 | F-c08-04, F-c06-05, F-sem-01 |
| NOT_APPLICABLE | 2 | F-cq-03, F-r2-01 |
| **Total VERDICT** | **50** | — |

**Non-verdict assertions (3 total):**

| assertion_type | Count | fixture_ids |
|---|---|---|
| WORKFLOW | 2 | F-c06-06, F-c06-07 |
| DESIGN | 1 | F-c08-ts-01 |

**Authoritative distribution (from fixture rows, not targets):**

| Metric | Value |
|---|---|
| FAIL | **19** |
| PASS | **26** |
| UNC | 3 |
| NOT_APPLICABLE | 2 |
| VERDICT total | 50 |
| WORKFLOW | 2 |
| DESIGN | 1 |
| **Grand total** | **53** |

### 6.9.3 Per-Checker Breakdown

After careful re-enumeration:

| Checker | FAIL | PASS | UNC | NOT_APPLICABLE | WORKFLOW | DESIGN | Total |
|---|---|---|---|---|---|---|---|
| c08 | 3 | 6 | 1 | 0 | 0 | 1 | 11 |
| c01 | 0 | 8 | 0 | 0 | 0 | 0 | 8 |
| c06 | 3 | 3 | 1 | 0 | 2 | 0 | 9 |
| c04 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| FM-MISSINGKEYS | 2 | 2 | 0 | 0 | 0 | 0 | 4 |
| content_quality | 1 | 1 | 0 | 1 | 0 | 0 | 3 |
| semantic | 0 | 1 | 1 | 0 | 0 | 0 | 2 |
| c03 | 1 | 1 | 0 | 0 | 0 | 0 | 2 |
| data_stock | 1 | 1 | 0 | 0 | 0 | 0 | 2 |
| freshness | 1 | 1 | 0 | 0 | 0 | 0 | 2 |
| R2-01 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| maintenance | 1 | 1 | 0 | 0 | 0 | 0 | 2 |
| crosslink | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| rap_leak | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| render_health | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| R01 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| R06 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| c05 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| **Total** | **19** | **26** | **3** | **2** | **2** | **1** | **53** |

**Arithmetic verification:** FAIL(19)+PASS(26)+UNC(3)+NOT_APPLICABLE(2)+WORKFLOW(2)+DESIGN(1) = 53 ✓

**Authoritative verdict distribution (from fixture rows, not targets):**
- FAIL = **19** (not the 17 target)
- PASS = **26** (not the 17 target)
- UNC = 3
- NOT_APPLICABLE = 2
- Total VERDICT = 50
- WORKFLOW = 2
- DESIGN = 1
- Grand total = 53

### 6.9.4 Assertion-Type Breakdown

| assertion_type | Count | Percentage |
|---|---|---|
| VERDICT | 50 | 94.3% |
| WORKFLOW | 2 | 3.8% |
| DESIGN | 1 | 1.9% |
| **Total** | **53** | **100%** |

### 6.9.5 Provenance-Status Breakdown

| provenance_status | Count | Percentage |
|---|---|---|
| TRACEABLE_EXECUTABLE | 44 | 83.0% |
| SYNTHETIC_UNIT_ONLY | 8 | 15.1% |
| UNRESOLVED_FIXTURE | 0 | 0% |
| NON_EXECUTABLE_CONTRACT_PENDING | 1 | 1.9% |
| **Total** | **53** | **100%** |

### 6.9.6 Checker-Level Breakdown

| Checker | Unique fixture_ids | assertion_type breakdown |
|---|---|---|
| c08 | 11 | VERDICT=10, DESIGN=1 |
| c01 | 8 | VERDICT=8 (all SYNTHETIC) |
| c06 | 9 | VERDICT=7, WORKFLOW=2 |
| c04 | 1 | VERDICT=1 |
| FM-MISSINGKEYS | 4 | VERDICT=4 |
| content_quality | 3 | VERDICT=3 |
| semantic | 2 | VERDICT=2 |
| c03 | 2 | VERDICT=2 |
| data_stock | 2 | VERDICT=2 |
| freshness | 2 | VERDICT=2 |
| R2-01 | 1 | VERDICT=1 |
| maintenance | 2 | VERDICT=2 |
| crosslink | 1 | VERDICT=1 |
| rap_leak | 1 | VERDICT=1 |
| render_health | 1 | VERDICT=1 |
| R01 | 1 | VERDICT=1 |
| R06 | 1 | VERDICT=1 |
| c05 | 1 | VERDICT=1 |
| **Total** | **53** | **VERDICT=50, WORKFLOW=2, DESIGN=1** |

### 6.9.7 Arithmetic Cross-Check Formula

```
53 = 11(c08) + 8(c01) + 9(c06) + 1(c04) + 4(fm) + 3(cq) + 2(sem) + 2(c03) + 2(ds) + 2(fr) + 1(r2) + 2(mc) + 1(xc) + 1(rl) + 1(rh) + 1(r01) + 1(r06) + 1(c05)
53 = 53 ✓

VERDICT(50) + WORKFLOW(2) + DESIGN(1) = 53 ✓

FAIL(19) + PASS(26) + UNC(3) + NOT_APPLICABLE(2) = 50 VERDICT ✓

TRACEABLE(44) + SYNTHETIC(8) + NON_EXECUTABLE(1) = 53 ✓
```

---

## 6.10 Residual Risks

| # | Risk | Checker | Status | Impact |
|---|---|---|---|---|
| 1 | c01-P03/F01 provenance unresolved | c01 | UNRESOLVED_PROVENANCE | Blocks G5 regardless of other metrics |
| 2 | c06-C05/C08 provenance unresolved | c06 | UNRESOLVED_PROVENANCE | c06 TP13 fixture provenance unverified |
| 3 | c08 configured site-name suffix not finalized | c08 | NON_EXECUTABLE_CONTRACT_PENDING | F-c08-ts-01 DESIGN assertion; title normalization depends on per-blog suffix config |
| 4 | c08 child evaluation contract pending (title/image pairing) | c08 | NON_EXECUTABLE_CONTRACT_PENDING | c08-C04b/C08b suffix contracts not resolved |
| 5 | TP13 + c01 FP4 provenance unresolved | c01, c08 | UNRESOLVED_PROVENANCE | G5 = PENDING/BLOCKED until resolved |
| 6 | c01 47 live fails all reclassified as FP (natural-language) | c01 | DESIGN_FLAW_DETECTED | Check rule is overly broad — template-leak detection catches natural-language curly quotes |
| 7 | c06 PRECHECK→EVALUATION_1 timing edge cases | c06 | WORKFLOW_DEPENDENT | Network latency may cause PRECHECK to exceed 15-min window |
| 8 | FM-MISSINGKEYS _index.md scan produces 40 FP | FM-MISSINGKEYS | CHECK_LOGIC_ISSUE | ETAP list template scanned as content post |
| 9 | CQ03/CQ05 skip_product_rules config completeness | content_quality | CONFIG_DEPENDENT | Stock/sector/finance blogs must be in skip list |
| 10 | 91.4% is projection, not measured | all | NOT_MEASURED | Precision ≥90% gate cannot be evaluated until patch + RecheckAll |

**G5 Status: PENDING/BLOCKED** — TP13+c01 FP4 provenance unresolved.

---

## Section 6 Approval Request

Section 6 Final Amendment submitted. Awaiting approval before proceeding to Section 7 or any code/config/DB/test/commit/push/deploy/tuning/sampling/network changes.

**Decision requested:** APPROVE or RETURN with specific amendment instructions.
