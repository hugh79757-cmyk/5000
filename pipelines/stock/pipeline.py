import os
import random
import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from shared.telegram_notifier import send_error as tg_error
except ImportError:
    tg_error = lambda *a, **k: None

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "stock.db")
EVERGREEN_TYPES = ["dividend_ranking", "etf_comparison", "sector_analysis", "ipo_schedule", "cma_savings"]


def run(blog_cfg):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"), override=True)

    blog_id = blog_cfg["id"]
    logger.info(f"STAP pipeline: {blog_id}")

    from shared.content_store import init_db, get_today_count
    from shared.publisher import publish
    from pipelines.stock.fetcher import fetch_recent_disclosure, fetch_company_info, fetch_financial_summary, get_listed_corps
    from pipelines.stock.writer import generate_disclosure_article, generate_evergreen_article

    init_db()
    today_count = get_today_count(blog_id)
    quota = blog_cfg.get("daily_quota", 5)
    if today_count >= quota:
        logger.info(f"{blog_id}: 오늘 발행 완료 ({today_count}/{quota})")
        return {"success": False, "reason": "quota_met"}

    conn = sqlite3.connect(DB_PATH)
    strategy = _pick_strategy(conn, blog_id)
    logger.info(f"{blog_id}: 전략 = {strategy}")

    result = None

    if strategy == "disclosure":
        disclosures = fetch_recent_disclosure(days=3, page_count=30)
        disclosures = _filter_unpublished(conn, blog_id, disclosures)
        if disclosures:
            disc = disclosures[0]
            corp_code = disc.get("corp_code", "")
            company = fetch_company_info(corp_code) if corp_code else None
            financials = fetch_financial_summary(corp_code) if corp_code else []
            article = generate_disclosure_article(disc, company, financials)
            if article.get("title") and article.get("body_md"):
                result = publish(
                    blog_id=blog_id,
                    title=article["title"],
                    body_md=article["body_md"],
                    category=article.get("category", "공시분석"),
                    tags=article.get("tags", ""),
                    data_source="dart_disclosure",
                    source_id=disc.get("rcept_no", ""),
                    model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                )
                if result and result.get("success"):
                    _record_publish(conn, blog_id, disc)
    else:
        topic_type = strategy
        corps = get_listed_corps(limit=50)
        sample = random.sample(corps, min(5, len(corps)))
        article = generate_evergreen_article(topic_type, corp_data=sample)
        if article.get("title") and article.get("body_md"):
            result = publish(
                blog_id=blog_id,
                title=article["title"],
                body_md=article["body_md"],
                category=article.get("category", "시장분석"),
                tags=article.get("tags", ""),
                data_source=f"evergreen_{topic_type}",
                source_id="",
                model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            )

    conn.close()
    if result and result.get("success") and result.get("deploy_error"):
        tg_error(blog_id, "deploy", result["deploy_error"][:300])
    if result and not result.get("success"):
        tg_error(blog_id, "pipeline", result.get("reason", "unknown"))
    return result or {"success": False, "reason": "no_content"}


def _pick_strategy(conn, blog_id):
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    today_disc = c.execute(
        "SELECT COUNT(*) FROM publish_history WHERE site_id=? AND date(published_at)=? AND post_type='disclosure'",
        (blog_id, today)
    ).fetchone()[0]

    if today_disc < 2:
        return "disclosure"
    return random.choice(EVERGREEN_TYPES)


def _filter_unpublished(conn, blog_id, disclosures):
    c = conn.cursor()
    published = {r[0] for r in c.execute(
        "SELECT corp_code FROM publish_history WHERE site_id=? AND post_type='disclosure' AND published_at > datetime('now', '-7 days')",
        (blog_id,)
    ).fetchall()}
    return [d for d in disclosures if d.get("corp_code") not in published]


def _record_publish(conn, blog_id, disclosure):
    conn.execute(
        "INSERT INTO publish_history (corp_code, stock_code, post_type, title, site_id) VALUES (?,?,?,?,?)",
        (disclosure.get("corp_code", ""), disclosure.get("stock_code", ""), "disclosure", disclosure.get("report_nm", ""), blog_id)
    )
    conn.commit()
