"""deals_writer.py - Flight deals guide (v4: all 35 routes fully utilized)"""
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta

from shared.ai_writer import generate as ai_generate

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
try:
    from pipelines.etap.post_processor import clean_prompt_leaks, clean_tags, fix_encoding
    HAS_PP = True
except ImportError:
    HAS_PP = False

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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_airport_cities():
    conn = _get_db()
    try:
        rows = conn.execute("""
            SELECT a.iata, c.name
            FROM ref_airports a
            JOIN ref_cities c ON a.city_code = c.code
        """).fetchall()
        result = {r["iata"]: r["name"] for r in rows}
    except Exception:
        result = {}
    conn.close()
    return result

def _fetch_deals(origin_code):
    """루트별 최저가 + 최고가 + 판매처 수"""
    conn = _get_db()
    rows = conn.execute("""
        SELECT destination,
               MIN(price) as min_price,
               MAX(price) as max_price,
               GROUP_CONCAT(DISTINCT airline) as sellers,
               MIN(stops) as min_stops,
               COUNT(*) as offer_count,
               MIN(departure_date) as earliest_date,
               MAX(departure_date) as latest_date
        FROM flight_prices
        WHERE origin = ? AND price > 0
        GROUP BY destination
        ORDER BY min_price ASC
    """, (origin_code,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]




def _fetch_popular_directions(origin_code):
    """popular_directions: 실제 항공사, 직항 정보 포함"""
    conn = _get_db()
    rows = conn.execute("""
        SELECT destination, price, airline, stops, departure_date, return_date
        FROM popular_directions
        WHERE origin = ? AND price > 0
        ORDER BY price ASC
    """, (origin_code,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _fetch_calendar(origin_code):
    """flight_calendar: 날짜별 최저가"""
    conn = _get_db()
    rows = conn.execute("""
        SELECT destination, date, price, airline, stops
        FROM flight_calendar
        WHERE origin = ? AND price > 0
        ORDER BY date ASC
    """, (origin_code,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def generate_deals_guide(topic):
    origin_code = topic["origin"]
    origin_city = topic.get("origin_city", origin_code)

    deals = _fetch_deals(origin_code)

    # 추가 데이터 소스 로드
    popular_dirs = _fetch_popular_directions(origin_code)
    calendar_data = _fetch_calendar(origin_code)
    if not deals:
        logger.warning(f"No deals for {origin_city} ({origin_code})")
        return None

    airport_cities = _load_airport_cities()
    for d in deals:
        d["dest_city"] = airport_cities.get(d["destination"], d["destination"])

    budget = [d for d in deals if d["min_price"] < 200]
    mid = [d for d in deals if 200 <= d["min_price"] <= 500]
    premium = [d for d in deals if d["min_price"] > 500]

    today = datetime.now().strftime("%B %Y")
    cheapest = deals[0]

    # 풍부한 요약: 모든 루트의 min/max/sellers 포함
    lines = []
    lines.append(f"FLIGHT DEALS FROM {origin_city} ({origin_code}) — {today}")
    lines.append(f"Total unique destinations: {len(deals)}")
    lines.append(f"Overall price range: ${cheapest['min_price']:.0f} - ${deals[-1]['max_price']:.0f}")
    lines.append(f"Cheapest deal: {origin_city} to {cheapest['dest_city']} from ${cheapest['min_price']:.0f}")

    for label, group in [("UNDER $200", budget), ("$200-$500", mid), ("OVER $500", premium)]:
        if group:
            lines.append("")
            lines.append(f"[{label}] — {len(group)} destinations:")
            for d in group:
                sellers = d.get("sellers", "")
                seller_count = len(sellers.split(",")) if sellers else 0
                price_range = f"${d['min_price']:.0f}"
                if d["max_price"] > d["min_price"] * 1.1:
                    price_range += f"-${d['max_price']:.0f}"
                stops = "direct" if d["min_stops"] == 0 else f"{d['min_stops']} stop(s)"
                dates = f"{(d.get('earliest_date') or '')[:10]}"
                if d.get("latest_date") and d["latest_date"] != d.get("earliest_date"):
                    dates += f" to {d['latest_date'][:10]}"
                lines.append(f"  {d['dest_city']} ({d['destination']}): {price_range} | {stops} | {d['offer_count']} offers from {seller_count} seller(s) | dates: {dates}")


    # Popular directions: 실제 항공사 + 직항 데이터
    if popular_dirs:
        lines.append(f"\nDIRECT FLIGHTS (verified airline data, {len(popular_dirs)} routes):")
        airport_cities = _load_airport_cities()
        for pd in popular_dirs:
            dest_city = airport_cities.get(pd["destination"], pd["destination"])
            stops_str = "DIRECT (non-stop)" if pd["stops"] == 0 else f"{pd['stops']} stop(s)"
            dep = (pd.get("departure_date") or "")[:10]
            lines.append(f"  {origin_city} → {dest_city} ({pd['destination']}): ${pd['price']:.0f} on {pd['airline']} | {stops_str} | departs {dep}")

    # Calendar: 날짜별 최저가
    if calendar_data:
        # 목적지별 최저가 날짜
        from collections import defaultdict
        cal_by_dest = defaultdict(list)
        for c in calendar_data:
            cal_by_dest[c["destination"]].append(c)
        lines.append(f"\nPRICE CALENDAR ({len(calendar_data)} date-price points across {len(cal_by_dest)} destinations):")
        for dest, entries in sorted(cal_by_dest.items(), key=lambda x: min(e["price"] for e in x[1]))[:10]:
            cheapest_cal = min(entries, key=lambda x: x["price"])
            dest_city = airport_cities.get(dest, dest)
            lines.append(f"  {dest_city} ({dest}): cheapest ${cheapest_cal['price']:.0f} on {cheapest_cal['date']} ({len(entries)} dates tracked)")

    summary = "\n".join(lines)

    # 동적 섹션 (제목은 hugo_writer H2 가드 허용 패턴만 사용 — 181패턴 실측 기반)
    sections = ["## Quick Facts"]
    if budget:
        sections.append(f"## Current Flight Prices Under $200 ({len(budget)} destinations)")
    if mid:
        sections.append(f"## Current Flight Prices $200-$500 ({len(mid)} destinations)")
    if premium:
        sections.append(f"## Current Flight Prices Over $500 ({len(premium)} destinations)")
    if popular_dirs:
        direct_count = sum(1 for p in popular_dirs if p["stops"] == 0)
        if direct_count > 0:
            sections.append("## Direct vs. Connecting Flights")
    if calendar_data:
        sections.append(f"## Money-Saving Tips for {origin_city} Travelers")
    sections.append("## Booking Tips")
    section_text = "\n".join(sections)

    prompt = f"""Write a flight deals guide for travelers from {origin_city}.

{summary}

STRUCTURE (use these EXACT H2 headings in your article):
{section_text}

- You MUST use the H2 headings above as markdown ## headings in your output
- Each H2 section must have at least 2 paragraphs

RULES:
- Start with a 2-3 sentence introduction paragraph BEFORE any heading (do NOT begin the article with an H2). Open with the single best deal: "{origin_city} to {cheapest['dest_city']} for ${cheapest['min_price']:.0f}."
- Write MINIMUM 1,100 words, target 1,200-1,600 words in English. Articles under 1,000 words are rejected. Expand each section into 2-3 full paragraphs.
- Use ONLY destinations and prices from the data. Do NOT invent destinations.
- For EACH destination mention: price, whether direct, travel dates available, and one sentence about why the destination is worth visiting.
- When price ranges are wide (e.g. $84-$150), explain why: different sellers, dates, or stops.
- Group destinations geographically within each price tier when possible (e.g. "Florida destinations", "Caribbean", "Europe").
- In the booking tips section, name the specific sellers from the data (e.g. Farera, Kiwi.com) and compare them.
- Flowing paragraphs only. NO bullet points or numbered lists.
- NEVER use: plethora, vibrant, bustling, tapestry, myriad, embark, hidden gem, unforgettable, crystal-clear, treasure trove, must-visit, paradise, bucket list, adventure awaits

Return ONLY the article in markdown starting with # title"""

    result = ai_generate(

        "You are a travel journalist writing data-driven flight deal articles. Use ONLY provided price data. Write flowing paragraphs, no lists. Prices as whole numbers. Start with the cheapest deal.",

        prompt,

        temperature=0.5,

        max_tokens=4000,

    )

    content = result["content"].strip()
    if HAS_PP:
        content = fix_encoding(content)
        content = clean_prompt_leaks(content)

    # ── Per-paragraph price table (4 cols, price approx + button) ──
    def _deals_table(rows: list) -> str:
        header = "\n\n| Destination | From Price | Stops | Details |\n|---|---|---|---|\n"
        body = []
        marker = os.getenv("TRAVELPAYOUTS_MARKER", "") or os.getenv("AVIASALES_MARKER", "")
        for r in rows[:10]:
            city = r.get("dest_city", r.get("destination", ""))
            iata = r.get("destination", "")
            dest_label = f"{city} ({iata})" if city != iata else city
            price = f"From ${int(r['min_price']):,}" if r.get("min_price") else "—"
            stops_raw = r.get("min_stops", 0)
            try:
                stops_raw = int(stops_raw)
            except Exception:
                stops_raw = 0
            stops = "Nonstop" if stops_raw == 0 else f"{stops_raw} stop(s)"
            # Aviasales/JetRadar search link — dynamic future date (DB dates are stale Apr/May)
            today_str = datetime.now().strftime("%Y-%m-%d")
            future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            dep_date = (r.get("earliest_date") or r.get("departure_date") or "")[:10]
            # if DB date is past or empty, use future date (30 days out)
            if not dep_date or dep_date < today_str:
                dep_date = future_date
            if marker and dep_date:
                link = f"https://www.jetradar.com/searches/new?origin_iata={origin_code}&destination_iata={iata}&depart_date={dep_date}&adults=1&marker={marker}"
            elif marker:
                link = f"https://www.aviasales.com/search/{origin_code}{iata}?marker={marker}"
            elif dep_date:
                link = f"https://www.jetradar.com/searches/new?origin_iata={origin_code}&destination_iata={iata}&depart_date={dep_date}&adults=1"
            else:
                link = f"https://www.aviasales.com/search/{origin_code}{iata}"
            body.append(f"| {dest_label} | {price}* | {stops} | [Check Details]({link}) |")
        note = "\n* Prices are approximate and may change. Please click **Check Details** to verify current fare.\n"
        return header + "\n".join(body) + note

    # Insert table right after each price-tier H2
    if budget:
        content = re.sub(
            r"(## Current Flight Prices Under \$200[^\n]*\n)",
            r"\1" + _deals_table(budget),
            content, count=1
        )
    if mid:
        content = re.sub(
            r"(## Current Flight Prices \$200-\$500[^\n]*\n)",
            r"\1" + _deals_table(mid),
            content, count=1
        )
    if premium:
        content = re.sub(
            r"(## Current Flight Prices Over \$500[^\n]*\n)",
            r"\1" + _deals_table(premium),
            content, count=1
        )

    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else f"Flight Deals From {origin_city}"
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()

    tags = [origin_city, "Flight Deals", "Cheap Flights", "Travel Deals"]
    if HAS_PP:
        tags = clean_tags(tags)

    topic_ctx = {"topic_type": "deals", "topic_id": topic.get("id"), "city": origin_city, "country": "", "slug": topic.get("slug", "")}
    content = _inject_editorial_synthesis(content, topic_ctx)

    return {
        "title": title, "slug": topic["slug"], "content": content,
        "description": f"Best flight deals from {origin_city}: {len(deals)} destinations, fares from ${cheapest['min_price']:.0f}. Updated {today}.",
        "tags": [t for t in tags if t],
        "origin": origin_city, "deals": deals,
        "unique_data_points": topic_ctx.get("unique_data") or [],
    }
