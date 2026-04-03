import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_URL = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"


def _esc(text):
    """Telegram HTML 특수문자 이스케이프"""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send(message, parse_mode="HTML"):
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram credentials missing")
        return False
    try:
        resp = requests.post(API_URL, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": parse_mode,
        }, timeout=10)
        if resp.status_code == 200:
            return True
        logger.warning("Telegram send failed: " + str(resp.status_code))
        return False
    except requests.RequestException as e:
        logger.error(f"[TELEGRAM_ERROR] Request failed: {e}")
        return False


def send_error(blog_id, stage, error_msg, exc=None):
    """에러 알림 전송. exc에 Exception 객체를 넘기면 traceback 포함."""
    import traceback as _tb
    import sys as _sys
    from datetime import datetime as _dt

    _SILENT_REASONS = ["quota_met", "quota_exceeded", "daily_quota_exceeded", "daily_quota"]
    _err_lower = str(error_msg).lower()
    if any(reason in _err_lower for reason in _SILENT_REASONS):
        logger.info(f"[Silent] {blog_id}/{stage}: {error_msg}")
        return False

    domain = ""
    repo = ""
    pipeline = ""
    try:
        import yaml
        from pathlib import Path
        cfg_path = Path(__file__).parent.parent / "config" / "blogs.yaml"
        with open(cfg_path, "r", encoding="utf-8") as yf:
            cfg = yaml.safe_load(yf)
        for blog in cfg.get("blogs", []):
            if blog.get("id") == blog_id:
                domain = blog.get("domain", "")
                repo = blog.get("repo", "")
                pipeline = blog.get("pipeline", "")
                break
    except Exception as e:
        logger.error(f"[CONFIG_ERROR] Failed to load blogs.yaml: {e}")

    now = _dt.now().strftime("%m-%d %H:%M:%S")

    text = "\U0001f6a8 <b>발행 오류</b>\n"
    text += f"<b>시각:</b> {now}\n"
    text += f"<b>블로그:</b> {_esc(blog_id)}\n"
    if domain:
        text += f"<b>도메인:</b> {_esc(domain)}\n"
    if pipeline:
        text += f"<b>파이프라인:</b> {_esc(pipeline)}\n"
    text += f"<b>단계:</b> {_esc(stage)}\n"
    text += f"<b>오류:</b> {_esc(str(error_msg)[:300])}\n"

    # traceback 추가
    tb_text = ""
    if exc is not None:
        tb_lines = _tb.format_exception(type(exc), exc, exc.__traceback__)
        tb_text = "".join(tb_lines)[-500:]
    else:
        ei = _sys.exc_info()
        if ei[1] is not None:
            tb_lines = _tb.format_exception(*ei)
            tb_text = "".join(tb_lines)[-500:]

    if tb_text:
        text += f"\n<b>Traceback:</b>\n<pre>{_esc(tb_text)}</pre>"

    return send(text)


def send_daily_report(report_text):
    return send(report_text)
