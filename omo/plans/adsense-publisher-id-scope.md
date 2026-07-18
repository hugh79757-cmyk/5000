# AdSense Publisher ID — 작업범위 & 플랜

## 도메인별 Publisher ID 매핑 (확정)

| Publisher ID | 도메인 | 적용 대상 |
|---|---|---|
| `ca-pub-6677996696534146` | **informationhot.kr** (모든 서브도메인 포함) | CUAP, RAP, SEAP, CAP pick/rank, informationhot-hugo, STAP stock-hugo 등 |
| `ca-pub-8772455780561463` | **rotcha.kr** | 5000 메인 사이트, rotcha-blog |
| `ca-pub-8772455780561463` | **techpawz.com** (+ 하위 도메인) | techpawz-hugo, biz.techpawz-hugo, issue-techpawz-hugo, info.techpawz-hugo |
| `ca-pub-8772455780561463` | **farmsolutionint.com** | farmsolution 관련 사이트 |

---

## Phase 1 — ROLLBACK (informationhot.kr 계열 원복)

**CUAP 10개 사이트** — `params.toml` clientID 원복
- `ca-pub-8772455780561463` → `ca-pub-6677996696534146`
- 5개 추가: `extend-head.html` 하드코딩도 원복

**RAP 5개 사이트** — `adsense/*.html` (4개) + `extend-head.html` 원복

**SEAP senior-hugo** — `adsense/*.html` (3개) 원복  
  ⚠ `extend-head.html`에 추가한 AdSense 스크립트 태그는 유효, 단 pub ID만 원복

**CAP pick-hugo, rank-hugo** — `baseof.html` + `adsense/*` (5개) 원복

**informationhot-hugo** — `extend-head.html` + `adsense*` 파일들 원복

**STAP stock-hugo** — `extend-head.html` + `single.html` 원복

**기준:** `informationhot.kr` 루트 도메인은 `ca-pub-6677996696534146`에 바인딩되어 있으므로, **모든 `*.informationhot.kr` 사이트는 이 ID를 사용해야 함**

---

## Phase 2 — CHECK & APPLY (rotcha.kr / farmsolutionint.com)

- `5000` 메인 사이트 (rotcha.kr): AdSense 설정 확인, 없으면 `ca-pub-8772455780561463` 적용
- `rotcha-blog`: AdSense 설정 확인
- `farmsolutionint.com` 사이트: 존재 여부 확인 후 AdSense 설정

**기준:** `rotcha.kr`, `techpawz.com`, `farmsolutionint.com`은 `ca-pub-8772455780561463`에 바인딩되어 있음

---

## Phase 3 — VERIFICATION

- 전 사이트 소스(`layouts/` + `config/`)에서 pub ID 검증
- `informationhot.kr` 계열 → `ca-pub-6677996696534146`만 존재
- `rotcha.kr` / `techpawz.com` / `farmsolutionint.com` → `ca-pub-8772455780561463`만 존재
- 상호 침투(mismatch) 0건
