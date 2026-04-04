"""airlines_writer.py – 항공사 리뷰 생성 (데이터 기반만)"""
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

def fetch_airline_data(iata_code):
    conn = _get_db()
    airline = conn.execute("""
        SELECT iata, name, country_code, is_lowcost
        FROM ref_airlines WHERE iata = ?
    """, (iata_code,)).fetchone()
    routes = conn.execute("""
        SELECT origin, destination
        FROM airline_routes WHERE airline = ?
    """, (iata_code,)).fetchall()
    # 운항 공항 수
    airports = set()
    for r in routes:
        airports.add(r[0])
        airports.add(r[1])
    conn.close()
    return (
        dict(airline) if airline else None,
        [dict(r) for r in routes],
        len(airports)
    )

def generate_airline_review(topic):
    iata = topic.get("iata_code", "")
    airline_name = topic.get("airline_name", "")
    is_lcc = topic.get("is_lowcost", 0)
    airline_data, routes, airport_count = fetch_airline_data(iata)
    if not airline_data:
        logger.warning(f"No airline data for {iata}")
        return None
    name = airline_data.get("name", airline_name or iata)
    lcc_str = "low-cost carrier (LCC)" if airline_data.get("is_lowcost") else "full-service carrier"
    summary = f"Airline: {name} (IATA: {iata})\n"
    summary += f"Type: {lcc_str}\n"
    summary += f"Country: {airline_data.get('country_code', 'Unknown')}\n"
    summary += f"Known routes: {len(routes)}\n"
    summary += f"Airports served: {airport_count}\n"
    if routes:
        summary += "Sample routes: " + ", ".join(f"{r['origin']}→{r['destination']}" for r in routes[:15]) + "\n"
    prompt = f"""Write an airline overview for {name} ({iata}).

DATA (use ONLY this data):
{summary}

RULES:
- Write 800-1,200 words in English
- Title must include "{name}"
- Do NOT invent routes, fleet info, baggage policies, or in-flight services
- Be HONEST about what data is available. If route data is limited, say so.
- If it is a low-cost carrier, explain what that generally means
- If it is a full-service carrier, explain what that generally means
- Do NOT make up specific baggage weights, meal options, or lounge info
- Required H2 sections:
  ## {name} ({iata}) Overview
  ## Route Network (only if route data exists)
  ## What to Expect as a {'Low-Cost' if is_lcc else 'Full-Service'} Carrier
  ## Booking Tips
  ## Is {name} Worth Flying?
- Write factually, acknowledge data limitations honestly

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.4, max_tokens=3000,
        messages=[{"role":"system","content":"You are an aviation journalist. Use ONLY provided data. Be honest about limitations — never fabricate airline details. STRICT RULES: 1) NEVER use these words/phrases: plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, hidden gems, crystal-clear, culinary delights, gastronomic, soak in, immerse yourself. 2) Write in flowing paragraphs, not numbered lists. 3) Format prices as whole numbers when .0."},
                  {"role":"user","content": prompt}]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"{name} Airline Review")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", f"{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}-airline-review")
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"{name} ({iata}) airline overview: route network, carrier type, and booking tips.",
        "tags": [name, iata, "Airline Review", "Aviation"],
        "airline_name": name, "iata": iata,
    }
