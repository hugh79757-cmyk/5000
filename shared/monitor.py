"""모니터링 — telegram_notifier 경유 (하위 호환 래퍼)
직접 API 호출 제거.
"""
import json
import logging
import os
from datetime import datetime, timedelta

from shared.content_store import get_conn
from shared.paths import DATA_DIR
from shared.telegram_notifier import send

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

    # no_result cooldown 현황 추가
    cooldown_file = os.path.join(DATA_DIR, "cooldown.json")
    if os.path.isfile(cooldown_file):
        try:
            with open(cooldown_file) as f:
                cd = json.load(f)
            now = datetime.now()
            active = {k: v for k, v in cd.items()
                      if now - datetime.fromisoformat(v) < timedelta(minutes=30)}
            if active:
                lines.append("")
                lines.append(f"<b>⏳ 쿨다운 중 ({len(active)}개):</b>")
                for bid, ts in sorted(active.items()):
                    remain = int(1800 - (now - datetime.fromisoformat(ts)).total_seconds())
                    lines.append(f"  {bid}: {remain // 60}분 남음")
        except Exception:
            pass

    send("\n".join(lines))
    return {"date": today, "total": total, "details": {r["blog_id"]: r["cnt"] for r in rows}}
