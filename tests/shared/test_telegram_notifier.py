import pytest
from unittest.mock import patch, MagicMock


@patch("shared.telegram_notifier.BOT_TOKEN", "")
@patch("shared.telegram_notifier.CHAT_ID", "")
class TestSendMissingCredentials:
    def test_missing_token_returns_false(self):
        from shared.telegram_notifier import send
        result = send("test message")
        assert result is False


class TestSendWithCredentials:
    @pytest.fixture(autouse=True)
    def setup_patches(self):
        with patch("shared.telegram_notifier.BOT_TOKEN", "test_token"), \
             patch("shared.telegram_notifier.CHAT_ID", "test_chat"), \
             patch("shared.telegram_notifier.API_URL", "https://api.telegram.org/bottest_token/sendMessage"):
            yield

    @patch("shared.telegram_notifier.requests.post")
    def test_send_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        from shared.telegram_notifier import send
        result = send("hello")
        assert result is True
        mock_post.assert_called_once()

    @patch("shared.telegram_notifier.requests.post")
    def test_send_api_failure(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_post.return_value = mock_resp
        from shared.telegram_notifier import send
        result = send("hello")
        assert result is False

    @patch("shared.telegram_notifier.requests.post")
    def test_send_exception(self, mock_post):
        from requests import RequestException
        mock_post.side_effect = RequestException("connection error")
        from shared.telegram_notifier import send
        result = send("hello")
        assert result is False


class TestSendError:
    def test_silent_reasons_return_false(self):
        with patch("shared.telegram_notifier.BOT_TOKEN", "test_token"), \
             patch("shared.telegram_notifier.CHAT_ID", "test_chat"):
            from shared.telegram_notifier import send_error
            result = send_error("test-blog", "publish", "daily_quota_exceeded")
            assert result is False

    def test_silent_reasons_variants(self):
        with patch("shared.telegram_notifier.BOT_TOKEN", "test_token"), \
             patch("shared.telegram_notifier.CHAT_ID", "test_chat"):
            from shared.telegram_notifier import send_error
            for reason in ["quota_met", "quota_exceeded", "daily_quota"]:
                result = send_error("test-blog", "publish", reason)
                assert result is False, f"Failed for reason: {reason}"

    def test_non_silent_reason(self):
        with patch("shared.telegram_notifier.BOT_TOKEN", "test_token"), \
             patch("shared.telegram_notifier.CHAT_ID", "test_chat"), \
             patch("shared.telegram_notifier.send", return_value=True):
            from shared.telegram_notifier import send_error
            result = send_error("test-blog", "publish", "real_error")
            assert result is True
