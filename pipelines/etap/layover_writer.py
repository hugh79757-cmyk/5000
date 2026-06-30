"""layover_writer.py - Layover Tours And Stopover Guide generator"""
import logging
import os
import re
import sqlite3

from pipelines.etap.quality_guard import preprocess_tours

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _safe_price(val):
    try:
        return float(str(val).replace("$","").replace(",","").strip())
    except:
        return 0

# category → 분 매핑 (보수적 추정)
_CATEGORY_DURATION = {
    "Layover Tours":      180,
    "Port Transfers":      60,
    "Private Drivers":    120,
    "Audio Guides":       120,
    "Self-guided Tours":  180,
    "City Tours":         240,
    "Half-day Tours":     210,
    "Sightseeing Passes": 240,
    "Ports of Call Tours":300,
    "Full-day Tours":     480,
    "Multi-day Tours":   1440,
}

# description 텍스트에서 duration 보조 추출
import re as _re

from shared.ai_writer import generate as ai_generate

_DUR_PATTERNS = [
    (_re.compile(r"(\d+)[-\s]?night", _re.IGNORECASE),  lambda m: int(m.group(1)) * 1440),
    (_re.compile(r"(\d+)[-\s]?day",   _re.IGNORECASE),  lambda m: int(m.group(1)) * 480),
    (_re.compile(r"(\d+)\s*hour",     _re.IGNORECASE),  lambda m: int(m.group(1)) * 60),
    (_re.compile(r"half[-\s]day",      _re.IGNORECASE),  lambda m: 210),
    (_re.compile(r"full[-\s]day",      _re.IGNORECASE),  lambda m: 480),
]

def _estimate_duration(tour: dict) -> int:
    """Category + description에서 소요 시간(분) 추정. 실패 시 category 기본값."""
    desc = (tour.get("description") or "").lower()
    for pattern, extractor in _DUR_PATTERNS:
        m = pattern.search(desc)
        if m:
            mins = extractor(m)
            if 30 <= mins <= 14400:   # 30분~10일 범위만 신뢰
                return mins
    # description 파싱 실패 → category 기본값
    cat = tour.get("category", "")
    return _CATEGORY_DURATION.get(cat, 240)  # 기본 4시간

def fetch_tours(city, country=None):
    conn = _get_db()
    rows = conn.execute("""
        SELECT product_name, description, category, price, currency,
               discount_percent as discount, image_url, deep_link,
               city, country
        FROM viator_tours
        WHERE (city = ? OR city IN (SELECT alias FROM city_aliases WHERE canonical_name = ?))
          AND category IN (
              'Layover Tours','Half-day Tours','Full-day Tours','City Tours',
              'Audio Guides','Self-guided Tours','Ports of Call Tours',
              'Sightseeing Passes','Port Transfers','Private Drivers'
          )
          AND deep_link IS NOT NULL AND deep_link != ''
        AND category != 'Multi-day Tours'
        ORDER BY CAST(price AS REAL) ASC
    """, (city, city)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _bucket_by_duration(tours):
    """Category + description 기반 duration 추정으로 시간대 버킷 분류."""
    short  = []  # ≤ 180분 (3시간 이하)
    half   = []  # 181–300분 (3~5시간, 반나절)
    full   = []  # 301–1439분 (5시간+, 당일)
    multi  = []  # 1440분+ (1박 이상 — layover 추천 제외)

    for t in tours:
        dur = _estimate_duration(t)
        if dur >= 1440:
            multi.append(t)   # 멀티데이 → layover 비추천
        elif dur <= 180:
            short.append(t)
        elif dur <= 300:
            half.append(t)
        else:
            full.append(t)

    return short, half, full, multi

def _build_tour_line(t) -> str:
    name  = re.sub(r"^Save [\d.]+%!\s*", "", t["product_name"])
    price = round(_safe_price(t.get("price", 0)))
    disc  = t.get("discount") or ""
    disc_str = f" | -{disc}% off" if disc and str(disc) not in ("0","","0.0") else ""
    dur     = _estimate_duration(t)
    dur_str = f" | ~{dur//60}h{dur%60:02d}m" if dur else ""
    return f"- {name} | ${price}{disc_str}{dur_str} | {t.get('category','')}"

def _build_summary(tours, city):
    if not tours:
        return None, None

    short, half, full, _multi = _bucket_by_duration(tours)
    discounted = [t for t in tours if t.get("discount") and
                  str(t["discount"]) not in ("0","","0.0")]
    budget  = [t for t in tours if 0 < _safe_price(t.get("price")) < 30]
    mid     = [t for t in tours if 30 <= _safe_price(t.get("price")) <= 100]
    [t for t in tours if _safe_price(t.get("price")) > 100]

    # 테이블 투어: mid price 우선 5개
    table_tours = (mid[:5] if len(mid) >= 2 else budget[:5]) or tours[:5]

    summary  = f"City: {city}\nTotal tours: {len(tours)}\n\n"
    summary += "[TABLE TOURS — body text MUST reference only these tours]\n"
    for t in table_tours:
        summary += _build_tour_line(t) + "\n"
    summary += "\n"

    # 시간대별 버킷 (실제 데이터 기반)
    if short:
        summary += "[SHORT TOURS ≤3h — good for tight layovers]\n"
        for t in short[:4]:
            summary += _build_tour_line(t) + "\n"
        summary += "\n"
    if half:
        summary += "[HALF-DAY TOURS 3-5h]\n"
        for t in half[:4]:
            summary += _build_tour_line(t) + "\n"
        summary += "\n"
    if full:
        summary += "[FULL-DAY TOURS 5h+ — only for layovers 8h+]\n"
        for t in full[:3]:
            summary += _build_tour_line(t) + "\n"
        summary += "\n"
    if discounted:
        deals = sorted(discounted,
                       key=lambda x: float(str(x.get("discount","0")) or 0), reverse=True)
        summary += "[DEALS]\n"
        for t in deals[:3]:
            summary += _build_tour_line(t) + "\n"
        summary += "\n"

    # 시간대 가이드 요약 (GPT가 참고할 수 있도록)
    summary += "[LAYOVER TIME GUIDE — based on actual tour durations]\n"
    if short:
        names = [re.sub(r"^Save [\d.]+%!\s*","",t["product_name"]) for t in short[:2]]
        summary += f"- 2-3h layover: {', '.join(names)}\n"
    if half:
        names = [re.sub(r"^Save [\d.]+%!\s*","",t["product_name"]) for t in half[:2]]
        summary += f"- 4-5h layover: {', '.join(names)}\n"
    if full:
        names = [re.sub(r"^Save [\d.]+%!\s*","",t["product_name"]) for t in full[:2]]
        summary += f"- 8h+ layover: {', '.join(names)}\n"
    elif not full and half:
        summary += "- 8h+ layover: combine two half-day tours or explore independently\n"

    return summary, table_tours

def generate_layover_guide(topic):
    city    = topic["city"]
    country = topic.get("country", "")
    tours   = fetch_tours(city, country)
    tours, _pre_issues, _excluded = preprocess_tours(tours, city=city)
    if not tours:
        logger.warning(f"[layover_writer] No tours for {city}")
        return None

    summary, table_tours = _build_summary(tours, city)
    if not summary:
        return None

    short, half, _full, _multi = _bucket_by_duration(tours)

    table_tour_names = [
        re.sub(r"^Save [\d.]+%!\s*", "", t["product_name"])
        for t in table_tours
    ]
    "\n".join(f"  {i+1}. {n} (${round(_safe_price(t.get('price',0)))})"
                                for i, (n, t) in enumerate(zip(table_tour_names, table_tours, strict=False)))

    # 섹션 조건부 구성
    sections = [f"## Making the Most of a Layover in {city}"]
    sections.append(f"## Best Layover Tours in {city}")
    if short or half:
        sections.append("## What You Can See by Layover Length")
    sections.append("## Prices and Logistics")
    sections.append(f"## Layover Tips for {city} Airport")
    h2s = "\n".join(f"  {s}" for s in sections)

    # 투어 설명 블록 사전 구성 — GPT가 투어를 지어내지 못하도록
    # 각 TABLE TOUR의 description을 직접 전달
    import re as _re2
    tour_desc_block = ""
    for i, t in enumerate(table_tours):
        tname  = _re2.sub(r"^Save [\d.]+%!\s*", "", t["product_name"])
        tprice = round(_safe_price(t.get("price", 0)))
        tdesc  = (t.get("description") or "")[:200].strip()
        tdur   = _estimate_duration(t)
        tdur_str = f"~{tdur//60}h{tdur%60:02d}m" if tdur else "duration varies"
        tdisc  = t.get("discount") or ""
        tdisc_str = f" ({tdisc}% off)" if tdisc and str(tdisc) not in ("0","","0.0") else ""
        tour_desc_block += f"""
TOUR {i+1}:
  Name: {tname}
  Price: ${tprice}{tdisc_str}
  Duration: {tdur_str}
  Category: {t.get("category","")}
  Description: {tdesc}
"""

    layover_guide_str = ""
    if "[LAYOVER TIME GUIDE" in summary:
        layover_guide_str = summary.split("[LAYOVER TIME GUIDE")[1]

    prompt = f"""Write a layover stopover guide for {city}, {country}.

=== VERIFIED TOUR DATA (USE ONLY THESE — never invent tours not listed here) ===
{tour_desc_block}

=== LAYOVER TIME GUIDE (from actual tour durations) ===
{layover_guide_str}

=== ARTICLE STRUCTURE ===
Write these H2 sections in order:
{h2s}

SECTION-BY-SECTION INSTRUCTIONS:

## Making the Most of a Layover in {city}
- First sentence must mention the airport name and distance to city center
- Explain what type of destination {city} is (port city, ancient history hub, transit point)
- What layover length this city suits best
- 2 paragraphs, NO tour names in this section

## Best Layover Tours in {city}
- Write one paragraph per tour from VERIFIED TOUR DATA (all {len(table_tours)} tours)
- Format: tour name in bold + $price, then 2-3 sentences based on the Description field
- Do NOT use numbered lists — flowing paragraphs only
- Do NOT invent any detail not in the Description field above
- Start each paragraph with a different word

## What You Can See by Layover Length
- Use ONLY the LAYOVER TIME GUIDE data above
- Format exactly as: "With 2-3 hours:" / "With 4-5 hours:" / "With 8+ hours:"
- Only include time windows that have matching tours
- Never recommend a tour whose duration exceeds the layover window

## Prices and Logistics
- State the price range from VERIFIED TOUR DATA (cheapest to most expensive)
- Estimate airport-to-city transport: distance, options, time, rough cost
- Booking tips: how far in advance, cancellation policies
- Do NOT re-mention tour names here

## Layover Tips for {city} Airport
- 3 practical tips for this specific airport
- If specific terminal info is unknown, give honest general advice (2-3 sentences per tip)
- Focus on: luggage storage, fast track, local currency, timing

STRICT WRITING RULES:
- Total 1,000-1,400 words
- Never mention any tour not listed in VERIFIED TOUR DATA
- No numbered lists anywhere in the article
- One natural CTA sentence near the end
- Final two lines: "Best value: [exact tour name] at $[price]" and "Best splurge: [exact tour name] at $[price]"
- BANNED WORDS (instant fail): vibrant, bustling, tapestry, soak in, unique blend,
  rich culture, hidden gem, must-visit, immerse, embark, world-class, bucket list,
  extraordinary, transform your layover, A Practical [noun], rich history, long history,
  unforgettable, stunning landscapes, perfect backdrop

Return ONLY markdown starting with # title"""

    result = ai_generate(
    "You are a seasoned frequent flyer who specializes in layover experiences. "
    "ABSOLUTE RULES: "
    "1) Only mention tours from TABLE TOURS in the article body. "
    "2) Never recommend a tour whose duration exceeds the layover window. "
    "3) 'Prices and Logistics' must NOT re-list tour names. "
    "4) Never output broken text like 'A Practical visit' or 'A Practical experience'. "
    "5) Never use placeholder text like {city} in the output. "
    "6) Airport tips must be specific to the named airport, not generic.",
    prompt,
    temperature=0.45,
    max_tokens=3500,
    )
    content = result["content"].strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else f"Layover Tours and Stopover Guide for {city}"
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()

    slug = topic.get("slug",
        re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-") + "-layover-tours")
    tags = [city, country, "Layover Tours"] if country else [city, "Layover Tours"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Layover tours and stopover guide for {city}: best tours by duration, prices, and airport tips.",
        "tags": [t for t in tags if t],
        "city": city, "country": country, "tours": tours,
        "table_tours": table_tours,
    }
