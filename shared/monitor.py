import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from shared.content_store import get_conn

load_dotenv()


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    url = "https://api.telegram.org/bot" + token + "/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})


def daily_report():
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
    lines = ["<b>[blog-hub] " + today + " 발행 리포트</b>", "총 발행: " + str(total) + "건", ""]
    for r in rows:
        lines.append("  " + r["blog_id"] + ": " + str(r["cnt"]) + "건")

    send_telegram("\n".join(lines))
    return {"date": today, "total": total, "details": {r["blog_id"]: r["cnt"] for r in rows}}
