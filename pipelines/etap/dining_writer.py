"""dining_writer.py - Michelin dining guide generator (city-focused, practical angle)"""
import os, sqlite3, logging, re
from openai import OpenAI
from pipelines.etap.quality_guard import preprocess_restaurants, postprocess_content

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

def fetch_restaurants(city, country=None):
    conn = _get_db()
    rows = conn.execute("""
        SELECT name, address, cuisine, price, award, green_star,
               description, url, city, country
        FROM michelin_restaurants
        WHERE city = ?
        ORDER BY CASE award
            WHEN '3 Stars' THEN 1 WHEN '2 Stars' THEN 2
            WHEN '1 Star' THEN 3 WHEN 'Bib Gourmand' THEN 4
            ELSE 5 END
    """, (city,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _build_summary(restaurants, city):
    total = len(restaurants)
    if total == 0:
        return None
    awards = {}
    cuisines = {}
    price_ranges = {}
    green_stars = 0
    for r in restaurants:
        a = r.get("award") or "Selected"
        awards[a] = awards.get(a, 0) + 1
        c = r.get("cuisine") or "Not specified"
        for cuisine in c.split(","):
            cuisine = cuisine.strip()
            if cuisine:
                cuisines[cuisine] = cuisines.get(cuisine, 0) + 1
        p = r.get("price") or "N/A"
        price_ranges[p] = price_ranges.get(p, 0) + 1
        if r.get("green_star"):
            green_stars += 1

    top_cuisines = sorted(cuisines.items(), key=lambda x: -x[1])[:10]
    summary = f"City: {city}\nTotal Michelin restaurants: {total}\n"
    summary += "Awards: " + ", ".join(f"{k}: {v}" for k, v in sorted(awards.items())) + "\n"
    summary += "Price ranges: " + ", ".join(f"{k}: {v}" for k, v in sorted(price_ranges.items())) + "\n"
    summary += f"Green Star (sustainability): {green_stars}\n"
    summary += "Top cuisines: " + ", ".join(f"{c} ({n})" for c, n in top_cuisines) + "\n\n"

    for tier in ["3 Stars", "2 Stars", "1 Star", "Bib Gourmand"]:
        tier_list = [r for r in restaurants if r.get("award") == tier]
        if tier_list:
            summary += f"[{tier.upper()}]\n"
            for r in tier_list[:8]:
                price_str = r["price"] if r["price"] else "Price N/A"
                desc = (r["description"] or "")[:120]
                summary += f"- {r['name']} | {r['cuisine']} | {price_str} | {desc}\n"
            summary += "\n"

    selected = [r for r in restaurants if r.get("award") not in ("3 Stars", "2 Stars", "1 Star", "Bib Gourmand")]
    if selected:
        summary += "[MICHELIN SELECTED]\n"
        for r in selected[:5]:
            price_str = r["price"] if r["price"] else "Price N/A"
            summary += f"- {r['name']} | {r['cuisine']} | {price_str}\n"
        summary += "\n"

    return summary

def generate_dining_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")
    restaurants = fetch_restaurants(city, country)
    restaurants, _pre_issues, _excluded = preprocess_restaurants(restaurants, city=city)
    if not restaurants:
        logger.warning(f"No restaurants for {city}")
        return None
    summary = _build_summary(restaurants, city)
    if not summary:
        return None

    has_3star = any(r.get("award") == "3 Stars" for r in restaurants)
    has_2star = any(r.get("award") == "2 Stars" for r in restaurants)
    has_1star = any(r.get("award") == "1 Star" for r in restaurants)
    has_bib = any(r.get("award") == "Bib Gourmand" for r in restaurants)
    has_green = any(r.get("green_star") for r in restaurants)

    sections = f"  ## The Dining Scene in {city}\n"
    if has_3star or has_2star:
        sections += f"  ## Fine Dining at Its Best: Multi-Star Restaurants\n"
    if has_1star:
        sections += f"  ## One-Star Restaurants Worth a Detour\n"
    if has_bib:
        sections += f"  ## Bib Gourmand: Great Food Without the Splurge\n"
    if has_green:
        sections += f"  ## Green Star: Sustainable Dining in {city}\n"
    sections += f"  ## Cuisine Styles and What {city} Does Best\n"
    sections += f"  ## Price Guide: What to Budget for Michelin Dining\n"
    sections += f"  ## Booking Tips and What to Know Before You Go\n"

    prompt = f"""Write a practical Michelin dining guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent restaurants or prices):
{summary}

RULES:
- Write 1,200-1,800 words in English
- Do NOT include any URLs or booking links in the text
- Do NOT invent restaurant names, awards, cuisines, or prices not in the data
- If price is "Price N/A", do not mention a price for that restaurant
- Title must include "{city}" and relate to dining/eating
- Required H2 sections (skip if no data for that tier):
{sections}
- Mention restaurants by exact name and award from the data
- For each tier, highlight 2-3 standout picks and explain WHY they stand out (based on cuisine style or description)
- Include practical info: dress code expectations, reservation lead time, lunch vs dinner pricing
- Write as a food-loving traveler sharing personal dining strategy, not as a directory listing
- End with a "where to eat tonight" quick recommendation for different budgets

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.5, max_tokens=4000,
        messages=[
            {"role": "system", "content": "You are a food and travel blogger who dines at Michelin restaurants worldwide. Write in first-person-informed tone. STRICT RULES: 1) Never use: plethora, vibrant, bustling, let\'s dive in, without further ado, hidden gem, tapestry, myriad, embark, culinary journey, gastronomic. 2) Never invent data. 3) Every section must include one practical tip (reservation lead time, dress code reality, lunch vs dinner value, which tasting menu to pick). 4) Open with a specific dish, restaurant detail, or dining scene."},
            {"role": "user", "content": prompt}
        ]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Where to Eat in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", f"michelin-dining-{re.sub(r'[^a-z0-9]+', '-', city.lower()).strip('-')}")
    tags = [city, country, "Michelin Restaurants", "Dining Guide", "Food Travel"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Where to eat in {city}: Michelin-starred restaurants, Bib Gourmand picks, price guide, and booking tips.",
        "tags": [t for t in tags if t], "city": city, "country": country,
        "restaurants": restaurants,
    }
