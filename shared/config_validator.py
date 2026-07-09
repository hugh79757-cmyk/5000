"""Config schema validation — blogs.yaml, blogs.d/*.yaml, prompts.yaml 구조 검증.

사용법:
    from shared.config_validator import validate_configs
    errors = validate_configs()
    if errors["blogs"] or errors["prompts"]:
        logger.warning(f"Config errors: {errors}")
"""

import os
import glob
import yaml

REQUIRED_BLOG_FIELDS = ["id", "pipeline", "platform"]
OPTIONAL_BLOG_FIELDS = ["daily_quota", "site_path", "repo", "theme", "status"]
VALID_PLATFORMS = ["hugo", "blogger", "wordpress"]

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")
_BLOGS_D_DIR = os.path.join(_CONFIG_DIR, "blogs.d")


def _resolve_config_path(path: str, filename: str) -> str:
    """Resolve config file path. If not found directly, try config/ subdir."""
    if not path:
        path = filename
    if os.path.isfile(path):
        return path
    alt = os.path.join(_CONFIG_DIR, filename if path == filename else os.path.basename(path))
    if os.path.isfile(alt):
        return alt
    return path


def _validate_blog_entry(blog: dict, source: str, idx: int) -> list[str]:
    """Validate a single blog definition entry."""
    errors: list[str] = []
    prefix = f"{source}[{idx}]"
    for field in REQUIRED_BLOG_FIELDS:
        if field not in blog:
            errors.append(f"{prefix}: missing required field '{field}'")
    if "platform" in blog and blog["platform"] not in VALID_PLATFORMS:
        errors.append(f"{prefix}: invalid platform '{blog['platform']}' (valid: {VALID_PLATFORMS})")
    schedule = blog.get("schedule", {})
    if not isinstance(schedule, dict):
        errors.append(f"{prefix}.schedule: not a dict")
    elif not schedule:
        errors.append(f"{prefix}.schedule: empty (should contain 'times')")
    if "repo" in blog and "site_path" not in blog:
        errors.append(f"{prefix}: has 'repo' but missing 'site_path'")
    return errors


def validate_master_config(path: str = "") -> list[str]:
    """Validate config/blogs.yaml master structure (batch_deploy, deploy, git_backup)."""
    errors: list[str] = []
    resolved = _resolve_config_path(path, "blogs.yaml")
    if not os.path.isfile(resolved):
        errors.append(f"blogs.yaml not found at {resolved}")
        return errors
    try:
        with open(resolved, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        errors.append(f"blogs.yaml parse error: {e}")
        return errors

    if not isinstance(config, dict):
        errors.append("blogs.yaml: root is not a dict")
        return errors
    for key in ("batch_deploy", "deploy", "git_backup"):
        if key not in config:
            errors.append(f"blogs.yaml: missing expected key '{key}'")
    return errors


def validate_blog_defs(directory: str = "") -> list[str]:
    """Validate all blog definition files in blogs.d/ directory."""
    errors: list[str] = []
    d = directory or _BLOGS_D_DIR
    if not os.path.isdir(d):
        errors.append(f"blogs.d directory not found: {d}")
        return errors

    for fpath in sorted(glob.glob(os.path.join(d, "*.yaml"))):
        fname = os.path.basename(fpath)
        try:
            with open(fpath, encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            errors.append(f"{fname}: parse error: {e}")
            continue

        if not isinstance(config, dict):
            errors.append(f"{fname}: root is not a dict")
            continue
        if "blogs" not in config:
            errors.append(f"{fname}: missing 'blogs' key")
            continue
        blog_list = config["blogs"]
        if not isinstance(blog_list, list):
            errors.append(f"{fname}.blogs: not a list")
            continue
        for i, blog in enumerate(blog_list):
            if not isinstance(blog, dict):
                errors.append(f"{fname}.blogs[{i}]: not a dict")
                continue
            errors.extend(_validate_blog_entry(blog, fname, i))
    return errors


def validate_prompts_config(path: str = "") -> list[str]:
    """Validate prompts.yaml structure."""
    errors: list[str] = []
    resolved = _resolve_config_path(path, "prompts.yaml")
    if not os.path.isfile(resolved):
        errors.append(f"prompts.yaml not found at {resolved}")
        return errors
    try:
        with open(resolved, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        errors.append(f"prompts.yaml parse error: {e}")
        return errors
    if not isinstance(config, dict):
        errors.append("prompts.yaml: root is not a dict")
        return errors
    if not config:
        errors.append("prompts.yaml: empty config")
    return errors


def validate_configs(paths: dict | None = None) -> dict[str, list[str]]:
    """Run all validations. Returns dict of {config_name: [error_msg, ...]}."""
    if paths is None:
        paths = {
            "master": "",
            "blogs_d": "",
            "prompts": "",
        }
    return {
        "master": validate_master_config(paths.get("master", "")),
        "blogs_d": validate_blog_defs(paths.get("blogs_d", "")),
        "prompts": validate_prompts_config(paths.get("prompts", "")),
    }
