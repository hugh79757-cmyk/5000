"""색인 제출 모듈 — Google Indexing API (200/일) + IndexNow (무제한)
- Google: 오전/오후 100개씩, 사이트 로테이션, 중복 제출 방지
- IndexNow: 하루 2회, 전체 사이트 미제출 URL만
- sites.yaml 기반 동적 사이트 목록
- 최근 7일 이내 lastmod + 제출 이력 DB로 필터
"""
import os, sys, json, time, hashlib, sqlite3, requests, yaml
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import urlparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
DB_PATH = os.path.join(DATA_DIR, "analytics.db")
STATE_FILE = os.path.join(DATA_DIR, "indexing_state.json")
INDEXNOW_KEY_PATH = os.path.join(DATA_DIR, "indexnow_key.txt")
GOOGLE_PER_RUN = 100
MAX_URLS_PER_SITE = 5
RECENT_DAYS = 7

SKIP_PATTERNS = ["/categories", "/tags", "/en/", "/page/", "/search/",
                 "/archive", "/about", "/contact", "/privacy"]

DOMAIN_ACCOUNT = {
    "rotcha.kr": "twinssn",
    "techpawz.com": "twinssn",
    "informationhot.kr": "informationhot",
    "aikorea24.kr": "aikorea24",
    "tistory.com": "twinssn",
    "farmsolutionint.com": "twinssn",
}

os.makedirs(LOG_DIR, exist_ok=True)

# ─── 텔레그램 알림 ───

def send_telegram(message):
    """텔레그램 알림 발송"""
    import os
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass


os.makedirs(DATA_DIR, exist_ok=True)


# ─── DB: 제출 이력 ───

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS indexing_log (
        url TEXT NOT NULL,
        engine TEXT NOT NULL,
        submitted_at TEXT NOT NULL,
        status TEXT,
        PRIMARY KEY (url, engine)
    )""")
    conn.commit()
    return conn


def is_already_submitted(conn, url, engine):
    row = conn.execute(
        "SELECT 1 FROM indexing_log WHERE url=? AND engine=?", (url, engine)
    ).fetchone()
    return row is not None


def mark_submitted(conn, url, engine, status="ok"):
    conn.execute(
        "INSERT OR REPLACE INTO indexing_log (url, engine, submitted_at, status) VALUES (?,?,?,?)",
        (url, engine, datetime.now().isoformat(), status)
    )
    conn.commit()


# ─── 사이트 목록 ───

def load_sites():
    path = os.path.join(PROJECT_ROOT, "dashboard", "sites.yaml")
    with open(path) as f:
        data = yaml.safe_load(f)
    sites = []
    for s in data.get("sites", []):
        domain = s.get("domain", "").strip()
        if domain:
            sites.append(domain)
    return sorted(sites)


def get_root_domain(domain):
    parts = domain.split(".")
    return ".".join(parts[-2:])


def get_account_for_domain(domain):
    root = get_root_domain(domain)
    return DOMAIN_ACCOUNT.get(root, "twinssn")


# ─── 로테이션 상태 ───

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_date": "", "last_offset": 0, "run_count": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ─── 사이트맵 파싱 (최근 7일 + 미제출만) ───

def fetch_new_urls(domain, conn, engine, max_urls=5):
    """사이트맵 또는 Atom 피드에서 최근 7일 이내 & 미제출 URL만 반환"""
    cutoff = (datetime.now() - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d")
    entries = _fetch_from_sitemap(domain, cutoff)
    if not entries:
        entries = _fetch_from_atom(domain, cutoff)

    result = []
    for u, mod in entries:
        if is_already_submitted(conn, u, engine):
            continue
        result.append(u)
        if len(result) >= max_urls:
            break
    return result


def _fetch_from_sitemap(domain, cutoff):
    """sitemap.xml에서 최근 URL 추출"""
    site_url = f"https://{domain}"
    candidates = [f"{site_url}/sitemap.xml", f"{site_url}/sitemap-index.xml"]

    for sitemap_url in candidates:
        try:
            resp = requests.get(sitemap_url, timeout=10)
            if resp.status_code != 200:
                continue

            root = ET.fromstring(resp.content)
            ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            sitemaps = root.findall("s:sitemap/s:loc", ns)
            if sitemaps:
                sub_url = None
                for sm in sitemaps:
                    if "/en/" in sm.text:
                        continue
                    sub_url = sm.text
                    break
                if not sub_url:
                    sub_url = sitemaps[0].text
                try:
                    sub_resp = requests.get(sub_url, timeout=10)
                    if sub_resp.status_code == 200:
                        root = ET.fromstring(sub_resp.content)
                except Exception:
                    continue

            entries = []
            has_lastmod = False
            for url_elem in root.findall("s:url", ns):
                loc = url_elem.find("s:loc", ns)
                lastmod = url_elem.find("s:lastmod", ns)
                if loc is None or not loc.text:
                    continue
                u = loc.text
                mod = lastmod.text[:10] if lastmod is not None and lastmod.text else None

                if mod:
                    has_lastmod = True
                if not mod or mod < cutoff:
                    continue
                upath = urlparse(u).path.rstrip("/")
                if not upath:
                    continue
                if any(p in u for p in SKIP_PATTERNS):
                    continue
                entries.append((u, mod))

            if has_lastmod and entries:
                entries.sort(key=lambda x: x[1], reverse=True)
                return entries
            # lastmod 없는 사이트맵 → Atom 폴백
            if not has_lastmod:
                return []
            return entries
        except Exception:
            continue
    return []


def _fetch_from_atom(domain, cutoff):
    """Blogger/Tistory Atom 피드에서 최근 URL 추출"""
    feed_urls = [
        f"https://{domain}/atom.xml?redirect=false&max-results=20",
        f"https://{domain}/feeds/posts/default?alt=atom&max-results=20",
        f"https://{domain}/rss",
    ]

    for feed_url in feed_urls:
        try:
            resp = requests.get(feed_url, timeout=10)
            if resp.status_code != 200:
                continue

            root = ET.fromstring(resp.content)
            ns_atom = {"a": "http://www.w3.org/2005/Atom"}

            entries = []

            # Atom 형식
            for entry in root.findall("a:entry", ns_atom):
                published = entry.find("a:published", ns_atom)
                updated = entry.find("a:updated", ns_atom)
                date_text = (updated.text if updated is not None else
                             published.text if published is not None else None)
                if not date_text:
                    continue
                mod = date_text[:10]
                if mod < cutoff:
                    continue

                # 링크 찾기 (rel=alternate)
                link = None
                for l in entry.findall("a:link", ns_atom):
                    if l.get("rel") == "alternate":
                        link = l.get("href")
                        break
                if not link:
                    continue
                if any(p in link for p in SKIP_PATTERNS):
                    continue
                entries.append((link, mod))

            if entries:
                entries.sort(key=lambda x: x[1], reverse=True)
                return entries
        except Exception:
            continue
    return []


# ─── Google Indexing API ───

def submit_google(sites, max_total, conn, verbose=True, urls_per_site=2):
    from analytics.auth import get_credentials
    from google.auth.transport.requests import Request as AuthRequest

    account_domains = defaultdict(list)
    for d in sites:
        acc = get_account_for_domain(d)
        account_domains[acc].append(d)

    total = 0
    results = {"success": 0, "fail": 0, "skip": 0, "quota_hit": False, "submitted_domains": {}}

    for account, doms in account_domains.items():
        try:
            creds = get_credentials(account)
            creds.refresh(AuthRequest())
        except Exception as e:
            if verbose:
                print(f"  [AUTH FAIL] {account}: {e}")
            continue

        headers = {
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json",
        }

        for domain in doms:
            if total >= max_total:
                results["quota_hit"] = True
                break

            urls = fetch_new_urls(domain, conn, "google", max_urls=urls_per_site)
            if not urls:
                results["skip"] += 1
                continue

            remaining = max_total - total
            urls = urls[:remaining]

            if verbose:
                print(f"  {domain}: {len(urls)}개")

            for url in urls:
                try:
                    resp = requests.post(
                        "https://indexing.googleapis.com/v3/urlNotifications:publish",
                        headers=headers,
                        json={"url": url, "type": "URL_UPDATED"},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        if verbose:
                            print(f"    [G OK] {url}")
                        mark_submitted(conn, url, "google", "ok")
                        results["success"] += 1
                        results["submitted_domains"][domain] = results["submitted_domains"].get(domain, 0) + 1
                    elif resp.status_code == 429:
                        if verbose:
                            print(f"    [G QUOTA] 쿼터 초과")
                        results["quota_hit"] = True
                        return results
                    else:
                        if verbose:
                            print(f"    [G {resp.status_code}] {url}")
                        results["fail"] += 1
                except Exception as e:
                    if verbose:
                        print(f"    [G ERR] {url} — {e}")
                    results["fail"] += 1
                total += 1
                time.sleep(0.2)

    return results


# ─── IndexNow ───

def get_indexnow_key():
    if os.path.exists(INDEXNOW_KEY_PATH):
        with open(INDEXNOW_KEY_PATH) as f:
            return f.read().strip()
    key = hashlib.md5(f"blogdex-indexnow-{datetime.now().isoformat()}".encode()).hexdigest()
    with open(INDEXNOW_KEY_PATH, "w") as f:
        f.write(key)
    return key


def submit_indexnow(sites, conn, verbose=True):
    key = get_indexnow_key()
    endpoint = "https://api.indexnow.org/indexnow"
    results = {"success": 0, "fail": 0, "skip": 0}

    for domain in sites:
        urls = fetch_new_urls(domain, conn, "indexnow", max_urls=MAX_URLS_PER_SITE)
        if not urls:
            results["skip"] += 1
            continue

        payload = {
            "host": domain,
            "key": key,
            "keyLocation": f"https://{domain}/{key}.txt",
            "urlList": urls,
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
                    print(f"  [IN OK] {domain} — {len(urls)}개")
                for u in urls:
                    mark_submitted(conn, u, "indexnow", "ok")
                results["success"] += len(urls)
            else:
                if verbose:
                    print(f"  [IN {resp.status_code}] {domain}")
                results["fail"] += len(urls)
        except Exception as e:
            if verbose:
                print(f"  [IN ERR] {domain} — {e}")
            results["fail"] += len(urls)
        time.sleep(0.1)

    return results


# ─── 메인 ───

def select_rotation_sites(sites, state, count):
    """블로그 단위 로테이션: offset부터 count개 블로그 선택"""
    n = len(sites)
    if n == 0:
        return []
    offset = state.get("last_offset", 0) % n
    selected = []
    for i in range(count):
        idx = (offset + i) % n
        selected.append(sites[idx])
    return selected


def run(verbose=True):
    sites = load_sites()
    state = load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()

    if state["last_date"] != today:
        state["last_date"] = today
        state["last_offset"] = 0
        state["run_count"] = 0

    run_num = state["run_count"] + 1
    n = len(sites)

    # 블로그 수에 따라 사이트당 URL 수 자동 계산
    # 절반의 블로그를 한 번에 처리, 사이트당 균등 분배
    blogs_per_run = max(1, n // 2)
    if blogs_per_run > n:
        blogs_per_run = n
    urls_per_site = max(1, GOOGLE_PER_RUN // blogs_per_run)
    urls_per_site = min(urls_per_site, MAX_URLS_PER_SITE)

    # 로테이션으로 이번 실행 대상 블로그 선택
    google_sites = select_rotation_sites(sites, state, blogs_per_run)

    if verbose:
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n{'='*50}")
        print(f"색인 제출 #{run_num} ({today} {now})")
        print(f"전체: {n}개 | 이번 대상: {blogs_per_run}개 | 사이트당: {urls_per_site}개")
        print(f"오프셋: {state.get('last_offset', 0)}")
        print(f"{'='*50}")

    # 1. Google — 로테이션된 블로그만
    if verbose:
        print(f"\n[Google Indexing] 최대 {GOOGLE_PER_RUN}개")
    g_result = submit_google(google_sites, GOOGLE_PER_RUN, conn, verbose=verbose,
                             urls_per_site=urls_per_site)

    # 2. IndexNow — 전체 사이트 (제한 없으므로)
    if verbose:
        print(f"\n[IndexNow] 전체 {n}개 사이트")
    in_result = submit_indexnow(sites, conn, verbose=verbose)

    # 다음 실행시 후반 블로그부터
    state["last_offset"] = (state.get("last_offset", 0) + blogs_per_run) % n
    state["run_count"] = run_num
    save_state(state)

    # 텔레그램 알림
    if g_result["success"] > 0 or g_result["fail"] > 0:
        msg_lines = [f"<b>색인 제출 #{run_num}</b> ({today})"]
        msg_lines.append(f"Google: {g_result['success']} OK / {g_result['fail']} FAIL")
        msg_lines.append(f"IndexNow: {in_result['success']} OK / {in_result['fail']} FAIL")
        if g_result.get("submitted_domains"):
            msg_lines.append("")
            msg_lines.append(f"<b>Google 색인 요청 블로그 ({len(g_result['submitted_domains'])}개):</b>")
            for d, cnt in sorted(g_result["submitted_domains"].items()):
                msg_lines.append(f"  {d}: {cnt}건")
        send_telegram("\n".join(msg_lines))

    log_line = (f"[{datetime.now().isoformat()}] run={run_num} "
                f"sites={blogs_per_run}/{n} per_site={urls_per_site} "
                f"google={g_result['success']}/{g_result['fail']}(skip:{g_result['skip']}) "
                f"indexnow={in_result['success']}/{in_result['fail']}(skip:{in_result['skip']})\n")
    log_path = os.path.join(LOG_DIR, "indexing.log")
    with open(log_path, "a") as f:
        f.write(log_line)

    if verbose:
        print(f"\n=== 결과 ===")
        print(f"Google:   {g_result['success']} OK / {g_result['fail']} FAIL / {g_result['skip']} skip")
        print(f"IndexNow: {in_result['success']} OK / {in_result['fail']} FAIL / {in_result['skip']} skip")
        print(f"다음 오프셋: {state['last_offset']}")

    conn.close()
    return {"google": g_result, "indexnow": in_result}


if __name__ == "__main__":
    run()
