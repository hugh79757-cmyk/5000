"""색인 제출 모듈 — Google Indexing API + IndexNow (Bing/Yandex/Naver)"""
import os
import sys
import json
import sqlite3
import time
import hashlib
import requests
import yaml
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_blogs_map():
    """blog_id → domain 매핑"""
    path = os.path.join(PROJECT_ROOT, "config", "blogs.yaml")
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    return {
        b["id"]: b for b in config.get("blogs", [])
        if b.get("status") == "active"
    }


def get_today_urls(date_str=None):
    """content.db publish_ledger에서 특정 날짜에 발행된 URL 목록 반환"""
    db_path = os.path.join(PROJECT_ROOT, "data", "content.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    try:
        c.execute("""
            SELECT blog_id, published_url, created_at
            FROM publish_ledger
            WHERE date(created_at) = ?
              AND published_url NOT LIKE 'pending://%'
              AND status = 'published'
            ORDER BY created_at
        """, (date_str,))
        rows = c.fetchall()
    except Exception as e:
        print(f"[ERR] publish_ledger 조회 실패: {e}")
        conn.close()
        return []

    conn.close()

    blogs = load_blogs_map()
    urls = []
    for blog_id, published_url, created_at in rows:
        blog = blogs.get(blog_id)
        if not blog:
            continue
        domain = blog.get("domain", "")
        urls.append({
            "url": published_url,
            "blog_id": blog_id,
            "domain": domain,
            "published_at": created_at,
            "language": blog.get("language", "ko"),
        })

    return urls


# ─── Google Indexing API ───

def submit_google_indexing(urls, verbose=True):
    """Google Indexing API로 URL 제출"""
    from analytics.auth import get_credentials
    from googleapiclient.discovery import build

    creds = get_credentials()
    service = build("indexing", "v3", credentials=creds)

    results = {"success": 0, "fail": 0, "errors": []}

    for item in urls:
        url = item["url"]
        try:
            body = {
                "url": url,
                "type": "URL_UPDATED",
            }
            resp = service.urlNotifications().publish(body=body).execute()
            if verbose:
                print(f"  [Google OK] {url}")
            results["success"] += 1
        except Exception as e:
            err_msg = str(e)
            if verbose:
                print(f"  [Google FAIL] {url} — {err_msg[:80]}")
            results["fail"] += 1
            results["errors"].append({"url": url, "error": err_msg[:200]})
        time.sleep(0.2)

    return results


# ─── IndexNow (Bing, Yandex, Naver, Seznam, Yep) ───

INDEXNOW_KEY_PATH = os.path.join(PROJECT_ROOT, "data", "indexnow_key.txt")


def get_or_create_indexnow_key():
    """IndexNow API key 가져오기/생성"""
    if os.path.exists(INDEXNOW_KEY_PATH):
        with open(INDEXNOW_KEY_PATH, "r") as f:
            return f.read().strip()

    # 새 키 생성 (32자 hex)
    key = hashlib.md5(f"5000-indexnow-{datetime.now().isoformat()}".encode()).hexdigest()
    with open(INDEXNOW_KEY_PATH, "w") as f:
        f.write(key)
    print(f"[IndexNow] 새 키 생성: {key}")
    return key


def submit_indexnow(urls, verbose=True):
    """
    IndexNow API로 URL 일괄 제출.
    한 번 제출하면 Bing, Yandex, Naver, Seznam, Yep에 전파.
    도메인별로 그룹핑하여 제출.
    """
    key = get_or_create_indexnow_key()
    endpoint = "https://api.indexnow.org/indexnow"

    # 도메인별 그룹핑
    from collections import defaultdict
    domain_urls = defaultdict(list)
    for item in urls:
        domain_urls[item["domain"]].append(item["url"])

    results = {"success": 0, "fail": 0, "errors": []}

    for domain, url_list in domain_urls.items():
        payload = {
            "host": domain,
            "key": key,
            "keyLocation": f"https://{domain}/{key}.txt",
            "urlList": url_list,
        }

        try:
            resp = requests.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=30,
            )
            if resp.status_code in (200, 202):
                if verbose:
                    print(f"  [IndexNow OK] {domain} — {len(url_list)}개 URL")
                results["success"] += len(url_list)
            else:
                if verbose:
                    print(f"  [IndexNow {resp.status_code}] {domain} — {resp.text[:100]}")
                results["fail"] += len(url_list)
                results["errors"].append({
                    "domain": domain,
                    "status": resp.status_code,
                    "body": resp.text[:200],
                })
        except Exception as e:
            if verbose:
                print(f"  [IndexNow ERR] {domain} — {e}")
            results["fail"] += len(url_list)
            results["errors"].append({"domain": domain, "error": str(e)[:200]})

        time.sleep(0.3)

    return results


# ─── 메인: 하루 한번 실행 ───

def daily_index_submit(date_str=None, verbose=True):
    """
    하루에 한 번 실행: 당일 발행된 모든 URL을 Google + IndexNow로 제출.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    urls = get_today_urls(date_str)

    if not urls:
        if verbose:
            print(f"[{date_str}] 발행된 URL 없음. 스킵.")
        return {"google": None, "indexnow": None, "total_urls": 0}

    if verbose:
        print(f"\n=== 색인 제출 ({date_str}) — {len(urls)}개 URL ===\n")

    # 1. Google Indexing API
    if verbose:
        print("[1/2] Google Indexing API")
    google_result = submit_google_indexing(urls, verbose=verbose)

    # 2. IndexNow
    if verbose:
        print(f"\n[2/2] IndexNow (Bing/Yandex/Naver)")
    indexnow_result = submit_indexnow(urls, verbose=verbose)

    if verbose:
        print(f"\n=== 색인 제출 완료 ===")
        print(f"Google:   {google_result['success']} OK / {google_result['fail']} FAIL")
        print(f"IndexNow: {indexnow_result['success']} OK / {indexnow_result['fail']} FAIL")

    # 제출 기록 저장
    log_path = os.path.join(PROJECT_ROOT, "logs", "indexing.log")
    with open(log_path, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] date={date_str} urls={len(urls)} "
                f"google={google_result['success']}/{google_result['fail']} "
                f"indexnow={indexnow_result['success']}/{indexnow_result['fail']}\n")

    return {
        "google": google_result,
        "indexnow": indexnow_result,
        "total_urls": len(urls),
    }


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    daily_index_submit(date_str=date_arg)
