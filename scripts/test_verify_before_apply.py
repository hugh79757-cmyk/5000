"""scripts/test_verify_before_apply.py — BLK-6 단위 검증 (plain assert)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import ops_dashboard.verify_before_apply as va


def _make_post(content: str) -> str:
    d = Path(tempfile.mkdtemp(prefix="vba_"))
    p = d / "post.md"
    p.write_text(content, encoding="utf-8")
    return str(p)


POST = """---
title: "테스트"
date: "2026-08-22"
slug: "test"
tags: ["x"]
---

본문입니다.
"""


def _add_description(content: str) -> str:
    # description 키 추가 (안전 fixer)
    return content.replace("title: ", "description: \"요약\"\ntitle: ", 1)


def _delete_all(content: str) -> str:
    return ""


def _remove_title(content: str) -> str:
    return "\n".join(l for l in content.splitlines() if not l.startswith("title:"))


def _strip_nonascii(content: str) -> str:
    return content.encode("ascii", "ignore").decode("ascii")


def test_safe_fixer():
    p = _make_post(POST)
    r = va.dry_apply("b1", p, "FM-MISSINGKEYS", _add_description)
    assert r.safe_to_apply is True, r.side_effects
    assert any("description" in l for l in r.diff_lines)


def test_original_unchanged():
    p = _make_post(POST)
    before = Path(p).read_text(encoding="utf-8")
    va.dry_apply("b1", p, "FM-MISSINGKEYS", _add_description)
    after = Path(p).read_text(encoding="utf-8")
    assert before == after  # 원본 수정 금지


def test_malicious_deletes_all():
    p = _make_post(POST)
    r = va.dry_apply("b1", p, "FM-MISSINGKEYS", _delete_all)
    assert r.safe_to_apply is False
    assert any(s.startswith("file_size_delta_>50%") for s in r.side_effects)


def test_key_removal_detected():
    p = _make_post(POST)
    r = va.dry_apply("b1", p, "FM-MISSINGKEYS", _remove_title)
    assert r.safe_to_apply is False
    assert any(s.startswith("unexpected_field_removed:title") for s in r.side_effects)


def test_encoding_change_detected():
    p = _make_post(POST)
    r = va.dry_apply("b1", p, "FM-MISSINGKEYS", _strip_nonascii)
    assert r.safe_to_apply is False
    assert "encoding_changed" in r.side_effects


if __name__ == "__main__":
    test_safe_fixer()
    test_original_unchanged()
    test_malicious_deletes_all()
    test_key_removal_detected()
    test_encoding_change_detected()
    print("test_verify_before_apply: PASS")
