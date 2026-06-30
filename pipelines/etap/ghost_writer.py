"""ghost_writer.py - Ghost Tours And Dark History guide generator"""
import logging
import os
import re
import sqlite3

from pipelines.etap.quality_guard import preprocess_tours
from shared.ai_writer import generate as ai_generate

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

def fetch_tours(city, country=None):
    conn = _get_db()
    rows = conn.execute("""
        SELECT product_name, description, category, price, currency,
               discount_percent as discount, image_url, deep_link, city, country
        FROM viator_tours
        WHERE (city = ? OR city IN (SELECT alias FROM city_aliases WHERE canonical_name = ?))
          AND category IN (
              'Ghost Tours','Underground Tours','Archaeology Tours',
              'Historical Tours','Cultural Tours','Walking Tours',
              'Architecture Tours','Movie Tours'
          )
          AND deep_link IS NOT NULL AND deep_link != ''
        ORDER BY CAST(price AS REAL) ASC
    """, (city, city)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _categorize_tours(tours):
    """투어를 카테고리별로 분류. ghost/underground/historical 로 구분."""
    ghost     = [t for t in tours if t.get("category") == "Ghost Tours"]
    underground = [t for t in tours if t.get("category") == "Underground Tours"]
    historical  = [t for t in tours if t.get("category") in (
        "Historical Tours","Archaeology Tours","Cultural Tours",
        "Walking Tours","Architecture Tours","Movie Tours"
    )]
    return ghost, underground, historical

def _build_tour_block(tours, max_items=5):
    """GPT에 전달할 투어 목록 텍스트 블록 생성."""
    lines = []
    for t in tours[:max_items]:
        name = re.sub(r"^Save [\d.]+%!\s*", "", t["product_name"])
        price = round(_safe_price(t.get("price", 0)))
        disc = t.get("discount") or ""
        disc_str = f" | -{disc}% off" if disc and str(disc) not in ("0","","0.0") else ""
        lines.append(f"- {name} | ${price}{disc_str} | {t.get('category','')}")
    return "\n".join(lines)

def _build_summary(tours, city):
    if not tours:
        return None, None
    ghost, underground, historical = _categorize_tours(tours)
    discounted = [t for t in tours if t.get("discount") and
                  str(t["discount"]) not in ("0","","0.0")]
    budget  = [t for t in tours if 0 < _safe_price(t.get("price")) < 30]
    mid     = [t for t in tours if 30 <= _safe_price(t.get("price")) <= 100]
    premium = [t for t in tours if _safe_price(t.get("price")) > 100]

    # 테이블에 들어갈 투어: mid price 최대 5개 우선, 없으면 budget
    table_tours = (mid[:5] if len(mid) >= 2 else budget[:5]) or tours[:5]

    summary  = f"City: {city}\n"
    summary += f"Total tours available: {len(tours)}\n"
    summary += f"Ghost tours: {len(ghost)}, Underground tours: {len(underground)}, Historical tours: {len(historical)}\n\n"

    summary += "[TABLE TOURS — these EXACT tours go in the product table AND body text]\n"
    summary += _build_tour_block(table_tours, 5)
    summary += "\n\n"

    if budget:
        summary += "[BUDGET PICKS under $30]\n"
        summary += _build_tour_block(budget, 3)
        summary += "\n\n"
    if premium:
        summary += "[PREMIUM PICKS over $100]\n"
        summary += _build_tour_block(premium, 2)
        summary += "\n\n"
    if discounted:
        deals = sorted(discounted, key=lambda x: float(str(x.get("discount","0")) or 0), reverse=True)
        summary += "[DEALS — biggest discounts]\n"
        summary += _build_tour_block(deals, 3)
        summary += "\n"

    return summary, table_tours

def generate_ghost_guide(topic):
    city    = topic["city"]
    country = topic.get("country", "")
    tours   = fetch_tours(city, country)
    tours, _pre_issues, _excluded = preprocess_tours(tours, city=city)
    if not tours:
        logger.warning(f"[ghost_writer] No tours for {city}")
        return None

    summary, table_tours = _build_summary(tours, city)
    if not summary:
        return None

    ghost, underground, historical = _categorize_tours(tours)

    # 섹션 가용성 판단 — 데이터 없으면 섹션 제거
    has_underground = len(underground) >= 2
    has_ghost_tours = len(ghost) >= 2 or len(historical) >= 2

    # GPT에게 전달할 섹션 목록 (데이터 기반으로 조건부 생성)
    sections = ["## The Dark History of {city}"]
    if has_ghost_tours:
        sections.append("## Best Ghost Tours in {city}")
    if has_underground:
        sections.append("## Underground and Catacombs Tours")
    sections.append("## Prices and What to Expect")
    sections.append("## Tips for Ghost Tours in {city}")
    h2s = "\n".join(f"  {s}" for s in sections)

    # 테이블 투어 목록을 명시적으로 전달
    table_tour_names = [
        re.sub(r"^Save [\d.]+%!\s*", "", t["product_name"])
        for t in table_tours
    ]
    table_list_str = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(table_tour_names))

    prompt = f"""Write a ghost tours and dark history guide for {city}, {country}.

=== TOUR DATA (ONLY use these tours — do NOT invent any) ===
{summary}

=== TABLE TOURS (CRITICAL) ===
The pipeline will insert a product table with EXACTLY these tours:
{table_list_str}

Your article body MUST reference these same tours by their EXACT names.
Do NOT mention tours in the body that are not in the TABLE TOURS list above.
Do NOT describe tours that are in budget/premium/deals sections unless they are also in TABLE TOURS.

=== SECTIONS TO WRITE ===
{h2s}

SECTION RULES:
- "The Dark History of {{city}}": Open with ONE specific historical event, date, or documented tragedy.
  Write 2-3 paragraphs of actual history. No ghost stories here — only documented history.
- "Best Ghost Tours in {{city}}": Describe each TABLE TOUR by name and price.
  Explain what makes each tour distinct in 2-3 sentences. Do NOT repeat the same description.
{"- 'Underground and Catacombs Tours': Only write this section because underground tour data exists." if has_underground else ""}
- "Prices and What to Expect": Give a PRICE RANGE summary (cheapest to most expensive from TABLE TOURS).
  Do NOT list tour names again — that was already done in 'Best Ghost Tours'.
  Instead explain: how long tours run, what to wear, best time of day, booking tips.
- "Tips for Ghost Tours in {{city}}": 4-5 practical tips specific to THIS city's geography/climate/culture.
  Avoid generic tips like "bring a flashlight" unless relevant to this specific location.

WRITING RULES:
- 1,000-1,400 words total
- Write as a paranormal investigator who has personally visited {city}
- Open the article with a specific date, event, or documented haunting at a named location
- Never write "long history" — use specific time periods (e.g., "since the 16th century")
- Never repeat a tour name more than once across the entire article
- One CTA near the end, naturally placed
- End with: best value pick (name + price) and best splurge pick (name + price)
- BANNED: vibrant, bustling, hidden gem, treasure trove, must-visit, immerse yourself,
  embark, crystal-clear, world-class, bucket list, plethora, tapestry, myriad,
  long history, rich history, standout experience, a practical guide

Return ONLY markdown starting with # title"""

    result = ai_generate(
    "You are a paranormal investigator and historian who leads ghost tours. "
    "ABSOLUTE RULES: "
    "1) Only reference tours explicitly listed in TABLE TOURS. "
    "2) Never invent prices, names, or historical events. "
    "3) 'Prices and What to Expect' must NOT re-list tour names already in 'Best Ghost Tours'. "
    "4) Every section must open differently — no two sections start with the same word. "
    "5) Never use placeholder text like {city} or [city] in the output.",
    prompt,
    temperature=0.45,
    max_tokens=3500,
    )
    content = result["content"].strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else f"Ghost Tours and Dark History in {city}"
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()

    slug = topic.get("slug",
        re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-") + "-ghost-tours")
    tags = [city, country, "Ghost Tours"] if country else [city, "Ghost Tours"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Ghost tours and dark history in {city}: top picks, prices, and what to expect.",
        "tags": [t for t in tags if t],
        "city": city, "country": country, "tours": tours,
        "table_tours": table_tours,
    }
