"""escape_writer.py - Escape Rooms And Puzzle Experiences guide generator"""
import os, sqlite3, logging, re
from pipelines.etap.quality_guard import preprocess_tours
from shared.ai_writer import generate as ai_generate

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
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
        WHERE (city = ? OR city IN (SELECT alias FROM city_aliases WHERE canonical_name = ?))
          AND category IN ('Escape Rooms')
          AND deep_link IS NOT NULL AND deep_link != ''
        ORDER BY CAST(price AS REAL) ASC
    """, (city, city)).fetchall()
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
    picks = {"budget": budget[:5], "mid": mid[:5], "premium": premium[:5],
              "deals": sorted(discounted, key=lambda x: x.get("discount","0"), reverse=True)[:5]}
    top_cats = sorted(categories.items(), key=lambda x: -x[1])[:8]
    summary = f"City: {city}\nTotal tours: {total}\nDiscounted: {len(discounted)}\n"
    summary += "Categories: " + ", ".join(f"{c} ({n})" for c,n in top_cats) + "\n"
    for label, items in picks.items():
        if items:
            summary += f"[{label.upper()} PICKS]\n"
            for t in items:
                nm = re.sub(r"^Save [\d.]+%!\s*", "", t["product_name"])
                summary += f"- {nm} | ${t['price']} {t['currency']} | {t['category']}\n"
            summary += "\n"
    return summary, picks

def generate_escape_guide(topic):
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
    h2s = """  ## Escape Rooms in {city}: What to Expect
  ## Best Escape Room Experiences in {city}
  ## Themes and Difficulty Levels
  ## Prices and Group Options
  ## Tips for First-Timers in {city}"""
    prompt = f"""Write a escape rooms and puzzle experiences guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent tours or prices):
{summary}

RULES:
- Write 1,200-1,800 words in English
- Do NOT include any booking links or URLs in the text
- Do NOT invent tour names, prices, or categories not in the data
- Title must include "{city}" and relate to escape rooms and puzzle experiences
- Required H2 sections:
{h2s}
- For each tour mentioned, include exact name and price from the data
- Remove "Save XX%!" prefixes from tour names
- If a section has fewer than 2 tours in the data, OMIT that H2 section entirely
- Write as a escape room enthusiast who has completed hundreds of rooms worldwide
- Write in flowing paragraphs, NEVER use numbered lists
- Add ONE natural CTA near the end of the article
- End with best value pick and best splurge pick by name and price

Return ONLY the article in markdown starting with # title"""
    result = ai_generate(
        "You are a escape room enthusiast who has completed hundreds of rooms worldwide. STRICT RULES: 1) Never use: vibrant, bustling, hidden gem, treasure trove, must-visit, immerse yourself, embark, crystal-clear, world-class, bucket list, plethora, tapestry, myriad. 2) Format prices as whole numbers. 3) Never invent data. 4) Every section must include one practical tip. 5) Open with a specific concrete scene or fact.",
        prompt,
        temperature=0.5,
        max_tokens=4000,
        )
    content = result["content"].strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Escape Rooms And Puzzle Experiences in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-") + "-escape-rooms")
    tags = [city, country, "Escape Rooms"] if country else [city, "Escape Rooms"]
    return {"title": title, "slug": slug, "content": content,
             "description": f"Best escape rooms and puzzle experiences in {city}: prices, top picks, and practical tips.",
             "tags": [t for t in tags if t], "city": city, "country": country, "tours": tours}
