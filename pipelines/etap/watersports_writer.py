"""watersports_writer.py - Water Sports guide generator"""
import os, sqlite3, logging, re
from openai import OpenAI
from pipelines.etap.quality_guard import preprocess_tours, postprocess_content, clean_tour_name
from pipelines.etap.tour_utils import fetch_city_meta, deduplicate_tours, build_city_context, build_picks_summary

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
_client = None

def _get_client():
    global _client
    if not _client:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

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
        WHERE city = ? AND category IN ('Water Tours', 'Sailing', 'Snorkeling', 'Jet Boat Rentals', 'Kayaking Tours', 'Surfing Lessons')
          AND deep_link IS NOT NULL AND deep_link != ''
        ORDER BY CAST(price AS REAL) ASC
    """, (city,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _build_summary(tours, city, city_meta=None):
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

    sailing = [t for t in tours if t.get("category") in ("Sailing", "Water Tours")]
    snorkeling = [t for t in tours if t.get("category") in ("Snorkeling", "Kayaking Tours", "Surfing Lessons")]
    budget = [t for t in tours if 0 < _safe_price(t.get("price")) < 50]
    picks = {
        "sailing": sailing[:5],
        "snorkeling": snorkeling[:5],
        "budget": budget[:5],
        "deals": sorted(discounted, key=lambda x: x.get("discount","0"), reverse=True)[:5],
    }
    top_cats = sorted(categories.items(), key=lambda x: -x[1])[:10]
    summary = f"City: {city}\nTotal tours: {total}\n"
    summary += f"Discounted: {len(discounted)}\n"
    summary += "Categories: " + ", ".join(f"{c} ({n})" for c,n in top_cats) + "\n"

    summary += f"Sailing/boat tours: {len(sailing)}\n"
    summary += f"Snorkeling/diving: {len(snorkeling)}\n"
    summary += f"Budget options: {len(budget)}\n\n"

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

def generate_watersports_guide(topic):
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
    summary, picks = result

    prompt = f"""Write a comprehensive water sports guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent tours or prices):
{summary}

RULES:
- Write 1,200-1,800 words in English
- Do NOT include any booking links or URLs in the text
- Do NOT invent tour names, prices, or categories not in the data
- Title must include "{city}" and be SEO-friendly
- Required H2 sections:
  ## Why {city} is Perfect for Water Activities
  ## Sailing and Boat Tours
  ## Snorkeling and Diving Experiences
  ## Budget Water Activities Under $50
  ## Best Deals on Water Sports
  ## What to Know Before Booking Water Activities in {city}
- For each tour mentioned, include exact name and price from the data
- If a section has no data, skip it gracefully
- Write naturally with engaging prose, not a list dump
- Include practical tips (best time, what to wear, booking advice)
- End with a brief practical summary
- Remove "Save XX%!" prefixes from tour names when mentioning them
- After mentioning 2-3 tours in each section, add a natural CTA like "These tours fill up fast during peak season — check availability and lock in today's price before it changes."
- Do NOT use numbered lists for tours. Weave them into flowing paragraphs
- Include a "Quick Comparison" sentence at the end of each price section (e.g., "At $15, the catamaran tour offers the best value per hour compared to the $50 private option.")
- Make the summary actionable: mention the best overall value pick and the best splurge pick by name and price

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.5, max_tokens=4000,
        messages=[
            {"role":"system","content":"You are a water sports travel blogger. Write in first-person-informed tone. STRICT RULES: 1) Never use: plethora, vibrant, bustling, let\'s dive in, without further ado, hidden gem, tapestry, myriad, embark, crystal-clear, crystal-clear waters, soak in, immerse yourself. 2) Format prices as whole numbers when .0. 3) Never invent data. 4) Every section must include one practical tip (water temperature, what to bring, seasickness warning, best time of day for calm water). 5) Open with a sensory detail about the water or coastline."},
            {"role":"user","content": prompt}
        ]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Best Water Sports in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-"))
    tags = [city, country, "Water Sports", "Travel"] if country else [city, "Water Sports", "Travel"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Water sports in {city}: sailing, snorkeling, kayaking with real prices and booking tips.".replace("{city}", city),
        "tags": [t for t in tags if t], "city": city, "country": country,
        "tours": tours,
    }
