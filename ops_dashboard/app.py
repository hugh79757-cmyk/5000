"""ops_dashboard.app — Flask web application for the ops dashboard.

Provides human-readable pages and a JSON API for the fleet health data.
All routes are protected by Basic Auth (OPS_USER/OPS_PASSWORD env vars).
"""
import logging
import os
import sqlite3
import time
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, Response, g, jsonify, render_template, request

from ops_dashboard.checks import run_all_checks
from ops_dashboard.db import (
    CHECK_SEVERITY,
    get_all_blogs,
    get_attention_blogs,
    get_attention_blogs_aggregate,
    get_attention_items,
    get_blog_brand,
    get_blog_config_status,
    get_blog_count,
    get_blog_detail,
    get_blog_domain,
    get_blog_pipeline_path,
    get_blog_site_path,
    get_blogs_by_brand,
    get_conn,
    get_daily_summary,
    get_maintenance_checklist,
    get_maintenance_summary,
    init_db,
    seed_known_issues,
    seed_maintenance_status,
    sync_blog_lifecycle,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# YAML 자동 싱크 — 파일 mtime 기반 (진실 소스: config/blogs.d/*.yaml)
# ---------------------------------------------------------------------------

_BLOGS_D_DIR = Path(__file__).resolve().parent.parent / "config" / "blogs.d"
_YAML_SYNC_MARKER = Path("/tmp/ops_yaml_sync_marker")

def _yaml_dirty() -> bool:
    """YAML 파일이 마지막 싱크 시점보다 새로 수정됐는지 확인.

    마커 파일이 없으면 최초 싱크로 간주 (True 반환).
    """
    try:
        last_sync = _YAML_SYNC_MARKER.stat().st_mtime
    except FileNotFoundError:
        return True  # 마커 없음 → 최초 싱크 필요
    if not _BLOGS_D_DIR.is_dir():
        return False
    for yf in _BLOGS_D_DIR.glob("*.yaml"):
        if yf.name.endswith(".bak") or yf.name.startswith("."):
            continue
        try:
            if yf.stat().st_mtime > last_sync:
                return True
        except OSError:
            continue
    return False

def _touch_sync_marker() -> None:
    """마지막 싱크 시점 마커를 현재 시각으로 갱신."""
    _YAML_SYNC_MARKER.touch()

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_auth_credentials() -> tuple[str, str]:
    """Read OPS_USER / OPS_PASSWORD from environment.

    Fail-closed: env var가 없으면 서비스 시작 거부.
    """
    user = os.environ.get("OPS_USER")
    password = os.environ.get("OPS_PASSWORD")
    if not user or not password:
        raise RuntimeError(
            "CRITICAL: OPS_USER and OPS_PASSWORD environment variables are required. "
            "Service cannot start without credentials. "
            "Set them in .env or launchd plist."
        )
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
    """DB 스키마 초기화 + 시드 데이터.

    최초 요청 시 1회 실행. YAML→DB 싱크는 _sync_yaml_if_needed()에서
    mtime 체크 후 별도 처리하므로 여기선 호출하지 않음.
    """
    init_db(conn)
    if get_blog_count(conn) == 0:
        seed_known_issues(conn)
    seed_maintenance_status(conn)


def _event_view(event: dict) -> dict:
    """표시 계층 분류 (DB 쓰기 없음 — Phase69-C M4 계약).

    - reason=no_topics + problem_id=P01 + retryable=0 → WAITING_FOR_CANDIDATES
      (후보 대기 = 실행 상태, incident lifecycle state는 open 유지)
    - incident_key가 NULL/빈 값 → LEGACY_UNMERGED (임의 hash 병합 금지)
    - pipeline 빈 값 → UNKNOWN
    """
    view = dict(event)
    if (
        event.get("reason") == "no_topics"
        and event.get("problem_id") == "P01"
        and event.get("retryable") == 0
    ):
        view["execution_status"] = "WAITING_FOR_CANDIDATES"
    else:
        view["execution_status"] = "OPEN" if event.get("state") == "open" else "CLOSED"
    view["incident_label"] = "LEGACY_UNMERGED" if not event.get("incident_key") else "INCIDENT"
    view["pipeline_label"] = event.get("pipeline") or "UNKNOWN"
    return view


def _sync_yaml_if_needed(conn: sqlite3.Connection) -> bool:
    """YAML이 새로 수정됐으면 blog_lifecycle 동기화.

    반환: True = 싱크 실행됨, False = 변경 없음.
    """
    if not _yaml_dirty():
        return False
    count = sync_blog_lifecycle(conn)
    _touch_sync_marker()
    if count:
        logger.info("[yaml-sync] %d개 블로그 갱신 (YAML mtime 변경)", count)
    return True





# ---------------------------------------------------------------------------
# Category Matrix helper (Phase 64-08)
# ---------------------------------------------------------------------------

def _category_counts(blog_id: str) -> dict:
    """Return C/S/L/P/V counts for a blog from latest failed checks.
    
    Uses db._category_counts which queries check_results, maps check_name/rule_id
    to category via get_rule_category(), and checks staleness (>48h).
    """
    from ops_dashboard.db import get_conn, _category_counts as _db_category_counts
    conn = get_conn()
    try:
        return _db_category_counts(conn, blog_id)
    finally:
        conn.close()


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

    # 베이크된 무관 크로스링크 이슈 (INC-CL): 코드 필터는 7e2bd2312로
    # 신규 생성을 차단했지만 기존 발행 포스트의 무관 링크는 재개 시
    # 재렌더로 정리해야 한다. open INC-CL 이슈가 있으면 재개 조건에 추가.
    baked_inc_cl_rows = conn.execute("""
        SELECT issue_id, symptom FROM known_issues
        WHERE gsd_status = 'open'
          AND issue_id LIKE 'INC-CL%'
          AND (',' || blog_ids || ',') LIKE ?
    """, (f"%,{blog_id},",)).fetchall()

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

    # 베이크드 크로스링크 재렌더 정리 (INC-CL open 이슈가 있는 블로그만)
    for idx, inc in enumerate(baked_inc_cl_rows, start=1):
        checklist.append({
            "id": f"U1{0 + idx}",
            "title": "베이크된 무관 크로스링크 재렌더 정리",
            "note": "코드 필터(7e2bd2312)로 신규 생성은 차단됨. 기존 발행 포스트의 CROSS_GRAPH 밖 링크는 재개 시 새 로직으로 재렌더해 정리",
            "auto_status": "needs_manual",
            "evidence": f"{inc['issue_id']}: {inc['symptom'][:120]}",
        })

    return checklist


# ---------------------------------------------------------------------------
# Human routes
# ---------------------------------------------------------------------------


def _register_human_routes(app: Flask) -> None:
    @app.route("/lookbook")
    @require_auth
    def lookbook():
        # 룩북 링크(index.html) 대상 — markdown 파일 그대로 서빙, 기능 없음
        from flask import send_file
        p = Path(__file__).resolve().parent.parent / "docs" / "lookbook" / "ERROR_LOOKBOOK.md"
        return send_file(p, mimetype="text/plain") if p.exists() else ("lookbook not found", 404)

    @app.route("/")
    @require_auth
    def index():
        conn = _get_db()
        _ensure_db(conn)
        blogs = get_all_blogs(conn)
        
        # Phase 64-08: Category Matrix (C/S/L/P/V) per blog for summary view
        category_matrix = {}
        for blog in blogs:
            bid = blog["blog_id"]
            matrix = _category_counts(bid)
            category_matrix[bid] = matrix
        
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

        # Fleet Status 표에도 brand 필터 적용 (주의 필요 테이블과 동일하게)
        if filter_brand:
            fleet_blogs = get_blogs_by_brand(conn, filter_brand)
        else:
            fleet_blogs = blogs

        # 필터 적용 시 summary 재계산
        if filter_brand:
            fleet_summary = {
                "total": len(fleet_blogs),
                "active": sum(1 for b in fleet_blogs if b["config_status"] == "active"),
                "stale": len(attention.get("stale_blogs", [])),
                "issues": len(attention.get("open_issues", [])),
                "maintenance": sum(1 for b in fleet_blogs if b.get("maintenance_status") in ("awaiting", "in_progress")),
                "ready_to_resume": sum(1 for b in fleet_blogs if b.get("maintenance_status") == "ready"),
            }
        else:
            fleet_summary = summary

        return render_template(
            "index.html",
            title="Fleet Overview",
            active="fleet",
            blogs=fleet_blogs,
            brands=len(brands),
            attention=attention,
            summary=fleet_summary,
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
            all_brands=attention_agg.get("all_brands", {}),
            all_check_names=attention_agg.get("all_check_names", {}),
            all_severities=attention_agg.get("all_severities", {}),
            category_matrix=category_matrix,
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

    @app.route("/feedback")
    @app.route("/rule-feedback")
    @require_auth
    def feedback():
        """Rule feedback read-only view — reads logs/rule_feedback.jsonl."""
        since = request.args.get("since", "")
        status_param = request.args.get("status", "open")
        # status=all -> no filter, else filter by value
        status_filter = None if status_param == "all" else status_param
        try:
            from shared.rule_feedback import read_feedback
            items = read_feedback(
                since_days=since if since else None,
                status=status_filter,
            )
        except Exception:
            items = []
        return render_template(
            "feedback.html",
            title="Rule Feedback",
            active="feedback",
            items=items,
            status_filter=status_param,
            since_filter=since,
        )

    @app.route("/publish-errors")
    @require_auth
    def publish_errors():
        conn = _get_db()
        _ensure_db(conn)
        from shared.publish_error_events import (
            get_publish_error_events,
            get_publish_error_events_count,
            get_publish_error_summary,
        )
        try:
            page = max(1, int(request.args.get("page", "1")))
        except ValueError:
            page = 1
        try:
            per_page = max(1, min(int(request.args.get("per_page", "50")), 200))
        except ValueError:
            per_page = 50
        total = get_publish_error_events_count(conn)
        total_pages = max(1, -(-total // per_page))
        page = min(page, total_pages)
        events = get_publish_error_events(
            conn, limit=per_page, offset=(page - 1) * per_page
        )
        waiting_count = conn.execute(
            "SELECT COUNT(*) FROM publish_error_events "
            "WHERE reason='no_topics' AND problem_id='P01' AND retryable=0"
        ).fetchone()[0]
        return render_template(
            "publish_errors.html",
            title="Operational Errors",
            active="publish-errors",
            summary=get_publish_error_summary(conn),
            events=[_event_view(e) for e in events],
            waiting_count=waiting_count,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )

    @app.route("/candidate-state")
    @require_auth
    def candidate_state():
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.db import (
            get_availability_summary,
            get_open_root_incidents,
            get_pipeline_availability,
            get_resource_health_all,
            get_retry_blocked_count,
        )
        from ops_dashboard.db import get_all_blogs
        blogs = get_all_blogs(conn)
        return render_template(
            "candidate_state.html",
            title="Candidate State",
            active="candidate-state",
            blogs=blogs,
            availability=get_pipeline_availability(),
            summary=get_availability_summary(),
            roots=get_open_root_incidents(),
            resources=get_resource_health_all(),
            retry_blocked=get_retry_blocked_count(),
        )

    @app.route("/standards")
    @require_auth
    def standards():
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.db import get_all_blogs
        from ops_dashboard.registry.rules import RULES
        from shared.standards_loader import (
            get_global_standard,
            get_brand_standards_summary,
        )
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
            rules=[
                {
                    "id": e.id,
                    "target": e.target,
                    "severity": e.severity,
                    "action": e.action,
                    "bucket": e.bucket,
                }
                for e in RULES
            ],
            global_standard=get_global_standard(),
            brand_standards_summary=get_brand_standards_summary(),
            compliance=brands,
        )

    @app.route("/schema")
    @require_auth
    def schema_overview():
        from ops_dashboard.views.schema_view import render_schema_summary
        ctx = render_schema_summary()
        return render_template("schema.html", title="Schema", active="schema", **ctx)

    @app.route("/schema/<blog_id>")
    @require_auth
    def schema_detail(blog_id: str):
        import json as _json

        from ops_dashboard.views.schema_view import render_schema_detail
        ctx = render_schema_detail(blog_id)
        if not ctx:
            return f"Unknown blog: {blog_id}", 404
        raw_pretty = _json.dumps(
            _json.loads(ctx["row"]["raw_schema"]), ensure_ascii=False,
            indent=2, sort_keys=True)
        return render_template("schema_detail.html", title=f"Schema — {blog_id}",
                               active="schema", raw_pretty=raw_pretty, **ctx)


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

    @app.route("/api/rollups")
    @require_auth
    def api_rollups():
        conn = _get_db()
        _ensure_db(conn)
        blog_id = request.args.get("blog_id")
        days = request.args.get("days", default=30, type=int)
        from ops_dashboard.db import get_check_rollups
        return jsonify(get_check_rollups(conn, blog_id=blog_id or None, days=days))

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

    @app.route("/api/publish-errors")
    @require_auth
    def api_publish_errors():
        conn = _get_db()
        _ensure_db(conn)
        from shared.publish_error_events import (
            get_publish_error_events,
            get_publish_error_events_count,
            get_publish_error_summary,
        )
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int) or 0
        blog_id = request.args.get("blog_id", "")
        severity = request.args.get("severity", "")
        state = request.args.get("state", "")
        return jsonify({
            "summary": get_publish_error_summary(conn),
            "total": get_publish_error_events_count(
                conn, blog_id=blog_id, severity=severity, state=state
            ),
            "events": [
                _event_view(e)
                for e in get_publish_error_events(
                    conn,
                    limit=limit,
                    offset=offset,
                    blog_id=blog_id,
                    severity=severity,
                    state=state,
                )
            ],
        })

    @app.route("/api/candidate-state")
    @require_auth
    def api_candidate_state():
        """PR3 — 후보 가용성 상태 (SSOT: ops.db pipeline_availability).

        응답 구조(하위 호환: 기존 필드에 추가만 함):
          summary: state별 COUNT
          availability: pipeline_availability 행 목록
          roots: open root incident 목록 (P33 등)
          resources: resource_health 행 목록
          retry_blocked: retry_blocked=1 open incident 수
        """
        from ops_dashboard.db import (
            get_availability_summary,
            get_open_root_incidents,
            get_pipeline_availability,
            get_resource_health_all,
            get_retry_blocked_count,
        )
        return jsonify({
            "summary": get_availability_summary(),
            "availability": get_pipeline_availability(),
            "roots": get_open_root_incidents(),
            "resources": get_resource_health_all(),
            "retry_blocked": get_retry_blocked_count(),
        })

    @app.route("/api/maintenance/checklist", methods=["POST"])
    @require_auth
    def api_maintenance_checklist_run():
        """특정 블로그의 정비 체크리스트 실행


        JSON body({"blog_id": "..."}) 또는 form data(blog_id=...) 모두 수용.
        JS fetch 호출(application/json)과 HTML form 제출을 모두 지원.
        """
        conn = _get_db()
        _ensure_db(conn)
        # JSON 우선, 없으면 form에서 추출 (JS fetch + HTML form 겸용)
        data = request.get_json(silent=True) or request.form
        blog_id = (data.get("blog_id") if isinstance(data, dict) else None)
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

    @app.route("/api/registry")
    @require_auth
    def api_registry():
        """통합 레지스트리 뷰 (Phase 69 W5-3): 규칙 + 오류선언 + 실데이터를 단일 스키마로 노출.

        쿼리 파라미터:
            blog_id — 지정 시 해당 블로그의 check_results만 대상으로 필터링.
                      미지정 시 모든 블로그 대상 (기존 동작).
        """
        from flask import request as _request
        blog_id = _request.args.get("blog_id") or None
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.db import get_registry_view
        return jsonify(get_registry_view(conn, blog_id=blog_id))

    @app.route("/api/category-matrix")
    @require_auth
    def api_category_matrix():
        """C/S/L/P/V 카테고리별 위반 카운트 매트릭스 (Phase 64-08).

        쿼리 파라미터:
            blog_id — 필수, 대상 블로그 ID (예: health-hugo)

        응답:
            {
                "blog_id": "health-hugo",
                "by_category": {"C": 0, "S": 0, "L": 1, "P": 0, "V": 0},
                "total": 1,
                "stale": false
            }
        """
        blog_id = request.args.get("blog_id")
        if not blog_id:
            return jsonify({"error": "blog_id required"}), 400
        
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.db import _category_counts as _db_category_counts
        result = _db_category_counts(conn, blog_id)
        result["blog_id"] = blog_id
        return jsonify(result)

    @app.route("/api/sync-yaml", methods=["POST"])
    @require_auth
    def api_sync_yaml():
        """YAML → blog_lifecycle 강제 동기화 (수동 백업).

        mtime 체크와 무관하게 즉시 sync 실행. YAML 편집 후 대시보드 반영이
        지연될 때 사용. before_request의 자동 sync와 동일한 함수를 호출.
        """
        conn = _get_db()
        _ensure_db(conn)
        count = sync_blog_lifecycle(conn)
        _touch_sync_marker()
        return jsonify({"synced": count, "status": "ok"})

    @app.route("/api/feedback")
    @require_auth
    def api_feedback():
        """Rule feedback JSON — reads logs/rule_feedback.jsonl, missing file -> []."""
        since = request.args.get("since", "")
        status = request.args.get("status")
        try:
            from shared.rule_feedback import read_feedback
            items = read_feedback(
                since_days=since if since else None,
                status=status,
            )
        except Exception:
            items = []
        return jsonify(items)

    @app.route("/api/pending-fixes")
    @require_auth
    def api_pending_fixes():
        """자동수정 파괴등급 영속 승인 큐 조회 (SC-4).

        쿼리 파라미터: blog_id(선택), status(선택). 미지정 시 active(proposed/
        approved/executing) 행을 최신순으로 노출하고 resolved/failed 이력을 함께
        확인하려면 status=all 또는 개별 status 를 지정한다.
        """
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.db import list_pending_fixes
        blog_id = request.args.get("blog_id") or None
        status = request.args.get("status")
        status = None if status == "all" else status
        rows = list_pending_fixes(conn, blog_id=blog_id, status=status)
        # status 미지정 시 active 우선 → 상단 정렬
        if status is None:
            _order = {"proposed": 0, "approved": 1, "executing": 2,
                      "resolved": 3, "failed": 4, "rejected": 5}
            rows.sort(key=lambda r: (_order.get(r["status"], 9), -r["id"]))
        return jsonify({"count": len(rows), "items": rows})

    @app.route("/api/pending-fixes/<int:fix_id>/approve", methods=["POST"])
    @require_auth
    def api_pending_fix_approve(fix_id: int):
        """승인 실행 (SC-4 단일 엔드포인트): proposed 행 → fixer 실행 → 재배포 → 재검사.

        dispatcher.execute_pending_fix 를 lazy import 로 호출 (실행 시점에만 무거운
        dispatcher 의존 로드). 승인 게이트 통과 후 호출되므로 redeploy=True (파괴적
        재배포 = 사람 승인 대체). 실패 시 상태는 failed 로 전이되고 에러를 JSON 으로 반환.
        """
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.db import get_pending_fix
        row = get_pending_fix(conn, fix_id)
        if not row:
            return jsonify({"ok": False, "msg": "pending_fixes 행 없음"}), 404
        try:
            from dispatcher import execute_pending_fix
            from ops_dashboard.db import DB_PATH
            result = execute_pending_fix(conn, fix_id, redeploy=True,
                                         ops_db_path=str(DB_PATH))
        except Exception as e:
            try:
                from ops_dashboard.db import set_pending_fix_status
                set_pending_fix_status(conn, fix_id, "failed",
                                       diff_ref=f"승인 실행 예외: {e}")
            except Exception:
                pass
            return jsonify({"ok": False, "msg": f"승인 실행 실패: {e}"}), 500
        return jsonify({"ok": result["ok"], **result})

    @app.route("/api/table-quality")
    @require_auth
    def api_table_quality():
        """CUAP 비교표 품질 — column_count + empty_ratio 모니터링 (TABLE_QUALITY).

        쿼리: blog(선택) — 지정 시 해당 블로그만 반환.
        응답: {count, warning, pass, items: run_check() 결과}
        """
        from ops_dashboard.checks.table_quality import run_check
        blog = request.args.get("blog") or request.args.get("blog_id")
        items = run_check()
        if blog:
            items = [r for r in items if r.get("blog_id") == blog]
        warned = [r for r in items if r.get("result") == "warning"]
        passed = [r for r in items if r.get("result") == "pass"]
        return jsonify({"count": len(items), "warning": len(warned), "pass": len(passed), "items": items})

    @app.route("/api/pending-fixes/<int:fix_id>/reject", methods=["POST"])
    @require_auth
    def api_pending_fix_reject(fix_id: int):
        """승인 거부: proposed 행을 rejected 로 전이 (fixer 실행 없음)."""
        conn = _get_db()
        _ensure_db(conn)
        from ops_dashboard.db import get_pending_fix, set_pending_fix_status
        row = get_pending_fix(conn, fix_id)
        if not row:
            return jsonify({"ok": False, "msg": "pending_fixes 행 없음"}), 404
        if row["status"] != "proposed":
            return jsonify({"ok": False,
                            "msg": f"상태 {row['status']!r} 에서 거부 불가 (proposed 만 허용)"}), 400
        set_pending_fix_status(conn, fix_id, "rejected",
                               resolved_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return jsonify({"ok": True, "fix_id": fix_id, "status": "rejected"})


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
    app.config["OPS_USER"] = os.environ.get("OPS_USER") or ""
    app.config["OPS_PASSWORD"] = os.environ.get("OPS_PASSWORD") or ""

    _register_human_routes(app)
    _register_api_routes(app)

    @app.before_request
    def _before_request_yaml_sync():
        """매 요청 전 YAML mtime 확인 → 변경됐으면 blog_lifecycle 동기화.

        진실 소스(config/blogs.d/*.yaml)와 DB의 config_status 일치를 유지.
       マー커 파일(/tmp/ops_yaml_sync_marker)로 마지막 sync 시점 추적.
        """
        conn = _get_db()
        _ensure_db(conn)
        _sync_yaml_if_needed(conn)

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
