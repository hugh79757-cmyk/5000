"""best_categories.py — BEST_CATEGORY_MAP for best-* fleet (Phase 75).

Wave0 probe (2026-08-30) lock:
- Correct API path: /v2/providers/affiliate_open_api/apis/openapi/v1/products/bestcategories/{categoryId}
  (path-param, not query param). coupang_client.py L67 old query path returns 404 [RESEARCH A4].
- Envelope: flat list data=[...] (not data.productData). Search uses data.productData;
  bestcategories uses data flat list — see live probe.
- Verified IDs (live 200, rCode 0, len 20):
  - 1020 → 주방용품 (best-kitchen-hugo) [RESEARCH L190-194 kitchen hint, corrected from assumed 1006]
  - 1010 → 뷰티 (best-beauty-hugo)
  - 1011 → 출산/유아 (best-baby-hugo)
  1006 returns rCode 0 but data None (empty best) — not usable.
  Invalid IDs 178144/99999 return rCode 400.

Wave0 verification commands:
  python3 -c "from pipelines.curation.coupang_client import get_best_categories; print(get_best_categories('1006'))" -> old path 404
  Manual HMAC path probe -> /v1/products/bestcategories/{id} 200 with correct shape

Cloudflare gate (2026-08-30): wrangler pages project list = 100 (limit 100) — at limit,
  +3 would exceed. Requires consolidation before Wave3 deploy. Code side (Wave1) unaffected.

Envelope branching decision (T00-3):
  if isinstance(body.get("data"), dict) and "productData" in body["data"]:
      products = body["data"]["productData"]
  elif isinstance(body.get("data"), list):
      products = body["data"]
  else:
      products = []
  best_collector.py implements both branches [RESEARCH L469].
"""

BEST_CATEGORY_MAP = {
    "best-kitchen-hugo": "1020",  # 주방용품 — live verified 20 items, flat list [RESEARCH L190]
    "best-beauty-hugo": "1010",   # 뷰티 — live verified 20 items
    "best-baby-hugo": "1011",     # 출산/유아 — live verified 20 items
}

BEST_CACHE_DAYS = 1  # [RESEARCH Open Q 2 L684, Pattern 1 L460] best lists change daily


def verify_all_categories() -> dict:
    """Live probe helper: call bestcategories for each mapped ID, log len + categoryName sample.

    Returns dict blog_id -> {status_code, rCode, len, categoryName_sample}.
    Uses direct HMAC path (v1/products/bestcategories/{id}) to avoid coupang_client stale path.
    Falls back to coupang_client.get_best_categories if patched.
    """
    import os
    import hashlib
    import hmac as _hmac
    from datetime import datetime, timezone
    from urllib.parse import urlencode

    # Try via coupang_client first if path fixed; otherwise manual HMAC path
    results = {}
    try:
        from pipelines.curation.coupang_client import get_best_categories as _g
        # Check if old path still used — probe will 404, so use manual path instead
        use_manual = True
    except Exception:
        use_manual = True

    if use_manual:
        import requests
        from dotenv import load_dotenv
        load_dotenv("/Users/twinssn/Projects/5000/.env")
        try:
            load_dotenv(os.path.expanduser("~/.env.common"))
        except Exception:
            pass
        ak = os.getenv("COUPANG_ACCESS_KEY", "")
        sk = os.getenv("COUPANG_SECRET_KEY", "")

        def _hdr(method, path, qs=""):
            dt = datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")
            msg = dt + method + path + qs
            sig = _hmac.new(sk.encode(), msg.encode(), hashlib.sha256).hexdigest()
            return {
                "Authorization": f"CEA algorithm=HmacSHA256, access-key={ak}, signed-date={dt}, signature={sig}",
                "Content-Type": "application/json",
            }

        import requests as _req
        for blog_id, cid in BEST_CATEGORY_MAP.items():
            path = f"/v2/providers/affiliate_open_api/apis/openapi/v1/products/bestcategories/{cid}"
            hdr = _hdr("GET", path, "")
            url = f"https://api-gateway.coupang.com{path}"
            try:
                resp = _req.get(url, headers=hdr, timeout=10)
                body = resp.json() if resp.headers.get("content-type","").startswith("application/json") else {}
                # Fallback try json parse regardless
                if not body:
                    try:
                        body = resp.json()
                    except Exception:
                        body = {}
                data = body.get("data")
                if isinstance(data, list):
                    sample = data[0].get("categoryName", "") if data else ""
                    results[blog_id] = {
                        "categoryId": cid,
                        "status_code": resp.status_code,
                        "rCode": body.get("rCode"),
                        "len": len(data),
                        "categoryName_sample": sample,
                    }
                elif isinstance(data, dict):
                    pd = data.get("productData", [])
                    sample = pd[0].get("categoryName", "") if isinstance(pd, list) and pd else ""
                    results[blog_id] = {
                        "categoryId": cid,
                        "status_code": resp.status_code,
                        "rCode": body.get("rCode"),
                        "len": len(pd) if isinstance(pd, list) else 0,
                        "categoryName_sample": sample,
                        "envelope": "dict.productData",
                    }
                else:
                    results[blog_id] = {
                        "categoryId": cid,
                        "status_code": resp.status_code,
                        "rCode": body.get("rCode"),
                        "rMessage": body.get("rMessage", "")[:120],
                        "len": 0,
                    }
            except Exception as e:
                results[blog_id] = {"categoryId": cid, "error": str(e)[:200]}
            # Log
            r = results[blog_id]
            print(f"{blog_id} ({cid}): status={r.get('status_code')} rCode={r.get('rCode')} len={r.get('len')} sample={r.get('categoryName_sample','')}")
        return results

    # Fallback: coupang_client path (if fixed to path-param)
    for blog_id, cid in BEST_CATEGORY_MAP.items():
        try:
            from pipelines.curation.coupang_client import get_best_categories
            resp = get_best_categories(cid)
            body = resp.get("body", {})
            data = body.get("data")
            if isinstance(data, list):
                sample = data[0].get("categoryName", "") if data else ""
                results[blog_id] = {"categoryId": cid, "status_code": resp["status_code"], "rCode": body.get("rCode"), "len": len(data), "categoryName_sample": sample}
            elif isinstance(data, dict):
                pd = data.get("productData", [])
                sample = pd[0].get("categoryName", "") if pd else ""
                results[blog_id] = {"categoryId": cid, "status_code": resp["status_code"], "rCode": body.get("rCode"), "len": len(pd), "categoryName_sample": sample, "envelope": "dict.productData"}
            else:
                results[blog_id] = {"categoryId": cid, "status_code": resp["status_code"], "rCode": body.get("rCode"), "rMessage": body.get("rMessage","")[:120], "len": 0}
            print(f"{blog_id} ({cid}): {results[blog_id]}")
        except Exception as e:
            results[blog_id] = {"categoryId": cid, "error": str(e)[:200]}
    return results


if __name__ == "__main__":
    verify_all_categories()
