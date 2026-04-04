"""airports_writer.py – 공항 가이드 생성 (데이터 기반만)"""
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

def fetch_airport_data(iata_code):
    conn = _get_db()
    airport = conn.execute("""
        SELECT iata, name, country_code, lat, lng, timezone
        FROM ref_airports WHERE iata = ?
    """, (iata_code,)).fetchone()
    # 이 공항을 사용하는 항공사 + 노선
    airlines = conn.execute("""
        SELECT DISTINCT a.iata, a.name, a.is_lowcost
        FROM airline_routes ar
        JOIN ref_airlines a ON ar.airline = a.iata
        WHERE ar.origin = ? OR ar.destination = ?
        ORDER BY a.name
    """, (iata_code, iata_code)).fetchall()
    # 연결 도시
    destinations = conn.execute("""
        SELECT DISTINCT destination FROM airline_routes
        WHERE origin = ? LIMIT 30
    """, (iata_code,)).fetchall()
    conn.close()
    return (
        dict(airport) if airport else None,
        [dict(a) for a in airlines],
        [d[0] for d in destinations]
    )

def generate_airport_guide(topic):
    iata = topic.get("iata_code", "")
    city = topic.get("city", "")
    country = topic.get("country", "")
    airport_data, airlines, destinations = fetch_airport_data(iata)
    if not airport_data:
        logger.warning(f"No airport data for {iata}")
        return None
    name = airport_data.get("name", iata)
    tz = airport_data.get("timezone", "")
    summary = f"Airport: {name} ({iata})\n"
    summary += f"Location: {city}, {country}\n"
    summary += f"Timezone: {tz}\n"
    summary += f"Coordinates: {airport_data.get('lat', '')}, {airport_data.get('lng', '')}\n"
    summary += f"Airlines operating: {len(airlines)}\n"
    if airlines:
        summary += "Airlines: " + ", ".join(f"{a['name']} ({'LCC' if a['is_lowcost'] else 'FSC'})" for a in airlines[:20]) + "\n"
    summary += f"Direct destinations: {len(destinations)}\n"
    if destinations:
        summary += "Sample destinations: " + ", ".join(destinations[:15]) + "\n"
    prompt = f"""Write an airport guide for {name} ({iata}) in {city}, {country}.

DATA (use ONLY this data):
{summary}

RULES:
- Write 800-1,200 words in English
- Title must include the airport name and IATA code ({iata})
- Do NOT invent terminal names, lounge names, restaurant names, or services
- ONLY write about what the data confirms
- If airline/route data is limited, say so honestly
- Required H2 sections:
  ## {name} ({iata}) Overview
  ## Airlines Operating at {iata} (only if airline data exists)
  ## Direct Destinations from {iata} (only if destination data exists)
  ## Getting To and From the Airport
  ## Practical Tips for Travelers
- For "Getting To and From" — write general advice only, do not invent specific bus lines or taxi prices
- Be honest about what information is available vs not
- Do NOT include any internal links, URLs, or markdown links in the text. No [text](url) patterns.

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.4, max_tokens=3000,
        messages=[{"role":"system","content":"You are an aviation travel writer. Use ONLY provided data. If data is limited, be honest — never fabricate airport facilities, terminal info, or services. STRICT RULES: 1) NEVER use these words/phrases: plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, hidden gems, crystal-clear, culinary delights, gastronomic, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Write in flowing paragraphs, not numbered lists. 3) Format prices as whole numbers when .0."},
                  {"role":"user","content": prompt}]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"{name} ({iata}) Airport Guide")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", f"{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}-{iata.lower()}-guide")
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Guide to {name} ({iata}): airlines, destinations, transport, and traveler tips.",
        "tags": [city, country, iata, "Airport Guide", "Travel"],
        "city": city, "country": country, "iata": iata,
    }
