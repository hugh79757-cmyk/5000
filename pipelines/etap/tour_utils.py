"""tour_utils.py - Viator 투어 기반 writer 공통 유틸리티

모든 Viator writer가 공유:
- fetch_city_meta(): 도시 메타데이터
- deduplicate_tours(): 중복 투어 그룹핑
- build_city_context(): GPT 프롬프트용 도시 컨텍스트
"""
import os, sqlite3, re, logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_price(val):
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except Exception:
        return 0


def fetch_city_meta(city):
    """viator_destinations에서 통화, 시간대, 언어, 좌표 가져오기"""
    conn = _get_db()
    row = conn.execute("""
        SELECT currency_code, timezone, country_calling_code, languages,
               latitude, longitude
        FROM viator_destinations
        WHERE name = ? AND type = 'CITY'
        LIMIT 1
    """, (city,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def deduplicate_tours(tours, similarity_threshold=0.65):
    """유사한 투어를 그룹핑하고 각 그룹에서 대표 1개만 선택.
    기준: $10 이상 + 이미지 있는 것 우선 + 최저가."""
    if not tours:
        return []

    for t in tours:
        t["_clean_name"] = re.sub(r"^Save [\d.]+%!\s*", "", t.get("product_name", "")).strip()

    groups = []
    used = set()

    for i, t in enumerate(tours):
        if i in used:
            continue
        group = [t]
        used.add(i)
        for j in range(i + 1, len(tours)):
            if j in used:
                continue
            ratio = SequenceMatcher(
                None, t["_clean_name"].lower(), tours[j]["_clean_name"].lower()
            ).ratio()
            if ratio > similarity_threshold:
                group.append(tours[j])
                used.add(j)
        groups.append(group)

    result = []
    for group in groups:
        valid = [t for t in group if _safe_price(t.get("price")) >= 10]
        if not valid:
            valid = group
        with_img = [t for t in valid if t.get("image_url")]
        pool = with_img if with_img else valid
        best = sorted(pool, key=lambda x: _safe_price(x.get("price")))[0]
        best["_group_size"] = len(group)
        best["_group_price_range"] = (
            min(_safe_price(t.get("price")) for t in group),
            max(_safe_price(t.get("price")) for t in group),
        )
        result.append(best)

    logger.info(f"[dedup] {len(tours)} tours -> {len(result)} after dedup ({len(tours) - len(result)} duplicates removed)")
    return result


def build_city_context(city, city_meta):
    """GPT 프롬프트에 삽입할 도시 컨텍스트 문자열"""
    currency = city_meta.get("currency_code", "USD")
    tz = city_meta.get("timezone", "")
    lang = city_meta.get("languages", "")
    lat = city_meta.get("latitude", "")
    lon = city_meta.get("longitude", "")

    ctx = f"CITY CONTEXT:\n"
    ctx += f"City: {city}\n"
    ctx += f"Local currency: {currency}\n"
    ctx += f"Timezone: {tz}\n"
    ctx += f"Languages: {lang}\n"
    ctx += f"Coordinates: {lat}, {lon}\n"
    return ctx


def build_picks_summary(tours, city_meta, budget_max=50, mid_max=150, picks_per_tier=3):
    """가격대별 TOP N 큐레이션 요약 생성"""
    currency = city_meta.get("currency_code", "USD")

    budget = [t for t in tours if 10 <= _safe_price(t.get("price")) < budget_max]
    mid = [t for t in tours if budget_max <= _safe_price(t.get("price")) <= mid_max]
    premium = [t for t in tours if _safe_price(t.get("price")) > mid_max]

    picks = {
        "budget": sorted(budget, key=lambda x: _safe_price(x.get("price")))[:picks_per_tier],
        "mid_range": sorted(mid, key=lambda x: _safe_price(x.get("price")))[:picks_per_tier],
        "premium": sorted(premium, key=lambda x: -_safe_price(x.get("price")))[:picks_per_tier],
    }

    all_prices = [_safe_price(t.get("price")) for t in tours if _safe_price(t.get("price")) > 0]
    min_p = min(all_prices) if all_prices else 0
    max_p = max(all_prices) if all_prices else 0

    categories = {}
    for t in tours:
        cat = t.get("category", "Other")
        categories[cat] = categories.get(cat, 0) + 1

    summary = f"TOUR DATA (deduplicated, {len(tours)} unique tours):\n"
    summary += "Categories: " + ", ".join(f"{c} ({n})" for c, n in sorted(categories.items(), key=lambda x: -x[1])) + "\n"
    summary += f"Price range: ${min_p:.0f} - ${max_p:.0f} {currency}\n\n"

    for label, items in picks.items():
        if items:
            summary += f"[{label.upper()} - TOP {len(items)} PICKS]\n"
            for t in items:
                name = re.sub(r"^Save [\d.]+%!\s*", "", t.get("product_name", ""))
                price = _safe_price(t.get("price"))
                cat = t.get("category", "")
                gs = t.get("_group_size", 1)
                plo, phi = t.get("_group_price_range", (price, price))
                desc = (t.get("description", "") or "")[:120]
                summary += f"- {name} | ${price:.0f} {currency} | {cat}"
                if gs > 1:
                    summary += f" | {gs} similar tours (${plo:.0f}-${phi:.0f})"
                summary += f"\n  Brief: {desc}\n"
            summary += "\n"

    return summary, picks
