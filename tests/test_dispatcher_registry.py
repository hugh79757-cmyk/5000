"""Verify dispatcher registry resolves all known blog IDs to callable modules."""

import glob
import os
import importlib
import yaml

import pytest

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def _load_all_blogs():
    main_path = os.path.join(CONFIG_DIR, "blogs.yaml")
    with open(main_path) as f:
        config = yaml.safe_load(f) or {}
    if "blogs" not in config:
        config["blogs"] = []
    blogs_d = os.path.join(CONFIG_DIR, "blogs.d")
    if os.path.isdir(blogs_d):
        for fpath in sorted(glob.glob(os.path.join(blogs_d, "*.yaml"))):
            with open(fpath) as f:
                data = yaml.safe_load(f) or {}
            config["blogs"].extend(data.get("blogs", []))
    return config


def _pipeline_module_path(blog_id, pipeline):
    ETAP_BLOG_EXCEPTIONS = {
        "flights-hugo": "pipelines.etap.flight_pipeline",
    }
    if pipeline == "etap":
        if blog_id in ETAP_BLOG_EXCEPTIONS:
            return ETAP_BLOG_EXCEPTIONS[blog_id]
        stem = blog_id.replace("-hugo", "")
        return f"pipelines.etap.{stem}_pipeline"
    if pipeline in ("tap", "stock"):
        return None
    return f"pipelines.{pipeline}.pipeline"


def test_all_active_blogs_resolve():
    config = _load_all_blogs()
    blogs = [b for b in config.get("blogs", []) if b.get("status") == "active"]
    assert len(blogs) > 0, "No active blogs found"

    unresolved = []
    for blog in blogs:
        blog_id = blog["id"]
        pipeline = blog.get("pipeline", "")
        if not pipeline or pipeline in ("tap", "stock"):
            continue
        module_path = _pipeline_module_path(blog_id, pipeline)
        if not module_path:
            unresolved.append((blog_id, "no module path"))
            continue
        try:
            mod = importlib.import_module(module_path)
        except ModuleNotFoundError as e:
            unresolved.append((blog_id, str(e)))
            continue
        if not hasattr(mod, "run") or not callable(mod.run):
            unresolved.append((blog_id, f"{module_path} has no callable run()"))

    assert not unresolved, f"Unresolved blogs: {unresolved}"
