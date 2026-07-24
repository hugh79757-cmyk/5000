# 블로우피쉬테마 광고설정 가이드

> 최종 갱신: 2026-07-22
> 기반: pet-hugo (pet.informationhot.kr) AdSense 표준화 결과

---

## 1. 광고架构 개요

Blowfish Hugo 블로그의 광고는 총 **4개 슬롯**으로 구성된다.

| 슬롯 | 위치 | data-ad-format | 설명 |
|------|------|----------------|------|
| **top** | `<header>` 내부, H1 직전 | `auto` (Display) | 타이틀 상단 배너 |
| **header in-article** | `<header>` 내부, Description(lead) 직후 | `fluid` + `in-article` | 설명문과 첫 H2 사이 |
| **split A** | 본문 도입단락 직후 | `fluid` + `in-article` | pick 로직 기반 |
| **split B** | 본문 3번째 H2 직전 (고가치 섹션) | `fluid` + `in-article` | 800자 이상 또는 고가치 섹션만 해당 |

---

## 2. 핵심 발견: TOC 비활성화 필수

### 원인
Blowfish의 sticky TOC (`showTableOfContents = true`)는 `order-first lg:ms-auto lg:order-last` CSS로 레이아웃을 좌우 이분한다. 이 레이아웃 구조가 AdSense의 fluid/In-article 광고 렌더링과 충돌하여 **모든 광고가 unfilled 상태**로 머무른다.

### 증상
- `showTableOfContents = true` → 광고 0개 노출 (모두 unfilled)
- `showTableOfContents = false` → 광고 4개 정상 노출

### 조치
**모든 광고 설정 블로그의 `params.toml`에서 `showTableOfContents = false`로 설정할 것.**

---

## 3. 파일별 설정

### 3-1. config/_default/params.toml

```toml
[article]
  showTableOfContents = false   # ← 반드시 false (광고 렌더링 충돌 방지)

[advertisement]
  adsense      = "ca-pub-6677996696534146"
  inArticleSlot = "2195212287"  # In-article / fluid 슬롯
  topSlot      = "2195212287"  # Display (topSlot) 슬롯
```

### 3-2. layouts/partials/extend-head.html

```html
{{ with site.Params.advertisement.adsense }}
<script async
        src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{ . }}"
        crossorigin="anonymous"></script>
{{ end }}
```

**즉시 로드** (`async`만 사용, lazy-load 없음). `client=` 파라미터로 Publisher ID 전달.

### 3-3. layouts/partials/adsense/top.html (신규)

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

### 3-4. layouts/partials/adsense/in-article.html (재작성)

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
- 각 `ins` 태그 직후 **즉시 `push({})` 호출** (IntersectionObserver lazy-load 불필요)

### 3-5. layouts/_default/single.html override

본문 분할 인젝션 로직 (pick-hugo에서 이식):

```html
<div class="article-content max-w-prose mb-20">
  {{/* ===== pick 로직: 본문 분할 인젝션 ===== */}}
  {{ $content := .Content }}
  {{ $wordCount := .WordCount }}
  {{ $section := .Section }}
  {{ $isHighValue := or (eq $section "cars") (eq $section "finance") }}
  {{ $maxAds := 2 }}
  {{ if or (ge $wordCount 800) $isHighValue }}{{ $maxAds = 3 }}{{ end }}

  {{ $h2parts := split $content "<h2" }}
  {{ if gt (len $h2parts) 1 }}
    {{ range $i, $part := $h2parts }}
      {{ if eq $i 0 }}
        {{ $pParts := split $part "</p>" }}
        {{ if gt (len $pParts) 1 }}
          {{ index $pParts 0 | safeHTML }}</p>
          {{ partial "adsense/in-article.html" . }}
          {{ range $j, $p := $pParts }}{{ if gt $j 0 }}{{ $p | safeHTML }}</p>{{ end }}{{ end }}
        {{ else }}
          {{ $part | safeHTML }}
        {{ end }}
      {{ else }}
        {{ if or (eq $i 1) (and (eq $i 3) (ge $maxAds 3)) }}
          {{ partial "adsense/in-article.html" . }}
        {{ end }}
        {{ printf "<h2%s" $part | safeHTML }}
      {{ end }}
    {{ end }}
  {{ else }}
    {{ $pParts := split $content "</p>" }}
    {{ if gt (len $pParts) 1 }}
      {{ index $pParts 0 | safeHTML }}</p>
      {{ partial "adsense/in-article.html" . }}
      {{ range $j, $p := $pParts }}{{ if gt $j 0 }}{{ $p | safeHTML }}</p>{{ end }}{{ end }}
    {{ else }}
      {{ $content | safeHTML }}
    {{ end }}
  {{ end }}
</div>
```

**단락/H2 분할 인젝션 규칙:**

| 조건 | 광고 개수 | 삽입 위치 |
|------|----------|----------|
| H2 없음 | 2개 | 첫 단락 후 + 두 번째 단락 후 |
| H2 1개 | 2개 | 도입단락 후 + 첫 H2 전 |
| H2 2개 | 2개 | 도입단락 후 + 첫 H2 전 |
| H2 3개 이상 | 3개 | 도입단락 후 + 첫 H2 전 + 3번째 H2 전 |
| 단어수 ≥ 800 또는 고가치 섹션 | 3개 | 상기 규칙 + H2=3일 때 3번째 전 |

### 3-6. layouts/_default/single.html — 헤더 내 광고 배치

```html
<header id="single_header" class="mt-5 max-w-prose">
  {{/* ===== H1 직전 광고 (Display) ===== */}}
  {{ partial "adsense/top.html" . }}

  <h1>{{ .Title }}</h1>
  {{ with .Description }}<p class="lead">{{ . }}</p>{{ end }}

  {{/* ===== lead(설명문) 후 광고 (In-article) ===== */}}
  {{ partial "adsense/in-article.html" . }}
</header>
```

### 3-7. assets/css/custom.css

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

## 4. AdSense 슬롯 설계

### 슬롯 발급 원칙

| 용도 | 슬롯 유형 | 크기 | 관리 |
|------|----------|------|------|
| `topSlot` (타이틀 상단) | Display | 가변 (auto) | AdSense 대시보드에서 Display로 발급 |
| `inArticleSlot` (본문) | In-article / Fluid | 가변 (fluid) | AdSense 대시보드에서 In-article으로 발급 |

**중요**: 동일 슬롯 번호를 두 유형에 재사용하면 광고가 채워지지 않음. 반드시 각각 별도 슬롯으로 발급받을 것.

### 현재 pet-hugo 슬롯 현황

| 슬롯 | 값 | 유형 | 상태 |
|------|---|------|------|
| `topSlot` | `2195212287` | Display | 정상 |
| `inArticleSlot` | `2195212287` | In-article (임시) | 동일 슬롯 — 슬롯 분리 권장 |

---

## 5. 앵커/전면 광고 (Auto Ads)

`extend-head.html`에서 adsbygoogle.js를 head에 즉시 로드하면 AdSense Auto ads가 자동으로 활성화된다. 별도 코딩 불필요.

**앵커광고가 안 보이는 경우:**
1. AdSense 대시보드 → Auto ads → **앵커 활성화** toggle ON 확인
2. `data-ad-format="fluid"` + `data-ad-layout="in-article"` 조합이 Auto ads와 충돌 가능 — 슬롯 분리 후 재확인

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
- [ ] `layouts/_default/single.html` override에 광고 배치 + 분할 인젝션 로직 포함
- [ ] `assets/css/custom.css`에 `.ad-inarticle`, `.ad-top`, `unfilled` 규칙 포함
- [ ] AdSense 대시보드에서 `topSlot` (Display)과 `inArticleSlot` (In-article) **별도 슬롯** 발급
- [ ] Hugo 빌드 정상 확인
- [ ] Worker/Pages 배포 후 광고 실제 노출 확인

---

## 8. 금기사항

1. **`showTableOfContents = true` 금지** — 광고 전체 렌더링 실패
2. **`lazy-load.html` 금지** — 즉시 로드 정책이 Adsense.js가 `<head>`에 있으므로 IntersectionObserver 중복
3. **슬롯 재사용 금지** — Display 슬롯과 In-article 슬롯은 반드시 별도 발급
4. **mobile-sticky.html 사용 금지** — Auto ads 앵커와 충돌