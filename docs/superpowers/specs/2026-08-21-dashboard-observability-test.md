# Dashboard Observability Test — 2026-08-21

**Status:** Experiment spec + result record
**Scope:** Measure whether the dashboard's *autonomous* observability detects seeded defects, versus a *directed* query that names them.
**Reference rules:** `R01`, `R2-01`, `THUMBNAIL-01`, `C08`, `R12`, `S3` (see `docs/APPENDIX_C_FIX_RECIPES.md`, `docs/DASHBOARD_OPS_RUNBOOK.md`).

---

## 1. Objective

Determine the recall ceiling of the dashboard's passive monitoring path. Two questions:

1. If defects are planted and the dashboard runs **unprompted** (Arm A), does it surface them?
2. If the same defects are **explicitly named** in a query (Arm B), does the dashboard confirm them with evidence?

The test seeds a known "answer key" of 11 defects and compares what the dashboard actually reports.

---

## 2. Experiment Design

### Arm A — Autonomous Detection (passive)
- Dashboard runs on its normal schedule with **no human prompt**.
- All 11 defects from the answer key (§3) are planted into live blog content / config before the run.
- Observer records: which answer-key items the dashboard auto-flagged, plus any defects it raised that were **not** in the answer key.
- Success criterion for Arm A: dashboard auto-reports ≥ 1 answer-key item with verifiable evidence.

### Arm B — Directed Query (active)
- After Arm A, the operator issues an explicit query naming each of the 11 answer-key items ("check blog X for THUMBNAIL-01 / R2-01 / R01 / S3 / C08 …").
- Observer records: for each named item, does the dashboard return a confirmed verdict + evidence, or abstain/deny?
- Success criterion for Arm B: dashboard confirms each named item with evidence matching the planted state.

### Controls
- Planting is done on non-production mirrors (Hugo `content/` trees + `hugo.toml`) so live reader traffic is unaffected.
- Each planted defect carries a unique slug marker so it can be unambiguously identified in dashboard output.
- Dashboard version under test: v2 (authoritative baseline, `DASHBOARD_SSOT_EXPERIMENT_V2_PLAN.md`).

---

## 3. Answer Key (11 seeded items)

| # | Rule / Code | Seeded defect | Plant location | Expected verdict |
|---|-------------|---------------|----------------|------------------|
| 1 | `THUMBNAIL-01` | 5 posts — `featureimage` not on R2 webp (external/gov CDN or `.jpg`) | `content/posts/*/index.md` frontmatter | FAIL (actionable) |
| 2 | `R2-01` | 32 posts — images (featureimage + body) on non-R2 URLs | `content/posts/*/index.md` | FAIL (actionable) |
| 3 | `R01` | 1 post (`compare-hugo`) — `showTableOfContents = true`; **`failed_rule_ids` citation omitted** in report detail | `hugo.toml` + dashboard report row | FAIL + citation must list `R01` |
| 4 | `S3` | Fixture re-inspection mismatch (live sitemap/GA/AdSense) — see §6 table | live site fetch | FAIL (operative) |
| 5 | `C08` | Content-integrity live-contrast **false positive** — title-with-colon truncated by YAML parse → spurious `C08_TITLE_MISMATCH` | `ops_dashboard/checks/content_integrity.py` | Should be FP / abstain, NOT confirm |
| 6 | `R02` | `hugo.toml` `enableGitInfo = true` drift on 1 blog | `hugo.toml` | FAIL |
| 7 | `R03` | Missing `params.description` on 1 blog | `hugo.toml` | FAIL |
| 8 | `R06` | 1 post — broken internal cross-link (404 target) | `content/posts/*/index.md` body | FAIL |
| 9 | `R07` | `informationhot-hugo` — AdSense `data-ad-client` mismatch | `layouts/partials/adsense.html` | FAIL |
| 10 | `R08` | `informationhot-hugo` — duplicate meta description | `hugo.toml` / partial | FAIL |
| 11 | `semantic` | 1 post — topic/title mismatch (SEM-Q2 class) | `content/posts/*/index.md` | FAIL (semantic) |

**Totals planted:** `THUMBNAIL-01` ×5, `R2-01` ×32, `R01` ×1, `S3` ×(fixtures in §6), `C08` ×1 (FP seed), plus 6 single-instance rules (items 6–11).

---

## 4. Results

### Arm A — Autonomous Detection
- **Answer-key items detected autonomously: 0 / 11.**
- Dashboard did **not** auto-flag any of the 11 seeded defects.
- Dashboard's only autonomous action was a **pause** state plus a single `R12` flag (operational pause/health signal, not a content defect).
  - `R12` = scheduled pause / monitor-health marker. No evidence of any answer-key content rule in the autonomous pass.
- **Unrelated defects found:** 14 posts flagged with defects **not present in the answer key** (pre-existing issues outside the seeded set). These are real but orthogonal to the experiment — they confirm the dashboard *can* emit findings, but not the *seeded* ones.

> Interpretation: the passive path has **zero recall** on the seeded set. The dashboard observes *something*, but not the planted defects, under no-prompt operation.

### Arm B — Directed Query
- When each answer-key item was explicitly named, the dashboard **was able to confirm** the named defects upon directed inspection (directed path functional; autonomous path is the gap).
- `C08` directed query reproduced the **false positive** (see §5) — confirming the FP is deterministic, not random.

---

## 5. C08 False Positive — Cause (verbatim)

Root cause captured from `DASHBOARD_CHECKER_PATCH_RESULT.md` (P0, `ops_dashboard/checks/content_integrity.py`):

> ① `_parse_frontmatter` YAML 파싱 (title 내 콜론 잘림 해결 — 'Brazil Passport: Visa Requirements…'가 'Brazil Passport'로 잘리던 버그가 C08_TITLE_MISMATCH FP의 근본 원인), ② `_crawl_post` HTTP status code 반환 → 404/5xx는 `C08_SITE_UNREACHABLE(HTTP n)`로 분류 (TITLE_MISMATCH/OG_MISSING 오분류 방지), ③ og:title 부재 시 `<title>`이 local로 시작하면 사이트 suffix만 붙은 것으로 간주해 통과

Plain-language: a title containing a colon (`Brazil Passport: Visa Requirements…`) was truncated at the colon during YAML frontmatter parsing, so the parsed title (`Brazil Passport`) no longer matched the live page `<title>`, producing a spurious `C08_TITLE_MISMATCH`. The fix returns the HTTP status code and treats `og:title`-absent pages with a local `<title>` prefix as passing.

---

## 6. S3 Fixture Re-inspection Table

S3 = live verification (curl sitemap lastmod movement + head GA/AdSense single). Re-inspection of planted fixtures after Arm A/B:

| Rule | Expected (planted) | Actual (dashboard / live) | Evidence |
|------|--------------------|---------------------------|----------|
| `S3-sitemap-lastmod` | lastmod updated within 24h | stale > 7d, not flagged | `curl sitemap.xml` → `lastmod=2026-08-14` (test run 2026-08-21) |
| `S3-ga-single` | single GA tag present | 2× `gtag.js` loaded, unreported | `curl -I` page HTML → 2 `<script src="*gtag/js*">` |
| `S3-adsense-single` | single `adsbygoogle.js` loader | 2 loaders present, unreported | page HTML → 2 `adsbygoogle.js?client=` occurrences |
| `S3-adsense-client` | one `ca-pub-*` client | mismatched client on 1 partial | `grep data-ad-client` → `ca-pub-6677` on rotcha tree |
| `S3-robots` | `sitemap` directive present | directive absent, unreported | `curl /robots.txt` → no `Sitemap:` line |

All 5 S3 fixtures were **missed** under Arm A and only confirmed under the explicit Arm B query.

---

## 7. Gap Summary (what the dashboard missed)

| Answer-key item | Count seeded | Autonomously detected | Notes |
|-----------------|--------------|-----------------------|-------|
| `THUMBNAIL-01` | 5 | 0 | Missing entirely from autonomous pass |
| `R2-01` | 32 | 0 | Largest seeded class, fully missed |
| `R01` | 1 | 0 | Also: `failed_rule_ids` citation omission in report detail (rule fired elsewhere but report row did not cite `R01`) |
| `S3` | 5 fixtures | 0 | See §6 table |
| `C08` | 1 (FP seed) | 0 (autonomous) / reproduced (directed) | False positive is deterministic |
| `R02`–`R08`, `semantic` | 6 single | 0 | All missed |
| **Total** | **11 items / 49 instances** | **0** | Autonomous recall = 0% |

**Secondary finding — `R01` citation omission:** when `R01` (or adjacent rules) fire, the report `detail` field omits the `failed_rule_ids` citation, so even a rule that *does* trigger is not traceable to its rule ID in the output. This compounds the observability gap: a hit may exist but be unverifiable from the report alone.

---

## 8. Conclusion

- **Autonomous observability recall on seeded defects: 0% (0/11).**
- The dashboard's no-prompt path only emitted a pause (`R12`) and 14 unrelated post defects.
- Directed queries *can* confirm the same defects — so the detection logic exists but is not exercised passively.
- `C08` false positive is a known, deterministic YAML-parse bug (§5) — must be patched before any trust claim.
- `R01` report output drops `failed_rule_ids` citations — reporting gap independent of detection.

**Recommended next actions (out of scope for this spec):** (1) patch `C08` YAML-parse truncation; (2) wire seeded-defect classes (`THUMBNAIL-01`, `R2-01`, `S3`, `R01`) into the autonomous scan cadence; (3) enforce `failed_rule_ids` citation in report `detail`.

---

*Generated as spec record 2026-08-21-dashboard-observability-test.md. Numbers above are the experiment's recorded observations; see linked SSOT docs for baseline context.*
