import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_URL = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"


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
    except Exception as e:
        logger.warning("Telegram error: " + str(e))
        return False


def send_error(blog_id, stage, error_msg):
    text = "🚨 <b>발행 오류</b>\n"
    text += "<b>블로그:</b> " + blog_id + "\n"
    text += "<b>단계:</b> " + stage + "\n"
    text += "<b>오류:</b> " + str(error_msg)[:500]
    return send(text)


def send_daily_report(report_text):
    return send(report_text)
