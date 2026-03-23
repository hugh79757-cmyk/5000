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

BLOG_TOPIC_MAP = {
    "stock-hugo": ["sector_analysis"],
    "dividend-hugo": ["dividend_ranking"],
    "etf-hugo": ["etf_comparison"],
    "sector-hugo": ["sector_analysis"],
    "ipo-hugo": ["ipo_schedule"],
    "finance-hugo": ["cma_savings"],
}


def run(blog_cfg):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"), override=True)

    blog_id = blog_cfg["id"]
    logger.info(f"STAP pipeline: {blog_id}")

    from shared.content_store import init_db, get_today_count
    from shared.publisher import publish
    from pipelines.stock.fetcher import fetch_recent_disclosure, fetch_company_info, fetch_financial_summary, get_listed_corps, fetch_etf_daily, fetch_dividend_ranking
    from pipelines.stock.writer import generate_disclosure_article, generate_evergreen_article
    from pipelines.stock.thumbnail import generate_stock_thumbnail
    from shared.r2_uploader import upload_file

    init_db()
    today_count = get_today_count(blog_id)

    # 하루 첫 발행이면 ETF/배당 데이터 갱신
    if today_count == 0:
        try:
            from pipelines.stock.fetcher import refresh_daily_data
            refresh_daily_data()
            logger.info(f"{blog_id}: 일일 데이터 갱신 완료")
        except Exception as e:
            logger.warning(f"{blog_id}: 일일 데이터 갱신 실패: {e}")

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
            # 전년도 재무도 가져와서 YoY 비교 가능하게
            financials_prev = fetch_financial_summary(corp_code, year=str(datetime.now().year - 2)) if corp_code else []
            # 배당 정보도 추가
            try:
                from pipelines.stock.fetcher import fetch_dividend_info
                dividend = fetch_dividend_info(corp_code) if corp_code else None
            except:
                dividend = None
            article = generate_disclosure_article(disc, company, financials, financials_prev, dividend)
            if article.get("title") and article.get("body_md"):
                # 썸네일 생성 + R2 업로드
                stock_code = company.get("stock_code", "") if company else ""
                thumb_url = _make_thumbnail(article["title"], article.get("category", "공시분석"), company.get("stock_code", "") if company else "", disc.get("corp_name", ""))
                # [P3] SEO description
                _corp = disc.get("corp_name", "")
                _report = disc.get("report_nm", "")
                from datetime import datetime as _dt
                _month = _dt.now().strftime("%Y년 %m월")
                _seo_desc = f"{_corp} {_report} 핵심 분석. {_month} DART 공시 기준."
                _body_d = "<!-- DESC: " + _seo_desc[:160] + " -->\n" + article["body_md"]
                result = publish(
                    blog_id=blog_id,
                    title=article["title"],
                    body_md=_body_d,
                    category=article.get("category", "공시분석"),
                    tags=article.get("tags", ""),
                    data_source="dart_disclosure",
                    source_id=disc.get("rcept_no", ""),
                    model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                    thumbnail_url=thumb_url,
                )
                if result and result.get("success"):
                    _record_publish(conn, blog_id, disc)
    else:
        topic_type = random.choice(BLOG_TOPIC_MAP.get(blog_id, EVERGREEN_TYPES))
        corps = get_listed_corps(limit=100)
        # 재무 데이터 있는 기업만 필터링
        _enriched_corps = []
        for _c in random.sample(corps, min(30, len(corps))):
            _fins = fetch_financial_summary(_c["corp_code"])
            if _fins and len(_fins) > 10:
                _c["_fin_count"] = len(_fins)
                _enriched_corps.append(_c)
                if len(_enriched_corps) >= 10:
                    break
        if not _enriched_corps:
            logger.warning("재무 데이터 있는 기업 없음, 전체에서 샘플링")
            _enriched_corps = random.sample(corps, min(10, len(corps)))
        sample = _enriched_corps
        logger.info(f"재무 데이터 보유 기업 {len(sample)}개 선택")

        # 각 기업의 실제 재무 데이터 수집
        enriched = []
        for corp in sample:
            corp_code = corp.get("corp_code", "")
            if not corp_code:
                continue
            try:
                info = fetch_company_info(corp_code)
                fins = fetch_financial_summary(corp_code)
                key_fins = [f for f in (fins or []) if f.get("account_nm") in ("매출액", "영업이익", "당기순이익")]
                corp_enriched = {
                    "corp_name": corp.get("corp_name", ""),
                    "stock_code": corp.get("stock_code", ""),
                    "sector": corp.get("sector", ""),
                    "ceo": info.get("ceo_nm", "") if info else "",
                    "financials": {f.get("account_nm"): f.get("thstrm_amount", "") for f in key_fins},
                }
                enriched.append(corp_enriched)
                if len(enriched) >= 5:
                    break
            except Exception as e:
                logger.warning(f"기업 데이터 수집 실패 {corp_code}: {e}")
                continue

        # 블로그별 실시간 데이터 주입
        extra = None
        if blog_id == "etf-hugo":
            extra = fetch_etf_daily(top_n=10)
            if extra:
                logger.info(f"ETF 실시간 데이터: 상승 {len(extra['gainers'])}건, 하락 {len(extra['losers'])}건")
        elif blog_id == "dividend-hugo":
            extra = fetch_dividend_ranking(top_n=10)
            if extra:
                logger.info(f"배당 종목 데이터: {len(extra.get('rankings', []))}건")
        article = generate_evergreen_article(topic_type, corp_data=enriched if enriched else sample, extra_data=extra)
        if article.get("title") and article.get("body_md"):
            # 썸네일 생성 + R2 업로드
            thumb_url = _make_thumbnail(article["title"], article.get("category", "시장분석"), "", "")
            # [P3] SEO description
            from datetime import datetime as _dt2
            _month2 = _dt2.now().strftime("%Y년 %m월")
            _eg_desc = f"{article['title']} - {_month2} 기준 {article.get('category', '시장분석')}."
            _body_eg = "<!-- DESC: " + _eg_desc[:160] + " -->\n" + article["body_md"]
            result = publish(
                blog_id=blog_id,
                title=article["title"],
                body_md=_body_eg,
                category=article.get("category", "시장분석"),
                tags=article.get("tags", ""),
                data_source=f"evergreen_{topic_type}",
                source_id="",
                model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                thumbnail_url=thumb_url,
            )

    conn.close()
    if result and result.get("success") and result.get("deploy_error"):
        tg_error(blog_id, "deploy", result["deploy_error"][:300])
    if result and not result.get("success"):
        tg_error(blog_id, "pipeline", result.get("reason", "unknown"))
    if not result or not result.get("success"):
        tg_error(blog_id, "pipeline", (result or {}).get("reason", "no_content"))
    return result or {"success": False, "reason": "no_content"}


def _pick_strategy(conn, blog_id):
    """blog_id별 전략 선택: stock은 disclosure 우선, 나머지는 evergreen 우선"""
    evergreen_blogs = ("dividend-hugo", "etf-hugo", "sector-hugo", "ipo-hugo", "finance-hugo")
    if blog_id in evergreen_blogs:
        return "evergreen"
    return "disclosure"


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

def _make_thumbnail(title, category, stock_code, corp_name):
    """Pillow 썸네일 생성 후 R2 업로드, URL 반환"""
    import tempfile
    try:
        from pipelines.stock.thumbnail import generate_stock_thumbnail
        from shared.r2_uploader import upload_file

        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
            tmp_path = tmp.name

        generate_stock_thumbnail(
            title=title,
            category=category,
            stock_code=stock_code,
            corp_name=corp_name,
            output_path=tmp_path,
        )

        import hashlib
        title_hash = hashlib.md5(title.encode()).hexdigest()[:10]
        r2_key = f"stock-thumbnails/{datetime.now().strftime('%Y%m%d')}-{title_hash}.webp"
        url = upload_file(tmp_path, r2_key, content_type="image/webp")

        os.remove(tmp_path)
        return url
    except Exception as e:
        logger.warning(f"썸네일 생성 실패: {e}")
        return None
