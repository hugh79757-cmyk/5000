"""항공권 딜 글 작성기 - DB 가격 데이터 기반 GPT 글 생성
"""
import logging
import os
import sqlite3
from datetime import datetime

from dotenv import load_dotenv

from shared.ai_writer import generate as ai_generate

load_dotenv("/Users/twinssn/Projects/5000/.env")
load_dotenv(os.path.expanduser("~/.env.common"))

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "travel-en.db"
)

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

try:
    from pipelines.etap.editorial_synthesis import editorial_synthesis_step
except ImportError:
    editorial_synthesis_step = None


def _inject_editorial_synthesis(body, topic=None):
    """Phase 70 Wave 3: append deterministic editorial synthesis paragraph.

    No-op unless the topic carries a recognized ``topic_type`` (graceful
    degradation — returns body unchanged when no unique data resolves).
    """
    if not body or editorial_synthesis_step is None:
        return body
    try:
        from pipelines.etap.data_adapters import get_unique_data_points
        _t = topic or {}
        _tt = _t.get("topic_type")
        _ud = get_unique_data_points(_tt, _t.get("topic_id")) if _tt else []
        if _ud:
            _t["unique_data"] = _ud  # Phase 72 W4: pipeline이 저장할 수 있게 points 노출
        _s = editorial_synthesis_step(body, _ud, _t)
    except Exception as _e:
        logger.warning("[editorial] synthesis skipped: %s", _e)
        return body
    if not _s:
        return body
    return body.rstrip() + "\n\n" + _s + "\n"

def _get_db():
    return sqlite3.connect(DB_PATH)


def _fetch_price_data(origin, destination):
    db = _get_db()
    data = {}
    rows = db.execute("""
        SELECT price, airline, stops, departure_date, return_date
        FROM flight_prices WHERE origin=? AND destination=?
        ORDER BY price LIMIT 5
    """, (origin, destination)).fetchall()
    data["latest"] = [{"price": r[0], "airline": r[1], "stops": r[2], "depart": r[3], "return": r[4]} for r in rows]

    rows2 = db.execute("""
        SELECT price, airline, departure_date, return_date
        FROM flight_direct WHERE origin=? AND destination=?
        ORDER BY price LIMIT 3
    """, (origin, destination)).fetchall()
    data["direct"] = [{"price": r[0], "airline": r[1], "depart": r[2], "return": r[3]} for r in rows2]

    rows3 = db.execute("""
        SELECT month, price, airline, stops
        FROM flight_monthly WHERE origin=? AND destination=?
        ORDER BY price
    """, (origin, destination)).fetchall()
    data["monthly"] = [{"month": r[0], "price": r[1], "airline": r[2], "stops": r[3]} for r in rows3]

    rows4 = db.execute("""
        SELECT date, price, airline, stops
        FROM flight_calendar WHERE origin=? AND destination=?
        ORDER BY price LIMIT 10
    """, (origin, destination)).fetchall()
    data["calendar"] = [{"date": r[0], "price": r[1], "airline": r[2], "stops": r[3]} for r in rows4]

    airline_codes = set()
    for key in ["latest", "direct", "monthly", "calendar"]:
        for item in data.get(key, []):
            if item.get("airline"):
                airline_codes.add(item["airline"])
    if airline_codes:
        ph = ",".join(["?"] * len(airline_codes))
        names = db.execute(f"SELECT iata, name FROM ref_airlines WHERE iata IN ({ph})", list(airline_codes)).fetchall()
        data["airline_names"] = {r[0]: r[1] for r in names}
    else:
        data["airline_names"] = {}
    db.close()
    return data


def _build_price_summary(pd):
    lines = []
    names = pd.get("airline_names", {})
    if pd["latest"]:
        lines.append("Recent lowest fares (last 48h):")
        for p in pd["latest"]:
            aname = names.get(p["airline"], p["airline"])
            lines.append(f"  ${p['price']} via {aname}, {p['stops']} stop(s), depart {p['depart']}")
    if pd["direct"]:
        lines.append("Direct (non-stop) flights:")
        for p in pd["direct"]:
            aname = names.get(p["airline"], p["airline"])
            lines.append(f"  ${p['price']} via {aname}, depart {p['depart']}")
    if pd["monthly"]:
        lines.append("Cheapest month to fly:")
        for p in pd["monthly"][:6]:
            aname = names.get(p["airline"], p["airline"])
            lines.append(f"  {p['month']}: ${p['price']} ({aname}, {p['stops']} stops)")
    if pd["calendar"]:
        lines.append("Cheapest specific dates:")
        for p in pd["calendar"][:5]:
            aname = names.get(p["airline"], p["airline"])
            lines.append(f"  {p['date']}: ${p['price']} ({aname}, {p['stops']} stops)")
    return "\n".join(lines) if lines else "No price data available."


def generate_flight_deal(topic):
    origin = topic["origin"]
    destination = topic["destination"]
    o_city = topic["origin_city"]
    d_city = topic["dest_city"]
    title = topic["title"]
    price_data = _fetch_price_data(origin, destination)
    price_summary = _build_price_summary(price_data)
    has_data = bool(price_data["latest"] or price_data["monthly"] or price_data["calendar"])
    today = datetime.now().strftime("%B %Y")
    prompt = f"""Write a comprehensive flight deal article in English.

TITLE: {title}
ROUTE: {o_city} ({origin}) to {d_city} ({destination})
CURRENT DATE: {today}

REAL PRICE DATA FROM OUR DATABASE:
{price_summary}

ARTICLE REQUIREMENTS:
- Write MINIMUM 1,100 words, target 1,200-1,600 words in English. Articles under 1,000 words are rejected. American English, friendly practical tone
- Use the EXACT prices from the data above when available
- Include specific airline names, dates, and prices from the data

REQUIRED H2 SECTIONS:
## Current Flight Prices: {o_city} to {d_city}
## Best Time to Book Flights to {d_city}
## Direct vs. Connecting Flights
## Which Airlines Fly This Route?
## Money-Saving Tips for {o_city} to {d_city} Flights
## What to Expect When You Arrive in {d_city}

RULES:
- Do NOT invent prices. Only use prices from the data provided.
- If a section has 0 relevant data, OMIT that H2 section entirely. Do NOT write filler content.
- Do NOT include any internal links, URLs, or markdown links in the text
- If no price data, use phrases like "prices typically range from..."
- No affiliate links or URLs, no markdown beyond H2, write in paragraphs not bullet lists
- Include a brief intro before the first H2
- Title must NOT contain the phrases "A Practical Guide" or "A Comprehensive Guide"
- NEVER bold an entire paragraph or write label-style bold leads like '**Option:**' — bold is for short phrases only (max 10 words)
"""
    try:
        result = ai_generate(
        "You are a travel journalist writing data-driven flight deal articles. Use real price data when provided. Be specific and helpful. STRICT RULES: 1) NEVER use these words/phrases: plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, hidden gems, crystal-clear, culinary delights, gastronomic, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Write in flowing paragraphs, not numbered lists. 3) Format prices as whole numbers when .0.",
        prompt,
        temperature=0.5,
        max_tokens=3500,
        )
        content = result["content"].strip()
        if content.startswith("# "):
            content = content.split("\n", 1)[1].strip()
        description = f"Find the cheapest flights from {o_city} to {d_city}. Real-time prices, best booking times, airline comparisons, and money-saving tips."
        tags = [o_city, d_city, "flights", "travel deals", "cheap flights"]
        topic_ctx = {"topic_type": "flight", "topic_id": topic.get("id"), "city": d_city, "country": "", "slug": topic.get("slug", "")}
        content = _inject_editorial_synthesis(content, topic_ctx)
        return {
            "title": title, "slug": topic["slug"], "content": content,
            "description": description, "tags": tags,
            "origin": o_city, "destination": d_city, "has_price_data": has_data,
            "unique_data_points": topic_ctx.get("unique_data") or [],
        }
    except Exception as e:
        logger.exception(f"[FlightWriter] GPT error: {e}")
        return None
