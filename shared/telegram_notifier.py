import logging
import os

import requests

logger = logging.getLogger(__name__)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_URL = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
DASHBOARD_URL = os.environ.get("OPS_DASHBOARD_URL", "http://localhost:5060")


def _audit_delivery(event_id, message, delivered, message_id="", http_status=None, detail=""):
    try:
        from shared.publish_error_events import record_telegram_delivery
        record_telegram_delivery(
            event_id, message, delivered=delivered,
            telegram_message_id=message_id, http_status=http_status, detail=detail,
        )
        if not delivered:
            from shared.publish_error_events import record_publish_error
            record_publish_error(
                "ops-dashboard", "notification", detail or "telegram delivery failure",
                problem_id="P31",
            )
    except Exception:
        pass


def send(message, parse_mode="HTML", audit_event_id=None):
    """Send one Telegram message and save a redacted delivery audit."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram credentials missing")
        _audit_delivery(audit_event_id, message, False, detail="credentials missing")
        return False
    try:
        response = requests.post(
            API_URL,
            json={"chat_id": CHAT_ID, "text": message, "parse_mode": parse_mode},
            timeout=10,
        )
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = {}
        delivered = response.status_code == 200 and bool(payload.get("ok", True))
        result = payload.get("result") or {}
        message_id = result.get("message_id", "")
        detail = "" if delivered else str(payload.get("description") or response.text[:240])
        _audit_delivery(audit_event_id, message, delivered, message_id, response.status_code, detail)
        if delivered:
            return True
        logger.warning("Telegram send failed: %s", response.status_code)
        return False
    except requests.RequestException as exc:
        logger.exception("[TELEGRAM_ERROR] Request failed: %s", exc)
        _audit_delivery(audit_event_id, message, False, detail=str(exc))
        return False


def _record_event(blog_id, stage, error_msg, **kwargs):
    try:
        from shared.publish_error_events import record_publish_error
        return record_publish_error(blog_id, stage, error_msg, **kwargs)
    except Exception:
        return {}


def _blog_metadata(blog_id):
    try:
        from pathlib import Path
        import yaml
        blogs_d = Path(__file__).parent.parent / "config" / "blogs.d"
        for config_path in sorted(blogs_d.glob("*.yaml")) if blogs_d.is_dir() else []:
            with open(config_path, encoding="utf-8") as source:
                for blog in (yaml.safe_load(source) or {}).get("blogs", []):
                    if blog and blog.get("id") == blog_id:
                        return blog.get("domain", ""), blog.get("repo", "")
    except Exception as exc:
        logger.warning("Could not resolve blog metadata: %s", exc)
    return "", ""


def send_error(blog_id, stage="", error_msg=""):
    """Send one publish error and persist a structured operational event."""
    silent_reasons = (
        "quota_met",
        "quota_exceeded",
        "daily_quota_exceeded",
        "daily_quota",
        # post_validator 의 "정상" WARNING 마커 ("생략 — 정상") — 발송 백스톱 드롭
        "생략 — 정상",
    )
    if any(reason in str(error_msg).lower() for reason in silent_reasons):
        logger.info("[Silent] %s/%s: %s", blog_id, stage, error_msg)
        return False
    event = _record_event(blog_id, stage, error_msg, reason=stage)
    domain, repo = _blog_metadata(blog_id)
    lines = ["[PUBLISH ERROR]", "Blog: " + blog_id]
    if domain:
        lines.append("Domain: " + domain)
    if repo:
        lines.append("Repo: " + repo)
    lines.append("Stage: " + stage)
    if event:
        lines.append("Code: " + event["problem_id"])
    lines.append("Error: " + str(error_msg)[:500])
    return send("\n".join(lines), audit_event_id=event.get("event_id"))


def send_daily_report(report_text):
    return send(report_text)


def send_validation(blog_id, title, url, validation):
    """Send post-publish validation findings and preserve a structured event."""
    if validation.get("passed", False):
        return False
    issues = validation.get("issues", [])
    if not issues:
        return False
    details = "; ".join(str(item.get("check", "")) + ": " + str(item.get("msg", "")) for item in issues)
    event = _record_event(blog_id, "validation", str(title) + ": " + details, reason="validation")
    lines = ["[PUBLISH VALIDATION]", "Blog: " + blog_id, "Title: " + str(title)[:80]]
    if url:
        lines.append("URL: " + url)
    for item in issues:
        lines.append("- " + str(item.get("check", "")) + ": " + str(item.get("msg", "")))
    return send("\n".join(lines), audit_event_id=event.get("event_id"))


def send_no_result_alert(blog_id, failure_count):
    event = _record_event(
        blog_id, "result_parse", "no eligible source data",
        reason="source_exhausted", attempt=failure_count,
    )
    text = "[CONSECUTIVE NO-RESULT]\nBlog: " + blog_id
    text += "\nFailures: " + str(failure_count)
    text += "\nAction: Check source inventory and source pipeline."
    return send(text, audit_event_id=event.get("event_id"))


def send_dashboard_alert(blog_id, check_name, status, detail):
    """Send an existing dashboard check alert with its detail-page link."""
    url = DASHBOARD_URL + "/blog/" + blog_id
    message = (
        "[OPS ALERT]\n"
        "Blog: " + blog_id + "\n"
        "Check: " + check_name + "\n"
        "Status: " + status + "\n"
        "Detail: " + detail + "\n"
        "Dashboard: " + url
    )
    return send(message)


def send_standard_violation(blog_id, rule_id, severity, detail):
    """Send a standard-compliance alert only for a critical violation."""
    if severity != "CRITICAL":
        return None
    url = DASHBOARD_URL + "/blog/" + blog_id
    message = (
        "[STANDARD VIOLATION]\n"
        "Blog: " + blog_id + "\n"
        "Rule: " + rule_id + " (" + severity + ")\n"
        "Detail: " + detail + "\n"
        "Dashboard: " + url
    )
    return send(message)
