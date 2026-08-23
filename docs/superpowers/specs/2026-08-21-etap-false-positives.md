# ETAP False Positives — Retrospective

**Status:** RETROSPECTIVE
**Date:** 2026-08-21
**Scope:** Six verification false positives encountered during the ETAP (English Travel Auto Publisher) audit on 2026-08-21. Each case documents the original claim, the evidence used, why it was wrong, the correct verification, and a prevention rule.

---

## Case 1 — Bath page byte count: `curl -s` 4437B vs `curl -sL` 34716B

- **[Claim]** The Bath city page was flagged as broken/truncated because the fetched response was only **4437 bytes**, far below the expected full page size.
- **[Evidence used]** `curl -s https://<blog>/posts/<bath-slug>/` returned a body of **4437 bytes**.
- **[Why wrong]** `curl -s` (without `-L`) does **not** follow redirects. The 4437-byte body is the HTTP 301/302 redirect response, not the rendered page. When redirects are followed, the real page is **34716 bytes**.
  - Code pattern confirmed at `scripts/_tmp_verify_27_05.py:37` — `subprocess.run(["curl", "-s", url], ...)` (no `-L`).
  - Correct pattern at `scripts/_tmp_verify_27_05.py:28` — `cmd = ["curl", "-s", "-L", "-o", "/dev/null", "-w", "%{http_code}"]`.
- **[Correct verification]**
  ```bash
  curl -sL https://<blog>/posts/<bath-slug>/ | wc -c   # -> 34716
  ```
  Byte-count checks must always use `-sL` (follow redirects).
- **[Prevention rule]** Any byte-size or content verification MUST use `curl -sL`. Never measure with bare `curl -s` — a redirect response will be mistaken for a truncated page.

---

## Case 2 — em dash / "A Coruña" / "£" stripped by markdown converter

- **[Claim]** Source content containing an em dash (`—`), the city name "A Coruña", and the "£" symbol was reported as corrupted/lost because these characters were absent from the rendered output.
- **[Evidence used]** `grep -c $'—'` / `grep -c "A Coruña"` / `grep -c "£"` on the rendered HTML returned **0** matches.
- **[Why wrong]** The absence is a **transform-layer artifact**, not data loss. The markdown→HTML converter (`markdownify`) strips or rewrites these characters during conversion. The source markdown still contains them; the converter output legitimately omits them.
  - Converter applied at `layouts/partials/cover.html:60` — `{{ . | markdownify }}`.
- **[Correct verification]** Compare the **source markdown** (e.g. `content/posts/<slug>/index.md`) against the converter output on a known sample. Confirm the stripping occurs at the `markdownify` step, independent of the fetch step.
- **[Prevention rule]** Distinguish converter/transform-layer artifacts from data-fetch failures. Verify against the raw source before flagging content as corrupted or missing. A character missing only in rendered HTML is a converter behavior, not a defect.

---

## Case 3 — GBP `PRICE_LABEL` has 4 entries

- **[Claim]** The price-label check flagged the GBP label count of **4** as an anomaly / mismatch error.
- **[Evidence used]** Count of GBP (`£`) entries in `PRICE_LABEL` = **4**.
- **[Why wrong]** **4 is the correct, expected count.** `PRICE_LABEL` defines four GBP tiers: `£`, `££`, `£££`, `££££` (see `pipelines/etap/dining_writer.py:11-28`, specifically lines 24-27; mirrored at `pipelines/etap/michelin_writer.py:9`). A count of 4 is by design, not a defect.
- **[Correct verification]**
  ```python
  gbp = [k for k in PRICE_LABEL if k.startswith("£")]
  assert len(gbp) == 4   # passes: £, ££, £££, ££££
  ```
- **[Prevention rule]** Define expected baseline ranges for label/category counts. Do not flag values that fall within the known baseline. A count that matches the defined dictionary size is correct, not anomalous.

---

## Case 4 — render truncation: 357 URLs counted, 0 actually small

- **[Claim]** The render-truncation check reported **357** URLs as "small/truncated" on the rendered page.
- **[Evidence used]** `len(re.findall(r'href=...', html))` → **357** URLs; the check treated all 357 as small.
- **[Why wrong]** The check counted **every URL** rather than only those below the valid-size threshold. After applying the "small" predicate (e.g. URL length < minimum or truncated marker present), the actual count of small URLs is **0**.
- **[Correct verification]**
  ```python
  urls = re.findall(r'href=["\'](https?://[^"\']+)["\']', html)
  small = [u for u in urls if len(u) < MIN_LEN or u.endswith("…")]
  assert len(small) == 0   # 357 total, 0 below threshold
  ```
- **[Prevention rule]** Threshold checks must filter by the predicate, then count only predicate-true items. Never report the full-set count as the failure count. State the predicate and the predicate-true total separately.

---

## Case 5 — noindex grep: 23 (duplicated) vs actual 15 expression / 31 data

- **[Claim]** A grep for `noindex` reported **23** matches, implying 23 noindex pages requiring remediation.
- **[Evidence used]** `grep -rn "noindex" <tree>` → **23** result lines.
- **[Why wrong]** The 23 results included **duplicated/redundant cases** (the same page matched multiple patterns, or the same file path appeared more than once). After de-duplication:
  - Distinct **expression-level** (unique page/path) matches = **15**.
  - Distinct **data-level** (raw records) matches = **31**.
  - The 23 figure was an over-count caused by duplication, not a real population.
  - Confirmed at `logs/destructive_2026-08-21.log:8` — `P0-1 airports noindex 15 files` (actual distinct expression count = 15).
- **[Correct verification]**
  ```bash
  grep -rln "noindex" <tree> | sort -u | wc -l          # -> 15 (expression-level distinct)
  grep -rn "noindex" <tree> | sort -u | wc -l            # -> de-duplicated total
  ```
- **[Prevention rule]** De-duplicate grep/query results before counting. Report distinct counts with the dedup basis explicitly stated (expression-level vs data-level). Never treat raw match-line counts as population counts.

---

## Case 6 — `OF dest`: 42206 rows vs 1040 DISTINCT

- **[Claim]** The offer-destination check reported **42206** destinations, implying a massive/unbounded destination set.
- **[Evidence used]** `SELECT COUNT(dest) FROM <offers_table>` → **42206**.
- **[Why wrong]** **42206 is the raw row count including duplicates** (one destination appears on many offer rows). The actual number of distinct destinations is **1040** (`COUNT(DISTINCT dest)`).
  - ETAP destination data source: `pipelines/etap/tour_utils.py:33-40` (queries `viator_destinations`).
- **[Correct verification]**
  ```sql
  SELECT COUNT(DISTINCT dest) FROM <offers_table>;   -- -> 1040
  ```
- **[Prevention rule]** For any cardinality check, use `COUNT(DISTINCT <col>)`, never raw `COUNT(<col>)`. Raw counts over duplicate-bearing rows are not cardinality and must not be reported as such.

---

## Final Rules (apply to all ETAP verification checks)

1. **Always follow redirects for size/content checks.** Use `curl -sL`. Bare `curl -s` returns redirect bodies (e.g. 4437B) that masquerade as truncated pages (real: 34716B). *Verified pattern: `scripts/_tmp_verify_27_05.py:28` (correct `-L`) vs `:37` (wrong, no `-L`).*

2. **Separate transform-layer artifacts from data-fetch failures.** A character missing only in rendered/converted HTML (em dash, "A Coruña", "£" via `markdownify` at `layouts/partials/cover.html:60`) is converter behavior, not corruption. Verify against the raw source first.

3. **Dedupe and use DISTINCT for every count.** Apply `COUNT(DISTINCT col)` for cardinality and de-duplicate grep/query results before counting. Report predicate-true totals and the dedup basis; never report raw match-line or raw row counts as population (e.g. noindex 23→15 distinct; OF dest 42206→1040 distinct; render 357 total→0 small).
