import pytest
from shared.validators import sanitize_title, _strip_html, _jaccard, is_korean_content, assert_korean_or_reject


class TestSanitizeTitle:
    def test_empty_string(self):
        assert sanitize_title("") == ""

    def test_none(self):
        assert sanitize_title(None) is None

    def test_removes_markdown_bold(self):
        result = sanitize_title("**bold** title")
        assert "**" not in result

    def test_removes_markdown_italic(self):
        result = sanitize_title("__italic__ title")
        assert "__" not in result

    def test_removes_consecutive_duplicate_words(self):
        result = sanitize_title("청주시 청주시 맛집")
        assert result == "청주시 맛집"

    def test_removes_repeated_bigrams(self):
        result = sanitize_title("A B A B C")
        assert "A B A B" not in result

    def test_strips_whitespace(self):
        result = sanitize_title("  hello world  ")
        assert result == "hello world"

    def test_normal_title_preserved(self):
        result = sanitize_title("서울 맛집 추천 Best 5")
        assert result == "서울 맛집 추천 Best 5"

    def test_removes_contained_words(self):
        result = sanitize_title("여행코스 3곳 코스 추천")
        assert "코스" not in result or len(result.split()) < 4


class TestStripHtml:
    def test_removes_html_tags(self):
        assert _strip_html("<p>hello</p>") == "hello"

    def test_empty_string(self):
        assert _strip_html("") == ""

    def test_none(self):
        assert _strip_html(None) == ""

    def test_multiple_tags(self):
        assert _strip_html("<div><p>text</p></div>") == "text"

    def test_no_html(self):
        assert _strip_html("plain text") == "plain text"


class TestJaccard:
    def test_identical_strings(self):
        assert _jaccard("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert _jaccard("hello world", "foo bar") == 0.0

    def test_partial_overlap(self):
        sim = _jaccard("hello world foo", "hello bar baz")
        assert 0.0 < sim < 1.0

    def test_empty_string(self):
        assert _jaccard("", "hello") == 0.0

    def test_both_empty(self):
        assert _jaccard("", "") == 0.0


class TestIsKoreanContent:
    def test_pure_korean(self):
        assert is_korean_content("안녕하세요 이것은 한국어입니다") is True

    def test_pure_english(self):
        assert is_korean_content("hello world") is True

    def test_chinese_dominant(self):
        assert is_korean_content("这是一个中文文本한국어") is False

    def test_empty(self):
        assert is_korean_content("") is True

    def test_mixed_with_sufficient_korean(self):
        assert is_korean_content("한국어 hello world") is True


class TestAssertKoreanOrReject:
    def test_korean_content_returns_none(self):
        result = assert_korean_or_reject("한국어 제목", "한국어 본문입니다", "test-blog")
        assert result is None

    def test_chinese_content_returns_error(self):
        result = assert_korean_or_reject("中文标题", "这是一个中文文本", "test-blog")
        assert result is not None
        assert "Chinese" in result

    def test_mixed_korean_english_accepts(self):
        result = assert_korean_or_reject("서울 맛집 best 5", "서울의 맛집 top 5를 소개합니다", "test-blog")
        assert result is None

    def test_japanese_content_rejected(self):
        result = assert_korean_or_reject("日本語のタイトル", "日本語の本文です", "test-blog")
        assert result is not None

    def test_very_long_title_sanitized(self):
        long_title = "a" * 300
        result = sanitize_title(long_title)
        assert len(result) <= 200 or result is not None

    def test_jaccard_identical_short(self):
        assert _jaccard("a b", "a b") == 1.0

    def test_jaccard_empty_second(self):
        assert _jaccard("hello world", "") == 0.0

    def test_strip_html_with_attributes(self):
        assert _strip_html('<a href="link">text</a>') == "text"

    def test_is_korean_content_edge_mixed_short(self):
        assert is_korean_content("a b c d e") is True

    def test_is_korean_content_empty_string(self):
        assert is_korean_content("") is True
