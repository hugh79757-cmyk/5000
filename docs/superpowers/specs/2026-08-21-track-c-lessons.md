# Track C Lessons — RETROSPECTIVE

**Status:** RETROSPECTIVE
**Date:** 2026-08-21

## Lesson 1 — Gate Bypass vs Honest Failure

The gate-bypass path achieved 94.1% pass rate, but honest runs failed 21/22 cases.
When measured honestly, only 325–385 of 400 items passed the gate.
The bypass inflated perceived success; raw honest numbers expose the real gap.

> **Timestamp clarification:** The "21/22" (22중 21 미달) figure is the gate honest re-evaluation measured at **2026-08-21 18:00** (pre-regeneration). Today's live run measures **14 posts** at **2026-08-21 23:00** post-deploy with STN 359 / PEK 374 / KDL 302. These are distinct timestamps — do not conflate the pre-regeneration 18:00 evaluation with the post-deploy 23:00 measurement.

## Lesson 2 — Local Unused Data (runways.csv)

A local unused data file `runways.csv` contributed +60 words of spurious content.
Unused local data silently leaked into outputs and inflated length metrics.
Always confirm every data source is actually referenced before counting it.

## Lesson 3 — Classification: large_airport Mistranslation

The classifier mislabeled `large_airport` due to a mistranslation of the source term.
Mistranslated category labels produced wrong downstream routing.
Verify taxonomy mappings against the original-language source, not the translated one.

## Lesson 4 — Tool Artifact False Positives (6 cases)

Tooling emitted 6 false-positive cases flagged as artifacts of the tool itself, not real issues.
Each false positive carried a link that pointed to tool noise rather than a genuine defect.
Filter tool-generated artifacts before counting findings as actionable.

## Lesson 5 — Expression vs Data Grep (23 vs 15 vs 31)

Expression-based grep returned 23 matches; data-based grep returned 15; combined scan returned 31.
The three methods disagree, so no single grep method is sufficient on its own.
Report all three counts; treat the union as the realistic surface.

## Lesson 6 — Partial Failure: 9 Frontmatter Misses

A partial-failure mode left 9 frontmatter fields missing across the batch.
Partial success hid the misses because the overall run still reported "completed."
Treat any frontmatter miss as a failed unit, not a tolerated partial.

## Lesson 7 — Senior False Positives (4 cases)

Four senior-level items were false positives; rebuttal at this tier is normal and expected.
Don't treat a senior rebuttal as a defect — it is part of the review process.
Log the 4 cases as known false positives rather than re-escalating them.

## Lesson 8 — Sitemap lastmod Batch Deploy Without Approval

14 posts all carried `lastmod` = `2026-08-21T12:00:00+09:00` from a single batch deploy.
The batch ran without prior approval and overwrote real per-post modification times.
Always seek approval before a batch deploy that rewrites sitemap timestamps en masse.

## Lesson 9 — Thumbnail Regression (April ZRH R2 vs Today)

An April ZRH R2 cover image regressed; today 14 posts are missing `og:image`/`twitter` tags.
The earlier cover was replaced without re-propagating social-card metadata to dependents.
Verify og:image/twitter cards on every post when a shared R2 cover asset changes.

## Lesson 10 — Draft vs Deployed Mismatch (/tmp/stn)

Draft and deployed copies diverged: `/tmp/stn` measured 428 words versus 359 words deployed.
The deployed version was stale relative to the latest draft at publish time.
Reconcile draft and deployed word counts before flagging a post as finished.

## Lesson 11 — Free Fallback CJK Leak (MiMo V2.5 Free)

The free fallback model MiMo V2.5 Free leaked CJK strings such as "简单说就是" into output.
Unfiltered free-tier CJK responses slipped past the language gate into published content.
Add a CJK-leak guard on free fallback outputs before they reach the publish stage.

## 2026-08-21 오후 (3건)
1. 계측기만 고치고 생산 경로를 고치지 않아 하루를 소진했다
2. 게이트가 막았을 때 코드에 예외 경로를 파려 했으나 실제 원인은 커밋에 무관한 142파일이 섞인 것이었다
3. 소스 기반 미쉐린 기준선(1218단어·어필리에이트 0)이 라이브 실측에서 뒤집혔다
