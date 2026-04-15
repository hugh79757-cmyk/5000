"""GA4 데이터 수집기 — 전체 활성 블로그 대상
수집 항목: 일별 요약, 페이지별 상세, 트래픽 소스별, AdSense 수익
"""
import sqlite3
import time
import yaml
import os, sys
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def load_active_blogs():
    path = os.path.join(PROJECT_ROOT, "config", "blogs.yaml")
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    return [
        b for b in config.get("blogs", [])
        if b.get("status") == "active" and b.get("ga4_property")
    ]


def get_db():
    db_path = os.path.join(PROJECT_ROOT, "data", "analytics.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def collect_all(days_back=7, verbose=True):
    """전체 활성 블로그 GA4 데이터 수집"""
    from analytics.auth import get_ga4_service_for_domain

    blogs = load_active_blogs()
    conn = get_db()
    c = conn.cursor()

    end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    if verbose:
        print(f"=== GA4 수집 시작 ({start_date} ~ {end_date}) ===")
        print(f"대상: {len(blogs)}개 블로그\n")

    total_daily = 0
    total_pages = 0
    total_traffic = 0

    for blog in blogs:
        bid = blog["id"]
        domain = blog.get("domain", "")
        service = get_ga4_service_for_domain(domain)
        prop = f"properties/{blog['ga4_property']}"

        if verbose:
            print(f"[{bid}] {domain} -> {prop}")

        daily_count = 0
        page_count = 0
        traffic_count = 0

        # --- 1. 일별 요약: 기본 metrics (10개 제한이므로 2회 호출) ---
        daily_data = {}  # date_str -> {metrics}

        # 1a. 기본 metrics (8개)
        try:
            resp1 = service.properties().runReport(
                property=prop,
                body={
                    "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                    "dimensions": [{"name": "date"}],
                    "metrics": [
                        {"name": "sessions"},
                        {"name": "totalUsers"},
                        {"name": "newUsers"},
                        {"name": "screenPageViews"},
                        {"name": "averageSessionDuration"},
                        {"name": "bounceRate"},
                        {"name": "engagedSessions"},
                        {"name": "engagementRate"},
                    ],
                },
            ).execute()
            for row in resp1.get("rows", []):
                date_raw = row["dimensionValues"][0]["value"]
                date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
                v = [m["value"] for m in row["metricValues"]]
                daily_data[date_str] = {
                    "sessions": int(v[0]), "total_users": int(v[1]),
                    "new_users": int(v[2]), "page_views": int(v[3]),
                    "avg_duration": float(v[4]), "bounce_rate": float(v[5]),
                    "engaged_sessions": int(v[6]), "engagement_rate": float(v[7]),
                    "ad_revenue": 0.0, "ad_impressions": 0, "ad_clicks": 0,
                }
        except Exception as e:
            if verbose:
                print(f"  [ERR basic] {str(e)[:80]}")

        # 1b. AdSense metrics (3개)
        try:
            resp2 = service.properties().runReport(
                property=prop,
                body={
                    "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                    "dimensions": [{"name": "date"}],
                    "metrics": [
                        {"name": "totalAdRevenue"},
                        {"name": "publisherAdImpressions"},
                        {"name": "publisherAdClicks"},
                    ],
                },
            ).execute()
            for row in resp2.get("rows", []):
                date_raw = row["dimensionValues"][0]["value"]
                date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
                v = [m["value"] for m in row["metricValues"]]
                if date_str in daily_data:
                    daily_data[date_str]["ad_revenue"] = float(v[0])
                    daily_data[date_str]["ad_impressions"] = int(v[1])
                    daily_data[date_str]["ad_clicks"] = int(v[2])
        except Exception as e:
            if verbose:
                print(f"  [ERR adsense] {str(e)[:80]}")

        # DB 저장
        for date_str, d in daily_data.items():
            pv = d["page_views"]
            rpm = (d["ad_revenue"] / pv * 1000) if pv > 0 else 0.0
            c.execute("""
                INSERT INTO ga4_daily
                (blog_id, date, sessions, total_users, new_users, page_views,
                 avg_session_duration, bounce_rate, engaged_sessions, engagement_rate,
                 ad_revenue, ad_impressions, ad_clicks, rpm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(blog_id, date) DO UPDATE SET
                    sessions=excluded.sessions, total_users=excluded.total_users,
                    new_users=excluded.new_users, page_views=excluded.page_views,
                    avg_session_duration=excluded.avg_session_duration,
                    bounce_rate=excluded.bounce_rate,
                    engaged_sessions=excluded.engaged_sessions,
                    engagement_rate=excluded.engagement_rate,
                    ad_revenue=excluded.ad_revenue, ad_impressions=excluded.ad_impressions,
                    ad_clicks=excluded.ad_clicks, rpm=excluded.rpm,
                    collected_at=datetime('now','localtime')
            """, (bid, date_str, d["sessions"], d["total_users"], d["new_users"], pv,
                  d["avg_duration"], d["bounce_rate"], d["engaged_sessions"],
                  d["engagement_rate"], d["ad_revenue"], d["ad_impressions"],
                  d["ad_clicks"], rpm))
            daily_count += 1

        total_daily += daily_count

        # --- 2. 페이지별 상세 ---
        try:
            resp_pages = service.properties().runReport(
                property=prop,
                body={
                    "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                    "dimensions": [{"name": "date"}, {"name": "pagePath"}],
                    "metrics": [
                        {"name": "screenPageViews"},
                        {"name": "totalUsers"},
                        {"name": "averageSessionDuration"},
                    ],
                    "limit": 10000,
                    "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
                },
            ).execute()

            page_count = 0
            for row in resp_pages.get("rows", []):
                dims = [d["value"] for d in row["dimensionValues"]]
                date_raw = dims[0]
                date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
                page_path = dims[1]
                v = [m["value"] for m in row["metricValues"]]

                c.execute("""
                    INSERT INTO ga4_pages
                    (blog_id, date, page_path, page_views, users, avg_duration)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(blog_id, date, page_path) DO UPDATE SET
                        page_views=excluded.page_views, users=excluded.users,
                        avg_duration=excluded.avg_duration,
                        collected_at=datetime('now','localtime')
                """, (bid, date_str, page_path, int(v[0]), int(v[1]), float(v[2])))
                page_count += 1

            total_pages += page_count
        except Exception as e:
            if verbose:
                print(f"  [ERR pages] {str(e)[:80]}")

        # --- 3. 트래픽 소스별 ---
        try:
            resp_src = service.properties().runReport(
                property=prop,
                body={
                    "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                    "dimensions": [{"name": "date"}, {"name": "sessionDefaultChannelGroup"}],
                    "metrics": [
                        {"name": "sessions"},
                        {"name": "screenPageViews"},
                        {"name": "totalUsers"},
                    ],
                    "limit": 10000,
                },
            ).execute()

            traffic_count = 0
            for row in resp_src.get("rows", []):
                dims = [d["value"] for d in row["dimensionValues"]]
                date_raw = dims[0]
                date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
                channel = dims[1]
                v = [m["value"] for m in row["metricValues"]]

                c.execute("""
                    INSERT INTO ga4_traffic_sources
                    (blog_id, date, channel_group, sessions, page_views, users)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(blog_id, date, channel_group) DO UPDATE SET
                        sessions=excluded.sessions, page_views=excluded.page_views,
                        users=excluded.users,
                        collected_at=datetime('now','localtime')
                """, (bid, date_str, channel, int(v[0]), int(v[1]), int(v[2])))
                traffic_count += 1

            total_traffic += traffic_count
        except Exception as e:
            if verbose:
                print(f"  [ERR traffic] {str(e)[:80]}")

        if verbose:
            print(f"  → daily:{daily_count} pages:{page_count} traffic:{traffic_count}")

        conn.commit()
        time.sleep(0.3)

    conn.close()

    if verbose:
        print(f"\n=== GA4 수집 완료 ===")
        print(f"일별: {total_daily}, 페이지: {total_pages}, 트래픽소스: {total_traffic}")

    return {"daily": total_daily, "pages": total_pages, "traffic": total_traffic}


if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print(f"수집 기간: {days}일")
    collect_all(days_back=days)
