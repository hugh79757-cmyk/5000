"""Blogdex-Lite 텔레그램 성과 리포트"""
import sqlite3
import os
import yaml
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def get_analytics_db():
    path = os.path.join(PROJECT_ROOT, "data", "analytics.db")
    return sqlite3.connect(path)


def get_content_db():
    path = os.path.join(PROJECT_ROOT, "data", "content.db")
    return sqlite3.connect(path)


def build_report():
    """텔레그램 성과 리포트 메시지 생성"""
    adb = get_analytics_db()
    cdb = get_content_db()
    ac = adb.cursor()
    cc = cdb.cursor()

    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # GSC 기준
    gsc_latest = (today - timedelta(days=3)).strftime("%Y-%m-%d")
    gsc_7d_start = (today - timedelta(days=9)).strftime("%Y-%m-%d")
    gsc_prev_end = (today - timedelta(days=10)).strftime("%Y-%m-%d")
    gsc_prev_start = (today - timedelta(days=16)).strftime("%Y-%m-%d")

    lines = []
    lines.append(f"📊 Blogdex-Lite 성과 리포트")
    lines.append(f"📅 {today_str}\n")

    # ── 1. 오늘 발행 현황 ──
    cc.execute("""
        SELECT COUNT(*), COUNT(DISTINCT blog_id) FROM publish_ledger
        WHERE date(created_at) = date('now','localtime')
          AND published_url NOT LIKE 'pending://%'
    """)
    pub = cc.fetchone()
    lines.append(f"📝 오늘 발행: {pub[0]}건 ({pub[1]}개 블로그)")

    # ── 2. GSC 주간 추이 ──
    ac.execute("""
        SELECT COALESCE(SUM(total_clicks),0), COALESCE(SUM(total_impressions),0)
        FROM gsc_daily_summary WHERE date BETWEEN ? AND ?
    """, (gsc_7d_start, gsc_latest))
    r = ac.fetchone()
    week_clicks, week_imp = r[0], r[1]

    ac.execute("""
        SELECT COALESCE(SUM(total_clicks),0), COALESCE(SUM(total_impressions),0)
        FROM gsc_daily_summary WHERE date BETWEEN ? AND ?
    """, (gsc_prev_start, gsc_prev_end))
    r = ac.fetchone()
    prev_clicks, prev_imp = r[0], r[1]

    click_chg = ((week_clicks - prev_clicks) / prev_clicks * 100) if prev_clicks > 0 else 0
    imp_chg = ((week_imp - prev_imp) / prev_imp * 100) if prev_imp > 0 else 0

    def arrow(val):
        if val > 5:
            return "🔺"
        elif val < -5:
            return "🔻"
        return "➡️"

    lines.append(f"\n🔍 검색 성과 ({gsc_7d_start} ~ {gsc_latest})")
    lines.append(f"노출: {week_imp:,d} {arrow(imp_chg)}{imp_chg:+.0f}% (전주 대비)")
    lines.append(f"클릭: {week_clicks:,d} {arrow(click_chg)}{click_chg:+.0f}%")

    # ── 3. GA4 주간 ──
    ga4_end = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    ga4_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    ac.execute("""
        SELECT COALESCE(SUM(sessions),0), COALESCE(SUM(page_views),0),
               COALESCE(SUM(total_users),0), COALESCE(SUM(ad_revenue),0)
        FROM ga4_daily WHERE date BETWEEN ? AND ?
    """, (ga4_start, ga4_end))
    ga = ac.fetchone()
    week_sessions, week_pv, week_users, week_revenue = ga[0], ga[1], ga[2], ga[3]

    lines.append(f"\n📈 트래픽 ({ga4_start} ~ {ga4_end})")
    lines.append(f"세션: {week_sessions:,d} | PV: {week_pv:,d} | 사용자: {week_users:,d}")
    if week_revenue > 0:
        lines.append(f"💰 수익: ${week_revenue:.3f} (RPM ${week_revenue/week_pv*1000:.2f})" if week_pv > 0 else f"💰 수익: ${week_revenue:.3f}")

    # ── 4. 트래픽 소스 ──
    ac.execute("""
        SELECT channel_group, SUM(sessions) as s
        FROM ga4_traffic_sources WHERE date BETWEEN ? AND ?
        GROUP BY channel_group ORDER BY s DESC LIMIT 5
    """, (ga4_start, ga4_end))
    src_rows = ac.fetchall()
    if src_rows:
        total_s = sum(r[1] for r in src_rows)
        lines.append(f"\n🌐 트래픽 소스")
        for ch, s in src_rows:
            pct = (s / total_s * 100) if total_s > 0 else 0
            lines.append(f"  {ch}: {s:,d} ({pct:.0f}%)")

    # ── 5. 효율 등급 요약 ──
    ac.execute("""
        SELECT grade, COUNT(*), SUM(gsc_impressions), SUM(ga4_page_views)
        FROM blog_efficiency WHERE date = ?
        GROUP BY grade ORDER BY grade
    """, (today_str,))
    grade_rows = ac.fetchall()
    if grade_rows:
        lines.append(f"\n🏆 블로그 등급 분포")
        for grade, cnt, imp, pv in grade_rows:
            lines.append(f"  {grade}: {cnt}개 (노출 {imp:,d} | PV {pv:,d})")

    # ── 6. TOP 5 블로그 ──
    ac.execute("""
        SELECT blog_id, grade, gsc_impressions, gsc_clicks, ga4_page_views, efficiency_score
        FROM blog_efficiency WHERE date = ?
        ORDER BY efficiency_score DESC LIMIT 5
    """, (today_str,))
    top_rows = ac.fetchall()
    if top_rows:
        lines.append(f"\n⭐ 효율 TOP 5")
        for i, (bid, g, imp, clk, pv, sc) in enumerate(top_rows, 1):
            lines.append(f"  {i}. {bid} ({g}) 노출:{imp:,d} 클릭:{clk} PV:{pv}")

    # ── 7. 주의 블로그 (노출 0) ──
    ac.execute("""
        SELECT blog_id FROM blog_efficiency
        WHERE date = ? AND gsc_impressions = 0 AND ga4_page_views = 0
          AND total_posts >= 10
        ORDER BY blog_id
    """, (today_str,))
    warn_rows = ac.fetchall()
    if warn_rows:
        lines.append(f"\n⚠️ 주의 (노출·PV 모두 0, 글 10개↑)")
        for (bid,) in warn_rows[:5]:
            lines.append(f"  - {bid}")
        if len(warn_rows) > 5:
            lines.append(f"  ... 외 {len(warn_rows)-5}개")

    # ── 8. 인기 키워드 TOP 5 ──
    ac.execute("""
        SELECT query, SUM(impressions) as ti, SUM(clicks) as tc
        FROM gsc_keywords WHERE date BETWEEN ? AND ?
        GROUP BY query ORDER BY ti DESC LIMIT 5
    """, (gsc_7d_start, gsc_latest))
    kw_rows = ac.fetchall()
    if kw_rows:
        lines.append(f"\n🔑 인기 키워드 TOP 5")
        for q, ti, tc in kw_rows:
            lines.append(f"  {q[:30]} (노출:{ti} 클릭:{tc})")

    # ── 9. 색인 제출 현황 ──
    ac.execute("""
        SELECT COUNT(*) FROM indexing_log
        WHERE date(submitted_at) = date('now','localtime')
    """)
    idx_cnt = ac.fetchone()[0]
    if idx_cnt > 0:
        lines.append(f"\n🔗 색인 제출: {idx_cnt}건")

    adb.close()
    cdb.close()

    return "\n".join(lines)


def send_report(test=False):
    """텔레그램으로 리포트 전송"""
    message = build_report()

    if test:
        print(message)
        return message

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[ERR] TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 미설정")
        print(message)
        return message

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=30)
        if resp.status_code == 200:
            print("[OK] 텔레그램 리포트 전송 완료")
        else:
            print(f"[ERR] 텔레그램 {resp.status_code}: {resp.text[:100]}")
            print(message)
    except Exception as e:
        print(f"[ERR] 텔레그램 전송 실패: {e}")
        print(message)

    return message


if __name__ == "__main__":
    import sys
    test_mode = "--test" in sys.argv
    send_report(test=test_mode)
