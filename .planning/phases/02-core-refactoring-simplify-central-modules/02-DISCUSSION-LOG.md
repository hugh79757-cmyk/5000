# Phase 2: Core Refactoring — Simplify Central Modules - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-30
**Phase:** 2-Core Refactoring — Simplify Central Modules
**Areas discussed:** Dispatcher Registry, Publisher Decomposition, Backup File Cleanup, Safety Net

---

## Dispatcher Registry

| Option | Description | Selected |
|--------|-------------|----------|
| Dynamic import from config | blog_id → module path in blogs.yaml, importlib | ✓ |
| Decorator-based | Each pipeline registers itself | |
| Package manifest | pipelines/__init__.py with dict | |

**User's choice:** Dynamic import from config

| Option | Description | Selected |
|--------|-------------|----------|
| Keep in dispatcher.py | Leave deploy/subprocess as-is | ✓ |
| Extract deploy | Move build_and_deploy out | |

**User's choice:** Keep in dispatcher.py

| Option | Description | Selected |
|--------|-------------|----------|
| Convention-based naming | Derive module from blog_id (strip -hugo) | ✓ |
| Explicit mapping in blogs.yaml | module_path field | |

**User's choice:** Convention-based naming (strip -hugo suffix)

---

## Publisher Decomposition

| Option | Description | Selected |
|--------|-------------|----------|
| By concern | hugo_writer + deploy + content_enhancer | ✓ |
| By platform | hugo + blogger + wordpress | |
| Minimal | Extract deploy only | |

**User's choice:** By concern into shared/publishers/ package

| Option | Description | Selected |
|--------|-------------|----------|
| shared/publishers/ package | Clean namespace | ✓ |
| shared/ flat files | Simpler | |

**User's choice:** shared/publishers/ package

| Option | Description | Selected |
|--------|-------------|----------|
| Re-export hub | publisher.py re-exports from submodules | ✓ |
| Update all imports | Change every import site | |

**User's choice:** publisher.py as re-export hub

---

## Backup File Cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| Delete all | Remove all .bak* files | ✓ |
| Archive | Move to data/backups/ | |
| Update gitignore only | Don't delete existing | |

**User's choice:** Delete all

| Option | Description | Selected |
|--------|-------------|----------|
| Script + dry-run | Write script, preview, execute | ✓ |
| Manual | find | grep manually | |

**User's choice:** Script + dry-run

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, harden gitignore | Add all backup variants | ✓ |
| Keep current | Just delete | |

**User's choice:** Yes, harden .gitignore comprehensively

---

## Safety Net

| Option | Description | Selected |
|--------|-------------|----------|
| Integration test | Capture current mapping, verify new registry | ✓ |
| Manual checklist | Test each pipeline manually | |
| Skip | Trust the refactor | |

**User's choice:** Integration test with current fixtures

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — test in CI | CI step verifies registry | ✓ |
| Manual only | Local verification | |

**User's choice:** Yes, test in CI

---

## the agent's Discretion

None — all decisions were explicitly made by the user.
