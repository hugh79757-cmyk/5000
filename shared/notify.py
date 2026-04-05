"""텔레그램 경고 알림 — telegram_notifier 경유 (하위 호환 래퍼)
직접 API 호출 제거. 모든 전송은 telegram_notifier.py가 담당.
"""
import logging
from shared.telegram_notifier import send, send_warning, send_critical

logger = logging.getLogger(__name__)


def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    """하위 호환 — 직접 send() 경유."""
    return send(message, parse_mode)


def alert(title: str, detail: str = "") -> bool:
    """경고 알림 — WARNING 등급으로 전송."""
    return send_warning(title, detail)
