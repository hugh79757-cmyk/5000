"""텔레그램 경고 알림 (발행 프로세스를 중단시키지 않음)"""
import os
import logging
import urllib.request
import urllib.parse
import json

logger = logging.getLogger(__name__)

_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    """텔레그램 메시지 전송. 실패해도 False만 반환."""
    if not _BOT_TOKEN or not _CHAT_ID:
        logger.debug("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정 — 알림 생략")
        return False
    try:
        url = f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": _CHAT_ID,
            "text": message[:4000],
            "parse_mode": parse_mode,
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        logger.debug(f"텔레그램 전송 실패 (무시): {e}")
        return False


def alert(title: str, detail: str = "") -> bool:
    """경고 알림. 문제 발생 시에만 호출."""
    msg = f"⚠️ <b>{title}</b>"
    if detail:
        msg += f"\n{detail}"
    return send_telegram(msg)
