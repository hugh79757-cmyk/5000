"""adventure_writer.py - Adventure guide generator"""
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
        WHERE city = ? AND category IN ('Extreme Sports', 'Hiking Tours', 'Mountain Bike Tours', 'Climbing Tours', 'Nature and Wildlife Tours', '4WD Tours', 'Rafting', 'White Water Rafting', 'Paragliding', 'Ziplining')
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

    hiking = [t for t in tours if t.get("category") == "Hiking Tours"]
    extreme = [t for t in tours if t.get("category") == "Extreme Sports"]
    biking = [t for t in tours if t.get("category") in ("Mountain Bike Tours", "Climbing Tours")]
    picks = {
        "hiking": hiking[:5],
        "extreme": extreme[:5],
        "biking": biking[:5],
        "deals": sorted(discounted, key=lambda x: x.get("discount","0"), reverse=True)[:5],
    }
    top_cats = sorted(categories.items(), key=lambda x: -x[1])[:10]
    summary = f"City: {city}\nTotal tours: {total}\n"
    summary += f"Discounted: {len(discounted)}\n"
    summary += "Categories: " + ", ".join(f"{c} ({n})" for c,n in top_cats) + "\n"

    summary += f"Hiking tours: {len(hiking)}\n"
    summary += f"Extreme sports: {len(extreme)}\n"
    summary += f"Mountain biking: {len(biking)}\n\n"

    # --- Include actual tour names + prices in summary for GPT ---
    for section_key, section_tours in picks.items():
        if section_tours:
            summary += f"\n[{section_key.upper()} PICKS]\n"
            for t in section_tours:
                name = t.get("product_name", "Unknown")
                price = t.get("price", "N/A")
                cat = t.get("category", "")
                summary += f"  - {name} | ${price} | {cat}\n"

    return summary, picks

def generate_adventure_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")
    tours = fetch_tours(city, country)
    tours, _pre_issues, _excluded = preprocess_tours(tours, city=city)
    if not tours:
        logger.warning(f"No tours for {city}")
        return None
    result = _build_summary(tours, city)
    if not result:
        return None
    summary, _picks = result

    prompt = f"""Write a comprehensive adventure guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent tours or prices):
{summary}

FORMAT (informational style — short paragraphs, tables, clear H3 breaks):
- Opening paragraph: 2-3 sentences telling readers exactly what this guide covers (hikes, extreme sports, bike tours, real prices) and who it is for
- ## Quick Facts: a compact markdown table of key data — total tours found, price range, top categories, cheapest and most expensive tour from the data
- ## Detailed sections: keep the required H2 sections; inside each, use ### for each individual tour with its exact name, price, and a 1-2 line description
- ## Practical Checklist: a short bullet checklist of what to bring and key tips (gear, fitness, safety, best season)
- ## Closing: a clear recommendation (best value pick + best splurge pick by name and price) and a note to re-check current prices and availability before booking
- Keep paragraphs short (2-4 sentences); let tables and ### sub-sections carry the details

RULES:
- Write 1,200-1,800 words in English
- Do NOT include any booking links or URLs in the text
- Do NOT invent tour names, prices, categories, or timings not in the data
- Title must include "{city}" and be SEO-friendly
- Required H2 sections:
  ## Why {city} is an Adventure Hotspot
  ## Best Hiking Tours
  ## Extreme Sports and Adrenaline Rushes
  ## Mountain Biking and Cycling Adventures
  ## Best Deals on Adventure Activities
  ## Safety Tips and What to Bring
- For each tour mentioned, include exact name and price from the data
- If a section has 0 tours in the data, OMIT that H2 section entirely. Do NOT write it with filler content
- NEVER use these in the title: "Awaits", "Ultimate Guide", "Your Guide To", "Everything You Need"
- Title format: "{city} Adventure Guide: [specific activity] with Prices and Tips"
- Write naturally with engaging prose, not a list dump
- Include practical tips (best time, what to wear, booking advice)
- End with a brief practical summary
- Remove "Save XX%!" prefixes from tour names when mentioning them
- Add ONE natural CTA near the end of the article (not in every section). Example: "Peak season fills up fast — check availability before prices change."
- Do NOT use numbered lists for tours. Weave them into flowing paragraphs
- If a section has fewer than 2 tours, merge it into the nearest relevant section rather than padding with unrelated content
- Include a "Quick Comparison" sentence at the end of each price section (e.g., "At $15, the catamaran tour offers the best value per hour compared to the $50 private option.")
- Make the summary actionable: mention the best overall value pick and the best splurge pick by name and price

Return ONLY the article in markdown starting with # title"""

    result = ai_generate(
    "You are an adventure travel blogger who has done these activities. Write in first-person-informed tone. STRICT RULES: 1) Never use: plethora, vibrant, bustling, let\\'s dive in, without further ado, hidden gem, tapestry, myriad, embark, adrenaline junkie, crystal-clear, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Format prices as whole numbers when .0. 3) Never invent data. 4) Every section must include one practical tip (fitness level needed, what to bring, safety considerations, best season). 5) Open with an action scene or physical sensation.",
    prompt,
    temperature=0.5,
    max_tokens=4000,
    )
    content = result["content"].strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Best Adventure in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-"))
    tags = [city, country, "Adventure", "Travel"] if country else [city, "Adventure", "Travel"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Adventure activities in {city}: hiking, extreme sports, mountain biking with real prices and expert tips.".replace("{city}", city),
        "tags": [t for t in tags if t], "city": city, "country": country,
        "tours": tours,
    }
