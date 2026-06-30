# Phase 1: Foundation — Test & Tooling Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-30
**Phase:** 1-Foundation — Test & Tooling Infrastructure
**Areas discussed:** Test Tooling Choice, Coverage Scope & Targets, Linting Rules, CI Workflow Design, Type Checking Scope

---

## Test Tooling Choice

| Option | Description | Selected |
|--------|-------------|----------|
| pyproject.toml | Single pyproject.toml for pytest, ruff, mypy — idiomatic modern Python | ✓ |
| Separate config files | Traditional pytest.ini, .ruff.toml, mypy.ini | |

**User's choice:** pyproject.toml

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: pytest + pytest-cov | Core only | ✓ |
| Standard: + pytest-mock | Add pytest-mock | |
| Full: + pytest-mock, pytest-asyncio | Add asyncio support | |

**User's choice:** Minimal: pytest + pytest-cov

| Option | Description | Selected |
|--------|-------------|----------|
| tests/ at root | All tests in top-level tests/ | ✓ |
| tests/ per module | tests/ inside each pipeline and shared/ | |

**User's choice:** tests/ at root

---

## Coverage Scope & Targets

| Option | Description | Selected |
|--------|-------------|----------|
| Those three only | validators.py, humanizer.py, telegram_notifier.py as specified | ✓ |
| Add content_store.py | Also test SQLite CRUD | |
| Add all small shared modules | Any shared module under 300 lines | |

**User's choice:** Those three only

| Option | Description | Selected |
|--------|-------------|----------|
| Per-module minimum | Each tested module >=70% | ✓ |
| Aggregate across shared/ | Total >=70% | |

**User's choice:** Per-module minimum

| Option | Description | Selected |
|--------|-------------|----------|
| CI failure | Fails if below threshold | ✓ |
| Report only | Advisory only | |

**User's choice:** CI failure

---

## Linting Rules

| Option | Description | Selected |
|--------|-------------|----------|
| All rules | Full ruff ruleset | ✓ |
| Standard: E, F, I, N, W | Common default | |
| Minimal: E, F | Errors and pyflakes | |

**User's choice:** All rules

| Option | Description | Selected |
|--------|-------------|----------|
| Check + unsafe-fix | Fix safe, flag rest | ✓ |
| Check only | No auto-fix | |
| Full auto-fix | Fix everything | |

**User's choice:** Check + unsafe-fix

---

## CI Workflow Design

| Option | Description | Selected |
|--------|-------------|----------|
| On push to main | Keeps existing pattern | ✓ |
| On PR + push | More coverage | |
| On any branch | Maximum coverage | |

**User's choice:** On push to main

| Option | Description | Selected |
|--------|-------------|----------|
| Separate workflow | New ci.yml | ✓ |
| Merge into indexnow.yml | Single workflow | |

**User's choice:** Separate workflow

---

## Type Checking Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Strict | --strict mode | ✓ |
| Standard | disallow_untyped_defs | |
| Lenient | Basic checks | |

**User's choice:** Strict

| Option | Description | Selected |
|--------|-------------|----------|
| shared/ + dispatcher.py + scheduler.py | Central modules | ✓ |
| All Python files | Everything | |
| shared/ only | Library modules | |

**User's choice:** shared/ + dispatcher.py + scheduler.py

---

## the agent's Discretion

None — all decisions were explicitly made by the user.

## Deferred Ideas

None — discussion stayed within phase scope.
