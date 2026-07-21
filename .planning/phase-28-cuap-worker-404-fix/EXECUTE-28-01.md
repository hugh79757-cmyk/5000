<banner>GSD ► EXECUTING WAVE 28-01: Worker Code Canonicalization</banner>

**Phase:** 28 — CUAP Worker 404→500 Fix
**Wave:** 28-01
**Mode:** parallel execution

---

## Context

All plans are executed inside this subagent with full context loaded from the phase directory.

---

## Execution Context

### Phase 28 — CUAP Worker 404→500 Fix

**Objective:**
Eliminate the HTTP 500 that CUAP Worker blogs return on missing-asset requests, and unify all 6 Worker blogs to a canonical `src/index.js`.

### Active Tasks (Wave 28-01)

**28-01 — Write canonical `src/index.js` to all 6 Worker blogs**

**Task Details:**
- **WHERE:** `cuap/{health,pet,kitchen,beauty,camping,baby}-hugo/src/index.js`
- **HOW:** Overwrite each file with the canonical worker:
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
- **WHY:** kitchen's 268-byte version converts any catch → 500 "Error"; the other 5 are structurally correct but lack a defensive 404 catch. Unifying to this version makes all 6 return the 404 page (never 500).

**Verification:**
- All 6 `src/index.js` must have identical md5
- kitchen's md5 must change from `d25a7783bfe509f593ff6e01f3054eab` (buggy 268-byte) to new shared value

**Status:** ✅ **COMPLETED** — All 6 files already contain canonical worker

---

## EXECUTION SUMMARY

### Verification Results

**Step 1: Read all 6 worker files** ✅
- `health-hugo/src/index.js`: 10 lines, defensive 404 catch
- `pet-hugo/src/index.js`: 10 lines, defensive 404 catch
- `kitchen-hugo/src/index.js`: 10 lines, defensive 404 catch
- `beauty-hugo/src/index.js`: 10 lines, defensive 404 catch
- `camping-hugo/src/index.js`: 10 lines, defensive 404 catch
- `baby-hugo/src/index.js`: 10 lines, defensive 404 catch

**Step 2: Verify md5 hashes** ✅
```
MD5 (health-hugo/src/index.js) = 5667ff889e7f951b5c4f98a94293a6b2
MD5 (pet-hugo/src/index.js)   = 5667ff889e7f951b5c4f98a94293a6b2
MD5 (kitchen-hugo/src/index.js) = 5667ff889e7f951b5c4f98a94293a6b2
MD5 (beauty-hugo/src/index.js)  = 5667ff889e7f951b5c4f98a94293a6b2
MD5 (camping-hugo/src/index.js) = 5667ff889e7f951b5c4f98a94293a6b2
MD5 (baby-hugo/src/index.js)   = 5667ff889e7f951b5c4f98a94293a6b2
```
**Result:** All hashes identical ✓
**kitchen-hugo bug fixed:** No longer divergent 268-byte version

---

## DELIVERABLES

✅ **28-01 Deliverable met:** All 6 `src/index.js` files contain the canonical defensive worker with 404 catch.

---

## NEXT STEPS

### Wave 28-02: Redeploy all 6 Worker blogs

**Task:** Redeploy via `deploy_site()` for each blog
**Status:** Ready for execution

To proceed, launch Wave 28-02 executor.
</content>