import pytest
from unittest.mock import patch, MagicMock

LONG_KOREAN_TEXT = "한국어 텍스트입니다. 이 글은 인공지능이 생성한 블로그 포스트입니다. " * 10
HUMANIZED_TEXT = ("다듬어진 한국어 텍스트입니다. 이 글은 인공지능이 생성한 블로그 포스트입니다. " * 10).rstrip()


class TestHumanizeKorean:
    @patch("shared.humanizer._ai_generate")
    def test_empty_body_returns_as_is(self, mock_generate):
        from shared.humanizer import humanize_korean
        result = humanize_korean("", "test-blog")
        assert result == ""
        mock_generate.assert_not_called()

    @patch("shared.humanizer._ai_generate")
    def test_whitespace_body_returns_as_is(self, mock_generate):
        from shared.humanizer import humanize_korean
        result = humanize_korean("   \n  ", "test-blog")
        assert result == "   \n  "
        mock_generate.assert_not_called()

    @patch("shared.humanizer._ai_generate")
    def test_english_dominant_body_skips(self, mock_generate):
        from shared.humanizer import humanize_korean
        body = "Hello world, this is an English text with some " * 10
        result = humanize_korean(body, "test-blog")
        assert result == body
        mock_generate.assert_not_called()

    @patch("shared.humanizer._ai_generate")
    def test_korean_body_calls_generate(self, mock_generate):
        mock_generate.return_value = {"content": HUMANIZED_TEXT}
        from shared.humanizer import humanize_korean
        result = humanize_korean(LONG_KOREAN_TEXT, "test-blog", title="제목")
        assert result == HUMANIZED_TEXT
        mock_generate.assert_called_once()

    @patch("shared.humanizer._ai_generate")
    def test_generate_returns_none_keeps_original(self, mock_generate):
        mock_generate.return_value = {}
        from shared.humanizer import humanize_korean
        result = humanize_korean(LONG_KOREAN_TEXT, "test-blog")
        assert result == LONG_KOREAN_TEXT

    @patch("shared.humanizer._ai_generate")
    def test_generate_raises_exception_keeps_original(self, mock_generate):
        mock_generate.side_effect = Exception("API error")
        from shared.humanizer import humanize_korean
        result = humanize_korean(LONG_KOREAN_TEXT, "test-blog")
        assert result == LONG_KOREAN_TEXT

    @patch("shared.humanizer._ai_generate")
    def test_too_short_result_keeps_original(self, mock_generate):
        mock_generate.return_value = {"content": "짧은 텍스트"}
        from shared.humanizer import humanize_korean
        result = humanize_korean(LONG_KOREAN_TEXT, "test-blog")
        assert result == LONG_KOREAN_TEXT

    @patch("shared.humanizer._ai_generate")
    def test_strips_codeblock_wrapper(self, mock_generate):
        mock_generate.return_value = {"content": f"```markdown\n{HUMANIZED_TEXT}\n```"}
        from shared.humanizer import humanize_korean
        result = humanize_korean(LONG_KOREAN_TEXT, "test-blog")
        assert "```" not in result
        assert HUMANIZED_TEXT in result

    @patch("shared.humanizer._ai_generate")
    def test_title_included_in_prompt(self, mock_generate):
        mock_generate.return_value = {"content": HUMANIZED_TEXT}
        from shared.humanizer import humanize_korean
        humanize_korean(LONG_KOREAN_TEXT, "test-blog", title="테스트 제목")
        call_args = mock_generate.call_args[1]
        assert "테스트 제목" in call_args["user_prompt"]
