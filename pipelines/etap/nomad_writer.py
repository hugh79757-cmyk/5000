"""nomad_writer.py - Digital Nomad Guide And Coworking guide generator"""
import logging
import os
import re
import sqlite3
from urllib.parse import quote_plus

from shared.ai_writer import generate as ai_generate

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
# Exchange rates to USD (as of 2026-04)
# Update quarterly or move to a DB table / API when rates drift significantly
_FX_TO_USD = {
    "USD": 1.0,
    "EUR": 1.10,
    "THB": 0.029,
    "IDR": 0.00006,
    "CZK": 0.044,
    "HUF": 0.00274,
    "GEL": 0.366,
    "GBP": 1.27,
    "JPY": 0.0066,
    "KRW": 0.00075,
    "AUD": 0.66,
    "CAD": 0.73,
}

def _to_usd(amount, currency):
    """Convert a local-currency amount to USD. Returns None if currency unknown."""
    if amount is None:
        return None
    rate = _FX_TO_USD.get((currency or "").upper())
    if rate is None:
        return None
    return amount * rate

def _fmt_money(amount, currency):
    """Render an amount as 'LOCAL CUR (~$USD)' with both sides pre-computed."""
    if amount is None or amount == 0:
        return None
    cur = (currency or "").upper()
    local_str = f"{amount:,.0f} {cur}"
    usd = _to_usd(amount, cur)
    if usd is None or cur == "USD":
        return local_str
    # Choose USD precision based on magnitude
    if usd >= 100:
        usd_str = f"~${usd:,.0f}"
    elif usd >= 10:
        usd_str = f"~${usd:,.1f}"
    else:
        usd_str = f"~${usd:,.2f}"
    return f"{local_str} ({usd_str})"

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _safe_price(val):
    try:
        return float(str(val).replace("$","").replace(",","").strip())
    except:
        return 0

def _maps_url(name, address="", city="", country="") -> str:
    """Build a Google Maps search URL from name + address + city + country."""
    parts = [name, address, city, country]
    query = " ".join(p for p in parts if p).strip()
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"

def _maps_button(name, address="", hours="", website="", city="", country="") -> str:
    """Render a Google Maps markdown link for a coworking space."""
    url = _maps_url(name, address, city, country)
    parts = []
    if address:
        parts.append(address)
    if hours:
        parts.append(hours)
    meta = " · ".join(parts)
    link = f"[📍 View on Google Maps]({url})"
    if website and website.startswith("http"):
        link += f" · [🌐 Website]({website})"
    if meta:
        return f" {link} _{meta}_"
    return f" {link}"


def _clean_gpt_map_tags(content):
    """GPT/이전 실행이 생성한 Google Maps 링크를 모두 제거한다.
    _inject_map_buttons()가 새로 정확한 링크를 삽입하므로 기존 것은 전부 제거.
    제거 대상:
      1) 마크다운: [📍 View on Google Maps](...) 이모지 유무 무관
      2) 일반 텍스트 줄: 📍 View on Google Maps (링크 없이 텍스트만)
      3) HTML broken: <a href=...>📍 View on Google Maps</a>
      4) [View on Google Maps](...) 이모지 없는 버전
    """
    cleaned = content

    # 1) 마크다운 링크 — 이모지 유무 무관, website/메타 후속 제거
    patterns = [
        # [📍 View on Google Maps](url) + 선택적 website 링크 — 문장 중간 포함
        r"\s*\[[^\]]*?(?:📍|View on Google Maps)[^\]]*?\]\([^\)]*\)(?:\s*·\s*\[[^\]]*?(?:🌐|Website)[^\]]*?\]\([^\)]*\))?(?:\s*_[^_]*_)?",
        # 연속 두 번째 맵 링크 (공백으로 이어진 경우)
        r"(?<=\))\s*\[[^\]]*?(?:📍|View on Google Maps)[^\]]*?\]\([^\)]*\)",
        # 텍스트만 있는 경우: 📍 View on Google Maps
        r"\s*📍\s*View on Google Maps[^\n]*",
        # HTML 링크
        r'<a\s+href="[^"]*google\.com/maps[^"]*"[^>]*>[^<]*(?:📍|View on Google Maps)[^<]*</a>',
        # broken HTML
        r'<a\s+href="\s*(?!https?://)[^"]*"[^>]*>\s*[^<]*(?:📍)?\s*View on Google Maps\s*[^<]*</a>',
    ]

    total_removed = 0
    for pat in patterns:
        compiled = re.compile(pat, re.IGNORECASE | re.DOTALL)
        cleaned, n = compiled.subn("", cleaned)
        total_removed += n

    if total_removed:
        logger.info(f"[nomad_writer] Removed {total_removed} map link(s) total")

    return cleaned

def _inject_map_buttons(content, coworking, city="", country=""):
    """Find coworking space names in article body and inject a Maps link.
    - front matter(---) 영역은 건너뜀
    - 본문(body)에서만 매칭
    - 장소명이 본문에 명시적으로 언급된 경우만 삽입 (부분매칭은 **bold** 또는 문장 내 단독 등장만)
    """
    if not coworking:
        return content

    # ── front matter 분리 ──────────────────────────────────────
    fm_end = 0
    if content.startswith("---"):
        second = content.find("---", 3)
        if second != -1:
            fm_end = second + 3  # front matter 끝 위치

    front_matter = content[:fm_end]
    body = content[fm_end:]

    # Build lookup: canonical name -> data
    lookup = {}
    for c in coworking:
        name = (c.get("name") or "").strip()
        if not name or len(name) < 3:
            continue
        if name not in lookup or (c.get("address") and not lookup[name].get("address")):
            lookup[name] = c

    # Sort names by length DESC so longer names match first
    sorted_names = sorted(lookup.keys(), key=len, reverse=True)
    used = set()

    def _find_match_in_body(name, body_text):
        """본문에서만 매칭. 정확한 단어 경계 매칭 우선."""
        # 1) 정확한 이름 매칭 (대소문자 무시)
        m = re.search(re.escape(name), body_text, re.IGNORECASE)
        if m:
            return m, name
        # 2) **bold** 형태로 부분 단어 매칭 (>=5자 단어만)
        words = [w for w in re.split(r"[\s/,.-]+", name) if len(w) >= 5]
        for word in sorted(words, key=len, reverse=True):
            # bold 형태(**word**) 또는 문장 시작/끝 단어 경계
            m = re.search(
                r"(?:\*\*[^*]*" + re.escape(word) + r"[^*]*\*\*)",
                body_text, re.IGNORECASE
            )
            if m:
                return m, name
        return None, None

    result_body = body
    any_matched = False
    for name in sorted_names:
        if name in used:
            continue
        info = lookup[name]
        match, _matched_name = _find_match_in_body(name, result_body)
        if not match:
            continue

        start = match.end()

        # 문장 끝(. ! ?) 다음에 삽입
        sentence_end = re.search(r"[.!?](?=\s|\n|$)", result_body[start:])
        if sentence_end:
            insert_pos = start + sentence_end.end()
        else:
            para_end = re.search(r"\n\n", result_body[start:])
            insert_pos = start + para_end.start() if para_end else len(result_body)

        card = _maps_button(
            name,
            info.get("address", ""),
            info.get("opening_hours", ""),
            info.get("website", ""),
            city=city,
            country=country,
        )
        result_body = result_body[:insert_pos] + card + result_body[insert_pos:]
        used.add(name)
        any_matched = True
        logger.debug(f"[nomad_writer] Injected map link: {name} @ pos {insert_pos}")

    # ── 폴백: DB 장소명이 본문에 전혀 없으면 코워킹 섹션 리스트 아이템 끝에 분산 삽입 ──
    if not any_matched and lookup:
        db_names = list(lookup.keys())
        # 코워킹 섹션 범위 찾기
        cowork_start = re.search(
            r"## Best Coworking[^\n]*\n",
            result_body, re.IGNORECASE
        )
        cowork_end = re.search(
            r"\n## ",
            result_body[cowork_start.end():] if cowork_start else result_body
        )
        if cowork_start:
            sec_start = cowork_start.end()
            sec_end = (sec_start + cowork_end.start()) if cowork_end else len(result_body)
            section = result_body[sec_start:sec_end]

            # 리스트 아이템(- 또는 숫자.) 끝 문장들 찾기
            sentence_ends = [(m.end(), m) for m in re.finditer(
                r"(?:^[\-\*]|^\d+\.)[^\n]+[.!?]", section, re.MULTILINE
            )]

            if not sentence_ends:
                # 리스트 없으면 단락 끝 문장들
                sentence_ends = [(m.end(), m) for m in re.finditer(
                    r"[^\n][.!?](?=\s|\n|$)", section
                )]

            # DB 상위 N개를 분산 삽입 (최대 sentence_ends 수만큼)
            insert_count = min(len(db_names), len(sentence_ends), 5)
            # 뒤에서부터 삽입해야 offset 안 밀림
            inserts = []
            for i in range(insert_count):
                name = db_names[i]
                info = lookup[name]
                pos = sec_start + sentence_ends[i][0]
                link = _maps_button(
                    name,
                    info.get("address", ""),
                    info.get("opening_hours", ""),
                    info.get("website", ""),
                    city=city,
                    country=country,
                )
                inserts.append((pos, link))

            # 뒤에서부터 삽입 (position 역순)
            for pos, link in sorted(inserts, key=lambda x: x[0], reverse=True):
                result_body = result_body[:pos] + link + result_body[pos:]

            logger.info(f"[nomad_writer] Fallback map injection for {city}: {db_names[:insert_count]}")

    return front_matter + result_body


def _clean_hours(hours):
    """Trim verbose holiday exclusions from OSM opening_hours."""
    if not hours:
        return ""
    # Keep only the first weekly-pattern segment (before holiday noise like "Jan 01 off")
    parts = hours.split(";")
    clean = [p.strip() for p in parts if p.strip()
             and not any(m in p for m in ["Jan ","Feb ","Mar ","Apr ","May ","Jun ",
                                           "Jul ","Aug ","Sep ","Oct ","Nov ","Dec "])]
    result = "; ".join(clean[:2])
    return result or hours[:60]

def _address_in_city(address, city):
    """Check if address string mentions the target city (OSM boundary sanity check)."""
    if not address:
        return True  # no address: keep it (don't have reason to filter)
    return city.lower() in address.lower()

def fetch_data(city, country=None):
    conn = _get_db()
    # eSIM: match country preferred
    esim_term = (country or city).lower()
    esim = conn.execute("""
        SELECT title, description, link FROM airalo_esim
        WHERE LOWER(description) LIKE ? OR LOWER(title) LIKE ?
        LIMIT 5
    """, (f"%{esim_term}%", f"%{esim_term}%")).fetchall()

    # Visa: nationality-specific lookup for main nomad-source countries
    # Schema: (passport, destination, requirement)
    MAIN_PASSPORTS = [
        "United States", "Canada", "United Kingdom", "Australia",
        "New Zealand", "Germany", "France", "Netherlands",
        "Ireland", "Japan", "South Korea", "Singapore"
    ]
    visa_rows = []
    if country:
        placeholders = ",".join("?" * len(MAIN_PASSPORTS))
        q = f"""
            SELECT passport, destination, requirement
            FROM visa_requirements
            WHERE LOWER(destination) = ? AND passport IN ({placeholders})
            ORDER BY passport
        """
        visa_rows = conn.execute(
            q, [country.lower(), *MAIN_PASSPORTS]
        ).fetchall()

    coworking_raw = conn.execute("""
        SELECT name, address, website, opening_hours, internet_access, fee
        FROM coworking_spaces
        WHERE LOWER(city) LIKE ? LIMIT 20
    """, (f"%{city.lower()}%",)).fetchall()
    # Filter: must have a name AND address should mention the city (or have no address)
    coworking = []
    for r in coworking_raw:
        d = dict(r)
        if not d.get("name") or not d["name"].strip():
            continue
        if d.get("address") and not _address_in_city(d["address"], city):
            continue
        d["opening_hours"] = _clean_hours(d.get("opening_hours"))
        coworking.append(d)
        if len(coworking) >= 10:
            break

    climate = conn.execute("""
        SELECT month, avg_temp, min_temp, max_temp, precipitation_mm,
               rain_days, humidity_pct
        FROM nomad_climate
        WHERE LOWER(city) LIKE ? ORDER BY month
    """, (f"%{city.lower()}%",)).fetchall()

    cafes_raw = conn.execute("""
        SELECT name, address, website, opening_hours, internet_access, cuisine
        FROM nomad_cafes
        WHERE LOWER(city) LIKE ? AND name IS NOT NULL AND name != ''
        LIMIT 20
    """, (f"%{city.lower()}%",)).fetchall()
    cafes = []
    for r in cafes_raw:
        d = dict(r)
        if d.get("address") and not _address_in_city(d["address"], city):
            continue
        d["opening_hours"] = _clean_hours(d.get("opening_hours"))
        cafes.append(d)
        if len(cafes) >= 10:
            break

    cost = conn.execute("""
        SELECT * FROM nomad_cost_of_living
        WHERE LOWER(city) LIKE ? LIMIT 1
    """, (f"%{city.lower()}%",)).fetchone()
    conn.close()
    return {
        "esim": [dict(r) for r in esim],
        "visa": [dict(r) for r in visa_rows],
        "coworking": coworking,
        "climate": [dict(r) for r in climate],
        "cafes": cafes,
        "cost": dict(cost) if cost else {},
    }

def _build_summary(data, city, country):
    MONTH_NAMES = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                   7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    summary = f"City: {city}, Country: {country}\n"

    coworking = data.get("coworking", [])
    if coworking:
        summary += f"\n[COWORKING SPACES - {len(coworking)} found]\n"
        for c in coworking:
            line = f"- {c.get('name','Unknown')}"
            if c.get("address"): line += f" | Address: {c['address']}"
            if c.get("website"): line += f" | Web: {c['website']}"
            if c.get("opening_hours"): line += f" | Hours: {c['opening_hours']}"
            if c.get("fee"): line += f" | Fee: {c['fee']}"
            summary += line + "\n"

    climate = data.get("climate", [])
    if climate:
        summary += "\n[MONTHLY CLIMATE]\n"
        for m in climate:
            mn = MONTH_NAMES.get(m["month"], str(m["month"]))
            summary += (f"- {mn}: avg {m['avg_temp']}C (min {m['min_temp']}C / max {m['max_temp']}C), "
                        f"rain {m['precipitation_mm']}mm over {m['rain_days']} days, "
                        f"humidity {m['humidity_pct']}%\n")

    cafes = data.get("cafes", [])
    if cafes:
        wifi_cafes = [c for c in cafes if c.get("internet_access") in ("wlan", "yes", "wifi")]
        summary += f"\n[WIFI CAFES - {len(wifi_cafes)} with confirmed wifi out of {len(cafes)} total]\n"
        for c in wifi_cafes[:8]:
            line = f"- {c.get('name','Unknown')}"
            if c.get("address"): line += f" | {c['address']}"
            if c.get("opening_hours"): line += f" | Hours: {c['opening_hours']}"
            if c.get("cuisine"): line += f" | Cuisine: {c['cuisine']}"
            summary += line + "\n"

    cost = data.get("cost", {})
    if cost:
        cur = cost.get("currency", "USD")
        summary += "\n[COST OF LIVING - use these EXACT strings, do not recalculate]\n"
        fields = [
            ("meal_inexpensive", "Cheap meal"),
            ("meal_mid_range", "Mid-range meal (2 people)"),
            ("cappuccino", "Cappuccino"),
            ("beer_domestic", "Domestic beer"),
            ("monthly_pass", "Monthly transit pass"),
            ("internet_monthly", "Internet (monthly)"),
            ("fitness_monthly", "Gym (monthly)"),
            ("rent_1br_center", "1BR apt center"),
            ("rent_1br_outside", "1BR apt outside center"),
            ("utilities_monthly", "Utilities (monthly)"),
        ]
        for key, label in fields:
            val = cost.get(key)
            fmt = _fmt_money(val, cur)
            if fmt: summary += f"- {label}: {fmt}\n"

    esim = data.get("esim", [])
    if esim:
        # Compress: only list product names (titles). Description is boilerplate.
        summary += f"\n[eSIM OPTIONS - {len(esim)} Airalo plans available]\n"
        for e in esim:
            summary += f"- {e['title']}\n"

    visa = data.get("visa", [])
    if visa:
        summary += f"\n[VISA REQUIREMENTS for {country or 'destination'} by passport]\n"
        # Group by requirement for cleaner output
        by_req = {}
        for v in visa:
            req = v.get("requirement", "unknown")
            by_req.setdefault(req, []).append(v.get("passport", "?"))
        for req, passports in sorted(by_req.items()):
            summary += f"- {req}: {', '.join(passports)}\n"

    return summary


# Banned style words that gpt-4o-mini keeps slipping in despite system prompt
_BANNED_PHRASES = [
    "vibrant", "bustling", "hidden gem", "treasure trove", "must-visit",
    "immerse yourself", "embark", "crystal-clear", "world-class", "bucket list",
    "plethora", "tapestry", "myriad",
    "making it an attractive", "making it an ideal", "making it appealing",
    "rich culture", "like-minded individuals", "unique blend", "no wonder",
]

# Template/hallucination leak patterns
_SUSPICIOUS_PATTERNS = [
    r"\{city\}", r"\{country\}", r"\[city\]", r"\[country\]",
    r"\bN/A\b", r"\bTBD\b", r"\[price\]", r"\[cost\]",
    r"unknown cost", r"not available", r"data not found",
    r"\$\s*0\b", r"\b0\s*EUR\b", r"\b0\s*USD\b",
    r"(?i)upcoming\s+(digital\s+nomad\s+)?visa",
    r"(?i)set\s+to\s+launch",
    r"(?i)will\s+soon\s+introduce",
]

def _validate_content(content, data, city):
    """Run quality checks on generated content. Logs warnings; does NOT regenerate."""
    warnings = []

    # 1) Banned phrases
    content_lower = content.lower()
    hits = [p for p in _BANNED_PHRASES if p.lower() in content_lower]
    if hits:
        warnings.append(f"BANNED_PHRASES: {hits}")

    # 2) Suspicious leak patterns
    pattern_hits = []
    for pat in _SUSPICIOUS_PATTERNS:
        m = re.search(pat, content)
        if m:
            pattern_hits.append(f"'{m.group(0)}'")
    if pattern_hits:
        warnings.append(f"SUSPICIOUS: {pattern_hits}")

    # 3) Data unused (if cost data exists but no local currency in content)
    cost = data.get("cost", {})
    if cost and cost.get("currency"):
        cur = cost["currency"].upper()
        if cur != "USD" and cur not in content:
            warnings.append(f"UNUSED_COST: currency {cur} not mentioned in article")

    # 4) Coworking data provided but barely referenced
    coworking = data.get("coworking", [])
    if coworking:
        valid_names = [c["name"] for c in coworking
                       if c.get("name") and len(c["name"]) >= 3]
        mentioned = sum(1 for n in valid_names if n in content)
        if len(valid_names) >= 4 and mentioned < 3:
            warnings.append(f"LOW_COWORKING_USAGE: {mentioned}/{len(valid_names)} names mentioned")

    # 5) Length sanity
    word_count = len(content.split())
    if word_count < 800:
        warnings.append(f"SHORT_CONTENT: {word_count} words")

    # Log all warnings at once
    if warnings:
        logger.warning(f"[nomad_writer] Quality issues for {city}: {' | '.join(warnings)}")
    else:
        logger.info(f"[nomad_writer] Quality OK for {city} ({word_count} words)")

    return warnings

def generate_nomad_guide(topic):
    city = topic["city"]
    country = topic.get("country", "")
    data = fetch_data(city, country)
    summary = _build_summary(data, city, country)
    h2s = """  ## Why Digital Nomads Choose {city}
  ## Best Coworking Spaces in {city}
  ## Internet SIM Cards and Connectivity
  ## Cost of Living for Nomads in {city}
  ## Visa and Stay Options
  ## Neighborhoods and Where to Stay
  ## Tips for Digital Nomads in {city}"""

    has_coworking = len(data.get("coworking", [])) > 0
    has_climate = len(data.get("climate", [])) > 0
    has_cost = bool(data.get("cost"))
    has_cafes = len(data.get("cafes", [])) > 0

    data_instructions = []
    if has_coworking:
        data_instructions.append(
            "- COWORKING: Use the EXACT names (character-for-character) from [COWORKING SPACES] data. "
            "Names will be auto-linked to Google Maps, so they MUST match the data spelling precisely. "
            "Describe each space with specific details from the data (location, hours, vibe). "
            "Mention at least 4-5 named coworking spaces from the data. "
            "Do NOT invent coworking spaces not in the data."
        )
    if has_climate:
        data_instructions.append(
            "- CLIMATE: Use [MONTHLY CLIMATE] data to recommend the best months to visit. "
            "Mention specific temperatures and rainy seasons. "
            "Compare seasons to help nomads plan their stay."
        )
    if has_cost:
        data_instructions.append(
            "- COST: Copy prices VERBATIM from [COST OF LIVING] data (the format 'LOCAL (~$USD)' is PRE-CALCULATED). "
            "Do NOT recalculate USD conversions yourself - use the exact parenthetical already provided. "
            "Do NOT invent any additional prices not in the data. "
            "Build a realistic monthly budget breakdown using only the provided figures."
        )
    if has_cafes:
        data_instructions.append(
            "- CAFES: Mention specific wifi cafes from [WIFI CAFES] data by name and location. "
            "These are real places - use their actual details."
        )

    data_rules = chr(10).join(data_instructions)

    prompt = f"""Write a digital nomad guide for {city}, {country}.

CONTEXT DATA (USE THIS - these are verified facts, not suggestions):
{summary}

DATA USAGE RULES:
{data_rules}
- For any section WITHOUT data provided, write general practical advice (2-3 sentences max).
- NEVER fabricate specific business names, prices, or statistics not in the data.
- CRITICAL: If [COST OF LIVING] data is NOT provided, do NOT write any percentage comparisons
  like "50% cheaper than X" or "40% lower than Y". These numbers are hallucinated.
  Instead write qualitative statements: "generally affordable", "lower than Western Europe".
- CRITICAL: If [COWORKING SPACES] data is NOT provided, do NOT invent coworking space names.

FORMAT RULES:
- Write MINIMUM 1,500 words, target 1,800-2,200 words in English. Articles under 1,500 words are rejected
- Do NOT include any booking links or affiliate URLs in the text
- Title MUST include "{city}" but MUST NOT follow the pattern "City + Digital Nomad Guide"
- Create a unique, specific title that highlights what makes {city} special for remote workers
- Good examples: "Why {city} Is the Best-Kept Secret for Remote Workers", "{city} on a Laptop: Coworking, Costs, and the Best Cafes", "Working Remotely from {city}: An Honest Cost and Connectivity Breakdown"
- Bad examples (NEVER use): "{city} Digital Nomad Guide", "A Digital Nomad\'s Guide to {city}", "{city}: Digital Nomad Guide to Coworking and Connectivity"
- Required H2 sections:
{h2s}
- If a section has fewer than 2 data points, OMIT that H2 entirely
- Do NOT use numbered lists, write in flowing paragraphs with transitions
- Each section must start differently - NEVER begin two sections the same way
- Add ONE actionable tip per section (bold the tip)
- Add ONE CTA near the end
- Vary sentence length: mix short punchy sentences with longer descriptive ones

STYLE RULES:
- Open with a specific sensory detail about {city}, not a generic "City X has become popular" statement
- Each section needs a unique opening - no two sections should start with similar phrasing
- Include at least 2 concrete comparisons (e.g. "cheaper than Lisbon by 30%", "faster wifi than Bali")
- Mention one genuine downside or challenge per section to build credibility
- Write from first-person experience perspective

Return ONLY the article in markdown starting with # title"""
    result = ai_generate(
        "You are a full-time digital nomad and remote work consultant who has lived and worked in 50+ cities for 8+ years. STRICT RULES: 1) BANNED WORDS - never use: vibrant, bustling, hidden gem, treasure trove, must-visit, immerse yourself, embark, crystal-clear, world-class, bucket list, plethora, tapestry, myriad, making it an attractive, making it an ideal, making it appealing, rich culture, like-minded individuals, unique blend, whether you, no wonder. 2) USE PROVIDED DATA as primary source of truth. Do not invent facts when data is given. 3) Every section must include one bold actionable tip. 4) Write with specific details, not generic praise. 5) Acknowledge real downsides - no city is perfect. 6) When cost data is provided, always use the exact figures with local currency and USD conversion.",
        prompt,
        temperature=0.5,
        max_tokens=4000,
        )
    content = result["content"].strip()
    title_match = re.match(r"^#\s+(.+)", content)
    title = title_match.group(1).strip() if title_match else f"Digital Nomad Guide to {city}"
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    # Inject Google Maps buttons next to coworking space mentions
    content = _clean_gpt_map_tags(content)  # GPT hallucinated map tags 제거
    content = _inject_map_buttons(content, data.get("coworking", []), city=city, country=country)
    # Post-hoc quality validation (logs warnings, does not regenerate)
    _validate_content(content, data, city)
    slug = topic.get("slug", re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-") + "-digital-nomad-guide")
    tags = [city, country, "Digital Nomad", "Coworking", "Remote Work"] if country else [city, "Digital Nomad", "Coworking"]
    return {"title": title, "slug": slug, "content": content,
             "description": f"Digital nomad guide to {city}: coworking spaces, internet, visa, cost of living and tips.",
             "tags": [t for t in tags if t], "city": city, "country": country, "tours": []}
