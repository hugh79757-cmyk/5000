import os
import sys
import json
import sqlite3
import yaml
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.content_store import get_conn
from shared.telegram_notifier import send_daily_report

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")

TAP_DB = "/Users/twinssn/Projects/TAP/tap.db"
LAP_LOG = "/Users/twinssn/Projects/LAP/data/publish_log.json"


def load_active_blogs():
    with open(os.path.join(CONFIG_DIR, "blogs.yaml"), "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [b for b in data["blogs"] if b.get("status") == "active"]


def _get_tap_blogger_posts(target_date):
    if not os.path.exists(TAP_DB):
        return []
    conn = sqlite3.connect(TAP_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT post_title, post_url, published_at, source FROM publish_logs WHERE date(published_at) = ? ORDER BY published_at ASC",
        (target_date,)
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        results.append({
            "title": r["post_title"],
            "url": r["post_url"],
            "created_at": r["published_at"],
            "source": r["source"],
        })
    return results


def _get_lap_posts(target_date):
    if not os.path.exists(LAP_LOG):
        return []
    with open(LAP_LOG, "r", encoding="utf-8") as f:
        data = json.load(f)
    posts = data if isinstance(data, list) else data.get("posts", data.get("logs", []))
    if isinstance(data, dict) and not posts:
        for key in data:
            if isinstance(data[key], list):
                posts = data[key]
                break
    results = []
    for p in posts:
        pub_date = ""
        for date_key in ["published_at", "date", "created_at", "timestamp"]:
            if date_key in p:
                pub_date = str(p[date_key])[:10]
                break
        if pub_date == target_date:
            results.append({
                "title": p.get("title", "제목없음"),
                "link": p.get("link", p.get("url", "")),
                "site": p.get("site", p.get("blog", "")),
            })
    return results


def generate_report(target_date=None):
    if not target_date:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    blogs = load_active_blogs()
    conn = get_conn()

    total_success = 0
    total_fail = 0
    blog_lines = []

    for blog in blogs:
        bid = blog["id"]
        rows = conn.execute(
            "SELECT title, status, created_at FROM publish_ledger WHERE blog_id = ? AND date(created_at) = ? ORDER BY created_at ASC",
            (bid, target_date)
        ).fetchall()

        success = sum(1 for r in rows if r["status"] == "published")
        fail = sum(1 for r in rows if r["status"] != "published")
        total_success += success
        total_fail += fail

        if not rows:
            blog_lines.append("  " + bid + ": 0건")
            continue

        titles = []
        for r in rows:
            mark = "✅" if r["status"] == "published" else "❌"
            short_title = r["title"][:35]
            titles.append("    " + mark + " " + short_title)

        blog_lines.append("  <b>" + bid + "</b>: " + str(success) + "건 성공" + (", " + str(fail) + "건 실패" if fail else ""))
        blog_lines.extend(titles)

    conn.close()

    tap_posts = _get_tap_blogger_posts(target_date)
    if tap_posts:
        total_success += len(tap_posts)
        blog_lines.append("")
        blog_lines.append("  <b>travel-blogger</b> (travel.rotcha.kr): " + str(len(tap_posts)) + "건")
        for p in tap_posts:
            blog_lines.append("    ✅ " + p["title"][:35])
    else:
        blog_lines.append("")
        blog_lines.append("  travel-blogger (travel.rotcha.kr): 0건")

    lap_posts = _get_lap_posts(target_date)
    if lap_posts:
        total_success += len(lap_posts)
        sites = {}
        for p in lap_posts:
            site = p.get("site", "LAP")
            if site not in sites:
                sites[site] = []
            sites[site].append(p)
        blog_lines.append("")
        for site, posts in sites.items():
            blog_lines.append("  <b>LAP-" + site + "</b>: " + str(len(posts)) + "건")
            for p in posts:
                blog_lines.append("    ✅ " + p["title"][:35])
    else:
        blog_lines.append("")
        blog_lines.append("  LAP: 0건")

    header = "📊 <b>일일 리포트</b> (" + target_date + ")\n"
    header += "총 발행: " + str(total_success) + "건 성공"
    if total_fail:
        header += ", " + str(total_fail) + "건 실패"
    header += "\n\n"

    body = "\n".join(blog_lines)

    return header + body


def send_report(target_date=None):
    report = generate_report(target_date)
    return send_daily_report(report)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    report = generate_report(target)
    print(report)
    send_report(target)
