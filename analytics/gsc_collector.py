#!/usr/bin/env python3
"""GSC Collector - sc-domain + URL-prefix 혼합 수집"""
import os, sys, sqlite3, time, yaml
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import urlparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# sc-domain 기반 (소유자 인증 완료)
SC_DOMAINS = [
    "sc-domain:rotcha.kr",
    "sc-domain:techpawz.com",
]

# URL-prefix 기반 (sc-domain 미등록)
URL_PREFIX_ACCOUNTS = {
    "informationhot.kr": "informationhot",
    "aikorea24.kr": "aikorea24",
}

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
    """sc-domain + URL-prefix 혼합 수집 → gsc_daily_summary"""
    from analytics.auth import get_gsc_service_for_domain, get_gsc_service

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

    # ── 1) sc-domain 수집 ──
    for sc_domain in SC_DOMAINS:
        if verbose:
            print(f"[{sc_domain}]")
        try:
            service = get_gsc_service_for_domain(sc_domain)
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

        agg = defaultdict(lambda: {"clicks": 0, "impressions": 0, "ctr_sum": 0.0, "pos_sum": 0.0})
        for r in rows:
            date_str, page = r["keys"]
            host = urlparse(page).hostname or ""
            key = (host, date_str)
            agg[key]["clicks"] += r.get("clicks", 0)
            agg[key]["impressions"] += r.get("impressions", 0)
            agg[key]["ctr_sum"] += r.get("ctr", 0.0) * r.get("impressions", 0)
            agg[key]["pos_sum"] += r.get("position", 0.0) * r.get("impressions", 0)

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
            """, (blog_id, date_str, data["clicks"], imp, round(avg_ctr, 4), round(avg_pos, 1)))
            saved += 1

        conn.commit()
        total_saved += saved
        if verbose:
            print(f"  {len(rows)} rows → {saved} entries saved")
        time.sleep(0.3)

    # ── 2) URL-prefix 수집 ──
    for root_domain, account in URL_PREFIX_ACCOUNTS.items():
        if verbose:
            print(f"\n[URL-prefix: {root_domain}]")
        try:
            service = get_gsc_service(account)
            site_list = service.sites().list().execute()
            site_urls = [
                e["siteUrl"] for e in site_list.get("siteEntry", [])
                if root_domain in e["siteUrl"]
            ]
            if verbose:
                print(f"  등록 사이트: {len(site_urls)}개")

            for site_url in site_urls:
                parsed = urlparse(site_url.rstrip("/"))
                host = parsed.netloc
                blog_id = domain_to_blog.get(host, "")
                if not blog_id:
                    continue
                try:
                    body = {
                        "startDate": start_date,
                        "endDate": end_date,
                        "dimensions": ["date"],
                        "rowLimit": 25000,
                    }
                    resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
                    rows = resp.get("rows", [])
                    for row in rows:
                        dt = row["keys"][0]
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
                        """, (blog_id, dt,
                              row.get("clicks", 0), row.get("impressions", 0),
                              round(row.get("ctr", 0), 4), round(row.get("position", 0), 1)))
                        total_saved += 1
                        total_blogs.add(blog_id)
                    conn.commit()
                    if verbose and rows:
                        print(f"  {blog_id}: {len(rows)} days")
                    time.sleep(0.3)
                except Exception as e:
                    if verbose:
                        print(f"  {blog_id}: ERR {str(e)[:60]}")
                    time.sleep(0.5)
        except Exception as e:
            if verbose:
                print(f"  ERR: {str(e)[:80]}")

    conn.close()
    if verbose:
        print(f"\n=== GSC 수집 완료 ===")
        print(f"저장: {total_saved}, 블로그: {len(total_blogs)}개")
    return {"saved": total_saved, "blogs": len(total_blogs)}


def collect_keywords(days_back=7, verbose=True):
    """sc-domain + URL-prefix 키워드/페이지 수집"""
    from analytics.auth import get_gsc_service_for_domain, get_gsc_service

    domain_to_blog = load_sites_yaml()
    conn = get_db()
    c = conn.cursor()

    end_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back + 2)).strftime("%Y-%m-%d")

    if verbose:
        print(f"\n=== GSC 키워드 수집 ({start_date} ~ {end_date}) ===")

    total_kw = 0
    total_pg = 0

    # ── sc-domain 키워드 ──
    for sc_domain in SC_DOMAINS:
        if verbose:
            print(f"[{sc_domain}]", end=" ")
        service = get_gsc_service_for_domain(sc_domain)
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

    # ── URL-prefix 키워드 ──
    for root_domain, account in URL_PREFIX_ACCOUNTS.items():
        if verbose:
            print(f"[URL-prefix: {root_domain}]", end=" ")
        try:
            service = get_gsc_service(account)
            site_list = service.sites().list().execute()
            site_urls = [
                e["siteUrl"] for e in site_list.get("siteEntry", [])
                if root_domain in e["siteUrl"]
            ]
            kw_count = 0
            pg_count = 0
            for site_url in site_urls:
                host = urlparse(site_url.rstrip("/")).netloc
                blog_id = domain_to_blog.get(host, "")
                if not blog_id:
                    continue
                try:
                    body = {
                        "startDate": start_date, "endDate": end_date,
                        "dimensions": ["date", "query"],
                        "rowLimit": 5000,
                    }
                    resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
                    for r in resp.get("rows", []):
                        keys = r["keys"]
                        c.execute("""
                            INSERT INTO gsc_keywords
                            (blog_id, date, query, page, device, country, clicks, impressions, ctr, position)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(blog_id, date, query, page, device, country) DO UPDATE SET
                                clicks=excluded.clicks, impressions=excluded.impressions,
                                ctr=excluded.ctr, position=excluded.position,
                                collected_at=datetime('now','localtime')
                        """, (blog_id, keys[0], keys[1], site_url, "", "",
                              r.get("clicks", 0), r.get("impressions", 0),
                              r.get("ctr", 0.0), r.get("position", 0.0)))
                        kw_count += 1
                    time.sleep(0.3)
                except Exception as e:
                    if verbose:
                        print(f"kw_err({blog_id}):{str(e)[:40]}", end=" ")

            total_kw += kw_count
            total_pg += pg_count
            conn.commit()
            if verbose:
                print(f"kw:{kw_count} pg:{pg_count}")
        except Exception as e:
            if verbose:
                print(f"ERR:{str(e)[:50]}")
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
