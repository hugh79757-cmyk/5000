# Phase 31 — rotcha-adsense-standard

**Goal:** AdSense 표준화 (pet-hugo 검증 표준) → rotcha.kr 계열 (Pub 8772) 6개 블로그 적용

**Mode:** discovery-first (research 완료 — 2026-07-22)

## Context

Phase 30으로 informationhot.kr 계열 (pub 6677, 17개 블로그) AdSense 표준화 완료.  
Phase 31은 **rotcha.kr 계열** (pub 8772) + compare-hugo(Blowfish) 적용.

## Publisher ID Mapping (확정)

| Pub ID | 도메인 | 블로그 |
|--------|-------|--------|
| `ca-pub-8772455780561463` | rotcha.kr (+ *.rotcha.kr) | hotissue(PaperMod 제외), compare, TAP 5개 |
| `ca-pub-8772455780561463` | techpawz.com | techpawz, biz/issue (별도 Phase) |

## Phase 31 Target (research 결과)

| Blog ID | 도메인 | 분기 | 테마 | 상태 | Deploy | 포함 |
|---------|-------|------|------|------|--------|------|
| **travel-hugo** | tour1.rotcha.kr | TAP | Blowfish | active | Pages | ✅ |
| **travel1-hugo** | travel1.rotcha.kr | TAP | Blowfish | active | Pages | ✅ |
| **travel2-hugo** | travel2.rotcha.kr | TAP | Blowfish | active | Pages | ✅ |
| **travel3-hugo** | tour2.rotcha.kr | TAP | Blowfish | active | Pages | ✅ |
| **travel4-hugo** | tour3.rotcha.kr | TAP | Blowfish | active | Pages | ✅ |
| **compare-hugo** | compare.rotcha.kr | CAP | Blowfish | active | Pages | ✅ |

**제외 사유:**
- tap-blogger → Blogger 플랫폼 (Hugo 아님)
- tvshow-blogger, ud-blogger → Blogger/inactive
- hotissue-hugo → **PaperMod** 테마 (Phase 30 규칙: PaperMod 건드리지 않음)
- deal/ev/guide/tco-hugo → inactive
- ETAP 30+ → 전부 inactive (techpawz.com)
- finance-hugo, sector-hugo → informationhot/techpawz 혼합, 별도 Phase

## Standard Template (rotcha 계열)

### params.toml (pages-build config)
```toml
[advertisement]
  adsense = "ca-pub-8772455780561463"
  inArticleSlot = "신규_슬롯_발급필요"
  leaderboardSlot = "신규_슬롯_발급필요"
```

> ⚠️ rotcha 계열은 정보hot 슬롯(2195212287, 3403350155) **재사용 금지**. AdSense 대시보드에서 rotcha 계열용 신규 슬롯 발급 필요.

### extend-head.html
```html
<script>
var _ad=0;function _ld(){if(_ad)return;_ad=1;var s=document.createElement("script");s.src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8772455780561463";s.async=1;s.crossOrigin="anonymous";document.head.appendChild(s);}["scroll","click","touchstart","keydown"].forEach(function(e){window.addEventListener(e,_ld,{once:1,passive:1});});setTimeout(_ld,7000);
</script>
```

### adsense/top.html
```html
<div class="ad-top not-prose">
  <ins class="adsbygoogle"
       style="display:block"
       data-ad-client="{{ .Site.Params.advertisement.adsense }}"
       data-ad-slot="{{ .Site.Params.advertisement.leaderboardSlot }}"
       data-ad-format="auto"
       data-full-width-responsive="true"></ins>
</div>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
```

### adsense/in-article.html
```html
<div class="ad-inarticle not-prose my-8">
  <ins class="adsbygoogle"
       style="display:block"
       data-ad-client="{{ .Site.Params.advertisement.adsense }}"
       data-ad-slot="{{ .Site.Params.advertisement.inArticleSlot }}"
       data-ad-format="auto"
       data-full-width-responsive="true"></ins>
</div>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
```

### custom.css (추가분)
```css
.ad-top { margin: 0 auto 24px; text-align: center; max-width: 728px; }
.ad-top ins, .ad-inarticle ins { display: block !important; width: 100% !important; text-align: center !important; margin: 8px auto !important; box-sizing: border-box !important; }
```

---

## Tasks

### Task 1 — Discovery (6개 블로그 설정 상태 확인)
- [ ] travel-hugo: params.toml, extend-head.html, top.html, in-article.html, single.html, custom.css 확인
- [ ] travel1-hugo: 동일 확인
- [ ] travel2-hugo: 동일 확인
- [ ] travel3-hugo: 동일 확인
- [ ] travel4-hugo: 동일 확인
- [ ] compare-hugo: 동일 확인
- [ ] showTableOfContents 여부 기록 (present/absent/false=true)
- [ ] [advertisement] section 존재 여부
- [ ] adsbygoogle.js 로드 여부

### Task 2 — 슬롯 발급 (AdSense 대시보드)
- [ ] AdSense 대시보드 → rotcha.kr 계열용 Display 슬롯 1개 발급
- [ ] AdSense 대시보드 → rotcha.kr 계열용 In-article 슬롯 1개 발급
- [ ] 슬롯 ID 기록 → Task 3 params.toml에 적용

### Task 3 — TAP 5개 블로그 표준화 (Pages)
- [ ] travel-hugo: [advertisement] + extend-head.html + top.html + showTOC 확인 + deploy
- [ ] travel1-hugo: 동일
- [ ] travel2-hugo: 동일
- [ ] travel3-hugo: 동일
- [ ] travel4-hugo: 동일
- [ ] 각 블로그 배포: `hugo --gc --minify --source <path> && wrangler pages deploy public --project-name=<id>`

### Task 4 — compare-hugo 표준화
- [ ] params.toml: [advertisement] section 추가 (pub 8772, 신규 슬롯)
- [ ] extend-head.html 생성/확인 (ca-pub-8772455780561463)
- [ ] top.html 신규 생성
- [ ] in-article.html 신규/갱신 (push({}) 추가)
- [ ] single.html: top.html partial 삽입
- [ ] custom.css: .ad-top + .ad-top ins 규칙 추가
- [ ] showTableOfContents 확인 (Blowfish 기본값)
- [ ] 배포: `hugo --gc --minify --source /Users/twinssn/Projects/cap/compare-hugo && wrangler pages deploy public --project-name=compare-hugo`

### Task 5 — Verification
- [ ] 6개 블로그 모두 wrangler pages deployment list 확인
- [ ] HTTP 200 + AdSense 렌더링 확인
- [ ] AdSense 대시보드 impressions 확인
- [ ] compare-hugo에서도 광고 정상 노출 확인
- [ ] Phase 31 완료 요약 작성

---

## Deployment

모든 Phase 31 블로그는 **Pages 배포** (Workers 블로그 없음).

```bash
# TAP 블로그 예시
cd /Users/twinssn/Projects/TAP/travel-hugo && hugo --gc --minify
export CLOUDFLARE_API_TOKEN=$(env -u CLOUDFLARE_API_TOKEN wrangler auth token 2>/dev/null | tail -1)
wrangler pages deploy public --project-name=travel-hugo
```

**절대 수동 wrangler 명령어 금지** (AGENTS.md 준수)

---

## Verification Criteria

1. Discovery: 6개 블로그 params.toml/checklist 완료 → Task 1 통과
2. AdSense 슬롯: Display 1개 + In-article 1개 발급 완료 → Task 2 통과
3. 6개 블로그 모두 [advertisement] section 존재 → `grep -r "\[advertisement\]" params.toml`
4. 6개 블로그 모두 top.html 존재 → `ls layouts/partials/adsense/top.html`
5. 6개 블로그 모두 in-article.html 존재 + push({}) 포함 → `grep "push" in-article.html`
6. all 6: `showTableOfContents = false` 또는 absent (기본 false)
7. wrangler pages deployment list — 6개 블로그 모두 Recent Deployment
8. AdSense impressions > 0 (대시보드)

---

## Phase 32+ 예고

**다음 대상 (Phase 32):**
- hotissue-hugo (PaperMod, rotcha.kr) — PaperMod 특화 표준
- techpawz 계열 (finance, dividend, etf, sector, ipo) — Blowfish, techpawz.com
- informationhot-hugo, techpawz-hugo, biz/issue-techpawz-hugo (Backup 4개)
