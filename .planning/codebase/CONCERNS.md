---
focus: concerns
last_mapped: 2026-06-30
version: 1
---

# Areas of Concern

## Technical Debt

### 1. No Test Coverage
- **Severity**: HIGH
- **Impact**: Any change risks breaking pipelines silently. No regression safety net.
- **Evidence**: No test framework, no test directory, only 2 manual test scripts in `scripts/`

### 2. Hardcoded Absolute Paths
- **Severity**: HIGH
- **Impact**: Code won't work on any machine other than the author's. Blocks CI/CD, collaboration, deployment to other environments.
- **Examples**:
  - `dispatcher.py:17`: `sys.path.insert(0, "/Users/twinssn/Projects/TAP")`
  - `shared/publisher.py:27`: `STAP_ENTITY_DB = "/Users/twinssn/Projects/STAP/data/stap_entities.db"`
  - `pipelines/etap/*`: All `Project/ETAP/` paths
  - `dispatcher.py:436-437`: `HUGO = "/opt/homebrew/bin/hugo"`, `WRANGLER = "/opt/homebrew/bin/wrangler"`
  - `dispatcher.py:379`: `tap_root = "/Users/twinssn/Projects/TAP"`

### 3. Backup File Pollution
- **Severity**: MEDIUM
- **Impact**: 50+ `.bak*` files in source directories (especially `pipelines/etap/` and `shared/`). Confusing, bloats repo, and `.gitignore` doesn't cover all patterns in subdirectories.
- **Evidence**: `shared/` has 16 `.bak*` files; `pipelines/etap/` has 30+ `.bak*` files

### 4. Large Monolithic Files
- **Severity**: MEDIUM
- **Impact**: Poor maintainability, difficult to reason about
- **Evidence**:
  - `shared/publisher.py`: 959 lines, handles multiple platform types
  - `pipelines/rap/pipeline.py`: 1043 lines, complex keyword filtering
  - `scheduler.py`: 712 lines
  - `dispatcher.py`: 666 lines
  - `config/prompts.yaml`: 1117 lines (prompt data, not code — less concerning)

### 5. No Type Checking / Linting
- **Severity**: MEDIUM
- **Impact**: Runtime type errors, inconsistent style, no automated quality gate
- **Evidence**: No `mypy.ini`, no `.ruff.toml`, no `.flake8`, no `pyproject.toml` config

## Security Concerns

### 6. API Keys in Config Files
- **Severity**: MEDIUM (mitigated)
- **Status**: `config/api_keys.yaml` is gitignored. `.env` files are gitignored. Token files are gitignored.
- **Residual risk**: `config/blogger_token.json` path is gitignored but `config/client_secret_hugh7973.json` has a `.gitignore` entry

### 7. IndexNow Hardcoded Key
- **Severity**: LOW
- **Evidence**: `scripts/indexnow.py:12`: `KEY = "b8f4e2a1c3d5e6f7a8b9c0d1e2f3a4b5"` — static key hardcoded in source, though this is a public key served at `rotcha.kr/{key}.txt`

### 8. Deploy Lock Path
- **Severity**: LOW
- **Evidence**: `dispatcher.py:462`: `DEPLOY_LOCK = "/tmp/wrangler_deploy.lock"` — world-writable path, though only advisory locking

## Performance

### 9. Sequential Wrangler Deploys
- **Severity**: LOW
- **Impact**: When multiple blogs publish simultaneously, deploys queue behind `flock()` lock. Each deploy takes 30-60s.
- **Mitigation**: Lock prevents wrangler API rate limiting and race conditions

### 10. Subprocess Overhead per Pipeline Run
- **Severity**: LOW
- **Impact**: STAP/TAP run as subprocesses with temp file generation, Python interpreter startup, and DB connection overhead each run

### 11. SQLite Under Load
- **Severity**: LOW
- **Impact**: 15+ separate SQLite databases, no connection pooling. Pipeline-heavy schedules may cause write contention on the central `content.db`

## Maintainability

### 12. Python 3.14 Compatibility
- **Severity**: MEDIUM
- **Impact**: `dispatcher.py:31` includes `check_package_imports()` specifically for Python 3.14 compatibility. The `openai` package needs `>=2.40.0` for 3.14 support.
- **Evidence**: `dispatcher.py:33-35`: Checks `openai.resources.chat` module availability

### 13. External Project Coupling
- **Severity**: HIGH
- **Impact**: TAP, STAP, ETAP, LAP, CUAP are external projects with hardcoded paths. If these projects move/change, 5000 breaks. No versioning or dependency management between them.
- **DB paths to external projects**: `dispatcher.py:134` references STAP DB, `shared/daily_report.py:15-16` references TAP DB and LAP log

### 14. `.env` File Fragmentation
- **Severity**: LOW
- **Impact**: Multiple `.env` files loaded in cascade: `~/.env.common`, `5000/.env`, per-project `.env`. Can make debugging credential issues difficult.

### 15. No Database Migrations
- **Severity**: MEDIUM
- **Impact**: Schema changes require manual SQLite commands. No migration history, no rollback capability. 15+ databases with no schema version tracking.

### 16. No Logging Aggregation
- **Severity**: LOW
- **Impact**: Logs go to stdout/stderr only. No log rotation, no central log storage, no log search. `logs/` directory exists in `.gitignore` but is empty.

## Fragile Areas

### 17. `dispatcher.py:_run_pipeline()` — Large if/elif Chain
- **Severity**: MEDIUM
- **Impact**: 50+ `elif` branches mapping blog_id → pipeline module. Adding a new blog requires adding an elif. Easy to miss or mis-order.

### 18. `shared/publisher.py` — Multi-Platform Publishing
- **Severity**: MEDIUM
- **Impact**: Single file handling Hugo, Blogger, WordPress publishing with conditional import logic. Entity linking requires TAP modules to be available.

### 19. ETAP Pipeline File Count
- **Severity**: LOW
- **Impact**: 30+ near-identical pipeline/writer file pairs. Each new topic requires new pipeline + writer files. High duplication, hard to maintain consistency.
