"""scripts/test_fix_draft.py — Fix 2 glob 확장 검증 (temp site, 실제 블로그 미수정).

- flat 파일 (content/posts/<name>.md) draft:true → 제거
- 디렉터리형 (content/posts/<slug>/index.md) draft:true → 제거
- _index.md (Hugo 섹션) → 무시 (미변경)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import frontmatter

from shared.autofix.fix_draft_true import _iter_posts, fix_draft_true


def _build_site() -> Path:
    root = Path(tempfile.mkdtemp(prefix="fixdraft_"))
    posts = root / "content" / "posts"
    posts.mkdir(parents=True)

    flat = posts / "flat-post.md"
    flat.write_text("---\ntitle: t\ndraft: true\n---\n\nbody\n", encoding="utf-8")

    idx = posts / "myslug" / "index.md"
    idx.parent.mkdir(parents=True)
    idx.write_text("---\ntitle: t\ndraft: true\n---\n\nbody\n", encoding="utf-8")

    section = posts / "_index.md"
    section.write_text("---\ntitle: section\ndraft: true\n---\n\nsec\n", encoding="utf-8")
    return root


def test_iter_includes_flat_and_index_excludes_section():
    root = _build_site()
    paths = _iter_posts(root)
    names = {p.name for p in paths}
    assert "flat-post.md" in names, names
    assert any(p.name == "index.md" and p.parent.name == "myslug" for p in paths)
    assert "_index.md" not in names, "section 파일이 순회에 포함됨"


def test_fix_removes_draft_flat_and_index():
    root = _build_site()
    ok, msg = fix_draft_true(root, "test-blog")
    assert ok is True
    flat = root / "content" / "posts" / "flat-post.md"
    assert "draft" not in frontmatter.load(flat).metadata, msg
    idx = root / "content" / "posts" / "myslug" / "index.md"
    assert "draft" not in frontmatter.load(idx).metadata, msg


def test_section_file_untouched():
    root = _build_site()
    fix_draft_true(root, "test-blog")
    section = root / "content" / "posts" / "_index.md"
    meta = frontmatter.load(section).metadata
    assert meta.get("draft") is True, "section _index.md 가 수정됨 (위험)"


if __name__ == "__main__":
    test_iter_includes_flat_and_index_excludes_section()
    test_fix_removes_draft_flat_and_index()
    test_section_file_untouched()
    print("test_fix_draft: PASS")
