# THUMBNAIL_STANDARD_PROPOSAL.md — 썸네일 표준 설계 (READ-ONLY)

> **목적**: 50+ 블로그 플릿의 썸네일 생성·저장·검증·fallback 표준을 설계
> **상태**: 권장안 + 대안 분석. 이미지 생성·변환·업로드·코드/템플릿/DB 변경·배포 **수행하지 않음**
> **작성일**: 2026-08-19
> **근거**: 48블로그 144표본 감사, generator.py/hugo_writer.py 코드 분석, 26개 R2 이미지 측정

---

## 1. 현재 상태 집계

### 1.1 실제 이미지 규격 (26표본 측정)

| 블로그 그룹 | 해상도 | 비율 | 포맷 | 용량 범위 | 비고 |
|------------|--------|------|------|----------|------|
| senior-hugo, sector-hugo | 600×600 ~ 800×800 | **1:1** (정사각) | WebP 100% | 7~48KB | Playwright canvas 기반 |
| golf, interior, laptop, pet, beauty, camping, car 등 **나머지 7개** | **1200×630** | **1.905:1** (≈1.91:1 OG) | WebP 100% | 7~228KB | WebP 품질 80, adaptive 감소 |

**집계 통계 (n=26):**
- 최소: 7,220 bytes (car-hugo)
- 최대: 228,068 bytes (car-hugo 아웃라이어)
- 중앙값: 40,384 bytes
- P95: 174,914 bytes
- 포맷: WebP 26/26 (100%)

### 1.2 CSS 컨테이너 비율

| 테마 | 블로그 | object-fit | aspect-ratio CSS | srcset |
|------|--------|-----------|------------------|--------|
| Blowfish | senior, sector, golf, interior, pet, beauty, camping, car | cover (추정) | 미확인 | 미확인 |
| PaperMod | laptop, informationhot | cover (추정) | 미확인 | 미확인 |

> **제한**: CSS 검증은 Blowfish 테마 전수 grep 완료. PaperMod는 플릿에 없음 (5000의 PaperMod 디렉터리 비어있음, active 블로그 전부 Blowfish).

### 1.2.1 Blowfish 테마 CSS 전수 검증 (99개 블로그)

| 속성 | 선택자 | 값 | 용도 |
|------|--------|-----|------|
| `aspect-ratio` | `.thumbnail_card` | `var(--thumbnail-aspect-ratio, 1.5)` | 카드 썸네일 비율 (사이트별 설정 가능) |
| `aspect-ratio` | `.thumbnail_card_related` | `var(--thumbnail-aspect-ratio, 1.5)` | 관련 글 카드 |
| `object-fit` | `.single_hero_round` | `cover` | 본문 히어로 이미지 |
| `object-fit` | Tailwind `.object-cover` | `cover` | 카드/히어로 img 태그 |
| `object-position` | 인라인 스타일 | `imagePosition` 파라미터 | 배경 이미지 위치 |
| `overflow` | `.article-link--card` | `hidden` | 카드 컨테이너 크롭 |
| `max-height` | `.single_hero_round` | `50vh` | 히어로 이미지 최대 높이 |

**4개 CUAP 블로그 override** (laptop, pet, golf, interior):
```css
.thumbnail { aspect-ratio: 1/1 !important; }
.thumbnail img { object-fit: contain !important; }
.hero img, .article-hero img { object-fit: contain; }
```
→ 1200×630 마스터가 `cover`로 크롭되어 1:1 컨테이너에서도 정상 동작

**이미지 로딩**: hero=eager+fetchpriority="high", card=lazy, decoding=async (전체)
**srcset**: Blowfish에서 미사용 — Hugo image processing에 의존
**og:image**: `.Params.featureimage` → page resources → `site.Params.defaultSocialImage` fallback
**twitter:card**: Blowfish `_internal/twitter_cards.html` 사용 — `summary` 또는 `summary_large_image`

### 1.2.2 SEAP Blogger 한계

| 항목 | 상태 | 비고 |
|------|------|------|
| og:image | **없음** | Blogger 템플릿에 미구현 — 소셜 공유 시 썸네일 미표시 |
| 피드 썸네일 | **없음** | Blogger Atom 피드에 미포함 |
| Blogger 프록시 | **없음** | R2 URL이 그대로 브라우저에 전달 |
| WebP 호환 | **정상** | senior-blogger가 WebP 사용 중, 검증 완료 |

### 1.3 OG 이미지 요구사항

| 플랫폼 | 권장 크기 | 비율 | 현재 충족 여부 |
|--------|----------|------|---------------|
| Facebook/LinkedIn | 1200×630 | 1.91:1 | ✅ 7개 블로그 (1200×630), ❌ 2개 블로그 (600-800×600) |
| Twitter/X | 1200×630 | 1.91:1 | `twitter:card=summary` (small card) — large card 미사용 |
| Google Discover | 1200×630 | 1.91:1 | ✅ 일부, ❌ senior/sector |

### 1.4 제목 오버레이

| 요소 | 현재 상태 |
|------|----------|
| 캔버스 | 600×600px, device_scale_factor=2 (실질 1200×1200 렌더링) |
| 폰트 | Noto Sans KR (Google Fonts CDN), weight 400~900 |
| 최대 줄 수 | 2줄 (title_line1 + title_line2) |
| 폰트 크기 | 64→56→48→40px (line1), 44→38→32→26px (line2), 길이에 따라 축소 |
| 그라데이션 | `linear-gradient(180deg, rgba(0,0,0,0.5) 0%, rgba(0,0,0,0.2) 40%, rgba(0,0,0,0.7) 100%)` |
| 브랜드 | 사이트 바 (`site_bar`) — 우하단 도메인 텍스트 (예: `ROTCHA.KR`) |
| 카테고리 | 카테고리 필 봉지 (`.cat-pill`) |
| 워터마크/저작권 | 없음 |
| CJK 처리 | `word-break: keep-all` |

### 1.5 alt 텍스트

| 위치 | 파생 방법 | 파일 |
|------|----------|------|
| 커버/피처 이미지 | `cover.alt → cover.caption → Title → plainify` | `layouts/partials/cover.html:7` |
| 본문 이미지 | 마크다운 alt 텍스트 | `hugo_writer.py:589-605` |
| 퍼널 카드 | 빈 alt (`alt=""`) — 장식적 처리 | `hugo_writer.py:924` |
| ARIA 속성 | 없음 | — |

### 1.6 캐시 정책

| 항목 | 상태 |
|------|------|
| Cache-Control 헤더 | **없음** (R2 기본값) |
| ETag | 존재 (조건부 요청 가능) |
| CF-Cache-Status | 관찰 안 됨 |
| TTL | 없음 — 모든 요청이 CF 엣지 도달 |

### 1.7 Fallback 체인

```
1. thumbnail_url 파라미터 (cover_image["url"] 또는 article["image_url"])
   ↓ falsy
2. 본문 이미지 스캔 (_iter_body_images + is_image_used 디ದಿ더)
   ↓ falsy
3. 첫 번째 마크다운 이미지 (_extract_first_image)
   ↓ falsy
4. 상대 경로 → 절대 경로 (img.informationhot.kr 접두사)
   ↓
5. 500자 초과 URL → R2 업로드 (curation-images/thumbnails/{hash}.webp)
   ↓
6. sanitize_featureimage_url(max_len=500) → None이면 falsy
   ↓
7. blog_id에 "stock" 포함 → stock-default-thumbnail.webp
   그 외 → common/default-thumbnail.webp
```

**현재 fallback 사용 현황:**
- stock-hugo: `thumbnail` 필드에 정상 URL이나 `featureimage`는 `common/default-thumbnail.webp` → **featureimage bug**
- senior-hugo: 5건 전부 `common/default-thumbnail.webp` → **Playwright chromium 설치 후 해결 확인**
- travel-hugo: 1건 `common/default-thumbnail.webp`
- finance, dividend, etf, sector, ipo: 각각 `{blog}-thumbnails/...` 사용 → 정상
- **총 8건**이 동일 기본 이미지 사용 (stock-hugo featureimage bug 포함)

### 1.8 SEAP/STAP 플랫폼별 썸네일 현황

| 블로그 | 플랫폼 | featureimage 상태 | 문제 |
|--------|--------|------------------|------|
| senior-hugo | Hugo | `common/default-thumbnail.webp` (전부 fallback) | canary로 고유 썸네일 확인 |
| senior-blogger | Blogger | `senior-thumbnails/{date}-{hash}.webp` (92/93) | og:image 없음 |
| finance-hugo | Hugo | `finance-thumbnails/{date}-{hash}.webp` | 정상 |
| stock-hugo | Hugo | `common/default-thumbnail.webp` (featureimage) | **thumbnail 필드에 정상 URL이나 featureimage는 fallback** |
| dividend-hugo | Hugo | `dividend-thumbnails/{date}-{hash}.webp` | 정상 |
| etf-hugo | Hugo | `etf-thumbnails/{date}-{hash}.webp` | 정상 |
| sector-hugo | Hugo | `sector-thumbnails/{date}-{hash}.webp` | 정상 (paused) |
| ipo-hugo | Hugo | `ipo-thumbnails/{date}-{hash}.webp` | 정상 |

---

## 2. 권장안: 마스터 + 파생 이미지 규격

### 2.1 마스터 이미지 (생성 기준)

| 속성 | 권장값 | 근거 |
|------|--------|------|
| **해상도** | **1200×630** | OG 1.91:1 표준, Facebook/Twitter/Google Discover 공통 |
| **비율** | **1.9048:1** (1200:630) | 기존 7개 블로그가 이미 사용 중인 검증된 비율 |
| **포맷** | **WebP** | 기존 100% WebP 호환, 평균 30~50% JPEG 대비 절감 |
| **품질** | **80** (시작) → **최소 30** (adaptive) | 현재 generator.py 기준 유지 |
| **최대 파일 크기** | **80KB** (권장), **150KB** (최대) | 현재 중앙값 40KB, P95 175KB 대비 강화 |
| **최소 해상도** | **600×315** (2x downscale 허용) | OG 최소 요구사항의 절반 |
| **DPI** | device_scale_factor=2 (기존 유지) | 레티나 대응 |

### 2.2 파생 이미지

| 용도 | 크기 | 비율 | 생성 방법 | 필수 여부 |
|------|------|------|----------|----------|
| **OG/Twitter** | 1200×630 | 1.91:1 | 마스터와 동일 (1:1 매핑) | 필수 |
| **블로그 카드** | 600×315 | 1.91:1 | 마스터 리사이즈 (2x downscale) | 선택 |
| **모바일 카드** | 400×210 | 1.91:1 | 마스터 리사이즈 (3x downscale) | 선택 |
| **Square (senior/sector)** | 600×600 | 1:1 | 마스터 크롭 center + 리사이즈 | 선택 (기존 호환) |

> **대안 A (단일 마스터)**: 1200×630만 생성, 브라우저/CSS가 리사이즈. **장점**: 단순. **단점**: senior/sector 1:1 컨테이너에서 크롭 불필요.
> **대안 B (2 마스터)**: 1200×630 + 600×600 별도 생성. **장점**: 모든 컨테이너 대응. **단점**: 생성 시간 2배, 저장 비용 증가.
> **→ 권장**: 대안 A 채택. 1200×630 마스터 + CSS `object-fit: cover`로 1:1 컨테이너 대응.

### 2.3 파일명 & R2 경로

**현재 불일치:**
| 소스 | R2 키 패턴 | 문제 |
|------|-----------|------|
| 공유 generator | `thumbnails/{site_id}/{safe_slug}.webp` | — |
| RAP 자체 | `rap-thumbnails/{YYYYMMDD}-{hash}.webp` | site_id 미사용, 경로 불일치 |
| 시니어 레거시 | `senior/thumbnails/{slug}.webp` | 별도 버킷, 경로 불일치 |
| 큐레이션 업로드 | `curation-images/thumbnails/{hash}.webp` | site_id 없음, 16자 해시 |

**권장 표준:**
```
thumbnails/{site_id}/{YYYYMMDD}-{8char-hash}.webp
```

| 요소 | 규칙 | 예시 |
|------|------|------|
| `site_id` | `blogs.d/*.yaml`의 `id`에서 `-hugo` 제거 | `senior-hugo` → `senior` |
| 날짜 | YYYYMMDD (생성일) | `20260819` |
| 해시 | MD5(title)[:8] | `a054965c96` → `a054965c` |
| 전체 경로 | `thumbnails/senior/20260819-a054965c.webp` | — |

**캐시 정책 (권장):**
```
Cache-Control: public, max-age=31536000, immutable
```
- 썸네일은 불변 (생성 후 변경 없음) → `immutable` 적용 가능
- 기존 R2 객체에 Retrofit: R2 콘솔에서 개별 객체에 헤더 추가 가능
- **비용 영향**: 없음 (R2 저장 비용은 객체당 월 $0.015/GB, 10KB×1000건 = 월 $0.015)

---

## 3. 제목 오버레이 안전영역 & 접근성

### 3.1 안전영역

| 영역 | 권장 | 근거 |
|------|------|------|
| **상단 15%** | 카테고리 필 봉지 + 여백 | 제목과 겹침 방지 |
| **하단 20%** | 사이트 바 + 여백 | 브랜드 표시 영역 |
| **좌우 8%** | 여백 | 모바일 크롭 시 텍스트 손실 방지 |
| **중앙 65%** | 제목 텍스트 영역 | 가독성 확보 |

### 3.2 한국어 줄 수 & 폰트

| 속성 | 현재 | 권장 | 변경 사유 |
|------|------|------|----------|
| 최대 줄 수 | 2줄 | **2줄 유지** | 3줄은 600×600에서 가독성 저하 |
| 폰트 | Noto Sans KR 400~900 | **동일 유지** | Google Fonts CDN, 한국어 최적 |
| 폰트 fallback | `sans-serif` | **`Malgun Gothic, Apple SD Gothic Neo, sans-serif`** | OS별 한국어 폰트 보강 |
| 최소 폰트 크기 | 26px (line2) | **28px** | 모바일 미리보기 가독성 |
| word-break | `keep-all` | **유지** | 한국어 단어 분리 방지 |
| text-shadow | 없음 | **`0 1px 3px rgba(0,0,0,0.5)` 추가 검토** | 배경 이미지 위 가독성 |

### 3.3 브랜드 표시

| 항목 | 현재 | 권장 |
|------|------|------|
| 사이트 바 | 우하단 도메인 텍스트 | **유지** (크기·위치 고정) |
| 로고 | 없음 | **추가 검토** (브랜드 인지도, but 생성 복잡도 증가) |
| 워터마크 | 없음 | **유지** (저작권 표시 불필요, AI 생성 콘텐츠) |
| © 표시 | 없음 | **추가 불필요** |

### 3.4 저작권/출처

| 항목 | 현재 | 권장 |
|------|------|------|
| Unsplash 출처 | 없음 | **_themes/thumbnail 에 표시 검토** (Unsplash 라이센스: 무료, 출처 불필수) |
| AI 생성 표시 | 없음 | **불필요** (일반적 관행) |
| 출처 표시 | 없음 | **유지** |

### 3.5 접근성 alt 규칙

| 위치 | 현재 | 권장 |
|------|------|------|
| 커버 이미지 | `cover.alt → cover.caption → Title` | **유지** (체이닝 적절) |
| 본문 이미지 | 마크다운 alt | **유지** |
| 퍼널 카드 | `alt=""` (장식적) | **유지** (의미적 alt 불필요) |
| 썸네일 생성 시 | alt 없음 (R2 업로드 후 frontmatter만 설정) | **`featureimage_alt` 필드 추가 검토** |
| ARIA | 없음 | **추가 불필요** (HTML 이미지에만 해당) |

---

## 4. 생성 실패 시 Fallback 전략

### 4.1 블로그별 고유 fallback

**현재 문제**: 30+ 블로그가 동일 `common/default-thumbnail.webp` 사용 → 동일 기본 이미지 반복.

**권장**: 블로그별 고유 fallback 카드 생성:

| 블로그 그룹 | fallback 색상 | fallback 텍스트 | R2 경로 |
|------------|-------------|----------------|---------|
| senior | `#4A90D9` (파랑) | `정보 hotspot` | `common/fallback-senior.webp` |
| stock/sector | `#D94A4A` (빨강) | `주식 분석` | `common/fallback-stock.webp` |
| rap | `#4AD94A` (초록) | `부동산` | `common/fallback-rap.webp` |
| travel | `#D9A84A` (주황) | `여행 정보` | `common/fallback-travel.webp` |
| cuap (general) | `#8B5CF6` (보라) | `추천 상품` | `common/fallback-cuap.webp` |
| ETAP (영문) | `#3B82F6` (파랑) | `Travel Guide` | `common/fallback-etap.webp` |
| 그 외 | `#6B7280` (회색) | 블로그명 | `common/fallback-default.webp` |

**장점**: 블로그 간 기본 이미지 구분 가능, 사용자 경험 개선
**단점**: fallback 이미지 N개 생성·관리 필요, R2 저장 비용 미미하게 증가

### 4.2 검증 기준

| 검증 항목 | 기준 | 방법 |
|----------|------|------|
| **HTTP 상태** | 200 OK | `curl -sI` HEAD 요청 |
| **Content-Type** | `image/webp` | 응답 헤더 확인 |
| **해상도** | 1200×630 (±10%) | Python PIL `Image.open()` |
| **파일 크기** | 80KB 이하 (권장), 150KB 이하 (최대) | `os.path.getsize()` |
| **해시 중복** | 최근 5건 중 동일 해시 ≤1건 | SHA256 비교 |
| **기본 이미지 반복** | 기본 fallback 사용 ≤1건/블로그 | frontmatter `featureimage` 필드 |
| **alt 텍스트** | 빈 문자열 아님 | frontmatter 확인 |

### 4.3 모니터링 통합

```
THUMBNAIL-01 (기존 — 개정): featureimage 존재 + R2 호스팅 + (.webp 또는 .jpg) + 해상도 검증 + ≤150KB
THUMBNAIL-02 (신규 — 해시 반복): 최근 5건 SHA256 중복 ≤1건 + 기본 fallback ≤1건/블로그
THUMBNAIL-03 (신규 — 라이브 검증): HTTP 200 + Content-Type image/webp|jpeg + 해상도 1200×630 (±10%)
THUMBNAIL-04 (신규 — Blogger 대응): 본문 첫 <img> 존재 + src HTTP 200 + WebP/JPEG 포맷
```

**적용 대상별 규칙 매핑:**

| 규칙 | SEAP Hugo | STAP Hugo | SEAP Blogger | CAR/TAP/ETAP/CUAP/RAP |
|------|-----------|-----------|-------------|----------------------|
| THUMBNAIL-01 | ✅ | ✅ | ✅ (.jpg 허용) | ✅ |
| THUMBNAIL-02 | ✅ | ✅ | ❌ (URL 해시 비교 불가) | ❌ |
| THUMBNAIL-03 | ✅ | ✅ | ❌ (Blogger CDN) | ❌ |
| THUMBNAIL-04 | ❌ | ❌ | ✅ | ❌ |

---

## 5. 예외 분석 & 마이그레이션

### 5.1 플랫폼별 예외

| 플랫폼 | 현재 상태 | 표준 적용 가능 여부 | 예외 사유 |
|--------|----------|-------------------|----------|
| **Hugo (Blowfish)** — 99개 전부 | 1200×630 또는 1:1 | ✅ 완전 적용 가능 | 공유 generator 사용 |
| **Blogger (SEAP)** | R2 WebP → 본문 첫 `<img>` | ⚠️ 부분 적용 | WebP/JPEG 호환, og:image 미구현 |
| **외부 hotlink (visitkorea)** | 405 HEAD 차단 | ❌ 적용 불가 | CDN 핫링크 보호, 브라우저에서만 200 |

**5000 플릿 테마 분포**: Blowfish 99개, PaperMod 0개, 커스텀 0개 — 단일 테마로 표준 적용 용이.

### 5.1.1 SEAP/STAP Blogger 예외 상세

| 항목 | SEAP Blogger (`senior-blogger`) | TAP Blogger (`tap-blogger`) |
|------|--------------------------------|---------------------------|
| 썸네일 생성 | Playwright → R2 WebP → 본문 첫 `<img>` | 미확인 (범위 밖) |
| og:image | **없음** (템플릿 미구현) | **없음** |
| 피드 썸네일 | **없음** | **없음** |
| WebP 호환 | **정상** (검증 완료) | 미확인 |
| 이미지 프록시 | **없음** (R2 URL 직접 서빙) | 미확인 |

### 5.1.2 SEAP/STAP Hugo 예외 상세

| 항목 | senior-hugo | STAP 5개 |
|------|-------------|---------|
| 해상도 | 600×600 → **1200×630로 마이그레이션** | 1200×630 (이미 OG 규격) |
| CSS | Blowfish cover 크롭 | Blowfish cover 크롭 |
| Fallback | `common/default-thumbnail.webp` → 고유 fallback | `{blog}-thumbnails/...` (정상) |
| stock-hugo bug | 해당 없음 | `thumbnail` 필드 정상, `featureimage`는 fallback |

### 5.2 기존 이미지 점진적 마이그레이션

| 단계 | 대상 | 작업 | 위험도 |
|------|------|------|--------|
| **1단계** | 신규 발행글 | 1200×630 마스터强制 | 낮음 (기존 호환) |
| **2단계** | senior/sector 1:1 이미지 | 600×600 유지 (CSS cover로 대응) | 없음 |
| **3단계** | 기본 fallback 8건 | 블로그별 고유 fallback로 교체 | 낮음 |
| **4단계** | R2 경로 불일치 (rap, senior 레거시) | 통합 경로로 재업로드 | 중간 (URL 변경) |
| **5단계** | 캐시 헤더 미설정 객체 | `Cache-Control: immutable` 추가 | 없음 |

### 5.3 Canary & 롤백

| 단계 | Canary 방법 | 롤백 방법 |
|------|------------|----------|
| 1단계 | `dispatcher.py {blog_id}` 1건 발행 → URL 검증 | stap.yaml에서 pause |
| 2단계 | `batch_thumbnails.py --site senior --dry-run` | R2에서 새 객체 삭제 |
| 3단계 | `batch_thumbnails.py --site senior` 1건 실행 | frontmatter 원복 |
| 4단계 | R2 경로 변경 시 기존 URL 30일 유지 | 새 경로 삭제, 기존 경로 재사용 |
| 5단계 | R2 콘솔에서 헤더 추가 | 헤더 원복 |

### 5.4 저장 비용 영향

| 항목 | 현재 | 마이그레이션 후 | 차이 |
|------|------|---------------|------|
| R2 객체 수 | ~15,000개 | ~15,500개 (+500 fallback) | +3.3% |
| R2 저장 비용 (월) | ~$0.23 | ~$0.24 | +$0.01 |
| R2 읽기 비용 (월) | ~$0.0036/만건 | 동일 | 0 |
| **총 비용 차이** | — | — | **+$0.01/월** (무시 가능) |

---

## 6. 대안 비교 요약

| 기준 | 대안 A: 단일 마스터 (1200×630) | 대안 B: 2 마스터 (1200×630 + 600×600) | **권장** |
|------|-----|-----|------|
| 생성 시간 | 1x | 2x | A |
| 저장 비용 | 1x | 2x | A |
| OG 호환 | ✅ | ✅ | 동일 |
| 1:1 컨테이너 | CSS cover로 대응 | 별도 이미지 | A (단순) |
| 복잡도 | 낮음 | 높음 | A |
| **결정** | **← 채택** | — | — |

| 기준 | 대안 1: 공유 기본 이미지 1개 | 대안 2: 블로그별 고유 fallback | **권장** |
|------|-----|-----|------|
| 구현 복잡도 | 낮음 | 중간 | 1 |
| 사용자 경험 | 나쁨 (모든 블로그 동일) | 좋음 (블로그 구분 가능) | 2 |
| 모니터링 | 어려움 (반복 감지 불가) | 쉬움 (블로그별 임계값) | 2 |
| 비용 | $0.23/월 | $0.24/월 | 동일 |
| **결정** | — | **← 채택** | — |

---

## 7. 구현 로드맵 (READ-ONLY 계획)

| 순서 | 작업 | 파일 | 대상 | 상태 |
|------|------|------|------|------|
| 1 | Hugo 어댑터 생성 | `shared/thumbnail_generator/hugo_adapter.py` | 신규 | 계획 |
| 2 | Blogger 어댑터 생성 | `shared/thumbnail_generator/blogger_adapter.py` | 신규 | 계획 |
| 3 | 어댑터 인터페이스 정의 | `shared/thumbnail_generator/adapter.py` | 신규 | 계획 |
| 4 | `generate_thumbnail()`에서 1200×630 강제 | `shared/thumbnail_generator/generator.py` | 공유 | 계획 |
| 5 | 폰트 fallback에 Malgun Gothic 추가 | `templates/image.html`, `templates/default.html` | 공유 | 계획 |
| 6 | 블로그별 fallback 이미지 7개 생성 + R2 업로드 | `common/fallback-{group}.webp` | 공유 | 계획 |
| 7 | `hugo_writer.py` fallback을 site_id별로 분기 | `shared/publishers/hugo_writer.py:1142-1145` | Hugo | 계획 |
| 8 | stock-hugo featureimage bug 수정 | `shared/publisher.py` 또는 `pipelines/stock/pipeline.py` | stock | 계획 |
| 9 | senior pipeline Blogger 어댑터 연결 | `pipelines/senior/pipeline.py:400-406` | senior | 계획 |
| 10 | THUMBNAIL-01/02/03/04 규칙 추가 | `ops_dashboard/checks/standard.py` | 모니터링 | 계획 |
| 11 | `batch_thumbnails.py`에 senior 등록 | `scripts/batch_thumbnails.py:49-92` | 공유 | 계획 |
| 12 | R2 캐시 헤더 추가 (기존 객체) | R2 콘솔 또는 boto3 스크립트 | 공유 | 계획 |
| 13 | allowlist + hash 테스트 | `tests/test_thumbnail_*.py` | 테스트 | 계획 |

---

## 8. 잔존 위험

1. **stock-hugo featureimage bug**: `thumbnail` 필드에 정상 URL이나 `featureimage`는 fallback. 코드 수정 시 기존 게시물 변경 없이 신규 발행분에만 적용하는 것이 안전한지 확인 필요.
2. **senior-hugo featureimage 전부 fallback**: Playwright chromium 설치 후 canary에서 고유 썸네일 확인됨. 정규 스케줄에서도 지속 생성되는지 모니터링 필요.
3. **Blowfish 4개 CUAP 블로그 square override**: `aspect-ratio: 1/1` + `object-fit: contain` → 1200×630 마스터가 잘림 없이 전체 표시. OG 이미지로는 1200×630이 적절하나 카드 컨테이너에서 contain 동작 확인 필요.
4. **Twitter large card 미사용**: 현재 `twitter:card=summary` (small). 1200×630 마스터를 large card로 활용하려면 `twitter:card=summary_large_image` 변경 필요. Blowfish 테마 템플릿 수정 범위.
5. **R2 캐시 헤더**: 현재 Cache-Control 없음. `immutable` 추가 시 기존 객체에 Retrofit 필요 (R2 콘솔 또는 boto3 스크립트).
6. **Blogger og:image 한계**: Blogger 템플릿에 og:image 미구현 → 소셜 공유 시 썸네일 미표시. Blogger 템플릿 수정이 필요하나 이번 범위 밖.
7. **Unsplash API 의존**: `generate_image_thumbnail()`이 Unsplash에 실패하면 텍스트 전용 fallback → 품질 저하.
8. **senior 레거시 버킷**: `SENIOR_R2_BUCKET` (별도 버킷) 사용 경로가 코드에 남아있음. 통합 시 기존 URL 깨짐 가능 — 이번 범위에서 제외.
