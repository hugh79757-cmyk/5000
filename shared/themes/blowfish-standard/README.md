# Blowfish Standard Override Directory

> **Phase**: 59-ops-dashboard-and-unification
> **Plan**: 06
> **Date**: 2026-08-06
> **Purpose**: Single source of truth for all Blowfish theme overrides

---

## Overview

This directory contains the canonical implementations of all allowed Blowfish theme overrides. These files are the reference standard that all Blowfish blogs should use.

**Source**: ADSENSE-GUIDE.md + Blowfish-Hugo-테마-업그레이드-표준-지침서.md v1.2

---

## Directory Structure

```
blowfish-standard/
├── layouts/
│   ├── _default/
│   │   └── single.html          # H2 split + prose wrapper
│   └── partials/
│       ├── extend-head.html      # adsbygoogle.js loader
│       ├── extend_head.html      # GA4 + mobile CSS
│       └── adsense/
│           ├── top.html          # Top ad slot
│           └── in-article.html   # In-article ad slot
└── assets/
    └── css/
        └── custom.css            # unfilled removal + dark mode
```

---

## File Descriptions

### 1. `layouts/_default/single.html`

**Purpose**: Standard single page template with H2 split injection for ads.

**Features**:
- Header 2-slot ad injection (top + in-article)
- H2-based content splitting for in-article ads
- Prose wrapper maintained for typography
- Description(lead) removed per standard

**Injection Rules**:
| Condition | in-article Count | Position |
|-----------|------------------|----------|
| H2 present, <800 chars | 2 | First paragraph + after 1st H2 |
| H2 present, ≥800 chars | 3 | First paragraph + after 1st H2 + after 3rd H2 |
| No H2 | 1 | After first `</p>` |

---

### 2. `layouts/partials/extend-head.html`

**Purpose**: AdSense `adsbygoogle.js` immediate loader.

**Features**:
- Uses `site.Params.advertisement.adsense` (no hardcoding)
- `async` only (no lazy-load)
- Enables anchor/fullpage Auto Ads

**Forbidden**:
- Hardcoded Publisher ID
- JavaScript placeholder manipulation

---

### 3. `layouts/partials/extend_head.html`

**Purpose**: GA4 tracking + mobile CSS corrections.

**Features**:
- GA4 gtag.js loader
- Mobile overflow prevention
- Unfilled ad space removal

**Note**: This is the underscore version. Blowfish loads both hyphen and underscore versions.

---

### 4. `layouts/partials/adsense/top.html`

**Purpose**: Top ad slot (Display format) before H1.

**Features**:
- `data-ad-format="auto"` (Display)
- `not-prose` class to disable Blowfish prose styles
- CLS prevention wrapper: `overflow:hidden;min-height:100px`
- `<script>` outside inner div

---

### 5. `layouts/partials/adsense/in-article.html`

**Purpose**: In-article ad slot (fluid+in-article format).

**Features**:
- `data-ad-format="fluid"` + `data-ad-layout="in-article"`
- `my-8` margin (larger than top's `my-4`)
- `text-align:center` inline style
- `<script>` outside inner div

**Forbidden**:
- `data-ad-format="auto"` (must use fluid+in-article)

---

### 6. `assets/css/custom.css`

**Purpose**: Ad styling + CLS prevention + dark mode.

**Features**:
- `.ad-inarticle`, `.ad-top` common styles
- Mobile responsive min-height
- Unfilled ad space removal
- Dark mode background defense

---

## Usage Instructions

### Option 1: Symlink (Recommended)

```bash
# For a blog at /path/to/blog
cd /path/to/blog

# Symlink individual files
ln -s /Users/twinssn/Projects/5000/shared/themes/blowfish-standard/layouts/_default/single.html layouts/_default/single.html
ln -s /Users/twinssn/Projects/5000/shared/themes/blowfish-standard/layouts/partials/extend-head.html layouts/partials/extend-head.html
ln -s /Users/twinssn/Projects/5000/shared/themes/blowfish-standard/layouts/partials/extend_head.html layouts/partials/extend_head.html
ln -s /Users/twinssn/Projects/5000/shared/themes/blowfish-standard/layouts/partials/adsense/top.html layouts/partials/adsense/top.html
ln -s /Users/twinssn/Projects/5000/shared/themes/blowfish-standard/layouts/partials/adsense/in-article.html layouts/partials/adsense/in-article.html
ln -s /Users/twinssn/Projects/5000/shared/themes/blowfish-standard/assets/css/custom.css assets/css/custom.css
```

### Option 2: Copy

```bash
# Copy entire directory structure
cp -r /Users/twinssn/Projects/5000/shared/themes/blowfish-standard/layouts/ /path/to/blog/layouts/
cp -r /Users/twinssn/Projects/5000/shared/themes/blowfish-standard/assets/ /path/to/blog/assets/
```

### Option 3: Hugo Module (Future)

```toml
# hugo.toml
[[module.imports]]
  path = "github.com/user/blowfish-standard"
```

---

## Customization

### GA4 Property ID

Replace `G-XXXXXXXXXX` in `extend_head.html` with your blog's GA4 property ID.

### Publisher ID

The `adsense` value in `hugo.toml` `[params.advertisement]` section controls the Publisher ID. No code changes needed.

### Slot IDs

The `topSlot` and `inArticleSlot` values in `hugo.toml` control ad slots. No code changes needed.

---

## Migration Checklist

For each blog migrating to this standard:

- [ ] Backup current `layouts/` directory
- [ ] Remove unauthorized override files
- [ ] Symlink or copy standard files
- [ ] Update `hugo.toml` with correct ad slots
- [ ] Test Hugo build: `hugo --gc --minify`
- [ ] Verify ads render correctly
- [ ] Remove `mobile-sticky.html` if present
- [ ] Remove custom `baseof.html` if present

---

## Related Documents

- `ADSENSE-GUIDE.md` — AdSense slot detailed guide
- `Blowfish-Hugo-테마-업그레이드-표준-지침서.md` — Theme upgrade standard
- `shared/themes/README.md` — Override audit report

---

**Next Steps**: Deploy to individual blogs in subsequent plans.
