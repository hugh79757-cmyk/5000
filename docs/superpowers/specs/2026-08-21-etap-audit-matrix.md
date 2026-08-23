# ETAP Audit Matrix — Corpus + Feed Master Table (FINAL)

- **Generated**: 2026-08-21 (feed pass appended to the 2026-08-21 corpus pass)
- **Corpus**: 36 ETAP blogs under `/Users/twinssn/Projects/ETAP/*-hugo`
- **Content inputs**: 5403 `index.md` (`content/posts/**/index.md`)
- **Feed inputs**: 36 `public/sitemap.xml` (5479 `<loc>`), 36 `public/robots.txt`, 5,5xx `public/**/*.html`
- **Shape**: 36 blog rows × 12 content checks + 9 feed checks + 2 derived, `TOTAL` row appended
- **Reference date for 30-day windows**: `2026-08-21`
- **Source of truth**: LOCAL built artifacts (`public/`), not live HTTP. Live drift is possible; see Caveats.
- **Machine-readable**: `2026-08-21-etap-audit-matrix.csv` (same 36+1 rows, all columns)

## Check definitions

### Content checks (from the corpus pass)

| column | definition |
| --- | --- |
| blog | Blog directory name (`*-hugo`) |
| table0 | posts with NO GitHub-Flavored markdown table (no `\|` row adjacent to a `\|-\|` separator) |
| no_airlines | posts with zero case-insensitive token `airline` |
| verified | posts whose frontmatter contains a `verified:` key |
| currency_no_symbol | posts whose body has a bare currency-word amount (`21 USD`, `56 Euro`, `1000 dollars`) with no `$/€/£/¥` symbol |
| cjk | posts containing any CJK / Hangul / Kana codepoint |
| hard_ads | posts containing hard-coded AdSense markup (`adsbygoogle` or `data-ad-client`) |
| ins | posts containing any `<ins` HTML tag |
| word400 | posts whose body word count < 400 |
| h2lt3 | posts with fewer than 3 `## ` H2 headings |
| latex | posts containing LaTeX markers (`\\(`, `\\]`, `\\begin{`, or `$...$`) |
| frontmatter_missing | posts whose first non-empty line is not `---` (no frontmatter block) |
| total_posts | total `index.md` for the blog |

### Feed checks (this pass)

| column | definition |
| --- | --- |
| sitemap_urls | `<url><loc>` entries in `public/sitemap.xml` |
| lastmod_earliest | oldest `<lastmod>` date in the sitemap (`YYYY-MM-DD`) |
| lastmod_latest | newest `<lastmod>` date in the sitemap |
| gap_days_max | largest gap in days between consecutive **distinct** `lastmod` dates (publishing blackout length) |
| last30d | sitemap URLs with `lastmod >= 2026-08-21 − 30d` (i.e. on/after `2026-07-22`) |
| noindex_fm | posts whose frontmatter sets `robots: "noindex"` |
| noindex_in_sitemap | of those, how many URLs are **still listed** in `sitemap.xml` (the overlap) |
| noindex_meta_html | built HTML pages that actually emit `<meta name="robots" ... noindex>` |
| robots_disallow | `Disallow:` rules in `public/robots.txt` |
| days_since_latest | `2026-08-21 − lastmod_latest` (staleness) |
| sitemap_minus_posts | `sitemap_urls − total_posts` (expected ≈2: home + `/posts/`) |

## Corpus master table (content checks)

| blog | table0 | no_airlines | verified | currency_no_symbol | cjk | hard_ads | ins | word400 | h2lt3 | latex | frontmatter_missing | total_posts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| adventure-hugo | 115 | 154 | 0 | 1 | 0 | 69 | 69 | 4 | 17 | 143 | 0 | 154 |
| airlines-hugo | 108 | 90 | 0 | 2 | 3 | 13 | 13 | 1 | 5 | 26 | 0 | 115 |
| airports-hugo | 138 | 91 | 0 | 0 | 1 | 34 | 34 | 15 | 8 | 15 | 0 | 163 |
| bus-hugo | 84 | 148 | 0 | 2 | 0 | 73 | 73 | 0 | 20 | 38 | 0 | 162 |
| citytours-hugo | 43 | 120 | 0 | 34 | 1 | 81 | 81 | 5 | 24 | 98 | 0 | 120 |
| cruise-hugo | 62 | 110 | 0 | 30 | 1 | 54 | 54 | 3 | 6 | 19 | 0 | 110 |
| culture-hugo | 161 | 167 | 0 | 65 | 0 | 68 | 68 | 4 | 32 | 124 | 0 | 167 |
| daytrips-hugo | 107 | 182 | 0 | 40 | 5 | 83 | 83 | 5 | 9 | 47 | 0 | 182 |
| deals-hugo | 105 | 37 | 0 | 0 | 0 | 40 | 40 | 0 | 0 | 104 | 0 | 105 |
| dining-hugo | 120 | 120 | 0 | 2 | 3 | 35 | 35 | 0 | 0 | 41 | 0 | 120 |
| escape-hugo | 98 | 102 | 0 | 43 | 0 | 71 | 71 | 6 | 21 | 64 | 0 | 102 |
| esim-hugo | 263 | 264 | 0 | 4 | 1 | 72 | 72 | 4 | 9 | 123 | 0 | 265 |
| eurail-hugo | 85 | 164 | 0 | 8 | 0 | 70 | 70 | 7 | 33 | 127 | 0 | 170 |
| extreme-hugo | 77 | 107 | 0 | 31 | 0 | 74 | 74 | 5 | 25 | 90 | 0 | 107 |
| ferry-hugo | 85 | 156 | 0 | 3 | 0 | 71 | 71 | 0 | 17 | 23 | 0 | 159 |
| flights-hugo | 272 | 90 | 0 | 18 | 4 | 53 | 53 | 0 | 16 | 150 | 0 | 272 |
| foodtour-hugo | 136 | 143 | 0 | 0 | 4 | 70 | 70 | 2 | 11 | 104 | 0 | 143 |
| ghost-hugo | 81 | 94 | 0 | 13 | 0 | 64 | 64 | 3 | 17 | 73 | 0 | 94 |
| hiking-hugo | 60 | 81 | 0 | 33 | 0 | 49 | 49 | 7 | 22 | 62 | 0 | 82 |
| layover-hugo | 48 | 96 | 0 | 6 | 1 | 67 | 67 | 6 | 19 | 90 | 0 | 99 |
| luxury-hugo | 65 | 112 | 0 | 41 | 3 | 78 | 78 | 7 | 23 | 98 | 0 | 112 |
| michelin-hugo | 273 | 273 | 0 | 6 | 3 | 0 | 0 | 5 | 8 | 65 | 0 | 273 |
| multiday-hugo | 157 | 163 | 0 | 91 | 1 | 71 | 71 | 5 | 26 | 106 | 0 | 163 |
| nature-hugo | 92 | 110 | 0 | 16 | 1 | 66 | 66 | 5 | 8 | 21 | 0 | 110 |
| nightlife-hugo | 88 | 107 | 0 | 45 | 3 | 75 | 75 | 5 | 23 | 53 | 0 | 107 |
| nomad-hugo | 39 | 39 | 0 | 10 | 4 | 30 | 30 | 0 | 0 | 25 | 0 | 39 |
| phototour-hugo | 105 | 111 | 0 | 23 | 1 | 64 | 64 | 5 | 6 | 9 | 0 | 111 |
| tour-hugo | 254 | 253 | 0 | 4 | 4 | 125 | 125 | 0 | 0 | 184 | 0 | 254 |
| tours-hugo | 204 | 204 | 0 | 28 | 0 | 83 | 83 | 82 | 113 | 98 | 0 | 204 |
| trains-hugo | 55 | 125 | 0 | 2 | 0 | 82 | 82 | 4 | 31 | 100 | 0 | 145 |
| transfers-hugo | 120 | 158 | 0 | 82 | 1 | 73 | 73 | 5 | 27 | 90 | 0 | 162 |
| visa-hugo | 252 | 249 | 0 | 0 | 0 | 80 | 80 | 6 | 13 | 15 | 0 | 252 |
| visafree-hugo | 169 | 164 | 0 | 0 | 0 | 67 | 67 | 5 | 7 | 0 | 0 | 169 |
| walking-hugo | 138 | 148 | 0 | 4 | 2 | 67 | 67 | 1 | 17 | 133 | 0 | 148 |
| watersports-hugo | 138 | 159 | 0 | 0 | 0 | 78 | 78 | 4 | 21 | 147 | 0 | 159 |
| watertours-hugo | 70 | 104 | 0 | 37 | 0 | 73 | 73 | 5 | 22 | 84 | 0 | 104 |
| TOTAL | 4467 | 4995 | 0 | 724 | 47 | 2323 | 2323 | 221 | 656 | 2789 | 0 | 5403 |

## Feed master table (sitemap / robots)

| blog | sitemap_urls | lastmod_earliest | lastmod_latest | gap_days_max | last30d | noindex_fm | noindex_in_sitemap | noindex_meta_html | robots_disallow | days_since_latest | sitemap_minus_posts |
|---|---|---|---|---|---|---|---|---|---|---|---|
| adventure-hugo | 156 | 2026-04-03 | 2026-08-21 | 98 | 23 | 0 | 0 | 0 | 0 | 0 | 2 |
| airlines-hugo | 117 | 2026-03-31 | 2026-08-20 | 99 | 9 | 0 | 0 | 0 | 0 | 1 | 2 |
| airports-hugo | 165 | 2026-04-01 | 2026-08-21 | 99 | 30 | 29 | 29 | 0 | 0 | 0 | 2 |
| bus-hugo | 164 | 2026-04-04 | 2026-08-21 | 98 | 22 | 0 | 0 | 0 | 0 | 0 | 2 |
| citytours-hugo | 122 | 2026-04-17 | 2026-08-20 | 96 | 36 | 0 | 0 | 0 | 0 | 1 | 2 |
| cruise-hugo | 113 | 2026-04-05 | 2026-08-21 | 96 | 31 | 0 | 0 | 0 | 0 | 0 | 3 |
| culture-hugo | 169 | 2026-04-04 | 2026-08-21 | 96 | 34 | 0 | 0 | 0 | 0 | 0 | 2 |
| daytrips-hugo | 184 | 2026-04-02 | 2026-08-21 | 98 | 41 | 0 | 0 | 0 | 0 | 0 | 2 |
| deals-hugo | 107 | 2026-04-05 | 2026-05-06 | 3 | 0 | 0 | 0 | 0 | 0 | 107 | 2 |
| dining-hugo | 122 | 2026-04-04 | 2026-08-21 | 100 | 7 | 0 | 0 | 0 | 0 | 0 | 2 |
| escape-hugo | 103 | 2026-04-17 | 2026-08-16 | 96 | 22 | 0 | 0 | 0 | 0 | 5 | 1 |
| esim-hugo | 267 | 2026-03-31 | 2026-08-21 | 98 | 43 | 0 | 0 | 0 | 0 | 0 | 2 |
| eurail-hugo | 173 | 2026-04-05 | 2026-08-21 | 96 | 36 | 0 | 0 | 0 | 0 | 0 | 3 |
| extreme-hugo | 109 | 2026-04-17 | 2026-08-21 | 96 | 27 | 0 | 0 | 0 | 0 | 0 | 2 |
| ferry-hugo | 161 | 2026-04-04 | 2026-08-21 | 98 | 19 | 0 | 0 | 0 | 0 | 0 | 2 |
| flights-hugo | 274 | 2026-04-01 | 2026-08-21 | 108 | 43 | 0 | 0 | 0 | 0 | 0 | 2 |
| foodtour-hugo | 145 | 2026-04-03 | 2026-08-21 | 98 | 16 | 0 | 0 | 0 | 0 | 0 | 2 |
| ghost-hugo | 96 | 2026-04-17 | 2026-08-21 | 98 | 19 | 0 | 0 | 0 | 0 | 0 | 2 |
| hiking-hugo | 84 | 2026-04-17 | 2026-08-16 | 96 | 24 | 0 | 0 | 0 | 0 | 5 | 2 |
| layover-hugo | 101 | 2026-04-17 | 2026-08-21 | 96 | 21 | 0 | 0 | 0 | 0 | 0 | 2 |
| luxury-hugo | 114 | 2026-04-17 | 2026-08-17 | 96 | 25 | 0 | 0 | 0 | 0 | 4 | 2 |
| michelin-hugo | 275 | 2026-04-01 | 2026-08-21 | 96 | 40 | 0 | 0 | 0 | 0 | 0 | 2 |
| multiday-hugo | 165 | 2026-04-04 | 2026-08-21 | 96 | 28 | 0 | 0 | 0 | 0 | 0 | 2 |
| nature-hugo | 112 | 2026-04-05 | 2026-08-21 | 96 | 30 | 0 | 0 | 0 | 0 | 0 | 2 |
| nightlife-hugo | 109 | 2026-04-17 | 2026-08-21 | 96 | 25 | 0 | 0 | 0 | 0 | 0 | 2 |
| nomad-hugo | 41 | 2026-04-17 | 2026-05-02 | 4 | 0 | 0 | 0 | 0 | 0 | 111 | 2 |
| phototour-hugo | 114 | 2026-04-05 | 2026-08-21 | 96 | 30 | 0 | 0 | 0 | 0 | 0 | 3 |
| tour-hugo | 258 | 2026-03-31 | 2026-08-21 | 96 | 41 | 0 | 0 | 0 | 0 | 0 | 4 |
| tours-hugo | 206 | 2026-04-01 | 2026-08-21 | 98 | 36 | 0 | 0 | 0 | 0 | 0 | 2 |
| trains-hugo | 147 | 2026-04-01 | 2026-08-21 | 96 | 33 | 0 | 0 | 0 | 0 | 0 | 2 |
| transfers-hugo | 164 | 2026-04-04 | 2026-08-21 | 96 | 29 | 0 | 0 | 0 | 0 | 0 | 2 |
| visa-hugo | 254 | 2026-04-01 | 2026-08-21 | 96 | 43 | 0 | 0 | 0 | 0 | 0 | 2 |
| visafree-hugo | 171 | 2026-04-05 | 2026-08-21 | 96 | 36 | 0 | 0 | 0 | 0 | 0 | 2 |
| walking-hugo | 150 | 2026-04-03 | 2026-08-21 | 98 | 19 | 0 | 0 | 0 | 0 | 0 | 2 |
| watersports-hugo | 161 | 2026-04-03 | 2026-08-21 | 96 | 23 | 0 | 0 | 0 | 0 | 0 | 2 |
| watertours-hugo | 106 | 2026-04-17 | 2026-08-17 | 96 | 24 | 0 | 0 | 0 | 0 | 4 | 2 |
| TOTAL | 5479 | 2026-03-31 | 2026-08-21 | 108 | 965 | 29 | 29 | 0 | 0 | 111 | 76 |

## Findings

1. **noindex ⟂ sitemap conflict — `airports-hugo`, 29 URLs.** 29 posts carry `robots: "noindex"` in frontmatter; all 29 are still emitted in `sitemap.xml` (`noindex_in_sitemap = 29`), and **zero** built pages emit a `noindex` meta tag (`noindex_meta_html = 0` corpus-wide). The theme ignores the frontmatter `robots` key, so the noindex intent is not honored anywhere — the pages are advertised as indexable. Fix = either drop the key or add a `robots` meta + sitemap exclusion in the layout.
2. **Two dead feeds.** `deals-hugo` (`lastmod_latest 2026-05-06`, 107 days stale, `last30d = 0`) and `nomad-hugo` (`2026-05-02`, 111 days, `last30d = 0`) have published nothing for ~3.5 months. Their small `gap_days_max` (3 / 4) is misleading — they stopped rather than paused, so read `days_since_latest` alongside `gap_days_max`.
3. **Corpus-wide ~96-day blackout.** 34/36 blogs show `gap_days_max` of 96–108 days, matching the May→August publishing hole visible in the monthly distribution (2026-06 and 2026-07 have zero posts). This is one fleet-level outage, not 34 independent ones.
4. **robots.txt is uniformly permissive.** All 36 files are `User-agent: * / Allow: / / Sitemap: …`, `robots_disallow = 0` everywhere — so the only indexability conflict is finding 1. `eurail-hugo` has a **relative** `Sitemap: /sitemap.xml` line (all others absolute) — relative sitemap URLs are invalid per spec and may be ignored by crawlers.
5. **Sitemap/post deltas mostly consistent.** `sitemap_minus_posts = 2` on 31/36 blogs (home + `/posts/`). Outliers: `escape-hugo` (1), `cruise-hugo`/`eurail-hugo`/`phototour-hugo` (3), `tour-hugo` (4) — extra taxonomy/section pages or, for `escape-hugo`, one content post missing from the built sitemap (stale build or excluded page). Worth one spot-check each.
6. **Fresh-content concentration.** `last30d` totals 965 URLs across 36 blogs; `visa-hugo`, `esim-hugo`, `flights-hugo` (43 each), `daytrips-hugo`/`tour-hugo` (41) lead, while 12 blogs sit below 22.

## Caveats

- All feed numbers come from **local `public/` builds**. A blog whose local build predates its last deploy (or vice versa) will report the build's state, not the live site's. Re-run after a fresh `hugo` build for deploy-accurate numbers.
- `last30d` uses `lastmod`, which Hugo derives from git/file mtime, not the post's `date:` frontmatter — a bulk edit inflates it. Compare against the content-pass monthly distribution before treating it as a publishing rate.
- `noindex_meta_html` scans every `*.html` under `public/`, including list/taxonomy pages, so it is an upper bound on rendered noindex — and it is 0, so the conclusion (nothing is noindexed) holds regardless.

## Monthly distribution (content pass, aggregated across 36 blogs)

Buckets by frontmatter `date:` → `YYYY-MM` (posts with no parsable date land in `unknown`).

| month | table0 | no_airlines | verified | currency_no_symbol | cjk | hard_ads | ins | word400 | h2lt3 | latex | frontmatter_missing | total_posts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-03 | 24 | 24 | 0 | 0 | 0 | 8 | 8 | 0 | 0 | 8 | 0 | 24 |
| 2026-04 | 3360 | 3513 | 0 | 392 | 23 | 1150 | 1150 | 97 | 82 | 1963 | 0 | 3788 |
| 2026-05 | 488 | 661 | 0 | 120 | 5 | 675 | 675 | 0 | 0 | 377 | 0 | 696 |
| 2026-08 | 595 | 797 | 0 | 212 | 19 | 490 | 490 | 124 | 574 | 441 | 0 | 895 |

## Queries

### 1. Feed audit (this pass)

````python
#!/usr/bin/env python3
"""ETAP feed (sitemap/robots) audit — 36 blogs.

Reads the LOCAL built artifacts (public/sitemap.xml, public/robots.txt,
public/**/index.html) plus content frontmatter. Local build snapshot, not live HTTP.

Columns:
  sitemap_urls      <url><loc> entries in public/sitemap.xml
  lastmod_earliest  min <lastmod> date (YYYY-MM-DD)
  lastmod_latest    max <lastmod> date
  gap_days_max      largest gap in days between consecutive DISTINCT lastmod dates
  last30d           sitemap URLs with lastmod >= REF_DATE - 30d
  noindex_fm        posts with frontmatter `robots: "noindex"`
  noindex_in_sitemap  of those, how many URLs are still listed in sitemap.xml (overlap)
  noindex_meta_html   built HTML pages emitting <meta name="robots" ... noindex>
  robots_disallow   Disallow: rules in public/robots.txt
"""
import csv, re, datetime as dt
from pathlib import Path

ROOT = Path("/Users/twinssn/Projects/ETAP")
REF_DATE = dt.date(2026, 8, 21)          # audit reference day
LOC_RE  = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S)
LM_RE   = re.compile(r"<lastmod>\s*(\d{4}-\d{2}-\d{2})")
NOIDX_FM_RE = re.compile(r'(?mi)^robots\s*:\s*["\']?\s*noindex')
NOIDX_META_RE = re.compile(r'(?is)<meta[^>]+name=["\']robots["\'][^>]*noindex')

COLS = ["blog","sitemap_urls","lastmod_earliest","lastmod_latest","gap_days_max",
        "last30d","noindex_fm","noindex_in_sitemap","noindex_meta_html","robots_disallow"]

rows = []
for blog in sorted(ROOT.glob("*-hugo")):
    pub = blog / "public"
    sm  = pub / "sitemap.xml"
    txt = sm.read_text(encoding="utf-8", errors="ignore") if sm.exists() else ""
    locs = LOC_RE.findall(txt)
    lastmods = sorted({dt.date.fromisoformat(d) for d in LM_RE.findall(txt)})

    gap = 0
    for a, b in zip(lastmods, lastmods[1:]):
        gap = max(gap, (b - a).days)

    # per-URL lastmod for the 30d window
    pairs = re.findall(r"<url>(.*?)</url>", txt, re.S)
    cutoff = REF_DATE - dt.timedelta(days=30)
    last30 = 0
    for blk in pairs:
        m = LM_RE.search(blk)
        if m and dt.date.fromisoformat(m.group(1)) >= cutoff:
            last30 += 1

    # frontmatter noindex posts and whether their URL is still in the sitemap
    loc_paths = {re.sub(r"^https?://[^/]+", "", u).rstrip("/") + "/" for u in locs}
    noidx_fm, noidx_in_sm = 0, 0
    for md in (blog / "content" / "posts").rglob("index.md"):
        if NOIDX_FM_RE.search(md.read_text(encoding="utf-8", errors="ignore")):
            noidx_fm += 1
            if f"/posts/{md.parent.name}/" in loc_paths:
                noidx_in_sm += 1

    noidx_meta = sum(1 for h in pub.rglob("*.html")
                     if NOIDX_META_RE.search(h.read_text(encoding="utf-8", errors="ignore")))

    rtxt = (pub / "robots.txt").read_text(encoding="utf-8", errors="ignore") if (pub / "robots.txt").exists() else ""
    disallow = len(re.findall(r"(?mi)^\s*Disallow\s*:\s*\S", rtxt))

    rows.append({
        "blog": blog.name, "sitemap_urls": len(locs),
        "lastmod_earliest": lastmods[0].isoformat() if lastmods else "",
        "lastmod_latest": lastmods[-1].isoformat() if lastmods else "",
        "gap_days_max": gap, "last30d": last30, "noindex_fm": noidx_fm,
        "noindex_in_sitemap": noidx_in_sm, "noindex_meta_html": noidx_meta,
        "robots_disallow": disallow,
    })

OUT = Path("/var/folders/6r/kjl8wkw53t1bnr1dypqtccj80000gn/T/opencode/etap/feed.csv")
with OUT.open("w", newline="") as f:
    w = csv.DictWriter(f, COLS); w.writeheader(); w.writerows(rows)
for r in rows:
    print(",".join(str(r[c]) for c in COLS))
tot = {"sitemap_urls":0,"last30d":0,"noindex_fm":0,"noindex_in_sitemap":0,"noindex_meta_html":0,"robots_disallow":0}
for r in rows:
    for k in tot: tot[k] += r[k]
print("TOTAL", tot)
print("earliest", min(r["lastmod_earliest"] for r in rows if r["lastmod_earliest"]),
      "latest", max(r["lastmod_latest"] for r in rows if r["lastmod_latest"]),
      "max gap", max(r["gap_days_max"] for r in rows))

````

### 2. Merge corpus + feed → final CSV

````python
#!/usr/bin/env python3
"""Merge ETAP corpus matrix (13 cols) + feed audit (10 cols) -> final CSV + MD."""
import csv, datetime as dt
from pathlib import Path

SPEC = Path("/Users/twinssn/Projects/5000/docs/superpowers/specs")
CORPUS = SPEC / "2026-08-21-etap-audit-matrix.csv"      # existing 36-row template
FEED = Path("/var/folders/6r/kjl8wkw53t1bnr1dypqtccj80000gn/T/opencode/etap/feed.csv")
REF = dt.date(2026, 8, 21)

corpus = {r["blog"]: r for r in csv.DictReader(CORPUS.open())}
feed = {r["blog"]: r for r in csv.DictReader(FEED.open())}
assert set(corpus) == set(feed) == set(corpus) and len(corpus) == 36, (len(corpus), len(feed))

CCOLS = ["table0","no_airlines","verified","currency_no_symbol","cjk","hard_ads","ins",
         "word400","h2lt3","latex","frontmatter_missing","total_posts"]
FCOLS = ["sitemap_urls","lastmod_earliest","lastmod_latest","gap_days_max","last30d",
         "noindex_fm","noindex_in_sitemap","noindex_meta_html","robots_disallow"]
DCOLS = ["days_since_latest","sitemap_minus_posts"]
ALL = ["blog"] + CCOLS + FCOLS + DCOLS

rows = []
for b in sorted(corpus):
    r = {"blog": b}
    r.update({k: int(corpus[b][k]) for k in CCOLS})
    for k in FCOLS:
        v = feed[b][k]
        r[k] = int(v) if k not in ("lastmod_earliest", "lastmod_latest") else v
    r["days_since_latest"] = (REF - dt.date.fromisoformat(r["lastmod_latest"])).days
    r["sitemap_minus_posts"] = r["sitemap_urls"] - r["total_posts"]
    rows.append(r)

num = [c for c in ALL if c not in ("blog", "lastmod_earliest", "lastmod_latest")]
tot = {c: sum(r[c] for r in rows) for c in num}
total_row = {"blog": "TOTAL", **tot,
             "lastmod_earliest": min(r["lastmod_earliest"] for r in rows),
             "lastmod_latest": max(r["lastmod_latest"] for r in rows)}
# gap/days_since are maxima, not sums
total_row["gap_days_max"] = max(r["gap_days_max"] for r in rows)
total_row["days_since_latest"] = max(r["days_since_latest"] for r in rows)

with (SPEC / "2026-08-21-etap-audit-matrix.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, ALL); w.writeheader(); w.writerows(rows); w.writerow(total_row)

def tbl(cols, rs):
    s = "| " + " | ".join(cols) + " |\n|" + "|".join(["---"] * len(cols)) + "|\n"
    for r in rs:
        s += "| " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n"
    return s

corpus_cols = ["blog"] + CCOLS
feed_cols = ["blog"] + FCOLS + DCOLS
print(tbl(corpus_cols, rows + [total_row]))
print(tbl(feed_cols, rows + [total_row]))
Path("/var/folders/6r/kjl8wkw53t1bnr1dypqtccj80000gn/T/opencode/etap/corpus_tbl.md").write_text(tbl(corpus_cols, rows + [total_row]))
Path("/var/folders/6r/kjl8wkw53t1bnr1dypqtccj80000gn/T/opencode/etap/feed_tbl.md").write_text(tbl(feed_cols, rows + [total_row]))
stale = [(r["blog"], r["days_since_latest"], r["last30d"]) for r in rows if r["days_since_latest"] > 30 or r["last30d"] == 0]
print("STALE:", stale)
print("sitemap_minus_posts distinct:", sorted({r["sitemap_minus_posts"] for r in rows}))
print("odd delta:", [(r["blog"], r["sitemap_minus_posts"]) for r in rows if r["sitemap_minus_posts"] != 2])
print("noindex blogs:", [(r["blog"], r["noindex_fm"], r["noindex_in_sitemap"], r["noindex_meta_html"]) for r in rows if r["noindex_fm"]])

````

### 3. Content corpus audit (original pass, unchanged)

````python
#!/usr/bin/env python3
"""ETAP corpus audit matrix query.

Scans every index.md under /Users/twinssn/Projects/ETAP/*-hugo/content/posts/
and produces per-blog counts for 13 checks plus an aggregated monthly
distribution. Output: CSV (docs/superpowers/specs/2026-08-21-etap-audit-matrix.csv)
and a markdown table printed to stdout.

Check definitions (kept concrete + reproducible):
  table0           posts with NO GitHub-Flavored markdown table
  no_airlines      posts with zero case-insensitive "airline" token
  verified         posts whose frontmatter contains a 'verified' key
  currency_no_symbol posts whose body has a bare currency word amount
                   (e.g. "21 USD", "56 Euro", "1000 dollars") with no $/€/£/¥ symbol
  cjk              posts containing any CJK/Hangul/Kana codepoint
  hard_ads         posts containing hard-coded AdSense markup (adsbygoogle / data-ad-client)
  ins              posts containing any '<ins' HTML tag
  word400          posts whose body word count < 400
  h2lt3            posts with fewer than 3 '## ' H2 headings
  latex            posts containing LaTeX markers (\( \] \begin{ or $...$ )
  frontmatter_missing posts whose first non-empty line is not '---'
  total_posts      total index.md for the blog
"""
import csv, re, sys
from pathlib import Path

ROOT = Path("/Users/twinssn/Projects/ETAP")
OUT_CSV = Path("/Users/twinssn/Projects/5000/docs/superpowers/specs/2026-08-21-etap-audit-matrix.csv")

COLS = ["blog","table0","no_airlines","verified","currency_no_symbol","cjk",
        "hard_ads","ins","word400","h2lt3","latex","frontmatter_missing","total_posts"]

CJK_RE = re.compile(r'[一-鿿぀-ヿ가-힯]')
TABLE_SEP_RE = re.compile(r'^\s*\|?[\s:\-|]+\|[\s:\-|]*$')
TABLE_ROW_RE = re.compile(r'^\s*\|.*\|\s*$')
CURRENCY_RE = re.compile(r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(USD|EUR|GBP|JPY|Euro|euros|dollars?|won|Won)\b')
LATEX_RE = re.compile(r'\\\(|\\\[|\\begin\{|\$[^$\n]+\$')
DATE_RE = re.compile(r'^date:\s*[\'"]?\s*(\d{4}-\d{2})', re.M)
FIRST_RE = re.compile(r'^\s*---\s*$')

def body_words(text):
    fm_end = text.find('\n---', 3)
    body = text[fm_end+4:] if fm_end != -1 else text
    return len(re.findall(r"\S+", body))

def has_fm(text):
    # frontmatter block = starts with --- then closes with ---
    if not text.lstrip().startswith('---'):
        return False
    return text.find('\n---', 3) != -1

def has_table(text):
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if TABLE_ROW_RE.match(ln):
            # look at adjacent lines for a separator
            for j in (i-1, i, i+1):
                if 0 <= j < len(lines) and TABLE_SEP_RE.match(lines[j]) and j != i:
                    return True
    return False

def month_of(text):
    m = DATE_RE.search(text)
    return m.group(1) if m else "unknown"

rows = []
monthly = {}  # month -> {check: count}
for blog_dir in sorted(ROOT.glob("*-hugo")):
    posts = list((blog_dir / "content" / "posts").rglob("index.md"))
    if not posts:
        posts = list(blog_dir.rglob("index.md"))
    n = len(posts)
    c = {k: 0 for k in COLS if k != "blog"}
    for p in posts:
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        fm = has_fm(t)
        body = t
        if fm:
            end = t.find('\n---', 3)
            if end != -1:
                body = t[end+4:]
        if not has_table(t): c["table0"] += 1
        if not re.search(r'airline', t, re.I): c["no_airlines"] += 1
        if re.search(r'(?m)^verified\s*:', t): c["verified"] += 1
        if CURRENCY_RE.search(t): c["currency_no_symbol"] += 1
        if CJK_RE.search(t): c["cjk"] += 1
        if "adsbygoogle" in t or "data-ad-client" in t: c["hard_ads"] += 1
        if "<ins" in t: c["ins"] += 1
        if body_words(t) < 400: c["word400"] += 1
        if len(re.findall(r'(?m)^##\s', t)) < 3: c["h2lt3"] += 1
        if LATEX_RE.search(t): c["latex"] += 1
        if not fm: c["frontmatter_missing"] += 1
        mo = month_of(t)
        md = monthly.setdefault(mo, {k: 0 for k in COLS if k != "blog"})
        md["total_posts"] = md.get("total_posts", 0) + 1
        for key in ("table0","no_airlines","verified","currency_no_symbol","cjk",
                    "hard_ads","ins","word400","h2lt3","latex","frontmatter_missing"):
            if (key == "table0" and not has_table(t)) or \
               (key == "no_airlines" and not re.search(r'airline', t, re.I)) or \
               (key == "verified" and re.search(r'(?m)^verified\s*:', t)) or \
               (key == "currency_no_symbol" and CURRENCY_RE.search(t)) or \
               (key == "cjk" and CJK_RE.search(t)) or \
               (key == "hard_ads" and ("adsbygoogle" in t or "data-ad-client" in t)) or \
               (key == "ins" and "<ins" in t) or \
               (key == "word400" and body_words(t) < 400) or \
               (key == "h2lt3" and len(re.findall(r'(?m)^##\s', t)) < 3) or \
               (key == "latex" and LATEX_RE.search(t)) or \
               (key == "frontmatter_missing" and not fm):
                md[key] += 1
    c["total_posts"] = n
    rows.append((blog_dir.name, c))

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
with OUT_CSV.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(COLS)
    for name, c in rows:
        w.writerow([name] + [c[k] for k in COLS if k != "blog"])

# build markdown table strings
corpus_tbl = "| " + " | ".join(COLS) + " |\n"
corpus_tbl += "|" + "|".join(["---"]*len(COLS)) + "|\n"
tot = {k: 0 for k in COLS if k != "blog"}
for name, c in rows:
    corpus_tbl += "| " + name + " | " + " | ".join(str(c[k]) for k in COLS if k != "blog") + " |\n"
    for k in tot: tot[k] += c[k]
corpus_tbl += "| " + "TOTAL" + " | " + " | ".join(str(tot[k]) for k in COLS if k != "blog") + " |\n"

mcols = [k for k in COLS if k != "blog"]
monthly_tbl = "| month | " + " | ".join(mcols) + " |\n"
monthly_tbl += "|" + "|".join(["---"]*(len(mcols)+1)) + "|\n"
for mo in sorted(monthly.keys()):
    md = monthly[mo]
    monthly_tbl += "| " + mo + " | " + " | ".join(str(md.get(k, 0)) for k in mcols) + " |\n"

# write markdown spec
query_src = Path(__file__).read_text()
md_doc = f"""# ETAP Audit Matrix — Corpus Master Table

- **Generated**: 2026-08-21
- **Corpus**: 36 ETAP blogs under `/Users/twinssn/Projects/ETAP/*-hugo`
- **Input files**: {tot['total_posts']} `index.md` (scanned via `content/posts/**/index.md`)
- **Shape**: 36 rows (blogs) × 13 columns (checks + total_posts). A `TOTAL` row is appended.
- **Reproducible query**: the Python source embedded at the end of this document (run as `python3 etap_audit_matrix.py`).

## Check definitions

| column | definition |
| --- | --- |
| blog | Blog directory name (`*-hugo`) |
| table0 | posts with NO GitHub-Flavored markdown table (no `\\|` row adjacent to a `\\|-\\|` separator) |
| no_airlines | posts with zero case-insensitive token `airline` |
| verified | posts whose frontmatter contains a `verified:` key |
| currency_no_symbol | posts whose body has a bare currency-word amount (`21 USD`, `56 Euro`, `1000 dollars`) with no `$/€/£/¥` symbol |
| cjk | posts containing any CJK / Hangul / Kana codepoint |
| hard_ads | posts containing hard-coded AdSense markup (`adsbygoogle` or `data-ad-client`) |
| ins | posts containing any `<ins` HTML tag |
| word400 | posts whose body word count < 400 |
| h2lt3 | posts with fewer than 3 `## ` H2 headings |
| latex | posts containing LaTeX markers (`\\\\(`, `\\\\]`, `\\\\begin{{`, or `$...$`) |
| frontmatter_missing | posts whose first non-empty line is not `---` (no frontmatter block) |
| total_posts | total `index.md` for the blog |

## Corpus master table

{corpus_tbl}
## Monthly distribution (aggregated across 36 blogs, for regression)

Buckets by frontmatter `date:` → `YYYY-MM` (posts with no parsable date land in `unknown`).

{monthly_tbl}
## Query source

```python
{query_src}
```
"""
OUT_MD = OUT_CSV.with_suffix(".md")
OUT_MD.write_text(md_doc)

# also print to stdout
print(corpus_tbl)
print("\n## Monthly distribution (aggregated across 36 blogs)\n")
print(monthly_tbl)
print(f"\nWrote {OUT_CSV} and {OUT_MD}")

````
