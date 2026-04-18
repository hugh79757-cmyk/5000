"""블로그 효율 스코어 산출 — GSC + GA4 + 발행 데이터 통합"""
import sqlite3
import os
import yaml
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_analytics_db():
    path = os.path.join(PROJECT_ROOT, "data", "analytics.db")
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_content_db():
    path = os.path.join(PROJECT_ROOT, "data", "content.db")
    return sqlite3.connect(path)


def load_active_blog_ids():
    """blogs.yaml + blogs.d/*.yaml 통합 로드"""
    import glob
    config_dir = os.path.join(PROJECT_ROOT, "config")
    all_blogs = []

    main_path = os.path.join(config_dir, "blogs.yaml")
    with open(main_path, "r") as f:
        main_cfg = yaml.safe_load(f) or {}
    all_blogs.extend(main_cfg.get("blogs", []))

    blogs_d = os.path.join(config_dir, "blogs.d")
    if os.path.isdir(blogs_d):
        for fpath in sorted(glob.glob(os.path.join(blogs_d, "*.yaml"))):
            with open(fpath, "r") as f:
                sub = yaml.safe_load(f) or {}
            all_blogs.extend(sub.get("blogs", []))

    return [b["id"] for b in all_blogs if b.get("status") == "active"]


def update_scores(verbose=True):
    """전체 활성 블로그의 효율 스코어 계산 후 blog_efficiency 테이블 저장"""
    adb = get_analytics_db()
    cdb = get_content_db()
    ac = adb.cursor()
    cc = cdb.cursor()

    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    # GSC 기준 날짜 (2~3일 래그)
    gsc_end = (today - timedelta(days=3)).strftime("%Y-%m-%d")
    gsc_7d_start = (today - timedelta(days=9)).strftime("%Y-%m-%d")
    gsc_30d_start = (today - timedelta(days=32)).strftime("%Y-%m-%d")

    # GA4 기준 날짜 (1일 래그)
    ga4_end = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    ga4_7d_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    ga4_30d_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")

    blog_ids = load_active_blog_ids()
    scores = []

    for bid in blog_ids:
        # 누적 발행 수
        try:
            cc.execute("""
                SELECT COUNT(*) FROM publish_ledger
                WHERE blog_id = ? AND published_url NOT LIKE 'pending://%'
            """, (bid,))
            total_posts = cc.fetchone()[0]
        except:
            total_posts = 0

        # GSC 7일 합계
        ac.execute("""
            SELECT COALESCE(SUM(total_clicks),0), COALESCE(SUM(total_impressions),0),
                   COALESCE(AVG(avg_ctr),0), COALESCE(AVG(avg_position),0)
            FROM gsc_daily_summary
            WHERE blog_id = ? AND date BETWEEN ? AND ?
        """, (bid, gsc_7d_start, gsc_end))
        gsc7 = ac.fetchone()
        week_clicks, week_impressions = gsc7[0], gsc7[1]
        week_ctr, week_position = gsc7[2], gsc7[3]

        # GSC 30일 합계
        ac.execute("""
            SELECT COALESCE(SUM(total_clicks),0), COALESCE(SUM(total_impressions),0)
            FROM gsc_daily_summary
            WHERE blog_id = ? AND date BETWEEN ? AND ?
        """, (bid, gsc_30d_start, gsc_end))
        gsc30 = ac.fetchone()
        month_clicks, month_impressions = gsc30[0], gsc30[1]

        # GA4 7일 합계
        ac.execute("""
            SELECT COALESCE(SUM(sessions),0), COALESCE(SUM(page_views),0),
                   COALESCE(SUM(total_users),0), COALESCE(SUM(ad_revenue),0),
                   COALESCE(AVG(bounce_rate),0), COALESCE(AVG(engagement_rate),0)
            FROM ga4_daily
            WHERE blog_id = ? AND date BETWEEN ? AND ?
        """, (bid, ga4_7d_start, ga4_end))
        ga7 = ac.fetchone()
        week_sessions, week_pv, week_users = ga7[0], ga7[1], ga7[2]
        week_revenue, week_bounce, week_engagement = ga7[3], ga7[4], ga7[5]
        week_rpm = (week_revenue / week_pv * 1000) if week_pv > 0 else 0.0

        # GA4 30일 합계
        ac.execute("""
            SELECT COALESCE(SUM(sessions),0), COALESCE(SUM(page_views),0),
                   COALESCE(SUM(ad_revenue),0)
            FROM ga4_daily
            WHERE blog_id = ? AND date BETWEEN ? AND ?
        """, (bid, ga4_30d_start, ga4_end))
        ga30 = ac.fetchone()
        month_sessions, month_pv, month_revenue = ga30[0], ga30[1], ga30[2]

        # 효율 스코어 계산
        # 노출 × CTR × (1 + RPM) / max(total_posts, 1)
        if total_posts > 0:
            efficiency_score = (week_impressions * max(week_ctr, 0.001) * (1 + week_rpm)) / total_posts
        else:
            efficiency_score = 0.0

        scores.append({
            "blog_id": bid,
            "total_posts": total_posts,
            "week_clicks": week_clicks,
            "week_impressions": week_impressions,
            "week_ctr": week_ctr,
            "week_position": week_position,
            "month_clicks": month_clicks,
            "month_impressions": month_impressions,
            "week_sessions": week_sessions,
            "week_pv": week_pv,
            "week_users": week_users,
            "week_revenue": week_revenue,
            "week_rpm": week_rpm,
            "week_bounce": week_bounce,
            "week_engagement": week_engagement,
            "month_sessions": month_sessions,
            "month_pv": month_pv,
            "month_revenue": month_revenue,
            "efficiency_score": efficiency_score,
        })

    # 등급 산정 (상대 평가)
    scored = sorted(scores, key=lambda x: x["efficiency_score"], reverse=True)
    total = len(scored)
    for i, s in enumerate(scored):
        pct = (i / total) if total > 0 else 1.0
        if pct < 0.2:
            s["grade"] = "A"
        elif pct < 0.4:
            s["grade"] = "B"
        elif pct < 0.6:
            s["grade"] = "C"
        elif pct < 0.8:
            s["grade"] = "D"
        else:
            s["grade"] = "F"

    # DB 저장
    for s in scored:
        ac.execute("""
            INSERT INTO blog_efficiency
            (blog_id, date, total_posts, gsc_clicks, gsc_impressions,
             ga4_sessions, ga4_page_views, clicks_per_post, sessions_per_post,
             efficiency_score, grade)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(blog_id, date) DO UPDATE SET
                total_posts=excluded.total_posts, gsc_clicks=excluded.gsc_clicks,
                gsc_impressions=excluded.gsc_impressions, ga4_sessions=excluded.ga4_sessions,
                ga4_page_views=excluded.ga4_page_views,
                clicks_per_post=excluded.clicks_per_post,
                sessions_per_post=excluded.sessions_per_post,
                efficiency_score=excluded.efficiency_score, grade=excluded.grade,
                collected_at=datetime('now','localtime')
        """, (
            s["blog_id"], today_str, s["total_posts"],
            s["week_clicks"], s["week_impressions"],
            s["week_sessions"], s["week_pv"],
            (s["week_clicks"] / s["total_posts"]) if s["total_posts"] > 0 else 0,
            (s["week_sessions"] / s["total_posts"]) if s["total_posts"] > 0 else 0,
            s["efficiency_score"], s["grade"],
        ))

    adb.commit()
    adb.close()
    cdb.close()

    if verbose:
        print(f"=== 효율 스코어 산출 완료 ({today_str}) ===\n")
        print(f"{'blog_id':22s} {'등급':>4s} {'글수':>5s} {'7d클릭':>7s} {'7d노출':>7s} {'7dCTR':>7s} {'7dPV':>6s} {'7d수익':>8s} {'RPM':>7s} {'스코어':>8s}")
        print("-" * 105)
        for s in scored:
            rev_str = f"${s['week_revenue']:.3f}" if s['week_revenue'] > 0 else "-"
            rpm_str = f"${s['week_rpm']:.2f}" if s['week_rpm'] > 0 else "-"
            print(f"{s['blog_id']:22s} {s['grade']:>4s} {s['total_posts']:>5d} {s['week_clicks']:>7d} {s['week_impressions']:>7d} {s['week_ctr']:>7.4f} {s['week_pv']:>6d} {rev_str:>8s} {rpm_str:>7s} {s['efficiency_score']:>8.3f}")

    return scored


if __name__ == "__main__":
    update_scores()
