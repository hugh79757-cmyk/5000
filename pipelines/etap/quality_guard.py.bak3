"""quality_guard.py - Pre/post processing quality checks for ETAP content pipeline.

Pre-processing: validates and cleans tour/route data before sending to GPT.
Post-processing: validates generated content for suspicious numbers, formatting issues.
If quality check fails, marks post as draft and sends Telegram alert.
"""
import os, re, logging, requests

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ============================================================
# TELEGRAM ALERT
# ============================================================
def send_alert(blog_id, slug, issues):
    """Send Telegram alert for quality issues."""
    msg = f"⚠️ ETAP Quality Alert\n\nBlog: {blog_id}\nSlug: {slug}\nIssues:\n"
    for issue in issues:
        msg += f"  - {issue}\n"
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
            logger.info(f"[QualityGuard] Telegram alert sent for {blog_id}/{slug}")
        except Exception as e:
            logger.error(f"[QualityGuard] Telegram failed: {e}")
    else:
        logger.warning(f"[QualityGuard] No Telegram config. Issues: {issues}")

# ============================================================
# PRE-PROCESSING: Tour Data Validation
# ============================================================
MIN_PRICE_USD = 5.0
MAX_PRICE_USD = 50000.0
MAX_DISCOUNT_PCT = 70.0

def clean_tour_name(name):
    """Remove 'Save XX%!' prefix and clean whitespace."""
    if not name:
        return name
    name = re.sub(r"^Save\s+[\d.]+%!\s*", "", name)
    name = re.sub(r"\s{2,}", " ", name).strip()
    return name

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
        issues.append(f"Suspicious discount: {discount_val}% for '{tour['product_name'][:50]}'")

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
    for pattern_pn in [r'\*\*\[([^\]]+)\]', r'\[([^\]]+)\]\(https://www\.viator\.com']:
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
    }
    import re as _re
    for phrase, replacement in REPLACEMENTS.items():
        pattern = _re.compile(_re.escape(phrase), _re.IGNORECASE)
        if pattern.search(content):
            content = pattern.sub(replacement, content)
            issues.append(f"Auto-replaced: '{phrase}' -> '{replacement}'")

    # Fix article mismatches from replacements (an -> a before consonant)
    content = re.sub(r'\ban (standout|busy|lively|lesser-known|mix|long|start)\b', r'a \1', content)
    content = re.sub(r'\bAn (standout|busy|lively|lesser-known|mix|long|start)\b', r'A \1', content)

    # Fix $X.0 formatting -> $X
    content = re.sub(r'\$(\d+)\.0\b', r'$\1', content)
    content = re.sub(r'\$(\d+)\.00\b', r'$\1', content)

    # Check for suspicious prices in text ($0, $0.X, $1, $2, $3, $4)
    suspicious_prices = re.findall(r'\$([0-4](?:\.\d+)?)\b', content)
    if suspicious_prices:
        issues.append(f"Suspicious low prices in text: ${', $'.join(suspicious_prices)}")
        is_draft = True

    # Check for very high prices (possible hallucination)
    high_prices = re.findall(r'\$(\d{5,})', content)
    if high_prices:
        issues.append(f"Suspiciously high prices: ${', $'.join(high_prices)}")
        is_draft = True

    # Validate prices against source data if provided
    hallucinated_prices = []
    if data_prices:
        text_prices = set(re.findall(r'\$(\d+(?:\.\d{1,2})?)', content))
        for tp in text_prices:
            try:
                tpf = float(tp)
                if tpf >= 5 and not any(abs(tpf - dp) < 2.0 for dp in data_prices):
                    hallucinated_prices.append(tp)
                    issues.append(f"Hallucinated price ${tp} not in source data")
            except ValueError:
                pass
    if len(hallucinated_prices) >= 3:
        is_draft = True
        issues.append(f"Too many hallucinated prices ({len(hallucinated_prices)}), marking as draft")

    # Check for fabricated URLs (GPT sometimes adds them despite instructions)
    url_pattern = re.findall(r'https?://[^\s\)]+', content)
    allowed_domains = ["r2.dev", "techpawz.com", "googlesyndication.com"]
    for url in url_pattern:
        if not any(d in url for d in allowed_domains):
            issues.append(f"Unauthorized URL found: {url[:60]}")
            content = content.replace(url, "")

    # Check minimum H2 sections
    h2_count = len(re.findall(r'^## ', content, re.MULTILINE))
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
