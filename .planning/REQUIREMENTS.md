# Requirements: 5000

**Defined:** 2026-06-30
**Core Value:** Pipelines run reliably with clear errors when they don't

## v1 Requirements

### Stability

- [ ] **STB-01**: Central modules (validators, humanizer, telegram_notifier) have unit tests covering core logic
- [ ] **STB-02**: Hardcoded absolute paths (`/Users/twinssn/...`) are replaced with env vars or config
- [ ] **STB-03**: All `.bak*` files cleaned from source directories; `.gitignore` covers all backup variants
- [ ] **STB-04**: ruff (linting) and mypy (type checking) configured and passing for all Python source
- [ ] **STB-05**: Python 3.14 compatibility verified — `check_package_imports()` removed from startup
- [ ] **STB-06**: GitHub Actions CI runs lint + test on every push to main

### Architecture

- [ ] **STB-07**: `dispatcher.py` blog-id-to-pipeline routing replaced with dynamic registry pattern
- [ ] **STB-08**: `shared/publisher.py` split into focused per-platform modules
- [ ] **STB-09**: Error handling produces actionable messages — no silent `except Exception: pass`
- [ ] **STB-10**: External project coupling (TAP, STAP, ETAP) isolated behind import-time interfaces with clear fallbacks

## v2 Requirements

- **STB-11**: Launchd plist for scheduler auto-restart on crash
- **STB-12**: Log aggregation and rotation (structured logging via `structlog` or stdlib)
- **STB-13**: Config schema validation for blogs.yaml and prompts.yaml

## Out of Scope

| Feature | Reason |
|---------|--------|
| Tech stack changes | Python/Hugo/Cloudflare stays as-is |
| Greenfield rewrite | Refactoring existing code, not replacing it |
| New blog pipelines | Only stabilizing existing ones |
| Database migration framework | Too heavy for SQLite-per-pipeline model |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| STB-01 | Phase 1 | Pending |
| STB-04 | Phase 1 | Pending |
| STB-05 | Phase 1 | Pending |
| STB-06 | Phase 1 | Pending |
| STB-07 | Phase 2 | Pending |
| STB-08 | Phase 2 | Pending |
| STB-03 | Phase 2 | Pending |
| STB-02 | Phase 3 | Pending |
| STB-09 | Phase 3 | Pending |
| STB-10 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-30*
*Last updated: 2026-06-30 after initial definition*
