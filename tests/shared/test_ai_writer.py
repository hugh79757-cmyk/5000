import pytest
from unittest.mock import patch, MagicMock


class TestIsTruncated:
    """BUG-001: reasoning_content/응답 절단 감지 — _is_truncated 검증."""

    def test_finish_reason_length_detects(self):
        from shared.ai_writer import _is_truncated
        assert _is_truncated("정상처럼 보이는 내용", "length") is True

    def test_trailing_json_comma_detects(self):
        from shared.ai_writer import _is_truncated
        assert _is_truncated('{"key": "value",') is True

    def test_trailing_colon_detects(self):
        from shared.ai_writer import _is_truncated
        assert _is_truncated('{"key":') is True

    def test_trailing_open_brace_detects(self):
        from shared.ai_writer import _is_truncated
        assert _is_truncated('{"key": "value", "nested": {') is True

    def test_trailing_double_quote_detects(self):
        from shared.ai_writer import _is_truncated
        assert _is_truncated('"image_prompt": "Overhead panoramic view') is False  # 마지막이 일반 문자

    def test_unclosed_json_object_detects(self):
        """BUG-001 재현 케이스: 문자열 도중 절단 — {로 시작하고 }가 부족하면 절단."""
        from shared.ai_writer import _is_truncated
        # 742자 재현: "image_prompt": "Overhead panoramic view... 문자열 도중 절단
        assert _is_truncated('{"title": "test", "image_prompt": "Overhead panoramic view') is True
        assert _is_truncated('{"a": 1, "b": [1, 2') is True

    def test_unclosed_json_array_detects(self):
        from shared.ai_writer import _is_truncated
        assert _is_truncated('[{"a": 1}, {"b": 2') is True

    def test_closed_json_not_truncated(self):
        from shared.ai_writer import _is_truncated
        assert _is_truncated('{"title": "test"}') is False
        assert _is_truncated('[{"a": 1}, {"b": 2}]') is False

    def test_normal_korean_text_not_truncated(self):
        from shared.ai_writer import _is_truncated
        assert _is_truncated("이 글은 정상적으로 끝났습니다.", "stop") is False

    def test_empty_or_none_not_truncated(self):
        from shared.ai_writer import _is_truncated
        assert _is_truncated("") is False
        assert _is_truncated(None) is False

    def test_whitespace_only_not_truncated(self):
        from shared.ai_writer import _is_truncated
        assert _is_truncated("   \n  ") is False

    def test_plain_text_starting_with_brace_not_truncated_if_closed(self):
        from shared.ai_writer import _is_truncated
        # 마크다운 코드블록 예시처럼 { 로 시작하지만 균형 잡힌 경우
        assert _is_truncated("{균형 잡힌 중괄호} 텍스트") is False


class TestReasoningContentFallback:
    """BUG-001: content 비어있으면 reasoning_content에서 추출하는 경로 검증."""

    def _make_response(self, content, reasoning_content, finish_reason="stop"):
        """OpenAI 응답 객체 모사."""
        message = MagicMock()
        message.content = content
        message.reasoning_content = reasoning_content
        choice = MagicMock()
        choice.message = message
        choice.finish_reason = finish_reason
        response = MagicMock()
        response.choices = [choice]
        response.usage = MagicMock(total_tokens=100)
        return response

    @patch("shared.ai_writer.get_client")
    @patch("shared.ai_writer.load_models_config")
    def test_reasoning_content_extracted_when_content_empty(self, mock_config, mock_client):
        from shared.ai_writer import generate
        # 모델 설정: default tier 하나만 사용
        mock_config.return_value = {
            "default": {"model": "test-model", "provider": "test", "max_tokens": 100},
            "providers": {"test": {"api_key_env": "TEST_KEY", "base_url": "http://x"}},
        }
        with patch("shared.ai_writer.os.getenv", return_value="fake-key"):
            client = MagicMock()
            client.chat.completions.create.return_value = self._make_response(
                content=None, reasoning_content='{"title": "정상 JSON"}'
            )
            mock_client.return_value = client
            result = generate("sys", "user", temperature=0.7)
        assert result["content"] == '{"title": "정상 JSON"}'

    @patch("shared.ai_writer.get_client")
    @patch("shared.ai_writer.load_models_config")
    def test_truncated_reasoning_content_retries_with_more_tokens(self, mock_config, mock_client):
        """BUG-001 재현: reasoning_content가 절단된 채 반환 → 재시도로 정상 응답 획득."""
        from shared.ai_writer import generate
        mock_config.return_value = {
            "default": {"model": "test-model", "provider": "test", "max_tokens": 100},
            "providers": {"test": {"api_key_env": "TEST_KEY", "base_url": "http://x"}},
        }
        with patch("shared.ai_writer.os.getenv", return_value="fake-key"):
            client = MagicMock()
            # 1차: 절단된 reasoning_content (BUG-001 재현), 2차: 정상
            client.chat.completions.create.side_effect = [
                self._make_response(
                    content=None,
                    reasoning_content='{"title": "test", "image_prompt": "Overhead panoramic view',
                ),
                self._make_response(content='{"title": "정상 완료"}', reasoning_content=None),
            ]
            mock_client.return_value = client
            result = generate("sys", "user", temperature=0.7)
        assert result["content"] == '{"title": "정상 완료"}'
        # max_tokens 증분되어 재호출되었는지 확인
        create = client.chat.completions.create
        assert create.call_count == 2
        first_kwargs = create.call_args_list[0].kwargs
        second_kwargs = create.call_args_list[1].kwargs
        assert second_kwargs["max_tokens"] > first_kwargs["max_tokens"]
