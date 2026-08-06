import logging
import os

import requests

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_URL = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
DASHBOARD_URL = os.environ.get("OPS_DASHBOARD_URL", "http://localhost:5060")


def send(message, parse_mode="HTML") -> bool | None:
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram credentials missing")
        return False
    try:
        resp = requests.post(
            API_URL,
            json={
                "chat_id": CHAT_ID,
                "text": message,
                "parse_mode": parse_mode,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        logger.warning("Telegram send failed: " + str(resp.status_code))
        return False
    except requests.RequestException as e:
        logger.exception(f"[TELEGRAM_ERROR] Request failed: {e}")
        return False


def send_error(blog_id, stage, error_msg):
    # 정상 동작인 quota 초과는 알림 불필요 (로그에만 기록)
    _SILENT_REASONS = [
        "quota_met",
        "quota_exceeded",
        "daily_quota_exceeded",
        "daily_quota",
    ]
    _err_lower = str(error_msg).lower()
    if any(reason in _err_lower for reason in _SILENT_REASONS):
        logger.info(f"[Silent] {blog_id}/{stage}: {error_msg}")
        return False

    # blogs.d/*.yaml 전체에서 도메인, 레포 정보 가져오기
    domain = ""
    repo = ""
    try:
        from pathlib import Path

        import yaml

        config_dir = Path(__file__).parent.parent / "config"
        all_blogs = []
        blogs_d = config_dir / "blogs.d"
        if blogs_d.is_dir():
            for fpath in sorted(blogs_d.glob("*.yaml")):
                with open(fpath, encoding="utf-8") as yf:
                    data = yaml.safe_load(yf) or {}
                all_blogs.extend(data.get("blogs", []))
        for blog in all_blogs:
            if blog and blog.get("id") == blog_id:
                domain = blog.get("domain", "")
                repo = blog.get("repo", "")
                break
    except (OSError, yaml.YAMLError) as e:
        logger.exception(f"[CONFIG_ERROR] Failed to load blogs.d: {e}")

    text = "🚨 <b>발행 오류</b>\n"
    text += "<b>블로그:</b> " + blog_id + "\n"
    if domain:
        text += "<b>도메인:</b> " + domain + "\n"
    if repo:
        text += "<b>레포:</b> " + repo + "\n"
    text += "<b>단계:</b> " + stage + "\n"
    text += "<b>오류:</b> " + str(error_msg)[:500]
    return send(text)


def send_daily_report(report_text):
    return send(report_text)


def send_validation(blog_id: str, title: str, url: str, validation: dict):
    """발행 후 HTML 검증 결과 전송 (문제 있을 때만)"""
    if validation.get("passed", False):
        return False
    issues = validation.get("issues", [])
    if not issues:
        return False

    text = "🔍 <b>발행 품질 검증 실패</b>\n"
    text += f"<b>블로그:</b> {blog_id}\n"
    text += f"<b>제목:</b> {title[:80]}\n"
    if url:
        text += f"<b>URL:</b> {url}\n"
    for i in issues:
        emoji = "🔴" if i["severity"] == "ERROR" else "🟡"
        text += f"{emoji} <b>{i['check']}</b>: {i['msg']}\n"
    return send(text)


def send_no_result_alert(blog_id: str, failure_count: int):
    """no_result 연속 실패 알림 (에스컬레이션)"""
    text = "⚠️ <b>no_result 연속 실패</b>\n"
    text += f"<b>블로그:</b> {blog_id}\n"
    text += f"<b>연속 실패:</b> {failure_count}회\n"
    text += "<b>조치:</b> 데이터 수집 파이프라인 점검 필요"
    return send(text)


def send_dashboard_alert(blog_id: str, check_name: str, status: str, detail: str) -> bool | None:
    """Send alert with link to blog detail page on dashboard."""
    url = f"{DASHBOARD_URL}/blog/{blog_id}"
    msg = (
        f"🔴 <b>Ops Alert</b>\n"
        f"Blog: <code>{blog_id}</code>\n"
        f"Check: {check_name}\n"
        f"Status: {status}\n"
        f"Detail: {detail}\n"
        f"🔗 <a href=\"{url}\">Dashboard</a>"
    )
    return send(msg)


def send_standard_violation(blog_id: str, rule_id: str, severity: str, detail: str) -> bool | None:
    """Send alert for standard compliance violation (CRITICAL only)."""
    if severity != "CRITICAL":
        return None
    url = f"{DASHBOARD_URL}/blog/{blog_id}"
    msg = (
        f"⚠️ <b>Standard Violation</b>\n"
        f"Blog: <code>{blog_id}</code>\n"
        f"Rule: {rule_id} ({severity})\n"
        f"Detail: {detail}\n"
        f"🔗 <a href=\"{url}\">Dashboard</a>"
    )
    return send(msg)
