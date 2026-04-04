"""transfers_writer.py - Airport and hotel transfer guide generator"""
import os, sqlite3, logging, re
from openai import OpenAI
from pipelines.etap.quality_guard import preprocess_tours, postprocess_content, clean_tour_name

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
        WHERE city = ? AND category IN (
            'Airport & Hotel Transfers', 'Port Transfers',
            'Private Transfers', 'Water Transfers', 'Private Drivers', 'Bus Services'
        )
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
    for t in tours:
        cat = t.get("category") or "Other"
        categories[cat] = categories.get(cat, 0) + 1

    shared = [t for t in tours if _safe_price(t.get("price")) < 50]
    private = [t for t in tours if _safe_price(t.get("price")) >= 50]
    picks = {
        "shared_shuttle": shared[:5],
        "private_transfer": private[:5],
    }
    top_cats = sorted(categories.items(), key=lambda x: -x[1])[:10]
    summary = f"City: {city}\nTotal transfer options: {total}\n"
    summary += "Categories: " + ", ".join(f"{c} ({n})" for c,n in top_cats) + "\n"

    for label, items in picks.items():
        if items:
            summary += f"[{label.upper().replace('_',' ')}]\n"
            for t in items:
                nm = re.sub(r"^Save [\d.]+%!\s*", "", t["product_name"])
                summary += f"- {nm} | ${t['price']} {t['currency']} | {t['category']}\n"
            summary += "\n"
    return summary, picks

def generate_transfers_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")
    tours = fetch_tours(city, country)
    tours, _pre_issues, _excluded = preprocess_tours(tours, city=city)
    if not tours:
        logger.warning(f"No transfer tours for {city}")
        return None
    result = _build_summary(tours, city)
    if not result:
        return None
    summary, picks = result

    prompt = f"""Write an airport and hotel transfer guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent transfers or prices):
{summary}

RULES:
- Write 1,000-1,500 words in English
- Do NOT include any booking links or URLs in the text
- Do NOT invent transfer names, prices, or categories not in the data
- Title must include "{city}" and "Transfer" or "Airport"
- Required H2 sections:
  ## Getting From the Airport to {city} City Center
  ## Shared Shuttles and Budget Options
  ## Private Transfers: Comfort and Convenience
  ## Port Transfers (only if port transfer data exists)
  ## How to Choose the Right Transfer
  ## Booking Tips and What to Know Before You Land
- For each transfer mentioned, include exact name and price from the data
- Remove "Save XX%!" prefixes from transfer names
- If a section has no matching data, skip it gracefully
- Write as a frequent traveler who knows the hassle of airport arrivals
- Compare shared vs private options with specific price differences
- Include practical tips: meeting points, luggage, late flights, tipping
- End with a clear recommendation for different traveler types

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.5, max_tokens=3500,
        messages=[
            {"role": "system", "content": "You are a practical travel blogger who has landed at airports worldwide. Write in first-person-informed tone. STRICT RULES: 1) Never use: plethora, vibrant, bustling, let\'s dive in, without further ado, hidden gem, tapestry, myriad, embark, seamless, crystal-clear, soak in, immerse yourself. 2) Format prices as whole numbers when .0. 3) Never invent data. 4) Every section must include one practical tip (where the driver meets you, luggage limits, late flight contingency, tipping customs). 5) Open with the specific airport arrival experience."},
            {"role": "user", "content": prompt}
        ]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Airport Transfers in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-") + "-transfers")
    tags = [city, country, "Airport Transfers", "Private Transfers", "Travel Tips"] if country else [city, "Airport Transfers", "Private Transfers", "Travel Tips"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Airport and hotel transfers in {city}: shared shuttles, private cars, prices, and booking tips.",
        "tags": [t for t in tags if t], "city": city, "country": country,
        "tours": tours,
    }
