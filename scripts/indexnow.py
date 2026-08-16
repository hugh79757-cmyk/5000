import glob
import json
import os
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
import yaml

STATE_PATH = os.path.join(BASE_DIR, "data", "indexnow_last_status.json")


def _load_indexnow_state():
    """data/indexnow_last_status.json 로드 (없으면 기본 구조)."""
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"updated_at": None, "domains": {}, "any_failure": False}


def _save_indexnow_state(state):
    """data/indexnow_last_status.json 기록 (실패해도 크래시 없이 pass)."""
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _alert_indexnow(msg):
    """기존 텔레그램 헬퍼로 IndexNow 실패 경고 발송 (신규 함수 미생성, 크래시 금지)."""
    try:
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)
        from shared.telegram_notifier import send_dashboard_alert
        send_dashboard_alert("indexnow", "indexnow_submission", "fail", msg)
    except Exception:
        pass

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
    return {r[0] for r in conn.execute("SELECT url FROM submitted_urls").fetchall()}


def _parse_sitemap(content, base_domain):
    """Sitemap XML에서 URL 추출. sitemap index 중첩 처리 포함."""
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
    failures_this = []  # (engine, status_or_error)

    # 연속 실패 추적을 위한 상태 로드 (도메인별 엔진별 consecutive_failures)
    state = _load_indexnow_state()
    dom = state.setdefault("domains", {}).setdefault(
        domain, {"engines": {}}
    )
    engines_state = dom.setdefault("engines", {})

    for engine in ENGINES:
        try:
            r = requests.post(
                engine, json=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=15
            )
            code = r.status_code
            print(f"    {engine} -> {code}")
            if code in (200, 202):
                ok += 1
                engines_state[engine] = {"consecutive_failures": 0, "last_status": code}
            else:
                failures_this.append((engine, code))
                prev = engines_state.get(engine, {})
                cf = prev.get("consecutive_failures", 0) + 1
                engines_state[engine] = {"consecutive_failures": cf, "last_status": code}
        except Exception as e:
            print(f"    {engine} -> {e}")
            failures_this.append((engine, str(e)))
            prev = engines_state.get(engine, {})
            cf = prev.get("consecutive_failures", 0) + 1
            engines_state[engine] = {"consecutive_failures": cf, "last_status": "error"}

    # 경고 게이팅: 사고 발생 시점(첫 403) 또는 연속실패 3회 도달 시 1회 발송
    # (매 회차 반복 발송 방지 — detect-only, 재시도/자동수정 없음)
    alert_lines = []
    for engine, code in failures_this:
        cf = engines_state[engine]["consecutive_failures"]
        if (code == 403 and cf == 1) or cf == 3:
            alert_lines.append(f"{engine} status={code} consecutive={cf}")
    if alert_lines:
        _alert_indexnow(
            f"domain={domain} IndexNow 제출 실패: " + "; ".join(alert_lines)
        )

    state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["any_failure"] = bool(state.get("any_failure", False) or failures_this)
    _save_indexnow_state(state)
    return ok


def save(conn, domain, urls, code) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for u in urls:
        conn.execute(
            "INSERT OR REPLACE INTO submitted_urls VALUES (?,?,?,?)",
            (u, domain, now, code)
        )
    conn.commit()


def run() -> None:
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
            print("  -> 제출 실패")

    conn.close()
    print(f"\n=== 완료: {t_ok}/{t_new} URLs 제출 ===")


if __name__ == "__main__":
    run()
