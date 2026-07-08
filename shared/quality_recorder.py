"""Quality metrics recorder for content pipeline."""
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

QUALITY_DB = Path(__file__).resolve().parent.parent / "data" / "quality.db"


def _get_conn():
    QUALITY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(QUALITY_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS article_quality (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            slug TEXT NOT NULL,
            title TEXT,
            published_at TEXT NOT NULL,
            raw_bold_count INTEGER DEFAULT 0,
            raw_italic_count INTEGER DEFAULT 0,
            raw_strike_count INTEGER DEFAULT 0,
            raw_code_count INTEGER DEFAULT 0,
            has_cta INTEGER DEFAULT 0,
            has_og_image INTEGER DEFAULT 0,
            has_map_text INTEGER DEFAULT 0,
            min_length_pass INTEGER DEFAULT 0,
            empty_template_count INTEGER DEFAULT 0,
            readability_score REAL,
            keyword_coverage_ratio REAL,
            content_length INTEGER,
            paragraph_count INTEGER,
            lead_shortcode INTEGER DEFAULT 0,
            figure_shortcode_count INTEGER DEFAULT 0,
            gallery_shortcode_count INTEGER DEFAULT 0,
            accordion_shortcode_count INTEGER DEFAULT 0,
            chart_shortcode_count INTEGER DEFAULT 0,
            build_success INTEGER DEFAULT 1,
            build_warnings INTEGER DEFAULT 0,
            build_errors INTEGER DEFAULT 0,
            build_time_ms INTEGER DEFAULT 0,
            collected_at TEXT DEFAULT (datetime('now')),
            UNIQUE(blog_id, slug)
        );

        CREATE INDEX IF NOT EXISTS idx_quality_blog_date ON article_quality(blog_id, published_at);
        CREATE INDEX IF NOT EXISTS idx_quality_collected ON article_quality(collected_at);

        CREATE TABLE IF NOT EXISTS daily_quality_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            blog_id TEXT NOT NULL,
            total_articles INTEGER DEFAULT 0,
            avg_readability REAL,
            avg_keyword_coverage REAL,
            pct_has_cta REAL,
            pct_has_og_image REAL,
            pct_min_length_pass REAL,
            total_raw_md_issues INTEGER DEFAULT 0,
            articles_with_shortcodes INTEGER DEFAULT 0,
            build_success_rate REAL,
            UNIQUE(date, blog_id)
        );

        CREATE TABLE IF NOT EXISTS funnel_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id TEXT NOT NULL,
            slug TEXT NOT NULL,
            published_at TEXT NOT NULL,
            has_attention INTEGER DEFAULT 0,
            has_interest INTEGER DEFAULT 0,
            has_desire INTEGER DEFAULT 0,
            has_action INTEGER DEFAULT 0,
            cta_clicks INTEGER DEFAULT 0,
            affiliate_clicks INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            revenue REAL DEFAULT 0,
            UNIQUE(blog_id, slug)
        );

        CREATE INDEX IF NOT EXISTS idx_funnel_date ON funnel_tracking(published_at);

        CREATE INDEX IF NOT EXISTS idx_dqs_date ON daily_quality_summary(date);
    """)
    conn.close()


def record_quality(blog_id: str, slug: str, title: str, published_at: str, metrics: dict):
    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO article_quality
        (blog_id, slug, title, published_at,
         raw_bold_count, raw_italic_count, raw_strike_count, raw_code_count,
         has_cta, has_og_image, has_map_text, min_length_pass, empty_template_count,
         readability_score, keyword_coverage_ratio, content_length, paragraph_count,
         lead_shortcode, figure_shortcode_count, gallery_shortcode_count,
         accordion_shortcode_count, chart_shortcode_count,
         build_success, build_warnings, build_errors, build_time_ms)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        blog_id, slug, title, published_at,
        metrics.get("raw_bold_count", 0),
        metrics.get("raw_italic_count", 0),
        metrics.get("raw_strike_count", 0),
        metrics.get("raw_code_count", 0),
        int(metrics.get("has_cta", False)),
        int(metrics.get("has_og_image", False)),
        int(metrics.get("has_map_text", False)),
        int(metrics.get("min_length_pass", False)),
        metrics.get("empty_template_count", 0),
        metrics.get("readability_score"),
        metrics.get("keyword_coverage_ratio"),
        metrics.get("content_length", 0),
        metrics.get("paragraph_count", 0),
        int(metrics.get("lead_shortcode", False)),
        metrics.get("figure_shortcode_count", 0),
        metrics.get("gallery_shortcode_count", 0),
        metrics.get("accordion_shortcode_count", 0),
        metrics.get("chart_shortcode_count", 0),
        int(metrics.get("build_success", True)),
        metrics.get("build_warnings", 0),
        metrics.get("build_errors", 0),
        metrics.get("build_time_ms", 0),
    ))
    conn.commit()
    conn.close()


def record_build(blog_id: str, slug: str, build_result: dict):
    conn = _get_conn()
    conn.execute("""
        UPDATE article_quality
        SET build_success = ?, build_warnings = ?, build_errors = ?, build_time_ms = ?
        WHERE blog_id = ? AND slug = ?
    """, (
        int(build_result.get("build_success", True)),
        build_result.get("build_warnings", 0),
        build_result.get("build_errors", 0),
        build_result.get("build_time_ms", 0),
        blog_id, slug,
    ))
    conn.commit()
    conn.close()


def get_quality_summary(blog_id=None, days=30):
    conn = _get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    if blog_id:
        rows = conn.execute(
            "SELECT * FROM daily_quality_summary WHERE blog_id = ? AND date > ? ORDER BY date DESC",
            (blog_id, cutoff)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM daily_quality_summary WHERE date > ? ORDER BY date DESC",
            (cutoff,)
        ).fetchall()
    conn.close()
    return rows


def get_blog_quality_scores():
    conn = _get_conn()
    rows = conn.execute("""
        SELECT blog_id,
               COUNT(*) as total,
               AVG(readability_score) as avg_readability,
               AVG(keyword_coverage_ratio) as avg_keyword_coverage,
               SUM(has_cta) * 100.0 / COUNT(*) as pct_cta,
               SUM(has_og_image) * 100.0 / COUNT(*) as pct_og_image
        FROM article_quality
        GROUP BY blog_id
        ORDER BY avg_readability DESC
    """).fetchall()
    conn.close()
    return rows


def record_funnel(blog_id: str, slug: str, published_at: str, funnel_data: dict):
    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO funnel_tracking
        (blog_id, slug, published_at,
         has_attention, has_interest, has_desire, has_action,
         cta_clicks, affiliate_clicks, conversions, revenue)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        blog_id, slug, published_at,
        int(funnel_data.get("has_attention", False)),
        int(funnel_data.get("has_interest", False)),
        int(funnel_data.get("has_desire", False)),
        int(funnel_data.get("has_action", False)),
        funnel_data.get("cta_clicks", 0),
        funnel_data.get("affiliate_clicks", 0),
        funnel_data.get("conversions", 0),
        funnel_data.get("revenue", 0),
    ))
    conn.commit()
    conn.close()


def get_funnel_stats(blog_id=None, days=30):
    conn = _get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    if blog_id:
        rows = conn.execute(
            "SELECT * FROM funnel_tracking WHERE blog_id = ? AND published_at > ? ORDER BY published_at DESC",
            (blog_id, cutoff)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM funnel_tracking WHERE published_at > ? ORDER BY published_at DESC",
            (cutoff,)
        ).fetchall()
    conn.close()
    return rows


init_db()
