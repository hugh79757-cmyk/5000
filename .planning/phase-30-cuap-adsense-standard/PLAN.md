# Phase 30 — cuap-adsense-standard

**Goal:** AdSense 표준화 (pet-hugo 검증 표준) → Wave 1 블로그 **17개** 적용

**Mode:** discovery-first (discovery 완료 — 2026-07-22)

## Context

pet-hugo (pet.informationhot.kr) AdSense 표준화 완료. 핵심 발견:
- `showTableOfContents = false` 필수 (sticky TOC 레이아웃이 AdSense fluid/in-article 광고 렌더링 방해 → 모든 광고 unfilled)
- adsbygoogle.js는 head에 즉시 로드 (lazy-load.html 중복 방지)
- 각 `ins.adsbygoogle` 직후 `(adsbygoogle = window.adsbygoogle || []).push({})` 필수
- Display 슬롯과 In-article 슬롯은 AdSense 대시보드에서 **별도 발급** (재사용 금지 — pet 슬롯 문제로 확인)
- pick-hugo, rank-hugo: in-article.html slot=1391844966 (별도 슬롯 확인 필요)
- Wave 1: 17개 blogs | Wave 2: 4개 | Wave 3: 6개 (inactive blogs)

## Publisher ID Mapping (확정)

| Pub ID | 도메인 | Blogs |
|--------|-------|-------|
| `ca-pub-6677996696534146` | informationhot.kr | pick-hugo, rank-hugo, 9 CUAP blogs, 5 RAP blogs, senior-hugo |
| `ca-pub-8772455780561463` | rotcha.kr, techpawz.com | hotissue-hugo, compare-hugo, deal/ev/guide/tco-hugo (inactive) |

## Standard Template (pet-hugo 검증 기준)

### params.toml (Blowfish)
```toml
[advertisement]
  adsense = "ca-pub-6677996696534146"
  inArticleSlot = "2195212287"
  leaderboardSlot = "2195212287"

[params]
  showTableOfContents = false
```

### extend-head.html
```html
<script>
var _ad=0;function _ld(){if(_ad)return;_ad=1;var s=document.createElement("script");s.src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-{PUBLISHER_ID}";s.async=1;s.crossOrigin="anonymous";document.head.appendChild(s);}["scroll","click","touchstart","keydown"].forEach(function(e){window.addEventListener(e,_ld,{once:1,passive:1});});setTimeout(_ld,7000);
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
.ad-inarticle { margin: 32px 0; min-height: 250px; text-align: center; }
.ad-top { margin: 0 auto 24px; text-align: center; max-width: 728px; }
.ad-top ins, .ad-inarticle ins { display: block !important; width: 100% !important; text-align: center !important; margin: 8px auto !important; box-sizing: border-box !important; }
```

---

## Wave 1 — 17개 Blogs (Active, informationhot.kr, Blowfish)

### Discovery Findings (2026-07-22)

| Blog | showTOC | [advertisement] | adsbygoogle.js | top.html | in-article.html | single.html pattern | Deploy |
|------|---------|----------------|----------------|----------|-----------------|---------------------|--------|
| **pick-hugo** | not set ✓ | NO ✗ | MISSING ✗ | MISSING ✗ | EXISTS (slot=1391844966) | split-content ✓ | Pages |
| **rank-hugo** | not set ✓ | NO ✗ | MISSING ✗ | MISSING ✗ | EXISTS (slot=1391844966) | split-content ✓ | Pages |
| **appliance-hugo** | true ✗ | YES (6677) ✓ | EXISTS ✓ | MISSING ✗ | MISSING ✗ | marker-based | Pages |
| **baby-hugo** | true ✗ | YES (6677) ✓ | EXISTS ✓ | MISSING ✗ | MISSING ✗ | marker-based | **Workers** |
| **fitness-hugo** | true ✗ | YES (6677) ✓ | EXISTS ✓ | MISSING ✗ | MISSING ✗ | marker-based | Pages |
| **interior-hugo** | true ✗ | YES (6677) ✓ | EXISTS ✓ | MISSING ✗ | MISSING ✗ | marker-based | Pages |
| **laptop-hugo** | true ✗ | YES (6677) ✓ | EXISTS ✓ | MISSING ✗ | MISSING ✗ | marker-based | Pages |
| **health-hugo** | true ✗ | YES (6677) ✓ | EXISTS ✓ | MISSING ✗ | MISSING ✗ | marker-based | **Workers** |
| **kitchen-hugo** | true ✗ | YES (6677) ✓ | EXISTS ✓ | MISSING ✗ | MISSING ✗ | marker-based | **Workers** |
| **beauty-hugo** | true ✗ | YES (6677) ✓ | EXISTS ✓ | MISSING ✗ | MISSING ✗ | marker-based | **Workers** |
| **camping-hugo** | true ✗ | YES (6677) ✓ | EXISTS ✓ | MISSING ✗ | MISSING ✗ | marker-based | **Workers** |
| **rap-hugo** | not set ✓ | NO ✗ | EXISTS ✓ | MISSING ✗ | EXISTS (slot=3403350155) | split-content ✓ | Pages |
| **rap2-hugo** | not set ✓ | NO ✗ | EXISTS ✓ | MISSING ✗ | EXISTS (slot=3403350155) | split-content ✓ | Pages |
| **rap3-hugo** | not set ✓ | NO ✗ | EXISTS ✓ | MISSING ✗ | EXISTS (slot=3403350155) | split-content ✓ | Pages |
| **rap4-hugo** | not set ✓ | NO ✗ | EXISTS ✓ | MISSING ✗ | EXISTS (slot=3403350155) | split-content ✓ | Pages |
| **rap5-hugo** | not set ✓ | NO ✗ | EXISTS ✓ | MISSING ✗ | EXISTS (slot=3403350155) | split-content ✓ | Pages |
| **senior-hugo** | true ✗ | YES (6677) ✓ | EXISTS ✓ | MISSING ✗ | EXISTS (slot=3905913036) | marker-based ✓ | Pages |

### Consolidated Problems

| Problem | Affected Blogs (Count) | Fix |
|---------|------------------------|-----|
| showTableOfContents = true | appliance, baby, fitness, interior, laptop, health, kitchen, beauty, camping, senior (10개) | set to false in params.toml |
| [advertisement] section missing | pick-hugo, rank-hugo, rap-hugo, rap2-hugo, rap3-hugo, rap4-hugo, rap5-hugo (7개) | add [advertisement] section |
| extend-head.html missing (adsbygoogle.js 미로딩) | pick-hugo, rank-hugo (2개) | create extend-head.html |
| top.html missing | ALL 17개 | create top.html |
| in-article.html missing | appliance, baby, fitness, interior, laptop, health, kitchen, beauty, camping (9개) | create in-article.html |
| in-article slot 불일치 ( RAP=3403350155, senior=3905913036, pick/rank=1391844966) | RAP 5개, senior-hugo, pick/rank | AdSense 대시보드에서 슬롯 발급 후 통일 |

---

## Tasks

### Task 1 — pick-hugo, rank-hugo (2개, Pages)
- [ ] params.toml에 `[advertisement]` section 추가 (`inArticleSlot`, `leaderboardSlot`)
- [ ] layouts/partials/extend-head.html 생성 (adsbygoogle.js 즉시 로드, ca-pub-6677996696534146)
- [ ] layouts/partials/adsense/top.html 생성 (leaderboardSlot 사용)
- [ ] deploy: `hugo --gc --minify --source /Users/twinssn/Projects/cap/pick-hugo && wrangler pages deploy public --project-name=pick-hugo`
- [ ] deploy: `hugo --gc --minify --source /Users/twinssn/Projects/cap/rank-hugo && wrangler pages deploy public --project-name=rank-hugo`

### Task 2 — laptop-hugo (1개, Pages)
- [ ] params.toml: `showTableOfContents = false`로 변경 (현재 true)
- [ ] layouts/partials/adsense/top.html 생성
- [ ] layouts/partials/adsense/in-article.html 생성 (params-driven)
- [ ] deploy: `hugo --gc --minify --source /Users/twinssn/Projects/cuap/laptop-hugo && wrangler pages deploy public --project-name=laptop-hugo`

### Task 3 — Group B: CUAP 8개 blogs (Mixed Pages/Workers)

**Workers blogs** (wrangler deploy --config wrangler.toml):
- baby-hugo: showTOC=false + top.html + in-article.html
- health-hugo: showTOC=false + top.html + in-article.html
- kitchen-hugo: showTOC=false + top.html + in-article.html
- beauty-hugo: showTOC=false + top.html + in-article.html
- camping-hugo: showTOC=false + top.html + in-article.html

**Pages blogs** (wrangler pages deploy public --project-name):
- appliance-hugo: showTOC=false + top.html + in-article.html
- fitness-hugo: showTOC=false + top.html + in-article.html
- interior-hugo: showTOC=false + top.html + in-article.html

- [ ] 위 각博客 파일 수정 적용
- [ ] Workers blogs: `wrangler deploy --config wrangler.toml --commit-dirty=false`
- [ ] Pages blogs: `wrangler pages deploy public --project-name={blog_id} --commit-dirty=false`

### Task 4 — RAP 5개 (apt~brand, Pages)
- [ ] 각博客 params.toml에 `[advertisement]` section 추가
- [ ] 각博客 layouts/partials/adsense/top.html 생성
- [ ] in-article slot 3403350155 → AdSense 대시보드 확인 (별도 슬롯 발급 여부)
- [ ] 배치 deploy: `wrangler pages deploy public --project-name={blog_id}`

### Task 5 — senior-hugo (1개, Pages)
- [ ] params.toml: `showTableOfContents = false`로 변경 (현재 true)
- [ ] layouts/partials/adsense/top.html 생성
- [ ] in-article slot 3905913036 → AdSense 대시보드 확인
- [ ] deploy: `hugo --gc --minify --source /Users/twinssn/Projects/SEAP/senior-hugo && wrangler pages deploy public --project-name=senior-hugo`

### Task 6 — AdSense 슬롯 통일 (모든 Wave 1 블로그)
- [ ] AdSense 대시보드에서 Wave 1 블로그용 In-article 슬롯 발급 (2195212287 또는 블로그별 신규)
- [ ] Display 슬롯: leaderboardSlot = 2195212287 통일
- [ ] params.toml의 [advertisement] 슬롯 값 AdSense 대시보드와突き合わせ

### Task 7 — Verification
- [ ] deploy 후 wrangler pages deployment list로 각博客 배포 확인
- [ ] HTTP 200 + AdSense 슬롯 렌더링 확인 (브라우저 DevTools)
- [ ] AdSense 대시보드에서 impressions 발생 확인
- [ ] Phase 30 완료 요약 작성

---

## Deployment

### Pages blogs (12개) — wrangler pages deploy
pick-hugo, rank-hugo, appliance-hugo, fitness-hugo, interior-hugo, laptop-hugo, senior-hugo

```bash
# Hugo 빌드
hugo --gc --minify --source /path/to/{blog}
# Pages 배포
wrangler pages deploy public --project-name={blog_id} --commit-dirty=false
```

### Workers blogs (5개) — wrangler deploy
health-hugo, kitchen-hugo, beauty-hugo, camping-hugo, baby-hugo

```bash
# Hugo 빌드
hugo --gc --minify --source /path/to/{blog}
# Workers 배포 (wrangler.toml 사용)
wrangler deploy --config wrangler.toml --commit-dirty=false
```

> **참고:** beauty-hugo, camping-hugo, baby-hugo는 `wrangler.toml` 존재하지만 `WORKERS_BLOGS`에 미등록 → 현재 pages로 배포 중. Phase 30 배포 후 wrangler pages deployment list로 정상 배포 여부 확인.

**절대 수동 wrangler 명령어 금지** (AGENTS.md deployment rules 준수)

---

## Verification Criteria

1. pick-hugo, rank-hugo: adsbygoogle.js network 탭에서 확인 → PASS
2. laptop-hugo + Group B 8개 + senior-hugo (총 10개): showTableOfContents = false 확인 → `grep -r "showTableOfContents" params.toml`
3. 모든 17개博客: top.html 존재 확인 → `ls layouts/partials/adsense/top.html`
4. Group B 8개: in-article.html 존재 확인
5. 모든 17개博客: `[advertisement]` section 존재 확인 (pick/rank/RAP는 추가, 나머지는既に存在)
6. wrangler pages deployment list — 17개博客 모두 Recent Deployment 있음
7. AdSense impressions > 0 (대시보드에서 확인)

---

## Wave 2 & Wave 3 (별도 Phase)

**Wave 2** (다음 Phase로):
- hotissue-hugo (rotcha.kr, PaperMod theme — 구조 달라서 별도 작업)
- compare-hugo (rotcha.kr, PaperMod theme)

**Wave 3** (Phase 31 이후):
- deal-hugo, ev-hugo, guide-hugo, tco-hugo (rotcha.kr, inactive, 8772)
- senior-blogger (blogger platform, 2.techpawz.com)