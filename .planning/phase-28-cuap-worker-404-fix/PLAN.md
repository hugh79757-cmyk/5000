# PLAN.md — Phase 28: CUAP Worker 404→500 Fix

**Mode:** standard (horizontal)
**Verified against:** `CONTEXT.md` (md5 + file reads) and `RESEARCH.md` (Cloudflare Workers SDK docs).
**Next Up after plan:** `/gsd-execute-phase 28` (or explicit "go").

---

## Goal

Eliminate the HTTP 500 that CUAP Worker blogs return on missing-asset requests
(typo'd/old post slugs). Missing assets must serve the configured **404 page**
(`not_found_handling = "404-page"`), status 404. Unify all 6 Worker blogs'
`src/index.js` to one canonical version.

Success = 6/6 blogs return **404** (not 500) on a missing path, and **200** on
real published posts (regression guard).

---

## Scope

**IN**
- `cuap/{health,pet,kitchen,beauty,camping,baby}-hugo/src/index.js` → rewrite all 6 to canonical version.
- Redeploy all 6 Worker blogs via `deploy_site()`.
- Post-deploy live verification (missing→404, real→200).

**OUT**
- Pages blogs (appliance, interior, etc. — handled in Phase 27).
- Card-link 404s (Phase 27 done/verified).
- AdSense code, Hugo content/theme.

---

## Context references
- `CONTEXT.md` — verified sharing facts (5 share 142-byte; kitchen divergent 268-byte buggy).
- `RESEARCH.md` — Cloudflare doc finding (`ASSETS.fetch` returns 404 Response, modern model; kitchen's `catch→500` is the bug).

---

## Tasks

### 28-01 — Write canonical `src/index.js` to all 6 Worker blogs
- **WHERE:** `cuap/{health,pet,kitchen,beauty,camping,baby}-hugo/src/index.js`
- **HOW:** overwrite each file with the canonical worker:
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
- **WHY:** kitchen's 268-byte version converts any catch → 500 "Error"; the other
  5 are structurally correct but lack a defensive 404 catch. Unifying to this
  version makes all 6 return the 404 page (never 500).
- **EXPECTED RESULT:** `md5` of all 6 `src/index.js` identical; kitchen's md5 changes
  from `d25a7783bfe509f593ff6e01f3054eab` to the new shared value.

### 28-02 — Redeploy all 6 Worker blogs
- **WHERE:** each `cuap/{blog}-hugo`
- **HOW:** for each blog call
  `python3 -c "import sys; sys.path.insert(0,'/Users/twinssn/Projects/5000'); from shared.publishers.deploy import deploy_site; deploy_site('/Users/twinssn/Projects/cuap/{blog}-hugo','{blog}-hugo')"`
- **WHY:** `deploy_site()` runs `wrangler deploy --config wrangler.toml` for Worker
  blogs, after popping `CLOUDFLARE_API_TOKEN` and using OAuth profile `hugh79757`
  (bound to cuap). Confirmed working in Phase 27 (kitchen deployed OK).
- **EXPECTED RESULT:** `deploy_site()` returns `True` for all 6; `logs/deploy.log`
  shows no `Hugo build failed` / `Wrangler deploy failed`. Sequential (lock at
  `/tmp/wrangler_deploy.lock`).

### 28-03 — Live verification (missing→404, real→200)
- **WHERE:** live `https://{sub}.informationhot.kr/`
- **HOW:**
  - Missing: `curl -s -L -o /dev/null -w "%{http_code}" "https://{sub}.informationhot.kr/posts/this-post-does-not-exist-00000000/"` → expect **404** for all 6 subs
    (health/pet/kitchen/beauty/camping/baby).
  - Real: pick one real published slug per blog (from `content/posts/`), curl → expect **200**.
- **WHY:** proves the 500 is gone and real posts still serve (regression guard).
- **EXPECTED RESULT:** 6/6 missing → 404; 6/6 real → 200. Any 500 → FAIL.

---

## Verification loop (goal-backward)

| Criterion | Source | Pass when |
|-----------|--------|-----------|
| All 6 `src/index.js` identical md5 | 28-01 | `md5` matches across health/pet/kitchen/beauty/camping/baby |
| kitchen md5 changed from buggy value | 28-01 | old `d25a...eab` no longer present |
| All 6 deploy OK | 28-02 | `deploy_site()` `True`, no deploy.log errors |
| 6/6 missing → 404 | 28-03 | every subs missing-path curl = 404 |
| 6/6 real → 200 | 28-03 | every subs real-post curl = 200 |

If any criterion fails: diff the worker file, re-check `logs/deploy.log`, re-apply.

---

## Residual risks
- **R1 (low):** if `ASSETS.fetch` throws on miss in this runtime, the `catch` returns 404 (covered).
- **R2 (low):** OAuth profile `hugh79757` must stay bound to cuap — confirmed in Phase 27.
- **R3 (none):** no content/AdSense change; cards already 200 (Phase 27).

---

## Deliverables
- 6 updated `src/index.js` (canonical, unified).
- 6 redeployed Worker blogs.
- Verification report: 6/6 missing→404, 6/6 real→200.
