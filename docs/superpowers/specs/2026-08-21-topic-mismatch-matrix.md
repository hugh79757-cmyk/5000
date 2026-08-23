# ETAP Topic Mismatch Matrix — 3-Stage AND (36 blogs)

**Status:** MEASURED  
**Date:** 2026-08-21  
**Corpus:** `/Users/twinssn/Projects/ETAP/*-hugo/content/posts/*/index.md` — 36 blogs, 5405 posts (`_index.md` excluded)  
**Gate:** `approved = stage1 AND stage2 AND stage3` per `2026-08-21-topic-suitability-criteria.md`

## Measurement rules (as executed)

| Stage | Rule executed | Declared FP rate |
|---|---|---|
| 1 | frontmatter `slug` ends with `-guide` (fallback: post dir name) | ~5% (IATA exceptions) |
| 2 | `categories` ∪ `tags` contains the blog topic tag (modal `categories` value, excluding generic `Travel` / `Travel Guide` / `uncategorized`) | ~10% |
| 3 | `title` contains the blog keyword, case-insensitive | ~15% |

Stage 2/3 counts are evaluated **only on the survivors of the prior stage** (AND cascade). `mismatch = total − approved`.

## Provenance correction — the "91 for airports"

The 91 figure is **not** an airports stage-1 count. Measured airports stage-1: **73 pass / 90 fail** of 163.
Where 91 actually occurs:

- `2026-08-21-etap-audit-matrix.md:54` — airports `no_airlines` column = 91 (a different check).
- **Measured stage-3-style corpus count:** airports titles lacking `airport` = **91**. Identical 91 for `michelin` (no `michelin`), `visa` (no `visa`), `esim` (no `esim`).
- Cause: **90 identical generic destination posts** (`amalfi-coast-italy`, `amsterdam-netherlands`, `athens-greece`, …) are duplicated into 7 blogs; 90 shared + 1 blog-local = 91.

Shared non-guide corpus overlap with airports: `airlines` 90, `esim` 90, `flights` 90, `michelin` 90, `tour` 90, `visa` 90, `tours` 27, `trains` 23, all others 0. This duplicated set is the dominant mismatch driver, not per-blog title drift.

## Matrix

| blog | total | S1 fail | S1 pass | stage-2 tag | S2 fail | S2 pass | stage-3 kw | S3 fail | approved | mismatch | mismatch % | expected FP of approved |
|---|--:|--:|--:|---|--:|--:|---|--:|--:|--:|--:|--:|
| adventure-hugo | 154 | 154 | 0 | Adventure | 0 | 0 | adventure | 0 | 0 | 154 | 100.0% | n/a (0 approved) |
| airlines-hugo | 115 | 115 | 0 | Airline Review | 0 | 0 | airline | 0 | 0 | 115 | 100.0% | n/a (0 approved) |
| airports-hugo | 163 | 90 | 73 | Airport Guide | 55 | 18 | airport | 1 | 17 | 146 | 89.6% | ~0.075% |
| bus-hugo | 162 | 162 | 0 | Bus Travel | 0 | 0 | bus | 0 | 0 | 162 | 100.0% | n/a (0 approved) |
| citytours-hugo | 120 | 120 | 0 | City Tours | 0 | 0 | city tour | 0 | 0 | 120 | 100.0% | n/a (0 approved) |
| cruise-hugo | 111 | 83 | 28 | Shore Excursions | 13 | 15 | cruise | 0 | 15 | 96 | 86.5% | ~0.075% |
| culture-hugo | 167 | 167 | 0 | Culture Tours | 0 | 0 | culture | 0 | 0 | 167 | 100.0% | n/a (0 approved) |
| daytrips-hugo | 182 | 182 | 0 | Day Trips | 0 | 0 | day trip | 0 | 0 | 182 | 100.0% | n/a (0 approved) |
| deals-hugo | 105 | 105 | 0 | Flight Deals | 0 | 0 | deal | 0 | 0 | 105 | 100.0% | n/a (0 approved) |
| dining-hugo | 120 | 120 | 0 | Dining Guide | 0 | 0 | dining | 0 | 0 | 120 | 100.0% | n/a (0 approved) |
| escape-hugo | 102 | 102 | 0 | Escape Rooms | 0 | 0 | escape | 0 | 0 | 102 | 100.0% | n/a (0 approved) |
| esim-hugo | 265 | 265 | 0 | eSIM Guide | 0 | 0 | esim | 0 | 0 | 265 | 100.0% | n/a (0 approved) |
| eurail-hugo | 171 | 171 | 0 | European Rail | 0 | 0 | rail | 0 | 0 | 171 | 100.0% | n/a (0 approved) |
| extreme-hugo | 107 | 107 | 0 | Extreme Sports | 0 | 0 | extreme | 0 | 0 | 107 | 100.0% | n/a (0 approved) |
| ferry-hugo | 159 | 159 | 0 | Ferry Travel | 0 | 0 | ferry | 0 | 0 | 159 | 100.0% | n/a (0 approved) |
| flights-hugo | 272 | 272 | 0 | Flight Deals | 0 | 0 | flight | 0 | 0 | 272 | 100.0% | n/a (0 approved) |
| foodtour-hugo | 143 | 143 | 0 | Food Tours | 0 | 0 | food | 0 | 0 | 143 | 100.0% | n/a (0 approved) |
| ghost-hugo | 94 | 94 | 0 | Ghost Tours | 0 | 0 | ghost | 0 | 0 | 94 | 100.0% | n/a (0 approved) |
| hiking-hugo | 82 | 82 | 0 | Hiking Tours | 0 | 0 | hiking | 0 | 0 | 82 | 100.0% | n/a (0 approved) |
| layover-hugo | 99 | 99 | 0 | Layover Tours | 0 | 0 | layover | 0 | 0 | 99 | 100.0% | n/a (0 approved) |
| luxury-hugo | 112 | 112 | 0 | Luxury Tours | 0 | 0 | luxury | 0 | 0 | 112 | 100.0% | n/a (0 approved) |
| michelin-hugo | 272 | 272 | 0 | Michelin Guide | 0 | 0 | michelin | 0 | 0 | 272 | 100.0% | n/a (0 approved) |
| multiday-hugo | 163 | 163 | 0 | Multi-Day Tours | 0 | 0 | multi-day | 0 | 0 | 163 | 100.0% | n/a (0 approved) |
| nature-hugo | 110 | 110 | 0 | Nature Tours | 0 | 0 | nature | 0 | 0 | 110 | 100.0% | n/a (0 approved) |
| nightlife-hugo | 107 | 107 | 0 | Nightlife | 0 | 0 | nightlife | 0 | 0 | 107 | 100.0% | n/a (0 approved) |
| nomad-hugo | 39 | 0 | 39 | Digital Nomad | 9 | 30 | nomad | 29 | 1 | 38 | 97.4% | ~0.075% |
| phototour-hugo | 112 | 112 | 0 | Photography Tours | 0 | 0 | photo | 0 | 0 | 112 | 100.0% | n/a (0 approved) |
| tour-hugo | 254 | 90 | 164 | (none) | 164 | 0 | tour | 0 | 0 | 254 | 100.0% | n/a (0 approved) |
| tours-hugo | 204 | 204 | 0 | Tours & Activities | 0 | 0 | tour | 0 | 0 | 204 | 100.0% | n/a (0 approved) |
| trains-hugo | 145 | 145 | 0 | Route Guide | 0 | 0 | train | 0 | 0 | 145 | 100.0% | n/a (0 approved) |
| transfers-hugo | 162 | 162 | 0 | Airport Transfers | 0 | 0 | transfer | 0 | 0 | 162 | 100.0% | n/a (0 approved) |
| visa-hugo | 252 | 252 | 0 | Visa Guide | 0 | 0 | visa | 0 | 0 | 252 | 100.0% | n/a (0 approved) |
| visafree-hugo | 169 | 169 | 0 | Visa-Free Travel | 0 | 0 | visa | 0 | 0 | 169 | 100.0% | n/a (0 approved) |
| walking-hugo | 148 | 148 | 0 | Walking Tours | 0 | 0 | walking | 0 | 0 | 148 | 100.0% | n/a (0 approved) |
| watersports-hugo | 159 | 159 | 0 | Water Sports | 0 | 0 | water sports | 0 | 0 | 159 | 100.0% | n/a (0 approved) |
| watertours-hugo | 104 | 104 | 0 | Water Tours | 0 | 0 | water tour | 0 | 0 | 104 | 100.0% | n/a (0 approved) |
| **TOTAL (36)** | **5405** | **5101** | **304** | — | **241** | **63** | — | **30** | **33** | **5372** | **99.4%** | ~0.075% |

## Ungated stage-2/3 signal (diagnostic, no stage-1 gate)

Stage 1 rejects 94.4% of the corpus, which masks stage-2/3 behaviour. Applying stage 2 and stage 3 to the **full** per-blog corpus:

| blog | total | tag fail | tag fail % | title-kw fail | kw fail % |
|---|--:|--:|--:|--:|--:|
| adventure-hugo | 154 | 100 | 65% | 1 | 1% |
| airlines-hugo | 115 | 103 | 90% | 99 | 86% |
| airports-hugo | 163 | 145 | 89% | 91 | 56% |
| bus-hugo | 162 | 104 | 64% | 7 | 4% |
| citytours-hugo | 120 | 57 | 48% | 19 | 16% |
| cruise-hugo | 111 | 67 | 60% | 29 | 26% |
| culture-hugo | 167 | 113 | 68% | 82 | 49% |
| daytrips-hugo | 182 | 118 | 65% | 14 | 8% |
| deals-hugo | 105 | 65 | 62% | 0 | 0% |
| dining-hugo | 120 | 88 | 73% | 22 | 18% |
| escape-hugo | 102 | 44 | 43% | 7 | 7% |
| esim-hugo | 265 | 203 | 77% | 91 | 34% |
| eurail-hugo | 171 | 106 | 62% | 170 | 99% |
| extreme-hugo | 107 | 50 | 47% | 32 | 30% |
| ferry-hugo | 159 | 102 | 64% | 5 | 3% |
| flights-hugo | 272 | 253 | 93% | 179 | 66% |
| foodtour-hugo | 143 | 82 | 57% | 30 | 21% |
| ghost-hugo | 94 | 42 | 45% | 23 | 24% |
| hiking-hugo | 82 | 47 | 57% | 8 | 10% |
| layover-hugo | 99 | 43 | 43% | 10 | 10% |
| luxury-hugo | 112 | 47 | 42% | 2 | 2% |
| michelin-hugo | 272 | 199 | 73% | 91 | 33% |
| multiday-hugo | 163 | 106 | 65% | 6 | 4% |
| nature-hugo | 110 | 59 | 54% | 0 | 0% |
| nightlife-hugo | 107 | 48 | 45% | 36 | 34% |
| nomad-hugo | 39 | 9 | 23% | 34 | 87% |
| phototour-hugo | 112 | 64 | 57% | 0 | 0% |
| tour-hugo | 254 | 254 | 100% | 254 | 100% |
| tours-hugo | 204 | 129 | 63% | 133 | 65% |
| trains-hugo | 145 | 76 | 52% | 145 | 100% |
| transfers-hugo | 162 | 104 | 64% | 8 | 5% |
| visa-hugo | 252 | 184 | 73% | 91 | 36% |
| visafree-hugo | 169 | 105 | 62% | 106 | 63% |
| walking-hugo | 148 | 92 | 62% | 51 | 34% |
| watersports-hugo | 159 | 95 | 60% | 33 | 21% |
| watertours-hugo | 104 | 45 | 43% | 10 | 10% |
| **TOTAL** | **5405** | **3548** | **66%** | **1919** | **36%** |

## Expected FP rates

| Quantity | Value | Basis |
|---|--:|---|
| Stage-1 FP | ~5% | declared (IATA exceptions) |
| Stage-2 FP | ~10% | declared |
| Stage-3 FP | ~15% | declared |
| Residual FP of an approved post | **~0.075%** | 0.05 × 0.10 × 0.15, independence assumed |
| Approved posts across 36 blogs | **33** | measured |
| Expected false positives among them | **<1 post** (33×0.00075 = 0.025) | derived |
| False-negative rate of the gate | **99.4%** (5372/5405) | measured — dominated by stage 1 |

Only 4 blogs exercise the gate at all (`airports` 73, `tour` 164, `nomad` 39, `cruise` 28 stage-1 passers). For the other 32 blogs stage-1 pass = 0, so FP is undefined (nothing approved) and FN = 100%.

## Residual risk

- Stage 1 (`*-guide`) does not match 32 of 36 blogs' slug conventions (`*-adventure`, `*-by-bus`, `*-ferry`…). Applying this gate as-is would reject 5101/5405 posts. The FP math is sound; the recall is not.
- Stage-2 tags here are **derived** (modal non-generic `categories`), not owner-approved. `tour-hugo` has no non-generic category at all → tag `(none)` → 0 approved by construction.
- Stage-3 keywords are derived from blog names (`eurail`→`rail`, `phototour`→`photo`). `eurail` 170/171 and `trains` 145/145 title-kw failures are keyword-choice artifacts, not necessarily off-topic content.
- The declared 5/10/15% FP rates remain **unverified** — no labelled ground-truth set exists; independence between stages is assumed, not tested.
- The 90-post duplicated destination corpus in 7 blogs is a content-duplication defect that this gate detects but does not explain; deduplication is a separate action.
