import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.etap.quality_guard import postprocess_content

_LONG_CONTENT = (
    "## Section One\n\n"
    + ("This is a sufficiently long article body used for freshness gate testing. " * 25)
    + "\n\n## Section Two\n\n"
    + ("Another paragraph with more words to satisfy the word count minimum requirement. " * 25)
    + "\n\n## Section Three\n\n"
    + ("Final paragraph ensuring the article has enough unique text for the quality gate. " * 25)
)


def test_dynamic_stale_blocks():
    fm = {"lastmod": "2020-01-01T00:00:00+00:00"}
    content, issues, is_draft = postprocess_content(
        content=_LONG_CONTENT, front_matter=fm, content_type="deals"
    )
    assert is_draft is True
    assert any("Content stale" in i for i in issues), issues


def test_static_passes():
    fm = {"lastmod": "2020-01-01T00:00:00+00:00"}
    content, issues, is_draft = postprocess_content(
        content=_LONG_CONTENT, front_matter=fm, content_type="senior"
    )
    assert is_draft is False
    assert not any("Content stale" in i for i in issues), issues


def test_missing_lastmod_skips():
    content, issues, is_draft = postprocess_content(
        content=_LONG_CONTENT, front_matter={}, content_type="deals"
    )
    assert is_draft is False
    assert not any("Content stale" in i for i in issues), issues
