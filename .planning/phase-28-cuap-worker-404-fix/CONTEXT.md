# CONTEXT — Phase 28: CUAP Worker 404→500 Fix

**Last updated:** 2026-07-21
**Author:** Sisyphus (orchestrator) — facts verified directly via `md5` + file reads.

---

## 1. Objective

CUAP Worker 블로그 6개(health, pet, kitchen, beauty, camping, baby)에서
**존재하지 않는 경로(missing asset) 접근 시 HTTP 500을 반환하는 버그**를 수정하여
정상적인 **404 페이지(`not_found_handling = "404-page"`)** 가 반환되도록 한다.

근본 목표: 카드 링크(Phase 27에서 이미 200 검증 완료)와 무관하게,
훼손된 포스트/오타 URL 접근 시 사용자에게 500이 아닌 404가 노출되도록 함.

---

## 2. 현재 상태 (검증됨 — md5 + file read)

### Worker `src/index.js` 공유 여부
| Blog | src/index.js | md5 | 바이트 | 내용 |
|------|---------------|-----|--------|------|
| health-hugo | 존재 | `3fece1c5b4b2fd725e8166968e7627df` | 142 | 공유본 |
| pet-hugo | 존재 | `3fece1c5b4b2fd725e8166968e7627df` | 142 | 공유본 |
| beauty-hugo | 존재 | `3fece1c5b4b2fd725e8166968e7627df` | 142 | 공유본 |
| camping-hugo | 존재 | `3fece1c5b4b2fd725e8166968e7627df` | 142 | 공유본 |
| baby-hugo | 존재 | `3fece1c5b4b2fd725e8166968e7627df` | 142 | 공유본 |
| **kitchen-hugo** | 존재 | `d25a7783bfe509f593ff6e01f3054eab` | **268** | **다름(버그본)** |

→ **5개 블로그는 동일 142-byte 워커를 공유**, **kitchen-hugo만 268-byte 버그본으로 발산**.

### 공유본 (142-byte, 5개 블로그 — 정상 추정)
```js
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    return await env.ASSETS.fetch(url.pathname);
  },
};
```
- try/catch 없음. missing asset는 `ASSETS.fetch`가 `not_found_handling` 설정에 따라
  404 페이지 Response(상태 404)를 반환한다고 가정하면 정상.
- 단, `ASSETS.fetch`가 throw하는 런타임 상황에서는 uncaught → 플랫폼 기본 500 가능성 잔존.

### kitchen-hugo 버그본 (268-byte — 500 유발)
```js
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    try {
      const response = await env.ASSETS.fetch(url.pathname);
      return response;
    } catch (e) {
      return new Response('Error', { status: 500 });   // ← missing asset도 500으로 변환
    }
  }
};
```
- `catch`가 missing asset(또는 인코딩 예외)를 **무조건 500 "Error"** 로 변환.
- 관측: `https://kitchen.informationhot.kr/posts/<존재안함-slug>/` → HTTP **500**, 본문 `Error`.
- 실제 발행 포스트(정확한 slug)는 200 정상 (Phase 27 검증 완료).

---

## 3. wrangler.toml (6개 Worker 블로그 공통 구조)
```
name = "kitchen-hugo"            # blog별
main = "src/index.js"
compatibility_date = "2025-07-31"
[assets]
directory = "./public"
not_found_handling = "404-page"   # ← 404 페이지 설정 존재
html_handling = "auto-trailing-slash"
```
→ `ASSETS` binding이 404 처리를 담당. Worker 코드가 이를 가로채지 않아야 함.

---

## 4. 제약 (AGENTS.md / deploy.py 준수)

- **배포는 반드시 `shared/publishers/deploy.py:deploy_site()` 경유.**
  - Worker 블로그: `wrangler deploy --config wrangler.toml`
  - 내부에서 `CLOUDFLARE_API_TOKEN` env var를 **제거** 하고 OAuth profile(`hugh79757`, cuap bound) 사용.
  - Phase 27에서 kitchen-hugo 포함 9개 블로그 `deploy_site()` 성공 확인됨(EXIT=0).
- **절대 수동 `wrangler deploy` / `wrangler pages deploy` 금지** (AGENTS.md).
- **git push 금지** — 배포는 wrangler 직접 업로드.
- **AdSense**: CUAP = `ca-pub-6677996696534146` (informationhot.kr). 워커 코드 수정은 광고 ID 무관.

---

## 5. 수정 방향 (가설 — RESEARCH로 문서 확정 필요)

1. **kitchen-hugo**: 268-byte 버그본 → 142-byte 공유본(또는 동등 정상본)으로 교체.
   → missing asset 시 `catch`가 500을 강제하지 않고, `ASSETS.fetch`의 404 페이지가 그대로 전달됨.
2. **5개 공유본**: 이미 정상 추정이나, 6개 전체를 **동일 정상 캐노니컬 워커**로 통일 권장
   (kitchen 발산 방지 + 향후 유지보수 일관성). 공유본과 동일해지면 no-op.
3. **검증**: 배포 후 6개 블로그 각각에서 known-missing 경로 GET → **404**(아닌 500) 기대.
   실제 발행 포스트 → 200 유지.

### RESEARCH에서 확인할 핵심 (Cloudflare Workers Assets 문서)
- `env.ASSETS.fetch(pathname)` 이 **missing asset에서 throw하는가, 아니면 404 Response를 반환하는가?**
  - 404 Response 반환 → 공유본(142-byte, try/catch 없음)이 이미 정상. kitchen만 교체하면 됨.
  - throw하는 경우 → 공유본도 uncaught 500 가능. 그럼 캐노니컬 워커에
    `if (res.status === 404) return res; else if (!res.ok) return new Response(..., {status:404})` 형태 안전망 필요.
- `not_found_handling = "404-page"` 가 `ASSETS.fetch` 반환에 어떻게 반영되는가 (문서 확인).

---

## 6. 범위 (In/Out)

**IN:**
- `cuap/{health,pet,kitchen,beauty,camping,baby}-hugo/src/index.js` 수정 + 통일.
- `deploy_site()` 로 6개 Worker 블로그 재배포.
- 배포 후 6개 블로그 missing-asset 404 / 실포스트 200 라이브 검증.

**OUT:**
- Pages 블로그(appliance, interior 등 9개) — 이들은 Worker 아님, Phase 27에서 이미 처리.
- 카드 링크 404(Phase 27) — 이미 완료/검증됨.
- AdSense 코드, Hugo 컨텐츠, 테마 변경.
