"""tour_writer.py – 도시 종합 여행 가이드 생성 (tour-hugo 전용, 정체성: 종합 가이드 / 투어는 보조)

정체성 결정 기록: docs/superpowers/specs/2026-08-22-tour-hugo-identity.md
H2 제약: hugo_writer._ALLOWED_H2_PATTERNS에 매칭되는 제목만 사용 (비매칭 시 볼드 문단 강등됨)
"""
import contextlib
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

def fetch_tours(city, country=None):
    conn = _get_db()
    rows = conn.execute("""
        SELECT product_name, description, category, price, currency,
               discount_percent, image_url, deep_link, city, country
        FROM viator_tours
        WHERE city = ? AND deep_link IS NOT NULL AND deep_link != ''
        ORDER BY CAST(price AS REAL) ASC
    """, (city,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _build_tour_summary(tours, city):
    total = len(tours)
    if total == 0:
        return None
    categories = {}
    price_buckets = {"under_50": [], "50_200": [], "over_200": []}
    discounted = []
    for t in tours:
        cat = t.get("category") or "Other"
        categories[cat] = categories.get(cat, 0) + 1
        p = 0
        with contextlib.suppress(BaseException): p = float(t["price"])
        if p > 0 and p < 50: price_buckets["under_50"].append(t)
        elif p >= 50 and p <= 200: price_buckets["50_200"].append(t)
        elif p > 200: price_buckets["over_200"].append(t)
        disc = t.get("discount_percent") or ""
        if disc and disc != "0":
            discounted.append(t)
    # 각 버킷에서 대표 5개
    picks = {
        "budget": price_buckets["under_50"][:5],
        "mid": price_buckets["50_200"][:5],
        "premium": price_buckets["over_200"][:5],
        "deals": sorted(discounted, key=lambda x: x.get("discount_percent","0"), reverse=True)[:5],
    }
    top_cats = sorted(categories.items(), key=lambda x: -x[1])[:10]
    summary = f"City: {city}\nTotal tours: {total}\n"
    summary += f"Discounted tours: {len(discounted)}\n"
    summary += "Top categories: " + ", ".join(f"{c} ({n})" for c,n in top_cats) + "\n"
    summary += f"Price range: ${price_buckets['under_50'][0]['price'] if price_buckets['under_50'] else 'N/A'} ~ ${price_buckets['over_200'][-1]['price'] if price_buckets['over_200'] else 'N/A'}\n\n"
    for label, items in picks.items():
        if items:
            summary += f"[{label.upper()} PICKS]\n"
            for t in items:
                summary += f"- {t['product_name']} | ${t['price']} {t['currency']} | {t['category']}\n"
            summary += "\n"
    return summary

def generate_tour_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")
    tours = fetch_tours(city, country)
    # 도시 가이드 정체성: 투어 데이터는 보조. 없어도 글 생성 (기존 클론은 return None으로 고갈 처리했음)
    summary = _build_tour_summary(tours, city) if tours else None
    data_block = f"""
TOUR DATA (use ONLY this data for the tour recommendation section — do NOT invent tours or prices):
{summary}
""" if summary else """
NO TOUR DATA available for this city. OMIT the tour recommendation section entirely.
"""
    prompt = f"""Write a comprehensive city travel guide for {city}, {country}.
{data_block}
RULES:
- Write 1,200-1,800 words in English
- Do NOT include any booking links or URLs in the text
- Title must include "{city}" and be SEO-friendly, guide-style (e.g. "{city} Travel Guide: What to See, Eat & Do")
- Required H2 sections (use these EXACT heading styles):
  ## Sightseeing & Top Attractions in {city}
  ## The Food Scene in {city}
  ## Tips for Getting Around {city}
  ## Practical Tips for Travelers
- If tour data is provided above, add ONE supplementary section:
  ## Best Guided Tours in {city}   (mention only tours/prices that appear in the data; omit if empty)
- End with ONE closing section:
  ## Money-Saving Tips for Visitors to {city}
- Do NOT invent tour names, prices, or estimates. If a price is not in the data, do NOT mention it
- Write naturally in flowing paragraphs, not as a list dump

Return ONLY the article in markdown starting with # title"""

    system_prompt = """You are an experienced travel writer creating comprehensive city guides.
Write in an authoritative, informative tone — like a well-researched Lonely Planet article.

STRUCTURE:
- Start with what makes this city special (2-3 sentences, no clichés)
- Cover: key attractions, local food scene, transportation tips, practical advice
- Tours/activities are mentioned as ONE recommendation section (not the main focus)
- End with money-saving tips or best time to visit

STRICT RULES:
1) Never use: plethora, vibrant, bustling, let's dive in, hidden gem, tapestry, myriad, embark, unforgettable, crystal-clear, culinary delights, gastronomic, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled
2) NEVER bold an entire paragraph. Bold for short phrases only (max 10 words).
3) NEVER use blockquote (>) syntax.
4) NEVER capitalize articles mid-sentence.
5) Tours are supplementary — max 1 H2 section for tour recommendations.
6) Focus 70% on practical travel info, 30% on bookable experiences."""

    result = ai_generate(
    system_prompt,
    prompt,
    temperature=0.5,
    max_tokens=4000,
    )
    content = result["content"].strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"{city} Travel Guide: What to See, Eat & Do")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-"))
    tags = [city, country, "Travel Guide", "City Guide", "Things to Do"] if country else [city, "Travel Guide", "Things to Do"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Complete travel guide to {city}: top attractions, local food, getting around, and practical tips.",
        "tags": [t for t in tags if t], "city": city, "country": country,
        "tours": tours,  # 전체 투어 데이터 (pipeline에서 카드 생성용, 빈 리스트 허용)
    }
