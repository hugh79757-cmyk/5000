"""JSON API endpoints — posts, revenue, traffic, search, health."""

import json
import logging
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import requests
from flask import Blueprint, current_app, jsonify, request

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)


# ── Helpers ──

def _content_db():
    return sqlite3.connect(current_app.config["CONTENT_DB"])


def _analytics_db():
    return sqlite3.connect(current_app.config["ANALYTICS_DB"])


def _dicts(cursor):
    """Return rows as list of dicts."""
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ── Site registry (38 active sites from config/blogs.d/) ──

SITES = [
    # Travel (TAP pipeline)
    {"blog_id": "travel-hugo", "url": "https://tour1.rotcha.kr", "group": "travel"},
    {"blog_id": "travel1-hugo", "url": "https://travel1.rotcha.kr", "group": "travel"},
    {"blog_id": "travel2-hugo", "url": "https://travel2.rotcha.kr", "group": "travel"},
    {"blog_id": "travel3-hugo", "url": "https://tour2.rotcha.kr", "group": "travel"},
    {"blog_id": "travel4-hugo", "url": "https://tour3.rotcha.kr", "group": "travel"},
    {"blog_id": "tap-blogger", "url": "https://travel.rotcha.kr", "group": "travel"},
    # Stock/Finance (STAP pipeline)
    {"blog_id": "stock-hugo", "url": "https://stock.informationhot.kr", "group": "stock"},
    {"blog_id": "dividend-hugo", "url": "https://dividend.techpawz.com", "group": "stock"},
    {"blog_id": "etf-hugo", "url": "https://etf.techpawz.com", "group": "stock"},
    {"blog_id": "sector-hugo", "url": "https://sector.techpawz.com", "group": "stock"},
    {"blog_id": "ipo-hugo", "url": "https://ipo.techpawz.com", "group": "stock"},
    {"blog_id": "finance-hugo", "url": "https://finance.techpawz.com", "group": "stock"},
    # RAP pipeline
    {"blog_id": "rap-hugo", "url": "https://apt.informationhot.kr", "group": "rap"},
    {"blog_id": "rap2-hugo", "url": "https://apply.informationhot.kr", "group": "rap"},
    {"blog_id": "rap3-hugo", "url": "https://tax.informationhot.kr", "group": "rap"},
    {"blog_id": "rap4-hugo", "url": "https://rent.informationhot.kr", "group": "rap"},
    {"blog_id": "rap5-hugo", "url": "https://brand.informationhot.kr", "group": "rap"},
    # Curation (CUAP pipeline)
    {"blog_id": "appliance-hugo", "url": "https://appliance.informationhot.kr", "group": "curation"},
    {"blog_id": "baby-hugo", "url": "https://baby.informationhot.kr", "group": "curation"},
    {"blog_id": "fitness-hugo", "url": "https://fitness.informationhot.kr", "group": "curation"},
    {"blog_id": "interior-hugo", "url": "https://interior.informationhot.kr", "group": "curation"},
    {"blog_id": "laptop-hugo", "url": "https://laptop.informationhot.kr", "group": "curation"},
    {"blog_id": "health-hugo", "url": "https://health.informationhot.kr", "group": "curation"},
    {"blog_id": "pet-hugo", "url": "https://pet.informationhot.kr", "group": "curation"},
    {"blog_id": "kitchen-hugo", "url": "https://kitchen.informationhot.kr", "group": "curation"},
    {"blog_id": "beauty-hugo", "url": "https://beauty.informationhot.kr", "group": "curation"},
    {"blog_id": "camping-hugo", "url": "https://camping.informationhot.kr", "group": "curation"},
    # Senior (SEAP pipeline)
    {"blog_id": "senior-hugo", "url": "https://senior.informationhot.kr", "group": "senior"},
    {"blog_id": "senior-blogger", "url": "https://2.techpawz.com", "group": "senior"},
    # Car/CAP (car pipeline) - compare, hotissue, rank, pick
    {"blog_id": "compare-hugo", "url": "https://compare.rotcha.kr", "group": "car"},
    {"blog_id": "hotissue-hugo", "url": "https://hotissue.rotcha.kr", "group": "car"},
    {"blog_id": "rank-hugo", "url": "https://rank.informationhot.kr", "group": "car"},
    {"blog_id": "pick-hugo", "url": "https://pick.informationhot.kr", "group": "car"},
    # Main sites (no pipeline)
    {"blog_id": "rotcha-blog", "url": "https://rotcha.kr", "group": "main"},
    {"blog_id": "informationhot-hugo", "url": "https://informationhot.kr", "group": "main"},
    {"blog_id": "techpawz-hugo", "url": "https://techpawz.com", "group": "main"},
    {"blog_id": "biz-techpawz-hugo", "url": "https://biz.techpawz.com", "group": "main"},
    {"blog_id": "issue-techpawz-hugo", "url": "https://issue.techpawz.com", "group": "main"},
]

SITE_INDEX = {s["blog_id"]: s for s in SITES}


# ═══════════════════════════════════════════════════════════════
#  /api/health — 사이트 헬스 체크
# ═══════════════════════════════════════════════════════════════

@api_bp.route("/health")
def api_health():
    """Check HTTP status for all sites in parallel."""
    per_site_timeout = float(request.args.get("timeout", 10))
    max_workers = int(request.args.get("workers", 15))

    def _check(site):
        start = time.monotonic()
        try:
            resp = requests.get(
                site["url"],
                timeout=per_site_timeout,
                allow_redirects=True,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "blog_id": site["blog_id"],
                "url": site["url"],
                "group": site["group"],
                "status": resp.status_code,
                "response_ms": elapsed_ms,
            }
        except requests.RequestException as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "blog_id": site["blog_id"],
                "url": site["url"],
                "group": site["group"],
                "status": 0,
                "response_ms": elapsed_ms,
                "error": str(e),
            }

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_check, site): site for site in SITES}
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda r: (0 if r["status"] == 200 else 1, r["response_ms"]))

    summary = {
        "total": len(results),
        "online": sum(1 for r in results if r["status"] == 200),
        "offline": sum(1 for r in results if r["status"] != 200),
        "sites": results,
    }
    return jsonify(summary)


# ═══════════════════════════════════════════════════════════════
#  /api/posts — 발행 현황
# ═══════════════════════════════════════════════════════════════

@api_bp.route("/posts/daily")
def api_posts_daily():
    days = int(request.args.get("days", 30))
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _content_db()
    rows = conn.execute(
        """SELECT blog_id, date(created_at) as dt, COUNT(*) as cnt
           FROM articles
           WHERE status='published' AND created_at > ?
           GROUP BY blog_id, dt
           ORDER BY dt ASC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return jsonify([{"blog_id": r[0], "date": r[1], "count": r[2]} for r in rows])


@api_bp.route("/posts/weekly")
def api_posts_weekly():
    weeks = int(request.args.get("weeks", 12))
    cutoff = (datetime.now() - timedelta(weeks=weeks)).isoformat()
    conn = _content_db()
    rows = conn.execute(
        """SELECT blog_id, strftime('%Y-%W', created_at) as wk, COUNT(*) as cnt
           FROM articles
           WHERE status='published' AND created_at > ?
           GROUP BY blog_id, wk
           ORDER BY wk ASC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return jsonify([{"blog_id": r[0], "week": r[1], "count": r[2]} for r in rows])


@api_bp.route("/posts/total")
def api_posts_total():
    conn = _content_db()
    rows = conn.execute(
        """SELECT blog_id, COUNT(*) as cnt
           FROM articles WHERE status='published'
           GROUP BY blog_id
           ORDER BY cnt DESC"""
    ).fetchall()
    conn.close()

    result = {r[0]: r[1] for r in rows}

    sap_cache = current_app.config.get("SAP_CACHE_DB")
    if sap_cache and Path(sap_cache).exists():
        try:
            sap_conn = sqlite3.connect(sap_cache)
            sap_rows = sap_conn.execute(
                """SELECT blog_id, COUNT(*) as cnt
                   FROM sap_posts
                   GROUP BY blog_id"""
            ).fetchall()
            sap_conn.close()
            for blog_id, cnt in sap_rows:
                result[blog_id] = result.get(blog_id, 0) + cnt
        except Exception as e:
            logger.warning(f"Failed to read SAP cache: {e}")

    aikorea24_cache = current_app.config.get("AIKOREA24_CACHE_DB")
    if aikorea24_cache and Path(aikorea24_cache).exists():
        try:
            ak24_conn = sqlite3.connect(aikorea24_cache)
            ak24_rows = ak24_conn.execute(
                """SELECT COUNT(*) as cnt FROM aikorea24_posts"""
            ).fetchall()
            ak24_conn.close()
            if ak24_rows and ak24_rows[0][0] > 0:
                result["aikorea24"] = result.get("aikorea24", 0) + ak24_rows[0][0]
        except Exception as e:
            logger.warning(f"Failed to read aikorea24 cache: {e}")

    money_cache = current_app.config.get("MONEY_AIKOREA24_CACHE_DB")
    if money_cache and Path(money_cache).exists():
        try:
            money_conn = sqlite3.connect(money_cache)
            money_rows = money_conn.execute(
                """SELECT COUNT(*) as cnt FROM money_aikorea24_posts"""
            ).fetchall()
            money_conn.close()
            if money_rows and money_rows[0][0] > 0:
                result["persona-aikorea24"] = result.get("persona-aikorea24", 0) + money_rows[0][0]
        except Exception as e:
            logger.warning(f"Failed to read money-aikorea24 cache: {e}")

    sorted_result = sorted(result.items(), key=lambda x: x[1], reverse=True)
    return jsonify([{"blog_id": k, "count": v} for k, v in sorted_result])


# ═══════════════════════════════════════════════════════════════
#  /api/revenue — AdSense 수익
# ═══════════════════════════════════════════════════════════════

@api_bp.route("/revenue/daily")
def api_revenue_daily():
    days = int(request.args.get("days", 30))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _analytics_db()
    rows = conn.execute(
        """SELECT date, SUM(estimated_earnings) as revenue,
                  SUM(page_views) as page_views,
                  SUM(clicks) as clicks,
                  AVG(rpm) as rpm, AVG(ctr) as ctr
           FROM adsense_daily
           WHERE date > ?
           GROUP BY date
           ORDER BY date ASC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return jsonify([{
        "date": r[0], "revenue": round(r[1] or 0, 2),
        "page_views": r[2] or 0, "clicks": r[3] or 0,
        "rpm": round(r[4] or 0, 2), "ctr": round(r[5] or 0, 4),
    } for r in rows])


@api_bp.route("/revenue/by-domain")
def api_revenue_by_domain():
    days = int(request.args.get("days", 30))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _analytics_db()
    rows = conn.execute(
        """SELECT domain, SUM(estimated_earnings) as revenue,
                  SUM(page_views) as pv, AVG(rpm) as rpm
           FROM adsense_daily
           WHERE date > ?
           GROUP BY domain
           ORDER BY revenue DESC
           LIMIT 50""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return jsonify([{
        "domain": r[0], "revenue": round(r[1] or 0, 2),
        "page_views": r[2] or 0, "rpm": round(r[3] or 0, 2),
    } for r in rows])


@api_bp.route("/revenue/rpm")
def api_revenue_rpm():
    days = int(request.args.get("days", 90))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _analytics_db()
    rows = conn.execute(
        """SELECT date, AVG(rpm) as avg_rpm, AVG(ctr) as avg_ctr
           FROM adsense_daily
           WHERE date > ?
           GROUP BY date
           ORDER BY date ASC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return jsonify([{
        "date": r[0], "rpm": round(r[1] or 0, 2), "ctr": round(r[2] or 0, 4),
    } for r in rows])


# ═══════════════════════════════════════════════════════════════
#  /api/traffic — GA4 트래픽
# ═══════════════════════════════════════════════════════════════

@api_bp.route("/traffic/daily")
def api_traffic_daily():
    days = int(request.args.get("days", 30))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _analytics_db()
    rows = conn.execute(
        """SELECT date, SUM(sessions) as sessions,
                  SUM(total_users) as users,
                  SUM(page_views) as page_views,
                  AVG(bounce_rate) as bounce_rate,
                  AVG(engagement_rate) as engagement_rate,
                  SUM(ad_revenue) as ad_revenue
           FROM ga4_daily
           WHERE date > ?
           GROUP BY date
           ORDER BY date ASC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return jsonify([{
        "date": r[0], "sessions": r[1] or 0, "users": r[2] or 0,
        "page_views": r[3] or 0, "bounce_rate": round(r[4] or 0, 1),
        "engagement_rate": round(r[5] or 0, 1),
        "ad_revenue": round(r[6] or 0, 2),
    } for r in rows])


@api_bp.route("/traffic/by-blog")
def api_traffic_by_blog():
    days = int(request.args.get("days", 30))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _analytics_db()
    rows = conn.execute(
        """SELECT blog_id, SUM(sessions) as sessions,
                  SUM(page_views) as page_views,
                  SUM(ad_revenue) as revenue
           FROM ga4_daily
           WHERE date > ?
           GROUP BY blog_id
           ORDER BY sessions DESC
           LIMIT 30""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return jsonify([{
        "blog_id": r[0], "sessions": r[1] or 0,
        "page_views": r[2] or 0, "revenue": round(r[3] or 0, 2),
    } for r in rows])


# ═══════════════════════════════════════════════════════════════
#  /api/search — GSC + Bing 검색 성과
# ═══════════════════════════════════════════════════════════════

@api_bp.route("/search/gsc/daily")
def api_search_gsc():
    days = int(request.args.get("days", 30))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _analytics_db()
    rows = conn.execute(
        """SELECT date, SUM(total_clicks) as clicks,
                  SUM(total_impressions) as impressions,
                  AVG(avg_ctr) as ctr, AVG(avg_position) as position
           FROM gsc_daily_summary
           WHERE date > ?
           GROUP BY date
           ORDER BY date ASC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return jsonify([{
        "date": r[0], "clicks": r[1] or 0, "impressions": r[2] or 0,
        "ctr": round(r[3] or 0, 4), "position": round(r[4] or 0, 1),
    } for r in rows])


@api_bp.route("/search/bing/daily")
def api_search_bing():
    days = int(request.args.get("days", 30))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _analytics_db()
    rows = conn.execute(
        """SELECT date, SUM(clicks) as clicks,
                  SUM(impressions) as impressions,
                  AVG(avg_position) as position
           FROM bing_daily_summary
           WHERE date > ?
           GROUP BY date
           ORDER BY date ASC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return jsonify([{
        "date": r[0], "clicks": r[1] or 0, "impressions": r[2] or 0,
        "position": round(r[3] or 0, 1),
    } for r in rows])


@api_bp.route("/search/efficiency")
def api_search_efficiency():
    days = int(request.args.get("days", 30))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _analytics_db()
    rows = conn.execute(
        """SELECT blog_id, AVG(efficiency_score) as score,
                  AVG(gsc_clicks) as clicks, AVG(gsc_impressions) as impressions
           FROM blog_efficiency
           WHERE date > ?
           GROUP BY blog_id
           ORDER BY score DESC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return jsonify([{
        "blog_id": r[0], "efficiency": round(r[1] or 0, 1),
        "clicks": int(r[2] or 0), "impressions": int(r[3] or 0),
    } for r in rows])


# ═══════════════════════════════════════════════════════════════
#  /api/summary — 대시보드 통합 요약 (한 번에 모든 지표)
# ═══════════════════════════════════════════════════════════════

@api_bp.route("/summary")
def api_summary():
    """Returns combined stats for dashboard overview cards."""
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    month_ago = (datetime.now() - timedelta(days=30)).isoformat()

    result = {}

    # Total posts
    conn = _content_db()
    total = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE status='published'"
    ).fetchone()[0]
    today_posts = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE status='published' AND date(created_at)=?",
        (today,),
    ).fetchone()[0]
    week_posts = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE status='published' AND created_at > ?",
        (week_ago,),
    ).fetchone()[0]
    conn.close()
    result["total_posts"] = total
    result["today_posts"] = today_posts
    result["week_posts"] = week_posts

    # Revenue
    conn = _analytics_db()
    month_revenue = conn.execute(
        "SELECT SUM(estimated_earnings) FROM adsense_daily WHERE date > ?",
        ((datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),),
    ).fetchone()[0]
    result["month_revenue"] = round(month_revenue or 0, 2)

    # Traffic
    month_sessions = conn.execute(
        "SELECT SUM(sessions) FROM ga4_daily WHERE date > ?",
        ((datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),),
    ).fetchone()[0]
    result["month_sessions"] = month_sessions or 0

    # Search
    month_clicks = conn.execute(
        "SELECT SUM(total_clicks) FROM gsc_daily_summary WHERE date > ?",
        ((datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),),
    ).fetchone()[0]
    result["month_search_clicks"] = month_clicks or 0
    conn.close()

    result["total_sites"] = len(SITES)
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════
#  /api/quality — 콘텐츠 품질 메트릭
# ═══════════════════════════════════════════════════════════════

def _quality_db():
    quality_path = Path(__file__).resolve().parent.parent.parent / "quality.db"
    if not quality_path.exists():
        return None
    return sqlite3.connect(str(quality_path))


@api_bp.route("/quality/summary")
def api_quality_summary():
    conn = _quality_db()
    if not conn:
        return jsonify({"error": "quality.db not found"}), 404
    
    row = conn.execute("""
        SELECT 
            AVG(readability_score) as avg_readability,
            AVG(keyword_coverage_ratio) as avg_keyword_coverage,
            SUM(has_cta) * 100.0 / COUNT(*) as pct_has_cta,
            SUM(has_og_image) * 100.0 / COUNT(*) as pct_has_og_image,
            COUNT(*) as total_articles
        FROM article_quality
        WHERE published_at > datetime('now', '-30 days')
    """).fetchone()
    conn.close()
    
    return jsonify({
        "avg_readability": round(row[0] or 0, 3),
        "avg_keyword_coverage": round(row[1] or 0, 3),
        "pct_has_cta": round(row[2] or 0, 1),
        "pct_has_og_image": round(row[3] or 0, 1),
        "total_articles": row[4] or 0,
    })


@api_bp.route("/quality/by-blog")
def api_quality_by_blog():
    conn = _quality_db()
    if not conn:
        return jsonify([])
    
    rows = conn.execute("""
        SELECT blog_id,
               COUNT(*) as total,
               AVG(readability_score) as avg_readability,
               AVG(keyword_coverage_ratio) as avg_keyword_coverage,
               SUM(has_cta) * 100.0 / COUNT(*) as pct_cta,
               SUM(has_og_image) * 100.0 / COUNT(*) as pct_og_image
        FROM article_quality
        WHERE published_at > datetime('now', '-30 days')
        GROUP BY blog_id
        ORDER BY avg_readability DESC
    """).fetchall()
    conn.close()
    
    return jsonify([{
        "blog_id": r[0], "total": r[1],
        "avg_readability": round(r[2] or 0, 3),
        "avg_keyword_coverage": round(r[3] or 0, 3),
        "pct_cta": round(r[4] or 0, 1),
        "pct_og_image": round(r[5] or 0, 1),
    } for r in rows])


@api_bp.route("/quality/markdown-issues")
def api_quality_markdown():
    conn = _quality_db()
    if not conn:
        return jsonify([])
    
    days = int(request.args.get("days", 30))
    rows = conn.execute("""
        SELECT DATE(published_at) as date,
               SUM(raw_bold_count) as bold,
               SUM(raw_italic_count) as italic,
               SUM(raw_strike_count) as strike
        FROM article_quality
        WHERE published_at > datetime('now', '-' || ? || ' days')
        GROUP BY DATE(published_at)
        ORDER BY date ASC
    """, (days,)).fetchall()
    conn.close()
    
    return jsonify([{
        "date": r[0], "bold": r[1] or 0,
        "italic": r[2] or 0, "strike": r[3] or 0,
    } for r in rows])


@api_bp.route("/quality/shortcodes")
def api_quality_shortcodes():
    conn = _quality_db()
    if not conn:
        return jsonify([])
    
    rows = conn.execute("""
        SELECT blog_id,
               SUM(lead_shortcode) as lead,
               SUM(figure_shortcode_count) as figure,
               SUM(gallery_shortcode_count) as gallery,
               SUM(accordion_shortcode_count) as accordion
        FROM article_quality
        WHERE published_at > datetime('now', '-30 days')
        GROUP BY blog_id
        ORDER BY lead DESC
    """).fetchall()
    conn.close()
    
    return jsonify([{
        "blog_id": r[0], "lead": r[1] or 0,
        "figure": r[2] or 0, "gallery": r[3] or 0,
        "accordion": r[4] or 0,
    } for r in rows])


@api_bp.route("/quality/hugo-build")
def api_quality_build():
    conn = _quality_db()
    if not conn:
        return jsonify([])
    
    rows = conn.execute("""
        SELECT DATE(published_at) as date,
               SUM(build_success) * 100.0 / COUNT(*) as success_rate,
               AVG(build_time_ms) as avg_time,
               SUM(build_warnings) as warnings,
               SUM(build_errors) as errors
        FROM article_quality
        WHERE published_at > datetime('now', '-30 days')
        GROUP BY DATE(published_at)
        ORDER BY date ASC
    """).fetchall()
    conn.close()
    
    return jsonify([{
        "date": r[0], "success_rate": round(r[1] or 0, 1),
        "avg_time": round(r[2] or 0, 0),
        "warnings": r[3] or 0, "errors": r[4] or 0,
    } for r in rows])
