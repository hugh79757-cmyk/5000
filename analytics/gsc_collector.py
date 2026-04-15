#!/usr/bin/env python3
"""GSC Collector - sc-domain 기반 서브도메인별 수집"""
import os, sys, sqlite3, time, yaml
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import urlparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# sc-domain → zone mapping
SC_DOMAINS = [
    "sc-domain:rotcha.kr",
    "sc-domain:informationhot.kr",
    "sc-domain:techpawz.com",
    "sc-domain:aikorea24.kr",
]

def load_active_blogs():
    with open(os.path.join(PROJECT_ROOT, "config", "blogs.yaml")) as f:
        config = yaml.safe_load(f)
    return [b for b in config.get("blogs", []) if b.get("status") == "active"]

def load_sites_yaml():
    path = os.path.join(PROJECT_ROOT, "dashboard", "sites.yaml")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    mapping = {}
    for s in data.get("sites", []):
        domain = s.get("domain", "")
        mapping[domain] = s.get("blog_id", "")
    return mapping

def get_db():
    return sqlite3.connect(os.path.join(PROJECT_ROOT, "data", "analytics.db"))

def collect_all(days_back=7, verbose=True):
    """sc-domain에서 서브도메인별로 분리하여 gsc_daily_summary에 저장"""
    from analytics.auth import get_gsc_service_for_domain

    domain_to_blog = load_sites_yaml()
    conn = get_db()
    c = conn.cursor()

    end_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back + 2)).strftime("%Y-%m-%d")

    if verbose:
        print(f"=== GSC 수집 ({start_date} ~ {end_date}) ===")
        print(f"도메인 매핑: {len(domain_to_blog)}개\n")

    total_saved = 0
    total_blogs = set()

    for sc_domain in SC_DOMAINS:
        if verbose:
            print(f"[{sc_domain}]")

        service = get_gsc_service_for_domain(sc_domain)

        # 1. Daily summary per subdomain
        try:
            body = {
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["date", "page"],
                "rowLimit": 25000,
            }
            resp = service.searchanalytics().query(siteUrl=sc_domain, body=body).execute()
            rows = resp.get("rows", [])
        except Exception as e:
            if verbose:
                print(f"  ERR: {str(e)[:80]}")
            continue

        # Aggregate by (subdomain, date)
        agg = defaultdict(lambda: {"clicks": 0, "impressions": 0, "ctr_sum": 0.0, "pos_sum": 0.0, "count": 0})
        for r in rows:
            date_str, page = r["keys"]
            host = urlparse(page).hostname or ""
            key = (host, date_str)
            agg[key]["clicks"] += r.get("clicks", 0)
            agg[key]["impressions"] += r.get("impressions", 0)
            agg[key]["ctr_sum"] += r.get("ctr", 0.0) * r.get("impressions", 0)
            agg[key]["pos_sum"] += r.get("position", 0.0) * r.get("impressions", 0)
            agg[key]["count"] += 1

        saved = 0
        for (host, date_str), data in agg.items():
            blog_id = domain_to_blog.get(host, "")
            if not blog_id:
                continue
            total_blogs.add(blog_id)
            imp = data["impressions"]
            avg_ctr = data["ctr_sum"] / imp if imp > 0 else 0.0
            avg_pos = data["pos_sum"] / imp if imp > 0 else 0.0

            c.execute("""
                INSERT INTO gsc_daily_summary
                (blog_id, date, total_clicks, total_impressions, avg_ctr, avg_position)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(blog_id, date) DO UPDATE SET
                    total_clicks=excluded.total_clicks,
                    total_impressions=excluded.total_impressions,
                    avg_ctr=excluded.avg_ctr,
                    avg_position=excluded.avg_position,
                    collected_at=datetime('now','localtime')
            """, (blog_id, date_str,
                  data["clicks"], imp, round(avg_ctr, 4), round(avg_pos, 1)))
            saved += 1

        conn.commit()
        total_saved += saved
        if verbose:
            print(f"  {len(rows)} rows → {saved} entries saved")
        time.sleep(0.3)

    conn.close()
    if verbose:
        print(f"\n=== GSC 수집 완료 ===")
        print(f"저장: {total_saved}, 블로그: {len(total_blogs)}개")
    return {"saved": total_saved, "blogs": len(total_blogs)}


def collect_keywords(days_back=7, verbose=True):
    """sc-domain에서 키워드별 상세 수집"""
    from analytics.auth import get_gsc_service_for_domain

    domain_to_blog = load_sites_yaml()
    conn = get_db()
    c = conn.cursor()

    end_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back + 2)).strftime("%Y-%m-%d")

    if verbose:
        print(f"\n=== GSC 키워드 수집 ({start_date} ~ {end_date}) ===")

    total_kw = 0
    total_pg = 0

    for sc_domain in SC_DOMAINS:
        if verbose:
            print(f"[{sc_domain}]", end=" ")

        service = get_gsc_service_for_domain(sc_domain)

        # Keywords: date, query, page, device, country
        kw_count = 0
        try:
            body = {
                "startDate": start_date, "endDate": end_date,
                "dimensions": ["date", "query", "page", "device", "country"],
                "rowLimit": 25000,
            }
            resp = service.searchanalytics().query(siteUrl=sc_domain, body=body).execute()
            for r in resp.get("rows", []):
                keys = r["keys"]
                host = urlparse(keys[2]).hostname or ""
                blog_id = domain_to_blog.get(host, "")
                if not blog_id:
                    continue
                c.execute("""
                    INSERT INTO gsc_keywords
                    (blog_id, date, query, page, device, country, clicks, impressions, ctr, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(blog_id, date, query, page, device, country) DO UPDATE SET
                        clicks=excluded.clicks, impressions=excluded.impressions,
                        ctr=excluded.ctr, position=excluded.position,
                        collected_at=datetime('now','localtime')
                """, (blog_id, keys[0], keys[1], keys[2], keys[3], keys[4],
                      r.get("clicks", 0), r.get("impressions", 0),
                      r.get("ctr", 0.0), r.get("position", 0.0)))
                kw_count += 1
        except Exception as e:
            if verbose:
                print(f"kw_err:{str(e)[:50]}", end=" ")

        # Pages: date, page
        pg_count = 0
        try:
            body2 = {
                "startDate": start_date, "endDate": end_date,
                "dimensions": ["date", "page"],
                "rowLimit": 25000,
            }
            resp2 = service.searchanalytics().query(siteUrl=sc_domain, body=body2).execute()
            for r in resp2.get("rows", []):
                keys = r["keys"]
                host = urlparse(keys[1]).hostname or ""
                blog_id = domain_to_blog.get(host, "")
                if not blog_id:
                    continue
                c.execute("""
                    INSERT INTO gsc_pages
                    (blog_id, date, page, clicks, impressions, ctr, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(blog_id, date, page) DO UPDATE SET
                        clicks=excluded.clicks, impressions=excluded.impressions,
                        ctr=excluded.ctr, position=excluded.position,
                        collected_at=datetime('now','localtime')
                """, (blog_id, keys[0], keys[1],
                      r.get("clicks", 0), r.get("impressions", 0),
                      r.get("ctr", 0.0), r.get("position", 0.0)))
                pg_count += 1
        except Exception as e:
            if verbose:
                print(f"pg_err:{str(e)[:50]}", end=" ")

        total_kw += kw_count
        total_pg += pg_count
        conn.commit()
        if verbose:
            print(f"kw:{kw_count} pg:{pg_count}")
        time.sleep(0.3)

    conn.close()
    if verbose:
        print(f"\n=== 키워드/페이지 수집 완료 ===")
        print(f"키워드: {total_kw}, 페이지: {total_pg}")
    return {"keywords": total_kw, "pages": total_pg}


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    keywords = "--keywords" in sys.argv or "--all" in sys.argv
    print(f"수집 기간: {days}일")
    collect_all(days_back=days)
    if keywords:
        collect_keywords(days_back=days)
