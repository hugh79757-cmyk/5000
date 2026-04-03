"""daytrips_writer.py - Day Trips guide generator"""
import os, sqlite3, logging, re
from openai import OpenAI

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
    if not tours:
        logger.warning(f"No tours for {city}")
        return None
    result = _build_summary(tours, city)
    if not result:
        return None
    summary, picks = result

    prompt = f"""Write a comprehensive day trips guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent tours or prices):
{summary}

RULES:
- Write 1,200-1,800 words in English
- Do NOT include any booking links or URLs in the text
- Do NOT invent tour names, prices, or categories not in the data
- Title must include "{city}" and be SEO-friendly
- Required H2 sections:
  ## Why {city} is a Perfect Base for Day Trips
  ## Budget-Friendly Day Trips Under $50
  ## Mid-Range Excursions ($50-$200)
  ## Premium Full-Day Experiences
  ## Most Popular Day Trip Types From {city}
  ## Best Deals and Discounts on Day Trips
  ## Tips for Planning Day Trips From {city}
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
            {"role":"system","content":"You are a travel content writer specializing in day trips. Use only provided data. Never fabricate information. Write engaging, helpful content that makes readers want to book. Use a conversational but authoritative tone. Avoid generic filler. Every paragraph should either inform or persuade. Naturally weave in reasons to book now (limited spots, seasonal pricing, popular tours selling out)."},
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
