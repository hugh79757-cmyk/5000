import os, sqlite3, yaml
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)
app.config['SECRET_KEY'] = 'blogdex-2026'
from functools import wraps

def check_auth(username, password):
    return username == 'admin' and password == 'blogdex2026!'

def authenticate():
    from flask import Response
    return Response('Login required', 401, {'WWW-Authenticate': 'Basic realm="Blogdex"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request as req
        auth = req.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYTICS_DB = os.path.join(BASE, 'data', 'analytics.db')
CONTENT_DB = os.path.join(BASE, 'data', 'content.db')
TRAVEL_DB = os.path.join(BASE, 'data', 'travel-en.db')
SITES_YAML = os.path.join(os.path.dirname(__file__), 'sites.yaml')

def get_db(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def load_sites():
    try:
        with open(SITES_YAML, 'r') as f:
            data = yaml.safe_load(f)
        return data.get('sites', []), data.get('groups', {})
    except:
        return [], {}

def get_all_blog_ids():
    sites, _ = load_sites()
    return [s['blog_id'] for s in sites]

def get_latest_date(conn):
    r = conn.execute("SELECT MAX(date) FROM gsc_daily_summary").fetchone()
    return r[0] if r and r[0] else None

# ===== MAIN DASHBOARD =====
@app.route('/')
@requires_auth
def index():
    conn = get_db(ANALYTICS_DB)
    sites, groups = load_sites()
    all_blogs = get_all_blog_ids()
    latest = get_latest_date(conn)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    if not latest:
        return render_template('index.html', error="No data", now=now)

    d7 = (datetime.strptime(latest, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    d30 = (datetime.strptime(latest, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')

    # 7-day summary
    summary = conn.execute("""
        SELECT COALESCE(SUM(total_clicks),0) clicks, COALESCE(SUM(total_impressions),0) impressions,
               COUNT(DISTINCT blog_id) blogs
        FROM gsc_daily_summary WHERE date > ?
    """, (d7,)).fetchone()

    # GA4 7-day
    ga4 = conn.execute("""
        SELECT COALESCE(SUM(sessions),0) sessions, COALESCE(SUM(page_views),0) pv,
               COALESCE(SUM(ad_revenue),0) revenue
        FROM ga4_daily WHERE date > ?
    """, (d7,)).fetchone()

    # Per-blog stats (7 days)
    blog_stats = conn.execute("""
        SELECT g.blog_id,
               COALESCE(SUM(g.total_clicks),0) clicks,
               COALESCE(SUM(g.total_impressions),0) impressions,
               ROUND(AVG(g.avg_position),1) pos,
               e.efficiency_score, e.grade
        FROM gsc_daily_summary g
        LEFT JOIN blog_efficiency e ON g.blog_id = e.blog_id AND e.date = ?
        WHERE g.date > ?
        GROUP BY g.blog_id
        ORDER BY impressions DESC
    """, (latest, d7)).fetchall()

    tracked_ids = set(r['blog_id'] for r in blog_stats)
    unlinked = [b for b in all_blogs if b not in tracked_ids]

    # Top keywords
    keywords = conn.execute("""
        SELECT blog_id, query, SUM(clicks) clicks, SUM(impressions) impressions,
               ROUND(AVG(position),1) pos
        FROM gsc_keywords WHERE date > ?
        GROUP BY blog_id, query
        ORDER BY impressions DESC LIMIT 30
    """, (d7,)).fetchall()

    # Recycle candidates: high impressions, zero clicks
    recycle = conn.execute("""
        SELECT blog_id, query, SUM(impressions) impressions, ROUND(AVG(position),1) pos
        FROM gsc_keywords WHERE date > ? AND clicks = 0 AND impressions >= 3
        GROUP BY blog_id, query
        ORDER BY impressions DESC LIMIT 20
    """, (d7,)).fetchall()

    # Danger blogs: zero impressions in 7 days
    danger = conn.execute("""
        SELECT blog_id, SUM(total_impressions) imp
        FROM gsc_daily_summary WHERE date > ?
        GROUP BY blog_id HAVING imp = 0
    """, (d7,)).fetchall()

    # 30-day trend
    trend = conn.execute("""
        SELECT date, SUM(total_clicks) clicks, SUM(total_impressions) impressions
        FROM gsc_daily_summary WHERE date > ?
        GROUP BY date ORDER BY date
    """, (d30,)).fetchall()

    # Bing 7-day summary
    bing = conn.execute("""
        SELECT COALESCE(SUM(clicks),0) clicks, COALESCE(SUM(impressions),0) impressions,
               COUNT(DISTINCT blog_id) blogs
        FROM bing_daily_summary WHERE date > ?
    """, (d7,)).fetchone()

    # AdSense 7-day summary
    adsense = conn.execute("""
        SELECT COALESCE(SUM(estimated_earnings),0) revenue,
               COALESCE(SUM(page_views),0) page_views,
               COALESCE(SUM(clicks),0) clicks
        FROM adsense_daily WHERE date > ?
    """, (d7,)).fetchone()

    # AdSense 30-day trend (daily total)
    revenue_trend = conn.execute("""
        SELECT date, ROUND(SUM(estimated_earnings),2) revenue, SUM(page_views) pv
        FROM adsense_daily WHERE date > ?
        GROUP BY date ORDER BY date
    """, (d30,)).fetchall()

    conn.close()

    site_map = {s['blog_id']: s for s in sites}

    return render_template('index.html',
        latest=latest, now=now, summary=summary, ga4=ga4,
        blog_stats=blog_stats, keywords=keywords, recycle=recycle,
        danger=danger, unlinked=unlinked, trend=trend,
        site_map=site_map, groups=groups, total_blogs=len(all_blogs),
        bing=bing, adsense=adsense, revenue_trend=revenue_trend)

# ===== BLOG DETAIL =====
@app.route('/blog/<blog_id>')
@requires_auth
def blog_detail(blog_id):
    conn = get_db(ANALYTICS_DB)
    latest = get_latest_date(conn)
    if not latest:
        return "No data", 404

    d30 = (datetime.strptime(latest, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
    d7 = (datetime.strptime(latest, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')

    trend = conn.execute("""
        SELECT date, total_clicks clicks, total_impressions impressions
        FROM gsc_daily_summary WHERE blog_id=? AND date > ? ORDER BY date
    """, (blog_id, d30)).fetchall()

    keywords = conn.execute("""
        SELECT query, SUM(clicks) clicks, SUM(impressions) impressions,
               ROUND(AVG(position),1) pos
        FROM gsc_keywords WHERE blog_id=? AND date > ?
        GROUP BY query ORDER BY impressions DESC LIMIT 30
    """, (blog_id, d7)).fetchall()

    # Recycle candidates for this blog
    recycle = conn.execute("""
        SELECT query, SUM(impressions) impressions, ROUND(AVG(position),1) pos
        FROM gsc_keywords WHERE blog_id=? AND date > ? AND clicks = 0 AND impressions >= 2
        GROUP BY query ORDER BY impressions DESC LIMIT 15
    """, (blog_id, d7)).fetchall()

    pages = conn.execute("""
        SELECT page, SUM(clicks) clicks, SUM(impressions) impressions
        FROM gsc_pages WHERE blog_id=? AND date > ?
        GROUP BY page ORDER BY impressions DESC LIMIT 20
    """, (blog_id, d7)).fetchall()

    ga4 = conn.execute("""
        SELECT date, sessions, page_views, revenue
        FROM ga4_daily WHERE blog_id=? AND date > ? ORDER BY date DESC LIMIT 7
    """, (blog_id, d30)).fetchall()

    efficiency = conn.execute("""
        SELECT * FROM blog_efficiency WHERE blog_id=? ORDER BY date DESC LIMIT 1
    """, (blog_id,)).fetchone()

    conn.close()

    sites, groups = load_sites()
    site_info = next((s for s in sites if s['blog_id'] == blog_id), None)

    return render_template('blog_detail.html',
        blog_id=blog_id, trend=trend, keywords=keywords, recycle=recycle,
        pages=pages, ga4=ga4, efficiency=efficiency, site_info=site_info)

# ===== KEYWORDS TAB =====
@app.route('/keywords')
@requires_auth
def keywords_tab():
    conn = get_db(ANALYTICS_DB)
    latest = get_latest_date(conn)
    if not latest:
        return "No data", 404
    d7 = (datetime.strptime(latest, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')

    # All keywords grouped by blog
    all_kw = conn.execute("""
        SELECT blog_id, query, SUM(clicks) clicks, SUM(impressions) impressions,
               ROUND(AVG(position),1) pos
        FROM gsc_keywords WHERE date > ?
        GROUP BY blog_id, query
        ORDER BY blog_id, impressions DESC
    """, (d7,)).fetchall()

    # Opportunity keywords: position 5-20, impressions > 0
    opportunity = conn.execute("""
        SELECT blog_id, query, SUM(impressions) impressions, ROUND(AVG(position),1) pos
        FROM gsc_keywords WHERE date > ? AND position BETWEEN 5 AND 20 AND impressions >= 2
        GROUP BY blog_id, query
        ORDER BY impressions DESC LIMIT 30
    """, (d7,)).fetchall()

    # Recycle: zero clicks, high impressions
    recycle = conn.execute("""
        SELECT blog_id, query, SUM(impressions) impressions, ROUND(AVG(position),1) pos
        FROM gsc_keywords WHERE date > ? AND clicks = 0 AND impressions >= 3
        GROUP BY blog_id, query
        ORDER BY impressions DESC LIMIT 30
    """, (d7,)).fetchall()

    conn.close()
    return render_template('keywords.html',
        all_kw=all_kw, opportunity=opportunity, recycle=recycle, latest=latest)

# ===== API =====
@app.route('/api/trend/<blog_id>')
@requires_auth
def api_trend(blog_id):
    conn = get_db(ANALYTICS_DB)
    latest = get_latest_date(conn)
    d30 = (datetime.strptime(latest, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
    rows = conn.execute("""
        SELECT date, total_clicks clicks, total_impressions impressions
        FROM gsc_daily_summary WHERE blog_id=? AND date > ? ORDER BY date
    """, (blog_id, d30)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/publish')
@requires_auth
def publish_status():
    sites, groups = load_sites()
    from datetime import datetime, timedelta
    today = datetime.now().strftime('%Y-%m-%d')
    d7 = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    d30 = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    results = []
    for s in sites:
        bid = s['blog_id']
        row = {"blog_id": bid, "domain": s.get("domain",""), "group": s.get("group","")}

        db = get_db("data/analytics.db")
        for label, start in [("today", today), ("week", d7), ("month", d30)]:
            r = db.execute("SELECT COUNT(*) FROM gsc_pages WHERE blog_id=? AND date>=?", (bid, start)).fetchone()
            row[label] = r[0] if r else 0
        db.close()
        results.append(row)

    results.sort(key=lambda x: x["month"], reverse=True)
    for r in results:
        r["total"] = r["today"] + r["week"] + r["month"]
    totals = {
        "today": sum(r["today"] for r in results),
        "week": sum(r["week"] for r in results),
        "month": sum(r["month"] for r in results),
        "total": sum(r["total"] for r in results),
        "blogs": len([r for r in results if r["month"] > 0])
    }
    return render_template("publish.html", sites=results, groups=groups, now=today, totals=totals)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=False)
