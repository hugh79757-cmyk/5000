"""visa_writer.py – 비자 가이드 생성 (여권 기준 + 도착국 기준)"""
import os, sqlite3, logging, re
from openai import OpenAI

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
_client = None

try:
    from pipelines.etap.post_processor import fix_encoding, clean_tags, clean_prompt_leaks
    HAS_PP = True
except ImportError:
    HAS_PP = False

def _get_client():
    global _client
    if not _client:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _fetch_by_passport(passport):
    """여권 기준: 이 여권으로 갈 수 있는 나라들"""
    conn = _get_db()
    rows = conn.execute("""
        SELECT destination, requirement FROM visa_requirements
        WHERE passport = ? AND destination != ? ORDER BY requirement, destination
    """, (passport, passport)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _fetch_by_destination(destination):
    """도착국 기준: 이 나라에 오는 각국 여권의 비자 요건"""
    conn = _get_db()
    rows = conn.execute("""
        SELECT passport, requirement FROM visa_requirements
        WHERE destination = ? AND passport != ? ORDER BY requirement, passport
    """, (destination, destination)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _categorize(rows, key="destination"):
    cats = {}
    for r in rows:
        req = r["requirement"]
        cats.setdefault(req, []).append(r[key])
    return cats

def _build_passport_summary(passport, rows):
    cats = _categorize(rows, "destination")
    total = len(rows)
    visa_free_count = sum(len(v) for k, v in cats.items() if "visa free" in k.lower())
    voa_count = len(cats.get("visa on arrival", []))
    evisa_count = len(cats.get("e-visa", []))
    summary = f"Passport: {passport}\nTotal destinations: {total}\n"
    summary += f"Visa-free access: {visa_free_count} countries\n"
    summary += f"Visa on arrival: {voa_count} countries\n"
    summary += f"e-Visa: {evisa_count} countries\n\n"
    for req in sorted(cats.keys()):
        countries = cats[req]
        summary += f"[{req}] ({len(countries)} countries)\n"
        summary += ", ".join(sorted(countries)) + "\n\n"
    return summary

def _build_destination_summary(destination, rows):
    cats = _categorize(rows, "passport")
    total = len(rows)
    summary = f"Destination: {destination}\nTotal nationalities: {total}\n\n"
    for req in sorted(cats.keys()):
        passports = cats[req]
        summary += f"[{req}] ({len(passports)} nationalities)\n"
        summary += ", ".join(sorted(passports)) + "\n\n"
    return summary

def generate_visa_guide(topic):
    passport = topic["passport"]
    slug = topic["slug"]
    is_destination = slug.startswith("visa-policy-")
    if is_destination:
        rows = _fetch_by_destination(passport)
        if not rows:
            logger.warning(f"No visa data for destination {passport}")
            return None
        summary = _build_destination_summary(passport, rows)
        prompt = f"""Write a visa policy guide for {passport} (as a destination country).

DATA (use ONLY this data, include ALL countries in each category):
{summary}

RULES:
- Write 1,200-1,800 words in English
- Title must include "{passport}" and "visa"
- This is about who needs a visa to ENTER {passport}
- If a section has 0 relevant data, OMIT that H2 section entirely. Do NOT write filler content.
- Required H2 sections:
  ## {passport} Visa Policy Overview
  ## Visa-Free and Visa-on-Arrival Access
  ## e-Visa and ETA Options
  ## Countries That Require a Visa
  ## Entry Requirements and Practical Tips
- List ALL countries in each category (this is reference content, completeness matters)
- Group visa-free countries by duration (90 days, 30 days, etc.)
- Do NOT invent visa rules not in the data
- Do NOT include URLs or links
- Write factually, no fluff

Return ONLY the article in markdown starting with # title"""
    else:
        rows = _fetch_by_passport(passport)
        if not rows:
            logger.warning(f"No visa data for passport {passport}")
            return None
        summary = _build_passport_summary(passport, rows)
        prompt = f"""Write a visa requirements guide for {passport} passport holders.

DATA (use ONLY this data, include ALL countries in each category):
{summary}

RULES:
- Write 1,200-1,800 words in English
- Title must include "{passport}" and "passport" or "visa"
- This is about where {passport} passport holders can travel
- Required H2 sections:
  ## {passport} Passport: Travel Freedom Overview
  ## Visa-Free Destinations
  ## Visa on Arrival Countries
  ## e-Visa and ETA Destinations
  ## Countries Requiring a Traditional Visa
  ## Tips for {passport} Passport Holders
- List ALL countries in each category (completeness is critical)
- Group visa-free countries by duration (90 days, 30 days, etc.)
- Do NOT invent visa rules not in the data
- Do NOT include URLs or links

Return ONLY the article in markdown starting with # title"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini", temperature=0.3, max_tokens=4500,
        messages=[{"role":"system","content":"You are a visa and immigration content writer. Use ONLY the provided data. Never guess or fabricate visa requirements. STRICT RULES: 1) NEVER use these words/phrases: plethora, vibrant, bustling, tapestry, myriad, embark, unforgettable, hidden gem, hidden gems, crystal-clear, culinary delights, gastronomic, soak in, immerse yourself, treasure trove, of a lifetime, must-visit, paradise for, world-class, bucket list, look no further, haven for, left me in awe, adventure awaits, palpable, escapades, playground for, adrenaline-fueled. 2) Write in flowing paragraphs, not numbered lists. 3) Format prices as whole numbers when .0."},
                  {"role":"user","content": prompt}]
    )
    content = resp.choices[0].message.content.strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else topic.get("title", f"{passport} Visa Guide")
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    tags = [passport, "Visa Requirements", "Passport", "Travel Documents", "Visa Free"]
    return {
        "title": title, "slug": slug, "content": content,
        "description": f"Complete visa requirements guide for {passport}: visa-free countries, visa on arrival, e-visa, and more.",
        "tags": tags, "country": passport, "is_destination": is_destination,
    }
