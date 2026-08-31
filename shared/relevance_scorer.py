"""relevance_scorer.py — 상품 적합도 점수 및 주간 off-topic 리포트"""

import sqlite3
from datetime import datetime, timedelta

RELEVANCE_CONFIG: dict[str, dict] = {
    "default": {"threshold": 0.75, "min_keyword_matches": 2},
    "laptop-hugo": {"threshold": 0.65},
    "health-hugo": {"threshold": 0.55},  # Phase72: 0.65->0.55
    "baby-hugo": {"threshold": 0.70},
    "beauty-hugo": {"threshold": 0.55},
    "interior-hugo": {"threshold": 0.55},
    "camping-hugo": {"threshold": 0.55},      # Phase 10: lowered from 0.65
    "kitchen-hugo": {"threshold": 0.50},
    "pet-hugo": {"threshold": 0.55},
    "appliance-hugo": {"threshold": 0.65},    # Phase 10: NEW — was using default 0.75
    "golf-hugo": {"threshold": 0.50},         # golf products use brand names, default 0.75 blocks all
    "bike-hugo": {"threshold": 0.50},         # bike compound-keyword products carry 1 allowed token -> default 0.75 blocks all (same as golf)
    "car-hugo": {"threshold": 0.50},          # Phase 72: car 12 keywords strict 0.75 blocks remaining 타이어/냉장고 (avg 0.67/0.33)
    "fitness-hugo": {"threshold": 0.50},      # P14 irrelevant_products — 0.55→0.50 (kin/kitchen 동조)
    "best-kitchen-hugo": {"threshold": 0.50},
    "best-beauty-hugo": {"threshold": 0.55},
    "best-electronics-hugo": {"threshold": 0.10},
    "best-sports-hugo": {"threshold": 0.10},
    "best-toys-hugo": {"threshold": 0.10},
    "best-stationery-hugo": {"threshold": 0.10},
    "best-pet-supplies-hugo": {"threshold": 0.10},
    "best-books-hugo": {"threshold": 0.50},
    "best-unisex-clothing-hugo": {"threshold": 0.10},
}

OFFTOPIC_THRESHOLD = 0.20


def score_product(product_name: str, category_name: str, allowed_keywords: list[str]) -> float:
    import re as _re
    combined = (product_name + " " + category_name).lower()
    combined_nospace = _re.sub(r'\s+', '', combined)
    def _kw_match(kw: str) -> bool:
        kl = kw.lower()
        kl_ns = _re.sub(r'\s+', '', kl)
        return kl in combined or kl_ns in combined_nospace
    count = sum(1 for kw in allowed_keywords if _kw_match(kw))
    min_matches = RELEVANCE_CONFIG["default"]["min_keyword_matches"]
    score = min(count / min_matches, 1.0)
    # brand 키워드 보너스 — 브랜드명이 product_name에 있으면 +0.15
    BRAND_KEYWORDS = {
        "lg", "삼성", "samsung", "samsung electronics",
        "레노버", "lenovo", "asus", "에이수스", "hp", "dell", "델",
        "msi", "apple", "애플", "맥북", "macbook",
        "그램", "gram", "갤럭시북", "galaxy book",
        "씽크패드", "thinkpad", "비보북", "vivobook", "젠북", "zenbook",
        "오멘", "omen", "빅터스", "victus", "프레데터", "predator",
        # 커피 브랜드 보너스 (kitchen 커피머신 관련성 보정)
        "드롱기", "delonghi", "필립스", "philips", "네스프레소", "nespresso",
        "리큅", "locknlock", "쿠첸", "cuchen", "위즈웰", "wizwell",
    }
    name_lower = product_name.lower()
    if any(b in name_lower for b in BRAND_KEYWORDS):
        score = min(score + 0.15, 1.0)
    return score


def score_products(products: list[dict], blog_id: str) -> dict:
    from pipelines.curation.pipeline import CATEGORY_FILTERS

    filters = CATEGORY_FILTERS.get(blog_id)
    allowed = filters["allowed"] if filters else []
    scores = [score_product(p.get("product_name", ""), p.get("category_name", ""), allowed) for p in products]
    threshold = get_threshold(blog_id)
    return {
        "avg": sum(scores) / len(scores) if scores else 0.0,
        "min": min(scores) if scores else 0.0,
        "scores": scores,
        "blog_id": blog_id,
        "threshold": threshold,
    }


def get_threshold(blog_id: str) -> float:
    return RELEVANCE_CONFIG.get(blog_id, {}).get("threshold", 0.75)


def _get_recent_avg_score(db_path: str, blog_id: str, limit: int = 10) -> float | None:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT avg_relevance_score FROM publish_log"
        " WHERE blog_id=? AND validation_passed=1"
        " ORDER BY published_at DESC LIMIT ?",
        (blog_id, limit),
    ).fetchall()
    conn.close()
    if not rows:
        return None
    scores = [r[0] for r in rows if r[0] is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)


def get_adaptive_threshold(db_path: str, blog_id: str, base_threshold: float | None = None) -> float:
    """최근 성공 글의 평균 점수를 기반으로 임계값을 동적으로 조정

    - 최근 10개 성공 글의 평균 점수가 있으면 base_threshold와 평균*0.95 중 낮은 값 사용
    - 없으면 base_threshold 그대로 반환
    """
    if base_threshold is None:
        base_threshold = get_threshold(blog_id)
    recent_avg = _get_recent_avg_score(db_path, blog_id, limit=10)
    if recent_avg is None:
        return base_threshold
    return min(base_threshold, recent_avg * 0.95)


def passes_gate(scores: dict) -> tuple[bool, str]:
    if scores["avg"] >= scores["threshold"]:
        return (True, "")
    return (False, f"low_relevance: avg={scores['avg']:.2f} < threshold={scores['threshold']:.2f}")


def migrate_publish_log(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("ALTER TABLE publish_log ADD COLUMN avg_relevance_score REAL")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE publish_log ADD COLUMN min_relevance_score REAL")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE publish_log ADD COLUMN product_count INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE publish_log ADD COLUMN filtered_count INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE publish_log ADD COLUMN validation_passed INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def log_publish_audit(db_path: str, blog_id: str, keyword: str, title: str, slug: str, scores: dict, passed: bool) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO publish_log (blog_id, keyword, title, slug, published_at, avg_relevance_score, min_relevance_score, product_count, filtered_count, validation_passed) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (blog_id, keyword, title, slug, datetime.utcnow().isoformat(), scores["avg"], scores["min"], len(scores["scores"]), len(scores["scores"]), 1 if passed else 0),
    )
    conn.commit()
    conn.close()


def get_last_week_range() -> tuple[str, str]:
    end = datetime.utcnow()
    start = end - timedelta(days=7)
    return (start.isoformat(), end.isoformat())


def weekly_offtopic_report(db_path: str, blog_id: str) -> str | None:
    threshold = get_threshold(blog_id)
    start_date, end_date = get_last_week_range()
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT avg_relevance_score FROM publish_log WHERE blog_id=? AND published_at BETWEEN ? AND ?",
        (blog_id, start_date, end_date),
    ).fetchall()
    conn.close()
    if not rows:
        return None
    total = len(rows)
    offtopic_count = sum(1 for r in rows if r[0] is not None and r[0] < threshold)
    rate = (offtopic_count / total) * 100
    if rate <= OFFTOPIC_THRESHOLD * 100:
        return None
    return (
        f"📊 [주간 리포트] off-topic 비율 경고\n"
        f"블로그: {blog_id}\n"
        f"기간: {start_date} ~ {end_date}\n"
        f"발행: {total}건\n"
        f"off-topic: {offtopic_count}건 ({rate:.1f}%)\n"
        f"임계값 초과: {rate:.0f}% > 20%\n"
        f"상세: per-keyword with avg scores"
    )


def run_all_weekly_reports(db_path: str) -> str | None:
    blogs = [
        "appliance-hugo", "baby-hugo", "fitness-hugo", "interior-hugo",
        "laptop-hugo", "health-hugo", "pet-hugo", "kitchen-hugo",
        "beauty-hugo", "camping-hugo", "massage-hugo", "car-hugo",
        "homeappliance-hugo", "golf-hugo", "bike-hugo",
    ]
    messages = []
    for blog_id in blogs:
        msg = weekly_offtopic_report(db_path, blog_id)
        if msg:
            messages.append(msg)
    if not messages:
        return None
    return "\n\n".join(messages)
