"""deals_writer.py - Flight deals by origin city guide generator"""
import os, sqlite3, logging, re
from datetime import datetime
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

def _fetch_deals_from_origin(origin_code):
    conn = _get_db()
    rows = conn.execute("""
        SELECT fp.destination, fp.price, fp.airline, fp.stops,
               fp.departure_date, fp.return_date,
               ft.dest_city
        FROM flight_prices fp
        LEFT JOIN flight_topics ft ON fp.origin = ft.origin AND fp.destination = ft.destination
        WHERE fp.origin = ?
        ORDER BY fp.price ASC
        LIMIT 30
    """, (origin_code,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _fetch_airline_names(codes):
    if not codes:
        return {}
    conn = _get_db()
    ph = ",".join(["?"] * len(codes))
    rows = conn.execute(f"SELECT iata, name FROM ref_airlines WHERE iata IN ({ph})", list(codes)).fetchall()
    conn.close()
    return {r["iata"]: r["name"] for r in rows}

def _build_deals_summary(deals, origin_city, airline_names):
    if not deals:
        return "No deals available."
    lines = [f"Flight deals from {origin_city}:"]
    for d in deals:
        dest = d.get("dest_city") or d.get("destination", "")
        aname = airline_names.get(d.get("airline",""), d.get("airline",""))
        lines.append(f"  {dest} ({d['destination']}): ${d['price']} via {aname}, {d['stops']} stop(s), depart {d.get('departure_date','N/A')}")
    return "\n".join(lines)

def generate_deals_guide(topic):
    origin_code = topic["origin"]
    origin_city = topic.get("origin_city", origin_code)
    
    deals = _fetch_deals_from_origin(origin_code)
    if not deals:
        logger.warning(f"No deals for {origin_city} ({origin_code})")
        return None
    
    airline_codes = set(d.get("airline","") for d in deals if d.get("airline"))
    airline_names = _fetch_airline_names(airline_codes)
    summary = _build_deals_summary(deals, origin_city, airline_names)
    today = datetime.now().strftime("%B %Y")
    
    prompt = f"""Write a flight deals guide for travelers departing from {origin_city}.

CURRENT DATE: {today}

REAL PRICE DATA FROM OUR DATABASE:
{summary}

ARTICLE REQUIREMENTS:
- 1,200-1,600 words, American English, friendly practical tone
- Use the EXACT prices from the data above
- Group destinations by price range or region

REQUIRED H2 SECTIONS:
## Cheapest Flights From {origin_city} Right Now
## Best Budget Destinations Under $200
## Mid-Range Getaways ($200-$500)
## Premium Long-Haul Deals
## Money-Saving Tips for {origin_city} Travelers
## Best Time to Book From {origin_city}

RULES:
- ONLY use prices from the data provided
- If a section has 0 relevant destinations, OMIT that H2 section entirely
- Do NOT include any URLs or links
- Do NOT invent prices or destinations not in the data
- Write in flowing paragraphs, NEVER use numbered lists
- If a price is not in the provided DATA, do NOT mention it

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.5, max_tokens=3500,
        messages=[
            {"role": "system", "content": "You are a travel journalist writing data-driven flight deal articles. Use real price data when provided. STRICT RULES: 1) NEVER use: plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, crystal-clear, soak in, immerse yourself, treasure trove, must-visit, paradise for, world-class, bucket list, look no further, haven for, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Write in flowing paragraphs, not numbered lists. 3) Format prices as whole numbers."},
            {"role": "user", "content": prompt}
        ]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Flight Deals From {origin_city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    
    return {
        "title": title, "slug": topic["slug"], "content": content,
        "description": f"Find the cheapest flights from {origin_city}. Real prices, best destinations, and money-saving tips.",
        "tags": [origin_city, "Flight Deals", "Cheap Flights", "Travel Deals"],
        "origin": origin_city, "deals": deals,
    }
