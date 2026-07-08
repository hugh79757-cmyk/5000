#!/usr/bin/env python3
"""Daily quality aggregate cron job."""
import sqlite3
from pathlib import Path
from datetime import datetime

QUALITY_DB = Path(__file__).resolve().parent.parent / "data" / "quality.db"


def aggregate_daily():
    if not QUALITY_DB.exists():
        print("quality.db not found")
        return

    conn = sqlite3.connect(str(QUALITY_DB))
    conn.execute("""
        INSERT OR REPLACE INTO daily_quality_summary
        (date, blog_id, total_articles, avg_readability, avg_keyword_coverage,
         pct_has_cta, pct_has_og_image, pct_min_length_pass,
         total_raw_md_issues, articles_with_shortcodes, build_success_rate)
        SELECT 
            DATE(published_at) as date,
            blog_id,
            COUNT(*) as total_articles,
            AVG(readability_score) as avg_readability,
            AVG(keyword_coverage_ratio) as avg_keyword_coverage,
            SUM(has_cta) * 100.0 / COUNT(*) as pct_has_cta,
            SUM(has_og_image) * 100.0 / COUNT(*) as pct_has_og_image,
            SUM(min_length_pass) * 100.0 / COUNT(*) as pct_min_length_pass,
            SUM(raw_bold_count + raw_italic_count + raw_strike_count) as total_raw_md_issues,
            SUM(CASE WHEN lead_shortcode + figure_shortcode_count > 0 THEN 1 ELSE 0 END) as articles_with_shortcodes,
            SUM(build_success) * 100.0 / COUNT(*) as build_success_rate
        FROM article_quality
        WHERE DATE(published_at) = DATE('now', '-1 day')
        GROUP BY DATE(published_at), blog_id
    """)
    conn.commit()
    
    count = conn.execute("SELECT COUNT(*) FROM daily_quality_summary WHERE date = DATE('now', '-1 day')").fetchone()[0]
    conn.close()
    
    print(f"Aggregated {count} blog summaries for yesterday")


if __name__ == "__main__":
    aggregate_daily()
