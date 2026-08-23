"""scripts/test_parser_upgrade.py — Fix 3 parser 교체 검증 (plain assert).

- block-style `tags:` 리스트 → 정상 파싱 (FM-MISSINGKEYS FALSE-POSITIVE 해소)
- inline `tags: [a, b]` → 기존과 동일 (문자열 보관, 호출부 호환)
- frontmatter 없는 파일 → (None, {})
- adventure-hugo 샘플 → tags 존재 → 누락 아님
"""
from __future__ import annotations

from ops_dashboard.checks.content_integrity import _parse_frontmatter

REQUIRED_KEYS = ["title", "description", "date", "slug", "tags"]


def _block_post() -> str:
    return """---
title: "여행 코스 추천"
date: "2026-08-20"
slug: "travel-course"
description: "설명"
tags:
  - 강릉
  - 여행
  - 코스
draft: true
---

본문.
"""


def _inline_post() -> str:
    return """---
title: "인라인"
tags: [a, b]
---

본문.
"""


def _no_fm() -> str:
    return "본문만.\n"


def test_block_style_tags_present():
    _, fm = _parse_frontmatter(_block_post())
    tags = fm.get("tags", "")
    assert tags, "block-style tags 가 빈값으로 파싱됨 (FALSE-POSITIVE 원인)"
    # 호출부 호환: 문자열이고 비어있지 않음
    assert isinstance(tags, str) and tags.strip()


def test_block_tags_not_flagged_missing():
    _, fm = _parse_frontmatter(_block_post())
    missing = [k for k in REQUIRED_KEYS if not (fm.get(k) or "").strip()]
    assert "tags" not in missing, f"tags 가 누락으로 오탐: {missing}"


def test_draft_bool_normalized_to_string():
    _, fm = _parse_frontmatter(_block_post())
    # 호출부 `.get('draft') or ''` + `.strip().lower()` 호환
    assert isinstance(fm.get("draft"), str)
    assert fm.get("draft") == "true"


def test_inline_tags_unchanged_shape():
    _, fm = _parse_frontmatter(_inline_post())
    assert fm.get("tags") == "[a, b]" or "a" in fm.get("tags", "")


def test_no_frontmatter_returns_empty():
    fm_text, fm = _parse_frontmatter(_no_fm())
    assert fm_text is None
    assert fm == {}


def test_adventure_sample_no_false_positive():
    # adventure-hugo 스타일 block-style tags
    sample = """---
title: "어드벤처 가이드"
description: "설명"
date: "2026-08-15"
slug: "adventure-guide"
categories:
  - 액티비티
tags:
  - 모험
  - 가이드
---

본문.
"""
    _, fm = _parse_frontmatter(sample)
    missing = [k for k in REQUIRED_KEYS if not (fm.get(k) or "").strip()]
    assert "tags" not in missing, f"adventure 샘플 tags 오탐: {missing}"


if __name__ == "__main__":
    test_block_style_tags_present()
    test_block_tags_not_flagged_missing()
    test_draft_bool_normalized_to_string()
    test_inline_tags_unchanged_shape()
    test_no_frontmatter_returns_empty()
    test_adventure_sample_no_false_positive()
    print("test_parser_upgrade: PASS")
