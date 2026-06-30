"""ETAP writer — GPT로 영문 도시 가이드 생성."""
import sqlite3
from pathlib import Path

from shared.ai_writer import generate as ai_generate

DB_PATH = Path(__file__).parent.parent.parent / "data" / "travel-en.db"


def _get_internal_links(current_dest_id: int, region: str, blog_id: str = "", limit: int = 3) -> list[dict]:
    """같은 region의 발행 완료된 글 중 내부링크 후보 반환."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT DISTINCT d.city, d.country, t.slug, t.title
        FROM publish_log pl
        JOIN topics t ON pl.topic_id = t.topic_id
        JOIN destinations d ON t.dest_id = d.dest_id
        WHERE d.region = ? AND t.dest_id != ? AND pl.blog_id = ?
        ORDER BY pl.published_at DESC
        LIMIT ?
    """, (region, current_dest_id, blog_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def generate_city_guide(topic: dict) -> dict:
    """도시 가이드 글 생성. topic은 topic_manager.pick_topic() 반환값."""
    city = topic["city"]
    country = topic["country"]
    region = topic["region"]
    title = topic["title"]
    slug = topic["slug"]

    internal_links = _get_internal_links(topic["dest_id"], region, blog_id=topic.get("blog_id", ""))

    link_instruction = ""
    if internal_links:
        link_list = "\n".join(
            f'- [{r["city"]}, {r["country"]}](/posts/{r["slug"]}/)'
            for r in internal_links
        )
        link_instruction = f"""
## Internal Links (MUST include):
Naturally weave these links into your text where relevant (e.g., "If you're also considering a trip to [City](/posts/slug/), check out our guide."). Do NOT create a separate "Related Articles" section. Place them within existing paragraphs where they fit contextually.

Available links:
{link_list}
"""

    prompt = f"""Write a comprehensive travel guide with this exact title: "{title}"

The guide is about {city}, {country} and targets American travelers.

## Requirements:
- Length: 1,800~2,200 words
- Tone: friendly, practical, first-hand experience style
- Language: American English

## Structure (use these exact H2 headings):
## Why Visit {city}?
(2~3 paragraphs on what makes this destination special)

## Best Time to Visit {city}
(seasonal breakdown with specific months, weather, crowd levels, pricing trends)

## Where to Stay in {city}
(3~4 neighborhood recommendations with budget/mid-range/luxury tiers, do NOT mention specific hotel names)

## Top Things to Do in {city}
(8~10 activities/attractions woven into flowing paragraphs, NOT a numbered list. Bold the attraction names. Mix famous landmarks and lesser-known spots)

## Food and Dining Guide
(local cuisine highlights woven into paragraphs, 4~5 must-try dishes with bold names, street food vs restaurant recommendations. NOT a numbered list)

## Getting Around {city}
(public transit, taxis, walking, rental car advice)

## Budget Breakdown
(daily budget estimates for budget/mid-range/luxury travelers in USD, covering accommodation, food, transport, activities)

## Travel Tips for {city}
(5~7 practical tips written as prose paragraphs, NOT a numbered list. Bold the topic of each tip)
{link_instruction}
## Important Rules:
- Do NOT invent specific prices or statistics. Use ranges like "budget hotels typically start around $30-50/night"
- Do NOT mention specific hotel or airline brand names
- Do NOT include any external links (only internal links listed above are allowed)
- Do NOT invent any internal links. Use ONLY the exact links provided in the "Internal Links" section above. If no internal links are provided, do not add any.
- Write in pure markdown with H2 headers only (no H3)
- No meta-commentary like "In this guide..." or "Let's dive in"
- Start directly with the first H2 section
"""

    result = ai_generate(
        "You are an experienced travel writer who creates practical, SEO-friendly destination guides for American travelers. STRICT RULES: 1) NEVER use these words/phrases: plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, hidden gems, let's dive in, without further ado, crystal-clear, culinary delights, gastronomic, rich cultural heritage, soak in, immerse yourself, adrenaline junkie. 2) Do NOT use numbered lists for attractions or tips. Write in flowing paragraphs with bold names. 3) Every section must read as prose, not a listicle. 4) Open with a concrete sensory detail, not a generic statement.",
        prompt,
        temperature=0.6,
        max_tokens=4000,
    )
    content = result["content"].strip()

    description = f"Everything you need to know about visiting {city}, {country} — best time to go, where to stay, top things to do, food guide, and budget tips."

    return {
        "title": title,
        "slug": slug,
        "content": content,
        "description": description,
        "city": city,
        "country": country,
        "region": region,
        "tags": [city, country, region, "travel guide"],
    }
