"""
Bing Webmaster 미등록 사이트 자동 등록 + Cloudflare DNS 인증
"""
import os, sys, time, requests, json
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

BING_BASE = "https://ssl.bing.com/webmaster/api.svc/json"
CF_BASE = "https://api.cloudflare.com/client/v4"

BING_KEY = os.getenv("BING_WEBMASTER_API_KEY")
CF_TOKEN = os.getenv("CF_DNS_TOKEN")

# 루트 도메인 → Cloudflare Zone ID 매핑
# Zone ID는 아래에서 자동으로 가져옴
ZONE_CACHE = {}

MISSING_SITES = [
    {"blog_id": "rap3-hugo",       "domain": "5.informationhot.kr"},
    {"blog_id": "rap5-hugo",       "domain": "6.informationhot.kr"},
    {"blog_id": "gap-hugo",        "domain": "7.informationhot.kr"},
    {"blog_id": "flights-hugo",    "domain": "flights.techpawz.com"},
    {"blog_id": "airlines-hugo",   "domain": "airlines.techpawz.com"},
    {"blog_id": "airports-hugo",   "domain": "airports.techpawz.com"},
    {"blog_id": "tours-hugo",      "domain": "tours.techpawz.com"},
    {"blog_id": "trains-hugo",     "domain": "trains.techpawz.com"},
    {"blog_id": "visa-hugo",       "domain": "visa.techpawz.com"},
    {"blog_id": "esim-hugo",       "domain": "esim.techpawz.com"},
    {"blog_id": "michelin-hugo",   "domain": "michelin.techpawz.com"},
    {"blog_id": "watersports-hugo","domain": "watersports.techpawz.com"},
    {"blog_id": "heritage-hugo",   "domain": "heritage.aikorea24.kr"},
    {"blog_id": "keyword-hugo",    "domain": "keyword.aikorea24.kr"},
    {"blog_id": "proto-hugo",      "domain": "proto.informationhot.kr"},
    {"blog_id": "protostats-hugo", "domain": "protostats.informationhot.kr"},
]


def cf_headers():
    return {"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"}


def get_zone_id(root_domain):
    """루트 도메인의 Cloudflare Zone ID 조회"""
    if root_domain in ZONE_CACHE:
        return ZONE_CACHE[root_domain]
    resp = requests.get(
        f"{CF_BASE}/zones",
        headers=cf_headers(),
        params={"name": root_domain}
    )
    data = resp.json()
    if data.get("success") and data["result"]:
        zone_id = data["result"][0]["id"]
        ZONE_CACHE[root_domain] = zone_id
        return zone_id
    return None


def get_root_domain(domain):
    """서브도메인에서 루트 도메인 추출"""
    parts = domain.split(".")
    # 숫자 서브도메인(5.informationhot.kr) 포함 처리
    return ".".join(parts[-2:])


def bing_add_site(site_url):
    """Bing에 사이트 추가"""
    resp = requests.put(
        f"{BING_BASE}/AddSite",
        params={"apikey": BING_KEY},
        headers={"Content-Type": "application/json"},
        data=json.dumps(site_url)
    )
    return resp.status_code == 200


def bing_get_site_info(site_url):
    """Bing 사이트 인증 토큰 조회"""
    resp = requests.get(
        f"{BING_BASE}/GetSiteInfo",
        params={"apikey": BING_KEY, "siteUrl": site_url}
    )
    if resp.status_code == 200:
        data = resp.json()
        site_info = data.get("d", {})
        return site_info
    return None


def bing_verify_site(site_url):
    """Bing 사이트 인증 요청"""
    resp = requests.get(
        f"{BING_BASE}/VerifySite",
        params={"apikey": BING_KEY, "siteUrl": site_url, "verificationCode": "DNS"}
    )
    return resp.status_code == 200, resp.text


def cf_add_cname(zone_id, subdomain, verify_token):
    """Cloudflare에 Bing 인증용 CNAME 추가"""
    # Bing DNS 인증: _bing-site-verification.domain CNAME → verify.bing.com
    name = f"_bing-site-verification.{subdomain}"
    resp = requests.post(
        f"{CF_BASE}/zones/{zone_id}/dns_records",
        headers=cf_headers(),
        json={
            "type": "TXT",
            "name": f"_bing-site-verification",
            "content": verify_token,
            "ttl": 300,
            "proxied": False
        }
    )
    data = resp.json()
    return data.get("success", False), data


def main():
    if not BING_KEY:
        print("[ERR] BING_WEBMASTER_API_KEY 없음")
        sys.exit(1)
    if not CF_TOKEN:
        print("[ERR] CF_DNS_TOKEN 없음")
        sys.exit(1)

    print(f"=== Bing 미등록 사이트 등록 시작 ({len(MISSING_SITES)}개) ===\n")

    for site in MISSING_SITES:
        bid = site["blog_id"]
        domain = site["domain"]
        site_url = f"https://{domain}/"
        root = get_root_domain(domain)

        print(f"[{bid}] {domain}")

        # 1. Zone ID 조회
        zone_id = get_zone_id(root)
        if not zone_id:
            print(f"  ❌ Cloudflare Zone 없음: {root}")
            continue
        print(f"  ✅ Zone ID: {zone_id[:8]}...")

        # 2. Bing에 사이트 추가
        added = bing_add_site(site_url)
        print(f"  {'✅' if added else '⚠️ '} Bing AddSite: {'성공' if added else '이미 등록됐거나 실패'}")
        time.sleep(1)

        # 3. 사이트 인증 토큰 조회
        info = bing_get_site_info(site_url)
        if not info:
            print(f"  ❌ GetSiteInfo 실패")
            continue

        verify_token = info.get("VerificationCode") or info.get("AuthCode")
        is_verified = info.get("IsVerified", False)

        if is_verified:
            print(f"  ✅ 이미 인증 완료")
            continue

        if not verify_token:
            print(f"  ⚠️  인증 토큰 없음: {info}")
            continue

        print(f"  🔑 인증 토큰: {verify_token[:20]}...")

        # 4. Cloudflare DNS에 TXT 레코드 추가
        ok, cf_resp = cf_add_cname(zone_id, domain, verify_token)
        if ok:
            print(f"  ✅ Cloudflare TXT 레코드 추가 완료")
        else:
            err = cf_resp.get("errors", [])
            if err and "already exists" in str(err):
                print(f"  ✅ TXT 레코드 이미 존재")
            else:
                print(f"  ❌ Cloudflare 실패: {err}")
                continue

        # 5. DNS 전파 대기 후 인증
        print(f"  ⏳ DNS 전파 대기 (5초)...")
        time.sleep(5)

        ok, msg = bing_verify_site(site_url)
        print(f"  {'✅' if ok else '❌'} Bing 인증: {msg[:80]}")
        print()
        time.sleep(1)

    print("=== 완료 ===")


if __name__ == "__main__":
    main()
