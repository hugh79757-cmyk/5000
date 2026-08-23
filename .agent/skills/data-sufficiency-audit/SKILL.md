---
name: data-sufficiency-audit
description: Use when a pipeline generates content from structured data, before writing or fixing any generation code
---

# Data Sufficiency Audit

## Overview

Before any content-generation code is written or patched, verify that the
structured source data actually contains enough fields to produce
non-vague, fully-grounded content. The cheapest fix for low-quality generated
content is to quarantine insufficient records at the data layer — not to
"improve the prompt" so it invents plausible-sounding filler.

Core principle: **No generation code change until the data gap is measured.**
If the data cannot support a factual statement, the pipeline must refuse to
generate that statement, not paraphrase it into vagueness.

## When to Use

- A pipeline turns rows/records (CSV, JSON, DB tables) into articles,
  descriptions, or cards.
- Generated content reads as hedged, generic, or location-ambiguous.
- You are about to edit the prompt, template, or generation function to
  "make it sound better" on records with missing fields.
- A categorical/code field (e.g. a type or class) is leaking raw codes
  into published content.

When NOT to use:
- Pure freeform writing with no backing dataset.
- Fixing a rendering bug unrelated to underlying data completeness.

## The 7-Step Audit

1. **Inventory available fields.** List every field present in the source
   record (name, type, nullability, example value). Do not assume a field
   exists because the template references it.

2. **Map required fields per content block.** For each sentence/section the
   generator must emit, list the exact fields it depends on. A content block
   with zero required fields is a red flag (it will be pure filler).

3. **Measure completeness per record.** For each record, compute which
   required fields are missing or empty. Produce a per-field fill rate
   (filled / total records).

4. **Identify gap-driven vagueness.** Find records where a required field is
   missing. These are the only records that force the generator toward
   generic language. Quantify how many records would be affected.

5. **Check categorical/code translation.** For every enum or code field
   (type, class, category), confirm a human-readable label mapping exists
   and is applied. Raw codes must never reach published content.

6. **Quarantine, don't patch.** Decide a sufficiency threshold. Records
   below threshold are held from generation (or routed to a degraded
   template that only states known facts). This is a data-layer decision,
   not a prompt tweak.

7. **Report metrics + required source fixes.** Output the fill-rate table,
   the count of quarantined records, and the specific source fields that
   must be populated before generation quality can improve. Hand this to the
   data owner; do not silently compensate in generation code.

## Red Flags — Stop and Audit the Data

### Vague qualifiers in output
If generated content contains these words, it almost always means a required
field was empty and the model bridged the gap with hedging:

- **"typically"** — a stand-in for a missing behavioral/statistical field.
- **"generally"** — a stand-in for a missing scope/condition field.
- **"in its regional context"** (or "locally", "in the area") — a stand-in
  for a missing location/region field. The model is admitting it does not
  know the specific region.

Any of these in output ⇒ the record lacked the field the sentence needed.
Fix the data; do not train the prompt to use these words intentionally.

### Classification not translated
A categorical code such as `large_airport` (or any `snake_case` type token)
appearing in published text means the translation map was skipped or
missing. The code is an internal key, not content. Translate to the
human-readable label (e.g. "large airport") before emission, and if no
mapping exists, treat the record as insufficient rather than printing the
raw code.

## Common Mistakes

- **Patching the prompt instead of the data.** "Write more concretely"
  cannot invent a field that does not exist.
- **Averaging over the whole dataset.** A 95% fill rate hides a cohort
  where one critical field is 0% — audit per required-field, not globally.
- **Silent fallback.** Letting the generator substitute a default/"N/A"
  string produces confidently wrong content. Quarantine is safer.
- **Leaking codes.** Shipping enum keys to readers because the label map
  was "optional."

## Real-World Impact

Auditing before coding prevents an entire class of "looks fine but is
factually hollow" content. The remediation cost is one data fix, not
continuous prompt babysitting.
- 임계값 미달이 반복되면 규칙을 의심하기 전에 원자료가 그 분량을 정직하게 채울 수 있는 주제인지 먼저 판정한다.
