"""GSC 일별 데이터 수집기 — 전체 활성 블로그 대상"""
import sqlite3
import time
import yaml
import os
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_active_blogs():
    """blogs.yaml에서 gsc_site가 있는 활성 블로그 반환"""
    path = os.path.join(PROJECT_ROOT, "config", "blogs.yaml")
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    return [
        b for b in config.get("blogs", [])
        if b.get("status") == "active" and b.get("gsc_site")
    ]


def get_db():
    db_path = os.path.join(PROJECT_ROOT, "data", "analytics.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def fetch_gsc_summary(service, site_url, start_date, end_date):
    """GSC에서 날짜별 summary 데이터 가져오기"""
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["date"],
        "rowLimit": 25000,
    }
    try:
        resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        return resp.get("rows", [])
    except Exception as e:
        print(f"  [ERR] {site_url}: {e}")
        return []


def fetch_gsc_pages(service, site_url, date_str):
    """특정 날짜의 페이지별 상세 데이터"""
    body = {
        "startDate": date_str,
        "endDate": date_str,
        "dimensions": ["page"],
        "rowLimit": 25000,
    }
    try:
        resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        return resp.get("rows", [])
    except Exception as e:
        print(f"  [ERR] pages {site_url}: {e}")
        return []


def collect_all(days_back=7, include_pages=False, verbose=True):
    """
    전체 활성 블로그의 GSC 데이터를 수집하여 analytics.db에 저장.
    
    Args:
        days_back: 며칠 전까지 수집할지 (기본 7일, 초기 수집 시 90일)
        include_pages: 페이지별 상세 데이터도 수집할지
        verbose: 진행 상황 출력
    """
    from analytics.auth import get_gsc_service
    
    service = get_gsc_service()
    blogs = load_active_blogs()
    conn = get_db()
    c = conn.cursor()
    
    # GSC는 2~3일 전 데이터까지만 확정됨
    end_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back + 2)).strftime("%Y-%m-%d")
    
    if verbose:
        print(f"=== GSC 수집 시작 ({start_date} ~ {end_date}) ===")
        print(f"대상: {len(blogs)}개 블로그\n")
    
    total_inserted = 0
    total_skipped = 0
    
    for blog in blogs:
        bid = blog["id"]
        site_url = blog["gsc_site"]
        
        if verbose:
            print(f"[{bid}] {site_url}")
        
        # 일별 summary 수집
        rows = fetch_gsc_summary(service, site_url, start_date, end_date)
        
        inserted = 0
        skipped = 0
        for row in rows:
            date_str = row["keys"][0]
            clicks = row.get("clicks", 0)
            impressions = row.get("impressions", 0)
            ctr = row.get("ctr", 0.0)
            position = row.get("position", 0.0)
            
            try:
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
                """, (bid, date_str, clicks, impressions, ctr, position))
                inserted += 1
            except Exception as e:
                print(f"  [DB ERR] {bid} {date_str}: {e}")
                skipped += 1
        
        # 페이지별 상세 (옵션)
        page_count = 0
        if include_pages:
            # 최근 1일만 페이지 상세 수집
            yesterday = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
            pages = fetch_gsc_pages(service, site_url, yesterday)
            for prow in pages:
                page_url = prow["keys"][0]
                try:
                    c.execute("""
                        INSERT INTO gsc_daily 
                        (blog_id, date, page, clicks, impressions, ctr, position)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(blog_id, date, page, query) DO UPDATE SET
                            clicks=excluded.clicks,
                            impressions=excluded.impressions,
                            ctr=excluded.ctr,
                            position=excluded.position,
                            collected_at=datetime('now','localtime')
                    """, (bid, yesterday, page_url,
                          prow.get("clicks", 0), prow.get("impressions", 0),
                          prow.get("ctr", 0.0), prow.get("position", 0.0)))
                    page_count += 1
                except Exception as e:
                    pass
        
        if verbose:
            extra = f" + {page_count} pages" if include_pages else ""
            print(f"  → {inserted} days saved{extra}")
        
        total_inserted += inserted
        total_skipped += skipped
        
        # API rate limit 방지
        time.sleep(0.3)
    
    conn.commit()
    conn.close()
    
    if verbose:
        print(f"\n=== GSC 수집 완료 ===")
        print(f"저장: {total_inserted}, 스킵: {total_skipped}")
    
    return total_inserted


def get_trend_data(blog_id, conn=None):
    """
    블로그의 추이 데이터 반환.
    어제, 7일전, 30일전, 90일전의 클릭/노출 비교.
    """
    close_conn = False
    if conn is None:
        conn = get_db()
        close_conn = True
    
    c = conn.cursor()
    today = datetime.now()
    
    # 비교 시점 (GSC 2~3일 래그 감안)
    points = {
        "latest":  (today - timedelta(days=3)).strftime("%Y-%m-%d"),
        "7d_ago":  (today - timedelta(days=10)).strftime("%Y-%m-%d"),
        "30d_ago": (today - timedelta(days=33)).strftime("%Y-%m-%d"),
        "90d_ago": (today - timedelta(days=93)).strftime("%Y-%m-%d"),
    }
    
    result = {}
    for label, date_str in points.items():
        c.execute("""
            SELECT total_clicks, total_impressions, avg_ctr, avg_position
            FROM gsc_daily_summary
            WHERE blog_id = ? AND date = ?
        """, (blog_id, date_str))
        row = c.fetchone()
        if row:
            result[label] = {
                "clicks": row[0],
                "impressions": row[1],
                "ctr": row[2],
                "position": row[3],
            }
        else:
            result[label] = None
    
    # 최근 7일 합계
    week_start = (today - timedelta(days=9)).strftime("%Y-%m-%d")
    week_end = (today - timedelta(days=3)).strftime("%Y-%m-%d")
    c.execute("""
        SELECT SUM(total_clicks), SUM(total_impressions), AVG(avg_ctr), AVG(avg_position)
        FROM gsc_daily_summary
        WHERE blog_id = ? AND date BETWEEN ? AND ?
    """, (blog_id, week_start, week_end))
    row = c.fetchone()
    if row and row[0] is not None:
        result["week_total"] = {
            "clicks": row[0],
            "impressions": row[1],
            "ctr": row[2],
            "position": row[3],
        }
    
    # 최근 30일 합계
    month_start = (today - timedelta(days=32)).strftime("%Y-%m-%d")
    c.execute("""
        SELECT SUM(total_clicks), SUM(total_impressions), AVG(avg_ctr), AVG(avg_position)
        FROM gsc_daily_summary
        WHERE blog_id = ? AND date BETWEEN ? AND ?
    """, (blog_id, month_start, week_end))
    row = c.fetchone()
    if row and row[0] is not None:
        result["month_total"] = {
            "clicks": row[0],
            "impressions": row[1],
            "ctr": row[2],
            "position": row[3],
        }
    
    if close_conn:
        conn.close()
    
    return result




def collect_keywords(days_back=7, verbose=True):
    """GSC 키워드별 상세 수집 (query + page + device + country)"""
    from analytics.auth import get_gsc_service

    service = get_gsc_service()
    blogs = load_active_blogs()
    conn = get_db()
    c = conn.cursor()

    end_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back + 2)).strftime("%Y-%m-%d")

    if verbose:
        print(f"=== GSC 키워드 수집 ({start_date} ~ {end_date}) ===")
        print(f"대상: {len(blogs)}개 블로그\n")

    total_keywords = 0
    total_pages = 0

    for blog in blogs:
        bid = blog["id"]
        site_url = blog["gsc_site"]

        if verbose:
            print(f"[{bid}]", end=" ")

        # 키워드별 (query + page + device + country)
        kw_count = 0
        try:
            body = {
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["date", "query", "page", "device", "country"],
                "rowLimit": 25000,
            }
            resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
            for row in resp.get("rows", []):
                keys = row["keys"]
                c.execute("""
                    INSERT INTO gsc_keywords
                    (blog_id, date, query, page, device, country, clicks, impressions, ctr, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(blog_id, date, query, page, device, country) DO UPDATE SET
                        clicks=excluded.clicks, impressions=excluded.impressions,
                        ctr=excluded.ctr, position=excluded.position,
                        collected_at=datetime('now','localtime')
                """, (bid, keys[0], keys[1], keys[2], keys[3], keys[4],
                      row.get("clicks", 0), row.get("impressions", 0),
                      row.get("ctr", 0.0), row.get("position", 0.0)))
                kw_count += 1
        except Exception as e:
            if verbose:
                print(f"kw_err:{str(e)[:50]}", end=" ")

        # 페이지별
        pg_count = 0
        try:
            body2 = {
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["date", "page"],
                "rowLimit": 25000,
            }
            resp2 = service.searchanalytics().query(siteUrl=site_url, body=body2).execute()
            for row in resp2.get("rows", []):
                keys = row["keys"]
                c.execute("""
                    INSERT INTO gsc_pages
                    (blog_id, date, page, clicks, impressions, ctr, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(blog_id, date, page) DO UPDATE SET
                        clicks=excluded.clicks, impressions=excluded.impressions,
                        ctr=excluded.ctr, position=excluded.position,
                        collected_at=datetime('now','localtime')
                """, (bid, keys[0], keys[1],
                      row.get("clicks", 0), row.get("impressions", 0),
                      row.get("ctr", 0.0), row.get("position", 0.0)))
                pg_count += 1
        except Exception as e:
            if verbose:
                print(f"pg_err:{str(e)[:50]}", end=" ")

        total_keywords += kw_count
        total_pages += pg_count

        if verbose:
            print(f"kw:{kw_count} pg:{pg_count}")

        conn.commit()
        time.sleep(0.3)

    conn.close()

    if verbose:
        print(f"\n=== GSC 키워드/페이지 수집 완료 ===")
        print(f"키워드: {total_keywords}, 페이지: {total_pages}")

    return {"keywords": total_keywords, "pages": total_pages}


if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    keywords = "--keywords" in sys.argv or "--all" in sys.argv
    print(f"수집 기간: {days}일")
    collect_all(days_back=days)
    if keywords:
        collect_keywords(days_back=days)
