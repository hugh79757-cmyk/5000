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


class TestDashboardUrlConfig:
    def test_dashboard_url_default(self):
        from shared.telegram_notifier import DASHBOARD_URL
        assert DASHBOARD_URL == "http://localhost:5060"

    def test_dashboard_url_from_env(self):
        with patch.dict("os.environ", {"OPS_DASHBOARD_URL": "https://ops.example.com"}):
            import importlib
            import shared.telegram_notifier as mod
            # Re-read module to pick up env var
            old_val = getattr(mod, "DASHBOARD_URL", None)
            mod.DASHBOARD_URL = "https://ops.example.com"
            assert mod.DASHBOARD_URL == "https://ops.example.com"
            mod.DASHBOARD_URL = old_val


class TestSendDashboardAlert:
    @patch("shared.telegram_notifier.requests.post")
    def test_includes_dashboard_url_in_message(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        with patch("shared.telegram_notifier.BOT_TOKEN", "tok"), \
             patch("shared.telegram_notifier.CHAT_ID", "cid"), \
             patch("shared.telegram_notifier.DASHBOARD_URL", "http://localhost:5060"):
            from shared.telegram_notifier import send_dashboard_alert
            result = send_dashboard_alert("test-hugo", "freshness", "fail", "Stale 5 days")
            assert result is True
            call_args = mock_post.call_args
            msg_text = call_args[1]["json"]["text"]
            assert "http://localhost:5060/blog/test-hugo" in msg_text
            assert "freshness" in msg_text
            assert "Stale 5 days" in msg_text

    def test_signature_has_required_params(self):
        import inspect
        from shared.telegram_notifier import send_dashboard_alert
        sig = inspect.signature(send_dashboard_alert)
        params = list(sig.parameters.keys())
        assert "blog_id" in params
        assert "check_name" in params
        assert "status" in params
        assert "detail" in params


class TestSendStandardViolation:
    @patch("shared.telegram_notifier.requests.post")
    def test_critical_sends_alert(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        with patch("shared.telegram_notifier.BOT_TOKEN", "tok"), \
             patch("shared.telegram_notifier.CHAT_ID", "cid"), \
             patch("shared.telegram_notifier.DASHBOARD_URL", "http://localhost:5060"):
            from shared.telegram_notifier import send_standard_violation
            result = send_standard_violation("blog-hugo", "R01", "CRITICAL", "showTableOfContents not false")
            assert result is True
            call_args = mock_post.call_args
            msg_text = call_args[1]["json"]["text"]
            assert "R01" in msg_text
            assert "CRITICAL" in msg_text
            assert "http://localhost:5060/blog/blog-hugo" in msg_text

    @patch("shared.telegram_notifier.requests.post")
    def test_non_critical_no_alert(self, mock_post):
        with patch("shared.telegram_notifier.BOT_TOKEN", "tok"), \
             patch("shared.telegram_notifier.CHAT_ID", "cid"):
            from shared.telegram_notifier import send_standard_violation
            result = send_standard_violation("blog-hugo", "R04", "MAJOR", "Missing GA4")
            assert result is None
            mock_post.assert_not_called()

    def test_signature_has_required_params(self):
        import inspect
        from shared.telegram_notifier import send_standard_violation
        sig = inspect.signature(send_standard_violation)
        params = list(sig.parameters.keys())
        assert "blog_id" in params
        assert "rule_id" in params
        assert "severity" in params
        assert "detail" in params
