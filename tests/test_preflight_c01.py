"""tests/test_preflight_c01.py — 64-01 preflight C01 gap

3 cases: curve single \u2018, curve double \u201c, normal straight quote.
C01 severity MAJOR => blocked=False warn-only.
Plus grep checks for C01 presence and docstring.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import dispatcher


def _make_blog(tmp_root: Path, blog_id: str = "test-preflight-c01-hugo"):
    site_path = tmp_root / blog_id
    posts_dir = site_path / "content" / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)
    return site_path, posts_dir, blog_id


def _write_post(posts_dir: Path, slug: str, content: str):
    d = posts_dir / slug
    d.mkdir(parents=True, exist_ok=True)
    f = d / "index.md"
    f.write_text(content, encoding="utf-8")
    # ensure mtime within 7d window
    now = time.time()
    # touch file and dir
    import os
    os.utime(f, (now, now))
    os.utime(d, (now, now))
    return f


def _valid_frontmatter(title="Test Title", slug="test-slug"):
    return f"""---
title: "{title}"
slug: "{slug}"
date: 2026-08-20
categories: ["test"]
tags: ["test"]
---
Body content here.
"""


def _run_preflight(posts_dir, blog_id, site_path):
    cfg = {"id": blog_id, "site_path": str(site_path)}
    with patch.object(dispatcher, "_load_all_blogs", return_value={"blogs": [cfg]}):
        result = dispatcher.preflight_check(blog_id)
    return result


def test_c01_curve_single_detected_warn_only():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        site_path, posts_dir, blog_id = _make_blog(tmp_root)
        # \u2018 = left single curly
        content = _valid_frontmatter(title="Test \u2018single\u2019 title")
        # content contains curved single quote in frontmatter
        _write_post(posts_dir, "post-single", content)
        result = _run_preflight(posts_dir, blog_id, site_path)
        c01 = [v for v in result["violations"] if v["rule_id"] == "C01"]
        assert len(c01) >= 1, f"expected C01 violation for \\u2018, got {result['violations']}"
        assert c01[0]["severity"] == "MAJOR"
        assert result["blocked"] is False, "C01 MAJOR should be warn-only, blocked=False"


def test_c01_curve_double_detected_warn_only():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        site_path, posts_dir, blog_id = _make_blog(tmp_root)
        # \u201c = left double curly
        content = _valid_frontmatter(title="Test \u201cdouble\u201d title")
        _write_post(posts_dir, "post-double", content)
        result = _run_preflight(posts_dir, blog_id, site_path)
        c01 = [v for v in result["violations"] if v["rule_id"] == "C01"]
        assert len(c01) >= 1, f"expected C01 violation for \\u201c, got {result['violations']}"
        assert c01[0]["severity"] == "MAJOR"
        assert result["blocked"] is False


def test_c01_normal_straight_no_violation():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        site_path, posts_dir, blog_id = _make_blog(tmp_root)
        # normal straight quotes ' and " should NOT trigger C01
        content = _valid_frontmatter(title="Test 'single' and \"double\" title")
        _write_post(posts_dir, "post-normal", content)
        result = _run_preflight(posts_dir, blog_id, site_path)
        c01 = [v for v in result["violations"] if v["rule_id"] == "C01"]
        assert len(c01) == 0, f"normal straight quotes should not trigger C01, got {c01}"


def test_c01_grep_presence():
    src = Path("dispatcher.py").read_text(encoding="utf-8", errors="replace")
    assert "C01" in src, "dispatcher.py must contain C01"
    # check docstring contains C01
    assert "C01" in (dispatcher.preflight_check.__doc__ or ""), "docstring must mention C01"


def test_hugo_writer_etap_locale_uses_detect():
    src = Path("shared/publishers/hugo_writer.py").read_text(encoding="utf-8", errors="replace")
    # find line with after_generation_etap
    found = False
    for line in src.splitlines():
        if "after_generation_etap" in line and "_detect_locale" in line:
            found = True
            break
    assert found, "hugo_writer line with after_generation_etap must contain _detect_locale"
