"""RAP (Real estate Auto Publisher) pipeline — GAP 구조 기반"""
import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from shared.telegram_notifier import send_error as tg_error
except ImportError:
    tg_error = lambda *a, **k: None

GAP_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "gap.db")

# 부동산 카테고리 목록
RAP_CATEGORIES = ("금융/부동산",)

# 키워드 → 전략 매핑
TRADE_PATTERNS = ["실거래", "매매", "시세", "집값", "아파트", "공시지가", "빌라", "오피스텔"]
SUB_PATTERNS = ["청약", "분양", "LH", "행복주택", "임대", "전세"]

WP_CATEGORY_MAP = {
    "부동산": 150,
    "실거래가": 150,
    "청약정보": 149,
    "임대주택": 149,
}


def _pick_keyword(blog_id):
    """gap.db에서 부동산 키워드 선택 (GAP _pick_keyword 방식)"""
    conn = sqlite3.connect(GAP_DB_PATH)
    try:
        # 최근 7일 발행된 키워드 제외
        published = set()
        try:
            rows = conn.execute(
                "SELECT keyword FROM publish_log WHERE site_id=? AND published_at > datetime('now', '-7 days')",
                (blog_id,)
            ).fetchall()
            published = {r[0] for r in rows}
        except sqlite3.OperationalError:
            pass  # publish_log 테이블 없을 수 있음

        placeholders = ",".join("?" * len(RAP_CATEGORIES))
        rows = conn.execute(f"""
            SELECT keyword, category FROM keywords
            WHERE status='active' AND category IN ({placeholders})
            ORDER BY use_count ASC, last_used_at ASC NULLS FIRST
        """, RAP_CATEGORIES).fetchall()

        available = [(r[0], r[1]) for r in rows if r[0] not in published]
        if not available:
            logger.warning(f"{blog_id}: 사용 가능한 부동산 키워드 없음")
            return None, None

        keyword, category = available[0]
        conn.execute(
            "UPDATE keywords SET use_count = use_count + 1, last_used_at = ? WHERE keyword = ?",
            (datetime.now().isoformat(), keyword)
        )
        conn.commit()
        logger.info(f"{blog_id}: 키워드 선택 → {keyword} ({category})")
        return keyword, category
    finally:
        conn.close()


def _pick_strategy(keyword):
    """키워드로부터 전략 결정"""
    for p in SUB_PATTERNS:
        if p in keyword:
            return "subscription"
    for p in TRADE_PATTERNS:
        if p in keyword:
            return "trade"
    return "trade"


def run(blog_cfg):
    """dispatcher에서 호출하는 통일 인터페이스"""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))
    from shared.content_store import init_db, get_today_count
    from shared.publisher import publish
    from pipelines.rap.fetcher import fetch_apt_trade, fetch_subscription_info, find_lawd_cd, REGION_CD_MAP
    from pipelines.rap.writer import generate_trade_article, generate_subscription_article
    from pipelines.rap.thumbnail import upload_thumbnail

    blog_id = blog_cfg["id"]
    logger.info(f"RAP pipeline: {blog_id}")

    init_db()
    today_count = get_today_count(blog_id)
    daily_quota = blog_cfg.get("daily_quota", 5)
    if today_count >= daily_quota:
        logger.info(f"{blog_id} quota met: {today_count}/{daily_quota}")
        return {"success": False, "reason": "quota_met"}

    # 키워드 선택
    keyword, kw_category = _pick_keyword(blog_id)
    if not keyword:
        return {"success": False, "reason": "no_keyword"}

    strategy = _pick_strategy(keyword)
    logger.info(f"{blog_id}: keyword={keyword}, strategy={strategy}")

    article = None
    data_source = ""

    # ─── 실거래가 전략 ───
    if strategy == "trade":
        lawd_cd, city, district = find_lawd_cd(keyword)
        if not lawd_cd:
            lawd_cd, city, district = "11680", "서울", "강남구"
            logger.info(f"법정동코드 미매칭, 기본값: {city} {district}")

        trades = fetch_apt_trade(lawd_cd, rows=30)
        if not trades:
            from dateutil.relativedelta import relativedelta
            prev_ym = (datetime.now() - relativedelta(months=1)).strftime("%Y%m")
            trades = fetch_apt_trade(lawd_cd, deal_ymd=prev_ym, rows=30)

        if not trades:
            tg_error(blog_id, "fetcher", f"실거래가 0건: {keyword}")
            return {"success": False, "reason": "no_trade_data"}

        article = generate_trade_article(keyword, trades, region_info={"city": city, "district": district})
        data_source = "molit_trade_api"

    # ─── 청약 전략 ───
    elif strategy == "subscription":
        region_cd = None
        for region, code in REGION_CD_MAP.items():
            if region in keyword:
                region_cd = code
                break

        subs = fetch_subscription_info(region_cd=region_cd, page_size=10)
        if not subs:
            tg_error(blog_id, "fetcher", f"청약 공고 0건: {keyword}")
            return {"success": False, "reason": "no_subscription_data"}

        article = generate_subscription_article(keyword, subs)
        data_source = "applyhome_api"

    if not article:
        return {"success": False, "reason": "write_failed"}

    # 썸네일
    thumb_url = upload_thumbnail(article["title"], article.get("category", "부동산"))

    # WordPress용 카테고리 ID
    wp_category = WP_CATEGORY_MAP.get(article.get("category", ""), 150)

    # 내부링크/CTA 삽입 (WordPress인 경우)
    body_html = None
    if blog_cfg.get("platform") == "wordpress":
        try:
            import markdown
            body_html = markdown.markdown(article["body_md"], extensions=["tables", "fenced_code"])
            from pipelines.gap.internal_links import process_gap_content
            body_html = process_gap_content(body_html, kw_category)
        except Exception as e:
            logger.warning(f"내부링크 삽입 실패: {e}")

    # 발행
    result = publish(
        blog_id=blog_id,
        title=article["title"],
        body_md=article["body_md"],
        body_html=body_html,
        blog_cfg=blog_cfg,
        category=article.get("category", "부동산"),
        tags=article.get("tags", ""),
        data_source=data_source,
        source_id=keyword,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        thumbnail_url=thumb_url,
        wp_category=wp_category,
    )

    if result and result.get("success"):
        logger.info(f"RAP 발행 성공: {article['title']}")
    else:
        reason = (result or {}).get("reason", "publish_failed")
        tg_error(blog_id, "publish", f"{keyword}: {reason}")

    if result and result.get("deploy_error"):
        tg_error(blog_id, "deploy", result["deploy_error"][:300])

    return result or {"success": False, "reason": "publish_failed"}
