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

# --- Phase 61 (Plan 61-02) 통합 스키마 확장 (PIPELINE-STANDARD §4, additive) ---
STANDARD_BLOG_FIELDS = ["name", "domain", "daily_quota", "schedule", "status", "managed_by"]
EXTENSION_BLOG_FIELDS = [
    "cf_project",
    "repo",
    "site_path",
    "theme",
    "funnel_stage",
    "depth_next",
    "bridge_to",
    "post_type",
    "prompt",
    "ga4_property",
    "gsc_site",
    "blogger_blog_id",
    "force_draft",
    "language",
]
# 실측 추가 분기별 확장 키 (PIPELINE-STANDARD §4.2) — optional, 보존.
KNOWN_EXTRA_KEYS = {
    "fetch_sources",
    "prompt_map",
    "bridge_context",
    "shortcodes_enabled",
    "blog_type",
}
VALID_MANAGED_MODES = ("pipeline",)


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


def validate_blog_entry_standard(blog: dict) -> dict[str, list[str]]:
    """PIPELINE-STANDARD §4 통합 스키마 검증 (additive, non-blocking).

    반환: {"errors": [...], "warnings": [...]}
    - errors: 필수 필드(id/pipeline/platform) 누락, 유효하지 않은 platform.
    - warnings: 표준 필드 누락 + 미등록 확장 키(비차단, backward compat, D-08).
    """
    errors: list[str] = []
    warnings: list[str] = []
    for field in REQUIRED_BLOG_FIELDS:
        if field not in blog:
            errors.append(f"missing required field '{field}'")
    if "platform" in blog and blog["platform"] not in VALID_PLATFORMS:
        errors.append(f"invalid platform '{blog['platform']}' (valid: {VALID_PLATFORMS})")
    for field in STANDARD_BLOG_FIELDS:
        if field not in blog:
            warnings.append(f"missing standard field '{field}' (additive, non-blocking)")
    known = set(REQUIRED_BLOG_FIELDS) | set(STANDARD_BLOG_FIELDS) | set(EXTENSION_BLOG_FIELDS) | KNOWN_EXTRA_KEYS
    for key in blog:
        if key not in known:
            warnings.append(f"unknown extension key '{key}' (preserved, non-blocking)")
    return {"errors": errors, "warnings": warnings}


def validate_managed_mode(blog: dict) -> list[str]:
    """`managed_by` 값 검증. 표준은 "pipeline". 미래 값은 warning(비차단)."""
    warnings: list[str] = []
    mv = blog.get("managed_by")
    if mv is not None and mv not in VALID_MANAGED_MODES:
        warnings.append(f"managed_by '{mv}' not in {VALID_MANAGED_MODES} — future value, non-blocking")
    return warnings


def validate_standard_blog_defs(directory: str = "") -> list[str]:
    """blogs.d/*.yaml 전체를 통합 스키마로 스캔해 non-blocking 보고서를 만든다."""
    report: list[str] = []
    d = directory or _BLOGS_D_DIR
    if not os.path.isdir(d):
        return report
    for fpath in sorted(glob.glob(os.path.join(d, "*.yaml"))):
        fname = os.path.basename(fpath)
        try:
            with open(fpath, encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            report.append(f"{fname}: parse error: {e}")
            continue
        if not isinstance(config, dict) or not isinstance(config.get("blogs"), list):
            continue
        for i, blog in enumerate(config["blogs"]):
            if not isinstance(blog, dict):
                continue
            for issue in validate_blog_entry_standard(blog)["errors"]:
                report.append(f"{fname}.blogs[{i}]: {issue}")
            for issue in validate_blog_entry_standard(blog)["warnings"]:
                report.append(f"{fname}.blogs[{i}]: [warn] {issue}")
            for issue in validate_managed_mode(blog):
                report.append(f"{fname}.blogs[{i}]: [warn] {issue}")
    return report


def validate_configs(paths: dict | None = None) -> dict[str, list[str]]:
    """Run all validations. Returns dict of {config_name: [error_msg, ...]}."""
    if paths is None:
        paths = {
            "master": "",
            "blogs_d": "",
            "prompts": "",
        }
    result = {
        "master": validate_master_config(paths.get("master", "")),
        "blogs_d": validate_blog_defs(paths.get("blogs_d", "")),
        "prompts": validate_prompts_config(paths.get("prompts", "")),
    }
    # Phase 61: 통합 스키마 non-blocking 보고서 (기존 3개 키에 추가, 동작 불변)
    result["standard"] = validate_standard_blog_defs(paths.get("blogs_d", ""))
    return result
