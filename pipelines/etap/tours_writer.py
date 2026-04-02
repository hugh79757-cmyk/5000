"""tours_writer.py – Viator 투어 가이드 생성 (카이로, 파리 등 도시별)"""
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

def fetch_tours(city, country=None):
    conn = _get_db()
    rows = conn.execute("""
        SELECT product_name, description, category, price, currency,
               discount, image_url, deep_link, city, country
        FROM viator_tours
        WHERE city = ? AND deep_link IS NOT NULL AND deep_link != ''
        ORDER BY CAST(price AS REAL) ASC
    """, (city,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _build_tour_summary(tours, city):
    total = len(tours)
    if total == 0:
        return None
    categories = {}
    price_buckets = {"under_50": [], "50_200": [], "over_200": []}
    discounted = []
    for t in tours:
        cat = t.get("category") or "Other"
        categories[cat] = categories.get(cat, 0) + 1
        p = 0
        try: p = float(t["price"])
        except: pass
        if p > 0 and p < 50: price_buckets["under_50"].append(t)
        elif p >= 50 and p <= 200: price_buckets["50_200"].append(t)
        elif p > 200: price_buckets["over_200"].append(t)
        disc = t.get("discount") or ""
        if disc and disc != "0":
            discounted.append(t)
    # 각 버킷에서 대표 5개
    picks = {
        "budget": price_buckets["under_50"][:5],
        "mid": price_buckets["50_200"][:5],
        "premium": price_buckets["over_200"][:5],
        "deals": sorted(discounted, key=lambda x: x.get("discount","0"), reverse=True)[:5],
    }
    top_cats = sorted(categories.items(), key=lambda x: -x[1])[:10]
    summary = f"City: {city}\nTotal tours: {total}\n"
    summary += f"Discounted tours: {len(discounted)}\n"
    summary += "Top categories: " + ", ".join(f"{c} ({n})" for c,n in top_cats) + "\n"
    summary += f"Price range: ${price_buckets['under_50'][0]['price'] if price_buckets['under_50'] else 'N/A'} ~ ${price_buckets['over_200'][-1]['price'] if price_buckets['over_200'] else 'N/A'}\n\n"
    for label, items in picks.items():
        if items:
            summary += f"[{label.upper()} PICKS]\n"
            for t in items:
                summary += f"- {t['product_name']} | ${t['price']} {t['currency']} | {t['category']}\n"
            summary += "\n"
    return summary

def generate_tours_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")
    tours = fetch_tours(city, country)
    if not tours:
        logger.warning(f"No tours for {city}")
        return None
    summary = _build_tour_summary(tours, city)
    if not summary:
        return None
    prompt = f"""Write a comprehensive tour guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent tours or prices):
{summary}

RULES:
- Write 1,200-1,800 words in English
- Do NOT include any booking links or URLs in the text
- Do NOT invent tour names, prices, or categories not in the data
- Title must include "{city}" and be SEO-friendly
- Required H2 sections:
  ## Why {city} is Worth Exploring with a Guide
  ## Best Budget Tours Under $50
  ## Mid-Range Experiences ($50-$200)
  ## Premium and Multi-Day Tours
  ## Most Popular Tour Categories in {city}
  ## Best Deals and Discounts Available Now
  ## Tips for Booking Tours in {city}
- For each tour mentioned, include exact name and price from the data
- If a price bucket is empty, skip that section
- Write naturally, not as a list dump
- End with a brief practical summary, no links

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.5, max_tokens=4000,
        messages=[{"role":"system","content":"You are a travel content writer. Use only provided data. Never fabricate information."},
                  {"role":"user","content": prompt}]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Best Tours in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-"))
    tags = [city, country, "Tours", "Activities", "Things to Do"] if country else [city, "Tours", "Activities"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Best tours and activities in {city}: budget, mid-range, premium picks with real prices and discounts.",
        "tags": [t for t in tags if t], "city": city, "country": country,
        "tours": tours,  # 전체 투어 데이터 (pipeline에서 카드 생성용)
    }
