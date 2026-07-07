# Phase 10-05 Research: AdSense 수동광고 구조 개선

## 1. Hugo 사이트 구조

### 대상 사이트 (5개 Hugo)
| 사이트 | baseURL | config 경로 |
|--------|---------|-------------|
| travel-hugo | tour1.rotcha.kr | config/_default/hugo.toml, params.toml |
| travel1-hugo | travel1.rotcha.kr | config/_default/hugo.toml, params.toml |
| travel2-hugo | travel2.rotcha.kr | config/_default/hugo.toml, params.toml |
| travel3-hugo | tour2.rotcha.kr | config/_default/hugo.toml, params.toml |
| travel4-hugo | tour3.rotcha.kr | config/_default/hugo.toml, params.toml |

### Hugo 버전
`hugo v0.160.1+extended+withdeploy darwin/arm64`
→ `replace` 함수의 네 번째 인자(count) 지원 (0.111+ 필요 충족)

### 테마
Blowfish (`/Users/twinssn/Projects/shared-themes/blowfish`)
- 모든 사이트가 동일한 shared theme 사용
- 사이트별 layouts 디렉토리에서 오버라이드

## 2. 현재 AdSense 구현

### 2.1 adsbygoogle.js 로드
**파일**: `layouts/partials/extend-head.html` (모든 사이트 동일)
```html
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8772455780561463"
     crossorigin="anonymous"></script>
```
- `<head>` 내 로드
- Publisher ID: `ca-pub-8772455780561463` (5개 사이트 모두 동일)
- Blowfish 테마의 `[params] advertisement.adsense` 미사용 (수동 주입)

### 2.2 In-article 광고 (현재)
**파일**: `layouts/_default/single.html` (5개 사이트 모두 동일)
```go
{{ $content := .Content }}
{{ $parts := split $content "<h2" }}
{{ if gt (len $parts) 1 }}
  {{ range $i, $part := $parts }}
    {{ if eq $i 0 }}
      {{ $part | safeHTML }}
    {{ else }}
      {{ if or (eq $i 2) (eq $i 4) }}
        <div class="ad-in-article" style="margin:2em 0;text-align:center;">
          <ins class="adsbygoogle"
               style="display:block; text-align:center;"
               data-ad-layout="in-article"
               data-ad-format="fluid"
               data-ad-client="ca-pub-8772455780561463"
               data-ad-slot="3892531241"></ins>
          <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
        </div>
      {{ end }}
      {{ printf "<h2%s" $part | safeHTML }}
    {{ end }}
  {{ end }}
{{ else }}
  {{ .Content }}
{{ end }}
```

**현재 문제점:**
1. `split "<h2"` 방식 → HTML 태그 잘림 가능
2. 단일 슬롯 `3892531241` 하드코딩
3. push 스크립트 inline 포함 (즉시 실행)
4. 조건부 배치 없음 (모든 글에 동일)
5. min-width 미설정

### 2.3 baseof.html
**파일**: `/Users/twinssn/Projects/shared-themes/blowfish/layouts/_default/baseof.html`
- `</body>`: line 40
- 광고 관련 코드 없음
- `extend-footer.html` hook 존재하나 TAP 사이트에서 미사용

### 2.4 custom.css
**파일**: `assets/css/custom.css` (125줄)
- 광고 관련 스타일 없음
- `.ad-in-article` 인라인 스타일만 사용

## 3. 다크모드 전략

### 메커니즘
- `.dark` class on `<html>` element (Tailwind CSS convention)
- `appearance.js`에서 `classList.add("dark")` / `classList.remove("dark")`
- `localStorage` key `"appearance"`로 유지
- Tailwind `dark:` prefix 사용

### 광고 관련 다크모드
- 현재 광고에 다크모드 대응 없음
- `html.dark ins.adsbygoogle { background: #fff !important; }` 필요

## 4. config 구조

### hugo.toml
```toml
# [params] 섹션 없음 (adsense 설정 없음)
```

### params.toml
```toml
defaultAppearance = "light"
autoSwitchAppearance = false
# [advertisement] 섹션 없음
```

### Blowfish 테마 지원
```toml
# 테마 기본 params.toml에 지원되나 미사용:
[advertisement]
  adsense = "ca-pub-XXXXX"
```

## 5. 콘텐츠 구조

### 섹션별 카테고리
- travel-hugo: camping (일반)
- travel1-hugo: festival (일반)
- travel2-hugo: heritage (일반)
- travel3-hugo: food (일반)
- travel4-hugo: course (일반)

### 고단가 카테고리 후보
사용자 요청: cars, finance, insurance, crypto, loans, health
→ 현재 TAP 사이트에는 해당 없음. 향후 확장 대비로 분기 로직만 준비.

### WordCount 분기
- < 800: 본문 중간 광고 0개 (리더보드 + 모바일스티키만)
- >= 800 + 고단가 섹션: in-article 3개
- >= 800 + 일반: in-article 2개

## 6. 파일 구조 (현재)

```
travel-hugo/
├── config/_default/
│   ├── hugo.toml
│   └── params.toml
├── layouts/
│   ├── _default/
│   │   ├── baseof.html      (오버라이드 없음 → 테마 사용)
│   │   └── single.html      (인라인 광고 코드)
│   └── partials/
│       ├── extend-head.html  (adsbygoogle.js 로드)
│       └── extend_head.html  (중복?)
└── assets/css/custom.css     (125줄, 광고 없음)
```

## 7. 구현 시 고려사항

### shared-themes 접근
- 5개 사이트가 `/Users/twinssn/Projects/shared-themes/blowfish`를 공유
- 테마 수정 시 5개 사이트 모두 영향
- **권장**: 사이트별 layouts에서 오버라이드 (기존 패턴 유지)

### 광고 슬롯 ID
- In-article: `3892531241` (기존 그대로)
- Leaderboard: 새 슬롯 필요 → `params.toml`에 정의
- Mobile sticky: 새 슬롯 필요 → `params.toml`에 정의

### IntersectionObserver
- 글로벌 스크립트 1개만 `baseof.html`에 배치
- 자동광고와 충돌 방지: `data-adsbygoogle-status` 속성 체크
- `rootMargin: "400px 0px"`로 미리 로드

### push 스크립트
- 파셜에는 절대 넣지 않음
- 글로벌 observer에서만 push 수행
