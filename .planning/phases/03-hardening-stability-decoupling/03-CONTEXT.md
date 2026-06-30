# Phase 3: Hardening — Stability & Decoupling - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace 133 hardcoded `/Users/twinssn/...` paths with environment variables, audit error handling in central modules for consistency, and isolate external project dependencies (TAP, STAP, ETAP) behind clear interfaces.

Requirements: STB-02, STB-09, STB-10

</domain>

<decisions>
## Implementation Decisions

### Path Configuration Strategy
- **D-01:** Two-tier env loading: `~/.env.common` (shared/fallback) → `{PROJECT_ROOT}/.env` (project overrides)
- **D-02:** Place `5000_ROOT`, `STAP_ROOT`, `TAP_ROOT`, `ETAP_ROOT`, `LAP_ROOT`, `CUAP_ROOT` env vars in `~/.env.common`
- **D-03:** `5000_ROOT` defaults to `os.path.dirname(os.path.abspath(__file__))` root if unset
- **D-04:** Binary paths (`HUGO_PATH`, `WRANGLER_PATH`) as env vars with `which` fallback
- **D-05:** Central path resolver function (e.g., `shared/db_paths.py` or new `shared/paths.py`) — single source of truth for all paths

### Error Handling Audit
- **D-06:** Scope: `dispatcher.py`, `scheduler.py`, `shared/publisher.py` (central modules)
- **D-07:** Pattern: `logger.error(f"[{module_prefix}] {context}: {e}")` — module prefix + what failed + error
- **D-08:** Silent `except` allowed only for intentionally expected failures (quota checks, known API patterns)
- **D-09:** Every `except Exception:` (bare except) gets a specific exception type or a logged reason

### External Dependency Isolation
- **D-10:** On import failure: log clear error message (`"pip install/configure {project_name} required"`), skip affected blog only
- **D-11:** No hard startup failure — 5000 runs even if TAP/STAP/ETAP are missing
- **D-12:** Keep subprocess approach for TAP/STAP (no in-process import), just make paths configurable
- **D-13:** Wrapper functions in dispatcher.py with try/except at call site, not at import time

</decisions>

<canonical_refs>
## Canonical References

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — STB-02 (paths), STB-09 (errors), STB-10 (external deps)
- `.planning/ROADMAP.md` — Phase 3 success criteria and plans

### Current Code (paths to fix)
- `dispatcher.py:17` — TAP path
- `dispatcher.py:309` — tap_root hardcoded
- `dispatcher.py:382` — shared-themes path
- `shared/publisher.py:31-32` — STAP paths
- `shared/publishers/deploy.py` — hugo/wrangler binary paths
- `shared/publishers/content_enhancer.py:21-22` — STAP/TAP paths
- `shared/r2_uploader.py` — R2 endpoint env config (already partly env-driven)

### Prior Phases
- `.planning/phases/01-*/01-CONTEXT.md` — Phase 1 tooling decisions
- `.planning/phases/02-*/02-CONTEXT.md` — Phase 2 refactoring decisions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Patterns
- `shared/publisher.py:14` — Already has `load_dotenv(override=True)` pattern
- `dispatcher.py:19-23` — Already chains `.env.common` → project `.env`
- `shared/db_paths.py` — Existing path registry module, can extend it

### Integration Points
- All `/Users/twinssn/Projects/` references → env var `{PROJECT}_ROOT`
- All `/opt/homebrew/bin/hugo` → `HUGO_PATH` or `$PATH` resolution
- TAP entity manager import in `shared/publisher.py:44-48` → needs try/exist wrapper
- STAP content DB path in `shared/publishers/content_enhancer.py:21` → env var

</code_context>

<specifics>
## Specific Ideas

- Path resolver: function `project_root(name: str) -> str` that checks env var first, falls back to convention
- Error audit checklist: for each module, find all `except`, classify as "needs context" / "silent ok", fix
- External dep wrappers: `_try_tap()`, `_try_stap()` in dispatcher that catch import errors gracefully

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 3-Hardening — Stability & Decoupling*
*Context gathered: 2026-06-30*
