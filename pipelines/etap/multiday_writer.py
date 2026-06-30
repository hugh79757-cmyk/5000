"""multiday_writer.py - Multi-day tour guide generator"""
import logging
import os
import re
import sqlite3

from pipelines.etap.quality_guard import preprocess_tours
from shared.ai_writer import generate as ai_generate

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
try:
    from pipelines.etap.post_processor import clean_prompt_leaks, clean_tags, fix_encoding
    HAS_PP = True
except ImportError:
    HAS_PP = False

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _safe_price(val):
    try:
        return float(str(val).replace("$","").replace(",","").strip())
    except:
        return 0

def fetch_tours(city, country=None):
    conn = _get_db()
    rows = conn.execute("""
        SELECT product_name, description, category, price, currency,
               discount_percent as discount, image_url, deep_link, city, country
        FROM viator_tours
        WHERE city = ? AND category IN ('Multi-day Tours', 'Multi-day Cruises', 'Honeymoon Packages', 'Overnight Tours', 'Rail Tours')
          AND deep_link IS NOT NULL AND deep_link != ''
        ORDER BY CAST(price AS REAL) ASC
    """, (city,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _build_summary(tours, city):
    total = len(tours)
    if total == 0:
        return None
    categories = {}
    discounted = []
    for t in tours:
        cat = t.get("category") or "Other"
        categories[cat] = categories.get(cat, 0) + 1
        disc = t.get("discount") or ""
        if disc and str(disc) not in ("0", "", "0.0"):
            discounted.append(t)

    budget = [t for t in tours if 0 < _safe_price(t.get("price")) < 200]
    mid = [t for t in tours if 200 <= _safe_price(t.get("price")) <= 800]
    premium = [t for t in tours if _safe_price(t.get("price")) > 800]
    picks = {
        "budget": budget[:5],
        "mid": mid[:5],
        "premium": premium[:5],
        "deals": sorted(discounted, key=lambda x: x.get("discount","0"), reverse=True)[:5],
    }
    top_cats = sorted(categories.items(), key=lambda x: -x[1])[:10]
    summary = f"City: {city}\nTotal multi-day tours: {total}\n"
    summary += f"Discounted: {len(discounted)}\n"
    summary += "Categories: " + ", ".join(f"{c} ({n})" for c,n in top_cats) + "\n"

    for label, items in picks.items():
        if items:
            summary += f"[{label.upper()} PICKS]\n"
            for t in items:
                nm = re.sub(r"^Save [\d.]+%!\s*", "", t["product_name"])
                summary += f"- {nm} | ${t['price']} {t['currency']} | {t['category']}\n"
            summary += "\n"
    return summary, picks

def generate_multiday_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")
    tours = fetch_tours(city, country)
    tours, _pre_issues, _excluded = preprocess_tours(tours, city=city)
    if not tours:
        logger.warning(f"No multi-day tours for {city}")
        return None
    result = _build_summary(tours, city)
    if not result:
        return None
    summary, _picks = result

    prompt = f"""Write a multi-day tour guide for travelers departing from {city}, {country}.

DATA (use ONLY this data, do NOT invent tours or prices):
{summary}

RULES:
- Write 1,200-1,800 words in English
- Do NOT include any booking links or URLs in the text
- Do NOT invent tour names, prices, or categories not in the data
- Title must include "{city}" and "Multi-Day" or "Multi-Day Tours"
- Required H2 sections:
  ## Why Book a Multi-Day Tour From {city}
  ## Top Multi-Day Tours in {city} (feature 3-5 best tours, grouped by theme or duration)
  ## Prices and What's Included
- ONLY mention tours and prices that appear in the DATA above. Do NOT estimate or invent ANY price
- If a section has fewer than 2 tours in the data, OMIT that H2 section entirely
  ## Best Deals on Multi-Day Tours
  ## What Is Typically Included (and What Is Not)
  ## How to Choose the Right Multi-Day Tour
- For each tour mentioned, include exact name and price from the data
- Remove "Save XX%!" prefixes from tour names
- If a section has no matching data, OMIT that H2 section entirely. Do NOT write filler content
- Write as an experienced traveler who has done multi-day tours and knows what matters
- Weave tours into flowing paragraphs, not numbered lists
- Include practical tips: packing, group size expectations, solo vs couple, tipping guides
- After mentioning 2-3 tours per section, add a natural CTA
- End with best value pick and best premium pick by name and price

Return ONLY the article in markdown starting with # title"""

    result = ai_generate(
    "You are a travel blogger who specializes in multi-day group tours. Write in first-person-informed tone. STRICT RULES: 1) Never use: plethora, vibrant, bustling, let\\'s dive in, without further ado, hidden gem, tapestry, myriad, embark, unforgettable, crystal-clear, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Format prices as whole numbers when .0. 3) NEVER invent data. If a price is not in the provided DATA, do NOT mention it. Do NOT estimate prices. 4) Every section must include one practical tip (what hotel tier to expect, group size reality, tipping the guide, packing for overnight). 5) Open with a concrete itinerary snapshot or a distance/time detail.",
    prompt,
    temperature=0.5,
    max_tokens=4000,
    )
    content = result["content"].strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Multi-Day Tours From {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-") + "-multiday-tours")
    tags = [city, country, "Multi-Day Tours", "Tour Packages", "Travel"] if country else [city, "Multi-Day Tours", "Tour Packages", "Travel"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Best multi-day tours from {city}: budget to luxury itineraries, prices, and practical booking tips.",
        "tags": [t for t in tags if t], "city": city, "country": country,
        "tours": tours,
    }
