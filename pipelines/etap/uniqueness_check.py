"""uniqueness_check.py - Phase 70 Wave 1 uniqueness/differentiation helpers.

Three reusable calculators used by the quality gates:

    calculate_uniqueness_ratio(content, blog_id, slug=None) -> float
        TF-IDF (ngram 1-2) cosine vs the same blog's last-30-days published
        articles. Returns 1.0 on empty corpus (nothing to compare against).

    calculate_structural_similarity(content, blog_id) -> float
        Max cosine similarity of the H2 skeleton (H2 heading + first 50 chars
        of its body) vs the same blog's last-30-days published articles.
        Boilerplate H2s are excluded. Returns 0.0 on empty corpus.

    count_unique_data_points(content, data_prices=None) -> int
        Counts page-specific verifiable data points: $-prices, YYYY-MM-DD
        dates, location/airline names and stop counts found in the content.

DB access is wrapped in try/except and degrades gracefully (returns the
empty-corpus default) so a missing table or DB never crashes a pipeline.
"""

import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except ImportError:  # pragma: no cover - sklearn is a hard requirement
    HAS_SKLEARN = False

logger = logging.getLogger(__name__)

# H2 headings that are shared boilerplate across pages -> ignore in structure compare
BOILERPLATE_H2 = {
    "booking tips",
    "practical tips",
    "travel tips",
    "budget breakdown",
    "getting around",
    "money-saving tips",
}

_CONTENT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "content.db",
)

_LOOKBACK_DAYS = 30


def _fetch_corpus(blog_id: str, exclude_slug: Optional[str] = None) -> List[str]:
    """Return body_md of the same blog's published articles from the last 30 days."""
    if not os.path.exists(_CONTENT_DB):
        return []
    try:
        conn = sqlite3.connect(_CONTENT_DB)
        conn.row_factory = sqlite3.Row
        cutoff = (datetime.now() - timedelta(days=_LOOKBACK_DAYS)).isoformat()
        rows = conn.execute(
            "SELECT body_md, slug FROM articles "
            "WHERE blog_id = ? AND status = 'published' AND created_at >= ?",
            (blog_id, cutoff),
        ).fetchall()
        conn.close()
        corpus = []
        for r in rows:
            slug = r["slug"]
            if exclude_slug and slug == exclude_slug:
                continue
            body = r["body_md"] or ""
            if len(body) > 200:
                corpus.append(body)
        return corpus
    except Exception as exc:  # graceful: never block a publish on DB error
        logger.warning("[uniqueness_check] corpus fetch failed: %s", exc)
        return []


def _clean_text(text: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`]", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _extract_h2_blocks(content: str) -> List[str]:
    """Return list of 'h2_heading + first-50-chars-of-body' strings (boilerplate dropped)."""
    parts = re.split(r"^##\s+(.+)$", content, flags=re.MULTILINE)
    blocks = []
    # parts = [pre, h2_1, body_1, h2_2, body_2, ...]
    for i in range(1, len(parts) - 1, 2):
        heading = parts[i].strip().lower()
        heading = re.sub(r"[^\w\s]", "", heading)
        heading = re.sub(r"\s+", " ", heading).strip()
        if heading in BOILERPLATE_H2:
            continue
        body = parts[i + 1][:50]
        blocks.append(f"{heading} {body}")
    return blocks


def calculate_uniqueness_ratio(content: str, blog_id: str, slug: Optional[str] = None) -> float:
    """1.0 = completely unique. Lower = more overlap with recent published articles."""
    if not HAS_SKLEARN:
        logger.warning("[uniqueness_check] scikit-learn unavailable, returning 1.0")
        return 1.0

    corpus = _fetch_corpus(blog_id, exclude_slug=slug)
    if not corpus:
        return 1.0

    try:
        clean_content = _clean_text(content)
        clean_corpus = [c for c in (_clean_text(c) for c in corpus) if c]
        if not clean_corpus:
            return 1.0

        vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=5000)
        matrix = vectorizer.fit_transform([clean_content] + clean_corpus)
        sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
        max_sim = float(sims.max()) if len(sims) else 0.0
        return 1.0 - max_sim
    except Exception as exc:
        logger.warning("[uniqueness_check] uniqueness ratio error: %s", exc)
        return 1.0


def calculate_structural_similarity(content: str, blog_id: str) -> float:
    """Max H2-skeleton cosine similarity vs recent published articles. 0.0 if none."""
    if not HAS_SKLEARN:
        logger.warning("[uniqueness_check] scikit-learn unavailable, returning 0.0")
        return 0.0

    content_blocks = _extract_h2_blocks(content)
    if not content_blocks:
        return 0.0

    corpus = _fetch_corpus(blog_id)
    corpus_blocks = [_extract_h2_blocks(c) for c in corpus]
    corpus_blocks = [" ".join(b) for b in corpus_blocks if b]
    if not corpus_blocks:
        return 0.0

    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=5000)
        matrix = vectorizer.fit_transform([" ".join(content_blocks)] + corpus_blocks)
        sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
        return float(sims.max()) if len(sims) else 0.0
    except Exception as exc:
        logger.warning("[uniqueness_check] structural similarity error: %s", exc)
        return 0.0


def editorial_cosine_check(paragraph: str, blog_id: str, threshold: float = 0.70):
    """Phase 72 W3 T3.2: synthesis paragraph cosine vs same blog's recent articles.

    Reuses calculate_uniqueness_ratio's TF-IDF machinery (no new similarity
    implementation): ratio = 1 - max_cosine, so cosine = 1 - ratio.
    Passes (True, low cosine) when the paragraph is sufficiently distinct.

    Returns:
        (ok, cosine). Fail-open on any error / empty corpus / empty input.
    """
    if not paragraph or not paragraph.strip():
        return True, 0.0
    try:
        ratio = calculate_uniqueness_ratio(paragraph, blog_id)
        cos = round(max(0.0, min(1.0, 1.0 - ratio)), 4)
        return cos < threshold, cos
    except Exception as exc:  # graceful: warn-only gate must never block
        logger.warning("[uniqueness_check] editorial_cosine_check error: %s", exc)
        return True, 0.0


_AIRLINES = {
    "air france", "delta", "united", "american airlines", "lufthansa", "emirates",
    "qatar airways", "singapore airlines", "british airways", "korean air", "asiana",
    "ana", "japan airlines", "turkish airlines", "etihad", "cathay pacific",
    "klm", "air canada", "qantas", "thaiairways", "thai airways",
}

_LOCATION_RE = re.compile(r"\b(?:Paris|London|Tokyo|New York|Sydney|Rome|Berlin|Barcelona|"
                          r"Seoul|Bangkok|Singapore|Dubai|Istanbul|Madrid|Vienna|Amsterdam|"
                          r"Prague|Lisbon|Athens|Oslo|Stockholm|Helsinki|Copenhagen|"
                          r"Los Angeles|Chicago|San Francisco|Toronto|Vancouver|Frankfurt|"
                          r"Munich|Zurich|Geneva|Milan|Venice|Florence|Dublin|Edinburgh)\b")


def count_unique_data_points(content: str, data_prices: Optional[List[float]] = None) -> int:
    """Count page-specific verifiable data points present in the content."""
    if not content:
        return 0

    points = set()

    # $-prices
    for m in re.finditer(r"\$(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)", content):
        points.add(f"price:{m.group(1)}")

    # ISO dates YYYY-MM-DD
    for m in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", content):
        points.add(f"date:{m.group(0)}")

    # stop counts
    for m in re.finditer(r"\b(\d+)\s*(?:stops?|layovers?)\b", content, re.IGNORECASE):
        points.add(f"stops:{m.group(1)}")

    # airline names
    lower = content.lower()
    for airline in _AIRLINES:
        if airline in lower:
            points.add(f"airline:{airline}")

    # location names
    for m in _LOCATION_RE.finditer(content):
        points.add(f"location:{m.group(0)}")

    # prices from source data (if provided) that appear in content
    if data_prices:
        text_prices = {m.group(1).replace(",", "") for m in
                       re.finditer(r"\$(\d{1,3}(?:,\d{3})*|\d+)", content)}
        for dp in data_prices:
            for tp in text_prices:
                try:
                    if abs(float(tp) - float(dp)) <= 2.0:
                        points.add(f"src_price:{dp}")
                        break
                except (ValueError, TypeError):
                    pass

    return len(points)
