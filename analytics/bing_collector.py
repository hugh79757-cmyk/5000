"""Bing Webmaster 데이터 수집기 — 키워드, 페이지, 사이트 통계"""
import sqlite3
import os
import time
import yaml
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

BASE = "https://ssl.bing.com/webmaster/api.svc/json"


def _get_api_keys():
    """사용 가능한 Bing API key 목록 반환 (3계정)"""
    keys = []
    for suffix in ["", "_2", "_3"]:
        k = os.getenv(f"BING_WEBMASTER_API_KEY{suffix}")
        if k:
            keys.append(k)
    return keys


def _get_accessible_sites(api_key):
    """해당 API key로 접근 가능한 사이트 URL set 반환"""
    try:
        resp = requests.get(
            f"{BASE}/GetUserSites",
            params={"apikey": api_key},
            timeout=30,
        )
        sites = set()
        data = resp.json()
        for s in data.get("d", data) if isinstance(data, dict) else data:
            if isinstance(s, dict):
                sites.add(s.get("Url", "").rstrip("/"))
        return sites
    except Exception:
        return set()


def _parse_bing_date(date_str):
    """Bing /Date(timestamp)/ 형식을 YYYY-MM-DD로 변환"""
    if not date_str or "/Date(" not in date_str:
        return None
    try:
        ts_part = date_str.split("(")[1].split(")")[0]
        # timezone offset 제거
        if "-" in ts_part:
            ts_ms = int(ts_part.split("-")[0])
        elif "+" in ts_part:
            ts_ms = int(ts_part.split("+")[0])
        else:
            ts_ms = int(ts_part)
        return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")
    except Exception:
        return None


def load_active_blogs():
    """sites.yaml 기준으로 전체 블로그 로드 (81개)"""
    path = os.path.join(PROJECT_ROOT, "dashboard", "sites.yaml")
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return [
        {"id": s["blog_id"], "domain": s["domain"]}
        for s in data.get("sites", [])
        if s.get("domain") and s.get("blog_id")
    ]


def get_db():
    db_path = os.path.join(PROJECT_ROOT, "data", "analytics.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_bing_tables(conn):
    """Bing 전용 테이블 생성"""
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS bing_daily_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blog_id TEXT NOT NULL,
        date TEXT NOT NULL,
        clicks INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        avg_position REAL DEFAULT 0.0,
        crawled_pages INTEGER DEFAULT 0,
        collected_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(blog_id, date)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS bing_keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blog_id TEXT NOT NULL,
        date TEXT NOT NULL,
        query TEXT NOT NULL,
        clicks INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        avg_position REAL DEFAULT 0.0,
        collected_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(blog_id, date, query)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS bing_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blog_id TEXT NOT NULL,
        date TEXT NOT NULL,
        page TEXT NOT NULL,
        clicks INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        collected_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(blog_id, date, page)
    )
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_bing_summary_blog_date ON bing_daily_summary(blog_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bing_kw_blog_date ON bing_keywords(blog_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bing_pages_blog_date ON bing_pages(blog_id, date)")

    conn.commit()


def collect_all(verbose=True):
    """전체 활성 블로그의 Bing 데이터 수집"""
    api_keys = _get_api_keys()
    if not api_keys:
        if verbose:
            print("[ERR] Bing API key 없음")
        return {"summary": 0, "keywords": 0, "pages": 0}

    # 각 key별 접근 가능 사이트 매핑
    key_sites = {}
    for key in api_keys:
        sites = _get_accessible_sites(key)
        key_sites[key] = sites
        if verbose:
            print(f"[KEY] ...{key[-8:]}: {len(sites)}개 사이트")

    blogs = load_active_blogs()
    conn = get_db()
    _init_bing_tables(conn)
    c = conn.cursor()

    if verbose:
        print(f"\n=== Bing 수집 시작 ({len(blogs)}개 블로그) ===\n")

    total_summary = 0
    total_keywords = 0
    total_pages = 0

    for blog in blogs:
        bid = blog["id"]
        domain = blog.get("domain", "")
        site_url = f"https://{domain}/"

        # 이 사이트에 접근 가능한 key 찾기
        api_key = None
        for key, sites in key_sites.items():
            if site_url.rstrip("/") in sites or site_url in sites:
                api_key = key
                break

        if not api_key:
            if verbose:
                print(f"  [{bid}] SKIP — Bing 미등록")
            continue

        if verbose:
            print(f"  [{bid}]", end=" ")

        summary_count = 0
        kw_count = 0
        pg_count = 0

        # 1. RankAndTrafficStats (사이트 일별 통계)
        try:
            resp = requests.get(
                f"{BASE}/GetRankAndTrafficStats",
                params={"apikey": api_key, "siteUrl": site_url},
                timeout=30,
            )
            data = resp.json()
            rows = data.get("d", data) if isinstance(data, dict) else data
            if isinstance(rows, list):
                for r in rows:
                    date_str = _parse_bing_date(r.get("Date", ""))
                    if not date_str:
                        continue
                    c.execute("""
                        INSERT INTO bing_daily_summary
                        (blog_id, date, clicks, impressions, avg_position, crawled_pages)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(blog_id, date) DO UPDATE SET
                            clicks=excluded.clicks, impressions=excluded.impressions,
                            avg_position=excluded.avg_position,
                            crawled_pages=excluded.crawled_pages,
                            collected_at=datetime('now','localtime')
                    """, (bid, date_str, r.get("Clicks", 0), r.get("Impressions", 0),
                          r.get("AvgImpressionPosition", 0), r.get("CrawledPages", 0)))
                    summary_count += 1
        except Exception as e:
            if verbose:
                print(f"summary_err:{str(e)[:40]}", end=" ")

        # 2. QueryStats (키워드별)
        try:
            resp = requests.get(
                f"{BASE}/GetQueryStats",
                params={"apikey": api_key, "siteUrl": site_url},
                timeout=30,
            )
            data = resp.json()
            rows = data.get("d", data) if isinstance(data, dict) else data
            if isinstance(rows, list):
                for r in rows:
                    date_str = _parse_bing_date(r.get("Date", ""))
                    query = r.get("Query", "")
                    if not date_str or not query:
                        continue
                    c.execute("""
                        INSERT INTO bing_keywords
                        (blog_id, date, query, clicks, impressions, avg_position)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(blog_id, date, query) DO UPDATE SET
                            clicks=excluded.clicks, impressions=excluded.impressions,
                            avg_position=excluded.avg_position,
                            collected_at=datetime('now','localtime')
                    """, (bid, date_str, query, r.get("Clicks", 0),
                          r.get("Impressions", 0), r.get("AvgImpressionPosition", 0)))
                    kw_count += 1
        except Exception as e:
            if verbose:
                print(f"kw_err:{str(e)[:40]}", end=" ")

        # 3. PageStats (페이지별)
        try:
            resp = requests.get(
                f"{BASE}/GetPageStats",
                params={"apikey": api_key, "siteUrl": site_url},
                timeout=30,
            )
            data = resp.json()
            rows = data.get("d", data) if isinstance(data, dict) else data
            if isinstance(rows, list):
                for r in rows:
                    date_str = _parse_bing_date(r.get("Date", ""))
                    page = r.get("Query", "")
                    if not date_str or not page:
                        continue
                    c.execute("""
                        INSERT INTO bing_pages
                        (blog_id, date, page, clicks, impressions)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(blog_id, date, page) DO UPDATE SET
                            clicks=excluded.clicks, impressions=excluded.impressions,
                            collected_at=datetime('now','localtime')
                    """, (bid, date_str, page, r.get("Clicks", 0), r.get("Impressions", 0)))
                    pg_count += 1
        except Exception as e:
            if verbose:
                print(f"pg_err:{str(e)[:40]}", end=" ")

        total_summary += summary_count
        total_keywords += kw_count
        total_pages += pg_count

        if verbose:
            print(f"summary:{summary_count} kw:{kw_count} pg:{pg_count}")

        conn.commit()
        time.sleep(0.3)

    conn.close()

    if verbose:
        print(f"\n=== Bing 수집 완료 ===")
        print(f"일별: {total_summary}, 키워드: {total_keywords}, 페이지: {total_pages}")

    return {"summary": total_summary, "keywords": total_keywords, "pages": total_pages}


if __name__ == "__main__":
    collect_all()
