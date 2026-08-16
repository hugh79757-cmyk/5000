# 블로우피쉬테마 광고설정 가이드

> 최종 갱신: 2026-08-15
> 기반: issue-techpawz-hugo (issue.techpawz.com) — 광고 완벽 노출 검증 완료
> **이 문서가 유일한 표준. 다른 블로그의 광고 설정은 이 가이드를 따를 것.**

---

## 1. 광고 아키텍처 개요 (헤더 2슬롯 + 본문 분할 인젝션)

Blowfish Hugo 블로그의 광고는 **헤더 수동 2개 슬롯** + **본문 H2 분할 인젝션**으로 구성한다.

| 슬롯 | 위치 | `data-ad-format` | `data-ad-layout` | 용도 |
|------|------|------------------|------------------|------|
| **top** | `<header>` 내부, **H1 직전** | `auto` (Display) | — | 타이틀 상단 배너 |
| **in-article** | 본문 H2 분할 인젝션 | `fluid` | `in-article` | 본문 중간 삽입 |

> **본문 중간 광고는 서버사이드 H2 분할로 인젝션한다.** (Auto Ads 위임 아님)
> 단, `extend-head.html`에서 `adsbygoogle.js`를 즉시 로드하여 **앵커/전면 Auto Ads도 활성화**된다.

---

## 2. 핵심 발견: TOC 비활성화 필수

### 원인
Blowfish의 sticky TOC (`showTableOfContents = true`)는 `order-first lg:ms-auto lg:order-last` CSS로 레이아웃을 좌우 이분한다. 이 레이아웃 구조가 AdSense 광고 렌더링과 충돌하여 **모든 광고가 unfilled 상태**로 머무른다.

### 증상
- `showTableOfContents = true` → 광고 0개 노출 (모두 unfilled)
- `showTableOfContents = false` → 광고 정상 노출

### 조치
**모든 광고 설정 블로그의 `params.toml`에서 `showTableOfContents = false`로 설정할 것.**

---

## 3. 파일별 설정

### 3-1. hugo.toml (또는 config/_default/params.toml)

```toml
[params.advertisement]
  adsense       = "ca-pub-XXXXXXXXXXXXXXXX"  # 블로그 계정별 Publisher ID
  inArticleSlot = "XXXXXXXXXX"                # 본문 분할 인젝션 슬롯
  topSlot       = "XXXXXXXXXX"                # H1 위 Display 슬롯
```

> **슬롯 ID는 동일 값을 재사용해도 광고는 정상 노출된다.** (issue: top/in-article 둘 다 `6685009950`)
> 리포팅 분리가 필요하면 별도 슬롯으로 발급받을 것.

---

### 3-2. layouts/partials/extend-head.html (AdSense 즉시 로드)

```html
{{ with site.Params.advertisement.adsense }}
<script async
        src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{ . }}"
        crossorigin="anonymous"></script>
{{ end }}
```

**즉시 로드** (`async`만 사용, lazy-load 없음). `client=` 파라미터로 Publisher ID 전달.
이 한 줄로 **앵커/전면 Auto Ads까지 모두 활성화**된다.

> **금지**: 하드코딩된 Publisher ID 사용 금지. 반드시 `site.Params.advertisement.adsense` 사용.

---

### 3-3. layouts/partials/extend_head.html (GA4 + 모바일 보정)

> underscore(`_`) 버전은 Blowfish가 **로드하지 않는다** (DEAD/legacy). GA4 + 모바일 보정 CSS는 `extend-head.html`(hyphen)에 함께 둔다.

```html
<!-- GA4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>

<style>
/* ── 모바일 UI/UX 보정 ── */
@media (max-width: 767px) {
  /* 광고 컨테이너 오버플로 방지 */
  .ad-inarticle, .ad-leaderboard, .ad-top {
    overflow: hidden !important;
    max-width: 100% !important;
  }
  .ad-inarticle ins, .ad-leaderboard ins, .ad-top ins {
    max-width: 100% !important;
    height: auto !important;
  }
  /* unfilled 광고 공간 제거 */
  ins.adsbygoogle[data-ad-status="unfilled"] {
    min-height: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    display: none !important;
  }
}
</style>
```

> **Blowfish는 `extend-head.html`(hyphen) 하나만 로드한다** (`layouts/partials/head.html`의 `partialCached "extend-head.html"`).
> `extend_head.html`(underscore)은 **로드되지 않는다(DEAD)** — 생성하지 말 것. GA4 + 모바일 보정 CSS는 `extend-head.html` 안에 함께 둔다.

---

### 3-4. layouts/partials/adsense/top.html (H1 직전 — Display 슬롯)

```html
<div style="overflow:hidden;min-height:100px;">
<div class="ad-top not-prose my-4">
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="{{ site.Params.advertisement.adsense }}"
     data-ad-slot="{{ site.Params.advertisement.topSlot }}"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
</div>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>
```

- `data-ad-format="auto"` — Display 광고 (타이틀 상단)
- `not-prose` — Blowfish prose 스타일 비활성화
- 바깥 `<div style="overflow:hidden;min-height:100px;">` — CLS 방지 래퍼
- `<script>`는 안쪽 `<div>` **바깥** (div 닫은 후 push 호출)

---

### 3-5. layouts/partials/adsense/in-article.html (본문 분할 인젝션 슬롯)

```html
<div class="ad-inarticle not-prose my-8" style="overflow:hidden;max-width:100%;min-height:100px">
<ins class="adsbygoogle"
     style="display:block; text-align:center;"
     data-ad-layout="in-article"
     data-ad-format="fluid"
     data-ad-client="{{ site.Params.advertisement.adsense }}"
     data-ad-slot="{{ site.Params.advertisement.inArticleSlot }}"></ins>
</div>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
```

- `data-ad-format="fluid"` + `data-ad-layout="in-article"` — AdSense가 본문 맞춤형 광고 자동 선택
- `my-8` — top 슬롯(`my-4`)보다 상하 마진 넓음
- `text-align:center` — 인라인 스타일로 중앙 정렬
- `<script>`는 `<div>` **바깥** (div 닫은 후 push 호출)
- 본문 분할 인젝션에서 동일 태그가 2~3회 반복 삽입됨

---

### 3-6. layouts/_default/single.html — 헤더 2슬롯 + 본문 H2 분할 인젝션

```html
{{ define "main" }}
  {{ .Scratch.Set "scope" "single" }}
  <article>
    {{/* Header */}}
    <header id="single_header" class="mt-5 max-w-prose">
      {{ if .Params.showBreadcrumbs | default (site.Params.article.showBreadcrumbs | default false) }}
        {{ partial "breadcrumbs.html" . }}
      {{ end }}
      {{ partial "adsense/top.html" . }}
      <h1 class="mt-0 text-4xl font-extrabold text-neutral-900 dark:text-neutral">
        {{ .Title | emojify }}
      </h1>
      <div class="mt-1 mb-6 text-base text-neutral-500 dark:text-neutral-400 print:hidden">
        {{ partial "article-meta/basic.html" (dict "context" . "scope" "single") }}
      </div>
      {{ if not (.Params.showAuthorBottom | default (site.Params.article.showAuthorBottom | default false)) }}
        {{ template "SingleAuthor" . }}
      {{ end }}
    </header>

    {{/* Body — 본문 분할 인젝션 */}}
    <section class="flex flex-col max-w-full mt-0 prose dark:prose-invert lg:flex-row">
      <div class="min-w-0 min-h-0 max-w-fit">
        {{ partial "series/series.html" . }}
        <div class="article-content max-w-prose mb-20">

          {{ $content := .Content }}
          {{ $wordCount := .WordCount }}
          {{ $maxAds := 2 }}
          {{ if ge $wordCount 800 }}{{ $maxAds = 3 }}{{ end }}

          {{ $h2parts := split $content "<h2" }}
          {{ if gt (len $h2parts) 1 }}
            {{ range $i, $part := $h2parts }}
              {{ if eq $i 0 }}
                {{ $pParts := split $part "</p>" }}
                {{ if gt (len $pParts) 1 }}
                  {{ index $pParts 0 | safeHTML }}</p>
                  {{ partial "adsense/in-article.html" $ }}
                  {{ range $j, $p := $pParts }}{{ if gt $j 0 }}{{ $p | safeHTML }}</p>{{ end }}{{ end }}
                {{ else }}
                  {{ $part | safeHTML }}
                {{ end }}
              {{ else }}
                {{ if or (eq $i 1) (and (eq $i 3) (ge $maxAds 3)) }}
                  {{ partial "adsense/in-article.html" $ }}
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
      </div>
    </section>
  </article>
{{ end }}
```

**인젝션 규칙:**
| 조건 | in-article 삽입 횟수 | 위치 |
|------|---------------------|------|
| H2 있음, 800자 미만 | 2회 | 첫 본문 + 1번째 H2 뒤 |
| H2 있음, 800자 이상 | 3회 | 첫 본문 + 1번째 H2 뒤 + 3번째 H2 뒤 |
| H2 없음 | 1회 | 첫 `</p>` 위치 |

---

### 3-7. layouts/_default/baseof.html — 커스텀 오버라이드 불필요

**커스텀 baseof.html을 만들지 않는다.** 테마 기본을 그대로 사용한다.

---

### 3-8. assets/css/custom.css — 광고 + 확장 스타일

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

| 용도 | 슬롯 유형 | 발급 위치 |
|------|----------|----------|
| `topSlot` (타이틀 상단) | **Display** | AdSense 대시보드 → 광고 단위 → **디스플레이 광고** |
| `inArticleSlot` (본문 분할) | **Display** | AdSense 대시보드 → 광고 단위 → **디스플레이 광고** |

> **동일 슬롯 ID 재사용 허용.** (issue: top/in-article 둘 다 `6685009950`)
> 광고는 정상 노출됨. 리포팅 분리가 필요하면 별도 발급.

---

## 5. 본문 분할 인젝션 로직 상세

### 5-1. H2가 있는 글

```
┌─ [H1 직전: top 광고]
│  H1 (제목)
│  article-meta
│  ─── 본문 시작 ───
│  <p>첫 번째 문단...</p>
│  [첫 </p> 뒤: in-article 광고]  ← 1번째 삽입
│  <p>이 문단부터...</p>
│  <h2>첫 번째 소제목</h2>
│  [첫 번째 H2 뒤: in-article 광고]  ← 2번째 삽입
│  <p>내용...</p>
│  <h2>두 번째 소제목</h2>
│  <p>내용...</p>
│  <h2>세 번째 소제목</h2>         ← 800자 이상일 때만 in-article 광고 삽입
│  [세 번째 H2 뒤: in-article 광고]  ← 3번째 삽입
│  <p>내용...</p>
└─ 끝
```

### 5-2. H2가 없는 글

```
┌─ [H1 직전: top 광고]
│  H1 (제목)
│  article-meta
│  ─── 본문 시작 ───
│  <p>첫 문단...</p>
│  [첫 </p> 뒤: in-article 광고]  ← 1회만 삽입
│  <p>나머지...</p>
└─ 끝
```

---

## 6. CLS 방지 체계

| 위치 | 수단 | 상세 |
|------|------|------|
| HTML 인라인 | `style="overflow:hidden;min-height:100px"` | top 컨테이너 래퍼 |
| HTML 인라인 | `style="overflow:hidden;max-width:100%;min-height:100px"` | in-article 컨테이너 |
| CSS | `.ad-top, .ad-inarticle { min-height: 250px }` | PC 대기 높이 |
| CSS 모바일 | `@media (max-width:767px) { min-height: 200px }` | 모바일 대기 높이 |
| CSS unfilled | `ins[data-ad-status="unfilled"] { display:none }` | 미노출 시 공간 제거 |
| extend_head.html | `@media (max-width:767px) { overflow:hidden }` | 모바일 오버플로 방어 |

---

## 7. 체크리스트 — 신규 블로그 적용 시

- [ ] `hugo.toml`: `showTableOfContents = false` 설정
- [ ] `hugo.toml`: `[params.advertisement]` 섹션에 `adsense`, `inArticleSlot`, `topSlot` 정의
- [ ] `layouts/partials/extend-head.html` 생성 (adsbygoogle.js 즉시 로드)
- [ ] `extend_head.html`(underscore)은 **생성 금지** — Blowfish가 로드하지 않음(DEAD). GA4 + 모바일 보정 CSS는 `extend-head.html`(hyphen)에 포함
- [ ] `layouts/partials/adsense/top.html` 생성 (바깥 래퍼 div + div 밖 push)
- [ ] `layouts/partials/adsense/in-article.html` 생성 (fluid+in-article + div 밖 push)
- [ ] `layouts/_default/single.html` 오버라이드 (헤더 `top.html` 단일 광고 + 본문 H2 분할 인젝션)
- [ ] `layouts/_default/baseof.html` — **오버라이드하지 않음** (테마 기본 사용)
- [ ] `assets/css/custom.css`에 `.ad-inarticle`, `.ad-top`, `unfilled`, 다크모드 규칙 포함
- [ ] Hugo 빌드 정상 확인
- [ ] 배포 후 광고 노출 확인 (H1 위 + 본문 중간)
- [ ] freshness 판정 실데이터 확인 (publish_ledger 실시간 재계산으로 pass — 캐시 스테일 아님)

---

## 8. 금기사항

1. **`showTableOfContents = true` 금지** — 광고 전체 렌더링 실패
2. **레이지 로드 금지** — adsbygoogle.js는 `<head>`에서 async 즉시 로드
3. **mobile-sticky.html 사용 금지** — 앵커 광고와 충돌
4. **in-article에 `data-ad-format="auto"` 사용 금지** — `data-ad-format="fluid"` + `data-ad-layout="in-article"` 사용
5. **`<script>push({})`를 `<div>` 내부에 넣지 말 것** — div 밖에서 push 호출
6. **숨김 placeholder div (`display:none`) 사용 금지** — 항상 표준 `<ins>` 태그 사용
7. **JS로 placeholder를 이동하는 로직 사용 금지** — 서버사이드 H2 분할로 인젝션
8. **Description(lead) 사용 금지** — 광고 레이아웃 방해, 글 잘림 유발
9. **baseof.html 커스텀 오버라이드 금지** — 테마 기본 사용
10. **extend-head.html에 하드코딩된 Publisher ID 금지** — 반드시 `site.Params` 사용
11. **`leaderboardSlot` 등 비표준 키명 금지** — `topSlot`/`inArticleSlot` 단일화 (pet-hugo 파일럿, R02 기준)
12. **single.html 헤더 내 2번째 in-article 광고·dead TOC 마크업 잔존 금지** — 헤더는 `top.html` 단일, in-article은 본문 H2 분할에서만

---

## 9. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 광고 전체 unfilled | `showTableOfContents = true` | `false`로 변경 |
| top 광고 안 나옴 | `topSlot` 파라미터 미정의 | hugo.toml에 `topSlot` 추가 |
| 본문 중간 광고 없음 | single.html에 H2 분할 로직 없음 | H2 split 인젝션 로직 추가 |
| 모바일 광고 오버플로 | `overflow:hidden` 미적용 | extend_head.html 모바일 CSS 추가 |
| 제목 아래 문단이 잘림 | Description(lead) 사용 중 | single.html에서 lead 라인 제거 |
| 테마 업그레이드 후 광고 깨짐 | 커스텀 baseof.html 잔존 | baseof.html 삭제, 테마 기본 사용 |
| in-article 광고 포맷 이상 | `data-ad-format="auto"` 사용 중 | `fluid` + `in-article`로 변경 |

---

## 10. params.toml 표준값 (사이트 표시 파라미터 — 단일 기준)

> **이 절은 대표 승인 표준값의 유일한 기준(단일 기준)이다.** 모든 블로그의 `hugo.toml`/`params.toml` 사이트 표시 파라미터와 광고 슬롯 키명은 아래 값을 참조한다. downstream 규칙(ops_dashboard RULES/preflight)이 이 값을 검증 기준으로 쓴다.

### 10-1. 사이트 표시 파라미터 (`hugo.toml` → `[params]`)

| 파라미터 | 표준값 | 의미 | 근거 |
|----------|--------|------|------|
| `showTableOfContents` | `false` | 목차 비활성화 (광고 전체 렌더링 실패 방지) | §1, §8 금기#1 |
| `showDate` | `true` | 발행일자 **표시** | 대표 지시 (2026-08-15) |
| `showWordCount` | `false` | 단어수 **숨김** | 대표 지시 (2026-08-15) |
| `showReadingTime` | `false` | 읽기시간 **숨김** | 대표 지시 (2026-08-15) |

### 10-2. 광고 슬롯 키명 표준 (`[params.advertisement]`)

`hugo.toml`의 `[params.advertisement]` 섹션은 다음 키명을 단일 기준으로 사용한다.

| 키 | 용도 | 참조 파셜 |
|----|------|----------|
| `adsense` | Publisher ID (`ca-pub-...`, 사이트 계열 매핑 기준) | extend-head.html, adsense/top.html, adsense/in-article.html |
| `topSlot` | 타이틀 상단 Display 광고 슬롯 ID | adsense/top.html |
| `inArticleSlot` | 본문 H2 분할 인젝션 슬롯 ID | adsense/in-article.html |

> **금지**: `leaderboardSlot` 등 `topSlot`/`inArticleSlot` 외 키명으로 광고 슬롯을 정의하지 말 것. R02 검사는 `topSlot`/`inArticleSlot` 존재를 기준으로 한다. 단일 키명을 유지해야 downstream 검증(ops_dashboard R02)과 일치한다.

---

## 10-3. 대표 확정 5건 (2026-08-15)

> **[대표 확정]** 라벨이 붙은 값은 대표 승인 기준으로, 기존 §3-1·§10-1과 함께 단일 기준으로 취급한다.
> downstream 규칙(ops_dashboard RULES/preflight) 및 신규 블로그 매핑은 이 값들을 표준으로 따른다.

### ① 날짜 표시 포맷 — 한국식 "2026년 8월 10일"

**[대표 확정]** 날짜는 한국식 `YYYY년 M월 D일` 포맷을 사용한다.

`config/_default/languages.ko.toml` (`[languages.ko]`):

```toml
dateFormat = "2006년 1월 2일"
```

- 실제 렌더 결과: `2026년 8월 10일` (pet.informationhot.kr 포스트 화면 확인, HTTP 200)
- `showDate = true`와 결합하여 발행일을 한국식으로 표시한다.

### ② 읽기시간 삭제 — showReadingTime = false

**[대표 확정]** 읽기시간 표시를 비활성화한다. 광고 레이아웃과 글몫 표시를 깔끔하게 유지하기 위함.

`hugo.toml` `[params.article]` (또는 config/_default/params.toml):

```toml
showReadingTime = false
```

### ③ 단어수 삭제 — showWordCount = false

**[대표 확정]** 단어수 표시를 비활성화한다. (pet-hugo 기준값과 일치)

```toml
showWordCount = false
```

### ④ 히어로 이미지 — object-fit: contain (여백 허용, 전체 이미지 표시)

**[대표 확정]** 히어로(featured) 이미지는 `object-fit: contain`으로 렌더링한다.
이미지 원본 비율을 유지하면서 전체 이미지가 잘리지 않도록 하고, 남는 여백은 허용한다.
(crop/cover로 이미지 일부를 잘라내지 않음)

```css
/* 히어로 이미지 전용 — 전체 이미지 표시, 잘림 금지 */
.hero img,
.article-hero img {
  object-fit: contain;
}
```

### ⑤ 라이트/다크 토글 + pet 방식 글목록

**[대표 확정]** 라이트/다크 토글을 활성화하고, 글목록은 pet 방식을 채택한다.

- **라이트/다크 토글**: `defaultAppearance`와 토글 UI를 통해 사용자가 테마를 전환할 수 있다.
  (pet-hugo `config/_default/params.toml:4-7`: `defaultAppearance = "light"`, `autoSwitchAppearance = false` 기본값 + 토글 노출)
- **pet 방식 글목록**(`[list]`): `showCards = true` 카드형 목록을 기본으로 한다.

```toml
[list]
  showBreadcrumbs = true
  showSummary = true
  showCards = true
  groupByYear = false
```

> pet 방식 = 카드형(`showCards=true`) 목록 + 요약(`showSummary=true`). 신규 블로그 글목록은 이 구성을 따른다.

---

### ⑥ pet-hugo 파일럿 확정 규격 (2026-08-15)

**[대표 확정]** pet-hugo(pet.informationhot.kr) 파일럿 활성화로 검증된 규격. 신규·복제 블로그는 아래를 기준으로 한다.

**[대표 확정] topSlot 키명 단일화 — leaderboardSlot 폐기**
- 광고 슬롯 키명은 `topSlot`(H1 직전 Display), `inArticleSlot`(본문 분할) **두 가지만** 사용한다.
- `leaderboardSlot` 등 그 외 키명은 **사용 금지(폐기)** — R02 검사가 `topSlot`/`inArticleSlot` 존재만 기준으로 하므로, 다른 키명은 nil 바인딩 → 총 0슬롯 렌더 실패.
- 파일럿 전 pet-hugo `top.html`에 `leaderboardSlot`(undefined→nil)이 남아있어 광고가 0슬롯 렌더됐고, `topSlot`으로 교체 후 3슬롯 정상 렌더 확인.

**[대표 확정] single.html 헤더: 광고는 `top.html` 단일 + dead TOC 제거**
- 헤더(`<header id="single_header">`) 광고는 **`adsense/top.html` 1개만** 유지한다.
  - 파일럿 전 헤더 내 2번째 in-article 광고 + 미사용 TOC(목차) 마크업이 존재해 레이아웃 오염 → `single.html`에서 제거.
  - 지침: 본문 H2 분할 인젝션용 `in-article.html`은 헤더가 아니라 **본문 `.article-content` 내부**에서만 호출한다.
- dead TOC(렌더되지 않는 목차 마크업)는 제거한다 (`showTableOfContents = false`와 별개로, 마크업 자체도 남기지 않는다).
- `single.html` 참조 위치: `layouts/_default/single.html` — `{{ partial "adsense/top.html" . }}`는 `<h1>` 직전, 본문 H2 분할 인젝션은 위치 그대로 유지.

**[대표 확정] freshness 판정은 실데이터(발행 ledger) 재계산 기준**
- freshness(최근 발행 갱신)는 `content.db publish_ledger`의 `MAX(created_at)`을 **체크 호출 시점에 실시간 재계산**한다 — 대시보드에 캐시된 `days_since_last_publish` 값을 그대로 신뢰하지 않는다.
- 판정 근거: `Last publish {n}d ago (threshold: {m}d for {brand}) [live, cached={old}]` 형태로 라이브 값이 정확히 표기된다.
- fresh = 실제 발행이 n일 전임을 실데이터로 검증한 것이며, 허위 fail(캐시 스테일)이 아닌지가 표준 판정의 핵심. pet-hugo 활성화 후 실발행(0d) 기준 pass 확인.

> **확정 요약**: pet-hugo 파일럿이 검증한 표준 = `topSlot` 단일 키명(leaderboardSlot 폐기) + 헤더 `top.html` 단일 광고 + dead TOC 제거 + freshness 실데이터 재계산. 신규/복제 블로그는 이 규격 기준으로 적용한다.

---

> **요약**: issue-techpawz-hugo가 광고 완벽 노출 검증을 마친 유일한 표준. 헤더 2슬롯 + 본문 H2 분할 인젝션 + `showTableOfContents = false` + adsbygoogle.js 즉시 로드 + `fluid`+`in-article` 포맷이 핵심. (2026-08-15 pet-hugo 파일럿으로 `topSlot` 키명 단일화·헤더 단일 광고·freshness 실데이터 재계산이 추가 확정됨 — §⑥ 참조.)

---

**관련 문서**:
- `/Users/twinssn/Projects/5000/Blowfish-Hugo-테마-업그레이드-표준-지침서.md` — 테마 업그레이드 표준
- `5000/ADSENSE-GUIDE.md` — 이 문서
