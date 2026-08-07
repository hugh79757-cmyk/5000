# Phase 61: Pipeline Standardization & Branch Renewal - Research

**Researched:** 2026-08-07
**Domain:** Multi-branch Python pipeline standardization / refactor (additive, non-destructive)
**Confidence:** HIGH (code-verified against current working tree)

## Summary

Phase 61 standardizes 7 pipeline branches (car, curation, etap, rap, senior, travel, stock) that have drifted into divergent module skeletons, config schemas, `run()` contracts, and DB paths. The CONTEXT.md locked decisions (D-01 module skeleton, D-02 `PIPELINE-STANDARD.md` doc, D-03 `shared/subprocess_runner.py`, D-04 config schema unification, D-05 `scripts/scaffold_branch.py`, D-06 `shared/db.py`, D-07 staged A→B→C(SEAP/RAP pilot)→D rollout, D-08 incremental-compat) are all **additive** — this research confirms the current-state gaps those decisions target.

**Primary recommendation:** Because every change is additive and the scheduler + dispatcher already normalize results via `dispatcher.py:dispatch()`, the safest migration is: (1) freeze a written standard in `docs/PIPELINE-STANDARD.md`, (2) ship pure-additive helper modules first (`shared/db.py`, `shared/subprocess_runner.py`, `scripts/scaffold_branch.py`), (3) pilot a single low-traffic branch (SEAP/senior or RAP/rap — both `run(cfg)→dict` native, `managed_by: pipeline`, 2–5 blogs), then roll out. ETAP is the **highest-risk** branch (36 config entries, 35 topic pipelines, mixed `run()`/`run(cfg)` signatures) and must be deferred to stage D.

Two measured contract hazards require explicit planner attention:
1. **ETAP run() signature divergence** — 21 topic pipelines define `run() -> bool`; 14 define `run(cfg)`. Dispatcher handles both via `inspect.signature` at `dispatcher.py:463-465`, but the mixed contract is undocumented and unnormalized at the module level.
2. **Unregistered reason keys** — pipelines emit 11+ reason strings (`daily_quota_reached`, `expired_service`, `generation_failed`, `language_error`, `no_subscription_data`, `no_topic`, `no_topics`, `no_trade_data`, `prompt_not_found`, `publish_failed`, `write_failed`) that are **not** in `shared/problem_registry.py`'s P01–P24 `reason_keys`. They currently fall through to `unknown_failure`, so alerting is lossy. The standard must enumerate a closed reason-key vocabulary.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 — 표준 파이프라인 모듈 스켈레톤:** all pipelines conform to: `pipeline.py` / `fetcher` / `topic_manager` / `writer` / `enrich` / `validator`. Modules already present are kept and wired to the skeleton; absent modules are added as thin wrappers that delegate to existing shared/ code — nothing existing is removed.
- **D-02 — `docs/PIPELINE-STANDARD.md`:** written standard (contracts, skeleton, config schema, reason vocabulary, run() return contract) as the canonical reference.
- **D-03 — `shared/subprocess_runner.py`:** centralizes the duplicated subprocess isolation logic (STAP `_run_stap` + TAP `_run_tap_subprocess` + ETAP external-run paths) into one module.
- **D-04 — 통합 파이프라인 설정 스키마:** `config/blogs.d/*.yaml` unified onto one schema; branch-specific keys preserved via optional/extension fields; `managed_by: pipeline` is the standardized managed mode.
- **D-05 — `scripts/scaffold_branch.py`:** new-branch scaffolding from the standard skeleton to prevent future divergence.
- **D-06 — `shared/db.py`:** centralized DB-path + connection helper; branches keep their own DB files (no consolidation of data), only path/connection code is centralized.
- **D-07 — 단계적 전환 (stage A→B→C→D):** A=write standard, B=shared modules, C=pilot on SEAP/RAP (2+5 low-traffic branches), D=rollout to remaining (car, curation, travel, stock, ETAP last). Rollout is incremental-compat, never all-or-nothing.
- **D-08 — 증분 호환 / 비파괴 원칙:** additive-only; break nothing that works; existing green tests stay green; behavior changes and structure changes land in separate commits.

### the agent's Discretion
- Exact module-file contents for the thin wrapper modules (they must delegate to existing code, per D-01).
- Ordering of the sub-steps within each stage as long as A→B→C→D ordering is preserved.
- Whether `shared/subprocess_runner.py` returns dict-shaped results or reuses the existing `dispatcher.py:dispatch()` normalization (recommend: reuse).

### Deferred Ideas (OUT OF SCOPE)
- Physically merging TAP/STAP into the 5000 tree (external projects stay subprocess-isolated — only the **contract** is aligned, `shared/subprocess_runner.py`).
- Migrating/dispersing per-pipeline SQLite DB files (D-06 explicitly keeps DBs in place).
- Renaming blog IDs, AdSense Publisher IDs, domain families, or any runtime identifiers (deferred / out of scope).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| (from D-01) Standard skeleton | All 7 pipelines conform to pipeline/fetcher/topic_manager/writer/enrich/validator | Module-skeleton audit below maps each branch's current modules onto the target skeleton |
| (from D-03) subprocess runner | One shared module for STAP/TAP subprocess isolation | `_run_stap` L380 + `_run_tap_subprocess` L504 both build tempfile runners — consolidation target |
| (from D-04) Unified config schema | `blogs.d/*.yaml` on one schema | Config-schema disparity table below |
| (from D-06) Central DB helper | `shared/db.py` for path+connection | `shared/db_paths.py` exists but is bypassed by inline per-branch `*_DB_PATH` constants |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pipeline execution (run contract) | API / Backend (pipeline modules) | Dispatcher (orchestration) | `run(cfg)` is the per-branch entry; dispatcher normalizes + serializes |
| Subprocess isolation (STAP/TAP) | API / Backend (external projects) | `shared/subprocess_runner.py` (new) | External venv isolation lives at the 5000 boundary |
| Config schema / validation | API / Backend (config layer) | — | `blogs.d/*.yaml` parsed by dispatcher; schema must be single-source |
| DB path/connection | Database / Storage | `shared/db.py` (new) | Paths centralized; data stays per-DB |
| Deployment (Hugo/wrangler) | CDN / Static | `shared/publishers/deploy.py` | Already converged in Phase 59; NOT in Phase 61 scope |

## Standard Stack

This phase is **pure refactor** — it introduces **no new third-party dependencies** and installs no external packages. All work is additive restructuring of existing stdlib-only modules (json, subprocess, tempfile, sqlite3, inspect, importlib). The "stack" is the existing project stack:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `sqlite3` | 3.14.6 | DB path/connection helper | Already the DB layer everywhere |
| Python stdlib `subprocess`/`tempfile` | 3.14.6 | Subprocess runner | Already the isolation mechanism in dispatcher |
| Python stdlib `inspect`/`importlib` | 3.14.6 | Dynamic pipeline resolution | Already used at `dispatcher.py:462-463,456-465` |
| `yaml` (PyYAML) | ^6.0.1 | Config parse + scaffold | Config layer |
| `dotenv` | ^1.0.1 | env loading in runners | Used by STAP/TAP runners already |

**Version verification:** No new packages to verify — the phase relies entirely on existing stdlib + already-installed project deps. **No `npm install` / `pip install` required.**

## Package Legitimacy Audit

> **Not applicable — this phase installs zero external packages.** All work reuses stdlib modules and packages already present in `requirements.txt`. No slopcheck gate required. The planner must NOT add any package-install task to this phase.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                        ┌─────────────────────────────────────────────┐
                        │              scheduler.py (launchd)          │
                        │   reads blogs.d/*.yaml → dispatcher.py       │
                        └──────────────────┬──────────────────────────┘
                                           │ run_publish(blog_id)
                                           ▼
                        ┌─────────────────────────────────────────────┐
                        │            dispatcher.py:dispatch()          │
                        │  _resolve_pipeline()  +  _build_and_deploy() │
                        │  (normalizes bool→dict, records failure)     │
                        └───────┬─────────────────────────┬───────────┘
                                │ in-process              │ subprocess (isolated)
                                ▼                         ▼
        ┌───────────────────────────────┐   ┌─────────────────────────────┐
        │ pipelines.{branch}.pipeline    │   │  shared/subprocess_runner.py │
        │   run(cfg) → dict             │   │  (NEW: STAP/TAP/TAP-style)    │
        │   [standardize contract]      │   │    → external .venv python    │
        └───────────────┬───────────────┘   └───────────────┬─────────────┘
                        │                                   │
                        ▼                                   ▼
        ┌───────────────────────────────┐   ┌─────────────────────────────┐
        │  shared/publishers/hugo_writer │   │ STAP pipelines/{p}.pipeline  │
        │  (Phase-59 converged)          │   │ TAP app.run_publish()        │
        └───────────────┬───────────────┘   └───────────────┬─────────────┘
                        │                                   │ dict contract aligned
                        ▼                                   ▼
        ┌───────────────────────────────┐   ┌─────────────────────────────┐
        │  deploy.py (Phase-59)         │   │  data/*.db (per-branch)      │
        │  Hugo build + wrangler        │   │  path via shared/db.py (NEW) │
        └───────────────────────────────┘   └─────────────────────────────┘

        Config: config/blogs.d/*.yaml ──[unified schema D-04]──► dispatcher
        Standard: docs/PIPELINE-STANDARD.md ──[D-02, canonical]──► all modules
```

**Data flow (primary use case):** scheduler → dispatcher `_resolve_pipeline` → `run(cfg)` → (optional) subprocess isolation → publish via shared/hugo_writer → deploy via shared/deploy.py → result dict → dispatch() normalizes → recorded/logged. Phase 61 adds: standard run contract, central DB path, central subprocess runner — all upstream of publish/deploy, none touching deployed output.

### Recommended Project Structure (Phase 61 additions only)
```
5000/
├── docs/
│   └── PIPELINE-STANDARD.md          # NEW (D-02) canonical standard
├── shared/
│   ├── db.py                         # NEW (D-06) central DB path+connection helper
│   ├── subprocess_runner.py          # NEW (D-03) STAP/TAP isolation runner
│   └── db_paths.py                   # EXISTS — extend, don't replace
├── scripts/
│   └── scaffold_branch.py            # NEW (D-05) branch scaffolding
└── pipelines/
    ├── senior/                       # PILOT (stage C) — run(cfg) native, managed_by=pipeline
    ├── rap/                          # PILOT (stage C) — run(cfg) native
    ├── car/  curation/ travel/       # stage D rollout
    └── etap/                         # stage D, HIGHEST RISK (36 cfg / 35 topic pipelines)
```

### Pattern 1: Dynamic pipeline resolution with signature-aware run() dispatch
**What:** Dispatcher dynamically imports `pipelines.{pipeline}.pipeline` and calls `run(cfg)` — but ETAP topic modules expose mixed `run()`/`run(cfg)`. `inspect.signature` at `dispatcher.py:463-465` already bridges this.
**When to use:** The standard run contract MUST be `run(cfg) -> dict` for all standardized pipelines. ETAP's `run()` (bool-returning) topic modules are the exception to be normalized in stage D.
**Example (existing, at `dispatcher.py:462-465`):**
```python
import inspect
if "cfg" in inspect.signature(run).parameters or len(inspect.signature(run).parameters) > 0:
    return run(cfg)
return run()
```

### Anti-Patterns to Avoid
- **Rewriting pipeline bodies during standardization:** Violates D-08 additive principle. Wrap/detect; never rewrite working generation logic.
- **Removing `.bak` files or refactoring pre-existing dead code:** Out of scope for this phase. `.bak` files (59 total) are report-only here.
- **Consolidating DB data:** D-06 explicitly keeps per-pipeline DB files. Only path/connection code centralizes.
- **Deploying via raw wrangler:** Per global rule + deployment rules, ALL deploys go through `dispatcher.py` / `deploy.py` (CLOUDFLARE_API_TOKEN removal, Worker/Pages auto-selection, serialization lock). Never hand-run `wrangler deploy`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Run-contract normalization (bool→dict, None→{success:False}) | Per-branch result shims | `dispatcher.py:dispatch()` (existing L740) + standard dict contract | Already handles `isinstance(result, bool)` and `no_result` backoff/cooldown |
| Subprocess isolation (tempfile runner + venv python + JSON parse) | Duplicate in each pipeline | `shared/subprocess_runner.py` (D-03) | `_run_stap` + `_run_tap_subprocess` are near-identical (400-line duplication) |
| DB path resolution | Inline `*_DB_PATH` in each pipeline | `shared/db.py` (D-06) over existing `shared/db_paths.py` | 6+ branches inline their own path; single source prevents drift |
| Dynamic module resolution | Reimplement registry | `dispatcher.py:_resolve_pipeline` (existing L448) | Already handles ETAP exceptions + fallback |
| AdSense ID handling | Hand-roll in standard | Keep immutable per global rule | IDs 8772/6677/5938 are domain-bound; never derive programmatically |

**Key insight:** This phase is unusual — the "don't hand-roll" problems are *already solved* by existing dispatcher infrastructure. The standardization work is about **centralizing the duplicated logic**, not writing new algorithms. Reuse, don't reinvent.

## Runtime State Inventory

> Include for rename/refactor/migration phases. This phase is a **structural refactor** (module skeleton, config schema, subprocess runner) with **no blog-ID / DB-name / env-var renames**. All identifiers stay the same; only code organization + config schema shape change. Verified categories below are explicit.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **None changed.** Per-pipeline DB files (`data/*.db`) stay in place; D-06 centralizes only path/connection code. | none (no data migration) |
| Live service config | **None changed.** External TAP/STAP projects stay subprocess-isolated; only the `run` contract is aligned (dict shape). | none (contract-only) |
| OS-registered state | **None changed.** `launchd` scheduler + blog IDs unchanged. | none |
| Secrets/env vars | **None renamed.** `.env`, `api_keys.yaml`, `CLOUDFLARE_API_TOKEN` handling unchanged. `shared/subprocess_runner.py` MUST preserve the existing `CLOUDFLARE_API_TOKEN`-removal behavior in deploy paths (see AGENTS.md). | none (code must preserve existing token handling) |
| Build artifacts | **None changed.** `pipelines/*/` module names unchanged; no renames. `scripts/scaffold_branch.py` is new, not a rename. | none |

**Nothing found in category:** All categories "none changed" — verified against `dispatcher.py`, `scheduler.py`, `shared/db_paths.py`, and inline `*_DB_PATH` constants. This is a code-organization refactor; no runtime state migration required.

## Common Pitfalls

### Pitfall 1: Breaking the ETAP signature bridge
**What goes wrong:** Standardizing ETAP's 35 topic pipelines to `run(cfg)` could break the `inspect.signature` bridge at `dispatcher.py:463-465` if a pipeline's `run()` signature is changed from `run()` to `run(cfg)` without updating the module import path (e.g., `flights-hugo` → `pipelines.etap.flight_pipeline`).
**Why it happens:** `_ETAP_BLOG_EXCEPTIONS` + stem-based module resolution at `dispatcher.py:444-465` is brittle; changing signatures without updating the map silently changes behavior.
**How to avoid:** In stage D, add adapter `run(cfg)` wrappers that delegate to the existing `run()` — never rename the entry function mid-migration. Keep `_ETAP_BLOG_EXCEPTIONS` intact.
**Warning signs:** `flights-hugo`/`_ETAP_BLOG_EXCEPTIONS` handling changes; `inspect.signature` call removed.

### Pitfall 2: Reason-key vocabulary drift
**What goes wrong:** 11+ pipeline reason strings are not in `problem_registry.py`'s P01–P24 reason_keys, so they classify as `unknown_failure` and lose alert specificity.
**Why it happens:** `shared/problem_registry.py:54+` enumerates known reasons; branches emit their own strings independently.
**How to avoid:** The `docs/PIPELINE-STANDARD.md` (D-02) MUST define a closed reason vocabulary, and `problem_registry.py` must gain the missing keys (`daily_quota_reached`, `expired_service`, `generation_failed`, `language_error`, `no_subscription_data`, `no_topic`, `no_topics`, `no_trade_data`, `prompt_not_found`, `publish_failed`, `write_failed`) OR the standard maps them to existing P-codes.
**Warning signs:** `_tg_error` / alerting reports `unknown_failure` for a reason the pipeline actually returned.

### Pitfall 3: `run(cfg)` returning `None` (travel) vs dict contract
**What goes wrong:** `travel/pipeline.py:413 run(cfg)` delegates to `_run_single` which returns `None` on quota/no-data; `run()` returns `None`-based result, while other branches return `{"success": False, "reason": ...}`. The standard contract must normalize `None` → `{"success": False, "reason": "no_result"}`.
**Why it happens:** Per-branch historical return shapes.
**How to avoid:** Standard mandates `run(cfg)` returns a dict, never None. Wrap travel's `_run_single` result in stage D.
**Warning signs:** A branch returns `None` from `run()`; dispatch relies on the `or {"success": False}` fallback at `dispatcher.py:407`.

### Pitfall 4: CLOUDFLARE_API_TOKEN in the subprocess runner
**What goes wrong:** `shared/subprocess_runner.py` (new) inherits the deploy-path token hazard. If a runner subprocess invokes wrangler, an injected `CLOUDFLARE_API_TOKEN` env var overrides OAuth profile → `Authentication error code: 10000`.
**Why it happens:** Global AGENTS.md rule + wrangler 4.x precedence (env var > OAuth profile).
**How to avoid:** The runner must `env -u CLOUDFLARE_API_TOKEN` (or pop it from env) before any wrangler call, mirroring `dispatcher.py:_build_and_deploy_central()` and `deploy.py:_deploy_site_inner()`.
**Warning signs:** Deploys fail with auth 10000 when run under agent sessions.

## Code Examples

Verified patterns from the current codebase (these are the ground truth to standardize against):

### Standard `run(cfg)` contract — STAP stock (returns dict natively)
```python
# STAP/pipelines/stock/pipeline.py:365
def run(blog_cfg):
    """dispatcher에서 호출하는 통일 인터페이스"""
    ...
    today_count = get_today_count(blog_id)
    daily_quota = blog_cfg.get("daily_quota", 5)
    if today_count >= daily_quota:
        return {"success": False, "reason": "quota_met"}
    ...
    return result or {"success": False, "reason": "no_content"}  # L442
```

### Dispatcher signature-aware dispatch (ETAP mixed contract bridge)
```python
# dispatcher.py:448-465
def _resolve_pipeline(blog_id, pipeline, cfg):
    if pipeline == "etap":
        ...
        mod = importlib.import_module(module_path)
        run = mod.run
        import inspect
        if "cfg" in inspect.signature(run).parameters or len(inspect.signature(run).parameters) > 0:
            return run(cfg)
        return run()
```

### Subprocess isolation pattern to centralize (STAP, dispatcher.py:380-440)
```python
# The runner-script + tempfile + venv-python + JSON-parse pattern (DUPLICATED in _run_stap and _run_tap_subprocess)
stap_python = os.path.join(stap_root, ".venv", "bin", "python3")
if not os.path.exists(stap_python):
    stap_python = sys.executable
runner = "\n".join([... "from pipelines.%s.pipeline import run" % stap_name, "result = run(cfg)", 'print(json.dumps(result or {"success": False, "reason": "no_result"}, ...))'])
proc = subprocess.run([stap_python, runner_path], capture_output=True, text=True, timeout=600, cwd=stap_root)
for line in reversed(proc.stdout.strip().split("\n")):
    if line.strip().startswith("{"):
        return json.loads(line.strip())
```
**→ `shared/subprocess_runner.py` should extract exactly this:** (1) resolve project root + venv python, (2) write tempfile runner, (3) run with 600s timeout, (4) parse last JSON line, (5) return dict. Both `_run_stap` and `_run_tap_subprocess` become thin callers.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-branch inline `*_DB_PATH` | `shared/db.py` central path helper (D-06) | Phase 61 | Single DB-path source; data files unchanged |
| Duplicated STAP/TAP tempfile runners | `shared/subprocess_runner.py` (D-03) | Phase 61 | ~400 lines consolidated; external isolation preserved |
| Mixed `run()`/`run(cfg)`/bool returns | Standard `run(cfg)->dict` (D-01/D-02) | Phase 61 | Dispatcher normalization stays; module contract unified |
| Per-branch config schemas | Unified schema + optional fields (D-04) | Phase 61 | One schema in PIPELINE-STANDARD.md |
| Ad-hoc branch creation | `scripts/scaffold_branch.py` (D-05) | Phase 61 | New branches start standard, prevent divergence |

**Deprecated/outdated:**
- **Inline DB path constants** in car/stock/rap/senior/curation/etap — replaced by `shared/db.py` (paths only, data files kept).
- **`shared/db_paths.py` as-is** — to be extended/used by `shared/db.py`, not replaced with a rename (preserve existing symbol names per D-08).

## Assumptions Log

> All claims in this research were verified against the current working tree (code-level, HIGH confidence) unless tagged [ASSUMED]. No third-party claims are made.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ETAP topic pipelines write exclusively via `shared/publishers/hugo_writer` `_write_hugo_post_etap` (all 35 verified via `rg`) | Current-state audit | Low — verified; but adapter must confirm no hidden local writer |
| A2 | Reason keys list is exhaustive of the "not in registry" gap | Common Pitfalls 2 | Low — additional unregistered reasons may surface during rollout; standard must be additive-tolerant |
| A3 | travel `run()` can return None | Common Pitfalls 3 | Medium — verified `_run_single` returns None on quota/no-data; standard normalization must cover it |
| A4 | External STAP/TAP DBs and code stay untouched | Runtime State Inventory | Low — contract-only alignment |

## Open Questions

1. **Should `problem_registry.py` gain the 11 missing reason keys, or should PIPELINE-STANDARD map them to existing P-codes?**
   - What we know: 11+ strings fall through to `unknown_failure`.
   - What's unclear: Whether adding keys to the registry (data change) or remapping in the standard (doc change) is preferred.
   - Recommendation: Add the missing keys to `problem_registry.py` as the closed vocabulary, since the registry already merges PLAN.md reasons into nearest P-code (see its header comment).

2. **Does the unified config schema (D-04) need a `config_validator`-level enforcement, or is documentation-only sufficient?**
   - What we know: `dispatcher.py:get_blog_config` / `_load_all_blogs` parse `blogs.d/*.yaml`; there is no schema validator today.
   - What's unclear: Whether a runtime validator is in scope or just the written standard.
   - Recommendation: Document the schema in PIPELINE-STANDARD.md first (D-04 scope); add a validator only if a follow-up phase is created — keep this phase additive.

## Environment Availability

> Skip section if no external dependencies. This phase depends on existing runtimes only — no new external tools.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All pipeline modules | ✓ | 3.14.6 | — |
| Hugo (extended) | Deploy verification | ✓ | v0.160.1 | — |
| wrangler | Deploy verification (via dispatcher/deploy.py only) | ✓ | 4.110.0 | — |
| pytest | Validation (existing tests) | ✓ | 8.4.2 | — |
| PyYAML | Config parse + scaffold | ✓ | ^6.0.1 | — |

**Missing dependencies with no fallback:** none — all runtimes present. This phase requires **zero new installs**.

## Validation Architecture

> workflow.nyquist_validation is enabled (absent in config.json). Existing test infra covers shared + curation + dispatcher_registry.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 (pyproject.toml `addopts = --cov=shared,pipelines/curation`) |
| Config file | `pyproject.toml` |
| Quick run command | `pytest tests/test_dispatcher_registry.py -x` |
| Full suite command | `pytest -q` (33 test files) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| D-03 | `shared/subprocess_runner.py` runs a target module + returns dict | integration | `pytest tests/test_subprocess_runner.py -x` | ❌ Wave 0 |
| D-06 | `shared/db.py` resolves per-branch DB path | unit | `pytest tests/test_db.py -x` | ❌ Wave 0 |
| D-05 | `scripts/scaffold_branch.py` produces standard skeleton | integration | `pytest tests/test_scaffold_branch.py -x` | ❌ Wave 0 |
| D-01 | Standard skeleton present per branch (pipeline/fetcher/topic_manager/writer/enrich/validator) | smoke | `pytest tests/test_pipeline_skeleton.py -x` | ❌ Wave 0 |
| D-04 | Unified config schema loads | unit | `pytest tests/test_config_schema.py -x` | ❌ Wave 0 |
| registry | Existing registry still resolves (regression) | unit | `pytest tests/test_dispatcher_registry.py -x` | ✅ |

### Sampling Rate
- **Per task commit:** `pytest tests/test_dispatcher_registry.py -x`
- **Per wave merge:** `pytest -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_subprocess_runner.py` — covers D-03
- [ ] `tests/test_db.py` — covers D-06
- [ ] `tests/test_scaffold_branch.py` — covers D-05
- [ ] `tests/test_pipeline_skeleton.py` — covers D-01
- [ ] `tests/test_config_schema.py` — covers D-04
- Framework install: `pip install pytest-cov` if not present — none needed (pytest 8.4.2 + cov already configured)

## Security Domain

> security_enforcement enabled (absent in config). ASVS below.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | External services use existing env-secret handling; no new auth surface |
| V3 Session Management | no | Stateless pipeline; no sessions |
| V4 Access Control | no | No user roles |
| V5 Input Validation | yes | `scripts/scaffold_branch.py` + config parsing must validate blog IDs / paths to prevent path traversal & injection into dynamically imported module paths (`dispatcher.py:454-455` builds `pipelines.etap.{stem}_pipeline` from `blog_id` — validate `blog_id` against a safe pattern) |
| V6 Cryptography | no | No new crypto |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Module-path injection via blog_id (`pipelines.etap.{stem}_pipeline`) | Tampering | Validate `blog_id` matches `^[a-z0-9-]+$` before importlib; reuse existing registry map rather than raw string concat |
| CLOUDFLARE_API_TOKEN leak into subprocess runner | Information Disclosure | Runner must strip the env var before any wrangler subprocess (mirror existing deploy code) |
| Path traversal in scaffold_branch | Tampering | Validate generated branch names against `^[a-z][a-z0-9_]*$`; ensure path joins are sanitized |

## Sources

### Primary (HIGH confidence) — code-verified against current working tree
- `dispatcher.py` — `_resolve_pipeline` L448, `_run_stap` L380, `_run_tap_subprocess` L504, `dispatch()` normalization L740, `_ETAP_BLOG_EXCEPTIONS` L444, `ETAP_PIPELINE_BLOGS` L566, `STAP_PIPELINE_MAP` L81, `_build_and_deploy_central` L596
- `pipelines/{car,curation,etap,rap,senior,travel,stock}/pipeline.py` — run() signatures/returns (grep-verified)
- `pipelines/etap/*_pipeline.py` — 35 topic pipelines, mixed `run()`/`run(cfg)` signatures (grep-verified), 35/35 write via shared hugo_writer
- `shared/problem_registry.py` — P01–P24 + reason_keys (verified gap)
- `shared/db_paths.py`, `shared/paths.py` — DB path + project-root resolution
- `STAP/pipelines/stock/pipeline.py:365` and `TAP/app.py:602` — external run contracts
- `config/blogs.d/*.yaml` — schema disparity (grep-verified)
- `tests/` — 33 test files, coverage config

### Secondary (MEDIUM confidence)
- `scheduler.py` — catchup/dispatch loop (L400-457)

### Tertiary (LOW confidence)
- None — all claims verified against working tree

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new deps, verified runtime versions
- Architecture: HIGH — code-verified module skeletons + dispatcher flow
- Pitfalls: HIGH — measured reason-key gap, ETAP signature bridge, None-return, token hazard
- Refactor-state inventory: HIGH — all categories "none changed," verified against dispatcher/scheduler/paths

**Research date:** 2026-08-07
**Valid until:** 2026-09-06 (stable refactor domain; 30-day window)
