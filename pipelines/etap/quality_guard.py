"""quality_guard.py - Pre/post processing quality checks for ETAP content pipeline.

Pre-processing: validates and cleans tour/route data before sending to GPT.
Post-processing: validates generated content for suspicious numbers, formatting issues.
If quality check fails, marks post as draft and sends Telegram alert.

Phase 70 Wave 1: Added S01 (Uniqueness Ratio), S02 (Structural Similarity),
S03 (Unique Data Points) quality gates.
"""
import logging
import os
import re
from typing import List, Tuple

# sklearn/numpy for quality gates
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

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
# PHASE 70 WAVE 1: NEW QUALITY GATES (S01, S02, S03)
# ============================================================

# S01: Uniqueness Ratio Gate
# Threshold: >= 0.85 (85% unique n-grams vs existing corpus)
# Returns (passed: bool, ratio: float, details: dict)
def uniqueness_ratio_gate(content: str, corpus: List[str], threshold: float = 0.85) -> Tuple[bool, float, dict]:
    """
    Compute uniqueness ratio of generated content against existing corpus.
    
    Uses TF-IDF cosine similarity to measure how much of the content
    overlaps with previously published articles. Higher ratio = more unique.
    
    Args:
        content: Generated article content (markdown)
        corpus: List of existing article bodies (markdown)
        threshold: Minimum uniqueness ratio to pass (default 0.85)
    
    Returns:
        (passed, ratio, details) where details contains:
        - max_similarity: highest cosine similarity to any corpus item
        - mean_similarity: average cosine similarity
        - n_compared: number of corpus items compared
    """
    if not HAS_SKLEARN:
        logger.warning("[S01] scikit-learn not available, skipping uniqueness gate")
        return True, 1.0, {"skipped": "sklearn unavailable"}
    
    if not corpus:
        return True, 1.0, {"n_compared": 0}
    
    try:
        # Extract text content (remove markdown formatting for better comparison)
        def clean_text(text: str) -> str:
            # Remove markdown headers, links, emphasis
            text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
            text = re.sub(r"[*_`]", "", text)
            text = re.sub(r"<[^>]+>", "", text)
            return text.strip()
        
        clean_content = clean_text(content)
        clean_corpus = [clean_text(c) for c in corpus if c and len(c) > 100]
        
        if not clean_corpus:
            return True, 1.0, {"n_compared": 0}
        
        # Build TF-IDF vectors
        vectorizer = TfidfVectorizer(
            ngram_range=(3, 5),  # 3-5 grams for phrase-level similarity
            min_df=1,
            max_df=0.9,
            stop_words='english',
            max_features=10000
        )
        
        all_texts = [clean_content] + clean_corpus
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        
        # Compute cosine similarity between content and each corpus item
        content_vec = tfidf_matrix[0:1]
        corpus_vecs = tfidf_matrix[1:]
        
        similarities = cosine_similarity(content_vec, corpus_vecs).flatten()
        
        max_sim = float(similarities.max()) if len(similarities) > 0 else 0.0
        mean_sim = float(similarities.mean()) if len(similarities) > 0 else 0.0
        
        # Uniqueness ratio = 1 - max_similarity
        uniqueness = 1.0 - max_sim
        
        details = {
            "max_similarity": round(max_sim, 4),
            "mean_similarity": round(mean_sim, 4),
            "n_compared": len(similarities),
            "threshold": threshold
        }
        
        passed = uniqueness >= threshold
        
        if not passed:
            logger.warning(
                f"[S01] Uniqueness gate FAILED: ratio={uniqueness:.4f} "
                f"(threshold={threshold}), max_sim={max_sim:.4f}, n_compared={len(similarities)}"
            )
        else:
            logger.info(
                f"[S01] Uniqueness gate PASSED: ratio={uniqueness:.4f} "
                f"(threshold={threshold}), max_sim={max_sim:.4f}"
            )
        
        return passed, uniqueness, details
    
    except Exception as e:
        logger.exception(f"[S01] Uniqueness gate error: {e}")
        return True, 1.0, {"error": str(e), "skipped": True}


# S02: Structural Similarity Gate
# Threshold: <= 0.70 (max 70% H2 sequence overlap with any existing article)
# Returns (passed: bool, similarity: float, details: dict)
def structural_similarity_gate(content: str, corpus: List[str], threshold: float = 0.70) -> Tuple[bool, float, dict]:
    """
    Compare H2 heading structure similarity against existing articles.
    
    Detects template reuse where the same H2 sequence is used with different content.
    Uses Jaccard similarity on H2 heading sequences (order-aware).
    
    Args:
        content: Generated article content (markdown)
        corpus: List of existing article bodies (markdown)
        threshold: Maximum allowed structural similarity (default 0.70)
    
    Returns:
        (passed, similarity, details) where details contains:
        - max_structural_sim: highest structural similarity to any corpus item
        - content_h2s: list of H2 headings in content
        - matched_article_h2s: H2 headings of most similar corpus article
    """
    def extract_h2s(text: str) -> List[str]:
        h2s = re.findall(r"^##\s+(.+)$", text, re.MULTILINE)
        # Normalize: lowercase, remove punctuation, strip
        normalized = []
        for h in h2s:
            h = h.lower().strip()
            h = re.sub(r"[^\w\s]", "", h)
            h = re.sub(r"\s+", " ", h)
            normalized.append(h)
        return normalized
    
    def jaccard_similarity(seq1: List[str], seq2: List[str]) -> float:
        """Order-aware Jaccard on n-grams of headings."""
        if not seq1 or not seq2:
            return 0.0
        
        # Use bigrams of headings for order awareness
        def get_bigrams(seq):
            return set(tuple(seq[i:i+2]) for i in range(len(seq)-1)) or set(tuple(seq))
        
        bigrams1 = get_bigrams(seq1)
        bigrams2 = get_bigrams(seq2)
        
        if not bigrams1 or not bigrams2:
            # Fallback to unigram Jaccard
            set1, set2 = set(seq1), set(seq2)
            inter = len(set1 & set2)
            union = len(set1 | set2)
            return inter / union if union > 0 else 0.0
        
        inter = len(bigrams1 & bigrams2)
        union = len(bigrams1 | bigrams2)
        return inter / union if union > 0 else 0.0
    
    content_h2s = extract_h2s(content)
    
    if not content_h2s:
        return True, 0.0, {"content_h2s": [], "n_compared": 0}
    
    max_sim = 0.0
    matched_h2s = []
    n_compared = 0
    
    for corpus_item in corpus:
        if not corpus_item or len(corpus_item) < 100:
            continue
        corpus_h2s = extract_h2s(corpus_item)
        if not corpus_h2s:
            continue
        
        sim = jaccard_similarity(content_h2s, corpus_h2s)
        if sim > max_sim:
            max_sim = sim
            matched_h2s = corpus_h2s
        n_compared += 1
    
    passed = max_sim <= threshold
    
    details = {
        "max_structural_sim": round(max_sim, 4),
        "content_h2s": content_h2s,
        "matched_article_h2s": matched_h2s,
        "n_compared": n_compared,
        "threshold": threshold
    }
    
    if not passed:
        logger.warning(
            f"[S02] Structural similarity gate FAILED: sim={max_sim:.4f} "
            f"(threshold={threshold}), content_h2s={content_h2s[:5]}"
        )
    else:
        logger.info(
            f"[S02] Structural similarity gate PASSED: sim={max_sim:.4f} "
            f"(threshold={threshold})"
        )
    
    return passed, max_sim, details


# S03: Unique Data Points Gate
# Threshold: >= 3 verifiable unique data points per article
# Returns (passed: bool, count: int, details: dict)
def unique_data_points_gate(content: str, source_data: dict = None, threshold: int = 3) -> Tuple[bool, int, dict]:
    """
    Verify article contains minimum number of verifiable unique data points.
    
    Counts specific, verifiable facts from source data that appear in the article:
    - Specific prices (e.g., "$45", "$1,200")
    - Specific dates (e.g., "March 15, 2024", "2024-03-15")
    - Specific names/identifiers from source (airlines, tour operators, destinations)
    - Specific metrics (duration, distance, capacity, ratings)
    
    Args:
        content: Generated article content (markdown)
        source_data: Dict of source data used for generation (prices, names, dates, etc.)
        threshold: Minimum unique data points required (default 3)
    
    Returns:
        (passed, count, details) where details contains:
        - found_points: list of verified data points found in content
        - source_coverage: which source data categories were covered
    """
    if source_data is None:
        source_data = {}
    
    found_points = []
    source_coverage = {}
    
    # 1. Price points - extract from content and verify against source
    price_pattern = r"\$(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
    content_prices = set(re.findall(price_pattern, content))
    source_prices = set()
    
    # Extract prices from source_data (various possible structures)
    for key, val in source_data.items():
        if isinstance(val, (list, tuple)):
            for item in val:
                if isinstance(item, dict):
                    for price_key in ["price", "min_price", "max_price", "cost", "fare"]:
                        if price_key in item and item[price_key]:
                            source_prices.add(str(item[price_key]))
        elif isinstance(val, dict):
            for price_key in ["price", "min_price", "max_price", "cost", "fare"]:
                if price_key in val and val[price_key]:
                    source_prices.add(str(val[price_key]))
    
    # Verify content prices against source
    for cp in content_prices:
        cp_clean = cp.replace(",", "")
        for sp in source_prices:
            sp_clean = str(sp).replace("$", "").replace(",", "")
            try:
                if abs(float(cp_clean) - float(sp_clean)) <= 2.0:  # Within $2 tolerance (inclusive)
                    found_points.append(f"price:${cp}")
                    source_coverage["prices"] = source_coverage.get("prices", 0) + 1
                    break
            except (ValueError, TypeError):
                pass
    
    # 2. Date points
    date_patterns = [
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
    ]
    content_dates = set()
    for pat in date_patterns:
        content_dates.update(re.findall(pat, content, re.IGNORECASE))
    
    source_dates = set()
    for key, val in source_data.items():
        if isinstance(val, (list, tuple)):
            for item in val:
                if isinstance(item, dict):
                    for date_key in ["date", "departure_date", "return_date", "start_date", "end_date", "available_date"]:
                        if date_key in item and item[date_key]:
                            source_dates.add(str(item[date_key]))
    
    for cd in content_dates:
        for sd in source_dates:
            if cd.lower() in sd.lower() or sd.lower() in cd.lower():
                found_points.append(f"date:{cd}")
                source_coverage["dates"] = source_coverage.get("dates", 0) + 1
                break
    
    # 3. Named entities from source (airlines, tour operators, destinations, hotels)
    entity_keys = ["airline", "operator", "provider", "seller", "destination", "origin",
                   "dest_city", "dest_city_name", "city", "hotel", "name", "tour_name", "product_name"]
    source_entities = set()
    for key, val in source_data.items():
        if isinstance(val, (list, tuple)):
            for item in val:
                if isinstance(item, dict):
                    for ek in entity_keys:
                        if ek in item and item[ek]:
                            source_entities.add(str(item[ek]).lower())
        elif isinstance(val, dict):
            for ek in entity_keys:
                if ek in val and val[ek]:
                    source_entities.add(str(val[ek]).lower())
    
    # Check if source entities appear in content
    content_lower = content.lower()
    for entity in source_entities:
        if len(entity) >= 3 and entity in content_lower:
            found_points.append(f"entity:{entity}")
            source_coverage["entities"] = source_coverage.get("entities", 0) + 1
    
    # 4. Specific numeric metrics (duration, distance, rating, capacity, stops)
    metric_patterns = [
        (r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|minutes?|mins?)\b", "duration"),
        (r"\b(\d+(?:\.\d+)?)\s*(?:km|kilometers?|miles?|mi\b)", "distance"),
        (r"\b(\d+(?:\.\d+)?)\s*(?:stars?|rating|out of 5|/5)\b", "rating"),
        (r"\b(\d+)\s*(?:stops?|layovers?)\b", "stops"),
        (r"\b(\d+)\s*(?:people|guests|passengers|capacity|seats?)\b", "capacity"),
    ]
    
    source_metrics = {}
    for key, val in source_data.items():
        if isinstance(val, (list, tuple)):
            for item in val:
                if isinstance(item, dict):
                    for mk in ["duration", "distance", "rating", "stops", "capacity", "min_duration", "max_duration"]:
                        if mk in item and item[mk] is not None:
                            source_metrics[mk] = str(item[mk])
    
    for pattern, mtype in metric_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            val = match if isinstance(match, str) else match[0]
            for sm_key, sm_val in source_metrics.items():
                try:
                    if abs(float(val) - float(sm_val)) < (2.0 if mtype == "duration" else 0.5):
                        found_points.append(f"{mtype}:{val}")
                        source_coverage[mtype] = source_coverage.get(mtype, 0) + 1
                        break
                except (ValueError, TypeError):
                    pass
    
    # Deduplicate
    unique_points = list(set(found_points))
    count = len(unique_points)
    
    passed = count >= threshold
    
    details = {
        "found_points": unique_points,
        "source_coverage": source_coverage,
        "threshold": threshold
    }
    
    if not passed:
        logger.warning(
            f"[S03] Unique data points gate FAILED: count={count} "
            f"(threshold={threshold}), points={unique_points}"
        )
    else:
        logger.info(
            f"[S03] Unique data points gate PASSED: count={count} "
            f"(threshold={threshold})"
        )
    
    return passed, count, details


# Phase 72 W3 T3.1: Editorial Synthesis Quality Gate
# Validates the deterministic synthesis paragraph appended by writers:
#   (a) length >= 80 chars
#   (b) every numeric token traces back to a unique_data value string
#   (c) at least one source_table name is cited in the paragraph
_NUM_TOKEN_RE = re.compile(r"\d[\d,._]*")

def editorial_synthesis_quality_gate(paragraph: str, unique_data: list) -> Tuple[bool, dict]:
    """Validate a synthesis paragraph against its source unique_data points.

    Args:
        paragraph: The synthesis paragraph text (may be empty).
        unique_data: List of {label, value, unit, source_table} dicts.

    Returns:
        (passed, details). details always contains length / missing_numbers /
        source_found; on failure also a human-readable reason.
    """
    details = {
        "length": len(paragraph or ""),
        "missing_numbers": [],
        "source_found": None,
        "threshold_length": 80,
    }
    if not isinstance(paragraph, str) or len(paragraph.strip()) < 80:
        details["reason"] = f"too short: {len((paragraph or '').strip())} chars (<80)"
        return False, details

    values = []
    tables = []
    for d in (unique_data or []):
        if isinstance(d, dict):
            v = d.get("value")
            if v is not None and str(v).strip():
                values.append(str(v))
            t = d.get("source_table")
            if t:
                tables.append(str(t))
    value_set = set(values)

    # (b) hallucination guard: every numeric token must appear inside some value.
    missing = sorted({tok for tok in _NUM_TOKEN_RE.findall(paragraph)
                      if not any(tok in v for v in value_set)})
    if missing:
        details["missing_numbers"] = missing[:10]
        details["reason"] = f"unverifiable numbers: {missing[:5]}"
        return False, details

    # (c) provenance guard: at least one source_table cited.
    found = next((t for t in tables if t in paragraph), None)
    details["source_found"] = found
    if not found:
        details["reason"] = "no source_table cited"
        return False, details

    return True, details


# ============================================================
# POST-PROCESSING: Content Validation
# ============================================================
BANNED_PHRASES = [
    "plethora", "vibrant", "bustling", "let's dive in", "without further ado",
    "hidden gem", "tapestry", "myriad", "embark on", "rich cultural heritage",
    "culinary delights", "adrenaline junkie", "crystal-clear waters",
    "unforgettable experience", "gastronomic journey",
]

def postprocess_content(content, data_prices=None, blog_id="", slug="", corpus: list = None, source_data: dict = None, front_matter=None, content_type=None):
    """Validate generated content. Returns (content, issues, is_draft).
    is_draft=True means the post should be published as draft.
    
    Phase 70 Wave 1: Added S01 (Uniqueness Ratio), S02 (Structural Similarity),
    S03 (Unique Data Points) quality gates.
    
    Args:
        content: Generated article content (markdown)
        data_prices: List of prices from source data for hallucination check
        blog_id: Blog identifier for logging
        slug: Article slug for logging
        corpus: List of existing article bodies for S01/S02 gates
        source_data: Dict of source data for S03 gate verification
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
        # "comprehensive" → "practical" (대소문자 보존: A→A, a→a)
        "comprehensive": "practical",
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
    # Honest word count: subtract common tips boilerplate and forbidden rephrase duplicates
    _honest = word_count
    # Subtract common tips section words (if present)
    import re as _re
    _tips_m = _re.search(r'## Practical Tips for Travelers.*?(?=\n## |\Z)', content, _re.S)
    if _tips_m:
        _honest -= len(_tips_m.group(0).split()) * 0  # keep tips as honest? Actually tips are boilerplate, subtract 50
        # count common tip sentences
        _common = ["Check the airport's official website", "Arrive with sufficient time", "Verify visa"]
        for _c in _common:
            if _c in content:
                _honest -= 12  # approximate per sentence
    # Forbidden phrases
    for _phrase in ["typically","in its regional context","reflecting local terrain","As a large airport","generally has"]:
        _honest -= content.lower().count(_phrase.lower()) * 4
    # Coordinate rephrase duplicate: sentences containing lat/lng/elev + rephrase
    honest_word_count = max(0, _honest)
    if honest_word_count < 400:
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

    # ── Tour name repetition check (2026-08-22) ──
    # Detect same tour name mentioned 2+ times = likely LLM loop
    # Check both **bold** and plain text tour names (product names from data)
    _tour_names = re.findall(r"\*\*([A-Z][^*]{10,60})\*\*", content)
    # Also detect tour names as plain text (not bolded) — common LLM pattern
    _plain_tours = re.findall(r"(?:^|\n)([A-Z][A-Za-z0-9&,']+(?:\s+[A-Za-z0-9&,']+){3,15}?)(?:\s*(?:priced?|from|at|costs?)\s+\$)", content, re.MULTILINE)
    _all_tours = _tour_names + _plain_tours
    _name_counts = {}
    for _tn in _all_tours:
        _name_norm = _tn.strip().lower()
        _name_counts[_name_norm] = _name_counts.get(_name_norm, 0) + 1
    for _name, _count in _name_counts.items():
        if _count >= 4:
            issues.append(f"[WARNING] Tour repeated {_count}x: '{_name[:50]}' — trimming to max 2 mentions")
            is_draft = True
        elif _count == 3:
            issues.append(f"[INFO] Tour mentioned 3x: '{_name[:50]}'")
        elif _count == 2:
            issues.append(f"[INFO] Tour mentioned twice: '{_name[:50]}'")

    # ── Bold paragraph detection (2026-08-22) ──
    # Flag paragraphs where >80% of text is bold (LLM wrapping entire paragraphs)
    for _bm in re.finditer(r"<strong>(.*?)</strong>", content, re.DOTALL):
        _bold_text = _bm.group(1).strip()
        _bold_wc = len(_bold_text.split())
        if _bold_wc > 15:
            issues.append(f"[WARNING] Long bold block ({_bold_wc} words): '{_bold_text[:60]}...'")
            # Strip bold, keep text
            content = content.replace(f"<strong>{_bold_text}</strong>", _bold_text)

    # Append disclaimer card if not already present
    disclaimer = """
<div class="etap-disclaimer-card">

> **📌 Disclaimer**
>
> Prices, schedules, tour details, flight routes, visa requirements, and all other information on this page are based on data **at the time of writing**. Fares, availability, and policies may change. Please verify current details on the official website before booking.

</div>
"""
    # ── S2: affiliate disclosure — DISABLED (템플릿 레이어로 이동, 2026-08-21)
    # 기존 글 재빌드 1회로 전 페이지 적용하려면 Hugo 파셜(affiliate-disclosure.html)에서
    # 렌더 시 출력해야 함. 본문에 박으면 신규 글만 고쳐져 34/34 미고지 그대로 남음.
    # → 중복 방지 위해 본문 삽입 무력화, 템플릿이 책임짐.

    if "etap-disclaimer-card" not in content:
        content = content + disclaimer

    # ── affiliate rel — DISABLED (render-link.html 훅이 담당, sponsored noopener)
    # 본문에서 직접 <a rel> 박으면 훅과 중복. 훅이 렌더 시 일괄 부여하므로 본문 변환은 제거.

    # ============================================================
    # PHASE 70 WAVE 1: NEW QUALITY GATES INTEGRATION
    # ============================================================
    
    # S01: Uniqueness Ratio Gate
    if corpus and len(corpus) > 0:
        passed, ratio, details = uniqueness_ratio_gate(content, corpus)
        issues.append(f"S01 uniqueness: {ratio:.4f} ({'PASS' if passed else 'FAIL'})")
        if not passed:
            issues.append(f"[S01 FAIL] Uniqueness ratio {ratio:.4f} below threshold {details['threshold']}")
            is_draft = True
    
    # S02: Structural Similarity Gate
    if corpus and len(corpus) > 0:
        passed, sim, details = structural_similarity_gate(content, corpus)
        issues.append(f"S02 structural: {sim:.4f} ({'PASS' if passed else 'FAIL'})")
        if not passed:
            issues.append(f"[S02 FAIL] Structural similarity {sim:.4f} exceeds threshold {details['threshold']}")
            is_draft = True
    
    # S03: Unique Data Points Gate
    if source_data:
        passed, count, details = unique_data_points_gate(content, source_data)
        issues.append(f"S03 data_points: {count} ({'PASS' if passed else 'FAIL'})")
        if not passed:
            issues.append(f"[S03 FAIL] Only {count} unique data points (threshold={details['threshold']})")
            is_draft = True

    # ── PHASE 70 WAVE 3: freshness gate (lastmod-based) ──
    # 동적 콘텐츠(deals/flights/nature/food/finance 등)의 lastmod가 30일 초과 시
    # [MAJOR] stale 이슈 + draft 처리. lastmod 누락 시 skip (pass).
    _DYNAMIC_TYPES = {"deals", "flights", "flight", "nature", "nature_tour",
                      "tour", "tours", "food", "foodtour", "dining", "finance"}
    _lm_raw = None
    if front_matter:
        if isinstance(front_matter, dict):
            _lm_raw = front_matter.get("lastmod") or front_matter.get("date")
        elif isinstance(front_matter, str):
            import re as _re_fm
            _m = _re_fm.search(r"lastmod:\s*([^\n]+)", front_matter)
            if _m:
                _lm_raw = _m.group(1).strip()
            else:
                _m = _re_fm.search(r"date:\s*([^\n]+)", front_matter)
                if _m:
                    _lm_raw = _m.group(1).strip()
    if _lm_raw:
        try:
            from datetime import datetime as _dt
            _lm_dt = _dt.fromisoformat(str(_lm_raw).replace("Z", "+00:00"))
            _stale_days = (_dt.now().astimezone() - _lm_dt).days
            if _stale_days > 30 and (content_type is None or content_type in _DYNAMIC_TYPES):
                issues.append(f"[MAJOR] Content stale: lastmod {_stale_days} days ago")
                is_draft = True
        except Exception:
            pass

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
