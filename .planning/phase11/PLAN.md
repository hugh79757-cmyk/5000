# Phase 11: AdSense 고효율 광고 구조 개선

## Phase Goal

10개 CUAP Hugo 블로그의 AdSense 광고를 자동광고(Auto Ads) + 수동 in-article + 리더보드 + 모바일 스티키 조합으로 개선. IntersectionObserver 기반 레이지로드로 성능 최적화.

## Phase Scope

### In Scope
1. **광고 파셜 3종** — in-article.html, leaderboard.html, mobile-sticky.html
2. **single.html 개선** — `split "<h2"` → `replace` + 마커 방식
3. **baseof.html override** — IntersectionObserver + mobile-sticky
4. **custom.css** — 광고 레이아웃 + 다크모드 + 반응형
5. **params.toml** — `[params.adsense]` 설정 추가
6. **10개 블로그 모두 적용** — laptop-hugo 기준으로 작성 후 배치 적용

### Out of Scope
- 자동광고(Auto Ads) 코드 변경 (AdSense 콘솔에서 제어)
- 새 광고 단위 신청 (기존 slot ID만 활용)
- 광고 성과 분석/RPM 측정

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Partial 위치 | 각 블로그의 `layouts/partials/adsense/` | 블로그별 독립성 유지, 공유 테마 보호 |
| baseof.html | 각 블로그의 `layouts/_default/baseof.html` override | 테마 수정 없이 </body> 직전 영역 확보 |
| CSS 경로 | `assets/css/custom.css` | Hugo 파이프라인에서 자동 처리 |
| 조건 분기 | `.WordCount` + `.Section` 기준 | 고단가 섹션(cars, finance)에서 광고 3개, 일반 2개, 800자 미만 0개 |
| 광고 로드 | IntersectionObserver (rootMargin 400px) | 뷰포트 진입 전 미리 로드, CLS 최소화 |
| 다크모드 | `.dark ins.adsbygoogle { background: #fff }` | AdSense 정책상 광고는 항상 밝은 배경 |

## Success Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| SC-01 | DevTools Console에 TagError/No slot size 없음 | Hugo server + DevTools |
| SC-02 | ins.adsbygoogle.lazyad가 AD1/AD2/AD3 자리에 존재 | Elements 탭 확인 |
| SC-03 | 광고 computed style: display:block, width >= 300px | Computed 탭 |
| SC-04 | pagead2.googlesyndication.com 200 응답 | Network 탭 |
| SC-05 | 스크롤 후 data-adsbygoogle-status="done" 부여 | Elements 탭 |
| SC-06 | PC(1440px) 리더보드 노출 | DevTools 뷰포트 변경 |
| SC-07 | 모바일(375px) 600px 이후 스티키 노출, 첫화면 미노출 | DevTools 뷰포트 변경 + 스크롤 |
| SC-08 | 다크모드에서 광고 흰 배경 | 다크모드 토글 |
| SC-09 | WordCount < 800 글: 본문 중간 광고 0개 | 해당 글 확인 |
| SC-10 | 고단가 섹션 + 800자↑: in-article 3개 | cars/finance 글 확인 |
| SC-11 | 일반 섹션 + 800자↑: in-article 2개 | 일반 글 확인 |
| SC-12 | 자동광고 + 수동광고 동시 렌더링, TagError 없음 | 실제 광고 노출 확인 |

## Task Breakdown

---

### Wave 1 — Reference Blog (laptop-hugo)

#### Task 11.1: Create directory + AdSense partials

**Directory:** `layouts/partials/adsense/` in laptop-hugo

**Files:**

**`layouts/partials/adsense/in-article.html`**
```html
<div class="ad-inarticle">
  <ins class="adsbygoogle lazyad"
       style="display:block; text-align:center;"
       data-ad-layout="in-article"
       data-ad-format="fluid"
       data-ad-client="{{ site.Params.adsense.clientID }}"
       data-ad-slot="{{ site.Params.adsense.inArticleSlot }}">
  </ins>
</div>
```

**`layouts/partials/adsense/leaderboard.html`**
```html
<div class="ad-leaderboard desktop-only">
  <ins class="adsbygoogle lazyad desktop-only"
       style="display:block;"
       data-ad-format="horizontal"
       data-ad-client="{{ site.Params.adsense.clientID }}"
       data-ad-slot="{{ site.Params.adsense.leaderboardSlot }}">
  </ins>
</div>
```

**`layouts/partials/adsense/mobile-sticky.html`**
```html
<div class="ad-mobile-sticky mobile-only" id="mobile-sticky-ad">
  <button class="close-btn" aria-label="광고 닫기" onclick="this.parentElement.style.display='none'">&times;</button>
  <ins class="adsbygoogle lazyad"
       id="mobile-sticky-ad-ins"
       style="display:block;"
       data-ad-format="horizontal"
       data-ad-client="{{ site.Params.adsense.clientID }}"
       data-ad-slot="{{ site.Params.adsense.mobileStickySlot }}">
  </ins>
</div>
```

**Done when:** 3 files exist in both laptop-hugo's partials directory.

---

#### Task 11.2: Add `[params.adsense]` to params.toml

**File:** `config/_default/params.toml` in laptop-hugo

**Add at end:**
```toml
[adsense]
  clientID = "ca-pub-6677996696534146"
  inArticleSlot = "2195212287"
  leaderboardSlot = "2195212287"
  mobileStickySlot = "2195212287"
```

Use same slot for all manual ad types (user specified this is OK). This keeps config DRY.

**Done when:** `grep -A4 '\[adsense\]' config/_default/params.toml` returns correct values.

---

#### Task 11.3: Create custom.css

**File:** `assets/css/custom.css` in laptop-hugo

**Content:** As specified in requirements (ad-inarticle, ad-leaderboard, ad-mobile-sticky, desktop/mobile breakpoints, dark mode, ad-leaderboard section, ad-mobile-sticky section)

**Done when:** `hugo --gc --minify` succeeds and custom.css is in the built output.

---

#### Task 11.4: Rewrite single.html (replace + marker approach)

**File:** `layouts/_default/single.html` in laptop-hugo

**Changes:**

1. **Remove** old ad code (current lines 49-58: top ad div with inline push)
2. **Remove** old split/h2 ad insertion logic (current lines 60-83)
3. **Add** conditional ad count logic at top:
   ```go
   {{ $adCount := 0 }}
   {{ if ge .WordCount 800 }}
     {{ $section := .Section }}
     {{ $highValueSections := slice "cars" "finance" "insurance" "crypto" "loans" "health" }}
     {{ if in $highValueSections $section }}
       {{ $adCount = 3 }}
     {{ else }}
       {{ $adCount = 2 }}
     {{ end }}
   {{ end }}
   ```
4. **Add** marker injection in `.Content` output:
   ```go
   {{ $content := .Content }}
   {{ if ge $adCount 1 }}{{ $content = replace $content "</p>" "</p><!--AD1-->" 1 }}{{ end }}
   {{ if ge $adCount 2 }}{{ $content = replace $content "<h2" "<!--AD2--><h2" 1 }}{{ end }}
   {{ if ge $adCount 3 }}{{ $content = replace $content "<h2" "<!--AD3--><h2" 1 }}{{ end }}
   {{ $content = printf "%s%s" $content (partial "adsense/leaderboard.html" .) }}
   {{ $content = replace $content "<!--AD1-->" (partial "adsense/in-article.html" .) | safeHTML }}
   {{ $content = replace $content "<!--AD2-->" (partial "adsense/in-article.html" .) | safeHTML }}
   {{ if eq $adCount 3 }}
     {{ $content = replace $content "<!--AD3-->" (partial "adsense/in-article.html" .) | safeHTML }}
   {{ end }}
   <div class="article-content max-w-prose mb-20">
     {{ $content }}
   </div>
   ```

Keep all existing Blowfish partials (series, sharing-links, related, etc.) unchanged.

**Done when:** Hugo build succeeds, DevTools shows correct ad markers in the rendered HTML.

---

#### Task 11.5: Override baseof.html

**File:** `layouts/_default/baseof.html` in laptop-hugo (NEW)

**Content:** Copy from `shared-themes/blowfish/layouts/_default/baseof.html` and add:

1. **Mobile sticky before `</body>`:**
   ```go
   {{ partial "adsense/mobile-sticky.html" . }}
   ```

2. **IntersectionObserver + mobile-sticky scroll script before `</html>`:**
   ```html
   <script>
   (function() {
     // IntersectionObserver: lazy-load manual ads
     if ('IntersectionObserver' in window && window.adsbygoogle) {
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
     // Mobile sticky: show after 600px scroll
     var stickyAd = document.getElementById('mobile-sticky-ad');
     if (stickyAd) {
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
     }
   })();
   </script>
   ```

**Done when:** Hugo build succeeds, sticky ad not visible on page load, shows after 600px scroll.

---

### Wave 2 — Batch Apply to 9 Remaining Blogs

#### Task 11.6: Copy partials + CSS + config to all blogs

**Action:** For each blog in [appliance, interior, baby, fitness, health, pet, kitchen, beauty, camping]:
1. `cp -r laptop-hugo/layouts/partials/adsense/ {blog}-hugo/layouts/partials/adsense/`
2. `cp laptop-hugo/assets/css/custom.css {blog}-hugo/assets/css/custom.css`
3. Append `[adsense]` block to `{blog}-hugo/config/_default/params.toml`

Note: Some blogs may have different client IDs or slot IDs. Check each blog's existing ad code (in single.html) for the correct values.

**Verification:**
```bash
for blog in appliance-hugo interior-hugo baby-hugo fitness-hugo health-hugo pet-hugo kitchen-hugo beauty-hugo camping-hugo; do
  ls /Users/twinssn/Projects/CUAP/$blog/layouts/partials/adsense/ 2>/dev/null
  ls /Users/twinssn/Projects/CUAP/$blog/assets/css/custom.css 2>/dev/null
  grep -q 'inArticleSlot' "/Users/twinssn/Projects/CUAP/$blog/config/_default/params.toml" && echo "$blog: adsense config ✅"
done
```

**Done when:** All 9 blogs have partials, CSS, and config.

---

#### Task 11.7: Copy single.html + baseof.html to all blogs

**Action:** For each blog in [appliance, interior, baby, fitness, health, pet, kitchen, beauty, camping]:
1. `cp laptop-hugo/layouts/_default/single.html {blog}-hugo/layouts/_default/single.html`
2. `cp laptop-hugo/layouts/_default/baseof.html {blog}-hugo/layouts/_default/baseof.html`

⚠️ Each blog may have custom modifications in single.html that differ from laptop-hugo. For the first pass, overwrite with laptop-hugo's version (they all use the same Blowfish template and same ad setup). Any blog-specific changes can be re-added later.

**Verification:**
```bash
for blog in appliance-hugo interior-hugo baby-hugo fitness-hugo health-hugo pet-hugo kitchen-hugo beauty-hugo camping-hugo; do
  echo "$blog: $(grep -c 'AD1' /Users/twinssn/Projects/CUAP/$blog/layouts/_default/single.html) ad markers"
done
```

**Done when:** All 9 blogs have AD1/AD2/AD3 markers in single.html.

---

### Wave 3 — Verification

#### Task 11.8: Build + verify all 10 blogs

**Action:** Hugo build each blog and check for errors.

```bash
for blog in laptop-hugo appliance-hugo interior-hugo baby-hugo fitness-hugo health-hugo pet-hugo kitchen-hugo beauty-hugo camping-hugo; do
  echo "=== $blog ==="
  cd /Users/twinssn/Projects/CUAP/$blog && /opt/homebrew/bin/hugo --gc --minify 2>&1 | tail -2
done
```

**Post-build checks:**
1. Open one blog in Hugo server mode
2. DevTools verification per checklist (SC-01 through SC-12)
3. If issues found, fix in laptop-hugo and re-copy to affected blogs

**Done when:** All 10 blogs build successfully, verification checklist passes.

## Dependency Graph

```
Wave 1 (laptop-hugo 기준)      Wave 2 (배치 적용)       Wave 3 (검증)
┌─────────────────────┐       ┌─────────────────┐     ┌─────────────────┐
│ Task 11.1: partials │       │ Task 11.6:      │     │ Task 11.8:      │
│ Task 11.2: config   │───────│ partials/CSS/   │─────│ build + verify  │
│ Task 11.3: CSS      │       │ config 복사     │     │ 10개 블로그     │
│ Task 11.4: single   │───┐   │                 │     └─────────────────┘
│ Task 11.5: baseof   │───┤   │ Task 11.7:      │
└─────────────────────┘   └───│ single/baseof   │
                              │ 복사            │
                              └─────────────────┘
```

- Wave 1 tasks are sequential (11.1 → 11.2 → 11.3 → 11.4 → 11.5) within laptop-hugo
- Wave 2 tasks depend on Wave 1 being complete (need reference files)
- Task 11.6 and 11.7 are parallel (different file sets)
- Wave 3 depends on both Wave 2 tasks

## Verification Strategy

| Task | Verification Method |
|------|-------------------|
| 11.1 | `ls layouts/partials/adsense/` shows 3 files |
| 11.2 | `grep -A4 '\[adsense\]' config/_default/params.toml` |
| 11.3 | Hugo build succeeds; `grep '.ad-inarticle' public/css/*.css` |
| 11.4 | Hugo build succeeds; `grep 'AD1' layouts/_default/single.html` |
| 11.5 | Hugo build succeeds; `grep 'IntersectionObserver' layouts/_default/baseof.html` |
| 11.6 | All 9 blogs have adsense/ dir, custom.css, adsense config |
| 11.7 | All 9 blogs have AD1 markers in single.html |
| 11.8 | All 10 blogs build; DevTools checklist passes |

## Rollback Strategy

| Change | Rollback |
|--------|----------|
| partials/adsense/ | `rm -rf layouts/partials/adsense/` per blog |
| custom.css | `rm -f assets/css/custom.css` per blog |
| params.toml `[adsense]` | Remove the `[adsense]` block |
| single.html | `git checkout HEAD -- layouts/_default/single.html` |
| baseof.html | `rm -f layouts/_default/baseof.html` (falls back to theme) |

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `split "<h2"` → `replace` changes break content rendering | Low | High | Verify with Hugo server; spot-check 3 different articles |
| baseof.html override breaks Blowfish theme features | Low | Medium | Keep original theme baseof intact; only add to `</body>` area |
| Custom CSS conflicts with Tailwind | Low | Low | Scoped class names (ad-*); no global overrides |
| AdSense slot mismatch (different client ID per blog) | Medium | Medium | Check each blog's existing ad code for correct `ca-pub-*` |
| IntersectionObserver not supported (old browsers) | Low | Low | `if ('IntersectionObserver' in window)` guard |
| `.dark` class not used by Blowfish (uses `data-appearance`) | Medium | Low | Check Blowfish init.js; use `html[data-appearance="dark"]` fallback |

## Execution Order

```yaml
order:
  - task_11.1: "Create adsense partials (laptop-hugo)"
  - task_11.2: "Add [params.adsense] to params.toml"
  - task_11.3: "Create assets/css/custom.css"
  - task_11.4: "Rewrite single.html (replace+marker)"
  - task_11.5: "Override baseof.html (observer + sticky)"
  - task_11.6: "Copy partials + CSS + config to 9 blogs"
  - task_11.7: "Copy single.html + baseof.html to 9 blogs"
  - task_11.8: "Build + verify all 10 blogs"

parallel_groups:
  wave_1: [task_11.1, task_11.2, task_11.3, task_11.4, task_11.5]  # NOTE: sequential in practice
  wave_2: [task_11.6, task_11.7]
  wave_3: [task_11.8]
```

Total tasks: 8 | Waves: 3 | New files: 6 per blog × 10 blogs = 60 | Modified files: 2 per blog × 10 blogs = 20
