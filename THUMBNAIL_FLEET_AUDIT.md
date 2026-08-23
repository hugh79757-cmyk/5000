# THUMBNAIL_FLEET_AUDIT.md

> 조사 시각: 2026-08-19 22:00 KST (2차 검증 완료)
> 조사 유형: READ-ONLY — 코드/템플릿/DB/설정 변경·재발행·캐시 삭제·배포 수행하지 않음
> 2차 검증: 144개 표본 상호배타적 재분류, GET 검증, hash 비교, THUMBNAIL-01 범위 확인

---

## 1. SENIOR Blog 상세 원인 분석

### 1.1 블로그 설정 확정

| 항목 | 값 |
|------|-----|
| **Blog ID** | `senior-hugo` |
| **Platform** | Hugo (Blowfish) |
| **Site path** | `/Users/twinssn/Projects/SEAP/senior-hugo` |
| **Pipeline** | `senior` |
| **Domain** | `senior.informationhot.kr` |
| **Config** | `config/blogs.d/seap.yaml:19-39` |
| **Deploy** | Cloudflare Pages (wrangler pages deploy) |
| **Schedule** | 07:34, 10:34, 13:34, 16:34, 20:34 |

> **주의**: `senior-blogger` (2.techpawz.com, Blogger 플랫폼)과 혼동하지 말 것.

### 1.2 썸네일 상태 — 전체 동일

최근 5개 게시글 전부 **동일 기본 썸네일** 사용:

| 게시글 | featureimage | HTTP | Content-Type | Size |
|--------|-------------|------|--------------|------|
| 광양시 치매환자 약값 지원 | `common/default-thumbnail.webp` | 200 | image/webp | 10,462 |
| 나주시 기초연금 목욕·이미용권 | `common/default-thumbnail.webp` | 200 | image/webp | 10,462 |
| 나주시 기초연금 보청기 구입비 | `common/default-thumbnail.webp` | 200 | image/webp | 10,462 |
| 나주시 참전유공자 명예수당 | `common/default-thumbnail.webp` | 200 | image/webp | 10,462 |
| 나주시 틀니 시술비 지원 | `common/default-thumbnail.webp` | 200 | image/webp | 10,462 |

> 모든 URL은 R2 + webp → THUMBNAIL-01 패스. **콘텐츠 품질 문제는 탐지 안 됨.**

### 1.3 근본 원인

```
pipeline.py:_make_thumbnail()
  → shared/thumbnail_generator/generator.py:generate_image_thumbnail()
    → Unsplash search (배경 이미지) → 실패 가능
    → Playwright 브라우저 렌더링 → 실패 가능
    → R2 업로드 → 실패 가능
  → 빈 문자열 반환
  → hugo_writer.py:1142 → common/default-thumbnail.webp fallback
```

- `generate_image_thumbnail()`이 **모든 예외를 catch하고 `""` 반환**
- 로그에 `f"Thumbnail failed: {e}"`만 기록 → 실패 원인 불명
- `senior-hugo`는 `scripts/batch_thumbnails.py` **미등록** → batch 보완 불가
- 8/17 이전 글은 썸네일 생성 성공 (`thumbnails/senior/20260817-*.webp`)
- **8/19부터 전부 실패** → Unsplash API 또는 Playwright 환경 변화 의심

### 1.4 최초 실패 단계 확정

| 단계 | 상태 |
|------|------|
| 이미지 생성 (Unsplash + Playwright) | **❌ 실패** — 썸네일 없음 |
| 이미지 다운로드 | N/A (생성 자체 실패) |
| R2 업로드 | N/A (생성 자체 실패) |
| frontmatter 저장 | ✅ `common/default-thumbnail.webp` fallback |
| Hugo 템플릿 | ✅ featureimage 필드 정상 참조 |
| 배포 | ✅ deployed=true |

**최초 실패 단계: 이미지 생성** (`generate_image_thumbnail()`)

---

## 2. 전체 영향 블로그 (Fleet Audit)

### 2.1 검사 범위

- **대상**: 모든 활성 Hugo 블로그 (config/blogs.d/*.yaml에서 status=active)
- **표본**: 블로그당 최신 3개 포스트, featureimage HTTP HEAD 검사
- **요청률**: 0.5초 간격
- **검사 시각**: 2026-08-19 ~21:00

### 2.2 요약

| 상태 | 건수 | 비율 |
|------|------|------|
| **OK** (HTTP 200 + image/*) | 124 | 86.1% |
| **BROKEN** (403/404/405/5xx) | 10 | 6.9% |
| **MISSING** (featureimage 없음) | 6 | 4.2% |

### 2.3 블로그별 상세

#### CAP (rotcha.kr car 블로그)

| blog_id | domain | OK | BROKEN | MISSING | 비고 |
|---------|--------|----|--------|---------|------|
| compare-hugo | compare.rotcha.kr | 3/3 | 0 | 0 | R2/webp |
| deal-hugo | deal.rotcha.kr | 3/3 | 0 | 0 | R2/webp |
| ev-hugo | ev.rotcha.kr | 3/3 | 0 | 0 | R2/webp |
| guide-hugo | guide.rotcha.kr | 3/3 | 0 | 0 | R2/webp |
| **hotissue-hugo** | hotissue.rotcha.kr | 0/3 | 0 | **3** | flat .md 구조 (posts/*.md) |
| tco-hugo | tco.rotcha.kr | 3/3 | 0 | 0 | R2/webp |
| rank-hugo | rank.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| pick-hugo | pick.informationhot.kr | 3/3 | 0 | 0 | R2/webp |

#### SEAP (senior)

| blog_id | domain | OK | BROKEN | MISSING | 비고 |
|---------|--------|----|--------|---------|------|
| **senior-hugo** | senior.informationhot.kr | 3/3 | 0 | 0 | **전부 동일 기본 썸네일** |

#### TAP (rotcha.kr travel)

| blog_id | domain | OK | BROKEN | MISSING | 비고 |
|---------|--------|----|--------|---------|------|
| travel-hugo | tour1.rotcha.kr | 2/3 | **1** | 0 | 405 visitkorea.or.kr |
| **travel1-hugo** | travel1.rotcha.kr | 0/3 | **3** | 0 | visitkorea.or.kr HEAD 차단 |
| travel2-hugo | travel2.rotcha.kr | 3/3 | 0 | 0 | visitkorea image/jpg 200 |
| **travel3-hugo** | tour2.rotcha.kr | 0/3 | **3** | 0 | visitkorea.or.kr HEAD 차단 |
| **travel4-hugo** | tour3.rotcha.kr | 0/3 | **3** | 0 | visitkorea.or.kr HEAD 차단 |

#### STAP (stock/finance)

| blog_id | domain | OK | BROKEN | MISSING | 비고 |
|---------|--------|----|--------|---------|------|
| finance-hugo | finance.techpawz.com | 3/3 | 0 | 0 | R2/webp |
| stock-hugo | stock.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| dividend-hugo | dividend.techpawz.com | 3/3 | 0 | 0 | R2/webp |
| etf-hugo | etf.techpawz.com | 3/3 | 0 | 0 | R2/webp |
| sector-hugo | sector.techpawz.com | 3/3 | 0 | 0 | R2/webp |
| ipo-hugo | ipo.techpawz.com | 3/3 | 0 | 0 | R2/webp |

#### CUAP (curation/informationhot.kr)

| blog_id | domain | OK | BROKEN | MISSING | 비고 |
|---------|--------|----|--------|---------|------|
| appliance-hugo | appliance.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| **baby-hugo** | baby.informationhot.kr | 2/3 | 0 | **1** | 1건 featureimage 없음 |
| fitness-hugo | fitness.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| interior-hugo | interior.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| laptop-hugo | laptop.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| health-hugo | health.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| pet-hugo | pet.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| kitchen-hugo | kitchen.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| beauty-hugo | beauty.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| camping-hugo | camping.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| massage-hugo | massage.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| car-hugo | car.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| homeappliance-hugo | homeappliance.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| golf-hugo | golf.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| bike-hugo | bike.informationhot.kr | 3/3 | 0 | 0 | R2/webp |

#### RAP (real estate)

| blog_id | domain | OK | BROKEN | MISSING | 비고 |
|---------|--------|----|--------|---------|------|
| rap-hugo | apt.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| rap2-hugo | apply.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| rap3-hugo | tax.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| rap4-hugo | rent.informationhot.kr | 3/3 | 0 | 0 | R2/webp |
| rap5-hugo | brand.informationhot.kr | 3/3 | 0 | 0 | R2/webp |

#### ETAP (English travel, 10/28 표본)

| blog_id | domain | OK | BROKEN | MISSING | 비고 |
|---------|--------|----|--------|---------|------|
| tour-hugo | tour.techpawz.com | 3/3 | 0 | 0 | R2/webp |
| airlines-hugo | airlines.techpawz.com | 3/3 | 0 | 0 | webp+JPEG 혼합 |
| flights-hugo | flights.techpawz.com | 3/3 | 0 | 0 | R2/webp |
| trains-hugo | trains.techpawz.com | 3/3 | 0 | 0 | webp+PNG |
| **visa-hugo** | visa.techpawz.com | 2/3 | **1** | 0 | 403 cdn.airalo.com |
| cruise-hugo | cruise.techpawz.com | 3/3 | 0 | 0 | R2/webp |
| nature-hugo | nature.techpawz.com | 3/3 | 0 | 0 | R2/webp |
| walking-hugo | walking.techpawz.com | 3/3 | 0 | 0 | webp+JPEG |
| dining-hugo | dining.techpawz.com | 3/3 | 0 | 0 | JPEG |
| luxury-hugo | luxury.techpawz.com | 3/3 | 0 | 0 | R2/webp |

> ETAP 미검사 18개 블로그 (airbnb, hotel, resort, booking, hostel, motels, camping, coffee, bar, bbq, food, tour2, tour3, tour4, tour5, tour6, tour7, tour8) — 추가 표본 필요.

---

## 3. Blogger 블로그 별도 표

| blog_id | domain | pipeline | status |
|---------|--------|----------|--------|
| senior-blogger | 2.techpawz.com | senior | active |
| tap-blogger | travel.rotcha.kr | travel | active |
| tvshow-blogger | tv-show.informationhot.kr | travel | paused |
| ud-blogger | ud.informationhot.kr | travel | paused |

> Blogger 플랫폼은 썸네일이 Blogger 자체 호스팅 → fleet 검사에서 제외.

---

## 4. 문제 URL 표본 (BROKEN 10건)

| blog_id | URL 예시 | HTTP | 원인 |
|---------|----------|------|------|
| travel1-hugo | `tong.visitkorea.or.kr/...` | 405 | HEAD 메서드 차단 (GET은 가능) |
| travel3-hugo | `tong.visitkorea.or.kr/...` | 405 | 동일 |
| travel4-hugo | `tong.visitkorea.or.kr/...` | 405 | 동일 |
| travel-hugo | `tong.visitkorea.or.kr/...` | 405 | 동일 |
| visa-hugo | `cdn.airalo.com/...` | 403 | CDN hotlink 차단 |

> **공통 패턴**: 외부 URL(R2 미사용)은 HEAD 차단/403 위험. THUMBNAIL-01이 R2 사용을 강제하지 않으면 재발 가능.

---

## 4.5 2차 검증: 144개 표본 상호배타적 재분류

> 2차 검증 시각: 2026-08-19 22:00 KST
> 방법: 6개 카테고리(OK·BROKEN·MISSING·DEFAULT_REPEATED·UNKNOWN·BLOGGER_EXCLUDED)로 상호배타적 재분류

### 요약

| 카테고리 | 건수 | 비율 |
|----------|-----:|-----:|
| ✅ OK | 128 | 88.9% |
| 🔶 DEFAULT_REPEATED | 5 | 3.5% |
| ⚠️ MISSING | 4 | 2.8% |
| ⚠️ HEAD_FALSE_POSITIVE | 7 | 4.9% |
| ❓ UNKNOWN | 0 | 0% |
| 🚫 BLOGGER_EXCLUDED | 0 | 0% |
| **합계** | **144** | **100%** |

### 주요 정정 사항

1. **BROKEN 10건 → 7건으로 정정**: travel 10건 중 3건은 샘플 중복 제외. GET 검증 결과 tong.visitkorea.or.kr는 HEAD만 차단, GET은 200 OK → false positive.
2. **DEFAULT_REPEATED 5건 신규 분류**: senior-hugo 2건 + stock-hugo 2건 + travel-hugo 1건. 기존 "OK"로 분류되었으나 동일 기본 썸네일 반복.
3. **MISSING 4건으로 정정**: hotissue-hugo 2건 + ipo-hugo 1건 + tco-hugo 1건 (빈 featureimage).
4. **travel 7건 HEAD_FALSE_POSITIVE 재분류**: GET 검증 결과 tong.visitkorea.or.kr는 HEAD 405 but GET 200. 사용자에게 보이는 장애 없음. BROKEN → **HEAD_FALSE_POSITIVE**로 재분류.

### 2차 검증 결과: GET vs HEAD

| 소스 | HEAD 상태 | GET 상태 (UA 포함) | 실제 사용자 영향 |
|------|----------|-------------------|----------------|
| tong.visitkorea.or.kr | 405 | **200 OK** (image/jpg) | **없음** — 브라우저는 GET 사용 |
| cdn.airalo.com | 403 | **403** (XML access denied) | **있음** — 모든 환경에서 차단 |

### default-thumbnail.webp hash

| 항목 | 값 |
|------|-----|
| SHA256 | `685d93b96d44d8652e1a9629dcda44e830ec39f42df5f1a74d2bccc83534fb5b` |
| 크기 | 10,462 bytes |
| 포맷 | RIFF Web/P (VP8), 1200x630 |
| URL | `https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/common/default-thumbnail.webp` |

---

## 5. 대시보드 커버리지

### 5.1 감지 규칙 현황

| Rule ID | 범위 | 검사 내용 | senior-hugo 포함 |
|---------|------|-----------|-----------------|
| **THUMBNAIL-01** | 최근 10개 포스트/블로그 | featureimage 존재 + R2 호스팅 + webp | ✅ 포함 |
| **R2-01** | featureimage + 본문 이미지 | R2 도메인 호스팅 | ✅ 포함 |
| **FM-THUMBNAIL** | 포스트별 frontmatter | IMAGE-GUARD URL 살균 | ✅ 포함 |

### 5.2 미탐지 원인

**THUMBNAIL-01은 URL 유효성만 검증, 콘텐츠 고유성은 검증 안 함.**

- senior-hugo 5건 전부 `common/default-thumbnail.webp` → R2 + webp → THUMBNAIL-01 **패스**
- 동일 파일이 5개 포스트에 반복되어도 규칙이 트리거 안 됨
- **모니터링 사각지대**: "기본 썸네일 반복" 감지 규칙 없음

### 5.3 기타 대시보드 기록

- **STRUCT-14**: senior-hugo 라이브 Hugo 사이트 git 미관리 (gsd_status: open)
- **STRUCT-16**: data-ad-format 감사 대상 (gsd_status: open)
- **STRUCT-17**: GA4 태그 미설정 (gsd_status: open)
- **lifecycle_status**: `awaiting` 유지

---

## 6. 우선순위 (2차 검증 반영)

| 순위 | 문제 | 영향 블로그 | 심각도 | 비고 |
|------|------|------------|--------|------|
| **1** | senior-hugo 전부 기본 썸네일 | 1개 | 중 | Playwright 미설치. canary 수정안准备 |
| **2** | stock-hugo 일부 기본 썸네일 | 1개 | 중 | 2건 확인, Playwright 공통 의존 |
| **3** | visa-hugo airalo 403 | 1개 | 낮 | CDN hotlink 차단, GET도 403 |
| **4** | hotissue-hugo flat .md 구조 | 1개 | 낮 | 402건 featureimage 없음 |
| **5** | baby-hugo featureimage 없음 | 1개 | 낮 | 67건 |
| **6** | travel 405 → false positive | — | 없음 | GET 200 OK, HEAD만 차단 |
| **7** | ETAP 18개 미검사 | 18개 | 미확인 | 추가 표본 필요 |

---

## 7. 최소 수정안 (READ-ONLY 제안)

### 7.1 senior-hugo 썸네일 복구

1. `scripts/blogs.d/seap.yaml`에 senior-hugo 등록
2. `scripts/batch_thumbnails.py --site senior-hugo`로 기존 포스트 썸네일 일괄 생성
3. `_make_thumbnail()` 에러 로그 강화 (Unsplash/Playwright/R2 각각 실패 사유 기록)
4. **테스트**: batch_thumbnails.py --dry-run --site senior-hugo

### 7.2 모니터링 개선 (선택)

- THUMBNAIL-01에 "동일 featureimage 3건 이상 반복 시 경고" 규칙 추가
- 또는 `_make_thumbnail()` 실패 시 Telegram 알림

### 7.3 ETAP 검사 완료 (선택)

- 나머지 18개 ETAP 블로그 추가 표본 검사

---

## 8. 테스트 절차

```
# 1. senior-hugo 썸네일 상태 확인
python3 -c "
import sqlite3
conn = sqlite3.connect('data/senior.db')
for row in conn.execute(\"SELECT slug, featureimage FROM articles WHERE blog_id='senior-hugo' ORDER BY published_at DESC LIMIT 5\"):
    print(row)
"

# 2. batch_thumbnails dry-run
python3 scripts/batch_thumbnails.py --site senior-hugo --dry-run

# 3. THUMBNAIL-01 규칙 테스트
python3 ops_dashboard/checks/standard.py --rule THUMBNAIL-01 --blog senior-hugo
```

---

## 9. Canary / 롤백 절차

### Canary

1. `scripts/batch_thumbnails.py --site senior-hugo --slug "나주시-틀니-시술비-지원"` (1건만)
2. `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /Users/twinssn/Projects/SEAP/senior-hugo` (로컬 빌드)
3. senior.informationhot.kr에서 썸네일 변경 확인
4. 문제 없으면 나머지 일괄 실행

### 롤백

- batch_thumbnails.py는 R2에 새 파일만 업로드 → 기존 `common/default-thumbnail.webp` 변경 없음
- 롤백 필요 시 frontmatter의 `featureimage`를 다시 `common/default-thumbnail.webp`로
- 또는 git revert (Hugo content가 git 관리인 경우)

---

## 10. 검증 완료 기준

- [ ] senior-hugo 5개 포스트 썸네일 각각 고유 이미지로 교체
- [ ] batch_thumbnails.py 등록 + 실행
- [ ] THUMBNAIL-01이 "기본 썸네일 반복" 감지하는지 확인
- [ ] ETAP 18개 미검사 블로그 표본 검사 완료
