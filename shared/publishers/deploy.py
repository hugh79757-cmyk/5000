import logging
import os
import re
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv

from shared.paths import FIVEK_ROOT, SHARED_THEMES, HUGO_PATH, WRANGLER_PATH

logger = logging.getLogger(__name__)


def deploy_site(site_path, cf_project) -> bool:
    Path(site_path)
    import fcntl as _fl

    _lock_path = Path("/tmp/wrangler_deploy.lock")
    _lock_file = open(_lock_path, "w")
    _lock_acquired = False
    _deadline = time.time() + 60
    try:
        while time.time() < _deadline:
            try:
                _fl.flock(_lock_file, _fl.LOCK_EX | _fl.LOCK_NB)
                _lock_acquired = True
                break
            except BlockingIOError:
                time.sleep(1)
        if not _lock_acquired:
            raise TimeoutError("wrangler deploy lock timeout (60s)")
    except Exception:
        pass
    try:
        _deploy_site_inner(site_path, cf_project)
    finally:
        if _lock_acquired:
            try:
                _fl.flock(_lock_file, _fl.LOCK_UN)
                _lock_file.close()
            except Exception:
                pass
    return True


def _deploy_site_inner(site_path, cf_project) -> bool:
    site = Path(site_path)
    load_dotenv(os.path.join(FIVEK_ROOT, ".env"), override=True)
    _wrangler_env = os.environ.copy()
    _cf_token = os.getenv("CLOUDFLARE_API_TOKEN", "")
    _cf_account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    if _cf_token:
        _wrangler_env["CLOUDFLARE_API_TOKEN"] = _cf_token
    if _cf_account:
        _wrangler_env["CLOUDFLARE_ACCOUNT_ID"] = _cf_account
    rogue = site / "content" / "posts" / "index.md"
    if rogue.exists():
        rogue.unlink()
        print(f"[guard] Removed rogue index.md from {site}")

    _hugo_toml = site / "hugo.toml"
    _hugo_theme = ""
    _themes_dir = SHARED_THEMES
    if _hugo_toml.exists():
        try:
            _toml_text = _hugo_toml.read_text(encoding="utf-8")
            _m_theme = re.search(r'^theme\s*=\s*["\'](.+?)["\']', _toml_text, re.MULTILINE)
            if _m_theme:
                _hugo_theme = _m_theme.group(1)
            _m_dir = re.search(r'^themesDir\s*=\s*["\'](.+?)["\']', _toml_text, re.MULTILINE)
            if _m_dir:
                _themes_dir = _m_dir.group(1)
        except Exception:
            pass
    _local_theme = site / "themes" / _hugo_theme if _hugo_theme else None
    if not (_local_theme and _local_theme.is_dir()):
        _wrangler_env.setdefault("HUGO_THEMESDIR", _themes_dir)

    log_path = Path(os.path.join(FIVEK_ROOT, "logs", "deploy.log"))
    with open(log_path, "a") as log_f:
        result = subprocess.run(
            [HUGO_PATH, "--gc", "--minify"],
            cwd=str(site), stdout=log_f, stderr=log_f,
            env=_wrangler_env, timeout=120
        )
    if result.returncode != 0:
        raise Exception("Hugo build failed: see deploy.log")
    index_file = site / "public" / "index.html"
    if not index_file.exists():
        raise Exception("Hugo build produced empty site: public/index.html not found")

    wf = site / "wrangler.toml"
    use_workers = wf.exists() and "[assets]" in wf.read_text()

    with open(log_path, "a") as log_f:
        _deploy_timeout = 120
        try:
            if use_workers:
                result = subprocess.run(
                    [WRANGLER_PATH, "deploy",
                     "--config", str(wf)],
                    cwd=str(site), stdout=log_f, stderr=log_f,
                    env=_wrangler_env, timeout=_deploy_timeout
                )
            else:
                result = subprocess.run(
                    [WRANGLER_PATH, "pages", "deploy", "./public",
                     "--project-name=" + cf_project,
                     "--branch=main",
                     "--commit-dirty=true",
                     "--commit-message=deploy-" + time.strftime("%Y%m%d%H%M%S")],
                    cwd=str(site), stdout=log_f, stderr=log_f,
                    env=_wrangler_env, timeout=_deploy_timeout
                )
        except subprocess.TimeoutExpired:
            msg = f"Wrangler deploy timed out ({_deploy_timeout}s)"
            raise Exception(msg)
    if result.returncode != 0:
        err_text = (result.stderr or "").lower()
        if "fetch failed" in err_text or "fetch error" in err_text or "network" in err_text:
            for attempt in range(2):
                time.sleep(10 * (attempt + 1))
                print(f"[deploy] {site.name} 재시도 {attempt + 1}/2 (network error)")
                with open(log_path, "a") as log_f:
                    try:
                        if use_workers:
                            result = subprocess.run(
[WRANGLER_PATH, "deploy",
                                 "--config", str(wf)],
                                cwd=str(site), stdout=log_f, stderr=log_f,
                                env=_wrangler_env, timeout=_deploy_timeout
                            )
                        else:
                            result = subprocess.run(
                                [WRANGLER_PATH, "pages", "deploy", "./public",
                                 "--project-name=" + cf_project,
                                 "--branch=main",
                                 "--commit-dirty=true",
                                 "--commit-message=deploy-" + time.strftime("%Y%m%d%H%M%S")],
                                cwd=str(site), stdout=log_f, stderr=log_f,
                                env=_wrangler_env, timeout=_deploy_timeout
                            )
                    except subprocess.TimeoutExpired:
                        print(f"[deploy] {site.name} 재시도 {attempt + 1}/2 timeout ({_deploy_timeout}s)")
                        continue
                if result.returncode == 0:
                    print(f"[deploy] {site.name} 재시도 성공")
                    break
        if result.returncode != 0:
            raise Exception("Wrangler deploy failed: see deploy.log")
    return True
