#!/usr/bin/env python3
"""85개 블로그 sitemap 병렬 수집 — 게시글 inventory 1단계"""
import json, re, sys, threading, urllib.request, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

REG = json.load(open("/tmp/5000-content-audit/blog_registry_raw.json"))
SITEMAP_CACHE = "/tmp/5000-content-audit/sitemaps"

def fetch_sitemap(b):
    bid = b.get("id")
    dom = b.get("domain")
    if not dom:
        return {"blog": bid, "status": "NO_DOMAIN", "url_count": 0}
    url = f"https://{dom}/sitemap.xml"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0"})
        r = urllib.request.urlopen(req, timeout=25)
        body = r.read()
        locs = re.findall(rb"<loc>(.*?)</loc>", body)
        sha = hashlib.sha256(body).hexdigest()[:16]
        with open(f"{SITEMAP_CACHE}/{bid}.xml", "wb") as f:
            f.write(body)
        return {"blog": bid, "status": r.status, "url_count": len(locs),
                "sha256_16": sha, "bytes": len(body),
                "first_loc": locs[0].decode()[:80] if locs else None}
    except Exception as e:
        return {"blog": bid, "status": "ERROR", "error": str(e)[:80], "url_count": 0}

results = []
with ThreadPoolExecutor(max_workers=16) as ex:
    futs = {ex.submit(fetch_sitemap, b): b for b in REG}
    for f in as_completed(futs):
        results.append(f.result())

results.sort(key=lambda x: x["blog"])
json.dump(results, open("/tmp/5000-content-audit/sitemap_scan.json", "w"), ensure_ascii=False, indent=1)

ok = [r for r in results if r["status"] == 200]
err = [r for r in results if r["status"] != 200]
total_urls = sum(r["url_count"] for r in ok)
print(f"블로그 {len(results)}개 중 sitemap 200: {len(ok)}, 실패/기타: {len(err)}")
print(f"총 URL 수(200 응답만): {total_urls}")
print("--- 실패 목록 ---")
for r in err:
    print(f"  {r['blog']}: {r['status']} {r.get('error','')}")
print("--- URL 수 분포 ---")
counts = sorted((r["url_count"], r["blog"]) for r in ok)
for c, b in counts[:5] + counts[-5:]:
    print(f"  {b}: {c}")