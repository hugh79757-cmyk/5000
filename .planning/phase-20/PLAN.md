# Phase 20: Hugo Build 안정화 — `--minify` 호환성 + badge shortcode 수정

**Goal:** Hugo 0.160.1 환경에서 모든 사이트가 `hugo --gc --minify`로 정상 빌드되어 자동 배포 파이프라인이 항상 성공하도록 한다.

---

## 도메인별 Publisher ID 매핑 (확정)

| Publisher ID | 도메인 | 적용 대상 |
|---|---|---|
| `ca-pub-6677996696534146` | **informationhot.kr** (모든 서브도메인) | CUAP 10개, RAP 5개, SEAP senior-hugo, CAP pick/rank, informationhot-hugo, STAP stock-hugo, kuta-hugo |
| `ca-pub-8772455780561463` | **rotcha.kr** | 5000 메인, rotcha-blog, CAP compare/deal/ev/guide/hotissue/tco, TAP 5개 |
| `ca-pub-8772455780561463` | **techpawz.com** (+ 하위도메인) | techpawz-hugo, STAP dividend/etf/finance/ipo/sector, biz.techpawz, issue.techpawz, info.techpawz |

---

## 이슈 1: `--minify` + `})()` IIFE 충돌 (CUAP 10 / TAP 5)

### 증상
`hugo --gc --minify` 실행 시 baseof.html의 IIFE 끝 `})()`를 Hugo minifier가 Go 템플릿 표현식으로 오인식:
```
unexpected } in expression on line X and column 11
   33:   })();
```
**영향:** CUAP 10개, TAP 5개 사이트 빌드 실패 → `--minify` 없이 수동 배포 필요

### 근본 원인
| 구분 | `--minify` 결과 | JS 위치 | baseof.html 구조 |
|---|---|---|---|
| **RAP/CAP/SEAP/STAP 등 (21개)** | ✅ 성공 | 별도 `lazy-loader.html` partial | 깔끔 (~60줄) |
| **CUAP 10개** | ❌ 실패 | **baseof.html에 인라인** `})()` | 88줄, lines 55-86 |
| **TAP 5개** | ❌ 실패 | **baseof.html에 인라인** `})()` | 97줄, lines 44-81 |

Hugo 0.160.1의 post-processor가 baseof.html에 직접 포함된 `})()`를 Go 템플릿 표현식으로 오해석. JS가 별도 partial 파일에 있으면 동일한 `})()`여도 문제 없음.

### 수정 방안

**안 A: inline JS → 별도 partial로 분리** (권장)
CUAP/TAP baseof.html의 IntersectionObserver JS 블록을 `layouts/partials/adsense/lazy-loader.html`로 분리하고, baseof.html에서는 `{{ partial "adsense/lazy-loader.html" . }}`만 호출.
- 기존 RAP 구조와 동일한 패턴
- Hugo minifier가 partial 파일 내 JS를 정확히 처리
- 단, 각 CUAP/TAP 사이트마다 JS 내용이 약간 다를 수 있어 개별 확인 필요

**안 B: IIFE → named function 변환**
```javascript
// BEFORE
(function() { ... })();
// AFTER
function _initAdLazy() { ... }
_initAdLazy();
```
- sed로 일괄 치환 가능 (최소 변경)
- `})()` 패턴만 제거, JS 로직은 변경 없음
- 단, CUAP/TAP의 JS 구조가 달라서 각각 대응 필요

### 해당 사이트

**CUAP 10개** — `layouts/_default/baseof.html` lines 55-86:
```javascript
(function() {
  if ('IntersectionObserver' in window && typeof adsbygoogle !== 'undefined') {
    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          var ad = entry.target;
          if (ad.getAttribute('data-adsbygoogle-status') !== 'done') {
            (adsbygoogle = window.adsbygoogle || []).push({});
            ad.setAttribute('data-adsbygoogle-status', 'done');
          }
          observer.unobserve(ad);
        }
      });
    }, { rootMargin: '400px 0px', threshold: 0 });
    document.querySelectorAll('ins.adsbygoogle.lazyad').forEach(function(ad) {
      observer.observe(ad);
    });
  }
  var onScroll = function() {
    if (window.scrollY > 600) {
      stickyAd.style.display = 'block';
      var ins = stickyAd.querySelector('ins.adsbygoogle.lazyad');
      if (ins && ins.getAttribute('data-adsbygoogle-status') !== 'done') {
        (adsbygoogle = window.adsbygoogle || []).push({});
        ins.setAttribute('data-adsbygoogle-status', 'done');
      }
      window.removeEventListener('scroll', onScroll);
    }
  };
  window.addEventListener('scroll', onScroll, { passive: true });
})();
```

> ⚠ **참고:** 이 JS는 이미 삭제된 `mobile-sticky-ad` DOM 요소(`stickyAd`)를 참조함 (line 75: `stickyAd.style.display = 'block'`). Phase 19에서 mobile-sticky.html을 삭제했으므로 이 JS 블록은 **사실상 사망 코드(dead code)**. `stickyAd`가 undefined이므로 스크롤 600px 이벤트는 에러만 발생시킴.

**TAP 5개** — `layouts/_default/baseof.html` lines 44-81:
```javascript
(function() {
  if (window.adsbygoogle) {
    var io = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          var el = entry.target;
          if (el.getAttribute('data-adsbygoogle-status')) return;
          try {
            (window.adsbygoogle = window.adsbygoogle || []).push({});
            el.setAttribute('data-adsbygoogle-status', 'done');
          } catch (e) {}
          io.unobserve(el);
        }
      });
    }, { rootMargin: '400px 0px', threshold: 0 });
    document.querySelectorAll('ins.adsbygoogle.lazyad:not([data-adsbygoogle-status])').forEach(function(ins) {
      io.observe(ins);
    });
  }
  window.addEventListener('scroll', function() {
    if (window.scrollY > 600) {
      stickyAd.style.display = 'block';
      if (window.adsbygoogle && !stickyAd.querySelector('ins').getAttribute('data-adsbygoogle-status')) {
        try {
          (window.adsbygoogle = window.adsbygoogle || []).push({});
          stickyAd.querySelector('ins').setAttribute('data-adsbygoogle-status', 'done');
        } catch (e) {}
      }
    }
  }, { passive: true });
})();
```

> ⚠ **참고:** TAP도 동일하게 사망 코드(`stickyAd` 참조) 포함.

### 적용 방안
CUAP/TAP 모두 이미 mobile-sticky가 제거된 상태이므로, 이 JS 블록들도 함께 제거하는 것이 가장 깔끔함:
- IntersectionObserver 로직은 RAP 등 다른 사이트에서 이미 `lazy-loader.html` partial로 처리 중
- `stickyAd` 참조는 dead code이므로 제거해도 기능적 영향 없음
- `--minify` 문제도 자연 해결

---

## 이슈 2: badge shortcode `{{ .Inner }}` 미인식 (travel-hugo)

### 증상
```
shortcode "badge" does not evaluate .Inner or .InnerDeindent, yet a closing tag was provided
```
`{{< badge >}}텍스트{{< /badge >}}` 사용 시 Hugo 0.160.1에서 `.Inner` 인식 실패.

### 근본 원인
`/Users/twinssn/Projects/shared-themes/blowfish/layouts/shortcodes/badge.html`:
```html
<span class="...">{{ .Inner }}</span>
```
Hugo 0.160.1에서 Go 템플릿 `.Inner` 처리 방식 변경으로 인해 미인식. `{{ .Inner }}` 사이에 공백 처리 이슈일 가능성.

### 수정 방안
**`.Inner` → `.InnerDeindent`로 변경** (Hugo v0.125+ 호환)

---

## 실행 순서

### Wave 1: 이슈1 — CUAP/TAP baseof.html 사망 코드 제거
- CUAP 10개: baseof.html lines 54-87 (`<script>` 블록 전체) 제거
- TAP 5개: baseof.html lines 42-82 (`<script>` 블록 전체) 제거
- Mobile-sticky가 이미 제거되었으므로 이 JS는 dead code

### Wave 2: 이슈2 — badge shortcode 수정
- `shared-themes/blowfish/layouts/shortcodes/badge.html`: `{{ .Inner }}` → `{{ .InnerDeindent }}`

### Wave 3: 검증
- CUAP 대표 1개 사이트: `hugo --gc --minify` 빌드 테스트 (exit code 0 확인)
- TAP 대표 1개 사이트: 동일 테스트
- 기존 성공하던 RAP 1개 사이트: regression 확인
- badge shortcode: `{{< badge >}}테스트{{< /badge >}}` 렌더링 테스트

---

## 검증 조건
- [ ] `hugo --gc --minify`가 CUAP에서 exit code 0
- [ ] `hugo --gc --minify`가 TAP에서 exit code 0
- [ ] 기존 성공하던 사이트에 regression 없음
- [ ] badge shortcode 정상 렌더링
- [ ] dispatcher.py `--minify` 옵션 유지 가능 (변경 불필요)
