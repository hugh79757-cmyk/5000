# Roadmap: 5000

**3 phases** | **10 requirements mapped** | All v1 requirements covered ✓

## Phase 1: Foundation — Test & Tooling Infrastructure

**Goal:** Establish test framework, linting, CI pipeline, and verify Python 3.14 compatibility
**Mode:** mvp
**Requirements:** STB-01, STB-04, STB-05, STB-06

**Success Criteria:**
1. `pytest` runs with >70% coverage on shared/ modules
2. `ruff check .` passes with no errors
3. `mypy .` passes for shared/ and pipelines/
4. GitHub Actions runs lint + test on push
5. `check_package_imports()` removed from `dispatcher.py`

**Plans:**
1. Tooling & test infra — pytest, ruff, mypy config, CI workflow
2. Unit tests for shared modules — validators, humanizer, telegram_notifier

---

## Phase 2: Core Refactoring — Simplify Central Modules

**Goal:** Replace brittle routing in dispatcher, split monolith publisher, clean up backup pollution
**Mode:** mvp
**Requirements:** STB-07, STB-08, STB-03

**Success Criteria:**
1. New blogs require config entry only (no elif chain in dispatcher)
2. `shared/publisher.py` split into 3+ focused platform modules
3. Zero `.bak*` files in source directories
4. All existing pipelines still deploy correctly

**Plans:**
1. Dispatcher registry — dynamic pipeline lookup
2. Publisher decomposition — per-platform modules
3. Backup file cleanup

---

## Phase 3: Hardening — Stability & Decoupling

**Goal:** Eliminate hardcoded paths, consistent error handling, isolate external deps
**Mode:** mvp
**Requirements:** STB-02, STB-09, STB-10

**Success Criteria:**
1. Zero hardcoded absolute paths in source code
2. Every `except Exception` block logs actionable context
3. TAP/STAP/ETAP import failures produce clear error messages with upgrade instructions
4. All pipelines run from clean clone with env-only config

**Plans:**
1. Path configuration — env-driven project roots
2. Error handling audit — consistent patterns across all modules
3. External dependency isolation — interface wrappers

---

## Configuration

**Granularity:** Coarse (3 phases)
**Execution:** Parallel within phases
**Mode:** Vertical MVP (each phase delivers end-to-end improvement)
**Research:** Yes (before each phase)
**Plan Check:** Yes
**Verifier:** Yes
