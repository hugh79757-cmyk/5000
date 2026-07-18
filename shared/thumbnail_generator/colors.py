"""
Blog-specific and category-based color palettes for the editorial thumbnail generator.

Each blog gets a primary brand identity color derived from its existing PIL thumbnail heritage.
Category-level accent colors are preserved from the original pipelines.
"""

import logging

logger = logging.getLogger(__name__)

# ── Blog-level brand palettes ──────────────────────────────────────────────

BLOG_PALETTES = {
    "senior": {
        "primary": "#3B1E54",      # Deep plum — dignity/wisdom (senior welfare identity)
        "secondary": "#6D28D9",    # Violet — contrast accent
        "badge_bg": "rgba(255,255,255,0.2)",
        "brand": "senior-blog",
        "site_bar": "SENIOR.INFORMATIONHOT.KR",
        "categories": {
            "의료지원":     "#5B2C6F",   # Muted plum — trust/care
            "돌봄서비스":   "#0D6B5E",   # Muted teal — calm/healing
            "교통복지":     "#6B5D2E",   # Warm olive — earthy/mobility
            "생활지원":     "#4C2D7A",   # Purple-violet — supportive
            "연금생활지원": "#8B2E3E",   # Deep burgundy — serious/financial
            "일자리금융":   "#2D4C7A",   # Deep blue — finance/trust
            "문화여가":     "#7A2D6B",   # Rose-purple — creative/vibrant
        },
    },
    "stock": {
        "primary": "#1e3a5f",      # Navy — finance/trust
        "secondary": "#3b82f6",    # Blue
        "badge_bg": "rgba(255,255,255,0.2)",
        "brand": "stock-blog",
        "site_bar": "CANDLETREND.KR",
        "categories": {
            "공시분석":     "#1e40af",
            "실적분석":     "#0f766e",
            "배당분석":     "#b91c1c",
            "IPO분석":      "#6b21a8",
            "ETF분석":      "#1d4ed8",
            "시장분석":     "#4b5563",
        },
    },
    "rap": {
        "primary": "#2563eb",      # Blue — real estate
        "secondary": "#2ecc71",    # Green
        "badge_bg": "rgba(255,255,255,0.2)",
        "brand": "rap-blog",
        "site_bar": "APT.INFORMATIONHOT.KR",
        "categories": {
            "부동산":       "#2563eb",
            "실거래가":     "#3b82f6",
            "청약정보":     "#16a34a",
            "임대주택":     "#7c3aed",
            "부동산세금":   "#dc2626",
            "전월세":       "#059669",
            "브랜드아파트": "#8b5cf6",
        },
    },
    "kuta": {
        "primary": "#e11d48",      # Rose — lifestyle/commerce
        "secondary": "#f43f5e",    # Rose red
        "badge_bg": "rgba(255,255,255,0.2)",
        "brand": "kuta-blog",
        "site_bar": "KUTALOG.COM",
        "categories": {},
    },
    "rotcha": {
        "primary": "#8b5cf6",      # Violet — general/creative
        "secondary": "#a78bfa",    # Soft violet
        "badge_bg": "rgba(255,255,255,0.2)",
        "brand": "rotcha-blog",
        "site_bar": "ROTCHA.KR",
        "categories": {},
    },
    "informationhot": {
        "primary": "#dc2626",      # Red — news/hot topics
        "secondary": "#f97316",    # Orange
        "badge_bg": "rgba(255,255,255,0.15)",
        "brand": "informationhot",
        "site_bar": "INFORMATIONHOT.KR",
        # Category accent colors from the informationhot generator
        "categories": {
            "자격증시험": "#2563eb",
            "스포츠":     "#dc2626",
            "생활정보":   "#059669",
            "금융":       "#1d4ed8",
            "여행":       "#0d9488",
            "세금":       "#475569",
            "최신뉴스":   "#dc2626",
            "경제":       "#d97706",
            "건강":       "#e11d48",
            "정부지원금": "#7c3aed",
            "부동산":     "#ea580c",
            "투자":       "#059669",
            "복지":       "#ca8a04",
            "교육":       "#2563eb",
            "IT":         "#2563eb",
            "기술":       "#2563eb",
            "재테크":     "#d97706",
        },
    },
    "techpawz": {
        "primary": "#6366f1",      # Indigo — tech
        "secondary": "#818cf8",    # Soft indigo
        "badge_bg": "rgba(255,255,255,0.2)",
        "brand": "techpawz",
        "site_bar": "TECHPAWZ.COM",
        "categories": {},
    },
    "issue-techpawz": {
        "primary": "#f59e0b",      # Amber — issues/opinion
        "secondary": "#fbbf24",    # Gold
        "badge_bg": "rgba(255,255,255,0.2)",
        "brand": "issue-techpawz",
        "site_bar": "ISSUE.TECHPAWZ.COM",
        "categories": {},
    },
    "biz.techpawz": {
        "primary": "#059669",      # Emerald — business
        "secondary": "#10b981",    # Green
        "badge_bg": "rgba(255,255,255,0.2)",
        "brand": "biz-techpawz",
        "site_bar": "BIZ.TECHPAWZ.COM",
        "categories": {},
    },
    "info.techpawz": {
        "primary": "#0284c7",      # Sky blue — information
        "secondary": "#38bdf8",    # Light blue
        "badge_bg": "rgba(255,255,255,0.2)",
        "brand": "info-techpawz",
        "site_bar": "INFO.TECHPAWZ.COM",
        "categories": {},
    },
}

DEFAULT_PALETTE = {
    "primary": "#4f46e5",
    "secondary": "#818cf8",
    "badge_bg": "rgba(255,255,255,0.2)",
    "brand": "default",
    "site_bar": "",
    "categories": {},
}


def get_blog_palette(site_id: str) -> dict:
    """Get the color palette for a blog. Falls back to default if unknown."""
    if site_id and site_id in BLOG_PALETTES:
        return BLOG_PALETTES[site_id]
    logger.warning(f"[ThumbColors] Unknown site_id='{site_id}', using default")
    return DEFAULT_PALETTE


def get_accent_for_category(site_id: str, category: str) -> str:
    """
    Get the accent color for a specific category within a blog.
    Falls back to blog primary color if no category match.
    """
    palette = get_blog_palette(site_id)
    if category and palette["categories"]:
        cat = category.strip()
        if cat in palette["categories"]:
            return palette["categories"][cat]
        # Partial match
        for key, color in palette["categories"].items():
            if key in cat or cat in key:
                return color
    return palette["primary"]


def list_supported_sites() -> list[str]:
    return list(BLOG_PALETTES.keys())
