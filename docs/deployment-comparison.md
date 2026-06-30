# CUAP 블로그 배포 방식 비교: Workers + Assets vs Cloudflare Pages

> 최종 업데이트: 2026-05-30

## 개요

CUAP 디렉토리(`/Users/twinssn/Projects/CUAP/`)의 Hugo 블로그들은 두 가지 방식으로 Cloudflare에 배포된다.

| 배포 방식 | 대상 블로그 | 비고 |
|-----------|-----------|------|
| **Cloudflare Pages** (기존) | `appliance-hugo`, `fitness-hugo`, `interior-hugo`, `laptop-hugo` | wrangler.toml 없음 |
| **Workers + Assets** (신규) | `health-hugo`, `pet-hugo`, `kitchen-hugo`, `beauty-hugo`, `camping-hugo`, `baby-hugo` | wrangler.toml 있음 (`[assets]`) |

---

## 1. 아키텍처 비교

### Cloudflare Pages (기존 방식)

```mermaid
flowchart LR
    A[Hugo 빌드] --> B[public/]
    B --> C[wrangler pages deploy public --project-name XXX]
    C --> D[Cloudflare Pages Project]
    D --> E[*.pages.dev + custom domain]
```

- **Cloudflare 리소스**: Pages Project (별도 프로젝트 단위)
- **라우팅**: Pages가 자동으로 `*.pages.dev` 및 커스텀 도메인 연결
- **설정 파일**: `wrangler.toml` 불필요 (프로젝트명만 CLI 인자로 전달)

### Workers + Assets (신규 방식)

```mermaid
flowchart LR
    A[Hugo 빌드] --> B[public/]
    B --> C[wrangler deploy --config wrangler.toml]
    C --> D[Workers Service + Assets]
    D --> E[*.workers.dev + routes 설정 필요]
```

- **Cloudflare 리소스**: Workers Service (정적 자산은 Assets으로 포함)
- **라우팅**: `wrangler.toml`의 `routes` 블록으로 수동 설정 필요
- **설정 파일**: `wrangler.toml` 필수 (`[assets]` 섹션 포함)

---

## 2. 설정 파일 비교

### 기존 (Pages) — wrangler.toml 없음

CLI 인자로 모든 설정 전달:

```bash
wrangler pages deploy public \
  --project-name interior-hugo \
  --commit-dirty=true \
  --commit-message=publish
```

### 신규 (Workers + Assets) — wrangler.toml 사용

```toml
name = "interior-hugo"          # Workers Service 이름
compatibility_date = "2025-07-31"

routes = [
  { pattern = "interior.informationhot.kr/*",
    zone_name = "informationhot.kr" }
]

[assets]
directory = "./public"
not_found_handling = "404-page"
html_handling = "auto-trailing-slash"
```

| 항목 | Pages | Workers + Assets |
|------|-------|-----------------|
| 설정 파일 | 불필요 | `wrangler.toml` 필수 |
| 서비스명 | CLI `--project-name` | `name` 필드 |
| 자산 경로 | `public` (고정) | `[assets].directory` |
| 라우트 | 자동 (Pages DNS) | `routes` 블록 수동 |
| Worker 스크립트 | 불필요 | 선택 (`main` 필드, 없으면 순수 정적 Assets만) |

---

## 3. 배포 명령어 비교

### Pages

```bash
wrangler pages deploy public \
  --project-name <blog-id> \
  --commit-dirty=true \
  --commit-message=publish
```

- `public` 디렉토리 통째로 업로드
- Pages 프로젝트에 자동 매핑
- 단일 명령어로 간단

### Workers + Assets

```bash
wrangler deploy --config <path>/wrangler.toml
```

- `wrangler.toml` 경로 지정
- Assets 업로드 + Worker 배포 동시 진행
- 라우트가 있으면 자동 등록 시도

---

## 4. Cloudflare API 토큰 권한 비교

| 필요 권한 | Pages | Workers + Assets |
|-----------|-------|-----------------|
| Cloudflare Pages:Edit | ✅ 필수 | ❌ 불필요 |
| Workers Scripts:Edit | ❌ 불필요 | ✅ 필수 |
| Workers Routes:Edit (Zone) | ❌ 불필요 | ✅ 필수 (라우트 있을 시) |

Pages 방식은 Pages 권한만 있으면 되지만, Workers + Assets 방식은 **3개 권한**이 모두 필요하다.

---

## 5. 제약사항 비교

| 항목 | Pages | Workers + Assets |
|------|-------|-----------------|
| **프로젝트 생성 한도** | ⚠️ 계정당 제한 있음 (100개, 현재 한도 도달) | ✅ Workers 서비스는 Pages와 별도 한도 |
| **정적 자산** | ✅ HTML/이미지/CSS 업로드 | ✅ 동일 (Assets 기능) |
| **동적 기능** | ❌ 순수 정적 사이트 전용 | ✅ Worker 스크립트로 동적 처리 가능 |
| **커스텀 도메인** | Pages 대시보드에서 간편 설정 | `routes` 설정 또는 DNS CNAME 필요 |
| **배포 속도** | 유사 | 유사 |
| **무료 티어** | 제한적 | Workers 무료 티어 10만 req/일 |

---

## 6. 디스패처(dispatcher.py) 분기 로직

현재 `dispatcher.py`는 `WORKERS_BLOGS` 집합으로 두 방식을 분기한다:

```python
WORKERS_BLOGS = {
    "health-hugo",
    "pet-hugo",
    "kitchen-hugo",
    # ← beauty, camping, baby는 아직 미등록
}

if blog_id in WORKERS_BLOGS:
    wrangler deploy --config <wrangler.toml>
else:
    wrangler pages deploy public --project-name <blog-id>
```

> **⚠️ 주의:** `beauty-hugo`, `camping-hugo`, `baby-hugo`는 wrangler.toml이 존재하지만 `WORKERS_BLOGS`에 등록되지 않아, 현재 `wrangler pages deploy`로 배포된다. 이들도 Workers + Assets으로 전환하려면 `WORKERS_BLOGS`에 추가해야 한다.

---

## 7. wrangler.toml 파일 현황

| 블로그 | wrangler.toml | routes | main(worker) | WORKERS_BLOGS 등록 |
|--------|---------------|--------|-------------|-------------------|
| appliance-hugo | ❌ 없음 | — | — | ❌ |
| baby-hugo | ✅ | ❌ 없음 | ❌ | ❌ |
| beauty-hugo | ✅ | ✅ | ❌ | ❌ |
| camping-hugo | ✅ | ✅ | ❌ | ❌ |
| fitness-hugo | ❌ 없음 | — | — | ❌ |
| health-hugo | ✅ | ✅ | ❌ | ✅ |
| interior-hugo | ❌ 없음 | — | — | ❌ |
| kitchen-hugo | ✅ | ✅ | ✅ (src/index.js) | ✅ |
| laptop-hugo | ❌ 없음 | — | — | ❌ |
| pet-hugo | ✅ | ✅ | ❌ | ✅ |

> `main` 필드가 없는 경우 (`baby-hugo` 등) Worker 스크립트 없이 순수 정적 Assets만 배포된다. `kitchen-hugo`만 Worker 스크립트(`src/index.js`)가 포함되어 있다.

---

## 8. 배포 플로우 요약

### 기존 Pages 방식 (appliance, fitness, interior, laptop)

```
1. Hugo 빌드 (hugo --gc --minify)
2. wrangler pages deploy public --project-name <id>
3. Pages 프로젝트에 자동 업로드 + 도메인 연결 (기존 설정 유지)
```

### 신규 Workers + Assets 방식 (health, pet, kitchen, beauty, camping, baby)

```
1. Hugo 빌드 (hugo --gc --minify)
2. wrangler deploy --config wrangler.toml
3. Assets 업로드 + Worker 배포
4. routes 블록이 있으면 라우트 자동 등록 시도
   (단, Workers Routes:Edit 권한 필요)
```

---

## 9. 마이그레이션 체크리스트 (Pages → Workers + Assets 전환 시)

- [ ] 프로젝트 루트에 `wrangler.toml` 생성 (`[assets]` 섹션 포함)
- [ ] Cloudflare API 토큰에 `Workers Scripts:Edit` 권한 추가
- [ ] Cloudflare API 토큰에 `Workers Routes:Edit` (Zone) 권한 추가
- [ ] `dispatcher.py`의 `WORKERS_BLOGS` 집합에 blog_id 추가
- [ ] 배포 테스트 (`wrangler deploy --config <path>`)
- [ ] 커스텀 도메인 라우트 확인 (workers.dev 자동 도메인 or routes 설정)
- [ ] 기존 Pages 프로젝트는 삭제 또는 유지 (선택사항)
