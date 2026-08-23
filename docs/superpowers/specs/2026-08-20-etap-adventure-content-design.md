# ETAP — adventure Branch Content Design

**Status:** DESIGN_DRAFT — NOT APPROVED
**Date:** 2026-08-20
**Scope:** `adventure-hugo` (adventure.techpawz.com) ONLY
**Companion discovery:** `2026-08-20-etap-auto-branches-discovery.md`
**Method:** Superpowers Design — grounded in actual code / DB schema / live rendered post. No invented disclosure text, no invented legal rules, no invented tracking params.

---

## 1. Scope & Boundaries (enforced)

| In scope | Out of scope (explicitly excluded) |
|---|---|
| `adventure-hugo` content pipeline, prompt, post-processing, quality gates, live evidence | SG-A2 (luxury/extreme/citytours/tour), other ETAP branches |
| Verified current behavior + content-design spec derived from it | Deploy-path fix (`env -u CLOUDFLARE_API_TOKEN`), any code change |
| UNRESOLVED items flagged for human/legal decision | Writing-plans, implementation, commit |

This design does **not** modify code, config, or DB. It documents the content contract for the adventure branch and isolates decisions that require external input (legal/FTC, disclosure wording, tracking policy).

---

## 2. Verified Current Architecture (adventure)

All evidence from direct file reads (no execution).

### 2.1 Pipeline flow
`dispatcher.py:465-475` → `pipelines.etap.adventure_pipeline` → `run()` (adventure_pipeline.py:151-153) → `_normalize_result(_run_impl())` (pipelines/etap/_contract.py:27-58).
`_run_impl` (adventure_pipeline.py:113-148):
1. `pick_topic` → `adventure_topics` row
2. `generate_adventure_guide` (adventure_writer.py:86-157)
3. `postprocess_content` (quality_guard.py:235-486)
4. `if is_draft` → stop + `send_alert` (129-132)
5. `_add_product_cards` (135) — Viator tour cards
6. `fetch_city_image` / `fetch_body_images` (138-139)
7. `_write_hugo_post` via `_write_hugo_post_etap` (140)
8. `_mark_published` (141)
9. `register_entity` (city, country) (143-147)

Daily quota = 5 (`run_batch` 157-171).

### 2.2 Prompt / content shape (adventure_writer.py:99-138)
- **H2 structure (6 sections):** `Why {city} is an Adventure Hotspot` / `Best Hiking Tours in {city}` / `Extreme Sports and Adrenaline Rushes` / `Mountain Biking and Cycling Adventures` / `Best Deals on Adventure Activities` / `Safety Tips and What to Bring`
- **Rules:** 1200–1800 words; **no booking links / URLs inside body prose**; no fabricated facts; omit empty sections; banned title phrases; **ONE natural CTA near end**; `Quick Facts` table; `Quick Comparison` sentence; name + price for "best value" / "splurge" picks.
- `ai_generate` temp 0.5, max_tokens 4000 (140-145).

### 2.3 Data input
`adventure_writer.py:30-41` `fetch_tours` → `viator_tours` WHERE `city=?` AND `category IN ('Extreme Sports','Hiking Tours','Mountain Bike Tours','Climbing Tours','Nature and Wildlife Tours','4WD Tours','Rafting','White Water Rafting','Paragliding','Ziplining')` AND `deep_link NOT NULL` ORDER BY price ASC.

### 2.4 Affiliate (verified)
- Provider: **Viator** only (`viator_tours.deep_link`). No Airalo / Omio / Aviasales / Coupang.
- Link injection: `post_processor.insert_product_cards` (9-82) builds `[Book Now](deep_link)` cards. **No runtime tracking params** — adventure uses raw `deep_link` (SG-A raw variant; `_affiliate_link` not present in adventure_pipeline.py).
- **Live evidence (kusadasi-adventure, m0085):** `viator.com`×6 links; **zero** `?pid` / `?mcid` / `?campaign` on any link.

### 2.5 Disclosure (verified absence)
- `quality_guard.postprocess_content` force-appends `etap-disclaimer-card` (474-484): *"Prices, schedules ... based on data at the time of writing ... verify current details on the official website before booking."* — this is an **informational price/schedule disclaimer, NOT an affiliate/commission disclosure**.
- `hugo_writer._insert_disclaimer_before_first_affiliate` (1241-1259) triggers **only** on `link.coupang.com` (regex `_affiliate_link_re`). Viator links are not covered → **no affiliate disclosure is inserted for Viator**.
- **Live evidence (m0085):** `etap-disclaimer-card` present; **zero** "affiliate"/"commission"/"may earn" disclosure text.

### 2.6 Entity linker (verified)
`shared/entity_linker.py`: `register_entity` (73-96) → `entity_links`; `inject_internal_links` (163-274, max_links=5, first-occurrence, skip H1/H2, skip self-blog); `build_cross_sell_html` (277-337, "More about {city/country}", max_items=3). `adventure-hugo` registered in `BLOG_DOMAINS` (40). Injected via `_write_hugo_post_etap` (inject_internal_links=True, cross_sell_config max_items:3, position:bottom).

### 2.7 Thumbnail (verified)
`image_fetcher.py`: Pexels (primary) + Unsplash (fallback); `fetch_city_image` (216-260) → R2 `etap/{slug}/cover.jpg` (webp via `_upload_to_r2` 175-186); `fetch_body_images` (263-294) → `etap/{slug}/body_%d.jpg`; `used_images` dedup (34-65).

### 2.8 Output / front matter (verified)
`_write_hugo_post_etap` (1346-1452): guards empty / <200 words; theme Blowfish; `_build_frontmatter_blowfish` (194-231): `title/date/draft/description/slug/categories/tags/featureimage`. `featureimage` = cover R2 URL.

### 2.9 Quality gates already present (verified, quality_guard.py)
- Tour validation: `MIN_PRICE 8` / `MAX_PRICE 50000` / `MAX_DISCOUNT 60`, `deep_link` must start `http` (validate_tour 74-114, preprocess_tours 116-136).
- Price hallucination vs `data_prices`: sentence removal; ≥3 → draft (235-486).
- `$0` → draft; `$100000+` → draft.
- Unauthorized URL removal (allowlist: `r2.dev`, `techpawz.com`, `googlesyndication.com`).
- Duplicate CTA removal; empty-H2 removal; fabricated `/posts/` link removal (checks `entity_links.published`).
- `H2 < 3` → draft; `word < 400` → draft; `benefit_connection_issues` → draft.

### 2.10 AdSense (verified live)
Live post contains `ca-pub-8772455780561463` (rotcha/techpawz family) — correct mapping per AGENTS.md publisher-ID governance.

---

## 3. Content Design Spec (adventure) — derived, not invented

The "good adventure post" contract, reconstructed from the verified prompt + gates above:

| Layer | Spec |
|---|---|
| Topic source | `adventure_topics` (city, country, tour_count, priority, exhausted) |
| Body structure | 6 fixed H2s (§2.2); omit empty; no prose URLs |
| Length | 1200–1800 words; <400 → draft |
| Facts | From `viator_tours` only; no fabrication; price range $8–$50000, discount ≤60% |
| CTA | Exactly ONE natural CTA near end (prompt-enforced) + Viator "Book Now" cards (post-processor) |
| Cards | `Top Tours & Activities` (max 5) with name/price/[Book Now]; comparison table optional |
| Cross-links | Internal entity links (max 5) + bottom cross-sell card (max 3, same city/country) |
| Disclaimer | `etap-disclaimer-card` (price/schedule info) — present |
| Affiliate disclosure | **ABSENT** (see §4) |
| Media | Pexels/Unsplash cover + body images → R2 `etap/{slug}/...` |
| Front matter | Blowfish; featureimage = cover |

---

## 4. UNRESOLVED — must NOT be invented here

Per instruction, the following are flagged **UNRESOLVED** and require human/legal decision. This design does not propose wording, legal citations, or tracking values.

| # | Item | Why unresolved | What is needed |
|---|------|----------------|----------------|
| U1 | **Affiliate disclosure text** (Viator) | No such text exists in code or live render; FTC-style "we may earn a commission" wording is a legal/compliance decision, not derivable from repo | Human/legal to supply exact disclosure string + insertion rule (e.g., before first Viator link) |
| U2 | **Legal/regulatory rule citation** (FTC §5, etc.) | External law, not present in repo; cannot be invented as "verified" | Cite authoritative source; confirm applicability to Viator partner links |
| U3 | **Tracking param policy** | adventure uses raw `deep_link` with no `pid/mcid/campaign` (live-confirmed). Whether to add runtime tracking is a business/affiliate decision | Decide: keep raw (collection-time bake) vs adopt `_affiliate_link` (SG-A2 style) |
| U4 | **Deploy path** | `env -u CLOUDFLARE_API_TOKEN` missing in etap (CONFIRMED violation of AGENTS.md) — out of scope for this content design | Separate fix track (not here) |

---

## 5. Residual Risk (this design only)

- **U1/U2 open** means adventure posts currently ship Viator affiliate links with **no affiliate disclosure** (live-confirmed). This is a compliance gap, not a code bug this design resolves.
- **SG-A2 divergence:** luxury/extreme/citytours/tour inject tracking params; adventure does not. Content-design parity across SG-A is a later design step (excluded here).
- Discovery-doc items (other 34 blogs) remain separate; this design covers adventure exclusively.

---

## 6. Next Design Candidates (not written here)

1. Affiliate-disclosure design (resolves U1/U2) — needs human/legal input first.
2. SG-A unified content design (adventure + raw-Viator siblings) — after U3 decided.
3. Quality-gate hardening (e.g., enforce disclosure presence as a draft gate).

**Approval requested before any of the above is drafted or any code/config/DB change is made.**
