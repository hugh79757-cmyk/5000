"""ops_dashboard.app — Flask web application for the ops dashboard.

Provides human-readable pages and a JSON API for the fleet health data.
All routes are protected by Basic Auth (OPS_USER/OPS_PASSWORD env vars).
"""
import logging
import os
import sqlite3
from functools import wraps

from flask import Flask, Response, g, jsonify, render_template, request

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

        summary = {
            "total": len(blogs),
            "active": sum(1 for b in blogs if b["config_status"] == "active"),
            "stale": len(attention.get("stale_blogs", [])),
            "issues": len(attention.get("open_issues", [])),
        }

        return render_template(
            "index.html",
            title="Fleet Overview",
            active="fleet",
            blogs=blogs,
            brands=len(brands),
            attention=attention,
            summary=summary,
        )

    @app.route("/blog/<blog_id>")
    @require_auth
    def blog_detail(blog_id: str):
        conn = _get_db()
        _ensure_db(conn)
        detail = get_blog_detail(conn, blog_id)
        if detail is None:
            return render_template("404.html", title="Not Found", active=""), 404

        return render_template(
            "blog.html",
            title=f"Blog: {blog_id}",
            active="fleet",
            blog=detail["blog"],
            checks=detail["checks"],
            issues=detail["issues"],
        )

    @app.route("/issues")
    @require_auth
    def issues():
        conn = _get_db()
        _ensure_db(conn)
        rows = conn.execute(
            "SELECT * FROM known_issues ORDER BY category, issue_id"
        ).fetchall()

        return render_template(
            "issues.html",
            title="Issues",
            active="issues",
            issues=[dict(r) for r in rows],
        )

    @app.route("/standards")
    @require_auth
    def standards():
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

        return render_template(
            "standards.html",
            title="Standards",
            active="standards",
            rules=[],
            compliance=brands,
        )


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

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html", title="Not Found", active=""), 404

    @app.teardown_appcontext
    def _close_db(exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5060, debug=False)
