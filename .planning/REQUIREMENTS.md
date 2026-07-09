# Requirements: 5000

**Defined:** 2026-06-30
**Last updated:** 2026-07-09 (code-audited)
**Core Value:** Pipelines run reliably with clear errors when they don't

## v1 Requirements

### Stability

- [x] **STB-01**: Central modules (validators, humanizer, telegram_notifier) have unit tests covering core logic
- [ ] **STB-02**: Hardcoded absolute paths (`/Users/twinssn/...`) are replaced with env vars or config
- [x] **STB-03**: All `.bak*` files cleaned from source directories; `.gitignore` covers all backup variants
- [x] **STB-04**: ruff (linting) and mypy (type checking) configured and passing for all Python source
- [x] **STB-05**: Python 3.14 compatibility verified — `check_package_imports()` removed from startup
- [ ] **STB-06**: GitHub Actions CI runs lint + test on every push to main (CI was removed — Phase 6+7)

### Architecture

- [x] **STB-07**: `dispatcher.py` blog-id-to-pipeline routing replaced with dynamic registry pattern
- [x] **STB-08**: `shared/publisher.py` split into focused per-platform modules
- [x] **STB-09**: Error handling produces actionable messages — no silent `except Exception: pass`
- [x] **STB-10**: External project coupling (TAP, STAP, ETAP) isolated behind import-time interfaces with clear fallbacks

## v2 Requirements

- [x] **STB-11**: Launchd plist for scheduler auto-restart on crash
- [x] **STB-12**: Log aggregation and rotation (structlog 도입은 안 됐지만 log_aggregator 구현됨)
- [ ] **STB-13**: Config schema validation for blogs.yaml and prompts.yaml

## Out of Scope

| Feature | Reason |
|---------|--------|
| Tech stack changes | Python/Hugo/Cloudflare stays as-is |
| Greenfield rewrite | Refactoring existing code, not replacing it |
| New blog pipelines | Only stabilizing existing ones |
| Database migration framework | Too heavy for SQLite-per-pipeline model |

## Traceability (Actual Status)

| Requirement | Phase | Status | Note |
|-------------|-------|--------|------|
| STB-01 | Phase 1 | ✅ Done | Unit tests exist for validators/humanizer/telegram |
| STB-04 | Phase 1 | ✅ Done | ruff + mypy configured |
| STB-05 | Phase 1 | ✅ Done | check_package_imports removed |
| STB-06 | Phase 1 | ❌ Removed | CI workflow 제거됨 (Phase 6+7: PR trigger만 남음) |
| STB-07 | Phase 2 | ✅ Done | dispatcher registry pattern |
| STB-08 | Phase 2 | ✅ Done | publisher 분할 완료 |
| STB-03 | Phase 2 | ✅ Done | .bak cleanup |
| STB-02 | Phase 3 | ❌ Open | 여전히 hardcoded path 존재 (`/Users/twinssn/...`) |
| STB-09 | Phase 3 | ✅ Done | Error handling audit 완료 |
| STB-10 | Phase 3 | ✅ Done | TAP/STAP/ETAP isolation |
| STB-11 | Phase 6+7 | ✅ Done | launchd plist 등록 |
| STB-12 | Phase 6+7 | ✅ Done | log_aggregator + metrics |
| STB-13 | — | ❌ Open | Config validation 없음 |

**Coverage:**
- v1 requirements: 10 total
- Complete: 7
- Open: 2 (STB-02 hardcoded paths, STB-06 CI)
- Partial: 1 (STB-13 config validation)
