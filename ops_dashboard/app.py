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
    CHECK_SEVERITY,
    get_all_blogs,
    get_attention_blogs,
    get_attention_blogs_aggregate,
    get_attention_items,
    get_blog_count,
    get_blog_detail,
    get_blog_site_path,
    get_blog_domain,
    get_blog_pipeline_path,
    get_conn,
    get_daily_summary,
    get_maintenance_checklist,
    get_maintenance_summary,
    get_blog_brand,
    get_blog_config_status,
    init_db,
    seed_known_issues,
    seed_maintenance_status,
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
    if get_blog_count(conn) == 0:
        sync_blog_lifecycle(conn)
        seed_known_issues(conn)
    # Phase 60: 정비 대상 블로그 시드 (기존 데이터에 maintenance_status 없으면 추가)
    seed_maintenance_status(conn)





# ---------------------------------------------------------------------------
# Unpause checklist builder
# ---------------------------------------------------------------------------


def _build_unpause_checklist(
    conn: sqlite3.Connection,
    blog_id: str,
    maintenance_checklist: list[dict],
) -> list[dict]:
    """Build the unpause checklist from maintenance results + blog-specific evidence.

    This is the human verification layer on top of M01~M10 auto-checks.
    Each item has: id, title, note, auto_status, evidence.
    """
    from ops_dashboard.db import get_blog_site_path, get_blog_domain, get_blog_pipeline_path
    
    # Index maintenance results by check_id
    m_map = {item["check_id"]: item for item in (maintenance_checklist or [])}

    def _m_status(check_id: str) -> str:
        item = m_map.get(check_id)
        if item:
            return item.get("status", "unknown")
        return "unknown"

    def _m_detail(check_id: str) -> str:
        item = m_map.get(check_id)
        if item:
            return item.get("detail", "")
        return ""

    # Blog-specific queries
    site_path = get_blog_site_path(conn, blog_id)
    domain = get_blog_domain(conn, blog_id)
    pipeline_path = get_blog_pipeline_path(conn, blog_id)

    checklist = [
        {
            "id": "U01",
            "title": "제목 CJK 누수 없음",
            "note": "한자/일본어/중국어가 제목에 섞여 있으면 검색 엔진 노출 불리",
            "auto_status": _m_status("M01"),
            "evidence": _m_detail("M01"),
        },
        {
            "id": "U02",
            "title": "이미지 정상 (URL 고유)",
            "note": "동일 featureimage 반복 사용 없음, R2 업로드 정상",
            "auto_status": _m_status("M02"),
            "evidence": _m_detail("M02"),
        },
        {
            "id": "U03",
            "title": "크로스링크 주제 일관",
            "note": "같은/인접 카테고리 링크만, 무관 카테고리 링크 없음",
            "auto_status": "needs_manual",
            "evidence": "M03 자동검사 미구현 — 에이전트가 content/posts/ 내부 링크 도메인 분석 필요",
        },
        {
            "id": "U04",
            "title": "본문 품질 게이트 통과",
            "note": "Q1(경험 허위), Q2(소스불명 수치), Q3(건강 효능 단정), Q4(제목-본문 불일치) 이슈 없음",
            "auto_status": _m_status("M04"),
            "evidence": _m_detail("M04"),
        },
        {
            "id": "U05",
            "title": "표준 (광고/테마) 준수",
            "note": "ADSENSE-GUIDE.md R01~R12 모두 통과, Blowfish 테마 표준",
            "auto_status": _m_status("M05"),
            "evidence": _m_detail("M05"),
        },
        {
            "id": "U06",
            "title": "금지어 미사용",
            "note": "좋은/최고의/강추/완전 좋 등 주관적 표현 없음",
            "auto_status": "needs_manual",
            "evidence": "M01~M10에 없음 — quality_checklist.yaml 정의 존재하나 curation 파이프라인 미적용",
        },
        {
            "id": "U07",
            "title": "H2/H3 구조 정상",
            "note": "최소 H2 3개 이상, H3 적절 배치, 단락 200자 초과",
            "auto_status": "needs_manual",
            "evidence": "M01~M10에 없음 — 프롬프트는 H2 구조 지시하나 미적용 글 존재 (writer.py:496 미검증)",
        },
        {
            "id": "U08",
            "title": "메타 (og:image, canonical, description)",
            "note": "og:image 200 OK, canonical 정상, description 존재",
            "auto_status": _m_status("M10"),
            "evidence": _m_detail("M10") + " (도메인 상태)",
        },
        {
            "id": "U09",
            "title": "URL 슬러그 정상",
            "note": "CJK/퍼센트인코딩 오염 없음, 적정 길이",
            "auto_status": _m_status("M01"),
            "evidence": _m_detail("M01") + " (슬러그는 제목에서 유도)",
        },
        {
            "id": "U10",
            "title": "토픽/키워드 잔량",
            "note": "active 키워드 충분, 유사 제목 재차단 없음",
            "auto_status": _m_status("M06"),
            "evidence": _m_detail("M06"),
        },
    ]

    return checklist


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
        maintenance_summary = get_maintenance_summary(conn)
        from ops_dashboard.db import get_daily_summary
        daily_summary = get_daily_summary(conn)

        summary = {
            "total": len(blogs),
            "active": sum(1 for b in blogs if b["config_status"] == "active"),
            "stale": len(attention.get("stale_blogs", [])),
            "issues": len(attention.get("open_issues", [])),
            "maintenance": sum(1 for b in blogs if b.get("maintenance_status") in ("awaiting", "in_progress")),
            "ready_to_resume": sum(1 for b in blogs if b.get("maintenance_status") == "ready"),
        }

        # 5-4: "주의 필요" 뷰 — 필터 파라미터 (기본: 전체)
        filter_brand = request.args.get("brand", "")
        filter_check = request.args.get("check", "")
        filter_severity = request.args.get("severity", "")
        # 서버사이드 페이지네이션
        try:
            page = max(1, int(request.args.get("page", "1")))
        except ValueError:
            page = 1
        page_size = 50
        attention_blogs_all = get_attention_blogs(
            conn,
            brand=filter_brand or None,
            check_name=filter_check or None,
            severity=filter_severity or None,
        )
        total_items = len(attention_blogs_all)
        total_pages = max(1, -(-total_items // page_size))  # ceil
        page = min(page, total_pages)
        start_idx = (page - 1) * page_size
        attention_blogs = attention_blogs_all[start_idx : start_idx + page_size]
        attention_agg = get_attention_blogs_aggregate(conn)
        check_severity_map = CHECK_SEVERITY

        # Part 6: 확장 준비도 지표
        from ops_dashboard.readiness import compute_readiness
        readiness = compute_readiness(conn)

        return render_template(
            "index.html",
            title="Fleet Overview",
            active="fleet",
            blogs=blogs,
            brands=len(brands),
            attention=attention,
            summary=summary,
            maintenance_summary=maintenance_summary,
            daily_summary=daily_summary,
            attention_blogs=attention_blogs,
            attention_agg=attention_agg,
            filter_brand=filter_brand,
            filter_check=filter_check,
            filter_severity=filter_severity,
            check_severity_map=check_severity_map,
            page=page,
            total_pages=total_pages,
            total_items=total_items,
            readiness=readiness,
        )

    @app.route("/blog/<blog_id>")
    @require_auth
    def blog_detail(blog_id: str):
        conn = _get_db()
        _ensure_db(conn)
        detail = get_blog_detail(conn, blog_id)
        if detail is None:
            return render_template("404.html", title="Not Found", active=""), 404

        maintenance_checklist = get_maintenance_checklist(conn, blog_id)
        unpause_checklist = _build_unpause_checklist(conn, blog_id, maintenance_checklist)

        return render_template(
            "blog.html",
            title=f"Blog: {blog_id}",
            active="fleet",
            blog=detail["blog"],
            checks=detail["checks"],
            issues=detail["issues"],
            maintenance_checklist=maintenance_checklist,
            unpause_checklist=unpause_checklist,
        )

    @app.route("/issues")
    @require_auth
    def issues():
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.db import get_open_known_issues
        issues = get_open_known_issues(conn)

        return render_template(
            "issues.html",
            title="Issues",
            active="issues",
            issues=issues,
        )

    @app.route("/standards")
    @require_auth
    def standards():
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.db import get_all_blogs
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
        from ops_dashboard.db import get_open_known_issues
        return jsonify(get_open_known_issues(conn))

    @app.route("/api/standards")
    @require_auth
    def api_standards():
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.db import get_all_blogs
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

    @app.route("/api/maintenance/status", methods=["POST"])
    @require_auth
    def api_maintenance_status():
        """정비 상태 변경: blog_id + maintenance_status"""
        from ops_dashboard.db import update_maintenance_status
        conn = _get_db()
        _ensure_db(conn)
        data = request.get_json(force=True)
        blog_id = data.get("blog_id")
        status = data.get("maintenance_status")
        if not blog_id or not status:
            return jsonify({"error": "blog_id and maintenance_status required"}), 400
        valid = ("none", "awaiting", "in_progress", "ready")
        if status not in valid:
            return jsonify({"error": f"Invalid status. Must be one of: {valid}"}), 400
        update_maintenance_status(conn, blog_id, status)
        return jsonify({"ok": True, "blog_id": blog_id, "maintenance_status": status})

    @app.route("/api/maintenance/checklist", methods=["POST"])
    @require_auth
    def api_maintenance_checklist_run():
        """특정 블로그의 정비 체크리스트 실행"""
        conn = _get_db()
        _ensure_db(conn)
        data = request.get_json(force=True)
        blog_id = data.get("blog_id")
        if not blog_id:
            return jsonify({"error": "blog_id required"}), 400
        from ops_dashboard.checks.maintenance import check_maintenance_checklist
        result = check_maintenance_checklist(conn, blog_id)
        return jsonify(result)

    @app.route("/api/daily-summary")
    @require_auth
    def api_daily_summary():
        """일일 알림 요약 데이터"""
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.db import get_daily_summary
        summary_date = request.args.get("date")
        return jsonify(get_daily_summary(conn, summary_date))

    @app.route("/api/readiness")
    @require_auth
    def api_readiness():
        """확장 준비도 지표 (Part 6)."""
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.readiness import compute_readiness
        return jsonify(compute_readiness(conn))


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
