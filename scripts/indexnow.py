import os
import sys
import glob
import sqlite3
import requests
import xml.etree.ElementTree as ET
import yaml
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "data", "indexnow.db")
KEY      = "b8f4e2a1c3d5e6f7a8b9c0d1e2f3a4b5"
KEY_TPL  = "https://{domain}/{key}.txt"

ENGINES = [
    "https://api.indexnow.org/indexnow",
    "https://www.bing.com/indexnow",
    "https://yandex.com/indexnow",
]


def load_domains():
    domains = []
    for fpath in sorted(glob.glob(os.path.join(BASE_DIR, "config/blogs.d/*.yaml"))):
        with open(fpath) as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict) and "blogs" in data:
            entries = data["blogs"]
        else:
            continue
        for blog in entries:
            if blog.get("status") != "active":
                continue
            if blog.get("platform") not in ("hugo", "cloudflare"):
                continue
            domain = blog.get("domain", "")
            if domain:
                domains.append(domain)

    # yaml 미등록 독립 Hugo 사이트
    EXTRA_DOMAINS = [
        "informationhot.kr",
        "issue.techpawz.com",
        "rotcha.kr",
        "info.techpawz.com",
        "aikorea24.kr",
        "cert.aikorea24.kr",
        "keyword.aikorea24.kr",
        "heritage.aikorea24.kr",
    ]
    for d in EXTRA_DOMAINS:
        if d not in domains:
            domains.append(d)

    return domains


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS submitted_urls "
        "(url TEXT PRIMARY KEY, domain TEXT, submitted_at TEXT, status_code INTEGER)"
    )
    conn.commit()
    return conn


def get_submitted(conn):
    return set(r[0] for r in conn.execute("SELECT url FROM submitted_urls").fetchall())


def _parse_sitemap(content, base_domain):
    """sitemap XML에서 URL 추출. sitemap index 중첩 처리 포함."""
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(content)
    urls = [loc.text.strip() for loc in root.findall(".//s:loc", ns) if loc.text]
    # sitemap index 처리
    if not urls:
        for sm in root.findall(".//s:sitemap/s:loc", ns):
            try:
                r2 = requests.get(sm.text.strip(), timeout=10)
                r2.raise_for_status()
                root2 = ET.fromstring(r2.content)
                urls += [loc.text.strip() for loc in root2.findall(".//s:loc", ns) if loc.text]
            except Exception:
                pass
    return urls


SITEMAP_CANDIDATES = [
    "sitemap.xml",
    "sitemap-index.xml",
    "sitemap_index.xml",
]


def fetch_sitemap(domain):
    for candidate in SITEMAP_CANDIDATES:
        try:
            resp = requests.get(f"https://{domain}/{candidate}", timeout=10)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            urls = _parse_sitemap(resp.content, domain)
            if urls:
                return urls
        except Exception:
            continue
    print(f"  [WARN] sitemap 조회 실패 {domain}: 모든 후보 실패")
    return []


def submit(domain, urls):
    if not urls:
        return 0
    payload = {
        "host": domain,
        "key": KEY,
        "keyLocation": KEY_TPL.format(domain=domain, key=KEY),
        "urlList": urls[:10000],
    }
    ok = 0
    for engine in ENGINES:
        try:
            r = requests.post(
                engine, json=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=15
            )
            print(f"    {engine} -> {r.status_code}")
            if r.status_code in (200, 202):
                ok += 1
        except Exception as e:
            print(f"    {engine} -> {e}")
    return ok


def save(conn, domain, urls, code):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for u in urls:
        conn.execute(
            "INSERT OR REPLACE INTO submitted_urls VALUES (?,?,?,?)",
            (u, domain, now, code)
        )
    conn.commit()


def run():
    print(f"=== IndexNow 5000 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===")
    conn   = init_db()
    already = get_submitted(conn)
    domains = load_domains()
    print(f"대상 도메인: {len(domains)}개\n")

    t_new = 0
    t_ok  = 0

    for domain in domains:
        print(f"[{domain}]")
        all_urls  = fetch_sitemap(domain)
        new_urls  = [u for u in all_urls if u not in already]
        print(f"  sitemap: {len(all_urls)}  /  신규: {len(new_urls)}")
        if not new_urls:
            continue
        t_new += len(new_urls)
        success = submit(domain, new_urls)
        if success > 0:
            save(conn, domain, new_urls, 200)
            t_ok += len(new_urls)
            print(f"  -> {len(new_urls)}건 제출 완료 ({success}/{len(ENGINES)} 엔진)")
        else:
            print(f"  -> 제출 실패")

    conn.close()
    print(f"\n=== 완료: {t_ok}/{t_new} URLs 제출 ===")


if __name__ == "__main__":
    run()
