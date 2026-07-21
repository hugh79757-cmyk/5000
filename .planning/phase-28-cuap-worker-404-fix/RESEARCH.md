# RESEARCH.md — Phase 28: CUAP Worker 404→500 Fix

**Last updated:** 2026-07-21
**Method:** Cloudflare Workers SDK docs via Context7 (`/cloudflare/workers-sdk`) + empirical observation from Phase 27 verification turn.

---

## 1. Deciding question

When a Cloudflare Worker calls `env.ASSETS.fetch(pathname)` for a path that does **not** match any deployed static asset, does the binding:
- **(a)** throw a JS exception, or
- **(b)** return a `Response` (the configured `not_found_handling = "404-page"` page, status 404)?

## 2. Finding (official Cloudflare Workers SDK docs)

- `Assets` binding config supports `not_found_handling: "404-page" | "single-page-application" | "none"`. ([workers-sdk `environment.ts`](https://github.com/cloudflare/workers-sdk/blob/main/packages/workers-utils/src/config/environment.ts))
- The asset worker handler (`workers-shared/asset-worker/src/handler.ts`) resolves a miss to a **Response object**, not a throw:
  ```ts
  case NotFoundResponse.status:
      return new NotFoundResponse(body, { headers });
  ```
  i.e. a missing asset becomes a **404 Response** (the 404-page), delivered normally.
- Caveat: the **legacy** `getAssetFromKV` (kv-asset-handler) **throws** `NotFoundError`/`KVError` on a miss. The modern `ASSETS` binding used by kitchen-hugo's `[assets]` `wrangler.toml` returns a Response.

## 3. Implication for the two worker variants

| Variant | Code | Missing-asset behavior | Verdict |
|---------|------|------------------------|---------|
| 142-byte shared (health/pet/beauty/camping/baby) | `return await env.ASSETS.fetch(url.pathname)` — no try/catch | ASSETS returns 404-page Response → served as **404**. Structurally correct in modern model. | ✅ Correct, but not defensive (an unexpected throw → uncaught → platform 500) |
| 268-byte kitchen | `try { … } catch (e) { return new Response('Error', {status:500}) }` | Any exception (incl. a thrown miss on some runtime paths) is converted to a generic **500** | ❌ BUG — this is the 500 source |

## 4. Empirical observation (prior turn)

- kitchen-hugo, typo'd (non-existent) slug → **HTTP 500**, body `Error`.
- kitchen-hugo, correct slug → **200**.
- The 142-byte shared version was not separately tested for missing assets but is structurally correct per (2).

## 5. Sharing conclusion

- 5 blogs (health, pet, beauty, camping, baby) share a **byte-identical** 142-byte worker (`md5 3fece1c5b4b2fd725e8166968e7627df`).
- `kitchen-hugo` is the **divergent** 268-byte bug source (`md5 d25a7783bfe509f593ff6e01f3054eab`).
- After fix, all 6 should carry the **same canonical** worker (unified, defensive).

## 6. Canonical worker (recommended)

Returns the `ASSETS.fetch` result directly (relies on `not_found_handling = "404-page"` to serve the 404 page as a 404 Response). Wraps in `try/catch` that returns **404** (never 500) on any throw — defensive against runtime/version edge cases.

```js
export default {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);
      return await env.ASSETS.fetch(url.pathname);
    } catch (e) {
      return new Response('Not Found', { status: 404 });
    }
  },
};
```

This makes kitchen's 500-on-miss → 404, and hardens the other 5 (functionally equivalent but gain the defensive 404 instead of a possible uncaught 500).

## 7. Deployment constraints

- Deploy **ONLY** via `shared/publishers/deploy.py:deploy_site(site_path, cf_project)`.
- For Worker blogs, `deploy_site_inner` runs `wrangler deploy --config wrangler.toml` (pops `CLOUDFLARE_API_TOKEN`, uses OAuth profile `hugh79757` bound to `cuap`).
- NEVER manual `wrangler deploy` / `wrangler pages deploy`. NO git push (deploy is wrangler upload only).

## 8. Verification approach

After deploy:
- GET a known-missing path on each of 6 blogs → expect **404** (not 500).
- GET a real published post on each → expect **200** (regression guard; Phase 27 already confirmed card links 200).
- If any blog returns 500 on missing → FAIL, diagnose (leftover divergent worker / deploy issue).
