# Phase 1: Foundation — Test & Tooling Infrastructure - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish test framework (pytest), linting (ruff), type checking (mypy), and CI pipeline (GitHub Actions) for the 5000 codebase, and write initial unit tests for the three core shared modules. Verify Python 3.14 compatibility and remove the startup compatibility check.

Requirements: STB-01, STB-04, STB-05, STB-06

</domain>

<decisions>
## Implementation Decisions

### Test Tooling
- **D-01:** Single `pyproject.toml` for pytest, ruff, and mypy configuration
- **D-02:** Minimal plugins — pytest + pytest-cov only (no pytest-mock or pytest-asyncio)
- **D-03:** `tests/` directory at repo root, mirroring source layout
- **D-04:** `pytest` added to `requirements.txt`

### Coverage Scope
- **D-05:** First test targets: `shared/validators.py`, `shared/humanizer.py`, `shared/telegram_notifier.py` (as specified in STB-01)
- **D-06:** Per-module minimum 70% coverage threshold
- **D-07:** CI fails if any tested module drops below 70%

### Linting
- **D-08:** Ruff with all rules enabled, per-file ignores where needed
- **D-09:** Auto-fix mode: check + unsafe-fix (fix what's safe, flag the rest)

### CI Workflow
- **D-10:** Separate `ci.yml` workflow from existing `indexnow.yml`
- **D-11:** Trigger: on push to `main` branch
- **D-12:** Steps: ruff check → mypy check → pytest with coverage

### Type Checking
- **D-13:** Mypy in strict mode (`--strict`)
- **D-14:** Scope: `shared/`, `dispatcher.py`, `scheduler.py` (central modules)
- **D-15:** Config in `pyproject.toml` under `[tool.mypy]`

### Python 3.14 Compatibility
- **D-16:** Remove `check_package_imports()` from `dispatcher.py` startup
- **D-17:** Verify all `requirements.txt` packages work on Python 3.14 (pytest will catch import issues)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — STB-01 (unit tests), STB-04 (linting), STB-05 (Python 3.14 compat), STB-06 (CI)
- `.planning/ROADMAP.md` — Phase 1 success criteria and plan structure

### Project Context
- `.planning/PROJECT.md` — Core value, constraints, overall vision
- `.planning/STATE.md` — Current project state

### Codebase Maps
- `.planning/codebase/TESTING.md` — Current testing state (no tests exist, CI has no test step)
- `.planning/codebase/CONVENTIONS.md` — Existing code patterns, naming, error handling style
- `.planning/codebase/STRUCTURE.md` — Directory layout, key file locations

### Existing Files That Will Be Modified
- `requirements.txt` — Add pytest and pytest-cov
- `dispatcher.py` — Remove `check_package_imports()`
- `.github/workflows/indexnow.yml` — Keep as-is (separate)
- `pyproject.toml` — Create with pytest, ruff, mypy config

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.planning/codebase/` — 7 codebase map documents already written with detailed analysis
- `scripts/test_sigungu_check.py`, `scripts/test_sigungu_distribution.py` — Existing manual test scripts (not pytest, but show test patterns)

### Established Patterns
- Python 3.14 runtime, `requirements.txt` for deps, `dotenv` for env vars
- `try/except` with `logger.error()` throughout — tests should verify these patterns
- Shared modules are modular and importable — good for unit testing

### Integration Points
- `.github/workflows/` — New `ci.yml` alongside existing `indexnow.yml`
- Config in `pyproject.toml` at repo root (new file)
- `pytest` and `pytest-cov` added to `requirements.txt`

</code_context>

<specifics>
## Specific Ideas

- Test files should mirror source: `tests/shared/test_validators.py`, `tests/shared/test_humanizer.py`, `tests/shared/test_telegram_notifier.py`
- `conftest.py` at `tests/` root for shared fixtures if needed
- `--strict` mypy mode may require many `# type: ignore` comments on existing code — acceptable for first pass

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 1-Foundation — Test & Tooling Infrastructure*
*Context gathered: 2026-06-30*
