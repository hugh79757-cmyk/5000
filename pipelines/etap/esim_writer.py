"""esim_writer.py – eSIM 가이드 생성 (국가별)"""
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

def fetch_esim_plans(country):
    conn = _get_db()
    rows = conn.execute("""
        SELECT title, link, description, price, sale_price,
               image_link, product_type, brand
        FROM airalo_esim
        WHERE title LIKE ? OR product_type LIKE ?
        ORDER BY CAST(REPLACE(price, '$', '') AS REAL) ASC
    """, (f"%{country}%", f"%{country.lower()}%")).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _build_plan_summary(plans, country):
    if not plans:
        return None
    summary = f"Country: {country}\nTotal plans: {len(plans)}\n\n"
    summary += "PLAN LIST:\n"
    for p in plans:
        price = p['price'] or 'N/A'
        sale = p['sale_price'] or ''
        sale_str = f" (sale: {sale})" if sale and sale != price else ""
        title = p['title'] or 'Unknown'
        summary += f"- {title} | {price}{sale_str}\n"
    # GB당 가격 계산
    best_value = None
    for p in plans:
        title = (p['title'] or '').lower()
        try:
            pr = float(str(p['sale_price'] or p['price'] or '0').replace('$','').replace(',',''))
        except: pr = 0
        gb_match = re.search(r'(\d+)\s*gb', title)
        if gb_match and pr > 0:
            gb = int(gb_match.group(1))
            if gb > 0:
                per_gb = pr / gb
                if not best_value or per_gb < best_value[1]:
                    best_value = (p['title'], per_gb, pr, gb)
    if best_value:
        summary += f"\nBest value: {best_value[0]} at ${best_value[2]:.2f} for {best_value[3]}GB (${best_value[1]:.2f}/GB)\n"
    return summary

def generate_esim_guide(topic):
    country = topic["country"]
    plans = fetch_esim_plans(country)
    if not plans:
        logger.warning(f"No eSIM plans for {country}")
        return None
    summary = _build_plan_summary(plans, country)
    if not summary:
        return None
    prompt = f"""Write an eSIM guide for travelers visiting {country}.

DATA (use ONLY this data):
{summary}

RULES:
- Write 1,000-1,500 words in English
- Title must include "{country}" and "eSIM"
- Do NOT include any URLs or links
- Do NOT invent plans not in the data
- Required H2 sections:
  ## Why Get an eSIM for {country}
  ## Available Plans Compared
  ## Best Value: Which Plan Saves You the Most
  ## How to Install Your eSIM Before Traveling
  ## eSIM vs Physical SIM vs Roaming
  ## Tips for Staying Connected in {country}
- Compare plans by data amount, duration, and price per GB
- Recommend specific plans from the data with exact prices
- Write practically, not generically

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.5, max_tokens=3500,
        messages=[{"role":"system","content":"You are a tech travel writer. Use only provided data. Never fabricate plans or prices. STRICT RULES: 1) NEVER use these words/phrases: plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, hidden gems, crystal-clear, culinary delights, gastronomic, soak in, immerse yourself. 2) Write in flowing paragraphs, not numbered lists. 3) Format prices as whole numbers when .0."},
                  {"role":"user","content": prompt}]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Best eSIM for {country}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", f"esim-{re.sub(r'[^a-z0-9]+', '-', country.lower()).strip('-')}")
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Compare eSIM plans for {country}: prices, data, coverage, and best value picks.",
        "tags": [country, "eSIM", "Travel SIM", "Mobile Data", "Stay Connected"],
        "country": country, "plans": plans,
    }
