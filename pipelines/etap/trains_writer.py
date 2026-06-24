"""trains_writer.py – 기차/버스/항공 노선 비교 가이드"""
import os, sqlite3, logging, re
from shared.ai_writer import generate as ai_generate
logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
# === ETAP v2 Enrichment ===
try:
    from pipelines.etap.data_enricher import get_city_context, format_context_for_prompt, get_airline_context, get_route_context
    from pipelines.etap.post_processor import fix_encoding, clean_tags, clean_prompt_leaks, calculate_quality_metrics
    from pipelines.etap.prompt_angles import pick_city_angle, pick_flight_angle, pick_route_angle
    HAS_ENRICHMENT = True
except ImportError:
    HAS_ENRICHMENT = False
# === END ETAP v2 ===

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_route_data(origin, destination):
    conn = _get_db()
    rows = conn.execute("""
        SELECT title, travel_mode, train_min_price, bus_min_price,
               flight_min_price, ferry_min_price, train_min_duration,
               bus_min_duration, flight_min_duration, ferry_min_duration,
               currency, link_url, image_url
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
    summary = f"Route: {origin} → {destination}\n"
    modes = []
    if r.get("train_min_price"):
        modes.append(f"Train: {currency} {r['train_min_price']} | {r.get('train_min_duration', 'N/A')}")
    if r.get("bus_min_price"):
        modes.append(f"Bus: {currency} {r['bus_min_price']} | {r.get('bus_min_duration', 'N/A')}")
    if r.get("flight_min_price"):
        modes.append(f"Flight: {currency} {r['flight_min_price']} | {r.get('flight_min_duration', 'N/A')}")
    if r.get("ferry_min_price"):
        modes.append(f"Ferry: {currency} {r['ferry_min_price']} | {r.get('ferry_min_duration', 'N/A')}")
    summary += "\n".join(modes) + "\n"
    summary += f"Booking link available: {'Yes' if r.get('link_url') else 'No'}\n"
    return summary

def generate_route_guide(topic):
    origin = topic["origin"]
    destination = topic["destination"]
    routes = fetch_route_data(origin, destination)
    if not routes:
        logger.warning(f"No route data for {origin} → {destination}")
        return None
    summary = _build_route_summary(routes, origin, destination)
    if not summary:
        return None
    prompt = f"""Write a travel route guide from {origin} to {destination}.

DATA (use ONLY this data):
{summary}

RULES:
- Write 1,000-1,500 words in English
- Title must include "{origin}" and "{destination}"
- - If a section has 0 matching data items, OMIT that H2 section entirely. Do NOT write filler content.
- Do NOT include any URLs or links
- Do NOT invent prices or durations not in the data
- If a transport mode has no data, do NOT write a section about it
- Required H2 sections (only for modes with data):
  ## {origin} to {destination}: Your Options at a Glance
  ## Traveling by Train (if train data exists)
  ## Traveling by Bus (if bus data exists)
  ## Should You Fly Instead? (if flight data exists)
  ## By Ferry (if ferry data exists)
  ## Price and Time Comparison
  ## Best Time to Book for Cheapest Fares
  ## Practical Tips for This Route
- Use exact prices and durations from data
- Write practically with real numbers

Return ONLY the article in markdown starting with # title"""
    
    result = ai_generate(
    "You are a European travel writer specializing in transportation. Use only provided data. STRICT RULES: 1) NEVER use these words/phrases: plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, hidden gems, crystal-clear, culinary delights, gastronomic, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Write in flowing paragraphs, not numbered lists. 3) Format prices as whole numbers when .0.",
    prompt,
    temperature=0.5,
    max_tokens=3500,
    )
    content = result["content"].strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"{origin} to {destination} Travel Guide")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", f"{re.sub(r'[^a-z0-9]+', '-', origin.lower())}-to-{re.sub(r'[^a-z0-9]+', '-', destination.lower())}")
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Compare train, bus, and flight options from {origin} to {destination}: prices, times, and booking tips.",
        "tags": [origin, destination, "Train Travel", "Bus Travel", "Route Guide"],
        "origin": origin, "destination": destination, "routes": routes,
    }
