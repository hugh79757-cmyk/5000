"""Central path resolver — env-driven project roots and binary paths.

Tiered resolution:
1. `{NAME}_ROOT` env var
2. `~/.env.common` fallback (if env var not set in process)
3. Convention-based default
"""

import os
import shutil
from pathlib import Path


def project_root(name: str) -> str:
    """Resolve project root for a named project.

    Checks `{NAME}_ROOT` env var. Falls back to `~/.env.common`.
    """
    var = f"{name.upper()}_ROOT"
    root = os.getenv(var)
    if root:
        return root
    common = os.path.expanduser("~/.env.common")
    if os.path.isfile(common):
        with open(common) as f:
            for line in f:
                line = line.strip()
                if line.startswith(var + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


_5000_ROOT = os.getenv("5000_ROOT")
if not _5000_ROOT:
    _5000_ROOT = str(Path(__file__).parent.parent.resolve())
FIVEK_ROOT = _5000_ROOT

STAP_ROOT = project_root("STAP") or os.path.join(FIVEK_ROOT, "..", "STAP")
TAP_ROOT = project_root("TAP") or os.path.join(FIVEK_ROOT, "..", "TAP")
ETAP_ROOT = project_root("ETAP") or os.path.join(FIVEK_ROOT, "..", "ETAP")
LAP_ROOT = project_root("LAP") or os.path.join(FIVEK_ROOT, "..", "LAP")
CUAP_ROOT = project_root("CUAP") or os.path.join(FIVEK_ROOT, "..", "CUAP")
RAP_ROOT = project_root("RAP") or os.path.join(FIVEK_ROOT, "..", "RAP")

SHARED_THEMES = os.getenv("SHARED_THEMES_DIR") or "/Users/twinssn/Projects/shared-themes"

# Phase 78 Task 9: 러너 환경 site_path 재해석 루트 (미설정 시 Mac 절대경로 fallback)
SITES_ROOT = os.getenv("SITES_ROOT") or "/Users/twinssn/Projects"

_MAC_SITES_PREFIX = "/Users/twinssn/Projects/"


def resolve_site_path(site_path: str) -> str:
    """blogs.d site_path 절대경로를 SITES_ROOT 기준으로 재해석 (Phase 78 Task 9).

    SITES_ROOT 미설정 시 원본 문자열 그대로 반환 (Mac 기본 동작 불변).
    러너에서 SITES_ROOT 설정 시 상대 재해석.
    """
    if not site_path:
        return site_path
    if site_path.startswith(_MAC_SITES_PREFIX):
        tail = site_path[len(_MAC_SITES_PREFIX):]
        return os.path.join(SITES_ROOT, tail)
    return site_path


LOGS_DIR = os.path.join(FIVEK_ROOT, "logs")
DATA_DIR = os.path.join(FIVEK_ROOT, "data")
CONFIG_DIR = os.path.join(FIVEK_ROOT, "config")


def _resolve_binary(name: str, env_var: str, default: str = "") -> str:
    path = os.getenv(env_var)
    if path:
        return path
    resolved = shutil.which(name)
    if resolved:
        return resolved
    return default


HUGO_PATH = _resolve_binary("hugo", "HUGO_PATH", "/opt/homebrew/bin/hugo")
WRANGLER_PATH = _resolve_binary("wrangler", "WRANGLER_PATH", "/opt/homebrew/bin/wrangler")
