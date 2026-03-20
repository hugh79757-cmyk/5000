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

# WordPress 카테고리 ID 매핑 (kuta.informationhot.kr)
WP_CATEGORY_MAP = {
    "생활/행정": 150,      # 생활정보
    "생활정보": 150,
    "생활/보조금": 150,
    "세금/납부": 150,
    "세금/재테크": 150,
    "금융/부동산": 150,
    "행정/민원": 150,
    "건강/복지": 150,
    "고용/취업": 150,
    "자동차/교통": 150,
    "IT/기술": 150,
    "여가/축제": 149,      # 여행
    "여행/축제": 149,
    "여행/항공": 149,
    "여행/자연": 149,
    "스포츠/야구": 150,
    "엔터테인먼트": 150,
}

GAP_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "gap.db")


def _pick_keyword(blog_id):
    """gap.db에서 미사용/오래된 키워드 선택, 사용 기록 갱신"""
    conn = sqlite3.connect(GAP_DB_PATH)
    try:
        # 최근 7일 이내 이 블로그에서 발행된 키워드 제외
        published = {r[0] for r in conn.execute(
            "SELECT keyword FROM publish_log WHERE site_id=? AND published_at > datetime('now', '-7 days')",
            (blog_id,)
        ).fetchall()}

        rows = conn.execute(
            "SELECT keyword FROM keywords WHERE status='active' ORDER BY use_count ASC, last_used_at ASC NULLS FIRST"
        ).fetchall()

        available = [r[0] for r in rows if r[0] not in published]
        if not available:
            available = [r[0] for r in rows]
        if not available:
            logger.error(f"{blog_id}: gap.db에 활성 키워드 없음")
            return None

        keyword = available[0]
        conn.execute(
            "UPDATE keywords SET use_count = use_count + 1, last_used_at = datetime('now') WHERE keyword = ?",
            (keyword,)
        )
        conn.commit()
        return keyword
    except Exception as e:
        logger.error(f"키워드 선택 실패: {e}")
        return None
    finally:
        conn.close()


def run(blog_cfg):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"), override=True)

    blog_id = blog_cfg["id"]
    logger.info(f"GAP pipeline: {blog_id}")

    from shared.content_store import init_db, get_today_count
    from shared.publisher import publish
    from pipelines.gap.fetcher import fetch_keyword_data
    from pipelines.gap.writer import generate_gap_article
    from pipelines.gap.thumbnail import upload_thumbnail

    init_db()
    today_count = get_today_count(blog_id)
    quota = blog_cfg.get("daily_quota", 10)
    if today_count >= quota:
        logger.info(f"{blog_id}: 오늘 발행 완료 ({today_count}/{quota})")
        return {"success": False, "reason": "quota_met"}

    keyword = _pick_keyword(blog_id)
    logger.info(f"{blog_id}: 키워드 = {keyword}")

    data = fetch_keyword_data(keyword)
    if data["total_sources"] < 1:
        logger.warning(f"{blog_id}: 검색 결과 없음 [{keyword}]")
        tg_error(blog_id, "fetcher", f"검색 결과 0건: {keyword}")
        return {"success": False, "reason": "no_search_results"}

    logger.info(f"{blog_id}: 수집 완료 - {data['total_sources']}건")

    article = generate_gap_article(keyword, data)
    if not article:
        tg_error(blog_id, "writer", f"글 생성 실패: {keyword}")
        return {"success": False, "reason": "write_failed"}

    logger.info(f"{blog_id}: 글 생성 완료 - {article['title']}")

    thumb_url = upload_thumbnail(article["title"], article.get("category", "생활정보"))

    # 키워드 카테고리에서 WP 카테고리 ID 결정
    kw_category = ""
    try:
        import sqlite3 as _sq
        _conn = _sq.connect(GAP_DB_PATH)
        _row = _conn.execute("SELECT category FROM keywords WHERE keyword=?", (keyword,)).fetchone()
        if _row:
            kw_category = _row[0]
        _conn.close()
    except:
        pass
    wp_cat_id = WP_CATEGORY_MAP.get(kw_category, 150)

    # 내부링크 + CTA 삽입 (WordPress만)
    if blog_cfg.get("platform") == "wordpress":
        try:
            from pipelines.gap.internal_links import process_gap_content
            import markdown as _md
            _html = _md.markdown(article["body_md"], extensions=["tables", "fenced_code"])
            _html = process_gap_content(_html, kw_category)
            article["body_html"] = _html
        except Exception as _e:
            logger.warning(f"내부링크/CTA 삽입 실패: {_e}")

    result = publish(
        blog_id=blog_id,
        title=article["title"],
        body_md=article["body_md"],
        category=article.get("category", "생활정보"),
        tags=article.get("tags", ""),
        data_source="naver_search",
        source_id=keyword,
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        thumbnail_url=thumb_url,
        wp_category=wp_cat_id,
    )

    if result and result.get("success"):
        logger.info(f"{blog_id}: 발행 성공 - {article['title']}")
    else:
        reason = result.get("reason", "unknown") if result else "no_result"
        tg_error(blog_id, "publish", f"{keyword}: {reason}")

    if result and result.get("success") and result.get("deploy_error"):
        tg_error(blog_id, "deploy", result["deploy_error"][:300])

    return result or {"success": False, "reason": "publish_failed"}
