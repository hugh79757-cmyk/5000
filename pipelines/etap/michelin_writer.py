"""michelin_writer.py – 미슐랭 레스토랑 가이드 생성"""
import logging
import os
import re
import sqlite3

from shared.ai_writer import generate as ai_generate

PRICE_LABEL = {
    "$":    "Budget (under $30)",
    "$$":   "Moderate ($30-$70)",
    "$$$":  "Expensive ($70-$150)",
    "$$$$": "Very Expensive (over $150)",
    "€":    "Budget (under €30)",
    "€€":   "Moderate (€30-€70)",
    "€€€":  "Expensive (€70-€150)",
    "€€€€": "Very Expensive (over €150)",
    "¥":    "Budget (under ¥3,000)",
    "¥¥":   "Moderate (¥3,000-¥8,000)",
    "¥¥¥":  "Expensive (¥8,000-¥20,000)",
    "¥¥¥¥": "Very Expensive (over ¥20,000)",
    "£":    "Budget (under £30)",
    "££":   "Moderate (£30-£70)",
    "£££":  "Expensive (£70-£150)",
    "££££": "Very Expensive (over £150)",
}

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

def fetch_restaurants(city):
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
    green_stars = 0
    for r in restaurants:
        a = r.get("award") or "Selected"
        awards[a] = awards.get(a, 0) + 1
        c = r.get("cuisine") or "Not specified"
        cuisines[c] = cuisines.get(c, 0) + 1
        if r.get("green_star"):
            green_stars += 1
    top_cuisines = sorted(cuisines.items(), key=lambda x: -x[1])[:10]
    summary = f"City: {city}\nTotal Michelin restaurants: {total}\n"
    summary += "Awards: " + ", ".join(f"{k}: {v}" for k, v in sorted(awards.items())) + "\n"
    summary += f"Green Star restaurants: {green_stars}\n"
    summary += "Top cuisines: " + ", ".join(f"{c} ({n})" for c, n in top_cuisines) + "\n\n"
    summary += "RESTAURANT LIST:\n"
    for r in restaurants[:30]:
        price_str = PRICE_LABEL.get(r["price"], r["price"]) if r["price"] else "Price N/A"
        desc = (r["description"] or "")[:100]
        summary += f"- {r['name']} | {r['award']} | {r['cuisine']} | {price_str} | {desc}\n"
    return summary

def generate_michelin_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")
    restaurants = fetch_restaurants(city)
    if not restaurants:
        logger.warning(f"No restaurants for {city}")
        return None
    summary = _build_summary(restaurants, city)
    if not summary:
        return None
    prompt = f"""Write a Michelin restaurant guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent restaurants):
{summary}

RULES:
- Write 1,200-1,800 words in English
- Do NOT include any URLs or booking links
- Do NOT invent restaurant names, awards, or prices not in the data
- If price is "Price N/A", do not mention a price for that restaurant
- Title must include "{city}" and "Michelin"
- STRICT STRUCTURE — MANDATORY. Your article body MUST contain EXACTLY these four H2 headings, in this exact order, each as its own line starting with "## " (NOT numbered, NOT bulleted, NOT nested under anything):
  ## At a Glance
  ## Where to Eat
  ## Compare
  ## FAQ
  Content required under each:
  - "## At a Glance" — a compact summary TABLE with columns: Restaurant | Award | Cuisine | Price (3-7 rows from data, sorted by award). Answers "what's here" immediately.
  - "## Where to Eat" — detailed per-restaurant H3 sections (each 120-180 words: award, signature dish, price tier, why choose it). 3-6 restaurants.
  - "## Compare" — a comparison TABLE with columns: Restaurant | Award | Cuisine | Price | Best For (same restaurants as At a Glance, add "Best For" verdict column). Drives dwell time.
  - "## FAQ" — 3 questions with answers (e.g. "How far in advance should I book?", "Are there vegetarian options?", "What is the dress code?"). Target long-tail keywords.
- HARD CONSTRAINT: all four H2 headings above MUST appear verbatim as level-2 headings. If ANY is missing, the article is invalid — always emit all four.
- OPENING PARAGRAPH — MANDATORY: before "## At a Glance", write a 3-4 sentence intro paragraph about {city}'s Michelin dining scene (NO heading above it, NO table). The article body must start with this paragraph, never with a heading.
- description/meta: 1-2 sentence summary of {city}'s Michelin scene (20-30 words). NEVER a section name like "At a Glance".
- Internal links: at most 3 links per 500 words, and only to other {city} guides
  or same-site travel content. Do NOT exceed 6 total internal links.
- Mention each restaurant by exact name and award from data
- Write naturally as a guide, not a list dump

Return ONLY the article in markdown starting with # title"""

    result = ai_generate(
    "You are a food and travel writer. Use only the provided Michelin data. Never fabricate information. STRICT RULES: 1) NEVER use these words/phrases: plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, hidden gems, crystal-clear, culinary delights, gastronomic, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Write in flowing paragraphs, not numbered lists. 3) Format prices as whole numbers when .0.",
    prompt,
    temperature=0.5,
    max_tokens=4000,
    )
    content = result["content"].strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Michelin Restaurants in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", f"michelin-restaurants-{re.sub(r'[^a-z0-9]+', '-', city.lower()).strip('-')}")
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Complete guide to Michelin-starred restaurants in {city}: awards, cuisines, prices, and booking tips.",
        "tags": [city, country, "Michelin Restaurants", "Fine Dining", "Food Guide"],
        "city": city, "country": country, "restaurants": restaurants,
    }
