"""relevance_scorer.py — 상품 적합도 점수 및 주간 off-topic 리포트"""

import sqlite3
from datetime import datetime, timedelta

RELEVANCE_CONFIG: dict[str, dict] = {
    "default": {"threshold": 0.75, "min_keyword_matches": 2},
    "laptop-hugo": {"threshold": 0.85},
    "health-hugo": {"threshold": 0.65},
    "baby-hugo": {"threshold": 0.85},
    "beauty-hugo": {"threshold": 0.55},
    "interior-hugo": {"threshold": 0.65},
    "camping-hugo": {"threshold": 0.65},
}

OFFTOPIC_THRESHOLD = 0.20


def score_product(product_name: str, category_name: str, allowed_keywords: list[str]) -> float:
    combined = (product_name + " " + category_name).lower()
    count = sum(1 for kw in allowed_keywords if kw.lower() in combined)
    min_matches = RELEVANCE_CONFIG["default"]["min_keyword_matches"]
    return min(count / min_matches, 1.0)


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
        "laptop-hugo", "appliance-hugo", "interior-hugo",
        "baby-hugo", "fitness-hugo", "health-hugo",
        "pet-hugo", "kitchen-hugo", "beauty-hugo", "camping-hugo",
    ]
    messages = []
    for blog_id in blogs:
        msg = weekly_offtopic_report(db_path, blog_id)
        if msg:
            messages.append(msg)
    if not messages:
        return None
    return "\n\n".join(messages)
