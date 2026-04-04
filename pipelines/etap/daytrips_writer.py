"""daytrips_writer.py - Day Trips guide generator"""
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
        WHERE city = ? AND category IN ('Day Trips', 'Full-day Tours', 'Half-day Tours')
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

    budget = [t for t in tours if 0 < _safe_price(t.get("price")) < 50]
    mid = [t for t in tours if 50 <= _safe_price(t.get("price")) <= 200]
    premium = [t for t in tours if _safe_price(t.get("price")) > 200]
    picks = {
        "budget": budget[:5],
        "mid": mid[:5],
        "premium": premium[:5],
        "deals": sorted(discounted, key=lambda x: x.get("discount","0"), reverse=True)[:5],
    }
    top_cats = sorted(categories.items(), key=lambda x: -x[1])[:10]
    summary = f"City: {city}\nTotal tours: {total}\n"
    summary += f"Discounted: {len(discounted)}\n"
    summary += "Categories: " + ", ".join(f"{c} ({n})" for c,n in top_cats) + "\n"

    for label, items in picks.items():
        if items:
            summary += f"[{label.upper()} PICKS]\n"
            for t in items:
                summary += f"- {t['product_name']} | ${t['price']} {t['currency']} | {t['category']}\n"
            summary += "\n"

    return summary, picks

def generate_daytrips_guide(topic):
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

    prompt = f"""Write a day trips guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent tours or prices):
{summary}

FORMAT RULES:
- 1,200-1,800 words in English
- No booking links or URLs in text
- No invented tour names, prices, or categories
- Format prices as whole numbers when .0 ($8 not $8.0, $50 not $50.0)
- Title: include "{city}", make it specific and clickable (not generic)
- Remove "Save XX%!" prefixes from tour names

STRUCTURE (H2 sections — skip any with no data):
  ## [Open with a specific hook about {city} — distance/time to key sites, a surprising fact, or a concrete scene]
  ## Budget Day Trips Under $50
  ## Mid-Range Excursions ($50-$200)
  ## Premium Full-Day Experiences
  ## Best Deals and Current Discounts
  ## Planning Tips: Timing, Transport, and What to Pack

WRITING STYLE:
- Open the article with a concrete, specific first sentence (e.g., "A 20-minute taxi from downtown {city} puts you at the foot of 4,500-year-old pyramids" NOT "City X is a vibrant destination with much to offer")
- Write as a knowledgeable local friend giving advice, not a catalog
- For each section, pick 2-3 BEST tours and explain WHY they stand out — don't just list names and prices
- Include at least one practical tip per section (best time of day, what to wear, how to get there, what most tourists get wrong)
- Compare tours against each other: "For $12 more you get a private guide and skip the 45-minute ticket line — worth it if you're short on time"
- Use flowing paragraphs, NOT numbered lists
- End with a quick "If you only have one day" recommendation with specific tour name and price
- NEVER use: plethora, vibrant, bustling, embark, tapestry, myriad, "let's dive in", "without further ado", "hidden gem", "rich history and culture"

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.5, max_tokens=4000,
        messages=[
            {"role":"system","content":"You are a travel blogger who has actually visited these destinations. Write in first-person-informed tone (not literally 'I did X' but 'the 20-minute taxi ride from downtown drops you right at the entrance'). STRICT RULES: 1) Never use these words/phrases: plethora, vibrant, bustling, let\'s dive in, without further ado, hidden gem, tapestry, myriad, embark. 2) Format prices as whole numbers when .0 (write $8 not $8.0, write $12 not $12.0). 3) Never invent data. 4) Every section must include at least one practical tip (best time of day, what to wear, how to get there, what to skip). 5) Open with a specific, concrete hook - a scene, a number, a surprising fact - not a generic overview sentence."},
            {"role":"user","content": prompt}
        ]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Best Day Trips in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-"))
    tags = [city, country, "Day Trips", "Travel"] if country else [city, "Day Trips", "Travel"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Best day trips from {city}: budget excursions, full-day tours, and hidden gems with real prices.".replace("{city}", city),
        "tags": [t for t in tags if t], "city": city, "country": country,
        "tours": tours,
    }
