"""quality_guard.py - Pre/post processing quality checks for ETAP content pipeline.

Pre-processing: validates and cleans tour/route data before sending to GPT.
Post-processing: validates generated content for suspicious numbers, formatting issues.
If quality check fails, marks post as draft and sends Telegram alert.
"""
import logging
import os
import re

logger = logging.getLogger(__name__)

# ── 텔레그램 알림은 shared/telegram_notifier 경유 ──
def _tg_warning(title, detail="") -> None:
    try:
        from shared.telegram_notifier import send_warning
        send_warning(title, detail)
    except Exception as _e:
        logger.exception(f"[QualityGuard] 텔레그램 전송 실패: {_e}")

def _tg_critical(title, detail="") -> None:
    try:
        from shared.telegram_notifier import send_critical
        send_critical(title, detail)
    except Exception as _e:
        logger.exception(f"[QualityGuard] 텔레그램 전송 실패: {_e}")


# ============================================================
# TELEGRAM ALERT
# ============================================================
def send_alert(blog_id, slug, issues) -> None:
    """품질 이슈 알림 — CRITICAL/WARNING 자동 분리."""
    if not issues:
        return

    critical_issues = [i for i in issues if "[CRITICAL]" in i]
    warning_issues  = [i for i in issues if "[WARNING]" in i or "[CRITICAL]" not in i]

    # Auto-replace는 WARNING으로도 보내지 않음 (INFO 레벨 — 로그만)
    auto_replaced  = [i for i in issues if i.startswith("Auto-replaced:")]
    real_warnings  = [i for i in warning_issues if i not in auto_replaced]

    detail_lines = [f"Blog: {blog_id}", f"Slug: {slug}", "Issues:"]
    for issue in issues[:10]:  # 최대 10개
        detail_lines.append(f"  - {issue}")
    detail = "\n".join(detail_lines)

    if critical_issues:
        _tg_critical(f"ETAP 품질 CRITICAL — {blog_id}", detail)
        logger.error(f"[QualityGuard] CRITICAL {blog_id}/{slug}: {critical_issues}")
    elif real_warnings:
        _tg_warning(f"ETAP 품질 이슈 — {blog_id}", detail)
        logger.warning(f"[QualityGuard] WARNING {blog_id}/{slug}: {real_warnings}")
    else:
        # auto-replace만 있으면 로그만
        logger.info(f"[QualityGuard] auto-replace only {blog_id}/{slug}: {auto_replaced[:3]}")

# ============================================================
# PRE-PROCESSING: Tour Data Validation
# ============================================================
MIN_PRICE_USD = 8.0
MAX_PRICE_USD = 50000.0
MAX_DISCOUNT_PCT = 60.0

def clean_tour_name(name):
    """Remove 'Save XX%!' prefix and clean whitespace."""
    if not name:
        return name
    name = re.sub(r"^Save\s+[\d.]+%!\s*", "", name)
    return re.sub(r"\s{2,}", " ", name).strip()

def validate_tour(tour):
    """Validate a single tour dict. Returns (cleaned_tour, issues_list).
    If issues_list is not empty, the tour has problems.
    Returns None for tour if it should be excluded entirely.
    """
    issues = []
    if not tour:
        return None, ["Empty tour"]

    # Clean name
    name = tour.get("product_name", "")
    tour["product_name"] = clean_tour_name(name)

    # Price validation
    try:
        price = float(str(tour.get("price", 0)).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        price = 0

    if price < MIN_PRICE_USD:
        return None, [f"Price too low: ${price} for '{tour['product_name'][:50]}' (min ${MIN_PRICE_USD})"]

    if price > MAX_PRICE_USD:
        return None, [f"Price too high: ${price} for '{tour['product_name'][:50]}' (max ${MAX_PRICE_USD})"]

    # Discount validation
    discount = tour.get("discount") or tour.get("discount_percent") or 0
    try:
        discount_val = float(str(discount).replace("%", "").strip())
    except (ValueError, TypeError):
        discount_val = 0

    if discount_val > MAX_DISCOUNT_PCT:
        return None, [f"Excluded: discount {discount_val}% exceeds {MAX_DISCOUNT_PCT}% for '{tour['product_name'][:50]}'"]

    # Deep link validation
    link = tour.get("deep_link", "")
    if not link or not link.startswith("http"):
        issues.append(f"Missing/invalid deep_link for '{tour['product_name'][:50]}'")

    return tour, issues

def preprocess_tours(tours, blog_id="", city=""):
    """Validate and clean a list of tours.
    Returns (clean_tours, all_issues, excluded_count).
    """
    clean = []
    all_issues = []
    excluded = 0

    for t in tours:
        cleaned, issues = validate_tour(t)
        if cleaned is None:
            excluded += 1
            all_issues.extend(issues)
        else:
            clean.append(cleaned)
            all_issues.extend(issues)

    if excluded > 0:
        logger.info(f"[QualityGuard] {blog_id}/{city}: excluded {excluded} tours, {len(clean)} remaining")

    return clean, all_issues, excluded

# ============================================================
# PRE-PROCESSING: Route Data Validation (Omio)
# ============================================================
MIN_ROUTE_PRICE = 1.0
MAX_ROUTE_PRICE = 5000.0

def validate_route(route):
    """Validate Omio route data."""
    issues = []
    if not route:
        return None, ["Empty route"]

    for mode in ["train", "bus", "flight", "ferry"]:
        price_key = f"{mode}_min_price"
        dur_key = f"{mode}_min_duration"
        price = route.get(price_key)
        dur = route.get(dur_key)

        if price is not None:
            try:
                pval = float(price)
                if pval < MIN_ROUTE_PRICE:
                    issues.append(f"{mode} price too low: {pval}")
                    route[price_key] = None
                if pval > MAX_ROUTE_PRICE:
                    issues.append(f"{mode} price too high: {pval}")
                    route[price_key] = None
            except (ValueError, TypeError):
                route[price_key] = None

        if dur is not None:
            try:
                dval = int(dur)
                if dval <= 0 or dval > 4320:
                    issues.append(f"{mode} duration suspicious: {dval} min")
                    route[dur_key] = None
            except (ValueError, TypeError):
                route[dur_key] = None

    return route, issues

def preprocess_routes(routes, blog_id="", origin="", dest=""):
    """Validate and clean route list."""
    clean = []
    all_issues = []
    for r in routes:
        cleaned, issues = validate_route(r)
        if cleaned:
            clean.append(cleaned)
        all_issues.extend(issues)
    return clean, all_issues

# ============================================================
# PRE-PROCESSING: Restaurant Data Validation (Michelin)
# ============================================================
VALID_AWARDS = {"3 Stars", "2 Stars", "1 Star", "Bib Gourmand", "Selected", ""}

def validate_restaurant(rest):
    """Validate Michelin restaurant data."""
    issues = []
    if not rest:
        return None, ["Empty restaurant"]

    name = rest.get("name", "")
    if not name or len(name) < 2:
        return None, ["Missing restaurant name"]

    award = rest.get("award", "")
    if award and award not in VALID_AWARDS:
        issues.append(f"Unknown award '{award}' for {name}")

    return rest, issues

def preprocess_restaurants(restaurants, blog_id="", city=""):
    """Validate and clean restaurant list."""
    clean = []
    all_issues = []
    excluded = 0
    for r in restaurants:
        cleaned, issues = validate_restaurant(r)
        if cleaned is None:
            excluded += 1
        else:
            clean.append(cleaned)
        all_issues.extend(issues)
    return clean, all_issues, excluded

# ============================================================
# POST-PROCESSING: Content Validation
# ============================================================
BANNED_PHRASES = [
    "plethora", "vibrant", "bustling", "let's dive in", "without further ado",
    "hidden gem", "tapestry", "myriad", "embark on", "rich cultural heritage",
    "culinary delights", "adrenaline junkie", "crystal-clear waters",
    "unforgettable experience", "gastronomic journey",
]

def postprocess_content(content, data_prices=None, blog_id="", slug=""):
    """Validate generated content. Returns (content, issues, is_draft).
    is_draft=True means the post should be published as draft.
    """
    issues = []
    is_draft = False

    if not content or len(content) < 200:
        issues.append("Content too short (< 200 chars)")
        is_draft = True
        return content, issues, is_draft

    # Extract tour/product names to protect them from replacement
    import re as _re2
    _protected_names = set()
    for pattern_pn in [r"\*\*\[([^\]]+)\]", r"\[([^\]]+)\]\(https://www\.viator\.com"]:
        for m in _re2.finditer(pattern_pn, content):
            _protected_names.add(m.group(1))

    # Replace protected names with placeholders
    _name_map = {}
    for i, name in enumerate(_protected_names):
        placeholder = f"__PROTECTED_NAME_{i}__"
        _name_map[placeholder] = name
        content = content.replace(name, placeholder)

    # Check and replace banned phrases
    REPLACEMENTS = {
        "plethora of": "range of",
        "plethora": "range",
        "vibrant": "lively",
        "bustling": "busy",
        "let's dive in": "",
        "let's dive into": "here's a look at",
        "without further ado": "",
        "hidden gem": "lesser-known spot",
        "hidden gems": "lesser-known spots",
        "tapestry": "mix",
        "myriad": "wide range",
        "embark on": "start",
        "embark": "start",
        "rich cultural heritage": "deep history",
        "culinary delights": "local dishes",
        "adrenaline junkie": "thrill-seeker",
        "crystal-clear waters": "clear water",
        "crystal-clear": "clear",
        "unforgettable experience": "standout experience",
        "unforgettable": "standout",
        "gastronomic journey": "food scene",
        "gastronomic": "food",
        "rich history and culture": "long history",
        "soak in": "take in",
        "immerse yourself": "explore",
        "treasure trove": "great destination",
        "unexpected treasures": "interesting finds",
        "incredible city": "remarkable city",
        "rich history": "long history",
        "A Comprehensive": "A Practical",
        "a comprehensive": "a practical",
        "In conclusion,": "",
        "In conclusion": "",
        "whisk you away": "take you",
        "living history book": "city full of history",
        "like flipping through the pages": "a walk through",
        "Your Ultimate": "A Practical",
        "your ultimate": "a practical",
        "must-try": "worth trying",
        "a must for": "ideal for",
        "spirit soaring": "",
        "synonymous with": "known for",
        "Greek adventure": "trip in Greece",
        "paradise for": "popular with",
        "bucket list": "travel wishlist",
        "playground for": "popular with",
        "soaking up": "enjoying",
        "unmatched": "impressive",
        "of a lifetime": "",
        "second to none": "excellent",
        "a must-visit": "worth visiting",
        "must-visit": "worth visiting",
        "paradise for": "great for",
        "world-class": "top-quality",
        "world class": "top-quality",
        "like no other": "distinctive",
        "one-of-a-kind": "distinctive",
        "bucket list": "travel wish list",
        "not disappoint": "deliver",
        "won't disappoint": "delivers",
        "leave you breathless": "impress you",
        "feast for the eyes": "beautiful sight",
        "a true": "a solid",
        "look no further": "",
        "haven for": "great for",
        "left me in awe": "impressed me",
        "in awe of": "impressed by",
        "adventure awaits": "",
        "awaits you": "is available",
        "your ultimate guide": "a practical guide",
        "palpable": "real",
        "escapades": "activities",
        "a playground for": "popular with",
        "thrill-seekers": "adventure travelers",
        "adrenaline-fueled": "exciting",
        "action-packed": "full of activities",
        "standout encounter": "great experience",
    }
    import re as _re
    for phrase, replacement in REPLACEMENTS.items():
        pattern = _re.compile(_re.escape(phrase), _re.IGNORECASE)
        if pattern.search(content):
            content = pattern.sub(replacement, content)
            issues.append(f"Auto-replaced: '{phrase}' -> '{replacement}'")

    # Fix article mismatches from replacements (an -> a before consonant)
    content = re.sub(r"\ban (standout|busy|lively|lesser-known|mix|long|start)\b", r"a \1", content)
    content = re.sub(r"\bAn (standout|busy|lively|lesser-known|mix|long|start)\b", r"A \1", content)

    # Fix price formatting: $X.0 -> $X, $X.00 -> $X
    content = re.sub(r"\$(\d+)\.0\b", r"$\1", content)
    content = re.sub(r"\$(\d+)\.00\b", r"$\1", content)

    # Normalize currency: "USD 31.50" -> "$32", "GBP 10.31" -> "$10", "EUR 25.00" -> "$25"
    def _normalize_currency(m) -> str:
        m.group(1)
        val = float(m.group(2))
        return f"${round(val)}"
    content = re.sub(r"\b(USD|GBP|EUR)\s+(\d+(?:\.\d+)?)", _normalize_currency, content)

    # Also fix "From **USD X**" patterns in product cards
    content = re.sub(r"From \*\*(USD|GBP|EUR)\s+(\d+(?:\.\d+)?)\*\*",
                     lambda m: f"From **${round(float(m.group(2)))}**", content)
    # Round prices with single decimal: $31.5 -> $32, $159.2 -> $159
    def _round_price(m) -> str:
        val = float(m.group(1) + "." + m.group(2))
        return f"${round(val)}"
    content = re.sub(r"\$(\d+)\.(\d)\b(?!\d)", _round_price, content)

    # Fix discount percentages in text: -20.01% -> -20%, -35.0% -> -35%, -0.0% -> remove
    def _fix_discount_text(m) -> str:
        val = abs(float(m.group(1)))
        if val < 0.5:
            return ""
        return f"-{round(val)}%"
    content = re.sub(r"-(\d+\.?\d*)%", _fix_discount_text, content)

    # Check for suspicious prices in text ($0, $0.X, $1 — $2~$4 is valid for rail/tour data)
    suspicious_prices = re.findall(r"\$0(?!\.\d)\b", content)
    if suspicious_prices:
        issues.append("Suspicious low prices in text: $0 found")
        is_draft = True

    # Check for very high prices (possible hallucination)
    high_prices = re.findall(r"\$(\d{5,})", content)
    if high_prices:
        issues.append(f"Suspiciously high prices: ${', $'.join(high_prices)}")
        is_draft = True

    # Validate prices against source data if provided
    hallucinated_prices = []
    if data_prices:
        text_prices = set(re.findall(r"\$(\d+(?:\.\d{1,2})?)", content))
        for tp in text_prices:
            try:
                tpf = float(tp)
                if tpf >= 5 and not any(abs(tpf - dp) < 2.0 for dp in data_prices):
                    hallucinated_prices.append(tp)
                    issues.append(f"Hallucinated price ${tp} not in source data")
                    # Remove sentence containing the hallucinated price
                    escaped = re.escape(f"${tp}")
                    content = re.sub(r"[^.!?]*" + escaped + r"[^.!?]*[.!?]", "", content, count=1)
            except ValueError:
                pass
    if len(hallucinated_prices) >= 3:
        is_draft = True
        issues.append(f"Too many hallucinated prices ({len(hallucinated_prices)}), marking as draft")

    # Check for fabricated URLs (GPT sometimes adds them despite instructions)
    url_pattern = re.findall(r"https?://[^\s\)]+", content)
    allowed_domains = ["r2.dev", "techpawz.com", "googlesyndication.com"]
    for url in url_pattern:
        if not any(d in url for d in allowed_domains):
            issues.append(f"Unauthorized URL found: {url[:60]}")
            content = content.replace(url, "")

        # Remove duplicate CTA phrases (keep only the first occurrence)
    cta_patterns = [
        "These tours fill up fast during peak season",
        "check availability and lock in today",
        "before it changes",
        "before prices change",
    ]
    for cta in cta_patterns:
        count = content.count(cta)
        if count > 1:
            first_pos = content.index(cta) + len(cta)
            content = content[:first_pos] + content[first_pos:].replace(cta, "")
            issues.append(f"Duplicate CTA removed: '{cta[:40]}...' ({count-1} removed)")

    # Remove empty H2 sections (GPT writes "Currently there are no..." filler)
    empty_patterns = [
        r"## [^\n]+\n+(?:Currently,? there are no|No specific|There are no specific|No data available|This section)[^\n]*(?:\n(?!## |<div|<script)[^\n]*)*",
    ]
    for ep in empty_patterns:
        content = re.sub(ep, "", content, flags=re.IGNORECASE)

        # Check for fabricated relative links (GPT invents /posts/slug/ links)
    fake_link_pattern = re.findall(r"\[([^\]]+)\]\(/posts/([^)]+)/\)", content)
    if fake_link_pattern:
        import sqlite3 as _sql
        _db = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "travel-en.db")
        _conn = _sql.connect(_db)
        _published_slugs = {r[0] for r in _conn.execute("SELECT DISTINCT post_slug FROM entity_links WHERE published = 1").fetchall()}
        _conn.close()
        for label, slug in fake_link_pattern:
            if slug.rstrip("/") not in _published_slugs:
                fake_md = f"[{label}](/posts/{slug}/)"
                content = content.replace(fake_md, label)
                issues.append(f"Removed fabricated link: {fake_md[:80]}")

    # Check minimum H2 sections
    h2_count = len(re.findall(r"^## ", content, re.MULTILINE))
    if h2_count < 3:
        issues.append(f"Only {h2_count} H2 sections (minimum 3)")
        is_draft = True

    # Word count check
    word_count = len(content.split())
    if word_count < 400:
        issues.append(f"Word count too low: {word_count} (minimum 400)")
        is_draft = True
    elif word_count < 500:
        issues.append(f"Word count low: {word_count} - will be supplemented with cards, images, and cross-links")

    # ── S0: LaTeX + 0허위 게이트 (Track C 2026-08-21) ──
    # LaTeX $\rightarrow$ 누수 치환
    if re.search(r"\$\\rightarrow\$|\\rightarrow", content):
        content = re.sub(r"\$\\rightarrow\$", "→", content)
        content = re.sub(r"\\rightarrow", "→", content)
        issues.append("Auto-replaced: LaTeX $\\rightarrow$ → →")
    # 빈 데이터 허위 단정 차단 — count 0을 사실로 렌더
    _zero_pats = [
        r"\|\s*(Airlines operating|Direct destinations|Route Count|Airports Served)[^|]*\|\s*0\s*\|",
        r"there are no airlines[^.\n]*operating",
        r"Route Count\s*0",
        r"Airports Served\s*0",
    ]
    for _pat in _zero_pats:
        if re.search(_pat, content, re.IGNORECASE):
            issues.append(f"[CRITICAL] empty-data hallucination: count=0 rendered as fact")
            is_draft = True
            break

    # Append disclaimer card if not already present
    disclaimer = """
<div class="etap-disclaimer-card">

> **📌 Disclaimer**
>
> Prices, schedules, tour details, flight routes, visa requirements, and all other information on this page are based on data **at the time of writing**. Fares, availability, and policies may change. Please verify current details on the official website before booking.

</div>
"""
    if "etap-disclaimer-card" not in content:
        content = content + disclaimer

    return content, issues, is_draft

# ============================================================
# HUGO DRAFT HELPER
# ============================================================
def make_draft(front_matter):
    """Add draft: true to Hugo front matter string."""
    if "draft:" not in front_matter:
        front_matter = front_matter.replace("showTableOfContents: true\n---",
                                             "showTableOfContents: true\ndraft: true\n---")
    return front_matter
