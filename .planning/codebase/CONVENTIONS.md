---
focus: quality
last_mapped: 2026-06-30
version: 1
---

# Coding Conventions

## Python Style

- **snake_case** for all functions, variables, file names
- **PascalCase** for classes (rarely used — most code is module-level functions)
- **UPPER_CASE** for constants, env var names
- **Type hints**: Partial adoption — some files use `typing` annotations, many don't
- **Docstrings**: Some modules have module-level docstrings (`"""..."""`), inline comments are sparse
- **Line length**: Not enforced — varies widely (some lines exceed 120 chars in `dispatcher.py`)
- **F-strings**: Preferred over `%` formatting or `.format()`
- **Imports**: Standard library → third-party → local, separated by blank lines

## Code Organization

### Module Pattern
```python
"""Module docstring — what this module does."""
import os
import sys
import logging

logger = logging.getLogger(__name__)

# Constants at module level
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")

# Helper functions first
def _private_helper():
    pass

# Public API functions
def public_function(param):
    pass
```

### Pipeline Pattern
Each pipeline follows a standard interface:
```python
# pipelines/{name}/pipeline.py
def run(cfg: dict) -> dict:
    """Execute pipeline. Returns {"success": True/False, ...}"""
    ...
```

### Error Handling
- **try/except** everywhere — external calls always wrapped
- **Graceful degradation**: On failure, log error + continue; never crash the pipeline
- **`_tg_error()`**: Critical failures sent to Telegram
- **`logger.error/fatal`**: Pipeline errors logged at module level
- **`sys.exit(1)`**: Only on catastrophic startup failures (import checks)

Example from `dispatcher.py:206`:
```python
except Exception as e:
    logger.error(f"ledger 기록 실패: {e}")
```

### Configuration Loading
```python
# Standard pattern from multiple files
from dotenv import load_dotenv
load_dotenv(os.path.expanduser("~/.env.common"))
load_dotenv("/Users/twinssn/Projects/5000/.env")
```

## Naming Conventions

- **Blog IDs**: `{category}-hugo` for Hugo sites, `{category}-blogger` for Blogger
- **Pipeline names**: Short acronyms (`etap`, `gap`, `rap`, `car`)
- **Config keys**: `snake_case` in YAML (`daily_quota`, `site_path`)
- **SQLite DB files**: `{pipeline}.db` (e.g., `car.db`, `rap.db`)
- **Lock files**: `data/.lock_{blog_id}` for pipeline concurrency
- **Private functions**: `_leading_underscore` for module-internal functions

## Configuration Conventions

### `blogs.d/*.yaml` Blog Definition
```yaml
blogs:
- id: rap-hugo
  name: 부동산 뉴스
  pipeline: rap
  platform: hugo
  domain: rap.rotcha.kr
  daily_quota: 10
  schedule:
    times:
    - 06:00
    - 09:00
    - ...
  status: active
  prompt_map:
    default: rap_general
```

### `prompts.yaml` Structure
```
[SEO RULES] - Title tag rules, keyword placement
[BAN headings] - Forbidden H2 patterns
[BAN phrases] - Forbidden expressions
[ABSOLUTE BAN] - Reject-worthy content
{category}_default: System prompt template
{category}_{topic}: Per-topic prompt variant
```

## Conditional Import Pattern
```python
try:
    from shared.telegram_notifier import send_error as tg_error
except ImportError:
    tg_error = lambda *a, **k: None
```
Used throughout to make Telegram alerts optional (graceful degradation).

## Deployment Pattern
```python
r1 = subprocess.run([HUGO, "--gc", "--minify"], cwd=site_path, capture_output=True, text=True)
if r1.returncode != 0:
    return False
r2 = subprocess.run([WRANGLER, "pages", "deploy", "public", "--project-name", blog_id, ...], ...)
```

## Version Control

- **Branch**: `main` — single branch development
- **Commit style**: Concise, no conventional commits format observed
- **`.gitignore`**: Aggressive — `.bak*`, `.venv/`, `__pycache__/`, `.env`, `api_keys.yaml`, `.db` files
- **Themes**: `themes/` is gitignored (git submodule or manual install)
- **Resources**: `resources/` is gitignored (Hugo cache)

## Shell/PATH Dependencies
Hardcoded paths to Homebrew binaries:
```python
HUGO     = "/opt/homebrew/bin/hugo"
WRANGLER = "/opt/homebrew/bin/wrangler"
```
