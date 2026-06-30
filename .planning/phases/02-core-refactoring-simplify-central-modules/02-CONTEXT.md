# Phase 2: Core Refactoring — Simplify Central Modules - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the brittle elif-chain in dispatcher.py with a dynamic registry, decompose the 952-line publisher.py into focused modules, and clean up 50+ backup files polluting source directories.

Requirements: STB-07, STB-08, STB-03

</domain>

<decisions>
## Implementation Decisions

### Dispatcher Registry
- **D-01:** Dynamic import from config — blog_id → module path mapping in blogs.yaml, dispatcher uses `importlib.import_module()` 
- **D-02:** Keep STAP/TAP subprocess isolation and deploy logic in dispatcher.py (minimize diff)
- **D-03:** Convention-based ETAP naming — blog_id 'flights-hugo' maps to `pipelines.etap.flight_pipeline` (strip -hugo suffix, derive module name)
- **D-04:** Same `run(cfg)` or `run()` call pattern preserved for backward compat

### Publisher Decomposition
- **D-05:** Split by concern into `shared/publishers/` package:
  - `shared/publishers/hugo_writer.py` — frontmatter building + post writing
  - `shared/publishers/deploy.py` — site deployment
  - `shared/publishers/content_enhancer.py` — related cards, coupang, internal links
- **D-06:** Keep original `shared/publisher.py` as re-export hub to avoid breaking existing imports

### Backup File Cleanup
- **D-07:** Delete all `.bak*`/`.bak_*`/`*.v1_bak`/`*.fix_bak`/`*-bak`/`.feat-bak`/`.dedup-bak` files from source directories
- **D-08:** Harden `.gitignore` with comprehensive backup file patterns
- **D-09:** Use cleanup script with dry-run preview before executing deletions

### Safety Net
- **D-10:** Write integration test that captures current blog_id → module mapping, then verifies new registry returns same results
- **D-11:** Add CI step to verify registry resolves all known blog IDs

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — STB-07 (dispatcher), STB-08 (publisher), STB-03 (bak cleanup)
- `.planning/ROADMAP.md` — Phase 2 success criteria and plans

### Current Code
- `dispatcher.py` — Lines 262-430: the elif/if chain to replace
- `shared/publisher.py` — 952 lines, 20+ functions to split
- `.planning/codebase/CONCERNS.md` — Identified fragile areas (monolithic files, elif chain)

### Prior Phase
- `.planning/phases/01-foundation-test-tooling-infrastructure/01-CONTEXT.md` — Phase 1 decisions (tooling, testing patterns)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Patterns
- `dispatcher.py:54-62` — Already has `STAP_PIPELINE_MAP` dict for stock blogs. This pattern can be generalized.
- `dispatcher.py:440-450` — `ETAP_PIPELINE_BLOGS` set with all 35 blog IDs. This is a manually curated list — ideal for convention-based derivation.

### Integration Points
- blogs.yaml config needs `module_path` or derived field for each blog
- New registry function `_resolve_pipeline(blog_id, pipeline_name)` that returns the `run` function
- Keep `_run_stap()`, `_run_pipeline()`, `_build_and_deploy_central()` signatures intact

### Testing Strategy
- Existing test infrastructure from Phase 1: pytest, 42 existing tests
- New test: `tests/test_dispatcher_registry.py` — map all known blog IDs to modules

</code_context>

<specifics>
## Specific Ideas

- Registry structure: `PIPELINE_REGISTRY = {"pipeline_name": "pipelines.{name}.pipeline"}` in blogs.yaml, or convention-based: `pipelines/{pipeline_name}/pipeline.py` with `run(cfg)` entry point
- ETAP: strip `-hugo` from blog_id, map `flights` → `pipelines.etap.flight_pipeline` (note: flights → flight, singular/plural convention)
- Backup cleanup: `find . -name '*.bak*' -o -name '*.v1_bak' -o -name '*.fix_bak'` etc., verify with dry-run first

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 2-Core Refactoring — Simplify Central Modules*
*Context gathered: 2026-06-30*
