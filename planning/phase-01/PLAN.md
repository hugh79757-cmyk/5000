# PLAN.md - Phase 01: Standardize AdSense Settings Across 6 Blogs

## Objective
Standardize AdSense implementation for the following blogs:
- rotcha-blog (rotcha.kr) – Blowfish theme
- techpawz-hugo (techpawz.com) – Blowfish theme
- informationhot-hugo (informationhot.kr) – PaperMod theme
- biz.techpawz-hugo (biz.techpawz.com) – Blowfish theme (subdomain of techpawz.com)
- kuta-hugo (kuta.informationhot.kr) – PaperMod theme (subdomain of informationhot.kr)
- issue.techpawz-hugo (issue.techpawz.com) – Blowfish theme (subdomain of techpawz.com)

Each blog must display ads correctly (no unfilled slots) while maintaining layout stability (CLS minimal) and adhering to domain‑specific AdSense Publisher IDs.

## Research Summary
- Blowfish theme AdSense guide is documented in `ADSENSE-GUIDE.md` (based on pet‑hugo).
- informationhot.kr uses PaperMod theme; requires different template adjustments.
- Publisher ID mapping:
  - rotcha.kr, techpawz.com (and subdomains) → `ca-pub-8772455780561463`
  - informationhot.kr (and subdomains) → `ca-pub-6677996696534146`
- Critical requirement: `showTableOfContents = false` for Blowfish sites to avoid ad rendering conflict.
- Slots must be separate: one Display (`topSlot`) and one In‑article (`inArticleSlot`). Reusing the same slot ID causes unfilled ads.

## Tasks

### 1. Prepare Common Resources
- [ ] Verify AdSense account has separate slot IDs allocated for each blog (or reuse same IDs if already approved, but ensure Display vs In‑article distinction).
- [ ] Record slot IDs in a reference table for later use.

### 2. Blowfish Sites (rotcha-blog, techpawz-hugo, biz.techpawz-hugo, issue.techpawz-hugo)
For each site:
#### Configuration
- [ ] Edit `config/_default/params.toml`:
  ```toml
  [article]
    showTableOfContents = false
  [advertisement]
    adsense = "<PUBLISHER_ID>"
    inArticleSlot = "<IN_ARTICLE_SLOT_ID>"
    topSlot = "<TOP_SLOT_ID>"
  ```
#### Templates
- [ ] Create `layouts/partials/extend-head.html` (if missing) with async adsbygoogle.js load:
  ```html
  {{ with site.Params.advertisement.adsense }}
  <script async
          src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={{ . }}"
          crossorigin="anonymous"></script>
  {{ end }}
  ```
- [ ] Create `layouts/partials/adsense/top.html` (Display slot):
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
- [ ] Create `layouts/partials/adsense/in-article.html` (In‑article slot):
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
- [ ] Override `layouts/_default/single.html` with header ads and body split injection logic (copy from ADSENSE-GUIDE.md lines 100‑140).
- [ ] Add/adjust `assets/css/custom.css`:
  ```css
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
  ins.adsbygoogle[data-ad-status="unfilled"] {
    min-height: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    display: none !important;
  }
  .dark ins.adsbygoogle,
  html.dark ins.adsbygoogle {
    background: #fff !important;
  }
  ```

#### Build & Deploy
- [ ] Run `hugo --gc --minify` to verify no build errors.
- [ ] Deploy via `dispatcher.py <blog_id>` (or wrappers) to Cloudflare Pages.
- [ ] Confirm deployment succeeds.

### 3. PaperMod Sites (informationhot-hugo, kuta-hugo)
For each site:
#### Configuration
- [ ] Edit `config/_default/params.toml`:
  ```toml
  [params]
    adsense = "<PUBLISHER_ID>"
    # PaperMod does not have built‑in ad slots; we will inject via partials
  [article]
    showTableOfContents = false   # disable TOC if present
  ```
#### Templates
- [ ] Create `layouts/partials/adsense.html` containing both ad slots:
  ```html
  {{- if site.Params.adsense }}
  <!-- Top (Display) ad -->
  <div class="ad-top my-4 text-center">
  <ins class="adsbygoogle"
       style="display:block"
       data-ad-client="{{ site.Params.adsense }}"
       data-ad-slot="{{ site.Params.topSlot | default \"<TOP_SLOT_ID>\" }}"
       data-ad-format="auto"
       data-full-width-responsive="true"></ins>
  <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
  </div>

  <!-- In‑article ad (to be placed after lead and after first paragraph) -->
  <div class="ad-inarticle my-4 text-center">
  <ins class="adsbygoogle"
       style="display:block"
       data-ad-client="{{ site.Params.adsense }}"
       data-ad-slot="{{ site.Params.inArticleSlot | default \"<IN_ARTICLE_SLOT_ID>\" }}"
       data-ad-layout="in-article"
       data-ad-format="fluid"></ins>
  <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
  </div>
  {{- end }}
  ```
- [ ] Update `layouts/_default/single.html`:
  - Insert `{{ partial "adsense.html" . }}` immediately after the opening `<article>` tag (top ad).
  - After the lead/description (if present) insert the same partial (in‑article ad after lead).
  - Use `.WordCount` and `.Section` logic to decide number of in‑article ads (similar to Blowfish split logic) – for simplicity, place one in‑article ad after the first paragraph and another before the third H2 if content length ≥ 800 words or high‑value section.
  - (Optional) Reuse the split‑injection logic from Blowfish if desired.
- [ ] Add/adjust `assets/css/custom.css` with same ad container styles and unfilled handling as above.

#### Build & Deploy
- [ ] Run Hugo build and verify no errors.
- [ ] Deploy via dispatcher.
- [ ] Confirm live deployment.

### 4. Verification Checks (applicable to all blogs)
- [ ] View page source of a sample post; confirm:
    - `adsbygoogle.js` loaded with correct `client=` ID.
    - Presence of `<ins class="adsbygoogle"` tags with correct `data-ad-slot` values.
    - No duplicate or missing slot IDs.
- [ ] Browser inspection:
    - Ads render (not collapsed) after page load.
    - No console errors related to AdSense.
    - Verify `showTableOfContents` is false (TOC not present).
- [ ] Run `hugo server` locally and check for any build warnings.
- [ ] Ensure CLS‑mitigating CSS is applied (min-height set, unfilled hidden).

## Acceptance Criteria
- All six blogs deploy successfully with Hugo build exit code 0.
- Each blog’s live pages show at least one ad slot filled (Top or In‑article) without empty placeholders.
- No AdSense policy violations (e.g., ads not obscured, proper spacing).
- TOC is disabled on Blowfish sites; PaperMod sites have TOC disabled if previously enabled.
- Slot IDs are correctly mapped per domain (rotcha/techpawz → 8772…, informationhot → 6677…).
- CSS rules for ad containers and unfilled handling are present in deployed `custom.css`.

## Notes
- If a blog already has some AdSense setup, migrate to the standardized files rather than duplicating.
- Keep backups of original templates before overriding.
- After deployment, monitor AdSense dashboard for `matched content` / `unfilled` impressions; adjust slot IDs or ad layout if needed.