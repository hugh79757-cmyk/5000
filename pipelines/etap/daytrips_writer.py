"""daytrips_writer.py - Day Trips guide generator (v2: curated, deduplicated)"""
import logging
import os
import re
import sqlite3
from difflib import SequenceMatcher

from pipelines.etap.quality_guard import preprocess_tours
from shared.ai_writer import generate as ai_generate

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
# === ETAP v2 Enrichment ===
try:
    from pipelines.etap.data_enricher import (
        format_context_for_prompt,
        get_airline_context,
        get_city_context,
        get_route_context,
    )
    from pipelines.etap.post_processor import (
        calculate_quality_metrics,
        clean_prompt_leaks,
        clean_tags,
        fix_encoding,
    )
    from pipelines.etap.prompt_angles import pick_city_angle, pick_flight_angle, pick_route_angle
    HAS_ENRICHMENT = True
except ImportError:
    HAS_ENRICHMENT = False
# === END ETAP v2 ===

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_price(val):
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except Exception:
        return 0


def fetch_city_meta(city):
    """viator_destinations에서 통화, 시간대, 언어, 좌표 가져오기"""
    conn = _get_db()
    row = conn.execute("""
        SELECT currency_code, timezone, country_calling_code, languages,
               latitude, longitude
        FROM viator_destinations
        WHERE name = ? AND type = 'CITY'
        LIMIT 1
    """, (city,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}


def fetch_tours(city, country=None):
    conn = _get_db()
    rows = conn.execute("""
        SELECT product_name, description, category, price, currency,
               discount_percent as discount, image_url, deep_link, city, country
        FROM viator_tours
        WHERE city = ? AND category IN ('Day Trips', 'Full-day Tours', 'Half-day Tours')
          AND deep_link IS NOT NULL AND deep_link != ''
        ORDER BY CAST(price AS REAL) ASC
    """, (city,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _deduplicate_tours(tours, similarity_threshold=0.85):
    """유사한 투어를 그룹핑하고 각 그룹에서 대표 1개만 선택."""
    if not tours:
        return []

    for t in tours:
        t["_clean_name"] = re.sub(r"^Save [\d.]+%!\s*", "", t.get("product_name", "")).strip()

    groups = []
    used = set()

    for i, t in enumerate(tours):
        if i in used:
            continue
        group = [t]
        used.add(i)
        for j in range(i + 1, len(tours)):
            if j in used:
                continue
            ratio = SequenceMatcher(
                None, t["_clean_name"].lower(), tours[j]["_clean_name"].lower()
            ).ratio()
            if ratio > similarity_threshold:
                group.append(tours[j])
                used.add(j)
        groups.append(group)

    result = []
    for group in groups:
        valid = [t for t in group if _safe_price(t.get("price")) >= 10]
        if not valid:
            valid = group
        with_img = [t for t in valid if t.get("image_url")]
        pool = with_img or valid
        best = sorted(pool, key=lambda x: _safe_price(x.get("price")))[0]
        best["_group_size"] = len(group)
        best["_group_price_range"] = (
            min(_safe_price(t.get("price")) for t in group),
            max(_safe_price(t.get("price")) for t in group),
        )
        result.append(best)

    return result


def _build_summary(tours, city, city_meta):
    """GPT에 전달할 풍부한 데이터 요약 생성"""
    total = len(tours)
    if total == 0:
        return None, None

    categories = {}
    for t in tours:
        cat = t.get("category", "Other")
        categories[cat] = categories.get(cat, 0) + 1

    budget = [t for t in tours if 10 <= _safe_price(t.get("price")) < 50]
    mid = [t for t in tours if 50 <= _safe_price(t.get("price")) <= 150]
    premium = [t for t in tours if _safe_price(t.get("price")) > 150]

    picks = {
        "budget": sorted(budget, key=lambda x: _safe_price(x.get("price")))[:3],
        "mid_range": sorted(mid, key=lambda x: _safe_price(x.get("price")))[:3],
        "premium": sorted(premium, key=lambda x: -_safe_price(x.get("price")))[:3],
    }

    currency = city_meta.get("currency_code", "USD")
    tz = city_meta.get("timezone", "")
    lang = city_meta.get("languages", "")
    lat = city_meta.get("latitude", "")
    lon = city_meta.get("longitude", "")

    all_prices = [_safe_price(t.get("price")) for t in tours if _safe_price(t.get("price")) > 0]
    min_price = min(all_prices) if all_prices else 0
    max_price = max(all_prices) if all_prices else 0

    summary = "CITY CONTEXT:\n"
    summary += f"City: {city}\n"
    summary += f"Local currency: {currency}\n"
    summary += f"Timezone: {tz}\n"
    summary += f"Languages: {lang}\n"
    summary += f"Coordinates: {lat}, {lon}\n\n"
    summary += f"TOUR DATA (deduplicated from {total} unique tours):\n"
    summary += "Categories: " + ", ".join(f"{c} ({n})" for c, n in sorted(categories.items(), key=lambda x: -x[1])) + "\n"
    summary += f"Price range: ${min_price:.0f} - ${max_price:.0f} {currency}\n\n"

    for label, items in picks.items():
        if items:
            summary += f"[{label.upper()} - TOP 3 PICKS]\n"
            for t in items:
                name = re.sub(r"^Save [\d.]+%!\s*", "", t.get("product_name", ""))
                price = _safe_price(t.get("price"))
                cat = t.get("category", "")
                group_size = t.get("_group_size", 1)
                price_lo, price_hi = t.get("_group_price_range", (price, price))
                desc_short = (t.get("description", "") or "")[:120]
                summary += f"- {name} | ${price:.0f} {currency} | {cat}"
                if group_size > 1:
                    summary += f" | {group_size} similar tours (${price_lo:.0f}-${price_hi:.0f})"
                summary += f"\n  Brief: {desc_short}\n"
            summary += "\n"

    # 빈약한 요약이면 AI 호출 전에 조기 실패 (데이터 부족)
    if len(summary) < 300:
        logger.warning(f"[daytrips] {city}: summary too short ({len(summary)} chars) — 데이터 부족, AI 호출 차단")
        return None, None
    return summary, picks


def generate_daytrips_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")

    tours = fetch_tours(city, country)
    tours, _pre_issues, _excluded = preprocess_tours(tours, city=city)
    if not tours:
        logger.warning(f"No tours for {city}")
        return None

    city_meta = fetch_city_meta(city)
    currency = city_meta.get("currency_code", "USD")

    original_count = len(tours)
    tours = _deduplicate_tours(tours)
    dedup_count = len(tours)
    logger.info(f"[daytrips] {city}: {original_count} tours -> {dedup_count} after dedup")

    result = _build_summary(tours, city, city_meta)
    if not result:
        return None
    summary, _picks = result

    prompt = f"""Write a day trips guide for {city}, {country}.

{summary}

ARTICLE REQUIREMENTS:
- 1,200-1,800 words in English
- All prices in {currency} (the local currency shown in data)
- If a price section has 0 tours in the data, OMIT that H2 section entirely. Do NOT write filler content.
- Use ONLY the tour names and prices from the data above
- Do NOT invent any tour names, prices, or statistics

TITLE (REQUIRED — first line, H1 format):
# [Write a unique, specific title for {city}. RULES:
  - Must start with "# "
  - NEVER use: "Hidden Gems", "Top Excursions", "Ultimate Guide", "Unforgettable"
  - Use a specific angle: e.g. "Day Trips From {city}: Beaches, Ruins & Safari in One Day" or "Escaping {city}: The Best Day Trips by Budget" or "{city} Day Trip Guide: Castles, Coasts & Mountain Roads"
  - Vary the structure each time — do NOT repeat the same subtitle pattern]

STRUCTURE (use these H2 headings — in this order, all required):
- Start with a 2-3 sentence introduction paragraph BEFORE any heading. Put the concrete hook here as plain text — do NOT put it in an H2.
## Best Budget Day Trips
## Mid-Range Excursions Worth the Upgrade
## Premium Full-Day Experiences
## When to Go (Best Season & Month)
## Getting There & Local Transport
## Planning Your Day Trip
## FAQ

WRITING RULES:
1. OPENING: Start with a concrete hook. Example style: "A 20-minute taxi from downtown drops you at the foot of 4,500-year-old pyramids, the driver waving you toward the trailhead." Do NOT start with generic overview sentences. Do NOT attach any invented transport or entry price to the scene.
2. CURATION: For each price section, feature 2-3 tours maximum. For each tour write 2-3 sentences explaining WHAT makes it worth choosing, WHO it suits best, and one PRACTICAL TIP.
3. COMPARISON: When multiple tours cover the same attraction, tell the reader which one to pick and why.
4. WHEN TO GO: Give a month-by-month or seasonal take — which months have best weather, lowest crowds, or shoulder-season deals. Be specific to {city}.
5. GETTING THERE: Cover how to reach the day-trip bases from {city} (train/bus/ferry/car), typical fares in {currency}, and one booking tip.
6. PLANNING: Include local currency tips, best day of week, what to wear, water and food advice.
7. FAQ: Answer 3 real reader questions (e.g. "Can I do this without a car?", "Is it safe for solo travelers?", "What if it rains?"). Keep each answer 2-3 sentences.
8. TONE: Write as a knowledgeable friend who has been there. Use "you" directly. Include subjective opinions.
9. FORMAT: Flowing paragraphs only. NO numbered lists, NO bullet points. Bold tour names on first mention.
10. CLOSING: End with a single "If you only have one day" recommendation with specific tour name and price.
11. NEVER use: plethora, vibrant, bustling, embark, tapestry, myriad, hidden gem, unforgettable, crystal-clear, soak in, immerse yourself, lets dive in, without further ado, a testament to, culinary delights, gastronomic, rich cultural heritage, seamlessly, breathtaking, brimming with, a must-visit, treasure trove, staggering"""

    SYSTEM_PROMPT = ("You are a travel writer who has visited these destinations. Write in second-person informed tone. "
    "STRICT RULES: 1) Use ONLY tour names and prices from the provided data. 2) Write in flowing paragraphs, "
    "NEVER use numbered lists or bullet points. 3) Each section must include at least one practical tip. "
    "4) Compare tours against each other. 5) Format prices as whole numbers when .0. 6) Open with a specific "
    "concrete scene or fact. 7) NEVER use: plethora, vibrant, bustling, tapestry, myriad, embark, hidden gem, "
    "unforgettable, crystal-clear, soak in, immerse yourself, lets dive in, without further ado, a testament to, "
    "seamlessly, breathtaking, brimming, culinary delights, gastronomic, staggering, rich cultural heritage, "
    "treasure trove, a must-visit.")

    # ponytail: self-correct loop — gate hard-min is 3 H2 / 400 words; enforce a 600-word floor
    # so published posts clear the gate on first try instead of burning tokens on repeated full regenerations.
    last_issues: list[str] = []
    content = ""
    for _attempt in range(3):  # 1 initial + up to 2 self-corrections
        if last_issues:
            gen_prompt = (prompt + "\n\nPREVIOUS DRAFT REJECTED — fix these and rewrite the FULL article: "
                          + "; ".join(last_issues) + ".")
        else:
            gen_prompt = prompt
        result = ai_generate(SYSTEM_PROMPT, gen_prompt, temperature=0.6, max_tokens=3500)
        content = result["content"].strip()
        h2 = len(re.findall(r"^##\s+", content, re.MULTILINE))
        wc = len(content.split())
        if h2 >= 3 and wc >= 600:
            break
        last_issues = []
        if h2 < 3:
            last_issues.append(f"only {h2} H2 sections, MUST have at least 3 '##' headings")
        if wc < 600:
            last_issues.append(f"only {wc} words, MUST be at least 600 (target 1000-1500)")
        logger.warning(f"[daytrips] quality self-correct attempt {_attempt+1}/3: {last_issues}")

    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Best Day Trips from {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()

    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-"))
    tags = [city, country, "Day Trips", "Travel"] if country else [city, "Day Trips", "Travel"]

    return {
        "title": title,
        "slug": slug,
        "content": content,
        "description": f"Best day trips from {city}: hand-picked tours with real prices, practical tips, and honest comparisons.",
        "tags": [t for t in tags if t],
        "city": city,
        "country": country,
        "tours": tours,
    }
