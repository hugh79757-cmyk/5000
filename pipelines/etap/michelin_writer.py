"""michelin_writer.py – 미슐랭 레스토랑 가이드 생성"""
import logging
import os
import re
import sqlite3

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

def fetch_restaurants(city):
    conn = _get_db()
    rows = conn.execute("""
        SELECT name, address, cuisine, price, award, green_star,
               description, url, city, country
        FROM michelin_restaurants
        WHERE city = ?
        ORDER BY CASE award
            WHEN '3 Stars' THEN 1 WHEN '2 Stars' THEN 2
            WHEN '1 Star' THEN 3 WHEN 'Bib Gourmand' THEN 4
            ELSE 5 END
    """, (city,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _build_summary(restaurants, city):
    total = len(restaurants)
    if total == 0:
        return None
    awards = {}
    cuisines = {}
    green_stars = 0
    for r in restaurants:
        a = r.get("award") or "Selected"
        awards[a] = awards.get(a, 0) + 1
        c = r.get("cuisine") or "Not specified"
        cuisines[c] = cuisines.get(c, 0) + 1
        if r.get("green_star"):
            green_stars += 1
    top_cuisines = sorted(cuisines.items(), key=lambda x: -x[1])[:10]
    summary = f"City: {city}\nTotal Michelin restaurants: {total}\n"
    summary += "Awards: " + ", ".join(f"{k}: {v}" for k, v in sorted(awards.items())) + "\n"
    summary += f"Green Star restaurants: {green_stars}\n"
    summary += "Top cuisines: " + ", ".join(f"{c} ({n})" for c, n in top_cuisines) + "\n\n"
    summary += "RESTAURANT LIST:\n"
    for r in restaurants[:30]:
        price_str = PRICE_LABEL.get(r["price"], r["price"]) if r["price"] else "Price N/A"
        desc = (r["description"] or "")[:100]
        summary += f"- {r['name']} | {r['award']} | {r['cuisine']} | {price_str} | {desc}\n"
    return summary

def generate_michelin_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")
    restaurants = fetch_restaurants(city)
    if not restaurants:
        logger.warning(f"No restaurants for {city}")
        return None
    summary = _build_summary(restaurants, city)
    if not summary:
        return None
    prompt = f"""Write a Michelin restaurant guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent restaurants):
{summary}

RULES:
- Write 1,200-1,800 words in English
- Do NOT include any URLs or booking links
- Do NOT invent restaurant names, awards, or prices not in the data
- If price is "Price N/A", do not mention a price for that restaurant
- Title must include "{city}" and "Michelin"
- STRICT STRUCTURE — MANDATORY. Your article body MUST contain EXACTLY these four H2 headings, in this exact order, each as its own line starting with "## " (NOT numbered, NOT bulleted, NOT nested under anything):
  ## At a Glance
  ## Where to Eat
  ## Compare
  ## FAQ
  Content required under each:
  - "## At a Glance" — a compact summary TABLE with columns: Restaurant | Award | Cuisine | Price (3-7 rows from data, sorted by award). Answers "what's here" immediately.
  - "## Where to Eat" — detailed per-restaurant H3 sections (each 120-180 words: award, signature dish, price tier, why choose it). 3-6 restaurants.
  - "## Compare" — a comparison TABLE with columns: Restaurant | Award | Cuisine | Price | Best For (same restaurants as At a Glance, add "Best For" verdict column). Drives dwell time.
  - "## FAQ" — 3 questions with answers (e.g. "How far in advance should I book?", "Are there vegetarian options?", "What is the dress code?"). Target long-tail keywords.
- HARD CONSTRAINT: all four H2 headings above MUST appear verbatim as level-2 headings. If ANY is missing, the article is invalid — always emit all four.
- OPENING PARAGRAPH — MANDATORY: before "## At a Glance", write a 3-4 sentence intro paragraph about {city}'s Michelin dining scene (NO heading above it, NO table). The article body must start with this paragraph, never with a heading.
- description/meta: 1-2 sentence summary of {city}'s Michelin scene (20-30 words). NEVER a section name like "At a Glance".
- Internal links: at most 3 links per 500 words, and only to other {city} guides
  or same-site travel content. Do NOT exceed 6 total internal links.
- Mention each restaurant by exact name and award from data
- Write naturally as a guide, not a list dump

Return ONLY the article in markdown starting with # title"""

    result = ai_generate(
    "You are a food and travel writer. Use only the provided Michelin data. Never fabricate information. STRICT RULES: 1) NEVER use these words/phrases: plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, hidden gems, crystal-clear, culinary delights, gastronomic, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Write in flowing paragraphs, not numbered lists. 3) Format prices as whole numbers when .0.",
    prompt,
    temperature=0.5,
    max_tokens=4000,
    )
    content = result["content"].strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Michelin Restaurants in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", f"michelin-restaurants-{re.sub(r'[^a-z0-9]+', '-', city.lower()).strip('-')}")
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Complete guide to Michelin-starred restaurants in {city}: awards, cuisines, prices, and booking tips.",
        "tags": [city, country, "Michelin Restaurants", "Fine Dining", "Food Guide"],
        "city": city, "country": country, "restaurants": restaurants,
    }


# === TRACKC_SELF_IMPROVE deliverable: generate_michelin_post + validate_structure ===
# E5 HARD CONSTRAINT — must be embedded verbatim in the LLM prompt.
_FILLER_HARD_CONSTRAINT = "Do NOT write filler. Every sentence must carry specific Michelin data (restaurant name, award, cuisine, price, or verdict). No generic travel-brochure padding."
_MICHELIN_SYSTEM = (
    "You are a food and travel writer. Use only the provided Michelin data. "
    "Never fabricate information. STRICT RULES: 1) NEVER use these words/phrases: "
    "plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, "
    "hidden gems, crystal-clear, culinary delights, gastronomic, soak in, immerse yourself, "
    "treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, "
    "look no further, haven for, left me in awe, adventure awaits, palpable, escapades, "
    "playground for, adrenaline-fueled. 2) Write in flowing paragraphs, not numbered lists. "
    "3) Format prices as whole numbers when .0. 4) " + _FILLER_HARD_CONSTRAINT
)

# Module constants for the quarantine write path (mirror michelin_pipeline.py).
_BLOG_ID = "michelin-hugo"
_SITE_PATH = "/Users/twinssn/Projects/ETAP/michelin-hugo"
_CATEGORY = "Michelin Guide"

_REQUIRED_H2 = ["At a Glance", "Where to Eat", "Compare", "FAQ"]


def generate_michelin_post(topic) -> dict | None:
    """TRACKC_SELF_IMPROVE generator.

    Produces a Michelin destination/food guide satisfying E1~E5 (STRICT).
    Returns the article dict (same shape as generate_michelin_guide) or None
    on data/LLM failure.
    """
    city = topic["city"]
    country = topic.get("country", "")
    restaurants = fetch_restaurants(city)
    if not restaurants:
        logger.warning(f"[TRACKC] No restaurants for {city}")
        return None
    summary = _build_summary(restaurants, city)
    if not summary:
        return None
    prompt = f"""Write a Michelin destination food guide for {city}, {country}.

DATA (use ONLY this data, do NOT invent restaurants):
{summary}

RULES:
- Write 1,200-1,800 words in English (word count MUST be >= 706).
- Do NOT include any URLs or booking links.
- Do NOT invent restaurant names, awards, or prices not in the data.
- If price is "Price N/A", do not mention a price for that restaurant.
- Title must include "{city}" and "Michelin".
- {_FILLER_HARD_CONSTRAINT}
- STRICT STRUCTURE — MANDATORY. Your article body MUST contain EXACTLY these four
  H2 headings, in this exact order, each as its own line starting with "## "
  (NOT numbered, NOT bulleted, NOT nested). A numbered heading like
  "## 1. At a Glance" is INVALID:
  ## At a Glance
  ## Where to Eat
  ## Compare
  ## FAQ
  Content required under each:
  - "## At a Glance" — a compact summary TABLE.
  - "## Where to Eat" — detailed per-restaurant H3 sections (each 120-180 words).
  - "## Compare" — a COMPARISON TABLE emitted as HTML: <table>...</table> with
    column headers Restaurant | Award | Cuisine | Price | Best For and AT LEAST 14
    <tr> rows (header + >=13 data rows). This is a HARD minimum.
  - "## FAQ" — AT LEAST 3 question/answer pairs (use "### Q: ... / ### A: ..." blocks).
- OPENING PARAGRAPH — MANDATORY: before "## At a Glance", write a 3-4 sentence intro
  paragraph. The article body must start with this paragraph, never with a heading.
- description/meta: 1-2 sentence summary (20-30 words). NEVER a section name.
- Mention each restaurant by exact name and award from data.

Return ONLY the article in markdown starting with # title"""

    try:
        result = ai_generate(_MICHELIN_SYSTEM, prompt, temperature=0.5, max_tokens=4000)
    except Exception as e:
        logger.error(f"[TRACKC] generate_michelin_post LLM failed for {city}: {e}")
        return None
    content = (result.get("content") or "").strip()
    if not content:
        return None
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"Michelin Restaurants in {city}")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    slug = topic.get("slug", f"michelin-restaurants-{re.sub(r'[^a-z0-9]+', '-', city.lower()).strip('-')}")
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Complete guide to Michelin-starred restaurants in {city}: awards, cuisines, prices, and booking tips.",
        "tags": [city, country, "Michelin Restaurants", "Fine Dining", "Food Guide"],
        "city": city, "country": country, "restaurants": restaurants,
    }


def validate_structure(content: str) -> tuple[bool, list]:
    """TRACKC_SELF_IMPROVE E1~E5 STRICT validator.

    Returns (passed, issues). E5 is a prompt-embedded HARD CONSTRAINT (no code
    check) — it is recorded in the log rather than flagged as a failure.
    """
    issues = []
    if not content:
        return (False, ["E0: empty content"])

    # E1: literal H2 headings present, no numbering inside headings.
    h2s = re.findall(r"^##\s+(.+?)\s*$", content, re.M)
    for h in _REQUIRED_H2:
        hlabel = "## " + h
        found = False
        for x in h2s:
            xs = x.strip()
            if xs == h:
                found = True
                break
            if re.match(r"^\d+[\.\)]\s*" + re.escape(h) + r"$", xs):
                issues.append(f"E1: numbered heading '{xs}' (numbering inside heading forbidden)")
                found = True
                break
        if not found:
            issues.append(f"E1: missing H2 '{hlabel}'")

    # E2: a <table> in body with >= 14 <tr> rows.
    tables = re.findall(r"<table.*?</table>", content, re.S | re.I)
    max_rows = 0
    for tb in tables:
        rows = len(re.findall(r"<tr", tb, re.I))
        max_rows = max(max_rows, rows)
    if max_rows < 14:
        issues.append(f"E2: no <table> with >=14 rows (max={max_rows})")

    # E3: >= 3 FAQ Q/A pairs under "## FAQ".
    m = re.search(r"##\s+FAQ\s*(.*?)(?=^##\s+|\Z)", content, re.S | re.M)
    faq_block = m.group(1) if m else ""
    qa = len(re.findall(r"^\s*(#{3,4}\s+.+\?|\*\*[^*]+\?\*\*)", faq_block, re.M))
    if qa < 3:
        issues.append(f"E3: FAQ Q/A pairs <3 (found={qa})")

    # E4: word count >= 706.
    wc = len(content.split())
    if wc < 706:
        issues.append(f"E4: word count {wc} < 706")

    # E5: HARD CONSTRAINT embedded in prompt (no code check) — log only.
    logger.info("[TRACKC] E5: filler prohibition is a HARD CONSTRAINT embedded in the LLM "
                f"prompt (contains 'Do NOT write filler': {_FILLER_HARD_CONSTRAINT in _MICHELIN_SYSTEM})")

    blocking = [i for i in issues if i.startswith(("E1", "E2", "E3", "E4"))]
    return (len(blocking) == 0, issues)


def postprocess_and_write(article, blog_id=_BLOG_ID, site_path=_SITE_PATH,
                          category=_CATEGORY, is_draft=False):
    """Mirror cruise/airports postprocess + _write_hugo_post_etap(..., is_draft=...).

    On quality-draft detection the post is quarantined as a draft (NOT skipped),
    so the topic is still consumed and the post never goes live in a broken state.
    Returns (result, issues, is_draft).
    """
    from pipelines.etap.quality_guard import postprocess_content, send_alert
    from shared.publishers.hugo_writer import _write_hugo_post_etap as _write

    prices = []
    for r in article.get("restaurants", []):
        try:
            p = float(str(r.get("price", 0)).replace("$", "").replace(",", ""))
            if p > 0:
                prices.append(p)
        except Exception:
            pass
    content, issues, draft = postprocess_content(
        article["content"], data_prices=prices or None,
        blog_id=blog_id, slug=article["slug"])
    if draft:
        is_draft = True
        logger.warning("[%s] Quality DRAFT -> quarantine as draft: %s - %s",
                       blog_id, article["slug"], issues)
        send_alert(blog_id, article["slug"], issues)
    article = dict(article)
    article["content"] = content
    res = _write(article, None, None, blog_id, site_path, category, is_draft=is_draft)
    return res, issues, is_draft
