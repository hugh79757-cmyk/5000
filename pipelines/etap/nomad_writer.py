"""nomad_writer.py - Digital Nomad Guide And Coworking guide generator"""
import os, sqlite3, logging, re
from openai import OpenAI
from pipelines.etap.quality_guard import preprocess_tours

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

def fetch_data(city, country=None):
    conn = _get_db()
    esim = conn.execute("""
        SELECT title, description, link FROM airalo_esim
        WHERE LOWER(description) LIKE ? OR LOWER(title) LIKE ?
        LIMIT 5
    """, (f'%{(country or city).lower()}%', f'%{(country or city).lower()}%')).fetchall()
    visa = conn.execute("""
        SELECT destination, requirement FROM visa_requirements
        WHERE LOWER(destination) LIKE ?
        LIMIT 10
    """, (f'%{city.lower()}%',)).fetchall()
    conn.close()
    return {"esim": [dict(r) for r in esim], "visa": [dict(r) for r in visa]}

def _build_summary(data, city, country):
    esim = data.get("esim", [])
    visa = data.get("visa", [])
    summary = f"City: {city}, Country: {country}\n"
    if esim:
        summary += "\n[eSIM OPTIONS]\n"
        for e in esim:
            summary += f"- {e['title']}: {e['description']}\n"
    if visa:
        summary += "\n[VISA INFO]\n"
        for v in visa:
            summary += f"- {v['destination']}: {v['requirement']}\n"
    return summary

def generate_nomad_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")
    data = fetch_data(city, country)
    summary = _build_summary(data, city, country)
    h2s = """  ## Why Digital Nomads Choose {city}
  ## Best Coworking Spaces in {city}
  ## Internet SIM Cards and Connectivity
  ## Cost of Living for Nomads in {city}
  ## Visa and Stay Options
  ## Neighborhoods and Where to Stay
  ## Tips for Digital Nomads in {city}"""
    prompt = f"""Write a digital nomad guide for {city}, {country}.

CONTEXT DATA:
{summary}

RULES:
- Write 1,200-1,800 words in English
- Do NOT include any booking links or URLs in the text
- Title must include "{city}" and "Digital Nomad" or "Coworking"
- Required H2 sections:
{h2s}
- If a section has fewer than 2 data points, OMIT that H2 entirely
- Include practical cost estimates, internet speeds, visa lengths
- Write as a nomad who has actually lived and worked in {city}
- Do NOT use numbered lists, write in flowing paragraphs
- Add ONE CTA near the end

Return ONLY the article in markdown starting with # title"""
    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.5, max_tokens=4000,
        messages=[
            {"role": "system", "content": "You are a full-time digital nomad who has lived and worked in 50+ cities. STRICT RULES: 1) Never use: vibrant, bustling, hidden gem, treasure trove, must-visit, immerse yourself, embark, crystal-clear, world-class, bucket list, plethora, tapestry, myriad. 2) Write practical, specific, data-driven content. 3) Every section must include one actionable tip."},
            {"role": "user", "content": prompt}
        ]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else f"Digital Nomad Guide to {city}"
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-") + "-digital-nomad-guide")
    tags = [city, country, "Digital Nomad", "Coworking", "Remote Work"] if country else [city, "Digital Nomad", "Coworking"]
    return {"title": title, "slug": slug, "content": content,
             "description": f"Digital nomad guide to {city}: coworking spaces, internet, visa, cost of living and tips.",
             "tags": [t for t in tags if t], "city": city, "country": country, "tours": []}
