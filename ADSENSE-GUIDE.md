# 블로우피쉬테마 광고설정 가이드

> 최종 갱신: 2026-07-24
> 기반: pet-hugo (pet.informationhot.kr) AdSense 표준화 결과
> **변경: 2슬롯 단순화 + Auto Ads 위임 (2026-07-24)**

---

## 1. 광고 아키텍처 개요 (2슬롯 + Auto Ads)

Blowfish Hugo 블로그의 광고는 **수동 2개 슬롯** + **Auto Ads(앵커/전면/장문 내 자동 배치)**로 구성한다.

| 슬롯 | 위치 | `data-ad-format` | 용도 |
|------|------|------------------|------|
| **top** | `<header>` 내부, **H1 직전** | `auto` (Display) | 타이틀 상단 배너 |
| **in-article** | `<header>` 내부, **Description(lead) 직후 = 첫 H2 직전** | `fluid` + `in-article` | 설명문과 첫 소제목 사이 |

> **나머지 모든 위치(본문 중간, 문단 사이, 3번째 H2 앞 등)는 Auto Ads에 위임한다.**
> `extend-head.html`에서 `adsbygoogle.js`를 즉시 로드하면 Auto Ads가 자동 활성화된다.

---

## 2. 핵심 발견: TOC 비활성화 필수

### 원인
Blowfish의 sticky TOC (`showTableOfContents = true`)는 `order-first lg:ms-auto lg:order-last` CSS로 레이아웃을 좌우 이분한다. 이 레이아웃 구조가 AdSense의 fluid/In-article 광고 렌더링과 충돌하여 **모든 광고가 unfilled 상태**로 머무른다.

### 증상
- `showTableOfContents = true` → 광고 0개 노출 (모두 unfilled)
- `showTableOfContents = false` → 광고 정상 노출

### 조치
**모든 광고 설정 블로그의 `params.toml`에서 `showTableOfContents = false`로 설정할 것.**

---

## 3. 파일별 설정

### 3-1. config/_default/params.toml

```toml
[article]
  showTableOfContents = false   # ← 반드시 false (광고 렌더링 충돌 방지)

[advertisement]
  adsense       = "ca-pub-6677996696534146"
  inArticleSlot = "2195212287"  # In-article / fluid 슬롯 (첫 H2 앞)
  topSlot       = "2195212287"  # Display (topSlot) 슬롯 (H1 위)
```

> **슬롯 ID는 각 블로그/계정별로 별도 발급받은 값으로 교체할 것.**

---

### 3-2. layouts/partials/extend-head.html

```html
{{ with site.Params.advertisement.adsense }}
<script async
        src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{ . }}"
        crossorigin="anonymous"></script>
{{ end }}
```

**즉시 로드** (`async`만 사용, lazy-load 없음). `client=` 파라미터로 Publisher ID 전달.
이 한 줄로 **Auto Ads(앵커, 전면, 장문 내 자동 삽입)까지 모두 활성화**된다.

---

### 3-3. layouts/partials/adsense/top.html (Display 슬롯)

```html
<div class="ad-top not-prose my-4">
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="{{ site.Params.advertisement.adsense }}"
     data-ad-slot="{{ site.Params.advertisement.topSlot }}"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>
```

- `data-ad-format="auto"` — Display 광고 (타이틀 상단)
- `not-prose` — Blowfish prose 스타일 비활성화
- `my-4` — 상하 마진

---

### 3-4. layouts/partials/adsense/in-article.html (In-article 슬롯)

```html
<div class="ad-inarticle not-prose my-4">
<ins class="adsbygoogle"
     style="display:block; text-align:center;"
     data-ad-layout="in-article"
     data-ad-format="fluid"
     data-ad-client="{{ site.Params.advertisement.adsense }}"
     data-ad-slot="{{ site.Params.advertisement.inArticleSlot }}"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>
```

- `data-ad-format="fluid"` + `data-ad-layout="in-article"` — AdSense In-article 자동 배치
- 각 `ins` 태그 직후 **즉시 `push({})` 호출**

---

### 3-5. layouts/_default/single.html override — 헤더 내 2슬롯만 배치

```html
<header id="single_header" class="mt-5 max-w-prose">
  {{/* ===== 1. H1 직전 광고 (Display) ===== */}}
  {{ partial "adsense/top.html" . }}

  <h1>{{ .Title }}</h1>
  {{ with .Description }}<p class="lead">{{ . }}</p>{{ end }}

  {{/* ===== 2. lead(설명문) 후 = 첫 H2 직전 광고 (In-article) ===== */}}
  {{ partial "adsense/in-article.html" . }}
</header>

<div class="article-content max-w-prose mb-20">
  {{ .Content }}
</div>
```

> **본문 분할 인젝션 로직(split A, split B) 완전 제거.**  
> `.Content`는 그대로 렌더링하고, Auto Ads가 알아서 장문 본문 중간에 광고를 삽입하게 둔다.

---

### 3-6. assets/css/custom.css

```css
/* ── AdSense 슬롯 공통 ── */
.ad-inarticle,
.ad-top {
  display: block;
  margin: 24px 0;
  min-height: 250px;
  text-align: center;
}
@media (max-width: 767px) {
  .ad-inarticle,
  .ad-top {
    min-height: 200px;
  }
}

/* ── unfilled: 공간 제거 ── */
ins.adsbygoogle[data-ad-status="unfilled"] {
  min-height: 0 !important;
  height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  display: none !important;
}

/* ── 다크모드 배경 방어 ── */
.dark ins.adsbygoogle,
html.dark ins.adsbygoogle {
  background: #fff !important;
}
```

---

## 4. AdSense 슬롯 발급 원칙

| 용도 | 슬롯 유형 | 크기 | 발급 위치 |
|------|----------|------|----------|
| `topSlot` (타이틀 상단) | **Display** | 가변 (auto) | AdSense 대시보드 → 광고 단위 → **디스플레이 광고** |
| `inArticleSlot` (첫 H2 앞) | **In-article** | 가변 (fluid) | AdSense 대시보드 → 광고 단위 → **인아티클 광고** |

> **별도 슬롯으로 각각 발급받을 것.** (동일 ID 재사용해도 광고는 채워지나, 리포팅/관리 분리 권장)

---

## 5. Auto Ads (앵커/전면/장문 내 자동 배치)

`extend-head.html`에서 `adsbygoogle.js`를 `<head>`에 즉시 로드하면 **Auto Ads 자동 활성화**. 별도 코딩 불필요.

**확인 사항:**
1. AdSense 대시보드 → Auto ads → **앵커 활성화** toggle ON
2. AdSense 대시보드 → Auto ads → **전면 광고** toggle ON (원할 경우)
3. 장문 콘텐츠(800자 이상) 본문 중간에 Auto Ads가 자동 삽입됨 — 수동 인젝션 불필요

---

## 6. CLS 방지 체계

| 상황 | CSS 규칙 |
|------|----------|
| 광고 로드 전 | `min-height: 250px` (PC) / `200px` (Mobile) |
| 광고 unfilled | `display:none` + `height:0` |
| 광고 filled | Hugo 기본 높이가 적용됨 |

---

## 7. 체크리스트 — 신규 블로그 적용 시

- [ ] `params.toml`: `showTableOfContents = false` 설정
- [ ] `params.toml`: `[advertisement]` 섹션에 `adsense`, `inArticleSlot`, `topSlot` 정의
- [ ] `layouts/partials/extend-head.html` 생성 (adsbygoogle.js 즉시 로드)
- [ ] `layouts/partials/adsense/top.html` 생성 (Display 슬롯)
- [ ] `layouts/partials/adsense/in-article.html` 생성 (In-article 슬롯)
- [ ] `layouts/_default/single.html` override에 **헤더 내 2슬롯만 배치** (본문 분할 로직 없음)
- [ ] `assets/css/custom.css`에 `.ad-inarticle`, `.ad-top`, `unfilled` 규칙 포함
- [ ] AdSense 대시보드에서 `topSlot` (Display)과 `inArticleSlot` (In-article) **별도 슬롯** 발급
- [ ] Hugo 빌드 정상 확인
- [ ] Worker/Pages 배포 후 광고 실제 노출 확인 (H1 위, 첫 H2 위 + Auto Ads 앵커/장문)

---

## 8. 금기사항

1. **`showTableOfContents = true` 금지** — 광고 전체 렌더링 실패
2. **레이지 로드 금지** — adsbygoogle.js는 `<head>`에서 async 즉시 로드. IntersectionObserver 기반 지연 로딩 사용 금지
3. **본문 분할 인젝션(split A/B) 금지** — Auto Ads에 위임
4. **mobile-sticky.html 사용 금지** — Auto ads 앵커와 충돌

---

> **요약**: 수동 슬롯은 **딱 2개(H1 위, 첫 H2 위)**만 직접 배치. 나머지는 **Auto Ads가 알아서**. 단, `showTableOfContents = false`와 `extend-head.html` 즉시 로드는 필수 선결 조건.