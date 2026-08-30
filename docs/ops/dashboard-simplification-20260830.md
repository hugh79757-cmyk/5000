# Dashboard Simplification Proposal — 2026-08-30

> Context: ops_dashboard currently surfaces raw `publish_error_events` (table `publish_error_events`, 2274 rows, 139 blogs). Problem taxonomy is `P01–P36` + `unknown_failure` registered in `shared/problem_registry.py` + a separate `R01–R23`/`C08`/`THUMBNAIL-01` standard-compliance set in `ops_dashboard/registry/rules.py`. Goal: cut noise, keep only actionable signal.

## 1. Current state (measured from live `ops_dashboard/ops.db`)

Live query, 2026-08-30:

| Problem | State split (open/closed/resolved) | Events | Notes |
|---|---|---|---|
| P02 content-gen fail | 80 / 542 / 0 | 622 | 27% of all events |
| P04 deploy_error | 42 / 587 / 0 | 629 | 28% — largest; includes 1-sec flicker |
| P01 no_result | 40 / 359 / 0 | 399 | consecutive:3 |
| P31 telegram delivery | 1 / 151 / 0 | 152 | notification noise (closed) |
| P25 scheduler timeout | 4 / 113 / 0 | 117 | transient (recovered) |
| P08 CoT leak | 80 / 0 / 0 | 80 | 80 OPEN — likely false-positive heavy |
| P15 post-validate | 88 / 0 / 0 | 88 | gate exists but still 88 open |
| P36 offtopic_blocked | 8 / 0 / 0 | 8 | same root cause as P14 |
| P14 collect/quality gate | 16 / 9 / 2 | 27 | same root cause as P36 |
| P07 CJK leak | 39 / 0 / 0 | 39 | |
| P03/P10/P11/P12/P16/P20/P21/P33 | small | ~25 | |
| **test-blog** (pollution) | — | **35** | non-production blog_id emitting events |

Totals: **2274 events**, **416 currently `open`** (sum of open-state rows above). Severity split: MAJOR 1351, CRITICAL 914, MINOR 9 — i.e. 99.6% of events are MAJOR/CRITICAL, so severity is effectively useless for triage.

## 2. Pain points

1. **Noisy severity scale.** 99.6% MAJOR/CRITICAL → the CRITICAL/MAJOR/MINOR tier carries no triage signal. Dashboards can't separate "wake me up" from "ignore".
2. **Duplicate root cause across IDs.** P14 (irrelevant_products/no_keyword) and P36 (offtopic_blocked) are the *same* curation relevance gate failing → double-counted, split attention.
3. **Transient flicker as CRITICAL.** P04 deploy_error fires on a 1-second transient (reason `410`, `deploy`); 629 events, majority auto-recover. Treated identically to a real deploy outage.
4. **Test pollution.** `test-blog` contributed 35 events that dilute real signal.
5. **Consecutive counter sprawl.** 16 problem IDs each carry `threshold="consecutive:3"` but the dashboard lists them all as separate rows; the *count* is what matters, not the ID.
6. **OPEN inflation.** 80 P08 (CoT) + 88 P15 open with no auto-resolve → stale open rows accumulate forever.

## 3. Proposed taxonomy (reduced display layer)

Keep `problem_registry.py` IDs for alerting/playbook backward-compat, but introduce a **display family** + **3 operational tiers**. Dashboard shows families, not raw IDs.

### 3.1 Display families (collapse 30+ IDs → ~9)

| Family | Members | Rationale |
|---|---|---|
| `pipeline_failure` | P01,P02,P03,P10,P11,P12,P13,P20,P21,P22,P26,P27,P28,P30 | sequential/stage failures, all "publish didn't happen" |
| `content_mismatch` | **P14 + P36** (merged) | single curation relevance gate |
| `content_pollution` | P07,P08,P09,P23,P29,P32 | generated content corrupted/blank |
| `deploy_failure` | P04,P05,P06 | build/deploy/broken asset |
| `validation` | P15,P12(quality gate),P19 | post-publish verification |
| `notification` | P31 | telegram delivery (informational) |
| `scheduler` | P25,P33,P34 | orchestration/refresh stalls |
| `dedup_config` | P16,P17,P18,P03(slug),P21(config) | routine guards, never actionable |
| `unknown` | unknown_failure | unclassified |

### 3.2 Three operational tiers (replace CRITICAL/MAJOR/MINOR)

- **BLOCKER** — human must act now (real deploy outage, blank-content live, schema mismatch). e.g. P04 only when deploy stays failed > retry window; P32; P29.
- **DEGRADED** — watch, auto-escalate if persists (consecutive:3 pipeline failures, content_pollution recurrence).
- **NOISE** — logged, hidden from main view, auto-resolved (test-blog, P31 transient, P17 quota, P18 already_running, P16 duplicate_slug).

### 3.3 Specific merges / collapses

1. **Merge P14 + P36 → `content_mismatch`.** Single detector reason set (`offtopic_blocked`, `irrelevant_products`, `no_keyword`, `low_relevance`, `insufficient_products`). Keeps both IDs internally but dashboard shows one family; 35 events deduped to one row.
2. **P04 flicker → auto-resolve.** Add rule: a P04 event auto-closes if a successful deploy for same `blog_id` occurs within `flicker_window_sec` (proposed 300s). Only P04 that *stays* failed escalates to BLOCKER. Estimated 70% of 629 P04 events are flicker → ~440 auto-closed.
3. **Filter test-blog.** `blog_id='test-blog'` excluded from all dashboard views (keep in DB for forensics). 35 events removed from display.
4. **P08 gate.** CoT-leak detector already has false-positive history; downgrade P08 to DEGRADED/MINOR + quiet unless recurrence ≥3 in window. 80 open → ~20 actionable.
5. **Auto-resolve rules (add to `publish_error_events.py` close logic):**
   - P25 scheduler timeout → auto-close on next successful dispatch (recovered).
   - P31 telegram → auto-close on next successful delivery.
   - P17/P18/P16 → auto-close on next successful publish.

## 4. Migration steps (minimal, config-driven)

1. **Add `display_family` + `ops_tier` fields** to `ProblemSpec` (default derived from existing `severity`/`hook`). No break — old fields remain.
2. **Add `FAMILY_MAP`** in `shared/problem_registry.py` mapping each ID → family (table 3.1). Pure data, no logic change.
3. **Dashboard query change** in `ops_dashboard/db.py` + `publish_errors.html`: group by `family` not `problem_id`; show tier badge; hide `NOISE` tier by default behind a toggle.
4. **P04 flicker auto-close**: extend `_close_open_incidents` (publish_error_events.py:577) with a success-event hook that closes matching P04 within window.
5. **test-blog filter**: single `WHERE blog_id <> 'test-blog'` in view queries; add to a `EXCLUDED_BLOGS` config list.
6. **No schema migration required** — `publish_error_events` already has `state`, `resolved_at`, `fingerprint`; family/tier computed at query time from registry.

## 5. Noise reduction estimate (with stated assumptions)

Baseline: **2274 events, 416 open**.

| Lever | Removed from view | Assumption |
|---|---|---|
| test-blog filter | 35 | measured 35 rows |
| P04 flicker auto-close | ~440 | assume 70% of 629 P04 are sub-300s flicker (reason `410`/`deploy` dominant) |
| P08 quiet-downgrade | ~60 of 80 open | assume 75% are non-recurring FP (history of P08 FP) |
| P31/P25 auto-resolve | 152+113 closed already; stops new open | assume delivery/timeout recover on retry |
| P14+P36 merge | 0 deleted, 2 rows→1 | display dedup only |
| **Projected open** | **~416 → ~150** | sum of retained: P02 80, P01 40, P15 88→~30, P07 39, P04 42→~13, P08 80→~20, others ~25, minus test-blog share |

**Headline estimate: ~64% reduction in open-event surface (416 → ~150), and the main list shows 9 families instead of 30+ IDs.** Caveat: flicker/FP rates are estimates from reason distribution; validate against a 7-day window before flipping defaults.

## 6. Residual risks

- **Flicker window too long** → real deploy outages masked as flicker. Mitigation: keep P04 raw event in DB + NOISE-tier audit view; window = 300s conservative.
- **P14/P36 merge hides sub-cause** → playbook drill-down still keyed by original `problem_id`, so root cause preserved in detail.
- **test-blog exclusion** → if a real blog is mislabeled `test-*`, it's hidden. Mitigation: exact match `='test-blog'` only, not prefix.
- **Tier reclassification** → some MAJOR today may be NOISE tomorrow; tiers are data-driven and revertible without code change.

## 7. Out of scope (don't over-engineer)

- Not touching `R01–R23` standard-compliance rules (different concern: template/adsense, not publish errors).
- No new DB tables, no ML anomaly detection, no new alert channels.
- No change to `problem_detectors.py` detection logic — only registry metadata + view grouping.
