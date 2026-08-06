"""ops_dashboard.app — Flask web application for the ops dashboard.

Provides human-readable pages and a JSON API for the fleet health data.
All routes are protected by Basic Auth (OPS_USER/OPS_PASSWORD env vars).
"""
import logging
import os
import sqlite3
from functools import wraps

from flask import Flask, Response, g, jsonify, render_template_string, request

from ops_dashboard.checks import run_all_checks
from ops_dashboard.db import (
    get_all_blogs,
    get_attention_items,
    get_blog_detail,
    get_conn,
    init_db,
    seed_known_issues,
    sync_blog_lifecycle,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

_DEFAULT_USER = "ops"
_DEFAULT_PASSWORD = "changeme"


def _get_auth_credentials() -> tuple[str, str]:
    """Read OPS_USER / OPS_PASSWORD from environment."""
    user = os.environ.get("OPS_USER", _DEFAULT_USER)
    password = os.environ.get("OPS_PASSWORD", _DEFAULT_PASSWORD)
    return user, password


def _check_auth(auth) -> bool:
    """Verify HTTP Basic Auth credentials."""
    if auth is None:
        return False
    expected_user, expected_password = _get_auth_credentials()
    return auth.username == expected_user and auth.password == expected_password


def require_auth(fn):
    """Decorator: reject unauthenticated requests with 401."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _check_auth(request.authorization):
            return Response(
                "Unauthorized",
                401,
                {"WWW-Authenticate": 'Basic realm="Ops Dashboard"'},
            )
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


def _get_db() -> sqlite3.Connection:
    """Get a DB connection, reusing Flask g if available."""
    if "db" not in g:
        g.db = get_conn()
    return g.db


def _ensure_db(conn: sqlite3.Connection) -> None:
    """Initialize DB schema and seed data if tables are empty."""
    init_db(conn)
    row = conn.execute("SELECT COUNT(*) FROM blog_lifecycle").fetchone()
    if row[0] == 0:
        sync_blog_lifecycle(conn)
        seed_known_issues(conn)


# ---------------------------------------------------------------------------
# Inline HTML templates (Jinja2)
# ---------------------------------------------------------------------------

_BASE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ops Dashboard — {{ title }}</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;background:#f8f9fa;color:#212529;line-height:1.5}
.container{max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:1.4rem;margin-bottom:12px}
h2{font-size:1.15rem;margin:16px 0 8px}
a{color:#0d6efd;text-decoration:none}
a:hover{text-decoration:underline}
.card{background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:12px;margin-bottom:10px}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.8rem;font-weight:600}
.badge-pass{background:#d1e7dd;color:#0f5132}
.badge-fail{background:#f8d7da;color:#842029}
.badge-unknown{background:#cff4fc;color:#055160}
.badge-open{background:#f8d7da;color:#842029}
.badge-resolved{background:#d1e7dd;color:#0f5132}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{padding:6px 8px;border:1px solid #dee2e6;text-align:left}
th{background:#e9ecef;font-weight:600}
.empty{color:#6c757d;font-style:italic}
nav{margin-bottom:16px;padding:8px 0;border-bottom:1px solid #dee2e6}
nav a{margin-right:12px;font-weight:500}
.status-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px}
.dot-active{background:#198754}.dot-inactive{background:#6c757d}.dot-stale{background:#ffc107}
@media(max-width:600px){.container{padding:8px}table{font-size:.8rem}th,td{padding:4px}}
</style>
</head>
<body>
<div class="container">
<nav><a href="/">Fleet</a> <a href="/issues">Issues</a> <a href="/standards">Standards</a></nav>
<h1>{{ title }}</h1>
{{ content|safe }}
</div>
</body>
</html>"""


def _render(title: str, content: str) -> str:
    """Render a page with base layout."""
    return render_template_string(
        _BASE, title=title, content=content
    )


def _dot(status: str) -> str:
    cls = {"active": "dot-active", "inactive": "dot-inactive"}.get(status, "dot-stale")
    return f'<span class="status-dot {cls}"></span>'


# ---------------------------------------------------------------------------
# Human routes
# ---------------------------------------------------------------------------


def _register_human_routes(app: Flask) -> None:
    @app.route("/")
    @require_auth
    def index():
        conn = _get_db()
        _ensure_db(conn)
        blogs = get_all_blogs(conn)
        attention = get_attention_items(conn)
        brands = {b["brand"] for b in blogs}

        rows = []
        for b in blogs:
            rows.append(
                f"<tr><td><a href='/blog/{b['blog_id']}'>{b['blog_id']}</a></td>"
                f"<td>{_dot(b['config_status'])}{b['brand']}</td>"
                f"<td>{b['config_status']}</td>"
                f"<td>{b.get('quality_grade','') or '-'}</td></tr>"
            )

        fail_count = len(attention.get("fail_checks", []))
        issue_count = len(attention.get("open_issues", []))
        stale_count = len(attention.get("stale_blogs", []))
        attention_html = ""
        if fail_count or issue_count or stale_count:
            parts = []
            if fail_count:
                parts.append(f"{fail_count} failed checks")
            if issue_count:
                parts.append(f"{issue_count} open issues")
            if stale_count:
                parts.append(f"{stale_count} stale blogs")
            attention_html = f'<div class="card badge badge-fail">⚠ {" · ".join(parts)}</div>'
        else:
            attention_html = '<p class="empty">No attention items — all clear.</p>'

        content = render_template_string(
            """<p>{{ total }} blogs tracked across {{ brands }} brands.</p>
<h2>Fleet Status</h2>
<table>
<tr><th>Blog ID</th><th>Brand</th><th>Config</th><th>Quality</th></tr>
{{ rows|safe }}
</table>
<h2>Attention Needed</h2>
{{ attention|safe }}""",
            total=len(brands),
            brands=len(brands),
            rows="\n".join(rows) or '<tr><td colspan="4" class="empty">No blogs synced</td></tr>',
            attention=attention_html,
        )
        return _render("Fleet Overview", content)

    @app.route("/blog/<blog_id>")
    @require_auth
    def blog_detail(blog_id: str):
        conn = _get_db()
        _ensure_db(conn)
        detail = get_blog_detail(conn, blog_id)
        if detail is None:
            return _render("Not Found", '<p class="empty">Blog not found.</p>'), 404

        b = detail["blog"]
        checks = detail["checks"]
        issues = detail["issues"]

        check_rows = []
        for c in checks:
            badge = f"badge-{c['status']}"
            check_rows.append(
                f"<tr><td>{c['check_name']}</td>"
                f"<td><span class='badge {badge}'>{c['status']}</span></td>"
                f"<td>{c.get('detail','')[:120]}</td>"
                f"<td>{c.get('checked_at','')}</td></tr>"
            )

        issue_rows = []
        for iss in issues:
            issue_rows.append(
                f'<div class="card"><strong>{iss["issue_id"]}</strong>: '
                f'{iss["symptom"][:100]} '
                f'<span class="badge badge-{iss["gsd_status"]}">{iss["gsd_status"]}</span></div>'
            )

        content = render_template_string(
            """<div class="card">
<h2>{{ blog_id }}</h2>
<table>
<tr><th>Brand</th><td>{{ brand }}</td></tr>
<tr><th>Config Status</th><td>{{ config_status }}</td></tr>
<tr><th>Theme</th><td>{{ theme }}</td></tr>
<tr><th>Domain</th><td>{{ domain }}</td></tr>
<tr><th>Consecutive Failures</th><td>{{ failures }}</td></tr>
</table>
</div>
<h2>Recent Checks ({{ check_count }})</h2>
<table>
<tr><th>Check</th><th>Status</th><th>Detail</th><th>At</th></tr>
{{ check_rows|safe }}
</table>
<h2>Related Issues ({{ issue_count }})</h2>
{{ issue_rows|safe }}""",
            blog_id=b["blog_id"],
            brand=b["brand"],
            config_status=b["config_status"],
            theme=b.get("theme", ""),
            domain=b.get("domain", ""),
            failures=b.get("consecutive_failures", 0),
            check_count=len(checks),
            check_rows="\n".join(check_rows) or '<tr><td colspan="4" class="empty">No checks run</td></tr>',
            issue_count=len(issues),
            issue_rows="\n".join(issue_rows) or '<p class="empty">No related issues</p>',
        )
        return _render(f"Blog: {blog_id}", content)

    @app.route("/issues")
    @require_auth
    def issues():
        conn = _get_db()
        _ensure_db(conn)
        rows = conn.execute(
            "SELECT * FROM known_issues ORDER BY category, issue_id"
        ).fetchall()
        open_issues = [r for r in rows if r["gsd_status"] == "open"]
        resolved_issues = [r for r in rows if r["gsd_status"] != "open"]

        def _issue_list(items):
            if not items:
                return '<p class="empty">None</p>'
            parts = []
            for iss in items:
                parts.append(
                    f'<div class="card"><strong>{iss["issue_id"]}</strong> '
                    f'<span class="badge badge-{iss["gsd_status"]}">{iss["gsd_status"]}</span> '
                    f'[{iss["category"]}] {iss["symptom"][:120]}</div>'
                )
            return "\n".join(parts)

        content = render_template_string(
            """<p>{{ open_count }} open issues, {{ resolved_count }} resolved.</p>
<h2>Open Issues</h2>
{{ open_rows|safe }}
<h2>Resolved Issues</h2>
{{ resolved_rows|safe }}""",
            open_count=len(open_issues),
            resolved_count=len(resolved_issues),
            open_rows=_issue_list(open_issues),
            resolved_rows=_issue_list(resolved_issues),
        )
        return _render("Issues", content)

    @app.route("/standards")
    @require_auth
    def standards():
        conn = _get_db()
        _ensure_db(conn)
        blogs = get_all_blogs(conn)
        brands = {}
        for b in blogs:
            brands.setdefault(b["brand"], []).append(b)

        sections = []
        for brand, brand_blogs in sorted(brands.items()):
            total = len(brand_blogs)
            with_theme = sum(1 for b in brand_blogs if b.get("theme"))
            with_domain = sum(1 for b in brand_blogs if b.get("domain"))
            sections.append(
                f'<div class="card"><strong>{brand}</strong> — {total} blogs<br>'
                f"Theme set: {with_theme}/{total} · "
                f"Domain set: {with_domain}/{total}</div>"
            )

        content = render_template_string(
            """<p>Standard compliance overview by brand.</p>
{{ brand_sections|safe }}""",
            brand_sections="\n".join(sections) or '<p class="empty">No data</p>',
        )
        return _render("Standards", content)


# ---------------------------------------------------------------------------
# JSON API routes
# ---------------------------------------------------------------------------


def _register_api_routes(app: Flask) -> None:
    @app.route("/api/fleet")
    @require_auth
    def api_fleet():
        conn = _get_db()
        _ensure_db(conn)
        return jsonify(get_all_blogs(conn))

    @app.route("/api/attention")
    @require_auth
    def api_attention():
        conn = _get_db()
        _ensure_db(conn)
        return jsonify(get_attention_items(conn))

    @app.route("/api/issues")
    @require_auth
    def api_issues():
        conn = _get_db()
        _ensure_db(conn)
        rows = conn.execute(
            "SELECT * FROM known_issues ORDER BY category, issue_id"
        ).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route("/api/standards")
    @require_auth
    def api_standards():
        conn = _get_db()
        _ensure_db(conn)
        blogs = get_all_blogs(conn)
        brands = {}
        for b in blogs:
            brand = b["brand"]
            if brand not in brands:
                brands[brand] = {"total": 0, "with_theme": 0, "with_domain": 0}
            brands[brand]["total"] += 1
            if b.get("theme"):
                brands[brand]["with_theme"] += 1
            if b.get("domain"):
                brands[brand]["with_domain"] += 1
        return jsonify(brands)

    @app.route("/api/run-checks", methods=["POST"])
    @require_auth
    def api_run_checks():
        conn = _get_db()
        _ensure_db(conn)
        blog_id = request.args.get("blog_id")
        blog_ids = [blog_id] if blog_id else None
        summary = run_all_checks(conn, blog_ids=blog_ids)
        return jsonify(summary)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["OPS_USER"] = os.environ.get("OPS_USER", _DEFAULT_USER)
    app.config["OPS_PASSWORD"] = os.environ.get("OPS_PASSWORD", _DEFAULT_PASSWORD)

    _register_human_routes(app)
    _register_api_routes(app)

    @app.teardown_appcontext
    def _close_db(exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5060, debug=False)
