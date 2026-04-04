"""bus_writer.py - Bus route guide generator using Omio data"""
import os, sqlite3, logging, re
from openai import OpenAI
from pipelines.etap.quality_guard import preprocess_routes, postprocess_content

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

def _fmt_duration(minutes):
    if not minutes:
        return "N/A"
    try:
        m = int(minutes)
        if m < 60:
            return f"{m} min"
        return f"{m // 60}h {m % 60}m"
    except:
        return str(minutes)

def fetch_route_data(origin, destination):
    conn = _get_db()
    rows = conn.execute("""
        SELECT title, travel_mode, bus_min_price, train_min_price,
               flight_min_price, ferry_min_price, bus_min_duration,
               train_min_duration, flight_min_duration, ferry_min_duration,
               currency, link_url, image_url,
               origin_name, destination_name
        FROM omio_routes
        WHERE (origin_name LIKE ? AND destination_name LIKE ?)
           OR (title LIKE ?)
        LIMIT 5
    """, (f"%{origin}%", f"%{destination}%",
          f"%{origin}%{destination}%")).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _build_route_summary(routes, origin, destination):
    if not routes:
        return None
    r = routes[0]
    currency = r.get("currency", "USD")
    summary = f"Route: {origin} -> {destination}\n"
    if r.get("bus_min_price"):
        summary += f"Bus: {currency} {r['bus_min_price']} | {_fmt_duration(r.get('bus_min_duration'))}\n"
    if r.get("train_min_price"):
        summary += f"Train: {currency} {r['train_min_price']} | {_fmt_duration(r.get('train_min_duration'))}\n"
    if r.get("flight_min_price"):
        summary += f"Flight: {currency} {r['flight_min_price']} | {_fmt_duration(r.get('flight_min_duration'))}\n"
    if r.get("ferry_min_price"):
        summary += f"Ferry: {currency} {r['ferry_min_price']} | {_fmt_duration(r.get('ferry_min_duration'))}\n"
    summary += f"Booking link available: {'Yes' if r.get('link_url') else 'No'}\n"
    return summary

def generate_bus_guide(topic):
    origin = topic["origin"]
    destination = topic["destination"]
    routes = fetch_route_data(origin, destination)
    routes, _pre_issues = preprocess_routes(routes, origin=origin, dest=destination)
    if not routes:
        logger.warning(f"No route data for {origin} -> {destination}")
        return None
    summary = _build_route_summary(routes, origin, destination)
    if not summary:
        return None

    has_bus = bool(routes[0].get("bus_min_price"))
    has_train = bool(routes[0].get("train_min_price"))
    has_flight = bool(routes[0].get("flight_min_price"))
    has_ferry = bool(routes[0].get("ferry_min_price"))

    sections = f"  ## Getting From {origin} to {destination} by Bus\n"
    if has_train:
        sections += f"  ## Bus vs Train: Which Is Better for {origin} to {destination}?\n"
    if has_flight:
        sections += f"  ## Is It Worth Flying Instead?\n"
    if has_ferry:
        sections += f"  ## Ferry as an Alternative\n"
    sections += f"  ## What to Expect on the Bus Journey\n"
    sections += f"  ## How to Get the Cheapest Bus Tickets\n"
    sections += f"  ## Practical Tips for This Route\n"

    prompt = f"""Write a bus travel guide from {origin} to {destination}.

DATA (use ONLY this data, do NOT invent prices or durations):
{summary}

RULES:
- Write 1,000-1,500 words in English
- Focus on bus travel but compare with other available modes
- Title must include "{origin}", "{destination}" and "Bus"
- Do NOT include any URLs or booking links in the text
- Do NOT invent any data not provided above
- If a transport mode has no data above, do NOT write about it. OMIT that H2 section entirely — do NOT write filler content
- Required H2 sections (skip sections for modes without data):
{sections}
- Use exact prices and durations from the data
- Write as an experienced traveler giving practical advice
- Include tips about luggage, comfort, stations, and timing
- End with a clear recommendation on when bus is the best choice

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.5, max_tokens=3500,
        messages=[
            {"role": "system", "content": "You are a budget travel blogger who rides buses across Europe. Write in first-person-informed tone. STRICT RULES: 1) Never use: plethora, vibrant, bustling, let\'s dive in, without further ado, hidden gem, tapestry, myriad, embark, crystal-clear, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Format prices as whole numbers when .0. 3) Never invent data. 4) Every section must include one practical tip (station location, luggage policy, wifi availability, seat selection strategy). 5) Open with a concrete detail about this specific route."},
            {"role": "user", "content": prompt}
        ]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"{origin} to {destination} by Bus")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", f"{re.sub(r'[^a-z0-9]+', '-', origin.lower())}-to-{re.sub(r'[^a-z0-9]+', '-', destination.lower())}-bus")
    tags = [origin, destination, "Bus Travel", "Budget Travel", "Route Guide"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"{origin} to {destination} by bus: prices, journey time, comfort tips, and how to book the cheapest tickets.",
        "tags": tags, "origin": origin, "destination": destination, "routes": routes,
    }
