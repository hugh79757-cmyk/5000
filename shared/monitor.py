"""모니터링 — telegram_notifier 경유 (하위 호환 래퍼)
직접 API 호출 제거.
"""
import logging
from datetime import datetime
from shared.telegram_notifier import send
from shared.content_store import get_conn

logger = logging.getLogger(__name__)


def send_telegram(message: str) -> bool:
    """하위 호환 — 직접 send() 경유."""
    return send(message)


def send_daily_report(report_text: str) -> bool:
    """INFO 등급으로 전송."""
    return send(report_text)


def daily_report() -> dict:
    conn = get_conn()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT blog_id, COUNT(*) as cnt FROM articles"
        " WHERE date(created_at)=? AND status='published'"
        " GROUP BY blog_id",
        (today,),
    ).fetchall()
    conn.close()

    total = sum(r["cnt"] for r in rows)
    lines = [
        f"<b>[blog-hub] {today} 발행 리포트</b>",
        f"총 발행: {total}건",
        "",
    ]
    for r in rows:
        lines.append(f"  {r['blog_id']}: {r['cnt']}건")

    send("\n".join(lines))
    return {"date": today, "total": total, "details": {r["blog_id"]: r["cnt"] for r in rows}}
