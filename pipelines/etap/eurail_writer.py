"""eurail_writer.py – 기차/버스/항공 노선 비교 가이드"""
import logging
import os
import re
import sqlite3

from shared.ai_writer import generate as ai_generate

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
# === ETAP v2 Enrichment ===
try:
    from pipelines.etap.data_enricher import (
        format_context_for_prompt,
        get_airline_context,
        get_city_context,
        get_route_context,
    )
    from pipelines.etap.post_processor import (
        calculate_quality_metrics,
        clean_prompt_leaks,
        clean_tags,
        fix_encoding,
    )
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

def generate_eurail_guide(topic):
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
- Write MINIMUM 1,100 words, target 1,200-1,600 words in English. Articles under 1,000 words are rejected
- Expand each H2 section into 2-3 full paragraphs. Do NOT submit a short draft
- Start with a 2-3 sentence introduction paragraph BEFORE any heading (no heading first)
- Title must include "{origin}" and "{destination}"
- Title must NOT contain the phrases "A Practical Guide" or "A Comprehensive Guide"
- If a transport mode has no data, do NOT write a section about it
- Do NOT include any URLs or links
- Do NOT invent prices or durations not in the data
- Required H2 sections (use these EXACT heading styles):
  ## Route Options at a Glance
  ## Train Guide: What to Expect        (omit if no train data)
  ## Bus Guide: What to Expect          (omit if no bus data)
  ## Flight Guide: Should You Fly?      (omit if no flight data)
  ## Tips for Ferry Travel              (omit if no ferry data)
  ## Tips for Booking Ahead
  ## Money-Saving Tips for This Route
  ## Practical Tips for Travelers
- Use exact prices and durations from data
- Write practically with real numbers, in flowing paragraphs

Return ONLY the article in markdown starting with # title"""

    result = ai_generate(
    "You are a European travel writer specializing in transportation. Use only provided data. STRICT RULES: 1) NEVER use these words/phrases: plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, hidden gems, crystal-clear, culinary delights, gastronomic, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Write in flowing paragraphs, not numbered lists. 3) Format prices as whole numbers when .0. 4) NEVER bold an entire paragraph or write label-style bold leads like '**Option:**' — bold is for short phrases only (max 10 words).",
    prompt,
    temperature=0.5,
    max_tokens=3500,
    )
    content = result["content"].strip()

    # v2 후처리
    if HAS_ENRICHMENT:
        content = fix_encoding(content)
        content = clean_prompt_leaks(content)
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
