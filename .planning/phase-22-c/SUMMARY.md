# Phase 22-C: Funnel Card Implementation (v2 Rewrite) — Summary

**Date:** 2026-07-20
**Status:** ✓ Complete
**Approach:** 전면 재작성 (complete rewrite of v1 plan)

## What Was Wrong with v1

The v1 plan was written against an imagined pre-execution state. Implementation already existed but had 4 critical flaws discovered during plan-check:

1. **BS4 undeclared in requirements.txt** — silent-skip failure mode on fresh installs
2. **Double Hugo build** — funnel function ran Hugo build, then deploy.py ran it again
3. **Batch publish wipes prior posts' cards** — Hugo rebuild in funnel function overwrites HTML cards injected into prior posts' `public/posts/{slug}/index.html`
4. **Korean keyword filter ineffective** — whitespace tokenization + stopword removal can't handle agglutinative Korean; threshold=0.15 produced false negatives

## What v2 Changed (3 Waves)

### Wave 1 — Declare BS4 dependency
- Added `beautifulsoup4>=4.12.0` to `requirements.txt`
- BS4 already used by `car/daily_refresh.py`, `stock/fetcher.py`, `diningcode_enricher.py` — was undeclared

### Wave 2 — Migrate injection from HTML-level back to markdown-level
- Replaced `_build_and_inject_funnel_cards()` with `_build_funnel_cards_md(blog_cfg, body_md) -> (body_md, counts)`
- Removed: Hugo build call, BeautifulSoup HTML parsing, file I/O on `public/posts/{slug}/index.html`
- New flow: inject raw HTML cards INTO `body_md` before `content = fm + body_md`
- Hugo Goldmark passes raw HTML through unchanged (proven by existing posts)
- Fixes both double-build (Issue 2) and batch-wipe (Issue 3)
- Removed dead BS4 import block from `hugo_writer.py` (BS4 no longer used there)

### Wave 3 — Disable broken Korean filter
- Changed `_keywords_overlap_check()` default `threshold=0.15` → `threshold=0.0`
- Filter now passes all bridge cards (safer default until konlpy integration)
- Marked with `ponytail:` comment explaining deferral

## Files Changed

| File | Change |
|------|--------|
| `requirements.txt` | +1 line (beautifulsoup4) |
| `shared/publishers/hugo_writer.py` | Replaced `_build_and_inject_funnel_cards()` with `_build_funnel_cards_md()` (smaller); updated call site in `_write_hugo_post()`; removed BS4 import block; threshold=0.0 |

**Net code reduction:** ~50 lines removed (Hugo build + HTML parsing + file I/O logic), ~40 lines added (markdown-level injection).

## Out of Scope (Deferred)

- **ETAP 10 pipelines** — each has own `_write_hugo_post()`, bypasses funnel. Separate refactor.
- **Korean morpheme analyzer** (konlpy) — needed for real keyword filtering. Separate phase.
- **AI/LLM 2nd-stage context check** — speculative, YAGNI.

## Verification Results

```
[PASS] requirements.txt has beautifulsoup4
[PASS] _build_funnel_cards_md exists, _build_and_inject_funnel_cards removed
[PASS] _write_hugo_post calls _build_funnel_cards_md before content=fm+body_md
[PASS] No subprocess.run([HUGO_PATH...]) in funnel function
[PASS] threshold=0.0 default
[PASS] BS4 dead import removed from hugo_writer.py
[PASS] Module imports cleanly
[PASS] publisher.py still imports _write_hugo_post
```

## Key Design Insight

v1 chose HTML-level injection for "rich card templates" but Hugo's Goldmark renderer passes raw HTML in markdown through unchanged. Markdown-level injection achieves the same visual result while fixing 3 bugs (double build, batch wipe, BS4 dependency in critical path) with less code. The shortest path to done.
