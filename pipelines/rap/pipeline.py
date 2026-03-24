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

# blog_id별 키워드 필터 패턴
BLOG_KEYWORD_FILTER = {
    "rap-hugo":  ["아파트", "매매", "시세", "실거래", "집값", "공시지가", "빌라", "오피스텔",
                  "은마", "헬리오", "파크리오", "래미안", "자이", "힐스테이트", "푸르지오",
                  "재건축", "재개발", "부동산", "드림타운", "주택", "레지던스", "하우스",
                  "단지", "미소지움", "아르티스", "트인시아", "펠루시드", "팰루시드",
                  "S클래스", "브라이튼", "에테르노", "디아이엘", "하이니티", "비스타",
                  "건설", "냉난방", "전원주택", "모아타운", "아페르", "라엘"],
    "rap2-hugo": ["청약", "분양", "LH", "행복주택", "임대주택", "청년주택", "청년안심",
                  "국민임대", "영구임대", "매입임대", "신혼희망"],
    "rap3-hugo": ["양도", "취득세", "상속세", "증여세", "세금", "과세", "공시지가", "재산세",
                  "종부세", "종합부동산세", "절세", "세율", "면제"],
    "rap4-hugo": ["전세", "월세", "임대", "보증금", "임대차", "전월세", "반전세",
                  "보증보험", "전세사기", "확정일자", "임차인", "계약갱신"],
    "rap5-hugo": ["헬리오시티", "힐스테이트", "래미안", "자이", "푸르지오", "아크로", "파크리오",
                  "더샵", "르엘", "롯데캐슬", "SK뷰", "아이파크", "e편한세상",
                  "디에이치", "트리우스", "브랜드", "풍림", "드파인", "브르넨",
                  "라브르", "원펜타스", "디디하우스"],
}

# blog_id별 강제 전략
BLOG_STRATEGY = {
    "rap-hugo":  "trade",
    "rap2-hugo": "subscription",
    "rap3-hugo": "trade",
    "rap4-hugo": "trade",
    "rap5-hugo": "trade",
}

WP_CATEGORY_MAP = {
    "부동산": 150,
    "실거래가": 150,
    "청약정보": 149,
    "임대주택": 149,
}


def _pick_keyword(blog_id):
    """blog_id에 맞는 부동산 키워드 선택"""
    conn = sqlite3.connect(GAP_DB_PATH)
    try:
        patterns = BLOG_KEYWORD_FILTER.get(blog_id, [])
        rows = conn.execute(
            "SELECT keyword, category FROM keywords "
            "WHERE category = '금융/부동산' AND status = 'active' "
            "ORDER BY use_count ASC, last_used_at ASC NULLS FIRST "
            "LIMIT 100",
        ).fetchall()
        
        if patterns:
            filtered = [(kw, cat) for kw, cat in rows if any(p in kw for p in patterns)]
            if filtered:
                rows = filtered
        
        if not rows:
            logger.warning(f"{blog_id}: 사용 가능한 부동산 키워드 없음")
            return None, None
        
        keyword, category = random.choice(rows[:20])
        conn.execute(
            "UPDATE keywords SET use_count = use_count + 1, "
            "last_used_at = datetime('now') WHERE keyword = ?",
            (keyword,)
        )
        conn.commit()
        logger.info(f"{blog_id}: 키워드 선택 -> {keyword} ({category})")
        return keyword, category
    finally:
        conn.close()


def _pick_strategy(keyword, blog_id=None):
    """blog_id에 따라 전략 결정, 없으면 키워드 기반"""
    if blog_id and blog_id in BLOG_STRATEGY:
        return BLOG_STRATEGY[blog_id]
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

    strategy = _pick_strategy(keyword, blog_id)
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
