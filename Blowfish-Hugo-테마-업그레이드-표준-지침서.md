# Blowfish Hugo 테마 업그레이드 표준 지침서 v1.3

> **작성일**: 2026-07-28
> **최종 갱신**: 2026-08-15
> **기반**: issue-techpawz-hugo (issue.techpawz.com) — 광고 완벽 노출 검증 완료
> **적용 대상**: 모든 Blowfish 테마 사용 Hugo 블로그

---

## 1. 핵심 원칙

> **"테마 기본 파일을 건드리지 마라. 오버라이드만 최소한으로 하라."**

| 오버라이드 허용 파일 | 목적 |
|---------------------|------|
| `layouts/_default/single.html` | 본문 H2 분할 인젝션, 헤더 2슬롯 광고 |
| `layouts/partials/extend-head.html` | AdSense `adsbygoogle.js` 즉시 로드 |
| `layouts/partials/extend_head.html` | GA4 추적, 모바일 보정 CSS |
| `layouts/partials/adsense/*.html` | 광고 슬롯 파셜 (top, in-article) |
| `assets/css/custom.css` | CLS 방지, 광고 미노출 시 공간 제거, 다크모드 보정 |

**절대 건드리지 말 것**: `baseof.html`, `list.html`, `hero/*.html`, `home/*.html`

> **baseof.html은 테마 기본을 그대로 사용한다.** 커스텀 오버라이드 불필요.
> BuyMeACoffee 위젯은 `buymeacoffee.globalWidget = false`(기본)이므로 표시되지 않음.

---

## 2. Blowfish v2.104.0+ 업그레이드 시 필수 체크리스트

### 2.1 `layouts/index.html` - 홈페이지 파손 방지
**문제**: 테마 업데이트 후 `{{ define "main" }}` 내부에서 잘못된 플레이스홀더 사용 시 홈페이지가 단일 글 페이지로 렌더링됨.

**해결**: 테마 기본 `index.html` 복원
```html
{{ define "main" }}
  {{ $partial := print "home/" .Site.Params.homepage.layout ".html" }}
  {{ if templates.Exists ( printf "partials/%s" $partial ) }}
    {{ partial $partial . }}
  {{ else }}
    {{ partial "home/profile.html" . }}
  {{ end }}
{{ end }}
```

### 2.2 `layouts/_default/single.html` - `prose` 래퍼 필수 유지
**문제**: 커스텀 single.html에서 `<section class="prose dark:prose-invert">` 래퍼 제거 시 H2~H6, p, ul, ol 등 타이포그래피 스타일 미적용.

**해결**: 테마 기본 구조 유지하며 본문 분할 인젝션 + 광고만 주입

### 2.3 Description(lead) 제거
**문제**: 제목 아래 디스크립션 문단이 글 잘림 현상 유발, 광고 레이아웃 방해.

**해결**: `{{ with .Description }}<p class="lead">{{ . }}</p>{{ end }}` 라인 제거

---

## 3. 광고 설정 표준

### 3.1 `hugo.toml` 필수 설정

```toml
[params]
[params.article]
  showTableOfContents = false  # 필수: TOC 켜면 광고 렌더링 실패

[params.advertisement]
  adsense = "ca-pub-XXXXXXXXXXXXXXXX"  # 블로그 계정별 Publisher ID
  topSlot = "XXXXXXXXXX"                # H1 위 Display 슬롯
  inArticleSlot = "XXXXXXXXXX"          # 본문 분할 인젝션 슬롯

[params.customCSS]
  css = ["css/custom.css"]
```

> **슬롯 ID는 동일 값을 재사용해도 광고는 정상 노출된다.**
> 리포팅 분리가 필요하면 별도 슬롯으로 발급받을 것.

---

### 3.2 `layouts/partials/extend-head.html` (AdSense 즉시 로드)

```html
{{ with site.Params.advertisement.adsense }}
<script async
        src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{ . }}"
        crossorigin="anonymous"></script>
{{ end }}
```

**즉시 로드** (`async`만 사용, lazy-load 없음). 이 한 줄로 **앵커/전면 Auto Ads까지 모두 활성화**된다.

> **금지**: JS로 placeholder를 이동하는 로직 포함 금지. 본문 인젝션은 서버사이드에서 처리.

---

### 3.3 `layouts/partials/extend_head.html` (GA4 + 모바일 보정)

> underscore(`_`) 버전. hyphen(`-`) 버전과 **별도 파일**로 존재. Blowfish가 둘 다 로드한다.

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

---

### 3.4 `layouts/partials/adsense/top.html` (H1 직전 — Display 슬롯)

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

### 3.5 `layouts/partials/adsense/in-article.html` (본문 분할 인젝션 슬롯)

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
- 본문 분할 인젝션에서 동일 태그가 2~3회 반복 삽입됨

> **금지**: 숨김 placeholder div (`display:none`) 사용 금지. 항상 표준 `<ins>` 태그 사용.

---

### 3.6 `layouts/_default/single.html` — 헤더 2슬롯 + 본문 H2 분할 인젝션

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

### 3.7 `layouts/_default/baseof.html` — 테마 기본 사용 (오버라이드 불필요)

**커스텀 baseof.html을 만들지 않는다.** 테마 기본을 그대로 사용한다.

테마 기본 baseof.html에 포함된 BuyMeACoffee 위젯은 `buymeacoffee.globalWidget = false`(기본값)이므로 표시되지 않는다.

> **이전 오류**: baseof.html을 커스텀하여 BuyMeACoffee를 제거하려 했으나,
> 테마 업그레이드 시마다 커스텀 baseof.html을 유지하기 어렵고,
> BuyMeACoffee는 조건부 렌더링이므로 문제 없음.

---

### 3.8 `assets/css/custom.css`

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
| HTML 인라인 | `style="overflow:hidden;min-height:100px"` | top/in-article 컨테이너 |
| CSS | `.ad-top, .ad-inarticle { min-height: 250px }` | PC 대기 높이 |
| CSS 모바일 | `@media (max-width:767px) { min-height: 200px }` | 모바일 대기 높이 |
| CSS unfilled | `ins[data-ad-status="unfilled"] { display:none }` | 미노출 시 공간 제거 |
| extend_head.html | `@media (max-width:767px) { overflow:hidden }` | 모바일 오버플로 방어 |

---

## 7. 체크리스트 — 신규 블로그 적용 시

- [ ] `hugo.toml`: `showTableOfContents = false` 설정
- [ ] `hugo.toml`: `[params.advertisement]` 섹션에 `adsense`, `topSlot`, `inArticleSlot` 정의
- [ ] `layouts/partials/extend-head.html` 생성 (adsbygoogle.js 즉시 로드, JS 로직 없음)
- [ ] `layouts/partials/extend_head.html` 생성 (GA4 + 모바일 보정 CSS)
- [ ] `layouts/partials/adsense/top.html` 생성 (인라인 min-height + div 밖 push)
- [ ] `layouts/partials/adsense/in-article.html` 생성 (표준 ins 태그 + div 밖 push)
- [ ] `layouts/_default/single.html` 오버라이드 (헤더 2슬롯 + 본문 H2 분할 인젝션 + Description 제거)
- [ ] `layouts/_default/baseof.html` — **오버라이드하지 않음** (테마 기본 사용)
- [ ] `assets/css/custom.css`에 `.ad-inarticle`, `.ad-top`, `unfilled`, 다크모드 규칙 포함
- [ ] Hugo 빌드 정상 확인
- [ ] 배포 후 광고 노출 확인 (H1 위 + 본문 중간)

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
11. **`leaderboardSlot` 등 비표준 키명 금지** — 광고 슬롯 키명은 `topSlot`/`inArticleSlot` 단일화. 다른 키명은 nil 바인딩 → 0슬롯 렌더 실패 (pet-hugo 파일럿 확인, 2026-08-15)
12. **single.html 헤더 내 2번째 in-article 광고·dead TOC 마크업 잔존 금지** — 헤더 광고는 `top.html` 단일, in-article은 본문 H2 분할 인젝션에서만 호출 (pet-hugo 파일럿 확인)

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

---

## 10. 버전 이력

| 버전 | 날짜 | 변경 사항 |
|------|------|----------|
| 1.0 | 2026-07-28 | 최초 작성 (techpawz-hugo 수정 경험 기반) |
| 1.1 | 2026-07-28 | techpawz-hugo + pet-hugo 검증 기반 전면 개정 — Description 제거, baseof.html 커스텀 금지, JS placeholder 로직 금지, 서버사이드 H2 분할 인젝션 표준화 |
| 1.2 | 2026-07-30 | issue-techpawz-hugo 기준으로 갱신 — in-article 포맷을 `fluid`+`in-article`으로 변경, top.html 래퍼 div 추가, 하드코딩 금지 명시 |
| 1.3 | 2026-08-15 | ADSENSE-GUIDE 기준으로 정정 — §8 금기#4를 `fluid`+`in-article`(auto 금지)으로 수정, 금기#10(extend-head 하드코딩 Publisher ID 금지) 명시 추가 |
| 1.4 | 2026-08-15 | pet-hugo 파일럿 확정 규격 반영 — §8 금기#11(`leaderboardSlot` 등 비표준 키명 금지), #12(헤더 내 2번째 in-article·dead TOC 잔존 금지) 추가. freshness 판정은 실데이터(publish_ledger 재계산) 기준, 캐시 미신뢰 |

---

**관련 문서**:
- `/Users/twinssn/Projects/5000/ADSENSE-GUIDE.md` — 광고 슬롯 상세 가이드 (issue-techpawz-hugo 기반)
- `5000/Blowfish-Hugo-테마-업그레이드-표준-지침서.md` — 이 문서
