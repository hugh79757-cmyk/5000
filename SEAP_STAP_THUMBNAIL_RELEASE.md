# SEAP_STAP_THUMBNAIL_RELEASE.md — SEAP/STAP 썸네일 표준 적용 계획 (READ-ONLY)

> **목적**: SEAP(Hugo+Blogger) + STAP(Hugo) 썸네일 표준 적용을 위한 canary·검증·롤백 계획
> **작성일**: 2026-08-19
> **상태**: 계획. 코드·CSS·템플릿·이미지·R2·DB·설정 변경·배포·push **수행하지 않음**

---

## 1. 적용 대상 (In-Scope)

### 1.1 SEAP (Senior Auto Publisher) — 2개 블로그

| blog_id | platform | domain | site_path | theme | status |
|---------|----------|--------|-----------|-------|--------|
| `senior-hugo` | hugo | senior.informationhot.kr | `/Users/twinssn/Projects/SEAP/senior-hugo` | Blowfish | active |
| `senior-blogger` | blogger | 2.techpawz.com | — | — | active |

### 1.2 STAP (Stock Auto Publisher) — 6개 블로그

| blog_id | platform | domain | site_path | theme | status |
|---------|----------|--------|-----------|-------|--------|
| `finance-hugo` | hugo | finance.techpawz.com | `/Users/twinssn/Projects/STAP/finance-hugo` | Blowfish | active |
| `stock-hugo` | hugo | stock.informationhot.kr | `/Users/twinssn/Projects/STAP/stock-hugo` | Blowfish | active |
| `dividend-hugo` | hugo | dividend.techpawz.com | `/Users/twinssn/Projects/STAP/dividend-hugo` | Blowfish | active |
| `etf-hugo` | hugo | etf.techpawz.com | `/Users/twinssn/Projects/STAP/etf-hugo` | Blowfish | active |
| `sector-hugo` | hugo | sector.techpawz.com | `/Users/twinssn/Projects/STAP/sector-hugo` | Blowfish | **paused** |
| `ipo-hugo` | hugo | ipo.techpawz.com | `/Users/twinssn/Projects/STAP/ipo-hugo` | Blowfish | active |

**총 8개 블로그** (Hugo 7 + Blogger 1)

### 1.3 제외 대상 (Out-of-Scope — 고정)

| 그룹 | 블로그 | 제외 사유 |
|------|--------|----------|
| **CAR** | compare-hugo, deal-hugo, ev-hugo, guide-hugo, hotissue-hugo, tco-hugo, rank-hugo, pick-hugo | 별도 파이프라인 |
| **TAP** | travel-hugo~travel4-hugo, tap-blogger | 별도 파이프라인 |
| **ETAP** | tour-hugo~nomad-hugo (27개) | 별도 파이프라인 |
| **CUAP** | appliance-hugo~bike-hugo (16개) | 별도 파이프라인 |
| **RAP** | rap-hugo~rap5-hugo | 별도 파이프라인 |
| **Blogger** | tvshow-blogger, ud-blogger | paused |

---

## 2. 현재 상태 진단

### 2.1 SEAP Hugo (`senior-hugo`)

| 항목 | 현재 상태 | 문제 |
|------|----------|------|
| 해상도 | 600×600 (1:1) | OG 1200×630 미충족 |
| 포맷 | WebP | 정상 |
| 용량 | ~48KB | 80KB 권장 내 |
| R2 경로 | `thumbnails/senior/{slug}.webp` | 코드에 존재, DB 0건 사용 |
| featureimage | `common/default-thumbnail.webp` | **전부 fallback** — 고유 썸네일 0건 |
| 원인 | Playwright chromium 미설치 → `generate_image_thumbnail()` 실패 → 빈 문자열 → fallback | **canary로 해결 확인** (Playwright v1228 설치됨) |

### 2.2 SEAP Blogger (`senior-blogger`)

| 항목 | 현재 상태 | 문제 |
|------|----------|------|
| 썸네일 수 | 92/93 (99%) | 1건 누락 (id=1945) |
| URL 형식 | `pub-*.r2.dev/senior-thumbnails/{date}-{hash}.webp` | 정상 |
| 본문 첫 이미지 | `<div style="text-align:center"><img src="..."></div>` | 정상 — Blogger가 첫 `<img>`를 대표 이미지로 인식 |
| og:image | **없음** — Blogger 템플릿에 미구현 | Blogger 플랫폼 한계 |
| 피드 썸네일 | **없음** — 피드 미노출 | Blogger 플랫폼 한계 |
| WebP 호환 | **정상** — senior-blogger가 WebP 사용 중 | 검증 완료 |

### 2.3 STAP Hugo (6개)

| 블로그 | featureimage 상태 | 문제 |
|--------|------------------|------|
| `finance-hugo` | `finance-thumbnails/{date}-{hash}.webp` | ✅ 정상 |
| `stock-hugo` | `common/default-thumbnail.webp` | ⚠️ **featureimage bug** — `thumbnail` 필드에 정상 URL이나 `featureimage`는 fallback |
| `dividend-hugo` | `dividend-thumbnails/{date}-{hash}.webp` | ✅ 정상 |
| `etf-hugo` | `etf-thumbnails/{date}-{hash}.webp` | ✅ 정상 |
| `sector-hugo` | `sector-thumbnails/{date}-{hash}.webp` | ✅ 정상 (paused) |
| `ipo-hugo` | `ipo-thumbnails/{date}-{hash}.webp` | ✅ 정상 |

**stock-hugo featureimage bug**: `thumbnail` 필드에 `stock-thumbnails/...` URL이 있으나, `_build_frontmatter_blowfish()`가 `thumbnail_url` 파라미터로 fallback 값을 받으면 featureimage가 `common/default-thumbnail.webp`로 설정됨.

### 2.4 Blowfish 테마 CSS (전 99개 Hugo 블로그 공통)

| 속성 | Blowfish 기본 | 4개 CUAP 블로그 override | 1200×630 마스터 호환 |
|------|-------------|------------------------|---------------------|
| `aspect-ratio` | `var(--thumbnail-aspect-ratio, 1.5)` (카드) | `1/1 !important` | ⚠️ 1.5:1 = 정상, 1:1 = 크롭 |
| `object-fit` | `cover` (hero) | `contain !important` | ✅ cover=크롭, contain=전체 표시 |
| `overflow` | `hidden` (카드) | — | ✅ 크롭 정상 |
| `loading` | lazy (카드), eager (hero) | — | ✅ 정상 |
| `decoding` | `async` (전체) | — | ✅ 정상 |
| `srcset` | Blowfish에서 미사용 | — | ⚠️ Hugo image processing에 의존 |

**핵심**: Blowfish는 `object-fit: cover`로 1200×630 이미지를 1:1 컨테이너에서도 크롭하여 표시. 4개 CUAP 블로그만 `contain`으로 override → 잘림 없음.

---

## 3. 플랫폼 어댑터 설계

### 3.1 Hugo 어댑터

```
Input: site_id, slug, title, category
Pipeline: generate 1200×630 WebP (80KB 목표) → upload R2 → immutable cache
Output: R2 URL → hugo_writer.py가 featureimage에 설정
Fallback: blog-unique default image
```

**변경 파일**:
| 파일 | 변경 내용 |
|------|----------|
| `shared/thumbnail_generator/generator.py` | 600×600 → 1200×630 해상도 강제 |
| `shared/thumbnail_generator/templates/image.html` | 폰트 fallback에 Malgun Gothic 추가 |
| `shared/thumbnail_generator/templates/default.html` | 동일 |
| `shared/publishers/hugo_writer.py:1142-1145` | fallback을 `site_id`별 고유 이미지로 분기 |
| `scripts/batch_thumbnails.py:49-92` | `senior` 등록 |

### 3.2 Blogger 어댑터

```
Input: site_id, slug, title, category, body_html
Pipeline: generate 1200×630 WebP → JPEG 변환 (호환) → upload R2 → body_html 앞에 <img> 삽입
Output: modified body_html (thumbnail 포함)
Fallback: blog-unique default image (body_html 앞에 <img> 삽입)
```

**변경 파일**:
| 파일 | 변경 내용 |
|------|----------|
| `shared/thumbnail_generator/blogger_adapter.py` | **신규** — Blogger용 어댑터 |
| `pipelines/senior/pipeline.py:400-406` | `_do_publish_blogger()`에서 어댑터 호출 |
| `shared/publisher.py:920-938` | Blogger 분기에서 thumbnail_url 처리 |

### 3.3 차이점 비교

| 속성 | Hugo | Blogger |
|------|------|---------|
| 썸네일 저장 | R2 (direct URL) | R2 URL을 본문 `<img>`에 삽입 |
| 포맷 | WebP | JPEG (더 안전) 또는 WebP (검증 완료) |
| 위치 | frontmatter `featureimage:` | 본문 첫 `<img>` |
| 캐시 | `Cache-Control: immutable` | Blogger CDN 자체 캐시 |
| OG 이미지 | Blowfish가 featureimage에서 추출 | Blogger가 본문 첫 `<img>`에서 자동 추출 |
| 피드 | Hugo sitemap/RSS | Blogger Atom 피드 |

---

## 4. Fallback 재설계

### 4.1 현재 문제

- 30+ 블로그가 동일 `common/default-thumbnail.webp` 사용
- stock-hugo는 `thumbnail` 필드에 정상 URL이나 `featureimage`는 fallback
- `write_post()` line 1142-1145: non-stock 블로그는 fallback 없이 빈 thumbnail_url 전달

### 4.2 블로그별 고유 fallback (7개 그룹)

| # | 그룹 ID | 라벨 | 블로그 | R2 경로 |
|---|---------|------|--------|---------|
| 1 | `rotcha-auto` | 핫이슈 · 비교분석 | compare, deal, ev, guide, hotissue, tco | `common/fallback-rotcha-auto.webp` |
| 2 | `infohot-car` | 랭킹 · 내차찾기 | rank, pick | `common/fallback-infohot-car.webp` |
| 3 | `infohot-general` | 시니어 · 복지 · 부동산 | senior, rap×5 | `common/fallback-infohot-general.webp` |
| 4 | `cuap-curation` | 추천 가이드 | appliance~bike (15개) | `common/fallback-cuap-curation.webp` |
| 5 | `stap-stock` | 주식 · 투자 분석 | stock, finance, dividend, etf, sector, ipo | `common/fallback-stap-stock.webp` |
| 6 | `tap-travel` | 여행 · 코스 추천 | travel×5 | `common/fallback-tap-travel.webp` |
| 7 | `etap-travel-en` | Travel Guide | ETAP 27개 | `common/fallback-etap-travel-en.webp` |

### 4.3 반복 경보 기준

| 기준 | 값 | 예외 |
|------|-----|------|
| 기본 fallback 사용 ≤1건/블로그/7일 | **1건** | paused 블로그, canary 1건 |
| 동일 해시 반복 ≤1건/최근 5건 | **1건** | default-thumbnail.webp (기존 이미지) |
| `common/default-thumbnail.webp` 사용 | **0건/신규 발행** | 기존 게시물은 변경 안 함 |

---

## 5. 모니터링 규칙

### 5.1 THUMBNAIL-01 (기존 — 개정)

| 항목 | 기존 | 개정 |
|------|------|------|
| 검사 대상 | 최근 10개 포스트 | **최근 5개 포스트** (정확도) |
| featureimage 존재 | ✅ | 유지 |
| R2 호스팅 | `pub-*.r2.dev` | 유지 |
| `.webp` 확장자 | ✅ | **`.webp` 또는 `.jpg`** (Blogger JPEG 허용) |
| **해상도** | — | **추가: 1200×630 (±10%) 또는 600×600 (senior/sector legacy)** |
| **파일 크기** | — | **추가: ≤150KB** |

### 5.2 THUMBNAIL-02 (신규 — 해시 반복)

| 항목 | 기준 |
|------|------|
| 검사 대상 | 최근 5개 포스트 |
| SHA256 해시 중복 | ≤1건 동일 해시 |
| 기본 fallback 사용 | ≤1건/블로그 |
| **대상**: SEAP Hugo, STAP Hugo | **제외**: SEAP Blogger (URL 해시 비교 불가) |

### 5.3 THUMBNAIL-03 (신규 — 라이브 검증)

| 항목 | 기준 | 대상 |
|------|------|------|
| HTTP 상태 | 200 OK | SEAP Hugo, STAP Hugo |
| Content-Type | `image/webp` 또는 `image/jpeg` | 전체 |
| 파일 크기 | ≤150KB | 전체 |
| 해상도 | 1200×630 (±10%) | SEAP Hugo, STAP Hugo |

### 5.4 THUMBNAIL-04 (신규 — Blogger 대응)

| 항목 | 기준 | 대상 |
|------|------|------|
| 본문 첫 `<img>` 존재 | 필수 | senior-blogger |
| `<img>` src HTTP | 200 OK | senior-blogger |
| WebP 또는 JPEG 포맷 | 필수 | senior-blogger |
| 빈 본문 `<img>` 없음 | 본문에 `<img>` 0개이면 FAIL | senior-blogger |

---

## 6. stock-hugo Featureimage Bug 수정 계획

### 6.1 근본원인

`pipelines/stock/pipeline.py`가 `_make_thumbnail()`로 정상 썸네일을 생성하고 `thumbnail` 필드에 저장. 그러나 `_build_frontmatter_blowfish()`가 `thumbnail_url` 파라미터로 **fallback 값**을 받아 featureimage를 `common/default-thumbnail.webp`로 설정.

### 6.2 수정 방향 (READ-ONLY)

1. `shared/publisher.py`의 `write_post()`에서 stock-hugo의 `thumbnail_url`이 falsy일 때 `thumbnail` 필드의 값을 featureimage로 사용
2. 또는 `pipelines/stock/pipeline.py`에서 `_make_thumbnail()` 결과를 `thumbnail_url` 파라미터로 전달

### 6.3 영향 범위

- stock-hugo의 **기존 게시물 featureimage는 변경하지 않음** (기존 URL 보존)
- **신규 발행분에만 적용**

---

## 7. Canary 계획

### 7.1 Canary 1건: SEAP Hugo (`senior-hugo`)

| 항목 | 내용 |
|------|------|
| **대상** | `senior-hugo` |
| **방법** | `python3 dispatcher.py senior-hugo` 1건 발행 |
| **검증** | ① featureimage가 `common/default-thumbnail.webp`가 아닌 고유 URL인지 ② R2 업로드 HTTP 200 ③ 해상도 1200×630 (±10%) ④ 파일 크기 ≤150KB ⑤ permalink HTTP 200 ⑥ Blowfish hero에 이미지 표시 |
| **성공 기준** | 위 6개 항목 전부 통과 |
| **롤백** | `stap.yaml`에서 senior-hugo pause + 기존 `common/default-thumbnail.webp` 유지 |
| **시점** | 코드 변경 후 첫 정규 스케줄 (07:34) |

### 7.2 Canary 1건: STAP Hugo (`finance-hugo`)

| 항목 | 내용 |
|------|------|
| **대상** | `finance-hugo` |
| **방법** | `python3 dispatcher.py finance-hugo` 1건 발행 |
| **검증** | ① featureimage가 `finance-thumbnails/...` 경로인지 ② R2 업로드 HTTP 200 ③ 해상도 1200×630 (±10%) ④ 파일 크기 ≤150KB ⑤ permalink HTTP 200 |
| **성공 기준** | 위 5개 항목 전부 통과 |
| **롤백** | `stap.yaml`에서 finance-hugo pause |
| **시점** | SEAP Hugo canary 성공 후 |

### 7.3 Canary 1건: SEAP Blogger (`senior-blogger`)

| 항목 | 내용 |
|------|------|
| **대상** | `senior-blogger` |
| **방법** | `BloggerClient`로 비공개 draft 1건 생성 (R2 WebP URL을 본문 첫 `<img>`로 삽입) |
| **검증** | ① Blogger draft URL에서 이미지 렌더링 ② og:image 메타 태그에 R2 URL 포함 ③ 이미지 Content-Type 확인 ④ 기존 게시물과 동일한 `<div><img>` 구조 |
| **성공 기준** | 위 4개 항목 전부 통과 |
| **롤백** | draft 삭제 |
| **시점** | STAP Hugo canary 성공 후 |
| **주의** | **게시하지 않음** — draft만 생성하여 검증 |

### 7.4 Canary 순서

```
1. 코드 변경 (어댑터 + fallback + 모니터링)
2. SEAP Hugo canary (1건) → 검증
3. STAP Hugo canary (1건) → 검증
4. SEAP Blogger canary (1건 draft) → 검증
5. 3건 전부 성공 시 정규 스케줄 재개
```

---

## 8. 검증 체크리스트

### 8.1 코드 변경 전 (Before)

| # | 검증 항목 | 방법 | 기대 |
|---|----------|------|------|
| B1 | 현재 featureimage 해시 스냅샷 | `for blog in senior-hugo finance-hugo stock-hugo; do grep -r "featureimage" ...` | 기존 URL 전부 기록 |
| B2 | 테스트 실행 | `pytest tests/test_sector_parse_response.py tests/test_monitor_patch.py -v` | 전부 통과 |
| B3 | generator.py 현재 해상도 확인 | `grep -n "600\|1200\|width\|height" shared/thumbnail_generator/generator.py` | 600×600 코드 확인 |

### 8.2 코드 변경 후 (After)

| # | 검증 항목 | 방법 | 기대 |
|---|----------|------|------|
| A1 | featureimage 변경 없음 | B1과 동일 비교 | 기존 URL 100% 동일 |
| A2 | 테스트 재실행 | B2와 동일 | 전부 통과 |
| A3 | generator.py 해상도 확인 | `grep -n "1200\|630" ...` | 1200×630 코드 확인 |
| A4 | fallback 이미지 R2 존재 | `curl -sI` 각 fallback URL | 전부 HTTP 200 |

---

## 9. 롤백 기준

| 기준 | 조건 | 조치 |
|------|------|------|
| **즉시 롤백** | canary 1건 featureimage가 fallback이거나 HTTP 404 | 코드 원복 + pause |
| **즉시 롤백** | 기존 게시물 featureimage 변경 감지 | 코드 원복 + DB 백업 복원 |
| **부분 롤백** | canary 성공 but 정규 스케줄에서 fallback 발생 | `_make_thumbnail()` 에러 로그 확인 후 재시도 |
| **유지** | canary 성공 + 정규 스케율 3건 성공 | 정규 스케줄 유지 |

---

## 10. 제외 대상 고정 목록

| 블로그 | 플랫폼 | 제외 사유 |
|--------|--------|----------|
| compare-hugo | hugo | CAR 파이프라인 |
| deal-hugo | hugo | CAR 파이프라인 |
| ev-hugo | hugo | CAR 파이프라인 |
| guide-hugo | hugo | CAR 파이프라인 |
| hotissue-hugo | hugo | CAR 파이프라인 |
| tco-hugo | hugo | CAR 파이프라인 |
| rank-hugo | hugo | CAR 파이프라인 |
| pick-hugo | hugo | CAR 파이프라인 |
| travel-hugo~travel4-hugo | hugo | TAP 파이프라인 |
| tap-blogger | blogger | TAP 파이프라인 |
| tour-hugo~nomad-hugo (27개) | hugo | ETAP 파이프라인 |
| appliance-hugo~bike-hugo (16개) | hugo | CUAP 파이프라인 |
| rap-hugo~rap5-hugo | hugo | RAP 파이프라인 |
| tvshow-blogger | blogger | paused |
| ud-blogger | blogger | paused |

---

## 11. 잔존 위험

1. **stock-hugo featureimage bug**: 코드 수정이 필요하나 기존 게시물 변경 없이 신규 발행분에만 적용하는 것이 안전한지 확인 필요
2. **Blogger og:image 한계**: Blogger 템플릿에 og:image 미구현 → 소셜 공유 시 썸네일 미표시. Blogger 템플릿 수정이 필요하나 이번 범위 밖
3. ** Blowfish 테마 통일**: 99개 블로그 전부 Blowfish. 4개 CUAP 블로그만 `aspect-ratio: 1/1` override → 1200×630 마스터가 `cover` 크롭으로 정상 동작하는지 추가 검증 필요
4. **R2 캐시 헤더**: 현재 Cache-Control 없음. `immutable` 추가 시 기존 객체에 Retrofit 필요 (R2 콘솔 또는 boto3 스크립트)
5. **senior-hugo featureimage 전부 fallback**: Playwright chromium 설치 후 canary에서 고유 썸네일 확인됨. 정규 스케줄에서도 지속 생성되는지 모니터링 필요
