"""walking_writer.py - Walking Tours guide generator"""
import os, sqlite3, logging, re
from openai import OpenAI
from pipelines.etap.quality_guard import preprocess_tours, postprocess_content, clean_tour_name

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
_client = None

try:
    from pipelines.etap.post_processor import fix_encoding, clean_tags, clean_prompt_leaks
    HAS_PP = True
except ImportError:
    HAS_PP = False

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
        WHERE city = ? AND category IN ('Walking Tours', 'Self-guided Tours', 'Audio Guides', 'Running Tours', 'Pedicab Tours', 'Tuk Tuk Tours')
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

    budget = [t for t in tours if 0 < _safe_price(t.get("price")) < 30]
    mid = [t for t in tours if 30 <= _safe_price(t.get("price")) <= 100]
    premium = [t for t in tours if _safe_price(t.get("price")) > 100]
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

def generate_walking_guide(topic):
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

    prompt = f"""Write a comprehensive walking tours guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent tours or prices):
{summary}

RULES:
- Write 1,000-1,500 words in English
- Do NOT include any booking links or URLs in the text
- Do NOT invent tour names, prices, or categories not in the data
- Title must include "{city}" and be SEO-friendly
- Required H2 sections:
  ## Why {city} is Best Explored on Foot
  ## Top Walking Tours in {city} (feature 3-5 best tours from the data, grouped naturally by theme or price)
  ## Types of Walking Tours in {city}
  ## Prices and Deals
  ## Tips for Walking Tours in {city}
- For each tour mentioned, include exact name and price from the data
- ONLY mention tours and prices that appear in the DATA above. Do NOT estimate, round, or invent ANY price
- If a tour costs $8, write $8. If it costs $32, write $32. NEVER write a price not in the data
- If a section has fewer than 2 tours in the data, OMIT that H2 section entirely. Do NOT write filler content
- Write naturally with engaging prose, not a list dump
- Include practical tips (best time, what to wear, booking advice)
- End with a brief practical summary
- Remove "Save XX%!" prefixes from tour names when mentioning them
- Add ONE natural CTA near the end of the article (not in every section). Example: "Peak season fills up fast — check availability before prices change."
- Do NOT use numbered lists for tours. Weave them into flowing paragraphs
- Include a "Quick Comparison" sentence at the end of each price section (e.g., "At $15, the catamaran tour offers the best value per hour compared to the $50 private option.")
- Make the summary actionable: mention the best overall value pick and the best splurge pick by name and price

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.5, max_tokens=4000,
        messages=[
            {"role":"system","content":"You are a travel blogger who walks cities for a living. Write in first-person-informed tone. STRICT RULES: 1) Never use: plethora, vibrant, bustling, let\'s dive in, without further ado, hidden gem, tapestry, myriad, embark, crystal-clear, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Format prices as whole numbers when .0 ($8 not $8.0). 3) NEVER invent data. If a price is not in the provided DATA, do NOT mention it. Do NOT estimate prices. 4) Every section must include one practical tip (comfortable shoes, best start time, neighborhoods to avoid, water stops). 5) Open with a concrete hook."},
            {"role":"user","content": prompt}
        ]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Best Walking Tours in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-"))
    tags = [city, country, "Walking Tours", "Travel"] if country else [city, "Walking Tours", "Travel"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Best walking tours in {city}: self-guided routes, audio guides, and expert-led walks with real prices.".replace("{city}", city),
        "tags": [t for t in tags if t], "city": city, "country": country,
        "tours": tours,
    }
