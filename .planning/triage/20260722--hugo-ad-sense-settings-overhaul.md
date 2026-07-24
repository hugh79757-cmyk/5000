---
date: 2026-07-22
type: fix
status: resolved
---

# 휴고 블로그 광고 설정 전면 정리 — rotcha.kr + 5.informationhot.kr

## What

rotcha.kr(rotcha-blog)과 5.informationhot.kr(5.informationhot-hugo)의 AdSense 광고가 공백으로 노출되는 문제를 조사하고, 테크포우즈(정상 작동 기준) 형식으로 통일 수정 후 배포.

## Why

### rotcha.kr 원인
1. `extend-head.html`에 adsbygoogle.js 로딩 코드 **없음** (meta + preconnect만)
2. adsbygoogle.js가 `extend-head-uncached.html`의 lazy-load(interaction/7초)로 로딩되어 지연
3. `head.html`의 `{{ with .Site.Params.advertisement.adsense }}` 블록 — params.toml에 `[advertisement]` 섹션 없어 **사망 코드**
4. `anchor-above-title.html`의 `height:100px` 고정이 `data-ad-format="auto"`와 충돌
5. `content-with-ads.html`의 `</p>` 기반 split 로직이 일부 글의 HTML 구조와 불일치

### 5.informationhot.kr 원인
1. 광고 인프라 전면 누락: `layouts/`, `assets/css/extended/`, `partials/adsense/` 디렉토리 없음
2. `params.toml`에 `slot_display`, `slot_infeed` 미정의
3. Blowfish 테마 기본 사용으로 광고 삽입 템플릿 없음

## Files changed

### rotcha-blog (6개 파일)
- `layouts/partials/extend-head.html` — adsbygoogle.js **즉시 로드** 스크립트 추가 (테크포우즈 동일)
- `layouts/partials/extend-head-uncached.html` — lazy-load 스크립트 **제거**, GA4만 유지
- `layouts/partials/head.html` — `advertisement.adsense` 사망 코드 블록 **제거**
- `layouts/_default/single.html` — `adsense/lazy-load.html` partial 호출 **제거**
- `layouts/partials/content-with-ads.html` — `</p>` split 로직 **제거**, 단순 `.Content` + Ad #2
- `layouts/partials/adsense/anchor-above-title.html` — `height:100px` **제거**, `display:block`만
- `layouts/partials/adsense/lazy-load.html` — **파일 삭제**

### 5.informationhot-hugo (신규 생성 8개 파일)
- `config/_default/params.toml` — `slot_display`, `slot_infeed` 추가
- `layouts/partials/extend-head.html` — adsbygoogle.js lazy-load (3초 timeout)
- `layouts/partials/adsense/in-article.html` — 본문 내 광고 partial
- `layouts/partials/adsense/leaderboard.html` — 리더보드 광고 partial
- `layouts/partials/adsense/in-feed.html` — 리스트 광고 partial
- `layouts/partials/adsense/lazy-load.html` — IntersectionObserver lazy push
- `layouts/_default/single.html` — Blowfish single.html 오버라이드 + 광고 삽입
- `assets/css/custom.css` — CLS 방지 CSS 보강 (min-height, unfilled 숨김, 중복 방지)

## How

### 테크포우즈 표준 도출 과정
테크포우즈(정상 작동) ↔ 롯차(공백) ↔ informationhot(공백) 3개 사이트를 비교 분석.

| 항목 | 테크포우즈 ✅ | informationhot ✅ | 롯차 ❌ (수정 전) |
|------|-------------|------------------|---------|
| adsbygoogle.js 로딩 | `<head>` 즉시 로드 | lazy-load (3초) | lazy-load (7초, .IsPage만) |
| head.html adsense | 없음 (테마 기본) | 없음 (테마 기본) | 사망 코드 |
| CSS 숨김 규칙 | 없음 | 없음 | 공격적 (unfilled→height:0) |
| 광고 배치 | content 하드코딩 | partials | partials + split 로직 |

테크포우즈의 핵심 원칙:
- ** adsbygoogle.js를 `<head>`에서 즉시 로드** (lazy-load 불필요)
- **CSS 최소화** (중앙 정렬만, 숨김/축소 규칙 없음)
- **head.html 오버라이드 없음** (테마 기본 사용)

### 수정 접근
1. rotcha: lazy-load → 즉시 로드로 전환, 사망 코드 제거, 공격적 CSS 유지(사용자 요청)
2. 5.informationhot: 빈 구조에 광고 인프라 전체 신규 구축

## Verification

### rotcha-blog
- Hugo 빌드 5988 페이지, 0 에러 ✅
- 배포 완료: https://50c098da.rotcha-blog.pages.dev ✅
- 빌드된 HTML에서 `data-ad-slot=8733248550` 3건 확인 ✅
- `height:100px` 제거 확인 ✅
- lazy-load 스크립트 제거 확인 (0건) ✅
- `adsbygoogle.js` 즉시 로딩 확인 (1건) ✅

### 5.informationhot-hugo
- Hugo 빌드 48 페이지, 0 에러 ✅
- 배포 완료: https://c3c55e30.5-informationhot.pages.dev ✅
- 빌드된 HTML에서 `data-ad-slot="6890858668"` 확인 ✅
- `adsbygoogle.push({})` 확인 ✅

### 잔존 위험
- rotcha.kr에서 광고가 실제로 채워지는지는 브라우저에서 직접 확인 필요 (AdSense 콘솔에서 슬롯 `8733248550`이 `ca-pub-8772455780561463` 계정에 유효한지)
- `adsense/lazy-load.html` 파일은 rotcha-blog에서 삭제됨 — 다른 사이트에서 참조 시 주의
- `head.html`의 사망 코드 제거로 인해 Blowfish 기본 head.html의 다른 로직에 영향 없음 확인됨
- 5.informationhot의 `single.html` 오버라이드가 Blowfish 테마 기본 기능(시리즈, 공유, 댓글)을 일부 포함 — Blowfish 업데이트 시 동기화 필요

## 개선 제안 (추후 검토)

1. **rotcha `custom.css`의 공격적 숨김 규칙 완화** — `ins.adsbygoogle[data-ad-status="unfilled"] { display:none; height:0 }`이 광고 미노출 시 공간도 제거하나, 사용자가 "공백"으로 인지할 수 있음. unfilled 시 최소 높이 유지 검토
2. **`[id^="aswift_"]` CSS 추가 검토** — 테크포우즈에만 있는 adSense iframe 중앙 정렬 CSS. rotcha에도 추가하면 레이아웃 안정성 향상
3. **informationhot-hugo `single.html` Blowfish 동기화** — 테마 업데이트 시 변경사항 반영 필요. Blowfish 기본 `single.html`과 병렬 유지 권장
4. **`extend-head.html` vs `extend_head.html` 네이밍 통일** — informationhot-hugo에 둘 다 존재. Blowfish는 `extend-head.html`(하이픈) 호출. underscore 버전은 미사용
