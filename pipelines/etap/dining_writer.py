"""dining_writer.py - Michelin dining guide generator (city-focused, practical angle)"""
import logging
import os
import re
import sqlite3
import unicodedata

from pipelines.etap.quality_guard import preprocess_restaurants
from shared.ai_writer import generate as ai_generate

PRICE_LABEL = {
    "$":    "Budget (under $30)",
    "$$":   "Moderate ($30-$70)",
    "$$$":  "Expensive ($70-$150)",
    "$$$$": "Very Expensive (over $150)",
    "€":    "Budget (under €30)",
    "€€":   "Moderate (€30-€70)",
    "€€€":  "Expensive (€70-€150)",
    "€€€€": "Very Expensive (over €150)",
    "¥":    "Budget (under ¥3,000)",
    "¥¥":   "Moderate (¥3,000-¥8,000)",
    "¥¥¥":  "Expensive (¥8,000-¥20,000)",
    "¥¥¥¥": "Very Expensive (over ¥20,000)",
    "£":    "Budget (under £30)",
    "££":   "Moderate (£30-£70)",
    "£££":  "Expensive (£70-£150)",
    "££££": "Very Expensive (over £150)",
}

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

# 국가명 표기 정규화: michelin_restaurants / dining_topics / city_aliases 간
# 형식 차이(USA vs United States vs US, UK vs United Kingdom, Türkiye vs
# Turkey)를 브리징한다. 표기만 다르고 동일 국가를 하나의 정규화 키로 맵핑.
COUNTRY_ALIASES = {
    "usa": "united states",
    "us": "united states",
    "united states": "united states",
    "uk": "united kingdom",
    "united kingdom": "united kingdom",
    "türkiye": "turkey",
    "turkey": "turkey",
}

# DB city_aliases로 커버되지 않는 실발행 토픽의 도시명 매핑(코드 레벨 폴백).
# key = (정규화할 alias, 정규화된 country) → canonical 도시명.
# value에 대한 매칭은 _resolve_city_alias에서 country 하드 게이트를 그대로
# 유지한다. 해당 국가에 michelin 데이터가 있음을 사전 검증한 경우만 등재.
# (예: Rīga→Riga 동국가 Latvia 확인, Los Angeles County→Los Angeles 동국가).
CITY_ALIAS_FALLBACK = {
    ("riga", "latvia"): "Riga",
    ("los angeles county", "united states"): "Los Angeles",
    ("merseyside", "united kingdom"): "Liverpool",
    ("nevsehir merkez", "turkey"): "Nevşehir",
}
_MICHELIN_RESTAURANT_SQL = """
    SELECT name, address, cuisine, price, award, green_star,
           description, url, city, country
    FROM michelin_restaurants
    WHERE city = ?
    ORDER BY CASE award
        WHEN '3 Stars' THEN 1 WHEN '2 Stars' THEN 2
        WHEN '1 Star' THEN 3 WHEN 'Bib Gourmand' THEN 4
        ELSE 5 END
"""


def _normalize_country(cntry):
    """국가명 표기 정규화 키 반환 (없으면 소문자 원본)."""
    c = (cntry or "").strip()
    return COUNTRY_ALIASES.get(c.lower(), c.lower())


def _resolve_city_alias(conn, city, country):
    """별칭(city) → 정식 도시명(canonical_name) 해석, country 하드 게이트.

    오매칭 방지를 위해 city_aliases.country가 주어진 topic country와
    (정규화 후) 일치할 때만 canonical_name을 반환한다. country 불일치(예:
    이탈리아 토픽의 'TP' → Taipei/Taiwan)는 거부되어 None을 돌려준다.
    """
    ref = _normalize_country(country)
    if not ref:
        return None
    rows = conn.execute(
        "SELECT canonical_name, country FROM city_aliases WHERE lower(alias) = lower(?)",
        (city,),
    ).fetchall()
    for r in rows:
        if r["country"] and _normalize_country(r["country"]) == ref:
            return r["canonical_name"]
    # DB 별칭 부재 시 코드 레벨 폴백(동일 국가 하드 게이트 유지). 소문자·공백
    # 축약 키로 매칭하고, 발음 구별 부호(예: Rīga→Riga)는 NFD 분해 후 제거해
    # 표기 변이에 강건하게 처리한다.
    def _fold(s):
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    key = (_fold(" ".join((city or "").strip().lower().split())), ref)
    return CITY_ALIAS_FALLBACK.get(key)


def fetch_restaurants(city, country=None, conn=None):
    """미쉐린 식당 조회.

    기본은 city 정확일치. city 단독으로 결과가 없고 country가 주어진 경우에만
    city_aliases 별칭 정규화를 통해 canonical 도시명으로 재조회하되, country
    일치를 하드 게이트로 유지해 타국가 오매칭을 방지한다.

    conn를 넘기면 caller가 소유한 연결로 조회하고 닫지 않는다 (테스트 주입용).
    """
    own_conn = conn is None
    db = conn if conn is not None else _get_db()
    try:
        rows = db.execute(_MICHELIN_RESTAURANT_SQL, (city,)).fetchall()
        if not rows and country:
            canonical = _resolve_city_alias(db, city, country)
            if canonical and canonical != city:
                rows = db.execute(_MICHELIN_RESTAURANT_SQL, (canonical,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            db.close()

def _build_summary(restaurants, city):
    total = len(restaurants)
    if total == 0:
        return None
    awards = {}
    cuisines = {}
    price_ranges = {}
    green_stars = 0
    for r in restaurants:
        a = r.get("award") or "Selected"
        awards[a] = awards.get(a, 0) + 1
        c = r.get("cuisine") or "Not specified"
        for cuisine in c.split(","):
            cuisine = cuisine.strip()
            if cuisine:
                cuisines[cuisine] = cuisines.get(cuisine, 0) + 1
        p = r.get("price") or "N/A"
        price_ranges[p] = price_ranges.get(p, 0) + 1
        if r.get("green_star"):
            green_stars += 1

    top_cuisines = sorted(cuisines.items(), key=lambda x: -x[1])[:10]
    summary = f"City: {city}\nTotal Michelin restaurants: {total}\n"
    summary += "Awards: " + ", ".join(f"{k}: {v}" for k, v in sorted(awards.items())) + "\n"
    summary += "Price ranges: " + ", ".join(f"{k}: {v}" for k, v in sorted(price_ranges.items())) + "\n"
    summary += f"Green Star (sustainability): {green_stars}\n"
    summary += "Top cuisines: " + ", ".join(f"{c} ({n})" for c, n in top_cuisines) + "\n\n"

    for tier in ["3 Stars", "2 Stars", "1 Star", "Bib Gourmand"]:
        tier_list = [r for r in restaurants if r.get("award") == tier]
        if tier_list:
            summary += f"[{tier.upper()}]\n"
            for r in tier_list[:8]:
                price_str = PRICE_LABEL.get(r["price"], r["price"]) if r["price"] else "Price N/A"
                desc = (r["description"] or "")[:120]
                summary += f"- {r['name']} | {r['cuisine']} | {price_str} | {desc}\n"
            summary += "\n"

    selected = [r for r in restaurants if r.get("award") not in ("3 Stars", "2 Stars", "1 Star", "Bib Gourmand")]
    if selected:
        summary += "[MICHELIN SELECTED]\n"
        for r in selected[:5]:
            price_str = PRICE_LABEL.get(r["price"], r["price"]) if r["price"] else "Price N/A"
            summary += f"- {r['name']} | {r['cuisine']} | {price_str}\n"
        summary += "\n"

    return summary

def generate_dining_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")
    restaurants = fetch_restaurants(city, country)
    restaurants, _pre_issues, _excluded = preprocess_restaurants(restaurants, city=city)
    if not restaurants:
        logger.warning(f"No restaurants for {city}")
        return None
    summary = _build_summary(restaurants, city)
    if not summary:
        return None

    has_3star = any(r.get("award") == "3 Stars" for r in restaurants)
    has_2star = any(r.get("award") == "2 Stars" for r in restaurants)
    has_1star = any(r.get("award") == "1 Star" for r in restaurants)
    has_bib = any(r.get("award") == "Bib Gourmand" for r in restaurants)
    has_green = any(r.get("green_star") for r in restaurants)

    sections = f"  ## The Dining Scene in {city}\n"
    if has_3star or has_2star:
        sections += "  ## Fine Dining at Its Best: Multi-Star Restaurants\n"
    if has_1star:
        sections += "  ## One-Star Restaurants Worth a Detour\n"
    if has_bib:
        sections += "  ## Bib Gourmand: Great Food Without the Splurge\n"
    if has_green:
        sections += f"  ## Green Star: Sustainable Dining in {city}\n"
    sections += f"  ## Cuisine Styles and What {city} Does Best\n"
    sections += "  ## Price Guide: What to Budget for Michelin Dining\n"
    sections += "  ## Booking Tips and What to Know Before You Go\n"

    prompt = f"""Write a practical Michelin dining guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent restaurants or prices):
{summary}

RULES:
- Write 1,200-1,800 words in English
- Do NOT include any URLs or booking links in the text
- Do NOT invent restaurant names, awards, cuisines, or prices not in the data
- If price is "Price N/A", do not mention a price for that restaurant
- Title must include "{city}" and relate to dining/eating
- Required H2 sections (OMIT that H2 section entirely if no data exists. Do NOT write filler content):
{sections}
- Mention restaurants by exact name and award from the data
- For each tier, highlight 2-3 standout picks and explain WHY they stand out (based on cuisine style or description)
- Include practical info: dress code expectations, reservation lead time, lunch vs dinner pricing
- Write as a food-loving traveler sharing personal dining strategy, not as a directory listing
- End with a "where to eat tonight" quick recommendation for different budgets

Return ONLY the article in markdown starting with # title"""

    result = ai_generate(
    "You are a food and travel blogger who dines at Michelin restaurants worldwide. Write in first-person-informed tone. STRICT RULES: 1) Never use: plethora, vibrant, bustling, let\\'s dive in, without further ado, hidden gem, tapestry, myriad, embark, culinary journey, gastronomic, crystal-clear, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Never invent data. 3) Every section must include one practical tip (reservation lead time, dress code reality, lunch vs dinner value, which tasting menu to pick). 4) Open with a specific dish, restaurant detail, or dining scene.",
    prompt,
    temperature=0.5,
    max_tokens=4000,
    )
    content = result["content"].strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Where to Eat in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", f"michelin-dining-{re.sub(r'[^a-z0-9]+', '-', city.lower()).strip('-')}")
    tags = [city, country, "Michelin Restaurants", "Dining Guide", "Food Travel"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Where to eat in {city}: Michelin-starred restaurants, Bib Gourmand picks, price guide, and booking tips.",
        "tags": [t for t in tags if t], "city": city, "country": country,
        "restaurants": restaurants,
    }
