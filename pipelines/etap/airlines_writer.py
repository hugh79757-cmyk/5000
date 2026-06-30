"""airlines_writer.py – 항공사 리뷰 (v3: flight_direct + flight_monthly 데이터)"""
import logging
import os
import re
import sqlite3

from shared.ai_writer import generate as ai_generate

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
try:
    from pipelines.etap.post_processor import clean_prompt_leaks, clean_tags, fix_encoding
    HAS_PP = True
except ImportError:
    HAS_PP = False


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _airport_name(code, cache=None):
    if cache is None:
        cache = {}
    if not cache:
        conn = _get_db()
        try:
            for r in conn.execute("""
                SELECT a.iata, c.name
                FROM ref_airports a
                JOIN ref_cities c ON a.city_code = c.code
            """):
                cache[r["iata"]] = r["name"]
        except Exception:
            pass
        conn.close()
    return cache.get(code, code)


def fetch_airline_data(iata_code):
    conn = _get_db()

    # 기본 정보
    airline = conn.execute(
        "SELECT iata, name, country_code, is_lowcost FROM ref_airlines WHERE iata = ?",
        (iata_code,)
    ).fetchone()

    # 노선
    routes = conn.execute(
        "SELECT DISTINCT origin, destination FROM airline_routes WHERE airline = ? ORDER BY popularity DESC",
        (iata_code,)
    ).fetchall()
    airports = set()
    for r in routes:
        airports.add(r[0])
        airports.add(r[1])

    # flight_direct: 실제 항공사 코드로 직항 가격
    directs = conn.execute("""
        SELECT DISTINCT origin, destination, price, flight_number, departure_date
        FROM flight_direct
        WHERE airline = ?
        ORDER BY price ASC
    """, (iata_code,)).fetchall()

    # flight_monthly: 월별 최저가
    monthly = conn.execute("""
        SELECT DISTINCT origin, destination, month, price, stops
        FROM flight_monthly
        WHERE airline = ?
        ORDER BY price ASC
    """, (iata_code,)).fetchall()

    # flight_prices: 해당 항공사 운항 공항 출발 시장가격
    route_prices = []
    try:
        route_prices = conn.execute("""
            SELECT fp.origin, fp.destination, MIN(fp.price) as min_price,
                   MAX(fp.price) as max_price, COUNT(*) as offer_count,
                   GROUP_CONCAT(DISTINCT fp.airline) as sellers
            FROM flight_prices fp
            WHERE fp.origin IN (
                SELECT DISTINCT origin FROM airline_routes WHERE airline = ?
                UNION
                SELECT DISTINCT destination FROM airline_routes WHERE airline = ?
            )
            GROUP BY fp.origin, fp.destination
            ORDER BY min_price ASC
        """, (iata_code, iata_code)).fetchall()
        route_prices = [dict(r) for r in route_prices]
    except Exception:
        pass

    # flight_calendar: 날짜별 가격 (AA 운항 공항 기반)
    calendar = []
    try:
        calendar = conn.execute("""
            SELECT DISTINCT origin, destination, date, price, airline
            FROM flight_calendar
            WHERE origin IN (
                SELECT DISTINCT origin FROM airline_routes WHERE airline = ?
                UNION
                SELECT DISTINCT destination FROM airline_routes WHERE airline = ?
            )
            ORDER BY price ASC
        """, (iata_code, iata_code)).fetchall()
        calendar = [dict(r) for r in calendar]
    except Exception:
        pass

    # popular_directions: 해당 항공사의 인기 노선
    popular = []
    try:
        popular = conn.execute("""
            SELECT DISTINCT origin, destination, price, stops, departure_date
            FROM popular_directions
            WHERE airline = ?
            ORDER BY price ASC
        """, (iata_code,)).fetchall()
        popular = [dict(r) for r in popular]
    except Exception:
        pass

    conn.close()
    return (
        dict(airline) if airline else None,
        [dict(r) for r in routes],
        len(airports),
        [dict(d) for d in directs],
        [dict(m) for m in monthly],
        route_prices,
        popular,
        calendar,
    )


def generate_airline_review(topic):
    iata = topic.get("iata_code", "")
    airline_name = topic.get("airline_name", "")

    airline_data, routes, airport_count, directs, monthly, route_prices, popular, calendar = fetch_airline_data(iata)
    if not airline_data:
        logger.warning(f"No airline data for {iata}")
        return None

    name = airline_data.get("name", airline_name or iata)
    is_lcc = airline_data.get("is_lowcost", 0)
    lcc_str = "low-cost carrier (LCC)" if is_lcc else "full-service carrier"
    country = airline_data.get("country_code", "Unknown")

    # 데이터 풍부도 체크
    has_routes = len(routes) > 0
    len(directs) > 0 or len(monthly) > 0
    total_data_points = len(routes) + len(directs) + len(monthly)

    if total_data_points < 3:
        logger.warning(f"[airlines] {name} ({iata}): 데이터 부족 ({total_data_points}건) - 스킵")
        return None

    # 요약 구성
    lines = []
    lines.append(f"AIRLINE: {name} (IATA: {iata})")
    lines.append(f"Type: {lcc_str}")
    lines.append(f"Country: {country}")
    lines.append(f"Route count: {len(routes)}")
    lines.append(f"Airports served: {airport_count}")

    if routes:
        lines.append(f"\nROUTE NETWORK ({len(routes)} routes):")
        shown_routes = set()
        for r in routes[:30]:
            o_city = _airport_name(r["origin"])
            d_city = _airport_name(r["destination"])
            pair = f"{o_city} → {d_city}"
            if pair not in shown_routes:
                lines.append(f"  {pair}")
                shown_routes.add(pair)

    if directs:
        lines.append(f"\nDIRECT FLIGHT PRICES ({len(directs)} data points):")
        seen = set()
        for d in directs:
            o_city = _airport_name(d["origin"])
            d_city = _airport_name(d["destination"])
            key = f"{d['origin']}-{d['destination']}"
            if key not in seen:
                dep = d.get("departure_date", "")[:10]
                fnum = d.get("flight_number", "")
                lines.append(f"  {o_city} → {d_city}: ${d['price']:.0f} (flight {iata}{fnum}, {dep})")
                seen.add(key)

    if monthly:
        lines.append(f"\nMONTHLY PRICE TRENDS ({len(monthly)} data points):")
        # 루트별 월별 정리
        route_months = {}
        for m in monthly:
            key = f"{m['origin']}-{m['destination']}"
            if key not in route_months:
                route_months[key] = []
            route_months[key].append(m)

        for key, months in list(route_months.items())[:10]:
            o, d = key.split("-")
            o_city = _airport_name(o)
            d_city = _airport_name(d)
            month_str = ", ".join(f"{m['month']}: ${m['price']:.0f}" for m in sorted(months, key=lambda x: x["month"]))
            lines.append(f"  {o_city} → {d_city}: {month_str}")


    # Market prices (flight_prices via airline_routes)
    if route_prices:
        lines.append(f"\nMARKET PRICES ({len(route_prices)} routes with comparison pricing):")
        for rp in route_prices[:40]:
            o_city = _airport_name(rp["origin"])
            d_city = _airport_name(rp["destination"])
            if rp["min_price"] == rp["max_price"]:
                price_str = f"${rp['min_price']:.0f}"
            else:
                price_str = f"${rp['min_price']:.0f}-${rp['max_price']:.0f}"
            lines.append(f"  {o_city} → {d_city}: {price_str} ({rp['offer_count']} offers from {rp['sellers']})")

    # Popular directions for this airline
    if popular:
        lines.append(f"\nPOPULAR ROUTES ({len(popular)} trending directions):")
        for p in popular[:30]:
            o_city = _airport_name(p["origin"])
            d_city = _airport_name(p["destination"])
            stops_str = "non-stop" if p.get("stops", 0) == 0 else f"{p['stops']} stop(s)"
            dep = (p.get("departure_date") or "")[:10]
            lines.append(f"  {o_city} → {d_city}: ${p['price']:.0f} ({stops_str}, {dep})")


    # Price calendar
    if calendar:
        from collections import defaultdict
        cal_by_dest = defaultdict(list)
        for c in calendar:
            cal_by_dest[c["destination"]].append(c)
        lines.append(f"\nPRICE CALENDAR ({len(calendar)} price points across {len(cal_by_dest)} destinations):")
        for dest, entries in sorted(cal_by_dest.items(), key=lambda x: min(e["price"] for e in x[1]))[:20]:
            cheapest = min(entries, key=lambda x: x["price"])
            d_city = _airport_name(dest)
            lines.append(f"  {d_city} ({dest}): cheapest ${cheapest['price']:.0f} on {cheapest['date']} ({len(entries)} dates)")

    summary = "\n".join(lines)

    # 동적 섹션 구성
    sections = [f"## {name} at a Glance"]
    if has_routes:
        sections.append(f"## Where {name} Flies: Route Network")
    if directs:
        sections.append(f"## Current Prices on {name} Flights")
    if monthly:
        sections.append(f"## Best Month to Fly {name}")
    if route_prices:
        sections.append(f"## Market Prices: What You'll Pay on {name} Routes")
    if popular:
        sections.append(f"## Trending Routes on {name}")
    sections.append(f"## What to Expect Flying {name}")
    sections.append("## Booking Tips")
    sections.append(f"## Verdict: Is {name} Worth It?")
    section_text = "\n".join(sections)

    prompt = f"""Write an airline review for {name} ({iata}).

{summary}

STRUCTURE (only include sections where data exists):
{section_text}

RULES:
- Use ONLY the data above. Do NOT invent baggage policies, meal options, fleet details, or lounge info.
- For routes: group by region/hub, mention specific city pairs with prices.
- For prices: cite exact dollar amounts and flight numbers from the data.
- For monthly trends: identify cheapest and most expensive months.
- Be honest: if data is limited, say "based on {len(directs)} direct flights and {len(monthly)} monthly data points in our database."
- Give a clear verdict: who should fly this airline.
- Use the STRUCTURE sections above as H2 headings (## Section Name). Each section MUST start with ## heading.
- Flowing paragraphs only within each section, NO bullet points or numbered lists.
- NEVER use: plethora, vibrant, bustling, tapestry, myriad, embark, hidden gem, unforgettable, crystal-clear, soak in, immerse yourself, treasure trove, must-visit, paradise, bucket list, adventure awaits

Return ONLY the article in markdown starting with # title"""

    result = ai_generate(

        "You are an aviation journalist who writes data-driven airline reviews. Use ONLY provided data, never fabricate details. Write in flowing paragraphs. Format prices as whole numbers.",

        prompt,

        temperature=0.5,

        max_tokens=4000,

    )

    content = result["content"].strip()

    content = resp.choices[0].message.content.strip()
    if HAS_PP:
        content = fix_encoding(content)
        content = clean_prompt_leaks(content)

    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else f"{name} Airline Review"
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()

    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + "-airline-review")
    tags = [name, iata, "Airline Review", "Aviation"]
    if HAS_PP:
        tags = clean_tags(tags)

    return {
        "title": title, "slug": slug, "content": content,
        "description": f"{name} ({iata}) airline review: {len(routes)} routes, direct flight prices, and monthly trends.",
        "tags": [t for t in tags if t],
        "airline_name": name, "iata": iata,
    }
